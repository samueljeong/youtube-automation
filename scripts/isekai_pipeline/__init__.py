"""
혈영 이세계편 파이프라인 (시즌2)

## 역할 분리

창작 작업 (Claude가 대화에서 직접 수행):
- 기획 (씬 구조, 클리프행어)
- 대본 작성 (12,000~15,000자)
- 이미지 프롬프트 생성
- TTS 연출 지시
- 자막 스타일 설계
- BGM/SFX 설정
- YouTube 메타데이터
- 품질 검수

실행 작업 (workers.py에서 API 호출):
- TTS 생성 → Gemini/Google TTS
- 이미지 생성 → Gemini Imagen
- 영상 렌더링 → FFmpeg
- YouTube 업로드 → YouTube API

## 참조 문서 (Claude 창작 시 활용)
- docs/series_bible.md: 세계관, 캐릭터, 스토리 구조
- docs/agent_prompts.md: 역할별 가이드라인
"""

# 설정
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
)

# Workers (실행 API)
from .workers import (
    generate_tts,
    generate_image,
    render_video,
    upload_youtube,
    save_script,
    save_brief,
    save_metadata,
    ensure_directories,
)

# Sheets (Google Sheets 연동)
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
    sync_episode_from_files,
    sync_all_episodes,
)

# Run (실행 오케스트레이션)
from .run import (
    execute_episode,
    execute_from_json,
    get_part_for_episode,
)

# Script Writer (대본 분할 작성)
from .script_writer import (
    get_episode_brief,
    save_scene,
    load_scene,
    get_scene_status,
    merge_scenes,
    print_episode_progress,
    start_episode,
    continue_episode,
    get_scene_prompt,
    SCENE_STRUCTURE,
    SCENE_CONFIG,
)

# Reviewers (대본 자동 리뷰)
from .reviewers import (
    auto_review_script,
    review_script_file,
    run_form_checker,
    run_voice_checker,
    run_feel_checker,
    get_review_checklists,
    print_checklists,
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
    # Workers
    "generate_tts",
    "generate_image",
    "render_video",
    "upload_youtube",
    "save_script",
    "save_brief",
    "save_metadata",
    "ensure_directories",
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
    "sync_episode_from_files",
    "sync_all_episodes",
    # Run
    "execute_episode",
    "execute_from_json",
    "get_part_for_episode",
    # Script Writer
    "save_scene",
    "load_scene",
    "get_scene_status",
    "merge_scenes",
    "print_episode_progress",
    "start_episode",
    "continue_episode",
    "get_scene_prompt",
    "SCENE_STRUCTURE",
    "SCENE_CONFIG",
    # Reviewers
    "auto_review_script",
    "review_script_file",
    "run_form_checker",
    "run_voice_checker",
    "run_feel_checker",
    "get_review_checklists",
    "print_checklists",
]
