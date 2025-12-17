"""
한국사 자동화 파이프라인 메인 오케스트레이션

에피소드 기반 시리즈 구조 (2024-12 개편):
- HISTORY_OPUS_INPUT: 에피소드별 대본 자료 (단일 통합 시트)
- 항상 PENDING 10개 유지
- 시대 순서: 고조선 → 부여 → 삼국 → 남북국 → 고려 → 조선전기 → 조선후기 → 대한제국

워크플로우:
1. 현재 PENDING 개수 확인
2. 10개 미만이면 다음 에피소드 추가
3. 새 시대 시작 시 AI가 에피소드 수 결정
4. 시대 완료 시 다음 시대로 자동 진행

사용법:
    from scripts.history_pipeline import run_history_pipeline
    result = run_history_pipeline(sheet_id, service)

API:
    GET /api/history/run-pipeline
    → 자동으로 PENDING 10개 유지
"""

import os
from typing import Dict, Any, Optional, List

from .config import (
    ERAS,
    ERA_ORDER,
    DEFAULT_TOP_K,
    LLM_ENABLED_DEFAULT,
    LLM_MIN_SCORE_DEFAULT,
    HISTORY_OPUS_INPUT_SHEET,
    PENDING_TARGET_COUNT,
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
    get_series_progress,
    get_next_episode_info,
    count_pending_episodes,
    SheetsSaveError,
)
from .collector import collect_materials
from .scoring import score_and_select_candidates
from .opus import (
    generate_opus_input,
    generate_episode_opus_input,
    determine_era_episodes,
)


def run_history_pipeline(
    sheet_id: str,
    service,
    max_results: int = 30,
    top_k: int = DEFAULT_TOP_K,
    llm_enabled: bool = LLM_ENABLED_DEFAULT,
    llm_min_score: float = LLM_MIN_SCORE_DEFAULT,
    force: bool = False
) -> Dict[str, Any]:
    """
    한국사 파이프라인 실행 (자동 에피소드 보충)

    PENDING 10개 미만이면 자동으로 다음 에피소드 추가

    Args:
        sheet_id: Google Sheets ID
        service: Google Sheets API 서비스 객체
        max_results: 수집할 최대 자료 수
        top_k: 선정할 후보 수
        llm_enabled: LLM 사용 여부
        llm_min_score: LLM 호출 최소 점수
        force: 강제 실행 (PENDING 10개여도 추가)

    Returns:
        실행 결과 딕셔너리
    """
    result = {
        "success": False,
        "pending_before": 0,
        "pending_after": 0,
        "episodes_added": 0,
        "current_era": None,
        "current_episode": 0,
        "all_complete": False,
        "details": [],
        "error": None,
    }

    try:
        print(f"[HISTORY] ========================================")
        print(f"[HISTORY] 에피소드 자동 보충 시작")
        print(f"[HISTORY] ========================================")

        # 0) 시트 준비
        if service and sheet_id:
            ensure_history_opus_input_sheet(service, sheet_id)

        # 1) 현재 진행 상황 확인
        progress = get_series_progress(service, sheet_id)
        result["pending_before"] = progress["pending_count"]
        result["current_era"] = progress["current_era"]
        result["current_episode"] = progress["last_episode"]

        print(f"[HISTORY] 현재 상태: PENDING {result['pending_before']}개, 에피소드 {result['current_episode']}개")

        # 2) PENDING 충분하면 종료 (force가 아닌 경우)
        if not force and result["pending_before"] >= PENDING_TARGET_COUNT:
            print(f"[HISTORY] PENDING {PENDING_TARGET_COUNT}개 이상, 추가 불필요")
            result["success"] = True
            result["pending_after"] = result["pending_before"]
            return result

        # 3) 에피소드 추가 루프
        episodes_added = 0
        max_add = PENDING_TARGET_COUNT - result["pending_before"]
        if force:
            max_add = max(1, max_add)  # force면 최소 1개 추가

        # 시대별 총 에피소드 수 캐시
        era_total_episodes_cache = {}

        while episodes_added < max_add:
            # 다음 에피소드 정보 계산
            next_info = get_next_episode_info(service, sheet_id)

            if not next_info["need_more"] and not force:
                print(f"[HISTORY] PENDING 충분, 추가 종료")
                break

            if not next_info["era"]:
                print(f"[HISTORY] 모든 시대 완료!")
                result["all_complete"] = True
                break

            era = next_info["era"]
            era_name = next_info["era_name"]
            era_episode = next_info["era_episode"]
            next_episode = next_info["next_episode"]
            is_new_era = next_info["is_new_era"]

            print(f"[HISTORY] --- 에피소드 {next_episode} 생성 중: {era_name} {era_episode}화 ---")

            # 새 시대 시작 시 에피소드 수 결정
            if is_new_era or era not in era_total_episodes_cache:
                # 시트 생성
                if service and sheet_id:
                    ensure_era_sheets(service, sheet_id, era)

                # 자료 수집 후 에피소드 수 결정
                existing_hashes = set()
                if service and sheet_id:
                    raw_sheet = get_era_sheet_name("RAW", era)
                    existing_hashes = read_recent_hashes(
                        service, sheet_id, raw_sheet,
                        hash_column="I", limit=500
                    )

                raw_rows, items = collect_materials(
                    era=era,
                    max_results=max_results,
                    existing_hashes=existing_hashes
                )

                if not raw_rows:
                    print(f"[HISTORY] {era_name} 자료 수집 실패, 스킵")
                    result["details"].append({
                        "episode": next_episode,
                        "era": era,
                        "error": "자료 수집 실패"
                    })
                    break

                # RAW 저장
                if service and sheet_id:
                    raw_sheet = get_era_sheet_name("RAW", era)
                    try:
                        append_rows(service, sheet_id, f"{raw_sheet}!A1", raw_rows)
                    except SheetsSaveError as e:
                        print(f"[HISTORY] RAW 저장 실패: {e}")

                # 에피소드 수 결정
                total_episodes = determine_era_episodes(era, items)
                era_total_episodes_cache[era] = {
                    "total": total_episodes,
                    "items": items,
                    "candidates": None,
                }

                print(f"[HISTORY] {era_name} 총 {total_episodes}편으로 결정")

            # 캐시에서 정보 가져오기
            era_cache = era_total_episodes_cache.get(era, {})
            total_episodes = era_cache.get("total", 5)
            items = era_cache.get("items", [])

            # 후보 선정 (캐시되지 않았으면)
            if era_cache.get("candidates") is None:
                candidate_rows = score_and_select_candidates(items, era, top_k)
                era_total_episodes_cache[era]["candidates"] = candidate_rows

                # CANDIDATES 저장
                if service and sheet_id and candidate_rows:
                    candidates_sheet = get_era_sheet_name("CANDIDATES", era)
                    try:
                        append_rows(service, sheet_id, f"{candidates_sheet}!A1", candidate_rows)
                    except SheetsSaveError as e:
                        print(f"[HISTORY] CANDIDATES 저장 실패: {e}")

            candidate_rows = era_total_episodes_cache[era].get("candidates", [])

            if not candidate_rows:
                print(f"[HISTORY] {era_name} 후보 없음, 스킵")
                result["details"].append({
                    "episode": next_episode,
                    "era": era,
                    "error": "후보 없음"
                })
                break

            # 에피소드에 맞는 후보 선택 (순환)
            candidate_idx = (era_episode - 1) % len(candidate_rows)
            candidate_row = candidate_rows[candidate_idx]

            # OPUS 입력 생성
            opus_rows = generate_episode_opus_input(
                episode=next_episode,
                era=era,
                era_episode=era_episode,
                total_episodes=total_episodes,
                candidate_row=candidate_row,
                is_new_era=is_new_era
            )

            if opus_rows:
                # 시트에 저장
                if service and sheet_id:
                    try:
                        append_rows(service, sheet_id, f"{HISTORY_OPUS_INPUT_SHEET}!A1", opus_rows)
                        print(f"[HISTORY] 에피소드 {next_episode} 저장 완료")
                    except SheetsSaveError as e:
                        print(f"[HISTORY] OPUS_INPUT 저장 실패: {e}")
                        result["details"].append({
                            "episode": next_episode,
                            "era": era,
                            "error": str(e)
                        })
                        break

                episodes_added += 1
                result["details"].append({
                    "episode": next_episode,
                    "era": era,
                    "era_name": era_name,
                    "era_episode": era_episode,
                    "total_episodes": total_episodes,
                    "success": True
                })

        result["episodes_added"] = episodes_added
        result["pending_after"] = result["pending_before"] + episodes_added
        result["success"] = True

        print(f"[HISTORY] ========================================")
        print(f"[HISTORY] 완료: {episodes_added}개 에피소드 추가")
        print(f"[HISTORY] PENDING: {result['pending_before']} → {result['pending_after']}")
        print(f"[HISTORY] ========================================")

    except Exception as e:
        result["error"] = str(e)
        print(f"[HISTORY] 파이프라인 오류: {e}")
        import traceback
        traceback.print_exc()

    return result


def run_single_era(
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
    특정 시대만 실행 (레거시 호환용)

    에피소드 기반으로 동작하며, 해당 시대의 다음 에피소드 1개만 추가

    Args:
        sheet_id: Google Sheets ID
        service: Google Sheets API 서비스 객체
        era: 시대 키 (GOJOSEON, BUYEO, SAMGUK, ...)
        ...

    Returns:
        실행 결과
    """
    result = {
        "success": False,
        "era": era,
        "era_name": "",
        "error": None,
    }

    if era not in ERAS:
        result["error"] = f"알 수 없는 시대: {era}"
        return result

    era_info = ERAS[era]
    result["era_name"] = era_info.get("name", era)

    if not era_info.get("active", False):
        result["error"] = f"비활성 시대: {era}"
        return result

    # 전체 파이프라인 실행 (1개만 추가)
    pipeline_result = run_history_pipeline(
        sheet_id=sheet_id,
        service=service,
        max_results=max_results,
        top_k=top_k,
        llm_enabled=llm_enabled,
        llm_min_score=llm_min_score,
        force=True  # 최소 1개 추가
    )

    result["success"] = pipeline_result.get("success", False)
    result["episodes_added"] = pipeline_result.get("episodes_added", 0)
    result["details"] = pipeline_result.get("details", [])
    result["error"] = pipeline_result.get("error")

    return result


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
        max_results=int(os.environ.get("MAX_RESULTS", "30")),
        top_k=int(os.environ.get("TOP_K", "5")),
        force=force
    )

    print(f"\n결과: {json.dumps(result, ensure_ascii=False, indent=2)}")
