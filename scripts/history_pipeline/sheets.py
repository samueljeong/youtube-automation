"""
Google Sheets 헬퍼 함수 (주제 기반 구조)

단순화된 구조 (2024-12 개편):
- HISTORY_OPUS_INPUT 시트 하나만 사용
- 시대별 RAW/CANDIDATES 시트 제거
- HISTORY_TOPICS 기반 주제 순서 관리

2024-12-20 업데이트:
- 통합 시트(HISTORY) 지원 추가
"""

import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from .config import (
    SHEET_HEADERS,
    HISTORY_OPUS_INPUT_SHEET,
    PENDING_TARGET_COUNT,
    ERA_ORDER,
    ERAS,
    HISTORY_TOPICS,
)


# 통합 시트 이름
UNIFIED_HISTORY_SHEET = "HISTORY"


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


def ensure_history_opus_input_sheet(service, spreadsheet_id: str) -> bool:
    """
    단일 통합 OPUS_INPUT 시트 자동 생성 (HISTORY_OPUS_INPUT)

    모든 에피소드가 여기에 누적됨

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
        range_a1: A1 표기법 범위 (예: "HISTORY_OPUS_INPUT!A1")
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


def append_to_unified_sheet(
    service,
    spreadsheet_id: str,
    opus_row: List[Any],
    field_names: List[str]
) -> bool:
    """
    통합 시트(HISTORY)에 데이터 추가 (헤더 매핑 적용)

    통합 시트 구조:
    - 행 1: 채널ID | UCxxx
    - 행 2: 헤더
    - 행 3~: 데이터

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        opus_row: 추가할 데이터 행 (단일 행)
        field_names: opus_row의 각 열에 해당하는 필드 이름

    Returns:
        성공 여부
    """
    try:
        # 1) 시트 헤더(행 2) 읽기
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{UNIFIED_HISTORY_SHEET}'!A2:Z2"
        ).execute()
        header_rows = result.get('values', [])

        if not header_rows:
            raise SheetsSaveError(f"시트 '{UNIFIED_HISTORY_SHEET}'의 헤더가 없습니다")

        headers = header_rows[0]
        header_idx = {h: i for i, h in enumerate(headers)}

        # 2) 데이터를 헤더에 맞게 변환
        new_row = [''] * len(headers)
        for i, field in enumerate(field_names):
            if i < len(opus_row) and field in header_idx:
                new_row[header_idx[field]] = opus_row[i]

        # 3) 행 3부터 append
        body = {"values": [new_row]}
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"'{UNIFIED_HISTORY_SHEET}'!A3",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()

        updated_rows = result.get("updates", {}).get("updatedRows", 0)
        print(f"[HISTORY] 통합 시트 '{UNIFIED_HISTORY_SHEET}'에 {updated_rows}개 행 추가 완료")
        return True

    except Exception as e:
        print(f"[HISTORY] 통합 시트 '{UNIFIED_HISTORY_SHEET}' 저장 실패: {e}")
        raise SheetsSaveError(f"통합 시트 저장 실패 ({UNIFIED_HISTORY_SHEET}): {e}")


def get_total_episode_count() -> int:
    """
    전체 에피소드 수 반환 (HISTORY_TOPICS 기반)

    Returns:
        전체 에피소드 수
    """
    total = 0
    for era_topics in HISTORY_TOPICS.values():
        total += len(era_topics)
    return total


def get_era_episode_count(era: str) -> int:
    """
    특정 시대의 에피소드 수 반환

    Args:
        era: 시대 키 (예: "GOJOSEON")

    Returns:
        에피소드 수
    """
    return len(HISTORY_TOPICS.get(era, []))


def get_topic_by_global_episode(episode: int) -> Optional[Dict[str, Any]]:
    """
    전역 에피소드 번호로 주제 정보 조회

    Args:
        episode: 전역 에피소드 번호 (1부터 시작)

    Returns:
        {
            "era": 시대 키,
            "era_name": 시대 한글명,
            "era_episode": 시대 내 에피소드 번호,
            "topic": 주제 정보 딕셔너리
        }
        또는 None (범위 초과 시)
    """
    current_episode = 0

    for era in ERA_ORDER:
        topics = HISTORY_TOPICS.get(era, [])
        era_info = ERAS.get(era, {})
        era_name = era_info.get("name", era)

        for i, topic in enumerate(topics, start=1):
            current_episode += 1
            if current_episode == episode:
                return {
                    "era": era,
                    "era_name": era_name,
                    "era_episode": i,
                    "total_episodes": len(topics),
                    "topic": topic,
                }

    return None


def get_series_progress(service, spreadsheet_id: str) -> Dict[str, Any]:
    """
    시리즈 진행 상황 조회 (HISTORY_OPUS_INPUT 시트 기반)

    Returns:
        {
            "total_episodes": 시트에 저장된 에피소드 수,
            "pending_count": PENDING 상태 에피소드 수,
            "last_episode": 마지막 에피소드 번호,
            "current_era": 현재 진행 중인 시대,
            "current_era_episode": 현재 시대의 마지막 에피소드 번호,
            "all_rows": 전체 데이터 (분석용),
            "planned_total": HISTORY_TOPICS 기반 계획된 총 에피소드 수,
        }
    """
    result = {
        "total_episodes": 0,
        "pending_count": 0,
        "last_episode": 0,
        "current_era": None,
        "current_era_episode": 0,
        "all_rows": [],
        "planned_total": get_total_episode_count(),
    }

    try:
        # 전체 데이터 읽기
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

        print(f"[HISTORY] 진행 상황: 에피소드 {result['last_episode']}/{result['planned_total']}개, PENDING {result['pending_count']}개, 현재 시대 {result['current_era']}")
        return result

    except Exception as e:
        print(f"[HISTORY] 진행 상황 조회 실패: {e}")
        return result


def get_next_episode_info(service, spreadsheet_id: str) -> Dict[str, Any]:
    """
    다음 에피소드 정보 계산 (HISTORY_TOPICS 기반)

    Returns:
        {
            "next_episode": 다음 전체 에피소드 번호,
            "era": 시대 키,
            "era_name": 시대 한글명,
            "era_episode": 시대 내 에피소드 번호,
            "total_episodes": 시대 총 에피소드 수,
            "topic": 주제 정보 딕셔너리,
            "is_new_era": 새 시대 시작 여부,
            "need_more": 더 추가 필요한지 (PENDING < 10),
            "pending_count": 현재 PENDING 개수,
            "all_complete": 모든 에피소드 완료 여부,
        }
    """
    progress = get_series_progress(service, spreadsheet_id)

    result = {
        "next_episode": progress["last_episode"] + 1,
        "era": None,
        "era_name": None,
        "era_episode": 1,
        "total_episodes": 0,
        "topic": None,
        "is_new_era": False,
        "need_more": progress["pending_count"] < PENDING_TARGET_COUNT,
        "pending_count": progress["pending_count"],
        "all_complete": False,
    }

    next_episode = progress["last_episode"] + 1

    # 다음 에피소드 주제 조회
    topic_info = get_topic_by_global_episode(next_episode)

    if topic_info is None:
        # 모든 에피소드 완료
        result["all_complete"] = True
        result["need_more"] = False
        print(f"[HISTORY] 모든 에피소드 완료! (총 {progress['planned_total']}화)")
        return result

    result["era"] = topic_info["era"]
    result["era_name"] = topic_info["era_name"]
    result["era_episode"] = topic_info["era_episode"]
    result["total_episodes"] = topic_info["total_episodes"]
    result["topic"] = topic_info["topic"]

    # 새 시대 시작 여부 (시대 내 에피소드 번호가 1이면 새 시대)
    result["is_new_era"] = (topic_info["era_episode"] == 1)

    if result["is_new_era"]:
        print(f"[HISTORY] 새 시대 시작: {result['era_name']} ({result['total_episodes']}화)")

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


def get_episode_by_number(
    service,
    spreadsheet_id: str,
    episode: int
) -> Optional[Dict[str, Any]]:
    """
    에피소드 번호로 시트에서 해당 행 조회

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        episode: 에피소드 번호

    Returns:
        에피소드 정보 딕셔너리 또는 None
    """
    try:
        response = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{HISTORY_OPUS_INPUT_SHEET}!A:L"
        ).execute()

        rows = response.get('values', [])
        if len(rows) <= 1:
            return None

        headers = rows[0]
        col_idx = {h: i for i, h in enumerate(headers)}
        episode_idx = col_idx.get("episode", 0)

        for row in rows[1:]:
            try:
                row_episode = int(row[episode_idx]) if len(row) > episode_idx and row[episode_idx] else 0
            except ValueError:
                continue

            if row_episode == episode:
                # 헤더와 매핑하여 딕셔너리 반환
                result = {}
                for header, idx in col_idx.items():
                    result[header] = row[idx] if len(row) > idx else ""
                return result

        return None

    except Exception as e:
        print(f"[HISTORY] 에피소드 조회 실패: {e}")
        return None
