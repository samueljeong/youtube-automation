"""
Shorts Pipeline API Blueprint
/api/shorts/* 엔드포인트 담당

기능:
- 시트 생성
- 뉴스 수집
- YouTube 트렌딩 수집
- 대본 생성
- 파이프라인 실행
- 바이럴 파이프라인
- Agent 시스템
"""

import os
import asyncio
from flask import Blueprint, request, jsonify

# Blueprint 생성
shorts_bp = Blueprint('shorts', __name__)


@shorts_bp.route('/api/shorts/create-sheet', methods=['GET', 'POST'])
def api_shorts_create_sheet():
    """SHORTS 시트 생성"""
    try:
        from scripts.shorts_pipeline import create_shorts_sheet, get_sheets_service, get_spreadsheet_id

        channel_id = request.args.get('channel_id', '')
        force = request.args.get('force', '0') == '1'

        service = get_sheets_service()
        spreadsheet_id = get_spreadsheet_id()

        created = create_shorts_sheet(
            service=service,
            spreadsheet_id=spreadsheet_id,
            channel_id=channel_id,
            force=force
        )

        if created:
            return jsonify({
                "ok": True,
                "message": "SHORTS 시트 생성 완료",
                "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
            })
        else:
            return jsonify({
                "ok": True,
                "message": "SHORTS 시트가 이미 존재합니다",
                "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@shorts_bp.route('/api/shorts/collect-news', methods=['GET', 'POST'])
def api_shorts_collect_news():
    """연예/스포츠/국뽕 뉴스 수집 및 SHORTS 시트 저장"""
    try:
        from scripts.shorts_pipeline import run_news_collection

        max_items = int(request.args.get('max_items', '10'))
        save_to_sheet = request.args.get('save', '1') != '0'

        result = run_news_collection(
            max_items=max_items,
            save_to_sheet=save_to_sheet
        )

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@shorts_bp.route('/api/shorts/youtube-collect', methods=['GET', 'POST'])
def api_shorts_youtube_collect():
    """YouTube 트렌딩 쇼츠 수집 및 SHORTS 시트 저장"""
    try:
        from scripts.shorts_pipeline import run_youtube_collection

        if request.is_json:
            data = request.get_json() or {}
        else:
            data = {}

        limit = int(data.get('limit') or request.args.get('limit', '10'))
        min_engagement = float(data.get('min_engagement') or request.args.get('min_engagement', '30'))
        categories = data.get('categories') or None
        save_to_sheet = str(data.get('save', request.args.get('save', '1'))) != '0'

        result = run_youtube_collection(
            max_items=limit,
            min_engagement=min_engagement,
            categories=categories,
            save_to_sheet=save_to_sheet
        )

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@shorts_bp.route('/api/shorts/generate-script', methods=['POST'])
def api_shorts_generate_script():
    """대기 상태 뉴스에 대해 대본 생성"""
    try:
        from scripts.shorts_pipeline import run_script_generation

        limit = int(request.args.get('limit', '1'))
        result = run_script_generation(limit=limit)

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@shorts_bp.route('/api/shorts/check-and-process', methods=['GET', 'POST'])
def api_shorts_check_and_process():
    """Shorts 파이프라인 전체 실행 (cron job용)"""
    try:
        from scripts.shorts_pipeline import run_shorts_pipeline, get_sheets_service, get_spreadsheet_id, SHEET_NAME, read_pending_rows

        person = request.args.get('person')
        collect_news = request.args.get('collect', '1') != '0'
        generate_script = request.args.get('generate', '1') != '0'
        generate_video = request.args.get('video', '0') == '1'
        limit = int(request.args.get('limit', '1'))

        print(f"\n[SHORTS API] check-and-process 시작")
        print(f"  - collect_news: {collect_news}")
        print(f"  - generate_script: {generate_script}")
        print(f"  - generate_video: {generate_video}")
        print(f"  - limit: {limit}")

        service = get_sheets_service()
        spreadsheet_id = get_spreadsheet_id()
        pending = read_pending_rows(service, spreadsheet_id, limit=10)
        print(f"[SHORTS API] 대기 상태 행: {len(pending)}개")
        for p in pending[:3]:
            print(f"  - 행 {p.get('row_number')}: {p.get('person', p.get('celebrity', ''))}")

        result = run_shorts_pipeline(
            person=person,
            collect_news=collect_news,
            generate_script=generate_script,
            generate_video=generate_video,
            limit=limit
        )

        result["debug"] = {
            "pending_rows_found": len(pending),
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": SHEET_NAME,
        }

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@shorts_bp.route('/api/shorts/status', methods=['GET'])
def api_shorts_status():
    """Shorts 파이프라인 상태 확인"""
    try:
        from scripts.shorts_pipeline import get_sheets_service, get_spreadsheet_id, SHEET_NAME

        service = get_sheets_service()
        spreadsheet_id = get_spreadsheet_id()

        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{SHEET_NAME}'!A2:Z"
        ).execute()
        rows = result.get('values', [])

        if not rows:
            return jsonify({
                "ok": True,
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
                "total": 0,
                "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
            })

        headers = rows[0] if rows else []
        status_col = headers.index("상태") if "상태" in headers else -1

        counts = {"대기": 0, "준비": 0, "처리중": 0, "완료": 0, "대본완료": 0, "실패": 0}
        sample_rows = []
        for i, row in enumerate(rows[1:], start=3):
            if status_col >= 0 and status_col < len(row):
                status = row[status_col]
                if status in counts:
                    counts[status] += 1
                if status == "대기" and len(sample_rows) < 3:
                    person_col = headers.index("person") if "person" in headers else -1
                    person = row[person_col] if person_col >= 0 and person_col < len(row) else ""
                    sample_rows.append({"row": i, "person": person})

        return jsonify({
            "ok": True,
            "pending": counts["대기"],
            "ready": counts["준비"],
            "processing": counts["처리중"],
            "script_done": counts["대본완료"],
            "completed": counts["완료"],
            "failed": counts["실패"],
            "total": len(rows) - 1,
            "headers": headers,
            "status_col": status_col,
            "sample_pending": sample_rows,
            "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@shorts_bp.route('/api/shorts/viral-pipeline', methods=['POST'])
def api_shorts_viral_pipeline():
    """바이럴 점수 기반 자동 쇼츠 파이프라인"""
    try:
        from scripts.shorts_pipeline.run import run_viral_pipeline

        data = request.get_json() or {}

        min_score = data.get("min_score", 40)
        categories = data.get("categories")
        generate_video = data.get("generate_video", True)
        upload_youtube = data.get("upload_youtube", False)
        privacy_status = data.get("privacy_status", "private")
        channel_id = data.get("channel_id")
        save_to_sheet = data.get("save_to_sheet", True)

        print(f"[API] /api/shorts/viral-pipeline 호출")
        print(f"[API] 파라미터: min_score={min_score}, generate_video={generate_video}, upload_youtube={upload_youtube}")

        result = run_viral_pipeline(
            min_score=min_score,
            categories=categories,
            generate_video=generate_video,
            upload_youtube=upload_youtube,
            privacy_status=privacy_status,
            channel_id=channel_id,
            save_to_sheet=save_to_sheet
        )

        if result.get("ok"):
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@shorts_bp.route('/api/shorts/agent-run', methods=['POST'])
def api_shorts_agent_run():
    """Supervisor Agent를 통한 쇼츠 생성"""
    try:
        import sys

        data = request.get_json() or {}

        topic = data.get("topic", "")
        person = data.get("person", "")
        category = data.get("category", "연예인")
        issue_type = data.get("issue_type", "이슈")
        skip_images = data.get("skip_images", False)

        if not topic:
            return jsonify({"ok": False, "error": "topic은 필수입니다"}), 400

        agents_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "shorts_pipeline", "agents")
        if agents_dir not in sys.path:
            sys.path.insert(0, agents_dir)

        from supervisor import SupervisorAgent

        supervisor = SupervisorAgent()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            supervisor.run(
                topic=topic,
                person=person or topic.split()[0],
                category=category,
                issue_type=issue_type,
                skip_images=skip_images,
            )
        )

        if result.success:
            return jsonify({
                "ok": True,
                "task_id": result.data.get("task_id"),
                "script": result.data.get("script"),
                "images": result.data.get("images"),
                "script_attempts": result.data.get("script_attempts"),
                "image_attempts": result.data.get("image_attempts"),
                "cost": result.cost,
                "duration": result.duration,
                "logs": result.data.get("logs", []),
            })
        else:
            return jsonify({
                "ok": False,
                "error": result.error,
                "logs": result.data.get("logs", []) if result.data else [],
            }), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@shorts_bp.route('/api/shorts/agent-status', methods=['GET'])
def api_shorts_agent_status():
    """Agent 시스템 상태 확인"""
    try:
        import sys
        agents_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "shorts_pipeline", "agents")
        if agents_dir not in sys.path:
            sys.path.insert(0, agents_dir)

        from supervisor import SupervisorAgent
        from script_agent import ScriptAgent
        from image_agent import ImageAgent
        from review_agent import ReviewAgent

        return jsonify({
            "ok": True,
            "agents": ["SupervisorAgent", "ScriptAgent", "ImageAgent", "ReviewAgent"],
            "ready": True,
            "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
        })

    except ImportError as e:
        return jsonify({
            "ok": False,
            "error": f"Agent import failed: {e}",
            "ready": False,
        }), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
