"""
Shorts Pipeline Module
연예 뉴스 기반 60초 YouTube Shorts 자동 생성

사용법:
    from scripts.shorts_pipeline import run_shorts_pipeline, run_full_pipeline

    # 뉴스 수집 + 대본 생성만
    result = run_shorts_pipeline(person="박나래")

    # 전체 파이프라인 (뉴스 수집 + 대본 생성 + 비디오 생성)
    result = run_full_pipeline(person="박나래")

또는 CLI:
    python -m scripts.shorts_pipeline.run --person 박나래
    python -m scripts.shorts_pipeline.run --collect
    python -m scripts.shorts_pipeline.run --generate --limit 3
    python -m scripts.shorts_pipeline.run --full  # 전체 파이프라인
    python -m scripts.shorts_pipeline.run --generate --video  # 대본 + 비디오
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
    # BGM
    SHORTS_BGM_MOODS,
    SHORTS_BGM_CONFIG,
    BGM_MOOD_OPTIONS,
    # 자막
    SHORTS_SUBTITLE_STYLE,
    SHORTS_EMPHASIS_STYLE,
    SUBTITLE_HIGHLIGHT_COLORS,
    KEYWORD_HIGHLIGHT_CONFIG,
    # 바이럴 자막 스타일
    VIRAL_SUBTITLE_STYLE,
    VIRAL_SUBTITLE_PRESETS,
    # Ken Burns 효과
    SHORTS_KEN_BURNS,
    FFMPEG_ZOOMPAN_PRESETS,
    # 이미지 생성 (Gemini 3 Pro)
    IMAGE_MODEL,
    IMAGE_PROMPT_CONFIG,
    # TTS (Gemini)
    TTS_CONFIG,
    TTS_VOICE_BY_ISSUE,
    GEMINI_TTS_VOICES,
    # 씬 전환 효과
    SCENE_TRANSITIONS,
    FFMPEG_TRANSITIONS,
    # YouTube SEO
    YOUTUBE_UPLOAD_CONFIG,
    YOUTUBE_SEO_PROMPT,
    # 썸네일
    THUMBNAIL_CONFIG,
    THUMBNAIL_PROMPT_TEMPLATE,
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
    validate_person_name,
    INVALID_PERSON_NAMES,
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

from .silhouette_generator import (
    generate_silhouette_dynamic,
    get_cached_silhouette,
    clear_cache as clear_silhouette_cache,
    get_cache_stats as get_silhouette_cache_stats,
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
    run_youtube_collection,
    run_script_generation,
    run_shorts_pipeline,
    run_full_pipeline,
    run_video_generation,
    run_viral_pipeline,
    generate_tts,
    generate_images_parallel,
    generate_single_image,
    generate_thumbnail,
    render_video,
    generate_viral_subtitles,
    YOUTUBE_SEARCH_AVAILABLE,
)

# YouTube 트렌딩 검색 (선택적)
try:
    from .youtube_search import (
        search_trending_shorts,
        search_shorts_by_category,
        get_best_shorts_topic,
        youtube_to_news_format,
        get_video_comments,
        extract_trending_topics,
    )
except ImportError:
    # googleapiclient 미설치 시
    pass


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
    # BGM
    'SHORTS_BGM_MOODS',
    'SHORTS_BGM_CONFIG',
    'BGM_MOOD_OPTIONS',
    # 자막
    'SHORTS_SUBTITLE_STYLE',
    'SHORTS_EMPHASIS_STYLE',
    'SUBTITLE_HIGHLIGHT_COLORS',
    'KEYWORD_HIGHLIGHT_CONFIG',
    # 바이럴 자막 스타일
    'VIRAL_SUBTITLE_STYLE',
    'VIRAL_SUBTITLE_PRESETS',
    # Ken Burns 효과
    'SHORTS_KEN_BURNS',
    'FFMPEG_ZOOMPAN_PRESETS',
    # 이미지 생성 (Gemini 3 Pro)
    'IMAGE_MODEL',
    'IMAGE_PROMPT_CONFIG',
    # TTS (Gemini)
    'TTS_CONFIG',
    'TTS_VOICE_BY_ISSUE',
    'GEMINI_TTS_VOICES',
    # 씬 전환 효과
    'SCENE_TRANSITIONS',
    'FFMPEG_TRANSITIONS',
    # YouTube SEO
    'YOUTUBE_UPLOAD_CONFIG',
    'YOUTUBE_SEO_PROMPT',
    # 썸네일
    'THUMBNAIL_CONFIG',
    'THUMBNAIL_PROMPT_TEMPLATE',
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
    'validate_person_name',
    'INVALID_PERSON_NAMES',
    'SheetsSaveError',

    # News Collector
    'collect_entertainment_news',
    'search_celebrity_news',
    'extract_celebrity_name',
    'detect_issue_type',
    'get_silhouette_description',
    'generate_hook_text',

    # Silhouette Generator (동적 실루엣 생성)
    'generate_silhouette_dynamic',
    'get_cached_silhouette',
    'clear_silhouette_cache',
    'get_silhouette_cache_stats',

    # Script Generator
    'DEFAULT_MODEL',
    'GPT51_COSTS',
    'generate_shorts_script',
    'generate_complete_shorts_package',
    'enhance_image_prompts',
    'format_script_for_sheet',
    'extract_gpt51_response',

    # Main Pipeline
    'run_news_collection',
    'run_youtube_collection',
    'run_script_generation',
    'run_shorts_pipeline',
    'run_full_pipeline',
    'run_viral_pipeline',

    # Video Generation (병렬 처리)
    'run_video_generation',
    'generate_tts',
    'generate_images_parallel',
    'generate_single_image',
    'generate_thumbnail',
    'render_video',
    'generate_viral_subtitles',

    # YouTube Search (선택적)
    'YOUTUBE_SEARCH_AVAILABLE',
    'search_trending_shorts',
    'search_shorts_by_category',
    'get_best_shorts_topic',
    'youtube_to_news_format',
    'get_video_comments',
    'extract_trending_topics',
]
