"""
한국사 자동화 파이프라인

시대 흐름형 시리즈를 위한 자동화 파이프라인
- 고조선부터 대한제국까지 시대별 자료 수집
- Google Sheets 기반 (DB 사용 안함)
- append-only 구조

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
    "get_active_eras",
    "get_era_sheet_name",
    "get_archive_sheet_name",
    # 시트 관리
    "SheetsSaveError",
    "ensure_era_sheets",
    "archive_old_rows",
]
