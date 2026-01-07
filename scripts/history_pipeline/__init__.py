"""
한국사 파이프라인 (역할 분리 구조)

## 2026-01 개편: 창작/실행 분리

창작 작업 (Claude가 대화에서 직접 수행):
- 자료 조사 및 검증
- 에피소드 기획 (구조, 흐름)
- 대본 작성 (12,000~15,000자)
- 이미지 프롬프트 생성
- YouTube 메타데이터 (제목, 설명, 태그)
- 썸네일 문구 설계
- 품질 검수

실행 작업 (workers.py에서 API 호출):
- TTS 생성 → Gemini/Google TTS
- 이미지 생성 → Gemini Imagen
- 영상 렌더링 → FFmpeg
- YouTube 업로드 → YouTube API

사용법:
    # Claude가 대화에서 대본 작성 후:
    from scripts.history_pipeline import execute_episode

    result = execute_episode(
        episode_id="ep001",
        title="광개토왕의 정복전쟁",
        script="대본 내용...",
        image_prompts=[{"prompt": "...", "scene_index": 1}],
        metadata={"title": "...", "description": "...", "tags": [...]},
        generate_video=True,
        upload=True,
    )
"""

from .config import (
    ERAS,
    ERA_ORDER,
    ERA_KEYWORDS,
    HISTORY_TOPICS,
    HISTORY_OPUS_INPUT_SHEET,
    PENDING_TARGET_COUNT,
    get_active_eras,
)

from .run import (
    run_history_pipeline,
    run_single_episode,
    get_pipeline_status,
    run_auto_script_pipeline,  # DEPRECATED: Claude가 대화에서 직접 작성
)

# ★ Workers (실행 담당) - 주요 사용 함수
from .workers import (
    execute_episode,      # 통합 실행 함수
    generate_tts,         # TTS 생성
    generate_image,       # 단일 이미지 생성
    generate_images_batch,  # 다중 이미지 생성
    render_video,         # 영상 렌더링
    upload_youtube,       # YouTube 업로드
    save_script,          # 대본 파일 저장
    save_brief,           # 기획서 저장
    save_metadata,        # 메타데이터 저장
)

from .sheets import (
    SheetsSaveError,
    ensure_history_opus_input_sheet,
    get_series_progress,
    get_next_episode_info,
    count_pending_episodes,
    get_topic_by_global_episode,
    get_total_episode_count,
    get_era_episode_count,
)

from .collector import (
    collect_topic_materials,
)

from .opus import (
    generate_topic_opus_input,
)

__all__ = [
    # ★ Workers (실행 담당) - 주요 사용 함수
    "execute_episode",      # 통합 실행 함수
    "generate_tts",         # TTS 생성
    "generate_image",       # 단일 이미지 생성
    "generate_images_batch",  # 다중 이미지 생성
    "render_video",         # 영상 렌더링
    "upload_youtube",       # YouTube 업로드
    "save_script",          # 대본 파일 저장
    "save_brief",           # 기획서 저장
    "save_metadata",        # 메타데이터 저장
    # 레거시 함수 (참고용)
    "run_history_pipeline",
    "run_single_episode",
    "get_pipeline_status",
    "run_auto_script_pipeline",  # DEPRECATED
    # 설정
    "ERAS",
    "ERA_ORDER",
    "ERA_KEYWORDS",
    "HISTORY_TOPICS",
    "HISTORY_OPUS_INPUT_SHEET",
    "PENDING_TARGET_COUNT",
    "get_active_eras",
    # 시트 관리
    "SheetsSaveError",
    "ensure_history_opus_input_sheet",
    "get_series_progress",
    "get_next_episode_info",
    "count_pending_episodes",
    "get_topic_by_global_episode",
    "get_total_episode_count",
    "get_era_episode_count",
    # 자료 수집
    "collect_topic_materials",
    # OPUS 생성
    "generate_topic_opus_input",
]
