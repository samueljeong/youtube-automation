"""
Google Sheets 헬퍼 함수
"""

import time
from datetime import datetime, timezone, timedelta


class SheetsSaveError(Exception):
    """Google Sheets 저장 실패 예외"""
    pass


# 통합 시트 이름 매핑 (채널 → 시트)
UNIFIED_SHEET_NAMES = {
    "ECON": "NEWS",
    "POLICY": "NEWS",
    "SOCIETY": "NEWS",
    "WORLD": "NEWS",
}

# 기존 필드 → 새 시트 헤더 매핑
NEWS_FIELD_MAPPING = {
    "run_id": "run_id",
    "selected_rank": "selected_rank",
    "category": "category",
    "issue_one_line": "issue_one_line",
    "core_points": "core_points",
    "brief": "brief",
    "thumbnail_copy": "thumbnail_copy",
    "opus_prompt_pack": "opus_prompt_pack",
}


def get_unified_sheet_name(channel: str) -> str:
    """채널에 해당하는 통합 시트 이름 반환"""
    return UNIFIED_SHEET_NAMES.get(channel, f"OPUS_INPUT_{channel}")


def append_to_unified_sheet(
    service,
    sheet_id: str,
    sheet_name: str,
    rows: list,
    field_names: list
) -> bool:
    """
    통합 시트에 데이터 추가 (헤더 매핑 적용)

    통합 시트 구조:
    - 행 1: 채널ID | UCxxx
    - 행 2: 헤더
    - 행 3~: 데이터

    Args:
        service: Google Sheets API 서비스 객체
        sheet_id: 스프레드시트 ID
        sheet_name: 시트 이름 (예: "NEWS")
        rows: 추가할 데이터 (각 행은 field_names 순서의 값 리스트)
        field_names: rows의 각 열에 해당하는 필드 이름

    Returns:
        성공 여부
    """
    try:
        # 1) 시트 헤더(행 2) 읽기
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"'{sheet_name}'!A2:Z2"
        ).execute()
        header_rows = result.get('values', [])

        if not header_rows:
            raise SheetsSaveError(f"시트 '{sheet_name}'의 헤더가 없습니다")

        headers = header_rows[0]
        header_idx = {h: i for i, h in enumerate(headers)}

        # 2) 데이터를 헤더에 맞게 변환
        mapped_rows = []
        for row in rows:
            new_row = [''] * len(headers)
            for i, field in enumerate(field_names):
                if i < len(row) and field in header_idx:
                    new_row[header_idx[field]] = row[i]
            mapped_rows.append(new_row)

        # 3) 행 3부터 append
        body = {"values": mapped_rows}
        result = service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"'{sheet_name}'!A3",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()

        updated_rows = result.get("updates", {}).get("updatedRows", 0)
        print(f"[NEWS] 통합 시트 '{sheet_name}'에 {updated_rows}개 행 추가 완료")
        return True

    except Exception as e:
        print(f"[NEWS] 통합 시트 '{sheet_name}' 저장 실패: {e}")
        raise SheetsSaveError(f"통합 시트 저장 실패 ({sheet_name}): {e}")


def cleanup_old_rows(service, sheet_id: str, tab_name: str, days: int = 7) -> int:
    """
    지정된 일수보다 오래된 행 삭제 (A열 = ingested_at 기준)

    Args:
        service: Google Sheets API 서비스 객체
        sheet_id: 스프레드시트 ID
        tab_name: 탭 이름 (예: "RAW_FEED")
        days: 보관 일수 (기본 7일)

    Returns:
        삭제된 행 수
    """
    try:
        # 1) 시트 ID 가져오기
        spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheet_id_num = None
        for sheet in spreadsheet.get('sheets', []):
            if sheet['properties']['title'] == tab_name:
                sheet_id_num = sheet['properties']['sheetId']
                break

        if sheet_id_num is None:
            print(f"[NEWS] {tab_name} 탭을 찾을 수 없음")
            return 0

        # 2) A열 데이터 읽기 (ingested_at)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f'{tab_name}!A:A'
        ).execute()
        rows = result.get('values', [])

        if len(rows) <= 1:  # 헤더만 있음
            return 0

        # 3) 삭제할 행 찾기 (7일 이상 된 데이터)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows_to_delete = []

        for i, row in enumerate(rows[1:], start=2):  # 헤더 제외, 행 번호는 2부터
            if not row:
                continue
            try:
                ingested_at = datetime.fromisoformat(row[0].replace('Z', '+00:00'))
                if ingested_at < cutoff:
                    rows_to_delete.append(i)
            except (ValueError, IndexError):
                continue

        if not rows_to_delete:
            print(f"[NEWS] {tab_name}: 삭제할 오래된 데이터 없음")
            return 0

        # 4) 역순으로 삭제 (뒤에서부터 삭제해야 인덱스가 안 밀림)
        rows_to_delete.sort(reverse=True)

        requests = []
        for row_num in rows_to_delete:
            requests.append({
                "deleteDimension": {
                    "range": {
                        "sheetId": sheet_id_num,
                        "dimension": "ROWS",
                        "startIndex": row_num - 1,  # 0-indexed
                        "endIndex": row_num
                    }
                }
            })

        # 5) 배치 삭제 (한 번에 최대 100개씩)
        deleted = 0
        for i in range(0, len(requests), 100):
            batch = requests[i:i+100]
            service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": batch}
            ).execute()
            deleted += len(batch)

        print(f"[NEWS] {tab_name}: {deleted}개 오래된 행 삭제 완료 ({days}일 기준)")
        return deleted

    except Exception as e:
        print(f"[NEWS] {tab_name} 정리 실패 (계속 진행): {e}")
        return 0


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

    Raises:
        SheetsSaveError: 모든 재시도 실패 시
    """
    body = {"values": rows}
    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            result = service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=range_a1,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()
            updated_range = result.get("updates", {}).get("updatedRange", "")
            updated_rows = result.get("updates", {}).get("updatedRows", 0)
            print(f"[NEWS] Sheets append 성공: {updated_range}, {updated_rows}행 추가")
            return True
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            transient_errors = ['500', '502', '503', '504', 'timeout', 'backend error']
            is_transient = any(p in error_str for p in transient_errors)

            if is_transient and attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                print(f"[NEWS] Sheets append 재시도 ({attempt + 1}/{max_retries}), {wait_time}초 대기: {e}")
                time.sleep(wait_time)
            else:
                print(f"[NEWS] Sheets append 실패 (최종): {e}")
                raise SheetsSaveError(f"시트 저장 실패 ({range_a1}): {e}")

    raise SheetsSaveError(f"시트 저장 실패 ({range_a1}): {last_error}")
