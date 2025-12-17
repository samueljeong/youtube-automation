"""
한국사 자동화 파이프라인

시대 흐름형 시리즈를 위한 자동화 파이프라인
- 고조선부터 대한제국까지 시대별 자료 수집
- Google Sheets 기반 (DB 사용 안함)
- append-only 구조

시트 구조 (2024-12 개편):
- {ERA}_RAW: 원문 수집 (시대별 분리)
- {ERA}_CANDIDATES: 점수화된 후보 (시대별 분리)
- HISTORY_OPUS_INPUT: Opus 입력 (★ 단일 통합 시트)

사용법:
    from scripts.history_pipeline import run_history_pipeline

    result = run_history_pipeline(
        sheet_id="YOUR_SHEET_ID",
        service=sheets_service,
        era="GOJOSEON"
    )
"""

from .config import (
    ERAS,
    ERA_ORDER,
    ERA_KEYWORDS,
    HISTORY_OPUS_INPUT_SHEET,
    get_active_eras,
    get_era_sheet_name,
    get_archive_sheet_name,
)

from .run import (
    run_history_pipeline,
    run_all_active_eras,
)

from .sheets import (
    SheetsSaveError,
    ensure_era_sheets,
    ensure_history_opus_input_sheet,
    archive_old_rows,
)

__all__ = [
    # 메인 함수
    "run_history_pipeline",
    "run_all_active_eras",
    # 설정
    "ERAS",
    "ERA_ORDER",
    "ERA_KEYWORDS",
    "HISTORY_OPUS_INPUT_SHEET",
    "get_active_eras",
    "get_era_sheet_name",
    "get_archive_sheet_name",
    # 시트 관리
    "SheetsSaveError",
    "ensure_era_sheets",
    "ensure_history_opus_input_sheet",
    "archive_old_rows",
]
