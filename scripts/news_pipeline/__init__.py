# News Pipeline Module
# Google News RSS 수집 → 후보 선정 → OPUS 입력 생성

from .run import (
    run_news_pipeline,
    ingest_rss_feeds,
    score_and_select_candidates,
    generate_opus_input,
    NEWS_FEEDS,
    CATEGORY_KEYWORDS,
)

__all__ = [
    'run_news_pipeline',
    'ingest_rss_feeds',
    'score_and_select_candidates',
    'generate_opus_input',
    'NEWS_FEEDS',
    'CATEGORY_KEYWORDS',
]
