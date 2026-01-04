"""
무협 파이프라인 Google Sheets 연동 모듈

- 혈영 시트 생성/조회/업데이트
- 에피소드 데이터 관리
"""

import os
import sys
from typing import Dict, Any, List, Optional

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from .config import SERIES_INFO, EPISODE_TEMPLATES, SHEET_HEADERS


# 시트 이름 (시리즈 제목 사용)
SHEET_NAME = SERIES_INFO["title"]  # "혈영"


def get_sheets_service():
    """Google Sheets 서비스 객체 가져오기"""
    try:
        from drama_server import get_sheets_service_account
        return get_sheets_service_account()
    except Exception as e:
        print(f"[WUXIA-SHEETS] 서비스 연결 실패: {e}")
        return None


def get_sheet_id() -> str:
    """시트 ID 가져오기"""
    return os.environ.get("AUTOMATION_SHEET_ID", "")


def create_wuxia_sheet(channel_id: str = "") -> Dict[str, Any]:
    """
    혈영 시트 생성

    Args:
        channel_id: YouTube 채널 ID

    Returns:
        {"ok": True, "message": "..."}
    """
    service = get_sheets_service()
    if not service:
        return {"ok": False, "error": "Sheets 서비스 연결 실패"}

    sheet_id = get_sheet_id()
    if not sheet_id:
        return {"ok": False, "error": "AUTOMATION_SHEET_ID 환경변수 필요"}

    try:
        # 기존 시트 확인
        spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        existing_sheets = [
            sheet['properties']['title']
            for sheet in spreadsheet.get('sheets', [])
        ]

        if SHEET_NAME in existing_sheets:
            return {
                "ok": True,
                "status": "already_exists",
                "message": f"시트 '{SHEET_NAME}'이(가) 이미 존재합니다"
            }

        # 1) 시트 생성
        requests_body = [{
            "addSheet": {
                "properties": {"title": SHEET_NAME}
            }
        }]
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": requests_body}
        ).execute()

        # 2) 행 1: 채널ID
        row1 = ["채널ID", channel_id]

        # 3) 행 2: 헤더
        row2 = SHEET_HEADERS

        # 4) 시트에 쓰기
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={"values": [row1, row2]}
        ).execute()

        print(f"[WUXIA-SHEETS] 시트 '{SHEET_NAME}' 생성 완료")

        return {
            "ok": True,
            "status": "created",
            "sheet_name": SHEET_NAME,
            "columns": len(SHEET_HEADERS),
            "message": f"시트 '{SHEET_NAME}' 생성 완료 ({len(SHEET_HEADERS)}개 열)"
        }

    except Exception as e:
        print(f"[WUXIA-SHEETS] 시트 생성 실패: {e}")
        return {"ok": False, "error": str(e)}


def add_episode_template(episode: int) -> Dict[str, Any]:
    """
    에피소드 템플릿 데이터를 시트에 추가

    Args:
        episode: 에피소드 번호

    Returns:
        {"ok": True, "row_index": 3}
    """
    template = EPISODE_TEMPLATES.get(episode)
    if not template:
        return {"ok": False, "error": f"에피소드 {episode} 템플릿 없음"}

    service = get_sheets_service()
    if not service:
        return {"ok": False, "error": "Sheets 서비스 연결 실패"}

    sheet_id = get_sheet_id()
    if not sheet_id:
        return {"ok": False, "error": "AUTOMATION_SHEET_ID 환경변수 필요"}

    try:
        # 현재 데이터 확인
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!A:A"
        ).execute()

        rows = result.get('values', [])
        next_row = len(rows) + 1

        # 에피소드 데이터 준비
        episode_id = f"EP{episode:03d}"
        characters = ", ".join(template.get("characters", []))
        key_events = "\n".join(template.get("key_events", []))

        # 행 데이터 (SHEET_HEADERS 순서에 맞춤)
        row_data = [
            episode_id,                    # episode
            template.get("title", ""),     # title
            template.get("summary", ""),   # summary
            characters,                    # characters (콤마 구분)
            key_events,                    # key_events (줄바꿈 구분)
            "",                            # prev_episode
            "",                            # next_preview
            "",                            # thumbnail_copy
            # 이하 VIDEO_AUTOMATION_HEADERS
            "",                            # 상태
            "",                            # 대본
            "",                            # 인용링크
            "",                            # 제목(GPT생성)
            "",                            # 제목(입력)
            "",                            # 썸네일문구(입력)
            "private",                     # 공개설정
            "",                            # 예약시간
            "",                            # 플레이리스트ID
            "",                            # 음성
            "",                            # 영상URL
            "",                            # 쇼츠URL
            "",                            # 제목2
            "",                            # 제목3
            "",                            # 비용
            "",                            # 에러메시지
            "",                            # 작업시간
        ]

        # 시트에 추가
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!A{next_row}",
            valueInputOption="RAW",
            body={"values": [row_data]}
        ).execute()

        print(f"[WUXIA-SHEETS] 에피소드 {episode} 추가 완료 (행 {next_row})")

        return {
            "ok": True,
            "episode": episode,
            "episode_id": episode_id,
            "row_index": next_row,
            "title": template.get("title", "")
        }

    except Exception as e:
        print(f"[WUXIA-SHEETS] 에피소드 추가 실패: {e}")
        return {"ok": False, "error": str(e)}


def get_pending_episodes() -> List[Dict[str, Any]]:
    """상태가 '대기'인 에피소드 목록 조회 (영상 생성 대기)"""
    return _get_episodes_by_status("대기")


def get_ready_episodes() -> List[Dict[str, Any]]:
    """상태가 '준비'인 에피소드 목록 조회 (대본 생성 대기)"""
    return _get_episodes_by_status("준비")


def _get_episodes_by_status(status: str) -> List[Dict[str, Any]]:
    """특정 상태의 에피소드 목록 조회"""
    service = get_sheets_service()
    if not service:
        return []

    sheet_id = get_sheet_id()
    if not sheet_id:
        return []

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!A:Z"
        ).execute()

        rows = result.get('values', [])
        if len(rows) < 3:  # 채널ID행 + 헤더행 + 최소 1개 데이터
            return []

        headers = rows[1]
        episodes = []

        for i, row in enumerate(rows[2:], start=3):
            row_dict = {headers[j]: row[j] if j < len(row) else "" for j in range(len(headers))}

            if row_dict.get("상태", "").strip() == status:
                row_dict["_row_index"] = i
                episodes.append(row_dict)

        return episodes

    except Exception as e:
        print(f"[WUXIA-SHEETS] 조회 실패: {e}")
        return []


def _clean_script_for_tts(script: str) -> str:
    """
    TTS용 대본 정제 - JSON escape 문자 및 불필요한 부호 제거

    문제: Claude가 JSON 형식으로 대본을 생성하면 escape 문자가 포함됨
    예: [무영] \""안녕하세요.\"" → [무영] "안녕하세요."

    Returns:
        정제된 대본 텍스트
    """
    if not script:
        return script

    import re

    # 1) JSON escape 따옴표 정리: \""  →  "
    cleaned = script.replace('\\"', '"')

    # 2) 이중 따옴표 정리: ""  →  "
    cleaned = re.sub(r'"{2,}', '"', cleaned)

    # 3) 역슬래시+n을 실제 줄바꿈으로: \\n → \n
    cleaned = cleaned.replace('\\n', '\n')

    # 4) 남은 불필요한 역슬래시 제거: \\ → (공백)
    cleaned = cleaned.replace('\\\\', '')

    # 5) 대괄호 안 태그와 내용 사이 공백 정리
    # [나레이션]   내용 → [나레이션] 내용
    cleaned = re.sub(r'\[([^\]]+)\]\s+', r'[\1] ', cleaned)

    print(f"[WUXIA-SHEETS] 대본 정제 완료: {len(script)}자 → {len(cleaned)}자")

    return cleaned


def update_episode_with_script(
    row_index: int,
    script: str,
    youtube_title: str = None,
    thumbnail_text: str = None,
    scenes: list = None,
    cost: float = None,
) -> Dict[str, Any]:
    """
    대본 생성 결과로 에피소드 업데이트

    - 상태를 '대기'로 변경 (영상 생성 대기)
    - 대본, 제목, 썸네일 문구 등 저장
    - ★ 대본에서 JSON escape 문자 제거 (TTS 문제 방지)
    """
    # ★ 대본 정제 (TTS가 부호를 읽는 문제 해결)
    script = _clean_script_for_tts(script)

    service = get_sheets_service()
    if not service:
        return {"ok": False, "error": "Sheets 서비스 연결 실패"}

    sheet_id = get_sheet_id()
    if not sheet_id:
        return {"ok": False, "error": "AUTOMATION_SHEET_ID 환경변수 필요"}

    try:
        # 헤더 조회
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!A2:Z2"
        ).execute()
        headers = result.get('values', [[]])[0]

        # 열 인덱스 매핑
        col_map = {h: i for i, h in enumerate(headers)}

        # 업데이트할 데이터
        updates = []

        # 상태를 '대기'로 변경
        if "상태" in col_map:
            col_letter = chr(ord('A') + col_map["상태"])
            updates.append({
                "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                "values": [["대기"]]
            })

        # 대본
        if script and "대본" in col_map:
            col_letter = chr(ord('A') + col_map["대본"])
            updates.append({
                "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                "values": [[script]]
            })

        # 제목(GPT생성)
        if youtube_title and "제목(GPT생성)" in col_map:
            col_letter = chr(ord('A') + col_map["제목(GPT생성)"])
            updates.append({
                "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                "values": [[youtube_title]]
            })

        # 썸네일문구(입력) - 생성된 값으로 채움 (사용자가 수정 가능)
        if thumbnail_text and "썸네일문구(입력)" in col_map:
            col_letter = chr(ord('A') + col_map["썸네일문구(입력)"])
            updates.append({
                "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                "values": [[thumbnail_text]]
            })

        # 비용
        if cost is not None and "비용" in col_map:
            col_letter = chr(ord('A') + col_map["비용"])
            updates.append({
                "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                "values": [[f"${cost:.4f}"]]
            })

        if updates:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=sheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": updates
                }
            ).execute()

            print(f"[WUXIA-SHEETS] 행 {row_index} 대본 업데이트 완료, 상태 → '대기'")

        return {"ok": True, "row_index": row_index, "status": "대기"}

    except Exception as e:
        print(f"[WUXIA-SHEETS] 업데이트 실패: {e}")
        return {"ok": False, "error": str(e)}


def update_episode_status(
    row_index: int,
    status: str,
    script: str = None,
    video_url: str = None,
    error_msg: str = None,
    cost: float = None,
) -> Dict[str, Any]:
    """에피소드 상태 업데이트 (일반)"""
    from datetime import datetime, timedelta, timezone

    service = get_sheets_service()
    if not service:
        return {"ok": False, "error": "Sheets 서비스 연결 실패"}

    sheet_id = get_sheet_id()
    if not sheet_id:
        return {"ok": False, "error": "AUTOMATION_SHEET_ID 환경변수 필요"}

    try:
        # 헤더 조회
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!A2:Z2"
        ).execute()
        headers = result.get('values', [[]])[0]

        # 열 인덱스 매핑
        col_map = {h: i for i, h in enumerate(headers)}

        # 업데이트할 데이터
        updates = []

        if status and "상태" in col_map:
            col_letter = chr(ord('A') + col_map["상태"])
            updates.append({
                "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                "values": [[status]]
            })

            # ★ "처리중"으로 변경 시 작업시간 설정 (check-and-process 호환)
            if status == "처리중" and "작업시간" in col_map:
                kst = timezone(timedelta(hours=9))
                now_str = datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')
                col_letter = chr(ord('A') + col_map["작업시간"])
                updates.append({
                    "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                    "values": [[now_str]]
                })

        if script and "대본" in col_map:
            col_letter = chr(ord('A') + col_map["대본"])
            updates.append({
                "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                "values": [[script]]
            })

        if video_url and "영상URL" in col_map:
            col_letter = chr(ord('A') + col_map["영상URL"])
            updates.append({
                "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                "values": [[video_url]]
            })

        if error_msg and "에러메시지" in col_map:
            col_letter = chr(ord('A') + col_map["에러메시지"])
            updates.append({
                "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                "values": [[error_msg]]
            })

        if cost is not None and "비용" in col_map:
            col_letter = chr(ord('A') + col_map["비용"])
            updates.append({
                "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                "values": [[f"${cost:.4f}"]]
            })

        if updates:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=sheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": updates
                }
            ).execute()

            print(f"[WUXIA-SHEETS] 행 {row_index} 업데이트 완료: 상태={status}")

        return {"ok": True, "row_index": row_index, "status": status}

    except Exception as e:
        print(f"[WUXIA-SHEETS] 업데이트 실패: {e}")
        return {"ok": False, "error": str(e)}


def initialize_sheet_with_templates(channel_id: str = "") -> Dict[str, Any]:
    """
    시트 생성 + 에피소드 템플릿 일괄 등록
    """
    # 1) 시트 생성
    create_result = create_wuxia_sheet(channel_id)
    if not create_result.get("ok"):
        return create_result

    # 2) 템플릿 에피소드 등록
    added = []
    for ep_num in sorted(EPISODE_TEMPLATES.keys()):
        result = add_episode_template(ep_num)
        if result.get("ok"):
            added.append(result)

    return {
        "ok": True,
        "sheet_name": SHEET_NAME,
        "episodes_added": len(added),
        "episodes": added,
        "message": f"'{SHEET_NAME}' 시트 생성 및 {len(added)}개 에피소드 등록 완료"
    }


# =====================================================
# 테스트
# =====================================================

if __name__ == "__main__":
    print("=== 무협 시트 테스트 ===")

    # 시트 생성 테스트
    result = create_wuxia_sheet()
    print(f"시트 생성: {result}")

    # 에피소드 추가 테스트
    if result.get("ok"):
        ep_result = add_episode_template(1)
        print(f"에피소드 1 추가: {ep_result}")
