"""
혈영 이세계편 파이프라인 Google Sheets 연동 모듈

- 시트 생성/조회/업데이트
- 에피소드 데이터 관리
"""

import os
import sys
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

# 프로젝트 루트 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from .config import SERIES_INFO, PART_STRUCTURE, SHEET_NAME, SHEET_HEADERS


def get_sheets_service():
    """Google Sheets 서비스 객체 가져오기"""
    try:
        from drama_server import get_sheets_service_account
        return get_sheets_service_account()
    except Exception as e:
        print(f"[ISEKAI-SHEETS] 서비스 연결 실패: {e}")
        return None


def get_sheet_id() -> str:
    """시트 ID 가져오기"""
    return os.environ.get("AUTOMATION_SHEET_ID", "")


def create_isekai_sheet(channel_id: str = "") -> Dict[str, Any]:
    """
    혈영 이세계편 시트 생성

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
        row1 = ["채널ID", channel_id or SERIES_INFO.get("youtube_channel_id", "")]

        # 3) 행 2: 헤더
        row2 = SHEET_HEADERS

        # 4) 시트에 쓰기
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="RAW",
            body={"values": [row1, row2]}
        ).execute()

        print(f"[ISEKAI-SHEETS] 시트 '{SHEET_NAME}' 생성 완료")

        return {
            "ok": True,
            "status": "created",
            "sheet_name": SHEET_NAME,
            "columns": len(SHEET_HEADERS),
            "message": f"시트 '{SHEET_NAME}' 생성 완료 ({len(SHEET_HEADERS)}개 열)"
        }

    except Exception as e:
        print(f"[ISEKAI-SHEETS] 시트 생성 실패: {e}")
        return {"ok": False, "error": str(e)}


def add_episode(episode: int, title: str = "", summary: str = "") -> Dict[str, Any]:
    """
    에피소드 데이터를 시트에 추가

    Args:
        episode: 에피소드 번호 (1~60)
        title: 에피소드 제목
        summary: 에피소드 요약

    Returns:
        {"ok": True, "row_index": 3}
    """
    service = get_sheets_service()
    if not service:
        return {"ok": False, "error": "Sheets 서비스 연결 실패"}

    sheet_id = get_sheet_id()
    if not sheet_id:
        return {"ok": False, "error": "AUTOMATION_SHEET_ID 환경변수 필요"}

    # 부 정보 가져오기
    part_info = {}
    for part_num, part_data in PART_STRUCTURE.items():
        start, end = part_data["episodes"]
        if start <= episode <= end:
            part_info = {"part": part_num, **part_data}
            break

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

        # 씬 구조 (기본 템플릿)
        scenes_json = "[]"

        # 행 데이터 (SHEET_HEADERS 순서에 맞춤)
        row_data = [
            episode_id,                         # episode
            part_info.get("part", 1),           # part
            title or f"제{episode}화",          # title
            summary or part_info.get("summary", ""),  # summary
            scenes_json,                        # scenes (JSON)
            # 영상 자동화 헤더
            "준비",                             # 상태 (대본 생성 대기)
            "",                                 # 대본
            "",                                 # 인용링크
            "",                                 # 제목(GPT생성)
            "",                                 # 제목(입력)
            "",                                 # 썸네일문구(입력)
            "private",                          # 공개설정
            "",                                 # 예약시간
            SERIES_INFO.get("playlist_id", ""), # 플레이리스트ID
            "chirp3:Charon",                    # 음성
            "",                                 # 영상URL
            "",                                 # 쇼츠URL
            "",                                 # 제목2
            "",                                 # 제목3
            "",                                 # 비용
            "",                                 # 에러메시지
            "",                                 # 작업시간
        ]

        # 시트에 추가
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!A{next_row}",
            valueInputOption="RAW",
            body={"values": [row_data]}
        ).execute()

        print(f"[ISEKAI-SHEETS] 에피소드 {episode} 추가 완료 (행 {next_row})")

        return {
            "ok": True,
            "episode": episode,
            "episode_id": episode_id,
            "row_index": next_row,
            "title": title,
            "part": part_info.get("part", 1),
        }

    except Exception as e:
        print(f"[ISEKAI-SHEETS] 에피소드 추가 실패: {e}")
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
        print(f"[ISEKAI-SHEETS] 조회 실패: {e}")
        return []


def get_episode_by_number(episode: int) -> Optional[Dict[str, Any]]:
    """에피소드 번호로 데이터 조회"""
    service = get_sheets_service()
    if not service:
        return None

    sheet_id = get_sheet_id()
    if not sheet_id:
        return None

    episode_id = f"EP{episode:03d}"

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!A:Z"
        ).execute()

        rows = result.get('values', [])
        if len(rows) < 3:
            return None

        headers = rows[1]

        for i, row in enumerate(rows[2:], start=3):
            if row and row[0] == episode_id:
                row_dict = {headers[j]: row[j] if j < len(row) else "" for j in range(len(headers))}
                row_dict["_row_index"] = i
                return row_dict

        return None

    except Exception as e:
        print(f"[ISEKAI-SHEETS] 조회 실패: {e}")
        return None


def _clean_script_for_tts(script: str) -> str:
    """
    TTS용 대본 정제 - JSON escape 문자 및 불필요한 부호 제거
    """
    if not script:
        return script

    # 1) JSON escape 따옴표 정리
    cleaned = script.replace('\\"', '"')

    # 2) 이중 따옴표 정리
    cleaned = re.sub(r'"{2,}', '"', cleaned)

    # 3) 역슬래시+n을 실제 줄바꿈으로
    cleaned = cleaned.replace('\\n', '\n')

    # 4) 남은 불필요한 역슬래시 제거
    cleaned = cleaned.replace('\\\\', '')

    print(f"[ISEKAI-SHEETS] 대본 정제 완료: {len(script)}자 → {len(cleaned)}자")

    return cleaned


def update_episode_with_result(
    row_index: int,
    script: str = None,
    youtube_title: str = None,
    thumbnail_text: str = None,
    audio_path: str = None,
    video_url: str = None,
    cost: float = None,
) -> Dict[str, Any]:
    """
    파이프라인 결과로 에피소드 업데이트

    - 상태를 '대기'로 변경 (영상 생성 대기)
    - 대본, 제목, 썸네일 문구 등 저장
    """
    service = get_sheets_service()
    if not service:
        return {"ok": False, "error": "Sheets 서비스 연결 실패"}

    sheet_id = get_sheet_id()
    if not sheet_id:
        return {"ok": False, "error": "AUTOMATION_SHEET_ID 환경변수 필요"}

    # 대본 정제
    if script:
        script = _clean_script_for_tts(script)

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

        # 썸네일문구(입력)
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

            print(f"[ISEKAI-SHEETS] 행 {row_index} 업데이트 완료, 상태 → '대기'")

        return {"ok": True, "row_index": row_index, "status": "대기"}

    except Exception as e:
        print(f"[ISEKAI-SHEETS] 업데이트 실패: {e}")
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

            # "처리중"으로 변경 시 작업시간 설정
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

            print(f"[ISEKAI-SHEETS] 행 {row_index} 업데이트 완료: 상태={status}")

        return {"ok": True, "row_index": row_index, "status": status}

    except Exception as e:
        print(f"[ISEKAI-SHEETS] 업데이트 실패: {e}")
        return {"ok": False, "error": str(e)}


def initialize_sheet_with_episodes(
    channel_id: str = "",
    start_episode: int = 1,
    end_episode: int = 60,
) -> Dict[str, Any]:
    """
    시트 생성 + 에피소드 일괄 등록

    Args:
        channel_id: YouTube 채널 ID
        start_episode: 시작 에피소드 번호
        end_episode: 끝 에피소드 번호

    Returns:
        {"ok": True, "episodes_added": 60}
    """
    # 1) 시트 생성
    create_result = create_isekai_sheet(channel_id)
    if not create_result.get("ok") and create_result.get("status") != "already_exists":
        return create_result

    # 2) 에피소드 등록
    added = []
    for ep_num in range(start_episode, end_episode + 1):
        # 부 정보에서 기본 제목 가져오기
        part_info = {}
        for part_num, part_data in PART_STRUCTURE.items():
            start, end = part_data["episodes"]
            if start <= ep_num <= end:
                part_info = part_data
                break

        result = add_episode(
            episode=ep_num,
            title=f"제{ep_num}화",
            summary=part_info.get("summary", ""),
        )
        if result.get("ok"):
            added.append(result)

    return {
        "ok": True,
        "sheet_name": SHEET_NAME,
        "episodes_added": len(added),
        "start": start_episode,
        "end": end_episode,
        "message": f"'{SHEET_NAME}' 시트 생성 및 {len(added)}개 에피소드 등록 완료"
    }


def get_prev_episode_summary(episode: int) -> str:
    """이전 에피소드의 요약 가져오기 (연속성 유지용)"""
    if episode <= 1:
        return ""

    prev_ep = get_episode_by_number(episode - 1)
    if prev_ep:
        return prev_ep.get("summary", "")

    return ""


# =====================================================
# 테스트
# =====================================================

if __name__ == "__main__":
    print("=== 이세계 시트 테스트 ===")

    # 시트 생성 테스트
    result = create_isekai_sheet()
    print(f"시트 생성: {result}")

    # 에피소드 추가 테스트
    if result.get("ok") or result.get("status") == "already_exists":
        ep_result = add_episode(1, "이방인의 눈", "무영이 이세계에 깨어나다")
        print(f"에피소드 1 추가: {ep_result}")
