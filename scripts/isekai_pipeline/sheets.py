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
            # 시트 존재 → 헤더만 업데이트
            row1 = ["채널ID", channel_id or SERIES_INFO.get("youtube_channel_id", "")]
            row2 = SHEET_HEADERS

            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"{SHEET_NAME}!A1",
                valueInputOption="RAW",
                body={"values": [row1, row2]}
            ).execute()

            print(f"[ISEKAI-SHEETS] 시트 '{SHEET_NAME}' 헤더 업데이트 완료")

            return {
                "ok": True,
                "status": "header_updated",
                "sheet_name": SHEET_NAME,
                "columns": len(SHEET_HEADERS),
                "message": f"시트 '{SHEET_NAME}' 헤더 업데이트 완료 ({len(SHEET_HEADERS)}개 열)"
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
            range=f"{SHEET_NAME}!A2:AZ2"
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
            range=f"{SHEET_NAME}!A2:AZ2"
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


def sync_episode_from_files(episode: int) -> Dict[str, Any]:
    """
    outputs/isekai/EP00X/ 폴더의 파일들을 읽어 시트에 동기화

    파일 구조:
    - EP001_brief.json      → summary, scenes
    - EP001_script.txt      → 대본
    - EP001_metadata.json   → 제목(GPT생성), 썸네일문구
    - EP001_image_prompts.json
    - EP001_tts_config.json
    - EP001_edit_config.json
    - EP001_subtitle_config.json
    - EP001_review.json     → review_status, review_score

    Returns:
        {"ok": True, "episode": 1, "status": "대기"}
    """
    import json
    from .config import OUTPUT_BASE

    episode_id = f"EP{episode:03d}"
    episode_dir = os.path.join(OUTPUT_BASE, episode_id)

    if not os.path.exists(episode_dir):
        return {"ok": False, "error": f"에피소드 디렉토리 없음: {episode_dir}"}

    # 파일 경로
    files = {
        "brief": os.path.join(episode_dir, f"{episode_id}_brief.json"),
        "script": os.path.join(episode_dir, f"{episode_id}_script.txt"),
        "metadata": os.path.join(episode_dir, f"{episode_id}_metadata.json"),
        "image_prompts": os.path.join(episode_dir, f"{episode_id}_image_prompts.json"),
        "tts_config": os.path.join(episode_dir, f"{episode_id}_tts_config.json"),
        "edit_config": os.path.join(episode_dir, f"{episode_id}_edit_config.json"),
        "subtitle_config": os.path.join(episode_dir, f"{episode_id}_subtitle_config.json"),
        "review": os.path.join(episode_dir, f"{episode_id}_review.json"),
    }

    # 데이터 수집
    data = {}

    # brief.json
    if os.path.exists(files["brief"]):
        with open(files["brief"], "r", encoding="utf-8") as f:
            brief = json.load(f)
            data["title"] = brief.get("title", "")
            data["summary"] = brief.get("summary", "")
            data["scenes"] = json.dumps(brief.get("scenes", []), ensure_ascii=False)
            data["part"] = brief.get("part", 1)

    # script.txt
    if os.path.exists(files["script"]):
        with open(files["script"], "r", encoding="utf-8") as f:
            data["script"] = f.read()

    # metadata.json
    if os.path.exists(files["metadata"]):
        with open(files["metadata"], "r", encoding="utf-8") as f:
            metadata = json.load(f)
            youtube = metadata.get("youtube", {})
            thumbnail = metadata.get("thumbnail", {})

            data["youtube_title"] = youtube.get("title", "")
            data["youtube_description"] = youtube.get("description", "")

            # 썸네일 문구 (줄바꿈 구분)
            thumb_lines = [
                thumbnail.get("text_line1", ""),
                thumbnail.get("text_line2", ""),
                thumbnail.get("text_line3", ""),
            ]
            data["thumbnail_text"] = "\n".join([l for l in thumb_lines if l])

    # review.json
    if os.path.exists(files["review"]):
        with open(files["review"], "r", encoding="utf-8") as f:
            review = json.load(f)
            data["review_status"] = review.get("status", "")
            data["review_score"] = review.get("quality_metrics", {}).get("overall_score", 0)

    # 시트에 동기화
    service = get_sheets_service()
    if not service:
        return {"ok": False, "error": "Sheets 서비스 연결 실패"}

    sheet_id = get_sheet_id()
    if not sheet_id:
        return {"ok": False, "error": "AUTOMATION_SHEET_ID 환경변수 필요"}

    try:
        # 에피소드 행 찾기 또는 생성
        existing = get_episode_by_number(episode)

        if existing:
            row_index = existing["_row_index"]
        else:
            # 새로 추가
            add_result = add_episode(
                episode=episode,
                title=data.get("title", f"제{episode}화"),
                summary=data.get("summary", ""),
            )
            if not add_result.get("ok"):
                return add_result
            row_index = add_result["row_index"]

        # 헤더 조회
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!A2:AZ2"
        ).execute()
        headers = result.get('values', [[]])[0]
        col_map = {h: i for i, h in enumerate(headers)}

        # 업데이트할 데이터 준비
        updates = []

        def add_update(header: str, value: str):
            if header in col_map and value:
                col_letter = chr(ord('A') + col_map[header])
                updates.append({
                    "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                    "values": [[value]]
                })

        # 기본 정보
        add_update("title", data.get("title", ""))
        add_update("summary", data.get("summary", ""))
        add_update("scenes", data.get("scenes", ""))
        add_update("part", str(data.get("part", 1)))

        # 대본 (정제 후)
        script = data.get("script", "")
        if script:
            script = _clean_script_for_tts(script)
            add_update("대본", script)

        # 메타데이터
        add_update("youtube_title", data.get("youtube_title", ""))
        add_update("thumbnail_hook", data.get("thumbnail_text", ""))

        # 리뷰 상태가 approved면 '대기'로 설정
        if data.get("review_status") == "approved":
            add_update("상태", "대기")
        else:
            add_update("상태", "준비")

        # 일괄 업데이트
        if updates:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=sheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": updates
                }
            ).execute()

        status = "대기" if data.get("review_status") == "approved" else "준비"
        print(f"[ISEKAI-SHEETS] EP{episode:03d} 동기화 완료: 상태={status}")

        return {
            "ok": True,
            "episode": episode,
            "episode_id": episode_id,
            "row_index": row_index,
            "status": status,
            "title": data.get("title", ""),
            "script_chars": len(data.get("script", "")),
        }

    except Exception as e:
        print(f"[ISEKAI-SHEETS] 동기화 실패: {e}")
        return {"ok": False, "error": str(e)}


def sync_all_episodes() -> Dict[str, Any]:
    """
    outputs/isekai/ 디렉토리의 모든 에피소드를 시트에 동기화
    """
    from .config import OUTPUT_BASE

    if not os.path.exists(OUTPUT_BASE):
        return {"ok": False, "error": f"출력 디렉토리 없음: {OUTPUT_BASE}"}

    # 시트 생성 확인
    create_result = create_isekai_sheet()
    if not create_result.get("ok") and create_result.get("status") != "already_exists":
        return create_result

    # EP로 시작하는 디렉토리 찾기
    synced = []
    failed = []

    for item in sorted(os.listdir(OUTPUT_BASE)):
        if item.startswith("EP") and os.path.isdir(os.path.join(OUTPUT_BASE, item)):
            try:
                ep_num = int(item[2:])
                result = sync_episode_from_files(ep_num)
                if result.get("ok"):
                    synced.append(result)
                else:
                    failed.append({"episode": ep_num, "error": result.get("error")})
            except ValueError:
                continue

    return {
        "ok": True,
        "synced": len(synced),
        "failed": len(failed),
        "episodes": synced,
        "errors": failed if failed else None,
    }


# =====================================================
# CLI 인터페이스
# =====================================================

def main():
    """
    CLI 명령어 처리

    사용법:
        python -m scripts.isekai_pipeline.sheets sync 1       # EP001 동기화
        python -m scripts.isekai_pipeline.sheets sync-all     # 모든 에피소드 동기화
        python -m scripts.isekai_pipeline.sheets create       # 시트 생성
        python -m scripts.isekai_pipeline.sheets init 1 60    # 시트 생성 + 60개 에피소드 등록
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="혈영 이세계편 Google Sheets 관리"
    )
    subparsers = parser.add_subparsers(dest="command", help="명령어")

    # sync: 단일 에피소드 동기화
    sync_parser = subparsers.add_parser("sync", help="에피소드를 시트에 동기화")
    sync_parser.add_argument("episode", type=int, help="에피소드 번호 (예: 1)")

    # sync-all: 모든 에피소드 동기화
    subparsers.add_parser("sync-all", help="모든 에피소드를 시트에 동기화")

    # create: 시트 생성
    create_parser = subparsers.add_parser("create", help="시트 생성")
    create_parser.add_argument("--channel-id", type=str, default="", help="YouTube 채널 ID")

    # init: 시트 생성 + 에피소드 등록
    init_parser = subparsers.add_parser("init", help="시트 생성 + 에피소드 일괄 등록")
    init_parser.add_argument("start", type=int, nargs="?", default=1, help="시작 에피소드 (기본: 1)")
    init_parser.add_argument("end", type=int, nargs="?", default=60, help="끝 에피소드 (기본: 60)")
    init_parser.add_argument("--channel-id", type=str, default="", help="YouTube 채널 ID")

    args = parser.parse_args()

    if args.command == "sync":
        print(f"[ISEKAI] EP{args.episode:03d} 동기화 시작...")
        result = sync_episode_from_files(args.episode)
        if result.get("ok"):
            print(f"✓ 동기화 완료: {result.get('title')} ({result.get('script_chars', 0):,}자)")
            print(f"  상태: {result.get('status')}")
        else:
            print(f"✗ 동기화 실패: {result.get('error')}")

    elif args.command == "sync-all":
        print("[ISEKAI] 모든 에피소드 동기화 시작...")
        result = sync_all_episodes()
        if result.get("ok"):
            print(f"✓ 동기화 완료: {result.get('synced')}개 성공, {result.get('failed')}개 실패")
            for ep in result.get("episodes", []):
                print(f"  - EP{ep['episode']:03d}: {ep.get('title')} ({ep.get('script_chars', 0):,}자)")
        else:
            print(f"✗ 동기화 실패: {result.get('error')}")

    elif args.command == "create":
        print("[ISEKAI] 시트 생성 중...")
        result = create_isekai_sheet(args.channel_id)
        print(f"결과: {result.get('message', result)}")

    elif args.command == "init":
        print(f"[ISEKAI] 시트 초기화 중 (EP{args.start:03d} ~ EP{args.end:03d})...")
        result = initialize_sheet_with_episodes(
            channel_id=args.channel_id,
            start_episode=args.start,
            end_episode=args.end,
        )
        print(f"결과: {result.get('message', result)}")

    else:
        parser.print_help()
        print("\n예시:")
        print("  python -m scripts.isekai_pipeline.sheets sync 1")
        print("  python -m scripts.isekai_pipeline.sheets sync-all")


if __name__ == "__main__":
    main()
