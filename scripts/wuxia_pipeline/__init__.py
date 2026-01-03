"""
무협 파이프라인 (혈영 시리즈)
- 다중 음성 TTS 지원
- Claude Opus 4.5 대본 생성
- YouTube 자동 업로드
"""

from .config import (
    SERIES_INFO,
    VOICE_MAP,
    MAIN_CHARACTER_TAGS,
    EXTRA_TAGS,
    SCRIPT_CONFIG,
    EPISODE_TEMPLATES,
    SHEET_HEADERS,
)

from .multi_voice_tts import (
    parse_script_to_segments,
    generate_multi_voice_tts,
    generate_srt_from_timeline,
    VoiceSegment,
)

from .script_generator import (
    generate_episode_script,
    generate_youtube_metadata,
)

__all__ = [
    # Config
    "SERIES_INFO",
    "VOICE_MAP",
    "MAIN_CHARACTER_TAGS",
    "EXTRA_TAGS",
    "SCRIPT_CONFIG",
    "EPISODE_TEMPLATES",
    "SHEET_HEADERS",
    # Multi-voice TTS
    "parse_script_to_segments",
    "generate_multi_voice_tts",
    "generate_srt_from_timeline",
    "VoiceSegment",
    # Script Generator
    "generate_episode_script",
    "generate_youtube_metadata",
]
