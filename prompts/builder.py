# -*- coding: utf-8 -*-
"""동적 프롬프트 빌더 - 언어/카테고리별 프롬프트 조합"""

import re
from .base import get_base_prompt
from .lang import LANG_PROMPTS, LANG_CONFIGS
from .category import CATEGORY_PROMPTS
from .vrcs import get_vrcs_prompt


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
        카테고리: 'health', 'news', 'education', 'faith', 'history',
                 'cooking', 'finance', 'motivation', 'story'
    """
    if not script:
        return 'story'

    # 앞부분만 분석 (토큰 절약)
    sample = script[:2000].lower()

    # 카테고리별 키워드 정의
    category_keywords = {
        'faith': [
            # 한국어
            '하나님', '예수', '성경', '믿음', '기도', '은혜', '말씀', '찬양', '교회', '목사',
            '설교', '신앙', '다윗', '모세', '요셉', '예배', '성령', '복음', '구원', '축복',
            # 일본어
            'かみさま', 'いのり', 'せいしょ', 'しんこう', 'きょうかい',
            # 영어
            'god', 'jesus', 'bible', 'faith', 'prayer', 'church', 'sermon',
        ],
        'history': [
            # 한국어
            '역사', '조선', '고려', '삼국', '일제', '전쟁', '왕', '황제', '고대', '중세', '근대',
            '임진왜란', '병자호란', '세종', '이순신', '정조', '영조', '태조', '왕조', '궁궐',
            # 일본어
            'れきし', 'せんそう', 'おう', 'こうてい', 'えどじだい',
            # 영어
            'history', 'war', 'king', 'emperor', 'dynasty', 'ancient', 'medieval',
        ],
        'cooking': [
            # 한국어
            '요리', '레시피', '음식', '맛있게', '만들기', '재료', '손질', '조리', '굽기', '볶기',
            '찌기', '반찬', '국', '찌개', '밥', '면', '고기', '채소', '양념', '소스',
            # 일본어
            'りょうり', 'れしぴ', 'たべもの', 'ざいりょう', 'ちょうり',
            # 영어
            'recipe', 'cooking', 'food', 'ingredient', 'dish', 'meal',
        ],
        'finance': [
            # 한국어
            '재테크', '투자', '주식', '부동산', '저축', '금리', '대출', '연금', '세금', '자산',
            '월급', '적금', 'etf', '펀드', '배당', '수익률', '원금', '이자', '신용',
            # 일본어
            'とうし', 'かぶしき', 'ふどうさん', 'ちょちく', 'きんり',
            # 영어
            'invest', 'stock', 'finance', 'money', 'saving', 'tax', 'loan',
        ],
        'motivation': [
            # 한국어
            '자기계발', '습관', '목표', '성공', '실패', '시간관리', '집중력', '번아웃', '동기부여',
            '성장', '변화', '마인드', '멘탈', '루틴', '생산성', '꿈', '도전', '노력',
            # 일본어
            'しゅうかん', 'もくひょう', 'せいこう', 'しっぱい', 'どりょく',
            # 영어
            'habit', 'goal', 'success', 'motivation', 'mindset', 'productivity', 'growth',
        ],
        'education': [
            # 한국어
            '지식', '교육', '학습', '과학', '심리', '뇌과학', '철학', '경제원리', '원리', '이유',
            '연구', '실험', '이론', '분석', '설명', '개념', '논리', '인지', '사고',
            # 일본어
            'ちしき', 'きょういく', 'がくしゅう', 'かがく', 'しんり',
            # 영어
            'science', 'psychology', 'brain', 'research', 'study', 'theory', 'analysis',
        ],
        'health': [
            # 한국어
            '건강', '질병', '증상', '치료', '예방', '의사', '병원', '약', '검사', '진단',
            '혈압', '혈당', '관절', '심장', '뇌', '영양제', '운동법', '노화', '장수',
            '치매', '암', '당뇨', '콜레스테롤', '비타민', '면역', '수면', '스트레스',
            '하면 안됩니다', '하지 마세요', '먹지 마세요', '피하세요',
            # 일본어
            'けんこう', 'びょういん', 'いしゃ', 'くすり', 'けんさ', 'しょうじょう',
            # 영어
            'health', 'doctor', 'hospital', 'symptom', 'treatment', 'disease', 'medical',
        ],
        'news': [
            # 한국어
            '대통령', '국회', '정치', '정당', '여당', '야당', '정부',
            '주가', '환율', '인플레이션', '사건', '사고', '재판', '법원', '검찰', '경찰',
            '기업', '삼성', '현대', '쿠팡', 'sk', 'lg', '발표', '성명', '기자회견', '속보', '뉴스',
            # 일본어
            'せいじ', 'けいざい', 'じけん', 'ニュース', 'そくほう',
            # 영어
            'president', 'government', 'breaking', 'news', 'announcement', 'politics',
        ],
    }

    # 각 카테고리별 키워드 카운트
    category_scores = {}
    for category, keywords in category_keywords.items():
        score = sum(1 for kw in keywords if kw in sample)
        category_scores[category] = score

    # 가장 높은 점수의 카테고리 선택 (최소 2개 이상 매칭)
    max_category = max(category_scores, key=category_scores.get)
    max_score = category_scores[max_category]

    if max_score >= 2:
        return max_category

    # 기본값: story
    return 'story'


def build_system_prompt(
    language: str = 'ko',
    category: str = 'story',
    audience: str = 'senior',
    image_count: int = 5,
    vrcs_enabled: bool = True,
) -> str:
    """언어와 카테고리에 맞는 시스템 프롬프트 동적 조합

    Args:
        language: 'ko', 'ja', 'en'
        category: 'health', 'news', 'story'
        audience: 'senior', 'general'
        image_count: 생성할 씬 이미지 개수
        vrcs_enabled: VRCS(시청 유지 제어 시스템) 적용 여부 (기본: True)

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

    # 5. VRCS 규칙 (시청 유지 제어 시스템) - 기본 적용
    if vrcs_enabled:
        parts.append(get_vrcs_prompt())

    # 6. 최종 지시
    vrcs_note = "\n7. Apply VRCS rules for subtitle/TTS/visual coordination" if vrcs_enabled else ""
    parts.append(f"""
## FINAL INSTRUCTIONS
1. Detect and confirm category as: {category}
2. Generate exactly {image_count} scenes
3. NARRATION = EXACT script text (no paraphrasing!)
4. image_prompt = ALWAYS in English
5. All other text = {lang_config['name']}
6. Respond ONLY with valid JSON. No other text.{vrcs_note}""")

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
