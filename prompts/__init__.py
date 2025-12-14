# -*- coding: utf-8 -*-
"""
GPT-5.1 대본 분석 프롬프트 모듈

토큰 최적화를 위해 언어별/카테고리별로 프롬프트를 분리하여
필요한 부분만 동적으로 조합합니다.

구조:
- base.py: 공통 규칙 (웹툰 캐릭터, SSML, BGM/SFX, video_effects 등)
- lang/: 언어별 규칙 (ko, ja, en)
- category/: 카테고리별 규칙 (health, news, story)
- builder.py: 동적 프롬프트 빌더
"""

from .builder import (
    build_system_prompt,
    detect_category_simple,
    detect_language_simple,
)
