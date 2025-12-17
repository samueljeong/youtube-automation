"""
한국사 자동화 파이프라인 메인 오케스트레이션

구조 (2024-12 개편):
- {ERA}_RAW: 원문 수집 데이터 (시대별 분리)
- {ERA}_CANDIDATES: 점수화된 후보 (시대별 분리)
- HISTORY_OPUS_INPUT: 대본 작성용 입력 (★ 단일 통합 시트, 모든 시대 누적)

Idempotency:
- 같은 날짜 + 같은 시대: 스킵 (중복)
- 같은 날짜 + 다른 시대: 허용

사용법:
    from scripts.history_pipeline import run_history_pipeline
    result = run_history_pipeline(sheet_id, service, era="GOJOSEON")

Render Cron:
    POST /api/history/run-pipeline?era=GOJOSEON
"""

import os
from typing import Dict, Any, Optional

from .config import (
    ERAS,
    ERA_ORDER,
    DEFAULT_TOP_K,
    LLM_ENABLED_DEFAULT,
    LLM_MIN_SCORE_DEFAULT,
    HISTORY_OPUS_INPUT_SHEET,
    get_era_sheet_name,
    get_active_eras,
)
from .utils import get_run_id
from .sheets import (
    ensure_era_sheets,
    ensure_history_opus_input_sheet,
    check_archive_needed,
    archive_old_rows,
    append_rows,
    read_recent_hashes,
    check_opus_input_exists,
    SheetsSaveError,
)
from .collector import collect_materials
from .scoring import score_and_select_candidates
from .opus import generate_opus_input


def run_history_pipeline(
    sheet_id: str,
    service,
    era: str = "GOJOSEON",
    max_results: int = 30,
    top_k: int = DEFAULT_TOP_K,
    llm_enabled: bool = LLM_ENABLED_DEFAULT,
    llm_min_score: float = LLM_MIN_SCORE_DEFAULT,
    force: bool = False
) -> Dict[str, Any]:
    """
    한국사 파이프라인 전체 실행 (시대별)

    Args:
        sheet_id: Google Sheets ID
        service: Google Sheets API 서비스 객체
        era: 시대 키 (GOJOSEON, BUYEO, SAMGUK, ...)
        max_results: 수집할 최대 자료 수
        top_k: 선정할 후보 수
        llm_enabled: LLM 사용 여부
        llm_min_score: LLM 호출 최소 점수
        force: 강제 실행 (Idempotency 무시)

    Returns:
        실행 결과 딕셔너리
    """
    result = {
        "success": False,
        "era": era,
        "era_name": "",
        "raw_count": 0,
        "candidate_count": 0,
        "opus_generated": False,
        "archived": 0,
        "sheets_created": [],
        "sheets_saved": [],
        "error": None,
    }

    # 시대 유효성 검사
    if era not in ERAS:
        result["error"] = f"알 수 없는 시대: {era}. 유효 시대: {list(ERAS.keys())}"
        return result

    era_info = ERAS[era]
    result["era_name"] = era_info.get("name", era)

    if not era_info.get("active", False):
        result["error"] = f"비활성 시대: {era} ({result['era_name']})"
        return result

    run_id = get_run_id()

    try:
        print(f"[HISTORY] ========================================")
        print(f"[HISTORY] 파이프라인 시작: {result['era_name']} ({era})")
        print(f"[HISTORY] 실행 ID: {run_id}")
        print(f"[HISTORY] ========================================")

        # 0) Idempotency 체크
        if not force and service and sheet_id:
            if check_opus_input_exists(service, sheet_id, era, run_id):
                result["error"] = f"이미 오늘({run_id}) 실행됨. force=True로 강제 실행 가능"
                print(f"[HISTORY] {result['error']}")
                return result

        # 1) 시트 자동 생성
        if service and sheet_id:
            print(f"[HISTORY] === 0단계: 시트 생성 확인 ===")
            # 시대별 시트 (RAW, CANDIDATES)
            created = ensure_era_sheets(service, sheet_id, era)
            result["sheets_created"] = [k for k, v in created.items() if v]
            # 단일 통합 OPUS_INPUT 시트
            if ensure_history_opus_input_sheet(service, sheet_id):
                result["sheets_created"].append("HISTORY_OPUS_INPUT")

        # 2) 아카이브 필요 여부 확인
        if service and sheet_id:
            if check_archive_needed(service, sheet_id, era):
                print(f"[HISTORY] === 0.5단계: 아카이브 실행 ===")
                archive_result = archive_old_rows(service, sheet_id, era)
                result["archived"] = archive_result.get("archived", 0)

        # 3) 기존 해시 로드 (중복 방지)
        existing_hashes = set()
        if service and sheet_id:
            raw_sheet = get_era_sheet_name("RAW", era)
            existing_hashes = read_recent_hashes(
                service, sheet_id, raw_sheet,
                hash_column="I",  # hash 열
                limit=500
            )

        # 4) 자료 수집
        print(f"[HISTORY] === 1단계: 자료 수집 ===")
        raw_rows, items = collect_materials(
            era=era,
            max_results=max_results,
            existing_hashes=existing_hashes
        )
        result["raw_count"] = len(raw_rows)

        if not raw_rows:
            result["error"] = "수집된 자료 없음"
            print(f"[HISTORY] {result['error']}")
            return result

        # RAW 시트에 저장
        if service and sheet_id:
            raw_sheet = get_era_sheet_name("RAW", era)
            try:
                append_rows(service, sheet_id, f"{raw_sheet}!A1", raw_rows)
                result["sheets_saved"].append(raw_sheet)
                print(f"[HISTORY] {raw_sheet}에 {len(raw_rows)}개 행 저장 완료")
            except SheetsSaveError as e:
                result["error"] = f"RAW 저장 실패: {e}"
                print(f"[HISTORY] {result['error']}")
                return result

        # 5) 점수화 및 후보 선정
        print(f"[HISTORY] === 2단계: 후보 선정 ===")
        candidate_rows = score_and_select_candidates(items, era, top_k)
        result["candidate_count"] = len(candidate_rows)

        if not candidate_rows:
            result["error"] = f"시대 {era}에 적합한 후보 없음"
            print(f"[HISTORY] {result['error']}")
            return result

        # CANDIDATES 시트에 저장
        if service and sheet_id:
            candidates_sheet = get_era_sheet_name("CANDIDATES", era)
            try:
                append_rows(service, sheet_id, f"{candidates_sheet}!A1", candidate_rows)
                result["sheets_saved"].append(candidates_sheet)
                print(f"[HISTORY] {candidates_sheet}에 {len(candidate_rows)}개 행 저장 완료")
            except SheetsSaveError as e:
                result["error"] = f"CANDIDATES 저장 실패: {e}"
                print(f"[HISTORY] {result['error']}")
                return result

        # 6) OPUS 입력 생성 (단일 통합 시트에 저장)
        print(f"[HISTORY] === 3단계: OPUS 입력 생성 ===")
        opus_rows = generate_opus_input(
            candidate_rows, era, llm_enabled, llm_min_score
        )

        if opus_rows:
            result["opus_generated"] = True

            if service and sheet_id:
                # 단일 통합 시트 HISTORY_OPUS_INPUT에 저장
                try:
                    append_rows(service, sheet_id, f"{HISTORY_OPUS_INPUT_SHEET}!A1", opus_rows)
                    result["sheets_saved"].append(HISTORY_OPUS_INPUT_SHEET)
                    print(f"[HISTORY] {HISTORY_OPUS_INPUT_SHEET}에 저장 완료 (era={era})")
                except SheetsSaveError as e:
                    result["error"] = f"OPUS_INPUT 저장 실패: {e}"
                    print(f"[HISTORY] {result['error']}")
                    return result

        result["success"] = True
        print(f"[HISTORY] ========================================")
        print(f"[HISTORY] 파이프라인 완료: {result['era_name']}")
        print(f"[HISTORY] 수집: {result['raw_count']}, 후보: {result['candidate_count']}")
        print(f"[HISTORY] ========================================")

    except Exception as e:
        result["error"] = str(e)
        print(f"[HISTORY] 파이프라인 오류: {e}")
        import traceback
        traceback.print_exc()

    return result


def run_all_active_eras(
    sheet_id: str,
    service,
    **kwargs
) -> Dict[str, Any]:
    """
    활성화된 모든 시대에 대해 파이프라인 실행

    Args:
        sheet_id: Google Sheets ID
        service: Google Sheets API 서비스 객체
        **kwargs: run_history_pipeline에 전달할 추가 인자

    Returns:
        시대별 실행 결과
    """
    active_eras = get_active_eras()

    if not active_eras:
        return {"error": "활성화된 시대 없음", "results": {}}

    results = {}

    for era in active_eras:
        print(f"\n[HISTORY] >>> 시대 처리 중: {era}")
        result = run_history_pipeline(sheet_id, service, era=era, **kwargs)
        results[era] = result

        if not result.get("success"):
            print(f"[HISTORY] >>> {era} 실패: {result.get('error')}")

    return {
        "total_eras": len(active_eras),
        "successful": sum(1 for r in results.values() if r.get("success")),
        "results": results,
    }


# ============================================================
# CLI 실행 (테스트용)
# ============================================================

if __name__ == "__main__":
    import json
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    # 뉴스 파이프라인과 같은 시트 사용 가능
    sheet_id = (
        os.environ.get("HISTORY_SHEET_ID") or
        os.environ.get("NEWS_SHEET_ID") or
        os.environ.get("AUTOMATION_SHEET_ID") or
        os.environ.get("SHEET_ID")
    )
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    llm_enabled = os.environ.get("LLM_ENABLED", "0") == "1"
    era = os.environ.get("HISTORY_ERA", "GOJOSEON")
    force = os.environ.get("FORCE", "0") == "1"

    if not sheet_id:
        print("ERROR: HISTORY_SHEET_ID, NEWS_SHEET_ID, 또는 AUTOMATION_SHEET_ID 환경변수 필요")
        exit(1)

    service = None
    if service_account_json:
        creds_info = json.loads(service_account_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
    else:
        print("WARNING: GOOGLE_SERVICE_ACCOUNT_JSON 없음, 시트 저장 스킵")

    result = run_history_pipeline(
        sheet_id=sheet_id,
        service=service,
        era=era,
        max_results=int(os.environ.get("MAX_RESULTS", "30")),
        top_k=int(os.environ.get("TOP_K", "5")),
        llm_enabled=llm_enabled,
        force=force
    )

    print(f"\n결과: {json.dumps(result, ensure_ascii=False, indent=2)}")
