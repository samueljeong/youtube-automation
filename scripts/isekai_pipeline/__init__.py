"""
혈영 이세계편 파이프라인 (시즌2)

8개 Opus 에이전트 구조:
1. PLANNER: 에피소드 기획
2. WRITER: 대본 작성 (25,000자)
3. ARTIST: 이미지 프롬프트
4. NARRATOR: TTS 설정
5. SUBTITLE: 자막 스타일
6. EDITOR: BGM/SFX
7. METADATA: YouTube 메타데이터
8. REVIEWER: 품질 검수
"""

from .config import (
    SERIES_INFO,
    PART_STRUCTURE,
    CHARACTERS,
    WORLD_SETTING,
    POWER_LEVELS,
    WRITING_STYLE,
    SCRIPT_CONFIG,
    TTS_CONFIG,
    IMAGE_STYLE,
    BGM_CONFIG,
    THUMBNAIL_CONFIG,
    SHEET_NAME,
    SHEET_HEADERS,
    OUTPUT_BASE,
    OPENROUTER_API_KEY,
    CLAUDE_MODEL,
)

from .agents import (
    run_planner,
    run_writer,
    run_artist,
    run_narrator,
    run_subtitle,
    run_editor,
    run_metadata,
    run_reviewer,
    load_series_bible,
    get_part_info,
)

from .sheets import (
    create_isekai_sheet,
    add_episode,
    get_pending_episodes,
    get_ready_episodes,
    get_episode_by_number,
    update_episode_status,
    update_episode_with_result,
    initialize_sheet_with_episodes,
    get_prev_episode_summary,
)

from .run import (
    run_pipeline,
    run_auto_pipeline,
    run_single_agent,
)

__all__ = [
    # Config
    "SERIES_INFO",
    "PART_STRUCTURE",
    "CHARACTERS",
    "WORLD_SETTING",
    "POWER_LEVELS",
    "WRITING_STYLE",
    "SCRIPT_CONFIG",
    "TTS_CONFIG",
    "IMAGE_STYLE",
    "BGM_CONFIG",
    "THUMBNAIL_CONFIG",
    "SHEET_NAME",
    "SHEET_HEADERS",
    "OUTPUT_BASE",
    "OPENROUTER_API_KEY",
    "CLAUDE_MODEL",
    # Agents
    "run_planner",
    "run_writer",
    "run_artist",
    "run_narrator",
    "run_subtitle",
    "run_editor",
    "run_metadata",
    "run_reviewer",
    "load_series_bible",
    "get_part_info",
    # Sheets
    "create_isekai_sheet",
    "add_episode",
    "get_pending_episodes",
    "get_ready_episodes",
    "get_episode_by_number",
    "update_episode_status",
    "update_episode_with_result",
    "initialize_sheet_with_episodes",
    "get_prev_episode_summary",
    # Run
    "run_pipeline",
    "run_auto_pipeline",
    "run_single_agent",
]
