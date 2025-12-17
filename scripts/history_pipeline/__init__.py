"""
한국사 자동화 파이프라인

에피소드 기반 시리즈 구조 (2024-12 개편):
- 고조선부터 대한제국까지 시대별 순차 진행
- PENDING 10개 자동 유지
- AI가 시대별 에피소드 수 결정 (자료량에 따라 3~10편)

시트 구조:
- HISTORY_OPUS_INPUT: 에피소드 관리 (단일 통합 시트)
  - episode: 전체 에피소드 번호
  - era_episode: 시대 내 에피소드 번호
  - status: PENDING/DONE

사용법:
    from scripts.history_pipeline import run_history_pipeline

    # 자동으로 PENDING 10개 유지
    result = run_history_pipeline(
        sheet_id="YOUR_SHEET_ID",
        service=sheets_service
    )
"""

from .config import (
    ERAS,
    ERA_ORDER,
    ERA_KEYWORDS,
    HISTORY_OPUS_INPUT_SHEET,
    PENDING_TARGET_COUNT,
    get_active_eras,
    get_era_sheet_name,
    get_archive_sheet_name,
)

from .run import (
    run_history_pipeline,
    run_single_era,
)

from .sheets import (
    SheetsSaveError,
    ensure_era_sheets,
    ensure_history_opus_input_sheet,
    archive_old_rows,
    get_series_progress,
    get_next_episode_info,
    count_pending_episodes,
)

__all__ = [
    # 메인 함수
    "run_history_pipeline",
    "run_single_era",
    # 설정
    "ERAS",
    "ERA_ORDER",
    "ERA_KEYWORDS",
    "HISTORY_OPUS_INPUT_SHEET",
    "PENDING_TARGET_COUNT",
    "get_active_eras",
    "get_era_sheet_name",
    "get_archive_sheet_name",
    # 시트 관리
    "SheetsSaveError",
    "ensure_era_sheets",
    "ensure_history_opus_input_sheet",
    "archive_old_rows",
    "get_series_progress",
    "get_next_episode_info",
    "count_pending_episodes",
]
