"""
Google Sheets 헬퍼 함수

- 시트 자동 생성
- 아카이브 관리
- append-only 쓰기
"""

import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from .config import (
    SHEET_HEADERS,
    MAX_ROWS_PER_SHEET,
    ARCHIVE_THRESHOLD_RATIO,
    ROWS_TO_KEEP_AFTER_ARCHIVE,
    HISTORY_OPUS_INPUT_SHEET,
    PENDING_TARGET_COUNT,
    ERA_ORDER,
    ERAS,
    get_era_sheet_name,
    get_archive_sheet_name,
)


class SheetsSaveError(Exception):
    """Google Sheets 저장 실패 예외"""
    pass


class SheetsReadError(Exception):
    """Google Sheets 읽기 실패 예외"""
    pass


def ensure_sheet_exists(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    headers: Optional[List[str]] = None
) -> bool:
    """
    시트가 없으면 자동 생성 (헤더 포함)

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        sheet_name: 시트(탭) 이름
        headers: 헤더 리스트 (없으면 빈 시트 생성)

    Returns:
        True: 새로 생성됨, False: 이미 존재
    """
    try:
        # 1) 기존 시트 목록 확인
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()

        existing_sheets = [
            sheet['properties']['title']
            for sheet in spreadsheet.get('sheets', [])
        ]

        if sheet_name in existing_sheets:
            print(f"[HISTORY] 시트 '{sheet_name}' 이미 존재")
            return False

        # 2) 시트 생성
        requests = [{
            "addSheet": {
                "properties": {
                    "title": sheet_name,
                }
            }
        }]

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests}
        ).execute()

        print(f"[HISTORY] 시트 '{sheet_name}' 생성 완료")

        # 3) 헤더 추가
        if headers:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                body={"values": [headers]}
            ).execute()
            print(f"[HISTORY] 시트 '{sheet_name}' 헤더 추가 완료")

        return True

    except Exception as e:
        print(f"[HISTORY] 시트 생성 실패 '{sheet_name}': {e}")
        raise SheetsSaveError(f"시트 생성 실패: {e}")


def ensure_era_sheets(service, spreadsheet_id: str, era: str) -> Dict[str, bool]:
    """
    시대별 수집/후보 시트 자동 생성 (RAW, CANDIDATES만)

    OPUS_INPUT은 단일 통합 시트(HISTORY_OPUS_INPUT)로 별도 관리

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        era: 시대 키 (예: "GOJOSEON")

    Returns:
        {"RAW": True/False, "CANDIDATES": True/False}
    """
    results = {}

    # RAW, CANDIDATES만 시대별로 생성
    for prefix in ["RAW", "CANDIDATES"]:
        sheet_name = get_era_sheet_name(prefix, era)
        headers = SHEET_HEADERS.get(prefix, [])

        try:
            created = ensure_sheet_exists(
                service, spreadsheet_id, sheet_name, headers
            )
            results[prefix] = created
        except Exception as e:
            print(f"[HISTORY] 시트 생성 오류 ({sheet_name}): {e}")
            results[prefix] = False

    return results


def ensure_history_opus_input_sheet(service, spreadsheet_id: str) -> bool:
    """
    단일 통합 OPUS_INPUT 시트 자동 생성 (HISTORY_OPUS_INPUT)

    모든 시대의 OPUS 입력이 여기에 누적됨

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID

    Returns:
        True: 새로 생성됨, False: 이미 존재
    """
    headers = SHEET_HEADERS.get("OPUS_INPUT", [])

    try:
        created = ensure_sheet_exists(
            service, spreadsheet_id, HISTORY_OPUS_INPUT_SHEET, headers
        )
        return created
    except Exception as e:
        print(f"[HISTORY] OPUS_INPUT 시트 생성 오류: {e}")
        return False


def get_sheet_row_count(service, spreadsheet_id: str, sheet_name: str) -> int:
    """
    시트의 데이터 행 수 반환 (헤더 제외)

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        sheet_name: 시트 이름

    Returns:
        데이터 행 수 (헤더 제외)
    """
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:A"
        ).execute()

        rows = result.get('values', [])
        # 헤더 제외
        return max(0, len(rows) - 1)

    except Exception as e:
        print(f"[HISTORY] 행 수 조회 실패 ({sheet_name}): {e}")
        return 0


def check_archive_needed(service, spreadsheet_id: str, era: str) -> bool:
    """
    아카이브 필요 여부 확인

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        era: 시대 키

    Returns:
        아카이브 필요 여부
    """
    raw_sheet = get_era_sheet_name("RAW", era)
    row_count = get_sheet_row_count(service, spreadsheet_id, raw_sheet)

    threshold = int(MAX_ROWS_PER_SHEET * ARCHIVE_THRESHOLD_RATIO)

    if row_count >= threshold:
        print(f"[HISTORY] 아카이브 필요: {raw_sheet} ({row_count}/{MAX_ROWS_PER_SHEET})")
        return True

    return False


def archive_old_rows(
    service,
    spreadsheet_id: str,
    era: str
) -> Dict[str, Any]:
    """
    오래된 행을 아카이브 시트로 이동

    절차:
    1. {ERA}_RAW 시트에서 최신 N개 제외한 행 읽기
    2. {ERA}_ARCHIVE_{YEAR} 시트로 복사
    3. 원본에서 해당 행 삭제

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        era: 시대 키

    Returns:
        {"archived": 아카이브된 행 수, "archive_sheet": 아카이브 시트 이름}
    """
    result = {
        "archived": 0,
        "archive_sheet": "",
        "error": None,
    }

    try:
        raw_sheet = get_era_sheet_name("RAW", era)

        # 1) 전체 데이터 읽기 (헤더 포함)
        response = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{raw_sheet}!A:Z"
        ).execute()

        all_rows = response.get('values', [])

        if len(all_rows) <= 1:
            print(f"[HISTORY] 아카이브 불필요: 데이터 없음")
            return result

        headers = all_rows[0]
        data_rows = all_rows[1:]

        # 유지할 최신 행 수
        rows_to_archive = data_rows[:-ROWS_TO_KEEP_AFTER_ARCHIVE]
        rows_to_keep = data_rows[-ROWS_TO_KEEP_AFTER_ARCHIVE:]

        if not rows_to_archive:
            print(f"[HISTORY] 아카이브 불필요: 충분히 적은 데이터")
            return result

        # 2) 아카이브 시트 생성/확인
        year = datetime.now(timezone.utc).year
        archive_sheet = get_archive_sheet_name(era, year)

        ensure_sheet_exists(service, spreadsheet_id, archive_sheet, headers)
        result["archive_sheet"] = archive_sheet

        # 3) 아카이브 시트에 데이터 추가
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{archive_sheet}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows_to_archive}
        ).execute()

        result["archived"] = len(rows_to_archive)
        print(f"[HISTORY] {len(rows_to_archive)}개 행 아카이브 완료 → {archive_sheet}")

        # 4) 원본 시트 정리 (헤더 + 유지할 데이터만 남김)
        # 전체 삭제 후 다시 쓰기 (가장 안전한 방법)
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"{raw_sheet}!A:Z"
        ).execute()

        new_data = [headers] + rows_to_keep
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{raw_sheet}!A1",
            valueInputOption="RAW",
            body={"values": new_data}
        ).execute()

        print(f"[HISTORY] 원본 시트 정리 완료: {len(rows_to_keep)}개 행 유지")

    except Exception as e:
        result["error"] = str(e)
        print(f"[HISTORY] 아카이브 실패: {e}")

    return result


def append_rows(
    service,
    spreadsheet_id: str,
    range_a1: str,
    rows: List[List[Any]],
    max_retries: int = 3
) -> bool:
    """
    Google Sheets에 행 추가 (재시도 로직 포함)

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        range_a1: A1 표기법 범위 (예: "GOJOSEON_RAW!A1")
        rows: 추가할 행 데이터
        max_retries: 최대 재시도 횟수

    Returns:
        성공 여부

    Raises:
        SheetsSaveError: 모든 재시도 실패 시
    """
    body = {"values": rows}
    last_error = None

    for attempt in range(max_retries):
        try:
            result = service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_a1,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()

            updated_range = result.get("updates", {}).get("updatedRange", "")
            updated_rows = result.get("updates", {}).get("updatedRows", 0)
            print(f"[HISTORY] Sheets append 성공: {updated_range}, {updated_rows}행 추가")
            return True

        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            transient_errors = ['500', '502', '503', '504', 'timeout', 'backend error']
            is_transient = any(p in error_str for p in transient_errors)

            if is_transient and attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                print(f"[HISTORY] Sheets append 재시도 ({attempt + 1}/{max_retries}), {wait_time}초 대기: {e}")
                time.sleep(wait_time)
            else:
                print(f"[HISTORY] Sheets append 실패 (최종): {e}")
                raise SheetsSaveError(f"시트 저장 실패 ({range_a1}): {e}")

    raise SheetsSaveError(f"시트 저장 실패 ({range_a1}): {last_error}")


def read_recent_hashes(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    hash_column: str = "I",
    limit: int = 500
) -> set:
    """
    중복 확인용 최근 해시값 읽기

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        sheet_name: 시트 이름
        hash_column: 해시가 저장된 열 (기본: I열)
        limit: 읽을 최대 행 수

    Returns:
        해시값 집합
    """
    try:
        # 최근 N개 행의 해시만 읽기
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!{hash_column}:{hash_column}"
        ).execute()

        rows = result.get('values', [])

        # 헤더 제외, 최근 limit개
        data_rows = rows[1:][-limit:] if len(rows) > 1 else []

        hashes = set()
        for row in data_rows:
            if row and row[0]:
                hashes.add(row[0])

        print(f"[HISTORY] {sheet_name}에서 {len(hashes)}개 해시 로드")
        return hashes

    except Exception as e:
        print(f"[HISTORY] 해시 읽기 실패 ({sheet_name}): {e}")
        return set()


def get_series_progress(service, spreadsheet_id: str) -> Dict[str, Any]:
    """
    시리즈 진행 상황 조회

    Returns:
        {
            "total_episodes": 전체 에피소드 수,
            "pending_count": PENDING 상태 에피소드 수,
            "last_episode": 마지막 에피소드 번호,
            "current_era": 현재 진행 중인 시대,
            "current_era_episode": 현재 시대의 마지막 에피소드 번호,
            "current_era_total": 현재 시대의 총 에피소드 수 (AI 결정),
            "all_rows": 전체 데이터 (분석용)
        }
    """
    result = {
        "total_episodes": 0,
        "pending_count": 0,
        "last_episode": 0,
        "current_era": None,
        "current_era_episode": 0,
        "current_era_total": 0,
        "all_rows": [],
    }

    try:
        # 전체 데이터 읽기
        # 헤더: episode, era, era_episode, total_episodes, era_name, title, ...
        response = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{HISTORY_OPUS_INPUT_SHEET}!A:L"
        ).execute()

        rows = response.get('values', [])

        if len(rows) <= 1:
            # 헤더만 있거나 비어있음
            return result

        headers = rows[0]
        data_rows = rows[1:]

        result["total_episodes"] = len(data_rows)
        result["all_rows"] = data_rows

        # 컬럼 인덱스 찾기
        col_idx = {h: i for i, h in enumerate(headers)}

        episode_idx = col_idx.get("episode", 0)
        era_idx = col_idx.get("era", 1)
        era_episode_idx = col_idx.get("era_episode", 2)
        total_episodes_idx = col_idx.get("total_episodes", 3)
        status_idx = col_idx.get("status", 10)

        # PENDING 개수 세기
        for row in data_rows:
            if len(row) > status_idx and row[status_idx] == "PENDING":
                result["pending_count"] += 1

        # 마지막 에피소드 정보
        if data_rows:
            last_row = data_rows[-1]
            try:
                result["last_episode"] = int(last_row[episode_idx]) if len(last_row) > episode_idx and last_row[episode_idx] else 0
            except (ValueError, IndexError):
                result["last_episode"] = len(data_rows)

            if len(last_row) > era_idx:
                result["current_era"] = last_row[era_idx]

            try:
                result["current_era_episode"] = int(last_row[era_episode_idx]) if len(last_row) > era_episode_idx and last_row[era_episode_idx] else 0
            except (ValueError, IndexError):
                result["current_era_episode"] = 0

            try:
                result["current_era_total"] = int(last_row[total_episodes_idx]) if len(last_row) > total_episodes_idx and last_row[total_episodes_idx] else 0
            except (ValueError, IndexError):
                result["current_era_total"] = 0

        print(f"[HISTORY] 진행 상황: 에피소드 {result['last_episode']}개, PENDING {result['pending_count']}개, 현재 시대 {result['current_era']}")
        return result

    except Exception as e:
        print(f"[HISTORY] 진행 상황 조회 실패: {e}")
        return result


def get_next_episode_info(service, spreadsheet_id: str) -> Dict[str, Any]:
    """
    다음 에피소드 정보 계산

    Returns:
        {
            "next_episode": 다음 전체 에피소드 번호,
            "era": 시대 키,
            "era_name": 시대 한글명,
            "era_episode": 시대 내 에피소드 번호,
            "is_new_era": 새 시대 시작 여부,
            "need_more": 더 추가 필요한지 (PENDING < 10),
            "pending_count": 현재 PENDING 개수
        }
    """
    progress = get_series_progress(service, spreadsheet_id)

    result = {
        "next_episode": progress["last_episode"] + 1,
        "era": None,
        "era_name": None,
        "era_episode": 1,
        "is_new_era": False,
        "need_more": progress["pending_count"] < PENDING_TARGET_COUNT,
        "pending_count": progress["pending_count"],
    }

    # 시트가 비어있으면 첫 번째 시대부터 시작
    if progress["last_episode"] == 0 or not progress["current_era"]:
        first_era = ERA_ORDER[0] if ERA_ORDER else "GOJOSEON"
        result["era"] = first_era
        result["era_name"] = ERAS.get(first_era, {}).get("name", first_era)
        result["era_episode"] = 1
        result["is_new_era"] = True
        return result

    current_era = progress["current_era"]
    current_era_episode = progress["current_era_episode"]
    current_era_total = progress["current_era_total"]

    # 현재 시대가 완료되었는지 확인
    if current_era_total > 0 and current_era_episode >= current_era_total:
        # 다음 시대로 이동
        try:
            current_idx = ERA_ORDER.index(current_era)
            if current_idx + 1 < len(ERA_ORDER):
                next_era = ERA_ORDER[current_idx + 1]
                result["era"] = next_era
                result["era_name"] = ERAS.get(next_era, {}).get("name", next_era)
                result["era_episode"] = 1
                result["is_new_era"] = True
            else:
                # 모든 시대 완료 (대한제국까지)
                result["era"] = None
                result["era_name"] = None
                result["need_more"] = False
                print("[HISTORY] 모든 시대 완료!")
        except ValueError:
            # current_era가 ERA_ORDER에 없는 경우
            result["era"] = current_era
            result["era_name"] = ERAS.get(current_era, {}).get("name", current_era)
            result["era_episode"] = current_era_episode + 1
    else:
        # 같은 시대 계속
        result["era"] = current_era
        result["era_name"] = ERAS.get(current_era, {}).get("name", current_era)
        result["era_episode"] = current_era_episode + 1
        result["is_new_era"] = False

    return result


def count_pending_episodes(service, spreadsheet_id: str) -> int:
    """
    PENDING 상태 에피소드 개수 반환

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID

    Returns:
        PENDING 상태 에피소드 수
    """
    progress = get_series_progress(service, spreadsheet_id)
    return progress["pending_count"]


def mark_episode_done(
    service,
    spreadsheet_id: str,
    episode: int
) -> bool:
    """
    특정 에피소드를 DONE으로 표시

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        episode: 에피소드 번호

    Returns:
        성공 여부
    """
    try:
        # 전체 데이터 읽기
        response = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{HISTORY_OPUS_INPUT_SHEET}!A:L"
        ).execute()

        rows = response.get('values', [])
        if len(rows) <= 1:
            return False

        headers = rows[0]
        col_idx = {h: i for i, h in enumerate(headers)}
        episode_idx = col_idx.get("episode", 0)
        status_idx = col_idx.get("status", 10)

        # 해당 에피소드 찾아서 DONE으로 변경
        for i, row in enumerate(rows[1:], start=2):
            try:
                row_episode = int(row[episode_idx]) if len(row) > episode_idx and row[episode_idx] else 0
            except ValueError:
                continue

            if row_episode == episode:
                # status 열 업데이트
                status_cell = f"{HISTORY_OPUS_INPUT_SHEET}!{chr(65 + status_idx)}{i}"
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=status_cell,
                    valueInputOption="RAW",
                    body={"values": [["DONE"]]}
                ).execute()
                print(f"[HISTORY] 에피소드 {episode} → DONE")
                return True

        return False

    except Exception as e:
        print(f"[HISTORY] 에피소드 상태 변경 실패: {e}")
        return False
