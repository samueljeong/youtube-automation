"""
쇼츠 파이프라인 - Google Sheets 연동

SHORTS 시트 구조:
- 행 1: 채널ID | UCxxx
- 행 2: 헤더
- 행 3~: 데이터
"""

import os
import json
import time
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build

from .config import SHEET_NAME, ALL_HEADERS, COLLECT_HEADERS, VIDEO_AUTOMATION_HEADERS


class SheetsSaveError(Exception):
    """Google Sheets 저장 실패 예외"""
    pass


def get_sheets_service():
    """Google Sheets API 서비스 객체 반환"""
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON 환경변수가 설정되지 않았습니다")

    creds_data = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_data,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)


def get_spreadsheet_id() -> str:
    """스프레드시트 ID 반환"""
    sheet_id = os.environ.get("AUTOMATION_SHEET_ID") or os.environ.get("NEWS_SHEET_ID")
    if not sheet_id:
        raise ValueError("AUTOMATION_SHEET_ID 또는 NEWS_SHEET_ID 환경변수가 설정되지 않았습니다")
    return sheet_id


def create_shorts_sheet(
    service=None,
    spreadsheet_id: str = None,
    channel_id: str = "",
    force: bool = False
) -> bool:
    """
    SHORTS 시트 생성

    Args:
        service: Google Sheets API 서비스 객체 (없으면 자동 생성)
        spreadsheet_id: 스프레드시트 ID (없으면 환경변수에서)
        channel_id: YouTube 채널 ID
        force: True면 기존 시트 삭제 후 재생성

    Returns:
        True: 생성 성공, False: 이미 존재 (force=False일 때)
    """
    if service is None:
        service = get_sheets_service()
    if spreadsheet_id is None:
        spreadsheet_id = get_spreadsheet_id()

    try:
        # 1) 기존 시트 목록 확인
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()

        existing_sheets = {
            sheet['properties']['title']: sheet['properties']['sheetId']
            for sheet in spreadsheet.get('sheets', [])
        }

        if SHEET_NAME in existing_sheets:
            if force:
                # 기존 시트 삭제
                service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={
                        "requests": [{
                            "deleteSheet": {
                                "sheetId": existing_sheets[SHEET_NAME]
                            }
                        }]
                    }
                ).execute()
                print(f"[SHORTS] 기존 시트 '{SHEET_NAME}' 삭제")
            else:
                print(f"[SHORTS] 시트 '{SHEET_NAME}' 이미 존재 - 건너뜀")
                return False

        # 2) 시트 생성
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [{
                    "addSheet": {
                        "properties": {
                            "title": SHEET_NAME,
                        }
                    }
                }]
            }
        ).execute()
        print(f"[SHORTS] 시트 '{SHEET_NAME}' 생성 완료")

        # 3) 행 1: 채널ID 설정
        row1 = ["채널ID", channel_id]

        # 4) 행 2: 헤더
        row2 = ALL_HEADERS

        # 5) 시트에 쓰기
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={"values": [row1, row2]}
        ).execute()

        print(f"[SHORTS] 헤더 설정 완료 ({len(row2)}개 열)")
        print(f"         - 수집 영역: {len(COLLECT_HEADERS)}개")
        print(f"         - 영상 자동화: {len(VIDEO_AUTOMATION_HEADERS)}개")

        return True

    except Exception as e:
        print(f"[SHORTS] 시트 생성 실패: {e}")
        raise


def get_header_mapping(service, spreadsheet_id: str) -> Dict[str, int]:
    """
    SHORTS 시트의 헤더 매핑 반환

    Returns:
        {"헤더명": 열인덱스, ...}
    """
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{SHEET_NAME}'!A2:Z2"
    ).execute()
    headers = result.get('values', [[]])[0]
    return {h: i for i, h in enumerate(headers)}


def read_pending_rows(
    service=None,
    spreadsheet_id: str = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    상태='대기'인 행 읽기

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        limit: 최대 반환 행 수

    Returns:
        [{"row_number": 3, "celebrity": "...", "상태": "대기", ...}, ...]
    """
    if service is None:
        service = get_sheets_service()
    if spreadsheet_id is None:
        spreadsheet_id = get_spreadsheet_id()

    try:
        # 헤더 매핑
        header_map = get_header_mapping(service, spreadsheet_id)
        status_col = header_map.get("상태", -1)

        if status_col == -1:
            print("[SHORTS] '상태' 열을 찾을 수 없음")
            return []

        # 데이터 읽기 (행 3부터)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{SHEET_NAME}'!A3:Z"
        ).execute()
        rows = result.get('values', [])

        # 대기 상태인 행 필터링
        pending = []
        for i, row in enumerate(rows, start=3):
            if len(row) > status_col and row[status_col] == "대기":
                # 행 데이터를 딕셔너리로 변환
                row_data = {"row_number": i}
                for header, col_idx in header_map.items():
                    row_data[header] = row[col_idx] if col_idx < len(row) else ""
                pending.append(row_data)

                if len(pending) >= limit:
                    break

        print(f"[SHORTS] 대기 상태 행 {len(pending)}개 조회")
        return pending

    except Exception as e:
        print(f"[SHORTS] 대기 행 조회 실패: {e}")
        return []


def update_cell(
    service,
    spreadsheet_id: str,
    row: int,
    column: str,
    value: str
) -> bool:
    """
    특정 셀 업데이트

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        row: 행 번호 (1-indexed)
        column: 헤더명 (예: "상태", "영상URL")
        value: 새 값

    Returns:
        성공 여부
    """
    try:
        header_map = get_header_mapping(service, spreadsheet_id)
        col_idx = header_map.get(column, -1)

        if col_idx == -1:
            print(f"[SHORTS] '{column}' 열을 찾을 수 없음")
            return False

        # 열 문자 변환 (0 -> A, 1 -> B, ...)
        col_letter = chr(65 + col_idx)
        cell_range = f"'{SHEET_NAME}'!{col_letter}{row}"

        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=cell_range,
            valueInputOption="RAW",
            body={"values": [[value]]}
        ).execute()

        print(f"[SHORTS] 셀 업데이트: {cell_range} = {value[:50]}..." if len(value) > 50 else f"[SHORTS] 셀 업데이트: {cell_range} = {value}")
        return True

    except Exception as e:
        print(f"[SHORTS] 셀 업데이트 실패: {e}")
        return False


def append_row(
    service=None,
    spreadsheet_id: str = None,
    data: Dict[str, str] = None
) -> bool:
    """
    SHORTS 시트에 새 행 추가

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        data: {"celebrity": "...", "issue_type": "...", ...}

    Returns:
        성공 여부
    """
    if service is None:
        service = get_sheets_service()
    if spreadsheet_id is None:
        spreadsheet_id = get_spreadsheet_id()
    if data is None:
        return False

    try:
        # 헤더 매핑
        header_map = get_header_mapping(service, spreadsheet_id)

        # 데이터를 헤더 순서에 맞게 변환
        row = [''] * len(header_map)
        for key, value in data.items():
            if key in header_map:
                row[header_map[key]] = value

        # 행 추가
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"'{SHEET_NAME}'!A3",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]}
        ).execute()

        updated_rows = result.get("updates", {}).get("updatedRows", 0)
        print(f"[SHORTS] 새 행 추가 완료 ({updated_rows}행)")
        return True

    except Exception as e:
        print(f"[SHORTS] 행 추가 실패: {e}")
        raise SheetsSaveError(f"행 추가 실패: {e}")


def check_duplicate(
    service,
    spreadsheet_id: str,
    person: str,
    news_url: str
) -> bool:
    """
    중복 체크 (같은 인물 + 같은 뉴스 URL)

    Args:
        person: 인물명 (연예인/운동선수 등)
        news_url: 뉴스 URL

    Returns:
        True: 중복 있음, False: 중복 없음
    """
    try:
        header_map = get_header_mapping(service, spreadsheet_id)
        # person 헤더 우선, 없으면 celebrity 헤더 사용 (호환성)
        person_col = header_map.get("person", header_map.get("celebrity", 2))
        url_col = header_map.get("news_url", 4)

        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{SHEET_NAME}'!A3:Z"
        ).execute()
        rows = result.get('values', [])

        for row in rows:
            if len(row) > max(person_col, url_col):
                if (row[person_col] == person and
                    row[url_col] == news_url):
                    return True
        return False

    except Exception as e:
        print(f"[SHORTS] 중복 체크 실패 (계속 진행): {e}")
        return False


def update_status(
    service,
    spreadsheet_id: str,
    row: int,
    status: str,
    **extra_fields
) -> bool:
    """
    상태 및 추가 필드 업데이트

    Args:
        service: Google Sheets API 서비스 객체
        spreadsheet_id: 스프레드시트 ID
        row: 행 번호
        status: 새 상태 (대기/처리중/완료/실패)
        **extra_fields: 추가 필드 (예: 영상URL="...", 에러메시지="...")

    Returns:
        성공 여부
    """
    success = update_cell(service, spreadsheet_id, row, "상태", status)

    for field, value in extra_fields.items():
        if value is not None:
            update_cell(service, spreadsheet_id, row, field, str(value))

    return success
