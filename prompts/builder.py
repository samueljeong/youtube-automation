# -*- coding: utf-8 -*-
"""동적 프롬프트 빌더 - 언어/카테고리별 프롬프트 조합"""

import re
from .base import get_base_prompt
from .lang import LANG_PROMPTS, LANG_CONFIGS
from .category import CATEGORY_PROMPTS


def detect_language_simple(script: str) -> str:
    """대본에서 언어 감지 (한국어/일본어/영어)

    Args:
        script: 대본 텍스트

    Returns:
        'ko', 'ja', 'en' 중 하나
    """
    if not script:
        return 'en'

    # 앞부분만 분석 (토큰 절약)
    sample = script[:3000]

    # 한글 감지
    korean_chars = len(re.findall(r'[가-힣]', sample))
    # 히라가나 + 가타카나 (일본어 고유 문자)
    japanese_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF]', sample))

    # 한국어 우선 (한글이 있으면 한국어)
    if korean_chars > 0:
        return 'ko'
    # 일본어 (히라가나/가타카나가 1개 이상)
    elif japanese_chars > 0:
        return 'ja'

    return 'en'


def detect_category_simple(script: str) -> str:
    """대본에서 카테고리 사전 감지 (키워드 기반)

    Args:
        script: 대본 텍스트

    Returns:
        'health', 'news', 'story' 중 하나
    """
    if not script:
        return 'story'

    # 앞부분만 분석 (토큰 절약)
    sample = script[:2000].lower()

    # 건강 키워드 (최우선 감지)
    health_keywords = [
        '건강', '질병', '증상', '치료', '예방', '의사', '병원', '약', '검사', '진단',
        '혈압', '혈당', '관절', '심장', '뇌', '영양제', '운동법', '노화', '장수',
        '치매', '암', '당뇨', '콜레스테롤', '비타민', '면역', '수면', '스트레스',
        '하면 안됩니다', '하지 마세요', '먹지 마세요', '피하세요',
        # 일본어 건강 키워드
        'けんこう', 'びょういん', 'いしゃ', 'くすり', 'けんさ',
        # 영어 건강 키워드
        'health', 'doctor', 'hospital', 'symptom', 'treatment', 'disease',
    ]

    # 뉴스 키워드
    news_keywords = [
        '대통령', '국회', '정치', '정당', '여당', '야당', '정부',
        '경제', '주가', '환율', '부동산', '금리', '인플레이션',
        '사건', '사고', '재판', '법원', '검찰', '경찰',
        '기업', '삼성', '현대', '쿠팡', 'SK', 'LG',
        '발표', '성명', '기자회견', '속보', '뉴스',
        # 일본어 뉴스 키워드
        'せいじ', 'けいざい', 'じけん', 'ニュース',
        # 영어 뉴스 키워드
        'president', 'government', 'economy', 'stock', 'breaking', 'news',
    ]

    # 키워드 카운트
    health_count = sum(1 for kw in health_keywords if kw in sample)
    news_count = sum(1 for kw in news_keywords if kw in sample)

    # 건강이 3개 이상이면 health
    if health_count >= 3:
        return 'health'
    # 뉴스가 3개 이상이면 news
    elif news_count >= 3:
        return 'news'

    # 기본값: story
    return 'story'


def build_system_prompt(
    language: str = 'ko',
    category: str = 'story',
    audience: str = 'senior',
    image_count: int = 5,
) -> str:
    """언어와 카테고리에 맞는 시스템 프롬프트 동적 조합

    Args:
        language: 'ko', 'ja', 'en'
        category: 'health', 'news', 'story'
        audience: 'senior', 'general'
        image_count: 생성할 씬 이미지 개수

    Returns:
        조합된 시스템 프롬프트 문자열
    """
    # 언어 설정
    lang_config = LANG_CONFIGS.get(language, LANG_CONFIGS['ko'])

    # 프롬프트 조합 시작
    parts = []

    # 1. 언어 지시 헤더
    parts.append(f"""You are an AI that analyzes scripts and generates image prompts for YouTube videos.

## LANGUAGE RULE (CRITICAL!)
Output Language: {lang_config['name']} ({lang_config['native']})
{lang_config['instruction']}

Target Audience: {'General (20-40s)' if audience == 'general' else 'Senior (50-70s)'}
Generate exactly {image_count} scenes.""")

    # 2. 공통 규칙 (base)
    parts.append(get_base_prompt())

    # 3. 언어별 규칙
    lang_prompt_fn = LANG_PROMPTS.get(language, LANG_PROMPTS['ko'])
    parts.append(lang_prompt_fn())

    # 4. 카테고리별 규칙 (해당 카테고리만!)
    category_prompt_fn = CATEGORY_PROMPTS.get(category, CATEGORY_PROMPTS['story'])
    parts.append(category_prompt_fn())

    # 5. 최종 지시
    parts.append(f"""
## FINAL INSTRUCTIONS
1. Detect and confirm category as: {category}
2. Generate exactly {image_count} scenes
3. NARRATION = EXACT script text (no paraphrasing!)
4. image_prompt = ALWAYS in English
5. All other text = {lang_config['name']}
6. Respond ONLY with valid JSON. No other text.""")

    return "\n\n".join(parts)


def get_token_estimate(prompt: str) -> int:
    """프롬프트의 대략적인 토큰 수 추정

    Args:
        prompt: 프롬프트 문자열

    Returns:
        추정 토큰 수 (영어 기준 4자 = 1토큰, 한글 1자 = 1토큰)
    """
    # 영어/숫자/기호
    ascii_chars = len(re.findall(r'[a-zA-Z0-9\s\.\,\!\?\:\;\-\(\)\[\]\{\}\"\'\/\\\@\#\$\%\^\&\*\+\=\<\>\~\`]', prompt))
    # 한글/일본어/중국어
    cjk_chars = len(re.findall(r'[\u3040-\u9fff\uac00-\ud7af]', prompt))

    # 대략적 토큰 추정
    return int(ascii_chars / 4) + cjk_chars
