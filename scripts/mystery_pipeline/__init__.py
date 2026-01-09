"""
미스테리 자동화 파이프라인

- 해외 미스테리: 영어 위키백과
- 한국 미스테리: 나무위키 (2025-12-22 추가)

사용법:
    # 해외 미스테리
    from scripts.mystery_pipeline import run_mystery_pipeline
    result = run_mystery_pipeline(sheet_id, service)

    # 한국 미스테리 ★
    from scripts.mystery_pipeline import run_kr_mystery_pipeline
    result = run_kr_mystery_pipeline(sheet_id, service)
"""

from .run import (
    run_mystery_pipeline,
    run_kr_mystery_pipeline,
    test_collect_kr_mystery,
)
from .collector import (
    collect_mystery_article,
    search_wikipedia_en,
    # 한국 미스테리
    collect_kr_mystery_article,
    get_next_kr_mystery,
    list_available_kr_mysteries,
)
from .config import (
    MYSTERY_CATEGORIES,
    MYSTERY_SHEET_NAME,
    MYSTERY_TTS_VOICE,
    MYSTERY_VIDEO_LENGTH_MINUTES,
    # 한국 미스테리
    KR_MYSTERY_CATEGORIES,
    FEATURED_KR_MYSTERIES,
)

__all__ = [
    # 해외 미스테리
    "run_mystery_pipeline",
    "collect_mystery_article",
    "search_wikipedia_en",
    "MYSTERY_CATEGORIES",
    "MYSTERY_SHEET_NAME",
    "MYSTERY_TTS_VOICE",
    "MYSTERY_VIDEO_LENGTH_MINUTES",
    # 한국 미스테리
    "run_kr_mystery_pipeline",
    "test_collect_kr_mystery",
    "collect_kr_mystery_article",
    "get_next_kr_mystery",
    "list_available_kr_mysteries",
    "KR_MYSTERY_CATEGORIES",
    "FEATURED_KR_MYSTERIES",
]
