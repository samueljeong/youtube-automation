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

            # ★ 기존 시트에 누락된 열 추가
            # HISTORY 시트 구조: 행1=채널ID, 행2=헤더, 행3~=데이터
            if headers and sheet_name == UNIFIED_HISTORY_SHEET:
                try:
                    # 현재 헤더 읽기 (행 2)
                    result = service.spreadsheets().values().get(
                        spreadsheetId=spreadsheet_id,
                        range=f"'{sheet_name}'!2:2"
                    ).execute()
                    current_headers = result.get('values', [[]])[0] if result.get('values') else []

                    # 누락된 열 찾기
                    missing_headers = [h for h in headers if h not in current_headers]

                    if missing_headers:
                        print(f"[HISTORY] 시트 '{sheet_name}'에 누락된 열 추가: {missing_headers}")

                        # 기존 헤더 뒤에 추가 (행 2)
                        new_headers = current_headers + missing_headers
                        service.spreadsheets().values().update(
                            spreadsheetId=spreadsheet_id,
                            range=f"'{sheet_name}'!A2",
                            valueInputOption="RAW",
                            body={"values": [new_headers]}
                        ).execute()
                        print(f"[HISTORY] 시트 '{sheet_name}' 헤더 업데이트 완료 (행 2)")
                except Exception as header_err:
                    print(f"[HISTORY] 헤더 업데이트 실패 (무시): {header_err}")

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
            # HISTORY 시트는 행1=채널ID, 행2=헤더 구조
            if sheet_name == UNIFIED_HISTORY_SHEET:
                # 행 1: 채널ID 레이블
                # 행 2: 헤더
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=f"'{sheet_name}'!A1",
                    valueInputOption="RAW",
                    body={"values": [
                        ["채널ID", ""],  # 행 1: 채널ID (값은 사용자가 입력)
                        headers           # 행 2: 헤더
                    ]}
                ).execute()
                print(f"[HISTORY] 시트 '{sheet_name}' 구조 생성 완료 (행1=채널ID, 행2=헤더)")
            else:
                # 다른 시트는 행 1에 헤더
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
    통합 HISTORY 시트 자동 생성 (영상 자동화용)

    모든 에피소드가 여기에 누적됨
    ★ UNIFIED_HISTORY_SHEET ("HISTORY")를 사용

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID

    Returns:
        True: 새로 생성됨, False: 이미 존재
    """
    headers = SHEET_HEADERS.get("OPUS_INPUT", [])

    try:
        # ★ UNIFIED_HISTORY_SHEET ("HISTORY") 시트 생성
        created = ensure_sheet_exists(
            service, spreadsheet_id, UNIFIED_HISTORY_SHEET, headers
        )
        return created
    except Exception as e:
        print(f"[HISTORY] HISTORY 시트 생성 오류: {e}")
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
    시리즈 진행 상황 조회 (통합 시트 HISTORY 기반)

    통합 시트 구조:
    - 행 1: 채널ID | UCxxx
    - 행 2: 헤더 (era, episode_slot, core_question, ..., 상태, ...)
    - 행 3~: 데이터

    Returns:
        {
            "total_episodes": 시트에 저장된 에피소드 수,
            "pending_count": '준비' 상태 에피소드 수,
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
        # 통합 시트에서 데이터 읽기 (행 2: 헤더, 행 3~: 데이터)
        response = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{UNIFIED_HISTORY_SHEET}'!A2:Z"
        ).execute()

        rows = response.get('values', [])

        if len(rows) <= 1:
            # 헤더만 있거나 비어있음
            print(f"[HISTORY] 통합 시트 '{UNIFIED_HISTORY_SHEET}'에 데이터 없음")
            return result

        headers = rows[0]  # 행 2 = 헤더
        data_rows = rows[1:]  # 행 3~ = 데이터

        # 컬럼 인덱스 찾기 (통합 시트 헤더 기준)
        col_idx = {h: i for i, h in enumerate(headers)}

        era_idx = col_idx.get("era", 0)
        era_episode_idx = col_idx.get("episode_slot", 1)
        status_idx = col_idx.get("상태", -1)  # 통합 시트는 한글 헤더 사용

        # ★ 빈 행 필터링: era 열이 비어있으면 스킵 (드롭다운만 있는 빈 행 제외)
        valid_rows = [row for row in data_rows if len(row) > era_idx and row[era_idx].strip()]

        result["total_episodes"] = len(valid_rows)
        result["all_rows"] = valid_rows

        # '준비' 상태 개수 세기 (수집 완료 상태)
        if status_idx >= 0:
            for row in valid_rows:
                if len(row) > status_idx and row[status_idx] == "준비":
                    result["pending_count"] += 1

        # 마지막 에피소드 정보
        if valid_rows:
            last_row = valid_rows[-1]

            if len(last_row) > era_idx:
                result["current_era"] = last_row[era_idx]

            try:
                result["current_era_episode"] = int(last_row[era_episode_idx]) if len(last_row) > era_episode_idx and last_row[era_episode_idx] else 0
            except (ValueError, IndexError):
                result["current_era_episode"] = 0

            # 전역 에피소드 번호 계산 (시대별 누적)
            # ERA_ORDER를 따라가면서 현재 시대까지의 에피소드 수를 합산
            total_ep = 0
            for era_key in ERA_ORDER:
                era_topics = HISTORY_TOPICS.get(era_key, [])
                if era_key == result["current_era"]:
                    total_ep += result["current_era_episode"]
                    break
                total_ep += len(era_topics)
            result["last_episode"] = total_ep

        print(f"[HISTORY] 진행 상황: 에피소드 {result['last_episode']}/{result['planned_total']}개, 준비 {result['pending_count']}개, 현재 시대 {result['current_era']}")
        return result

    except Exception as e:
        print(f"[HISTORY] 진행 상황 조회 실패: {e}")
        import traceback
        traceback.print_exc()
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
            "need_more": 더 추가 필요한지 ('준비' < 10),
            "pending_count": 현재 '준비' 개수,
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
    '준비' 상태 에피소드 개수 반환

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID

    Returns:
        '준비' 상태 에피소드 수
    """
    progress = get_series_progress(service, spreadsheet_id)
    return progress["pending_count"]


def mark_episode_done(
    service,
    spreadsheet_id: str,
    episode: int
) -> bool:
    """
    특정 에피소드를 '완료'로 표시

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


# ============================================================
# GPT-5.1 대본 자동 생성용 함수 (2025-01 신규)
# ============================================================

def get_pending_episodes_for_script(
    service,
    spreadsheet_id: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    '준비' 상태이면서 대본이 비어있는 에피소드 조회

    통합 시트(HISTORY) 구조:
    - 행 1: 채널ID | UCxxx
    - 행 2: 헤더 (era, episode_slot, core_question, ..., 상태, 대본, ...)
    - 행 3~: 데이터

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        limit: 최대 반환 개수

    Returns:
        [
            {
                "row_index": 시트 행 번호 (1-based, 데이터는 3부터),
                "era": 시대 키,
                "era_episode": 시대 내 에피소드 번호,
                "title": 에피소드 제목 (core_question),
                "total_episodes": 시대 총 에피소드 수,
            },
            ...
        ]
    """
    pending = []

    try:
        # 1) 시트 헤더(행 2) 읽기
        header_result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{UNIFIED_HISTORY_SHEET}'!A2:Z2"
        ).execute()
        header_rows = header_result.get('values', [])

        if not header_rows:
            print(f"[HISTORY] '{UNIFIED_HISTORY_SHEET}' 시트 헤더 없음")
            return []

        headers = header_rows[0]
        col_map = {h: i for i, h in enumerate(headers)}

        # 필요한 열 인덱스
        era_idx = col_map.get("era", 0)
        slot_idx = col_map.get("episode_slot", 1)
        title_idx = col_map.get("core_question", 3)
        status_idx = col_map.get("상태", -1)
        script_idx = col_map.get("대본", -1)

        if status_idx < 0 or script_idx < 0:
            print(f"[HISTORY] '상태' 또는 '대본' 열을 찾을 수 없음")
            return []

        # 2) 데이터(행 3~) 읽기
        data_result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{UNIFIED_HISTORY_SHEET}'!A3:Z"
        ).execute()
        data_rows = data_result.get('values', [])

        # 3) '준비' 상태 + 대본 비어있는 행 찾기
        for i, row in enumerate(data_rows):
            row_index = i + 3  # 시트 행 번호 (1-based, 데이터는 3부터)

            # 상태 확인
            status = row[status_idx] if len(row) > status_idx else ""
            if status != "준비":
                continue

            # 대본 비어있는지 확인
            script = row[script_idx] if len(row) > script_idx else ""
            if script.strip():
                continue  # 대본이 이미 있으면 스킵

            # 에피소드 정보 추출
            era = row[era_idx] if len(row) > era_idx else ""
            era_episode_str = row[slot_idx] if len(row) > slot_idx else ""
            title = row[title_idx] if len(row) > title_idx else ""

            try:
                era_episode = int(era_episode_str) if era_episode_str else 0
            except ValueError:
                era_episode = 0

            if not era or era_episode <= 0:
                continue

            # 시대 총 에피소드 수
            total_episodes = len(HISTORY_TOPICS.get(era, []))

            pending.append({
                "row_index": row_index,
                "era": era,
                "era_episode": era_episode,
                "title": title,
                "total_episodes": total_episodes,
            })

            if len(pending) >= limit:
                break

        print(f"[HISTORY] '준비' 상태 + 대본 없음: {len(pending)}개")
        return pending

    except Exception as e:
        print(f"[HISTORY] 에피소드 조회 실패: {e}")
        return []


def update_script_and_status(
    service,
    spreadsheet_id: str,
    row_index: int,
    script: str,
    new_status: str = "대기",
    youtube_title: str = None,      # ★ YouTube SEO 제목
    thumbnail_text: str = None,     # ★ 썸네일 문구
    youtube_sources: str = None,    # ★ YouTube 설명란 출처
) -> Dict[str, Any]:
    """
    특정 행의 대본, 상태, SEO 메타데이터 업데이트

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        row_index: 시트 행 번호 (1-based)
        script: 생성된 대본
        new_status: 새 상태 (기본 "대기")
        youtube_title: YouTube SEO 제목 (K열: 제목(GPT생성))
        thumbnail_text: 썸네일 문구 (L열: 썸네일문구(입력))
        youtube_sources: YouTube 설명란 출처 (I열: 인용링크)

    Returns:
        {"success": bool, "error": str}
    """
    result = {"success": False, "error": None}

    try:
        # 1) 시트 헤더(행 2) 읽기 - 더 넓은 범위
        header_result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{UNIFIED_HISTORY_SHEET}'!A2:AZ2"
        ).execute()
        header_rows = header_result.get('values', [])

        if not header_rows:
            result["error"] = "헤더 없음"
            return result

        headers = header_rows[0]
        col_map = {h: i for i, h in enumerate(headers)}

        # 필수 열 확인
        status_idx = col_map.get("상태", -1)
        script_idx = col_map.get("대본", -1)

        if status_idx < 0 or script_idx < 0:
            result["error"] = "'상태' 또는 '대본' 열을 찾을 수 없음"
            return result

        # 2) 상태 열 업데이트
        status_col = _idx_to_col(status_idx)
        status_range = f"'{UNIFIED_HISTORY_SHEET}'!{status_col}{row_index}"

        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=status_range,
            valueInputOption="RAW",
            body={"values": [[new_status]]}
        ).execute()

        # 3) 대본 열 업데이트
        script_col = _idx_to_col(script_idx)
        script_range = f"'{UNIFIED_HISTORY_SHEET}'!{script_col}{row_index}"

        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=script_range,
            valueInputOption="RAW",
            body={"values": [[script]]}
        ).execute()

        print(f"[HISTORY] 행 {row_index}: 상태='{new_status}', 대본={len(script):,}자 저장 완료")

        # 4) ★ YouTube SEO 메타데이터 업데이트
        if youtube_title:
            title_idx = col_map.get("제목(GPT생성)", col_map.get("제목", -1))
            if title_idx >= 0:
                title_col = _idx_to_col(title_idx)
                title_range = f"'{UNIFIED_HISTORY_SHEET}'!{title_col}{row_index}"
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=title_range,
                    valueInputOption="RAW",
                    body={"values": [[youtube_title]]}
                ).execute()
                print(f"[HISTORY] 제목 저장: {youtube_title[:30]}...")

        if thumbnail_text:
            thumb_idx = col_map.get("썸네일문구(입력)", col_map.get("thumbnail_copy", -1))
            if thumb_idx >= 0:
                thumb_col = _idx_to_col(thumb_idx)
                thumb_range = f"'{UNIFIED_HISTORY_SHEET}'!{thumb_col}{row_index}"
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=thumb_range,
                    valueInputOption="RAW",
                    body={"values": [[thumbnail_text]]}
                ).execute()
                print(f"[HISTORY] 썸네일 문구 저장: {thumbnail_text.replace(chr(10), ' / ')}")

        if youtube_sources:
            sources_idx = col_map.get("인용링크", col_map.get("source_url", -1))
            if sources_idx >= 0:
                sources_col = _idx_to_col(sources_idx)
                sources_range = f"'{UNIFIED_HISTORY_SHEET}'!{sources_col}{row_index}"
                service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=sources_range,
                    valueInputOption="RAW",
                    body={"values": [[youtube_sources]]}
                ).execute()
                print(f"[HISTORY] 인용링크 저장 완료")

        result["success"] = True

    except Exception as e:
        result["error"] = str(e)
        print(f"[HISTORY] 시트 업데이트 실패: {e}")

    return result


def _idx_to_col(idx: int) -> str:
    """인덱스를 열 문자로 변환 (0=A, 25=Z, 26=AA, ...)"""
    if idx < 26:
        return chr(65 + idx)
    else:
        return chr(64 + idx // 26) + chr(65 + idx % 26)


def update_status_to_failed(
    service,
    spreadsheet_id: str,
    row_index: int,
    error_message: str,
) -> Dict[str, Any]:
    """
    대본 생성 실패 시 상태를 '실패'로 변경하고 에러메시지 저장

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        row_index: 시트 행 번호 (1-based)
        error_message: 에러 메시지

    Returns:
        {"success": bool, "error": str}
    """
    result = {"success": False, "error": None}

    try:
        # 1) 시트 헤더(행 2) 읽기
        header_result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{UNIFIED_HISTORY_SHEET}'!A2:AZ2"
        ).execute()
        header_rows = header_result.get('values', [])

        if not header_rows:
            result["error"] = "헤더 없음"
            return result

        headers = header_rows[0]
        col_map = {h: i for i, h in enumerate(headers)}

        # 2) 상태 열 업데이트 → "실패"
        status_idx = col_map.get("상태", -1)
        if status_idx >= 0:
            status_col = _idx_to_col(status_idx)
            status_range = f"'{UNIFIED_HISTORY_SHEET}'!{status_col}{row_index}"
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=status_range,
                valueInputOption="RAW",
                body={"values": [["실패"]]}
            ).execute()

        # 3) 에러메시지 열 업데이트
        error_idx = col_map.get("에러메시지", -1)
        if error_idx >= 0:
            error_col = _idx_to_col(error_idx)
            error_range = f"'{UNIFIED_HISTORY_SHEET}'!{error_col}{row_index}"
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=error_range,
                valueInputOption="RAW",
                body={"values": [[error_message[:500]]]}  # 500자 제한
            ).execute()

        print(f"[HISTORY] 행 {row_index}: 상태='실패', 에러={error_message[:50]}...")
        result["success"] = True

    except Exception as e:
        result["error"] = str(e)
        print(f"[HISTORY] 실패 상태 업데이트 오류: {e}")

    return result
