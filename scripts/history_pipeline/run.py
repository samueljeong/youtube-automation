"""
한국사 자동화 파이프라인 메인 오케스트레이션 (주제 기반)

2024-12 개편:
- HISTORY_TOPICS에 정의된 주제별로 자료 수집
- 실제 API 자료를 Opus에게 전달
- HISTORY_OPUS_INPUT 단일 시트 사용

워크플로우:
1. 현재 PENDING 개수 확인
2. 10개 미만이면 다음 에피소드 추가
3. 주제별 자료 수집 (한국민족문화대백과, e뮤지엄 등)
4. 수집된 내용을 포함한 Opus 프롬프트 생성

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
    HISTORY_TOPICS,
    HISTORY_OPUS_INPUT_SHEET,
    PENDING_TARGET_COUNT,
)
from .sheets import (
    ensure_history_opus_input_sheet,
    append_rows,
    append_to_unified_sheet,
    get_series_progress,
    get_next_episode_info,
    count_pending_episodes,
    SheetsSaveError,
    UNIFIED_HISTORY_SHEET,
)
from .collector import collect_topic_materials
from .opus import generate_topic_opus_input, HISTORY_OPUS_FIELDS


def run_history_pipeline(
    sheet_id: str,
    service,
    force: bool = False
) -> Dict[str, Any]:
    """
    한국사 파이프라인 실행 (주제 기반, 자동 에피소드 보충)

    PENDING 10개 미만이면 자동으로 다음 에피소드 추가

    Args:
        sheet_id: Google Sheets ID
        service: Google Sheets API 서비스 객체
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
        print(f"[HISTORY] 주제 기반 에피소드 자동 보충 시작")
        print(f"[HISTORY] ========================================")

        # 0) 시트 준비
        if service and sheet_id:
            ensure_history_opus_input_sheet(service, sheet_id)

        # 1) 현재 진행 상황 확인
        progress = get_series_progress(service, sheet_id)
        result["pending_before"] = progress["pending_count"]
        result["current_era"] = progress["current_era"]
        result["current_episode"] = progress["last_episode"]

        print(f"[HISTORY] 현재 상태: PENDING {result['pending_before']}개, 에피소드 {result['current_episode']}/{progress['planned_total']}개")

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

        while episodes_added < max_add:
            # 다음 에피소드 정보 계산
            next_info = get_next_episode_info(service, sheet_id)

            if next_info["all_complete"]:
                print(f"[HISTORY] 모든 에피소드 완료!")
                result["all_complete"] = True
                break

            if not next_info["need_more"] and not force:
                print(f"[HISTORY] PENDING 충분, 추가 종료")
                break

            era = next_info["era"]
            era_name = next_info["era_name"]
            era_episode = next_info["era_episode"]
            next_episode = next_info["next_episode"]
            topic_info = next_info["topic"]
            is_new_era = next_info["is_new_era"]
            total_episodes = next_info["total_episodes"]

            print(f"[HISTORY] ---")
            print(f"[HISTORY] 에피소드 {next_episode} 생성 중:")
            print(f"[HISTORY]   시대: {era_name} ({era_episode}/{total_episodes}화)")
            print(f"[HISTORY]   주제: {topic_info.get('title', 'N/A')}")
            print(f"[HISTORY] ---")

            # 주제별 자료 수집
            collected = collect_topic_materials(era, era_episode)

            if "error" in collected:
                print(f"[HISTORY] 자료 수집 실패: {collected['error']}")
                result["details"].append({
                    "episode": next_episode,
                    "era": era,
                    "error": collected["error"]
                })
                # 자료가 없어도 에피소드는 생성 (키워드 기반)
                collected = {
                    "full_content": "",
                    "sources": [],
                    "materials": [],
                }

            # OPUS 입력 생성
            opus_rows = generate_topic_opus_input(
                episode=next_episode,
                era=era,
                era_episode=era_episode,
                topic_info=topic_info,
                collected_materials=collected,
            )

            if opus_rows:
                # 통합 시트(HISTORY)에 저장
                if service and sheet_id:
                    try:
                        # opus_rows는 [[...]] 형태이므로 첫 번째 행 추출
                        opus_row = opus_rows[0]
                        append_to_unified_sheet(
                            service,
                            sheet_id,
                            opus_row,
                            HISTORY_OPUS_FIELDS
                        )
                        print(f"[HISTORY] 에피소드 {next_episode} → '{UNIFIED_HISTORY_SHEET}' 시트 저장 완료")
                    except SheetsSaveError as e:
                        print(f"[HISTORY] 통합 시트 저장 실패: {e}")
                        result["details"].append({
                            "episode": next_episode,
                            "era": era,
                            "error": str(e)
                        })
                        result["error"] = str(e)
                        break

                episodes_added += 1
                result["details"].append({
                    "episode": next_episode,
                    "era": era,
                    "era_name": era_name,
                    "era_episode": era_episode,
                    "total_episodes": total_episodes,
                    "title": topic_info.get("title", ""),
                    "materials_count": len(collected.get("materials", [])),
                    "content_length": len(collected.get("full_content", "")),
                    "success": True
                })

        result["episodes_added"] = episodes_added
        result["pending_after"] = result["pending_before"] + episodes_added
        result["success"] = result.get("error") is None

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


def run_single_episode(
    sheet_id: str,
    service,
    episode: int = None,
    era: str = None,
    era_episode: int = None,
) -> Dict[str, Any]:
    """
    단일 에피소드 생성

    Args:
        sheet_id: Google Sheets ID
        service: Google Sheets API 서비스 객체
        episode: 전역 에피소드 번호 (지정 시 특정 에피소드 재생성)
        era: 시대 키 (episode 없을 때 사용)
        era_episode: 시대 내 에피소드 번호 (era와 함께 사용)

    Returns:
        실행 결과
    """
    result = {
        "success": False,
        "episode": episode,
        "era": era,
        "era_name": "",
        "error": None,
    }

    try:
        # 에피소드 정보 결정
        if episode:
            # 전역 에피소드 번호로 주제 찾기
            from .sheets import get_topic_by_global_episode
            topic_data = get_topic_by_global_episode(episode)
            if not topic_data:
                result["error"] = f"에피소드 {episode} 없음"
                return result
            era = topic_data["era"]
            era_episode = topic_data["era_episode"]
            topic_info = topic_data["topic"]
            total_episodes = topic_data["total_episodes"]
        elif era and era_episode:
            # 시대 + 시대 내 번호로 찾기
            topics = HISTORY_TOPICS.get(era, [])
            if era_episode > len(topics):
                result["error"] = f"{era} 에피소드 {era_episode} 없음"
                return result
            topic_info = topics[era_episode - 1]
            total_episodes = len(topics)

            # 전역 에피소드 번호 계산
            episode = 0
            for e in ERA_ORDER:
                if e == era:
                    episode += era_episode
                    break
                episode += len(HISTORY_TOPICS.get(e, []))
        else:
            result["error"] = "episode 또는 (era, era_episode) 필요"
            return result

        era_info = ERAS.get(era, {})
        result["era"] = era
        result["era_name"] = era_info.get("name", era)
        result["episode"] = episode

        print(f"[HISTORY] 단일 에피소드 생성: {result['era_name']} {era_episode}화")

        # 자료 수집
        collected = collect_topic_materials(era, era_episode)

        # OPUS 입력 생성
        opus_rows = generate_topic_opus_input(
            episode=episode,
            era=era,
            era_episode=era_episode,
            topic_info=topic_info,
            collected_materials=collected,
        )

        if opus_rows and service and sheet_id:
            # 통합 시트(HISTORY)에 저장
            opus_row = opus_rows[0]
            append_to_unified_sheet(
                service,
                sheet_id,
                opus_row,
                HISTORY_OPUS_FIELDS
            )
            print(f"[HISTORY] → '{UNIFIED_HISTORY_SHEET}' 시트 저장 완료")

        result["success"] = True
        result["title"] = topic_info.get("title", "")
        result["materials_count"] = len(collected.get("materials", []))
        result["content_length"] = len(collected.get("full_content", ""))

    except Exception as e:
        result["error"] = str(e)
        print(f"[HISTORY] 단일 에피소드 생성 오류: {e}")
        import traceback
        traceback.print_exc()

    return result


def get_pipeline_status(
    sheet_id: str,
    service,
) -> Dict[str, Any]:
    """
    파이프라인 상태 조회

    Returns:
        {
            "total_planned": 계획된 총 에피소드 수,
            "total_created": 생성된 에피소드 수,
            "pending_count": PENDING 상태 수,
            "current_era": 현재 시대,
            "current_episode": 현재 에피소드 번호,
            "progress_percent": 진행률 (%),
            "eras": {시대별 정보}
        }
    """
    status = {
        "total_planned": 0,
        "total_created": 0,
        "pending_count": 0,
        "current_era": None,
        "current_episode": 0,
        "progress_percent": 0,
        "eras": {},
    }

    # 계획된 총 에피소드 수
    for era in ERA_ORDER:
        topics = HISTORY_TOPICS.get(era, [])
        era_info = ERAS.get(era, {})
        status["eras"][era] = {
            "name": era_info.get("name", era),
            "planned": len(topics),
            "topics": [t.get("title", "") for t in topics],
        }
        status["total_planned"] += len(topics)

    # 현재 진행 상황
    if service and sheet_id:
        progress = get_series_progress(service, sheet_id)
        status["total_created"] = progress["total_episodes"]
        status["pending_count"] = progress["pending_count"]
        status["current_era"] = progress["current_era"]
        status["current_episode"] = progress["last_episode"]

        if status["total_planned"] > 0:
            status["progress_percent"] = round(
                status["total_created"] / status["total_planned"] * 100, 1
            )

    return status


# ============================================================
# CLI 실행 (테스트용)
# ============================================================

if __name__ == "__main__":
    import json
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

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
        force=force
    )

    print(f"\n결과: {json.dumps(result, ensure_ascii=False, indent=2)}")
