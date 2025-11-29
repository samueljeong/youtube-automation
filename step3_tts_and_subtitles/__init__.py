"""
Step 3: TTS & Subtitles
Google Cloud TTS 및 자막 생성 모듈

핵심 기능:
- 5000바이트 제한 해결 (tts_chunking)
- FFmpeg 기반 오디오 병합 (tts_service)
- SRT 자막 자동 생성 (tts_service)
"""

# 새 파이프라인 (권장)
from .tts_chunking import (
    build_chunks_for_scenes,
    split_korean_sentences,
    chunk_sentences,
    estimate_chunk_stats
)
from .tts_service import run_tts_pipeline

# 기존 모듈 (호환성 유지)
from .tts_script_builder import build_tts_input
from .subtitle_generator import generate_srt
from .call_google_tts import generate_tts, estimate_audio_duration
from .tts_gender_rules import decide_gender, get_tts_voice_id

__all__ = [
    # 새 파이프라인
    "run_tts_pipeline",
    "build_chunks_for_scenes",
    "split_korean_sentences",
    "chunk_sentences",
    "estimate_chunk_stats",
    # 기존 모듈
    "build_tts_input",
    "generate_srt",
    "generate_tts",
    "estimate_audio_duration",
    "decide_gender",
    "get_tts_voice_id",
]
