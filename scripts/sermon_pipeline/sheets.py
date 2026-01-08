"""
Google Sheets 헬퍼 함수

설교문 파이프라인용 시트 읽기/쓰기
"""

import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from .config import (
    SERMON_HEADERS,
    COL_STATUS,
    COL_SCRIPTURE,
    COL_REQUEST,
    COL_SERMON,
    COL_FEEDBACK,
    COL_REVISION,
    COL_DATETIME,
    COL_ERROR,
    STATUS_REQUEST,
    STATUS_REVISION_REQUEST,
    STATUS_PROCESSING,
    STATUS_COMPLETE,
    STATUS_FAILED,
)


class SheetsSaveError(Exception):
    """Google Sheets 저장 실패 예외"""
    pass


class SheetsReadError(Exception):
    """Google Sheets 읽기 실패 예외"""
    pass


def get_all_sheet_names(service, spreadsheet_id: str) -> List[str]:
    """
    스프레드시트의 모든 시트(탭) 이름 조회
    언더스코어(_)로 시작하는 시트는 제외

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID

    Returns:
        시트 이름 리스트
    """
    try:
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()

        sheet_names = [
            sheet['properties']['title']
            for sheet in spreadsheet.get('sheets', [])
            if not sheet['properties']['title'].startswith('_')
        ]

        return sheet_names
    except Exception as e:
        print(f"[SERMON] 시트 목록 조회 실패: {e}")
        raise SheetsReadError(f"시트 목록 조회 실패: {e}")


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
        headers: 헤더 리스트 (없으면 SERMON_HEADERS 사용)

    Returns:
        True: 새로 생성됨, False: 이미 존재
    """
    if headers is None:
        headers = SERMON_HEADERS

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
            print(f"[SERMON] 시트 '{sheet_name}' 이미 존재")
            return False

        # 2) 시트 추가
        request = {
            'addSheet': {
                'properties': {
                    'title': sheet_name,
                }
            }
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [request]}
        ).execute()

        print(f"[SERMON] 시트 '{sheet_name}' 생성됨")

        # 3) 헤더 추가 (행 1)
        if headers:
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption="RAW",
                body={"values": [headers]}
            ).execute()
            print(f"[SERMON] 시트 '{sheet_name}' 헤더 추가 완료")

        return True

    except Exception as e:
        print(f"[SERMON] 시트 생성 실패: {e}")
        raise SheetsSaveError(f"시트 생성 실패: {e}")


def init_sheet(service, spreadsheet_id: str, sheet_name: str) -> Dict[str, Any]:
    """
    새 시트 초기화 (API용)

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        sheet_name: 시트 이름

    Returns:
        결과 딕셔너리
    """
    try:
        created = ensure_sheet_exists(service, spreadsheet_id, sheet_name)
        return {
            "success": True,
            "sheet_name": sheet_name,
            "created": created,
            "message": f"시트 '{sheet_name}' {'생성' if created else '이미 존재'}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_pending_requests(
    service,
    spreadsheet_id: str,
    sheet_names: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    대기 중인 설교 요청 조회

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        sheet_names: 조회할 시트 이름 리스트 (None이면 전체)

    Returns:
        요청 리스트 [{sheet_name, row_number, scripture, request, ...}, ...]
    """
    if sheet_names is None:
        sheet_names = get_all_sheet_names(service, spreadsheet_id)

    pending = []

    for sheet_name in sheet_names:
        try:
            # 시트 전체 읽기 (행 1=헤더, 행 2~=데이터)
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A:H"
            ).execute()

            rows = result.get('values', [])
            if len(rows) < 2:
                continue  # 헤더만 있거나 빈 시트

            # 행 2부터 데이터
            for i, row in enumerate(rows[1:], start=2):
                # 빈 행 스킵
                if not row or len(row) == 0:
                    continue

                status = row[COL_STATUS] if len(row) > COL_STATUS else ""

                # 요청 또는 수정요청 상태만
                if status not in [STATUS_REQUEST, STATUS_REVISION_REQUEST]:
                    continue

                scripture = row[COL_SCRIPTURE] if len(row) > COL_SCRIPTURE else ""
                request = row[COL_REQUEST] if len(row) > COL_REQUEST else ""
                feedback = row[COL_FEEDBACK] if len(row) > COL_FEEDBACK else ""
                current_sermon = row[COL_SERMON] if len(row) > COL_SERMON else ""

                # 본문이 없으면 스킵
                if not scripture.strip():
                    continue

                # 수정요청인데 피드백이 없으면 스킵
                if status == STATUS_REVISION_REQUEST and not feedback.strip():
                    continue

                pending.append({
                    "sheet_name": sheet_name,
                    "row_number": i,
                    "status": status,
                    "scripture": scripture.strip(),
                    "request": request.strip(),
                    "feedback": feedback.strip() if status == STATUS_REVISION_REQUEST else "",
                    "current_sermon": current_sermon if status == STATUS_REVISION_REQUEST else "",
                })

        except Exception as e:
            print(f"[SERMON] 시트 '{sheet_name}' 읽기 실패: {e}")
            continue

    return pending


def update_status(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    row_number: int,
    status: str
) -> bool:
    """
    상태 업데이트

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        sheet_name: 시트 이름
        row_number: 행 번호 (1-based)
        status: 새 상태

    Returns:
        성공 여부
    """
    try:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A{row_number}",
            valueInputOption="RAW",
            body={"values": [[status]]}
        ).execute()
        return True
    except Exception as e:
        print(f"[SERMON] 상태 업데이트 실패: {e}")
        return False


def save_sermon(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    row_number: int,
    sermon: str,
    is_revision: bool = False,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    설교문 저장

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        sheet_name: 시트 이름
        row_number: 행 번호 (1-based)
        sermon: 설교문 내용
        is_revision: 수정본 여부
        error: 에러 메시지 (실패 시)

    Returns:
        결과 딕셔너리
    """
    try:
        # 현재 시간 (KST)
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")

        if error:
            # 실패 시: 상태=실패, 에러메시지
            updates = [
                (f"A{row_number}", STATUS_FAILED),
                (f"H{row_number}", error),
                (f"G{row_number}", now),
            ]
        else:
            if is_revision:
                # 수정본: F열에 저장, 상태=완료
                updates = [
                    (f"A{row_number}", STATUS_COMPLETE),
                    (f"F{row_number}", sermon),
                    (f"G{row_number}", now),
                ]
            else:
                # 신규: D열에 저장, 상태=완료
                updates = [
                    (f"A{row_number}", STATUS_COMPLETE),
                    (f"D{row_number}", sermon),
                    (f"G{row_number}", now),
                ]

        # 배치 업데이트
        data = [
            {
                "range": f"'{sheet_name}'!{cell}",
                "values": [[value]]
            }
            for cell, value in updates
        ]

        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "valueInputOption": "RAW",
                "data": data
            }
        ).execute()

        print(f"[SERMON] 설교문 저장 완료: {sheet_name} 행 {row_number}")

        return {
            "success": True,
            "sheet_name": sheet_name,
            "row_number": row_number,
            "is_revision": is_revision,
            "saved_at": now,
        }

    except Exception as e:
        print(f"[SERMON] 설교문 저장 실패: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_sheet_data(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    row_number: int
) -> Optional[Dict[str, Any]]:
    """
    특정 행의 데이터 조회

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        sheet_name: 시트 이름
        row_number: 행 번호 (1-based)

    Returns:
        데이터 딕셔너리 또는 None
    """
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A{row_number}:H{row_number}"
        ).execute()

        rows = result.get('values', [])
        if not rows:
            return None

        row = rows[0]

        return {
            "sheet_name": sheet_name,
            "row_number": row_number,
            "status": row[COL_STATUS] if len(row) > COL_STATUS else "",
            "scripture": row[COL_SCRIPTURE] if len(row) > COL_SCRIPTURE else "",
            "request": row[COL_REQUEST] if len(row) > COL_REQUEST else "",
            "sermon": row[COL_SERMON] if len(row) > COL_SERMON else "",
            "feedback": row[COL_FEEDBACK] if len(row) > COL_FEEDBACK else "",
            "revision": row[COL_REVISION] if len(row) > COL_REVISION else "",
            "datetime": row[COL_DATETIME] if len(row) > COL_DATETIME else "",
            "error": row[COL_ERROR] if len(row) > COL_ERROR else "",
        }

    except Exception as e:
        print(f"[SERMON] 데이터 조회 실패: {e}")
        return None
