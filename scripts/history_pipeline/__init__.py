"""
한국사 자동화 파이프라인 (주제 기반 구조)

2024-12 개편:
- HISTORY_TOPICS에 정의된 주제별로 자료 수집
- 한국민족문화대백과, e뮤지엄 등에서 실제 자료 추출
- 수집된 내용을 Opus에게 전달하여 대본 작성

시트 구조:
- HISTORY_OPUS_INPUT: 에피소드 관리 (단일 통합 시트)
  - episode: 전체 에피소드 번호
  - era_episode: 시대 내 에피소드 번호
  - opus_prompt_pack: 실제 자료가 포함된 Opus 프롬프트
  - status: 준비/완료

사용법:
    from scripts.history_pipeline import run_history_pipeline

    # 자동으로 '준비' 10개 유지
    result = run_history_pipeline(
        sheet_id="YOUR_SHEET_ID",
        service=sheets_service
    )
"""

from .config import (
    ERAS,
    ERA_ORDER,
    ERA_KEYWORDS,
    HISTORY_TOPICS,
    HISTORY_OPUS_INPUT_SHEET,
    PENDING_TARGET_COUNT,
    get_active_eras,
)

from .run import (
    run_history_pipeline,
    run_single_episode,
    get_pipeline_status,
    run_auto_script_pipeline,  # GPT-5.2 대본 자동 생성
)

from .sheets import (
    SheetsSaveError,
    ensure_history_opus_input_sheet,
    get_series_progress,
    get_next_episode_info,
    count_pending_episodes,
    get_topic_by_global_episode,
    get_total_episode_count,
    get_era_episode_count,
)

from .collector import (
    collect_topic_materials,
)

from .opus import (
    generate_topic_opus_input,
)

__all__ = [
    # 메인 함수
    "run_history_pipeline",
    "run_single_episode",
    "get_pipeline_status",
    "run_auto_script_pipeline",  # GPT-5.2 대본 자동 생성
    # 설정
    "ERAS",
    "ERA_ORDER",
    "ERA_KEYWORDS",
    "HISTORY_TOPICS",
    "HISTORY_OPUS_INPUT_SHEET",
    "PENDING_TARGET_COUNT",
    "get_active_eras",
    # 시트 관리
    "SheetsSaveError",
    "ensure_history_opus_input_sheet",
    "get_series_progress",
    "get_next_episode_info",
    "count_pending_episodes",
    "get_topic_by_global_episode",
    "get_total_episode_count",
    "get_era_episode_count",
    # 자료 수집
    "collect_topic_materials",
    # OPUS 생성
    "generate_topic_opus_input",
]
