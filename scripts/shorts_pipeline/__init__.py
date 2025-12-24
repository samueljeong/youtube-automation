"""
Shorts Pipeline Module
연예 뉴스 기반 60초 YouTube Shorts 자동 생성

사용법:
    from scripts.shorts_pipeline import run_shorts_pipeline
    result = run_shorts_pipeline(celebrity="박나래")

또는 CLI:
    python -m scripts.shorts_pipeline.run --celebrity 박나래
    python -m scripts.shorts_pipeline.run --collect
    python -m scripts.shorts_pipeline.run --generate --limit 3
"""

from .config import (
    SHEET_NAME,
    COLLECT_HEADERS,
    VIDEO_AUTOMATION_HEADERS,
    ALL_HEADERS,
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    VIDEO_SIZE,
    MAX_DURATION_SECONDS,
    DEFAULT_SCENE_COUNT,
    TARGET_SCRIPT_LENGTH,
    CONTENT_CATEGORIES,
    ISSUE_TYPES,
    CELEBRITY_SILHOUETTES,
    ATHLETE_SILHOUETTES,
    ALL_SILHOUETTES,
    BACKGROUND_STYLES,
    RSS_FEEDS,
    ENTERTAINMENT_RSS_FEEDS,
    DAILY_NEWS_LIMIT,
    NEWS_SELECTION_MODE,
    COMMENT_TRIGGERS,
    FACT_CHECK_RULES,
    estimate_cost,
)

from .sheets import (
    get_sheets_service,
    get_spreadsheet_id,
    create_shorts_sheet,
    read_pending_rows,
    update_status,
    update_cell,
    append_row,
    check_duplicate,
    SheetsSaveError,
)

from .news_collector import (
    collect_entertainment_news,
    search_celebrity_news,
    extract_celebrity_name,
    detect_issue_type,
    get_silhouette_description,
    generate_hook_text,
)

from .script_generator import (
    DEFAULT_MODEL,
    GPT51_COSTS,
    generate_shorts_script,
    generate_complete_shorts_package,
    enhance_image_prompts,
    format_script_for_sheet,
    extract_gpt51_response,
)

from .run import (
    run_news_collection,
    run_script_generation,
    run_shorts_pipeline,
)


__all__ = [
    # Config
    'SHEET_NAME',
    'COLLECT_HEADERS',
    'VIDEO_AUTOMATION_HEADERS',
    'ALL_HEADERS',
    'VIDEO_WIDTH',
    'VIDEO_HEIGHT',
    'VIDEO_SIZE',
    'MAX_DURATION_SECONDS',
    'DEFAULT_SCENE_COUNT',
    'TARGET_SCRIPT_LENGTH',
    'CONTENT_CATEGORIES',
    'ISSUE_TYPES',
    'CELEBRITY_SILHOUETTES',
    'ATHLETE_SILHOUETTES',
    'ALL_SILHOUETTES',
    'BACKGROUND_STYLES',
    'RSS_FEEDS',
    'ENTERTAINMENT_RSS_FEEDS',
    'DAILY_NEWS_LIMIT',
    'NEWS_SELECTION_MODE',
    'COMMENT_TRIGGERS',
    'FACT_CHECK_RULES',
    'estimate_cost',

    # Sheets
    'get_sheets_service',
    'get_spreadsheet_id',
    'create_shorts_sheet',
    'read_pending_rows',
    'update_status',
    'update_cell',
    'append_row',
    'check_duplicate',
    'SheetsSaveError',

    # News Collector
    'collect_entertainment_news',
    'search_celebrity_news',
    'extract_celebrity_name',
    'detect_issue_type',
    'get_silhouette_description',
    'generate_hook_text',

    # Script Generator
    'DEFAULT_MODEL',
    'GPT51_COSTS',
    'generate_shorts_script',
    'generate_complete_shorts_package',
    'enhance_image_prompts',
    'format_script_for_sheet',
    'extract_gpt51_response',

    # Main
    'run_news_collection',
    'run_script_generation',
    'run_shorts_pipeline',
]
