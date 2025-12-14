# -*- coding: utf-8 -*-
"""언어별 프롬프트 규칙"""

from .ko import KOREAN_RULES, get_korean_prompt
from .ja import JAPANESE_RULES, get_japanese_prompt
from .en import ENGLISH_RULES, get_english_prompt

LANG_PROMPTS = {
    'ko': get_korean_prompt,
    'ja': get_japanese_prompt,
    'en': get_english_prompt,
}

LANG_CONFIGS = {
    'ko': {
        'name': 'Korean',
        'native': '한국어',
        'instruction': 'Write ALL titles, description, thumbnail text, and narration in Korean (한국어).'
    },
    'ja': {
        'name': 'Japanese',
        'native': '日本語',
        'instruction': 'Write ALL text in Japanese using ONLY hiragana/katakana. NO KANJI! Example: 年金→ねんきん. Numbers/symbols OK.'
    },
    'en': {
        'name': 'English',
        'native': 'English',
        'instruction': 'Write ALL titles, description, thumbnail text, and narration in English.'
    },
}
