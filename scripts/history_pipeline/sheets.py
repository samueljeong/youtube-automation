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
    시대별 필수 시트 3개 자동 생성

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        era: 시대 키 (예: "GOJOSEON")

    Returns:
        {"RAW": True/False, "CANDIDATES": True/False, "OPUS_INPUT": True/False}
    """
    results = {}

    for prefix in ["RAW", "CANDIDATES", "OPUS_INPUT"]:
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


def check_opus_input_exists(
    service,
    spreadsheet_id: str,
    era: str,
    run_id: str
) -> bool:
    """
    같은 날 OPUS_INPUT이 이미 생성되었는지 확인 (Idempotency)

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        era: 시대 키
        run_id: 실행 ID (YYYY-MM-DD)

    Returns:
        이미 존재하면 True
    """
    try:
        opus_sheet = get_era_sheet_name("OPUS_INPUT", era)

        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{opus_sheet}!A:A"
        ).execute()

        rows = result.get('values', [])

        # 헤더 제외하고 run_id 확인
        for row in rows[1:]:
            if row and row[0] == run_id:
                return True

        return False

    except Exception as e:
        # 시트가 없거나 읽기 실패 시 False (새로 생성 허용)
        print(f"[HISTORY] OPUS_INPUT 확인 실패 (무시): {e}")
        return False


def get_existing_opus_titles(
    service,
    spreadsheet_id: str,
    era: str,
    title_column: str = "D"
) -> set:
    """
    OPUS_INPUT 시트에서 기존 title 목록 조회 (중복 방지용)

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        era: 시대 키
        title_column: title이 저장된 열 (기본: D열)

    Returns:
        기존 title 집합
    """
    try:
        opus_sheet = get_era_sheet_name("OPUS_INPUT", era)

        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{opus_sheet}!{title_column}:{title_column}"
        ).execute()

        rows = result.get('values', [])

        # 헤더 제외
        titles = set()
        for row in rows[1:]:
            if row and row[0]:
                # 제목에서 앞 100자만 비교 (저장 시 truncate되므로)
                titles.add(row[0].strip()[:100])

        print(f"[HISTORY] {opus_sheet}에서 기존 title {len(titles)}개 로드")
        return titles

    except Exception as e:
        print(f"[HISTORY] OPUS_INPUT title 조회 실패 (무시): {e}")
        return set()
