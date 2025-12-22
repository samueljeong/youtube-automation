"""
성경통독 파이프라인

- 개역개정 성경 JSON 기반
- TTS: 절 번호 제외, 말씀만 읽음
- 자막: 절 번호 포함 (1) 태초에...
- Google Sheets 연동
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
]
