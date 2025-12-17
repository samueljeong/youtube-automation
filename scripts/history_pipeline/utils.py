"""
한국사 파이프라인 유틸리티 함수
"""

import re
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from .config import (
    ERAS,
    ERA_KEYWORDS,
    RELEVANCE_WEIGHTS,
    QUALITY_WEIGHTS,
    SOURCE_TYPES,
)


def normalize_text(text: str) -> str:
    """텍스트 정규화 (공백 정리)"""
    return re.sub(r"\s+", " ", (text or "").strip())


def compute_hash(title: str, url: str) -> str:
    """제목+URL로 해시 생성 (중복 방지)"""
    s = f"{title}|{url}".encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:16]


def get_kst_now() -> datetime:
    """현재 KST 시간 반환"""
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst)


def get_run_id() -> str:
    """실행 ID 생성 (YYYY-MM-DD 형식)"""
    return get_kst_now().strftime("%Y-%m-%d")


def get_era_display_name(era: str) -> str:
    """시대의 한글 이름 반환"""
    era_info = ERAS.get(era, {})
    return era_info.get("name", era)


def get_era_period(era: str) -> str:
    """시대의 기간 반환"""
    era_info = ERAS.get(era, {})
    return era_info.get("period", "")


def detect_keywords(text: str, era: str) -> List[str]:
    """
    텍스트에서 시대 관련 키워드 감지

    Args:
        text: 검색할 텍스트
        era: 시대 키

    Returns:
        감지된 키워드 리스트
    """
    keywords = ERA_KEYWORDS.get(era, {})
    primary = keywords.get("primary", [])
    secondary = keywords.get("secondary", [])

    detected = []
    for kw in primary + secondary:
        if kw in text:
            detected.append(kw)

    return detected


def passes_era_filter(title: str, content: str, era: str) -> bool:
    """
    시대 필터 통과 여부 확인

    - primary 키워드 1개 이상 포함
    - exclude 키워드 없음

    Args:
        title: 제목
        content: 내용
        era: 시대 키

    Returns:
        필터 통과 여부
    """
    text = f"{title} {content}"
    keywords = ERA_KEYWORDS.get(era, {})

    primary = keywords.get("primary", [])
    exclude = keywords.get("exclude", [])

    # 제외 키워드 체크
    for kw in exclude:
        if kw in text:
            print(f"[FILTER] 제외 키워드 발견: {kw}")
            return False

    # 주요 키워드 1개 이상 필요
    has_primary = any(kw in text for kw in primary)
    if not has_primary:
        print(f"[FILTER] primary 키워드 없음 (era={era}, primary 샘플={primary[:3]})")
    return has_primary


def calculate_relevance_score(title: str, content: str, era: str) -> int:
    """
    관련도 점수 계산

    Args:
        title: 제목
        content: 내용
        era: 시대 키

    Returns:
        관련도 점수
    """
    keywords = ERA_KEYWORDS.get(era, {})
    primary = keywords.get("primary", [])
    secondary = keywords.get("secondary", [])

    score = 0

    # 주요 키워드
    for kw in primary:
        if kw in title:
            score += RELEVANCE_WEIGHTS["primary_keyword_in_title"]
        elif kw in content:
            score += RELEVANCE_WEIGHTS["primary_keyword_in_content"]

    # 보조 키워드
    for kw in secondary:
        if kw in title or kw in content:
            score += RELEVANCE_WEIGHTS["secondary_keyword"]

    return score


def calculate_quality_score(source_type: str) -> int:
    """
    자료 품질 점수 계산

    Args:
        source_type: 출처 유형 (university, museum, journal, long_form, encyclopedia)

    Returns:
        품질 점수
    """
    return QUALITY_WEIGHTS.get(source_type, 3)


def calculate_freshness_score(collected_at: str, now: Optional[datetime] = None) -> int:
    """
    신선도 점수 계산 (최근 수집일수록 높음)

    Args:
        collected_at: 수집 시간 (ISO 형식)
        now: 현재 시간 (기본: UTC now)

    Returns:
        신선도 점수 (0~10)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if not collected_at:
        return 5  # 기본값

    try:
        dt = datetime.fromisoformat(collected_at.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        days = (now - dt).total_seconds() / (24 * 3600)

        # 7일 이내: 10점, 30일: 5점, 90일 이상: 1점
        if days <= 7:
            return 10
        elif days <= 30:
            return max(5, 10 - int(days / 5))
        elif days <= 90:
            return max(1, 5 - int((days - 30) / 20))
        else:
            return 1
    except Exception:
        return 5


def guess_topic(title: str, content: str, era: str) -> str:
    """
    주제 분류 추정

    Args:
        title: 제목
        content: 내용
        era: 시대 키

    Returns:
        주제 분류 (정치/군사/문화/경제/외교/인물)
    """
    text = f"{title} {content}"

    topic_keywords = {
        "정치": ["왕", "정치", "제도", "법", "관료", "조정", "권력", "왕권", "신하"],
        "군사": ["전쟁", "전투", "군대", "침략", "정복", "장군", "병사", "무기"],
        "문화": ["문화", "예술", "불교", "유교", "사찰", "건축", "유물", "유적", "문화재"],
        "경제": ["경제", "무역", "농업", "상업", "화폐", "세금", "토지"],
        "외교": ["외교", "사신", "조공", "동맹", "중국", "당나라", "명나라", "일본"],
        "인물": ["왕", "장군", "대왕", "열전", "생애", "업적"],
    }

    best_topic = "일반"
    best_score = 0

    for topic, keywords in topic_keywords.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_topic = topic
            best_score = score

    return best_topic


def get_source_weight(source_type: str) -> float:
    """출처 유형의 가중치 반환"""
    return SOURCE_TYPES.get(source_type, {}).get("weight", 1.0)


def format_keywords_for_sheet(keywords: List[str]) -> str:
    """키워드 리스트를 시트 저장용 문자열로 변환"""
    return "|".join(keywords[:10])  # 최대 10개


def parse_keywords_from_sheet(keywords_str: str) -> List[str]:
    """시트의 키워드 문자열을 리스트로 변환"""
    if not keywords_str:
        return []
    return [k.strip() for k in keywords_str.split("|") if k.strip()]
