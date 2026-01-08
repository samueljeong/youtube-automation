"""
Sermon Pipeline Blueprint
설교문 작성 파이프라인 API

Routes:
- /api/sermon/pending: 대기 중인 요청 조회
- /api/sermon/save: 설교문 저장
- /api/sermon/init-sheet: 시트 초기화
- /api/sermon/data: 특정 행 데이터 조회
"""

import os
from flask import Blueprint, request, jsonify

# Blueprint 생성
sermon_bp = Blueprint('sermon', __name__)

# 의존성 주입
_get_sheets_service = None


def set_sheets_service_getter(func):
    """Google Sheets 서비스 getter 함수 주입"""
    global _get_sheets_service
    _get_sheets_service = func


def _get_sheet_id():
    """시트 ID 반환"""
    return (
        os.environ.get('SERMON_SHEET_ID') or
        os.environ.get('AUTOMATION_SHEET_ID')
    )


@sermon_bp.route('/api/sermon/pending', methods=['GET'])
def api_sermon_pending():
    """
    대기 중인 설교 요청 조회

    쿼리 파라미터:
    - sheet: 특정 시트만 조회 (선택)

    Returns:
        대기 중인 요청 리스트
    """
    print("[SERMON] ===== pending 호출됨 =====")

    try:
        from scripts.sermon_pipeline import get_pending_requests, get_all_sheet_names

        if not _get_sheets_service:
            return jsonify({"ok": False, "error": "Sheets 서비스가 설정되지 않았습니다"}), 500

        service = _get_sheets_service()
        if not service:
            return jsonify({
                "ok": False,
                "error": "Google Sheets 서비스 계정이 설정되지 않았습니다"
            }), 400

        sheet_id = _get_sheet_id()
        if not sheet_id:
            return jsonify({
                "ok": False,
                "error": "SERMON_SHEET_ID 또는 AUTOMATION_SHEET_ID 환경변수가 필요합니다"
            }), 400

        # 특정 시트만 조회
        sheet_param = request.args.get('sheet')
        sheet_names = [sheet_param] if sheet_param else None

        pending = get_pending_requests(
            service=service,
            spreadsheet_id=sheet_id,
            sheet_names=sheet_names
        )

        # 전체 시트 목록도 반환
        all_sheets = get_all_sheet_names(service, sheet_id)

        return jsonify({
            "ok": True,
            "count": len(pending),
            "pending": pending,
            "sheets": all_sheets,
        })

    except ImportError as e:
        print(f"[SERMON] ImportError: {e}")
        return jsonify({"ok": False, "error": f"모듈 import 실패: {e}"}), 500
    except Exception as e:
        print(f"[SERMON] Error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@sermon_bp.route('/api/sermon/save', methods=['POST'])
def api_sermon_save():
    """
    설교문 저장

    Request Body:
    {
        "sheet_name": "새벽기도",
        "row_number": 3,
        "sermon": "설교문 내용...",
        "is_revision": false,  // 수정본 여부 (선택)
        "error": null  // 에러 메시지 (선택)
    }
    """
    print("[SERMON] ===== save 호출됨 =====")

    try:
        from scripts.sermon_pipeline import save_sermon

        if not _get_sheets_service:
            return jsonify({"ok": False, "error": "Sheets 서비스가 설정되지 않았습니다"}), 500

        service = _get_sheets_service()
        if not service:
            return jsonify({
                "ok": False,
                "error": "Google Sheets 서비스 계정이 설정되지 않았습니다"
            }), 400

        sheet_id = _get_sheet_id()
        if not sheet_id:
            return jsonify({
                "ok": False,
                "error": "SERMON_SHEET_ID 또는 AUTOMATION_SHEET_ID 환경변수가 필요합니다"
            }), 400

        data = request.get_json() or {}

        sheet_name = data.get('sheet_name')
        row_number = data.get('row_number')
        sermon = data.get('sermon', '')
        is_revision = data.get('is_revision', False)
        error = data.get('error')

        if not sheet_name:
            return jsonify({"ok": False, "error": "sheet_name이 필요합니다"}), 400
        if not row_number:
            return jsonify({"ok": False, "error": "row_number가 필요합니다"}), 400
        if not sermon and not error:
            return jsonify({"ok": False, "error": "sermon 또는 error가 필요합니다"}), 400

        result = save_sermon(
            service=service,
            spreadsheet_id=sheet_id,
            sheet_name=sheet_name,
            row_number=int(row_number),
            sermon=sermon,
            is_revision=is_revision,
            error=error
        )

        if result.get('success'):
            return jsonify({"ok": True, **result})
        else:
            return jsonify({"ok": False, **result}), 500

    except ImportError as e:
        print(f"[SERMON] ImportError: {e}")
        return jsonify({"ok": False, "error": f"모듈 import 실패: {e}"}), 500
    except Exception as e:
        print(f"[SERMON] Error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@sermon_bp.route('/api/sermon/init-sheet', methods=['POST'])
def api_sermon_init_sheet():
    """
    새 시트 초기화

    Request Body:
    {
        "sheet_name": "금요철야"
    }
    """
    print("[SERMON] ===== init-sheet 호출됨 =====")

    try:
        from scripts.sermon_pipeline import init_sheet

        if not _get_sheets_service:
            return jsonify({"ok": False, "error": "Sheets 서비스가 설정되지 않았습니다"}), 500

        service = _get_sheets_service()
        if not service:
            return jsonify({
                "ok": False,
                "error": "Google Sheets 서비스 계정이 설정되지 않았습니다"
            }), 400

        sheet_id = _get_sheet_id()
        if not sheet_id:
            return jsonify({
                "ok": False,
                "error": "SERMON_SHEET_ID 또는 AUTOMATION_SHEET_ID 환경변수가 필요합니다"
            }), 400

        data = request.get_json() or {}
        sheet_name = data.get('sheet_name')

        if not sheet_name:
            return jsonify({"ok": False, "error": "sheet_name이 필요합니다"}), 400

        result = init_sheet(
            service=service,
            spreadsheet_id=sheet_id,
            sheet_name=sheet_name
        )

        if result.get('success'):
            return jsonify({"ok": True, **result})
        else:
            return jsonify({"ok": False, **result}), 500

    except ImportError as e:
        print(f"[SERMON] ImportError: {e}")
        return jsonify({"ok": False, "error": f"모듈 import 실패: {e}"}), 500
    except Exception as e:
        print(f"[SERMON] Error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@sermon_bp.route('/api/sermon/data', methods=['GET'])
def api_sermon_data():
    """
    특정 행 데이터 조회

    쿼리 파라미터:
    - sheet: 시트 이름 (필수)
    - row: 행 번호 (필수)
    """
    print("[SERMON] ===== data 호출됨 =====")

    try:
        from scripts.sermon_pipeline.sheets import get_sheet_data

        if not _get_sheets_service:
            return jsonify({"ok": False, "error": "Sheets 서비스가 설정되지 않았습니다"}), 500

        service = _get_sheets_service()
        if not service:
            return jsonify({
                "ok": False,
                "error": "Google Sheets 서비스 계정이 설정되지 않았습니다"
            }), 400

        sheet_id = _get_sheet_id()
        if not sheet_id:
            return jsonify({
                "ok": False,
                "error": "SERMON_SHEET_ID 또는 AUTOMATION_SHEET_ID 환경변수가 필요합니다"
            }), 400

        sheet_name = request.args.get('sheet')
        row_number = request.args.get('row')

        if not sheet_name:
            return jsonify({"ok": False, "error": "sheet 파라미터가 필요합니다"}), 400
        if not row_number:
            return jsonify({"ok": False, "error": "row 파라미터가 필요합니다"}), 400

        data = get_sheet_data(
            service=service,
            spreadsheet_id=sheet_id,
            sheet_name=sheet_name,
            row_number=int(row_number)
        )

        if data:
            return jsonify({"ok": True, "data": data})
        else:
            return jsonify({"ok": False, "error": "데이터를 찾을 수 없습니다"}), 404

    except ImportError as e:
        print(f"[SERMON] ImportError: {e}")
        return jsonify({"ok": False, "error": f"모듈 import 실패: {e}"}), 500
    except Exception as e:
        print(f"[SERMON] Error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@sermon_bp.route('/api/sermon/sheets', methods=['GET'])
def api_sermon_sheets():
    """
    전체 시트 목록 조회
    """
    print("[SERMON] ===== sheets 호출됨 =====")

    try:
        from scripts.sermon_pipeline import get_all_sheet_names

        if not _get_sheets_service:
            return jsonify({"ok": False, "error": "Sheets 서비스가 설정되지 않았습니다"}), 500

        service = _get_sheets_service()
        if not service:
            return jsonify({
                "ok": False,
                "error": "Google Sheets 서비스 계정이 설정되지 않았습니다"
            }), 400

        sheet_id = _get_sheet_id()
        if not sheet_id:
            return jsonify({
                "ok": False,
                "error": "SERMON_SHEET_ID 또는 AUTOMATION_SHEET_ID 환경변수가 필요합니다"
            }), 400

        sheets = get_all_sheet_names(service, sheet_id)

        return jsonify({
            "ok": True,
            "sheets": sheets,
            "count": len(sheets)
        })

    except ImportError as e:
        print(f"[SERMON] ImportError: {e}")
        return jsonify({"ok": False, "error": f"모듈 import 실패: {e}"}), 500
    except Exception as e:
        print(f"[SERMON] Error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
