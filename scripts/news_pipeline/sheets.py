"""
Google Sheets 헬퍼 함수
"""

import time


def append_rows(service, sheet_id: str, range_a1: str, rows: list) -> bool:
    """
    Google Sheets에 행 추가 (재시도 로직 포함)

    Args:
        service: Google Sheets API 서비스 객체
        sheet_id: 스프레드시트 ID
        range_a1: A1 표기법 범위 (예: "RAW_FEED!A1")
        rows: 추가할 행 데이터

    Returns:
        성공 여부
    """
    body = {"values": rows}
    max_retries = 3

    for attempt in range(max_retries):
        try:
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=range_a1,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()
            return True
        except Exception as e:
            error_str = str(e).lower()
            transient_errors = ['500', '502', '503', '504', 'timeout', 'backend error']
            is_transient = any(p in error_str for p in transient_errors)

            if is_transient and attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                print(f"[NEWS] Sheets append 재시도 ({attempt + 1}/{max_retries}), {wait_time}초 대기")
                time.sleep(wait_time)
            else:
                print(f"[NEWS] Sheets append 실패: {e}")
                return False

    return False
