# News Pipeline Module
# Google News RSS 수집 → 후보 선정 → OPUS 입력 생성

from .config import (
    CHANNELS,
    CHANNEL_FILTERS,
    WEEKDAY_ANGLES,
    NEWS_FEEDS,
    CATEGORY_KEYWORDS,
    google_news_rss_url,
)

from .utils import (
    normalize_text,
    compute_hash,
    get_tab_name,
    get_kst_now,
    get_weekday_angle,
    guess_category,
    calculate_relevance_score,
    calculate_recency_score,
    passes_channel_filter,
)

from .rss import (
    ingest_rss_feeds,
    deduplicate_items,
)

from .scoring import (
    score_and_select_candidates,
)

from .opus import (
    generate_opus_input,
)

from .sheets import (
    append_rows,
    SheetsSaveError,
    cleanup_old_rows,
)

from .run import (
    run_news_pipeline,
)

__all__ = [
    # Config
    'CHANNELS',
    'CHANNEL_FILTERS',
    'WEEKDAY_ANGLES',
    'NEWS_FEEDS',
    'CATEGORY_KEYWORDS',
    'google_news_rss_url',
    # Utils
    'normalize_text',
    'compute_hash',
    'get_tab_name',
    'get_kst_now',
    'get_weekday_angle',
    'guess_category',
    'calculate_relevance_score',
    'calculate_recency_score',
    'passes_channel_filter',
    # RSS
    'ingest_rss_feeds',
    'deduplicate_items',
    # Scoring
    'score_and_select_candidates',
    # OPUS
    'generate_opus_input',
    # Sheets
    'append_rows',
    'SheetsSaveError',
    'cleanup_old_rows',
    # Main
    'run_news_pipeline',
]
