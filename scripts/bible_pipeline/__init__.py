"""
성경통독 파이프라인

- 개역개정 성경 JSON 기반
- TTS: 절 번호 제외, 말씀만 읽음
- 자막: 절 번호 포함 (1) 태초에...
- Google Sheets 연동
- 106개 에피소드 (100일 성경통독 + 6일 보너스)
"""

from .config import (
    # TTS 설정
    BIBLE_TTS_VOICE,
    BIBLE_TTS_SPEAKING_RATE,

    # 영상 설정
    BIBLE_VIDEO_LENGTH_MINUTES,
    BIBLE_CHARS_PER_MINUTE,
    BIBLE_TARGET_CHARS,

    # 성경 데이터
    BIBLE_JSON_PATH,
    BIBLE_BOOKS,

    # Google Sheets 설정
    BIBLE_SHEET_NAME,
    BIBLE_SHEET_HEADERS,
)

from .run import (
    BiblePipeline,
    Episode,
    Chapter,
    Verse,
)

from .background import (
    generate_book_background,
    generate_all_backgrounds,
    get_background_path,
    get_background_prompt,
)

from .thumbnail import (
    generate_episode_thumbnail,
    generate_all_thumbnails,
)

from .renderer import (
    generate_verse_srt,
    generate_ass_subtitle,
    render_episode_video,
    render_verse_frame,
    create_bible_background,
)

__all__ = [
    # TTS 설정
    "BIBLE_TTS_VOICE",
    "BIBLE_TTS_SPEAKING_RATE",

    # 영상 설정
    "BIBLE_VIDEO_LENGTH_MINUTES",
    "BIBLE_CHARS_PER_MINUTE",
    "BIBLE_TARGET_CHARS",

    # 성경 데이터
    "BIBLE_JSON_PATH",
    "BIBLE_BOOKS",

    # Google Sheets 설정
    "BIBLE_SHEET_NAME",
    "BIBLE_SHEET_HEADERS",

    # 파이프라인 클래스
    "BiblePipeline",
    "Episode",
    "Chapter",
    "Verse",

    # 배경 이미지
    "generate_book_background",
    "generate_all_backgrounds",
    "get_background_path",
    "get_background_prompt",

    # 썸네일
    "generate_episode_thumbnail",
    "generate_all_thumbnails",
]
