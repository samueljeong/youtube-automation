# -*- coding: utf-8 -*-
"""
언어별 설정 모듈

사용법:
    from lang import get_config, detect_language

    # 언어 감지
    lang = detect_language("안녕하세요")  # 'ko'
    lang = detect_language("こんにちは")  # 'ja'

    # 설정 가져오기
    config = get_config('ko')
    print(config.FONTS)
    print(config.SUBTITLE['max_chars_total'])
"""

import re
from typing import Optional

# 언어별 설정 모듈 import
from . import ko
from . import ja
from . import en


# 지원 언어 목록
SUPPORTED_LANGUAGES = {
    'ko': ko,
    'ja': ja,
    'en': en,
}


def detect_language(text: str) -> str:
    """
    텍스트의 주요 언어를 감지

    일본어 뉴스/비즈니스 대본은 한자(漢字) 비율이 높고 히라가나/가타카나가 적음.
    따라서 한글이 없고 히라가나/가타카나가 1개 이상 있으면 일본어로 판단.

    Args:
        text: 분석할 텍스트

    Returns:
        언어 코드 ('ko', 'ja', 'en')
    """
    if not text:
        return 'en'

    # 한글 감지
    korean_chars = len(re.findall(r'[가-힣]', text))
    # 일본어 감지 (히라가나 + 가타카나)
    japanese_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF]', text))

    # 한국어 우선 (한글이 있으면 한국어)
    if korean_chars > 0:
        return 'ko'
    # 일본어: 히라가나/가타카나가 1개 이상 있으면 일본어
    elif japanese_chars > 0:
        return 'ja'

    return 'en'


def get_config(lang_code: str):
    """
    언어 코드에 해당하는 설정 모듈 반환

    Args:
        lang_code: 언어 코드 ('ko', 'ja', 'en')

    Returns:
        언어 설정 모듈 (없으면 한국어 기본값)
    """
    return SUPPORTED_LANGUAGES.get(lang_code, ko)


def get_fonts(lang_code: str) -> dict:
    """언어별 폰트 설정 반환"""
    config = get_config(lang_code)
    return getattr(config, 'FONTS', ko.FONTS)


def get_subtitle_settings(lang_code: str) -> dict:
    """언어별 자막 설정 반환"""
    config = get_config(lang_code)
    return getattr(config, 'SUBTITLE', ko.SUBTITLE)


def get_subtitle_max_chars(lang_code: str) -> int:
    """언어별 자막 최대 글자 수 반환"""
    config = get_config(lang_code)
    subtitle = getattr(config, 'SUBTITLE', ko.SUBTITLE)
    return subtitle.get('max_chars_total', 40)


def get_tts_settings(lang_code: str) -> dict:
    """언어별 TTS 설정 반환"""
    config = get_config(lang_code)
    return getattr(config, 'TTS', ko.TTS)


def get_tts_voice(lang_code: str, gender: str = 'male') -> str:
    """언어별 TTS 음성 반환"""
    config = get_config(lang_code)
    tts = getattr(config, 'TTS', ko.TTS)
    voices = tts.get('voices', {})
    return voices.get(gender, tts.get('default_voice', ko.TTS['default_voice']))


def get_ass_style(lang_code: str) -> str:
    """언어별 ASS 자막 스타일 문자열 반환"""
    config = get_config(lang_code)
    if hasattr(config, 'get_subtitle_ass_style'):
        return config.get_subtitle_ass_style()
    return ko.get_subtitle_ass_style()


def get_thumbnail_settings(lang_code: str) -> dict:
    """언어별 썸네일 텍스트 설정 반환"""
    config = get_config(lang_code)
    return getattr(config, 'THUMBNAIL_TEXT', ko.THUMBNAIL_TEXT)


def get_youtube_title_settings(lang_code: str) -> dict:
    """언어별 유튜브 제목 설정 반환"""
    config = get_config(lang_code)
    return getattr(config, 'YOUTUBE_TITLE', ko.YOUTUBE_TITLE)
