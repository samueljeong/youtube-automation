"""
Isekai Pipeline API Blueprint
/api/isekai/* 엔드포인트 담당

기능:
- 혈영 이세계편 시트 생성
- 에피소드 동기화
- 에피소드 데이터 전송
"""

import os
import json
from flask import Blueprint, request, jsonify

# Blueprint 생성
isekai_bp = Blueprint('isekai', __name__)


@isekai_bp.route('/api/isekai/create-sheet', methods=['GET', 'POST'])
def api_isekai_create_sheet():
    """혈영이세계 시트 생성"""
    from scripts.isekai_pipeline import create_isekai_sheet

    channel_id = request.args.get('channel_id') or (request.json.get('channel_id', '') if request.is_json else '')
    result = create_isekai_sheet(channel_id=channel_id)

    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code


@isekai_bp.route('/api/isekai/sync-episode', methods=['POST'])
def api_isekai_sync_episode():
    """특정 에피소드를 시트에 동기화"""
    from scripts.isekai_pipeline import sync_episode_from_files

    data = request.get_json() or {}
    episode = data.get('episode')

    if not episode:
        return jsonify({"ok": False, "error": "episode 파라미터가 필요합니다"}), 400

    try:
        episode_num = int(episode)
    except ValueError:
        return jsonify({"ok": False, "error": "episode은 숫자여야 합니다"}), 400

    result = sync_episode_from_files(episode_num)
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code


@isekai_bp.route('/api/isekai/sync-all', methods=['POST'])
def api_isekai_sync_all():
    """모든 에피소드를 시트에 동기화"""
    from scripts.isekai_pipeline import sync_all_episodes

    result = sync_all_episodes()
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code


@isekai_bp.route('/api/isekai/push-episode', methods=['POST'])
def api_isekai_push_episode():
    """에피소드 데이터를 직접 받아서 시트에 기록"""
    from scripts.isekai_pipeline.sheets import (
        get_sheets_service, get_sheet_id, get_episode_by_number,
        add_episode, SHEET_NAME, _clean_script_for_tts
    )
    from scripts.isekai_pipeline.config import SHEET_HEADERS

    data = request.get_json() or {}
    episode = data.get('episode')

    if not episode:
        return jsonify({"ok": False, "error": "episode 파라미터 필요"}), 400

    try:
        episode_num = int(episode)
    except ValueError:
        return jsonify({"ok": False, "error": "episode은 숫자여야 합니다"}), 400

    service = get_sheets_service()
    if not service:
        return jsonify({"ok": False, "error": "Sheets 서비스 연결 실패"}), 400

    sheet_id = get_sheet_id()
    if not sheet_id:
        return jsonify({"ok": False, "error": "AUTOMATION_SHEET_ID 필요"}), 400

    try:
        existing = get_episode_by_number(episode_num)

        if existing:
            row_index = existing["_row_index"]
        else:
            add_result = add_episode(
                episode=episode_num,
                title=data.get("title", f"제{episode_num}화"),
                summary=data.get("summary", ""),
            )
            if not add_result.get("ok"):
                return jsonify(add_result), 400
            row_index = add_result["row_index"]

        # 헤더 조회
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!A2:AZ2"
        ).execute()
        headers = result.get('values', [[]])[0]
        col_map = {h: i for i, h in enumerate(headers)}

        updates = []

        def add_update(header: str, value):
            if header in col_map and value:
                col_letter = chr(ord('A') + col_map[header])
                updates.append({
                    "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                    "values": [[str(value)]]
                })

        add_update("title", data.get("title"))
        add_update("summary", data.get("summary"))
        add_update("part", data.get("part", 1))

        script = data.get("script", "")
        if script:
            try:
                script = _clean_script_for_tts(script)
            except:
                pass
            add_update("대본", script)

        add_update("제목(GPT생성)", data.get("youtube_title"))
        add_update("썸네일문구(입력)", data.get("thumbnail_text"))

        status = data.get("status", "대기")
        add_update("상태", status)

        if updates:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=sheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": updates
                }
            ).execute()

        return jsonify({
            "ok": True,
            "episode": episode_num,
            "row_index": row_index,
            "fields_updated": len(updates),
            "status": status
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@isekai_bp.route('/isekai/push', methods=['GET'])
def isekai_push_page():
    """EP001 시트 전송 페이지"""
    html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>EP001 시트 전송</title>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
        button { font-size: 24px; padding: 20px 40px; cursor: pointer; background: #4CAF50; color: white; border: none; border-radius: 8px; }
        button:hover { background: #45a049; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        #result { margin-top: 20px; padding: 20px; background: #f5f5f5; border-radius: 8px; white-space: pre-wrap; }
        .success { color: green; }
        .error { color: red; }
    </style>
</head>
<body>
    <h1>혈영 이세계편 EP001</h1>
    <p><strong>제목:</strong> 이방인</p>
    <p><strong>대본:</strong> 26,079자</p>
    <p><strong>상태:</strong> 대기 (영상 생성 대기열)</p>
    <br>
    <button id="pushBtn" onclick="pushToSheet()">Google Sheets에 전송</button>
    <div id="result"></div>
    <script>
    async function pushToSheet() {
        const btn = document.getElementById('pushBtn');
        const resultDiv = document.getElementById('result');
        btn.disabled = true;
        btn.textContent = '전송 중...';
        resultDiv.innerHTML = '';
        resultDiv.className = '';
        try {
            const response = await fetch('/api/isekai/push-ep001', { method: 'POST' });
            const data = await response.json();
            if (data.ok) {
                resultDiv.innerHTML = '전송 성공!\\n\\n' + JSON.stringify(data, null, 2);
                resultDiv.className = 'success';
                btn.textContent = '완료!';
            } else {
                resultDiv.innerHTML = '전송 실패\\n\\n' + JSON.stringify(data, null, 2);
                resultDiv.className = 'error';
                btn.disabled = false;
                btn.textContent = '다시 시도';
            }
        } catch (error) {
            resultDiv.innerHTML = '오류: ' + error.message;
            resultDiv.className = 'error';
            btn.disabled = false;
            btn.textContent = '다시 시도';
        }
    }
    </script>
</body>
</html>'''
    return html


@isekai_bp.route('/api/isekai/push-ep001', methods=['POST'])
def api_isekai_push_ep001():
    """EP001 데이터를 시트에 전송 (파일에서 대본/이미지프롬프트 읽기)"""
    from scripts.isekai_pipeline.sheets import (
        get_sheets_service, get_sheet_id, get_episode_by_number,
        add_episode, SHEET_NAME
    )

    # blueprints 폴더의 상위 디렉토리
    base_dir = os.path.dirname(os.path.dirname(__file__))

    script_path = os.path.join(base_dir, 'static', 'isekai', 'EP001_script.txt')
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
    except Exception as e:
        return jsonify({"ok": False, "error": f"대본 파일 읽기 실패: {e}"}), 400

    image_prompt_path = os.path.join(base_dir, 'static', 'isekai', 'EP001_image_prompts.json')
    image_prompt = ""
    try:
        with open(image_prompt_path, 'r', encoding='utf-8') as f:
            prompts_data = json.load(f)
            image_prompt = prompts_data.get("main_image", {}).get("prompt", "")
    except Exception as e:
        print(f"[ISEKAI] 이미지 프롬프트 파일 읽기 실패 (무시): {e}")

    brief_path = os.path.join(base_dir, 'static', 'isekai', 'EP001_brief.json')
    scenes_json = ""
    cliffhanger = ""
    next_preview = ""
    try:
        with open(brief_path, 'r', encoding='utf-8') as f:
            brief_data = json.load(f)
            scenes = brief_data.get("scenes", [])
            if scenes:
                scenes_json = json.dumps(scenes, ensure_ascii=False)
            cliffhanger = brief_data.get("cliffhanger", "")
            next_preview = brief_data.get("next_preview", "")
    except Exception as e:
        print(f"[ISEKAI] 씬 데이터 파일 읽기 실패 (무시): {e}")

    metadata_path = os.path.join(base_dir, 'static', 'isekai', 'EP001_metadata.json')
    youtube_title = ""
    youtube_description = ""
    youtube_tags = ""
    thumbnail_hook = ""
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            yt = metadata.get("youtube", {})
            youtube_title = yt.get("title", "")
            youtube_description = yt.get("description", "")
            tags = yt.get("tags", [])
            if tags:
                youtube_tags = json.dumps(tags, ensure_ascii=False)
            thumb = metadata.get("thumbnail", {})
            thumbnail_hook = thumb.get("hook_text", "")
    except Exception as e:
        print(f"[ISEKAI] 메타데이터 파일 읽기 실패 (무시): {e}")

    ep001_data = {
        "episode": 1,
        "title": "이방인",
        "summary": "무림 최강의 검객 무영이 천마교주 혈마와의 최종전 중 차원 균열에 휩쓸려 이세계에 떨어진다. 모든 내공을 잃고 낯선 세계에서 눈을 뜬 그는, 언어도 통하지 않는 곳에서 생존을 위한 첫걸음을 내딛는다.",
        "status": "대기",
        "script": script_content,
        "image_prompt": image_prompt,
        "scenes": scenes_json,
        "youtube_title": youtube_title or "[혈영 이세계편] 제1화 - 이방인 | 무협 판타지 오디오북",
        "youtube_description": youtube_description,
        "youtube_tags": youtube_tags,
        "thumbnail_hook": thumbnail_hook,
        "cliffhanger": cliffhanger,
        "next_preview": next_preview,
        "음성": "chirp3:Charon",
        "공개설정": "private",
    }

    service = get_sheets_service()
    if not service:
        return jsonify({"ok": False, "error": "Sheets 서비스 연결 실패"}), 400

    sheet_id = get_sheet_id()
    if not sheet_id:
        return jsonify({"ok": False, "error": "AUTOMATION_SHEET_ID 필요"}), 400

    try:
        existing = get_episode_by_number(1)

        if existing:
            row_index = existing["_row_index"]
        else:
            add_result = add_episode(
                episode=1,
                title=ep001_data["title"],
                summary=ep001_data["summary"],
            )
            if not add_result.get("ok"):
                return jsonify(add_result), 400
            row_index = add_result["row_index"]

        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!A2:AZ2"
        ).execute()
        headers = result.get('values', [[]])[0]
        col_map = {h: i for i, h in enumerate(headers)}

        updates = []
        def add_update(header, value):
            if header in col_map and value:
                col_letter = chr(ord('A') + col_map[header])
                updates.append({
                    "range": f"{SHEET_NAME}!{col_letter}{row_index}",
                    "values": [[str(value)]]
                })

        add_update("title", ep001_data["title"])
        add_update("summary", ep001_data["summary"])
        add_update("scenes", ep001_data["scenes"])
        add_update("대본", ep001_data["script"])
        add_update("image_prompt", ep001_data["image_prompt"])
        add_update("상태", ep001_data["status"])

        add_update("youtube_title", ep001_data["youtube_title"])
        add_update("youtube_description", ep001_data["youtube_description"])
        add_update("youtube_tags", ep001_data["youtube_tags"])
        add_update("thumbnail_hook", ep001_data["thumbnail_hook"])
        add_update("cliffhanger", ep001_data["cliffhanger"])
        add_update("next_preview", ep001_data["next_preview"])

        add_update("음성", ep001_data["음성"])
        add_update("공개설정", ep001_data["공개설정"])

        if updates:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=sheet_id,
                body={"valueInputOption": "RAW", "data": updates}
            ).execute()

        return jsonify({
            "ok": True,
            "episode": 1,
            "row_index": row_index,
            "fields_updated": len(updates),
            "script_length": len(script_content),
            "message": "EP001 전송 완료!"
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500
