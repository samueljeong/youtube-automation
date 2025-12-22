"""
성경통독 Google Sheets 연동 모듈

기능:
  - BIBLE 시트 생성 (106개 에피소드 자동 등록)
  - 상태='대기' 행 조회
  - 상태 업데이트 (처리중/완료/실패)

사용법:
    from scripts.bible_pipeline.sheets import (
        create_bible_sheet,
        get_pending_episodes,
        update_episode_status
    )

    # 시트 생성 (106개 에피소드 자동 등록)
    result = create_bible_sheet(service, sheet_id)

    # 대기 중인 에피소드 조회
    pending = get_pending_episodes(service, sheet_id)

    # 상태 업데이트
    update_episode_status(service, sheet_id, row_idx, "완료", video_url="...")
"""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from .config import BIBLE_SHEET_NAME, BIBLE_SHEET_HEADERS
from .run import BiblePipeline


# ============================================================
# 시트 생성
# ============================================================

def create_bible_sheet(
    service,
    sheet_id: str,
    channel_id: str = "",
    force_recreate: bool = False
) -> Dict[str, Any]:
    """
    BIBLE 시트 생성 및 106개 에피소드 데이터 등록

    Args:
        service: Google Sheets API 서비스 객체
        sheet_id: 스프레드시트 ID
        channel_id: YouTube 채널 ID
        force_recreate: True면 기존 시트 삭제 후 재생성

    Returns:
        {"ok": True, "message": str, "episode_count": int} 또는
        {"ok": False, "error": str}
    """
    try:
        # 기존 시트 확인
        spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        existing_sheets = {
            sheet['properties']['title']: sheet['properties']['sheetId']
            for sheet in spreadsheet.get('sheets', [])
        }

        if BIBLE_SHEET_NAME in existing_sheets:
            if not force_recreate:
                return {
                    "ok": True,
                    "message": f"시트 '{BIBLE_SHEET_NAME}'이(가) 이미 존재합니다",
                    "already_exists": True
                }
            else:
                # 기존 시트 삭제
                sheet_gid = existing_sheets[BIBLE_SHEET_NAME]
                service.spreadsheets().batchUpdate(
                    spreadsheetId=sheet_id,
                    body={
                        "requests": [{
                            "deleteSheet": {"sheetId": sheet_gid}
                        }]
                    }
                ).execute()
                print(f"[BIBLE-SHEETS] 기존 시트 삭제: {BIBLE_SHEET_NAME}")

        # 1) 시트 생성
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={
                "requests": [{
                    "addSheet": {
                        "properties": {"title": BIBLE_SHEET_NAME}
                    }
                }]
            }
        ).execute()
        print(f"[BIBLE-SHEETS] 시트 생성: {BIBLE_SHEET_NAME}")

        # 2) 106개 에피소드 데이터 생성
        pipeline = BiblePipeline()
        episodes = pipeline.generate_all_bible_episodes()

        # 3) 데이터 행 구성
        # 행 1: 채널ID
        row1 = ["채널ID", channel_id]

        # 행 2: 헤더
        row2 = BIBLE_SHEET_HEADERS

        # 행 3~: 에피소드 데이터
        today = datetime.now().strftime("%Y-%m-%d")
        data_rows = []

        for ep in episodes:
            # 예상 시간 계산 (분)
            total_chars = sum(
                len(v.text) for ch in ep.chapters for v in ch.verses
            )
            estimated_minutes = round(total_chars / 910, 1)  # 910자/분

            # 책 목록 (다중 책인 경우)
            if ep.books_in_episode and len(ep.books_in_episode) > 1:
                books_str = ", ".join(ep.books_in_episode)
            else:
                books_str = ep.book

            row = [
                f"EP{ep.day_number:03d}",  # 에피소드
                books_str,                  # 책
                ep.start_chapter,           # 시작장
                ep.end_chapter,             # 끝장
                estimated_minutes,          # 예상시간(분)
                total_chars,               # 글자수
                "",                         # 상태 (대기로 설정 시 트리거)
                ep.video_title,            # 제목 (자동 생성)
                "",                         # 음성 (기본값 사용)
                "unlisted",                 # 공개설정
                "",                         # 예약시간
                "",                         # 플레이리스트ID
                "",                         # 영상URL
                "",                         # 에러메시지
                "",                         # 작업시간
                today,                      # 생성일
            ]
            data_rows.append(row)

        # 4) 시트에 쓰기
        all_rows = [row1, row2] + data_rows
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{BIBLE_SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={"values": all_rows}
        ).execute()

        print(f"[BIBLE-SHEETS] {len(episodes)}개 에피소드 등록 완료")

        return {
            "ok": True,
            "message": f"시트 '{BIBLE_SHEET_NAME}' 생성 및 {len(episodes)}개 에피소드 등록 완료",
            "episode_count": len(episodes),
            "already_exists": False
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


# ============================================================
# 데이터 조회
# ============================================================

def get_bible_sheet_header_map(service, sheet_id: str) -> Dict[str, int]:
    """
    BIBLE 시트 헤더 → 열 인덱스 매핑

    Returns:
        {"에피소드": 0, "책": 1, "상태": 6, ...}
    """
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{BIBLE_SHEET_NAME}!A2:Z2"  # 행 2가 헤더
        ).execute()

        headers = result.get('values', [[]])[0]
        return {header: idx for idx, header in enumerate(headers)}

    except Exception as e:
        print(f"[BIBLE-SHEETS] 헤더 조회 실패: {e}")
        return {}


def get_pending_episodes(
    service,
    sheet_id: str,
    limit: int = 1
) -> List[Dict[str, Any]]:
    """
    상태='대기'인 에피소드 조회

    Args:
        service: Google Sheets API 서비스 객체
        sheet_id: 스프레드시트 ID
        limit: 조회할 최대 개수

    Returns:
        [{"row_idx": 3, "episode_id": "EP001", "book": "창세기", ...}, ...]
    """
    try:
        # 전체 데이터 읽기 (행 3부터)
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{BIBLE_SHEET_NAME}!A3:Z"
        ).execute()

        rows = result.get('values', [])
        header_map = get_bible_sheet_header_map(service, sheet_id)

        if not header_map:
            return []

        pending = []
        status_idx = header_map.get("상태", 6)  # 기본값: 6번째 열

        for i, row in enumerate(rows):
            # 열 개수 부족 시 패딩
            while len(row) <= status_idx:
                row.append("")

            status = row[status_idx] if status_idx < len(row) else ""

            if status == "대기":
                episode_data = {
                    "row_idx": i + 3,  # 행 번호 (1-indexed, 헤더 제외)
                }

                # 헤더 기반으로 데이터 매핑
                for header, idx in header_map.items():
                    if idx < len(row):
                        episode_data[header] = row[idx]
                    else:
                        episode_data[header] = ""

                pending.append(episode_data)

                if len(pending) >= limit:
                    break

        return pending

    except Exception as e:
        print(f"[BIBLE-SHEETS] 대기 에피소드 조회 실패: {e}")
        return []


# ============================================================
# 상태 업데이트
# ============================================================

def update_episode_status(
    service,
    sheet_id: str,
    row_idx: int,
    status: str,
    **kwargs
) -> Dict[str, Any]:
    """
    에피소드 상태 및 결과 업데이트

    Args:
        service: Google Sheets API 서비스 객체
        sheet_id: 스프레드시트 ID
        row_idx: 행 번호 (1-indexed)
        status: 상태 값 (처리중/완료/실패)
        **kwargs: 추가 업데이트 필드
            - video_url: 영상 URL
            - error_message: 에러 메시지
            - work_time: 작업 시간

    Returns:
        {"ok": True} 또는 {"ok": False, "error": str}
    """
    try:
        header_map = get_bible_sheet_header_map(service, sheet_id)
        if not header_map:
            return {"ok": False, "error": "헤더를 찾을 수 없습니다"}

        # 업데이트할 셀 목록
        updates = []

        # 상태 업데이트
        if "상태" in header_map:
            col_letter = _idx_to_col_letter(header_map["상태"])
            updates.append({
                "range": f"{BIBLE_SHEET_NAME}!{col_letter}{row_idx}",
                "values": [[status]]
            })

        # 영상 URL
        if "video_url" in kwargs and "영상URL" in header_map:
            col_letter = _idx_to_col_letter(header_map["영상URL"])
            updates.append({
                "range": f"{BIBLE_SHEET_NAME}!{col_letter}{row_idx}",
                "values": [[kwargs["video_url"]]]
            })

        # 에러 메시지
        if "error_message" in kwargs and "에러메시지" in header_map:
            col_letter = _idx_to_col_letter(header_map["에러메시지"])
            updates.append({
                "range": f"{BIBLE_SHEET_NAME}!{col_letter}{row_idx}",
                "values": [[kwargs["error_message"]]]
            })

        # 작업 시간
        if "work_time" in kwargs and "작업시간" in header_map:
            col_letter = _idx_to_col_letter(header_map["작업시간"])
            updates.append({
                "range": f"{BIBLE_SHEET_NAME}!{col_letter}{row_idx}",
                "values": [[kwargs["work_time"]]]
            })

        # 배치 업데이트
        if updates:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=sheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": updates
                }
            ).execute()

        print(f"[BIBLE-SHEETS] 행 {row_idx} 상태 업데이트: {status}")
        return {"ok": True}

    except Exception as e:
        print(f"[BIBLE-SHEETS] 상태 업데이트 실패: {e}")
        return {"ok": False, "error": str(e)}


def _idx_to_col_letter(idx: int) -> str:
    """열 인덱스를 열 문자로 변환 (0 → A, 1 → B, ...)"""
    result = ""
    while idx >= 0:
        result = chr(ord('A') + idx % 26) + result
        idx = idx // 26 - 1
    return result


# ============================================================
# CLI 테스트
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="성경통독 Google Sheets 관리")
    parser.add_argument("--create", action="store_true", help="BIBLE 시트 생성")
    parser.add_argument("--force", action="store_true", help="기존 시트 삭제 후 재생성")
    parser.add_argument("--pending", action="store_true", help="대기 중인 에피소드 조회")
    parser.add_argument("--sheet-id", type=str, help="스프레드시트 ID")

    args = parser.parse_args()

    # Google Sheets 서비스 가져오기 (drama_server에서 import)
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

    if args.create:
        print("[BIBLE-SHEETS] 시트 생성 테스트 (서비스 계정 필요)")
        print("drama_server.py의 get_sheets_service_account() 사용 필요")

    elif args.pending:
        print("[BIBLE-SHEETS] 대기 에피소드 조회 테스트")
        print("drama_server.py의 get_sheets_service_account() 사용 필요")

    else:
        parser.print_help()
