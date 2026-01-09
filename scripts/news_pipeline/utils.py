"""
뉴스 파이프라인 유틸리티 함수
"""

import re
import hashlib
from datetime import datetime, timezone, timedelta

from .config import CATEGORY_KEYWORDS, CHANNEL_FILTERS, WEEKDAY_ANGLES


def normalize_text(text: str) -> str:
    """텍스트 정규화 (공백 정리)"""
    return re.sub(r"\s+", " ", (text or "").strip())


def compute_hash(title: str, link: str) -> str:
    """제목+링크로 해시 생성 (중복 방지)"""
    s = f"{title}|{link}".encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:16]


def get_tab_name(base: str, channel: str) -> str:
    """채널별 탭 이름 생성"""
    return f"{base}_{channel}"


def get_kst_now() -> datetime:
    """현재 KST 시간 반환"""
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst)


def get_weekday_angle() -> str:
    """오늘 요일에 맞는 권장 앵글 반환"""
    weekday = get_kst_now().weekday()
    return WEEKDAY_ANGLES.get(weekday, "이슈 정리")


def guess_category(title: str, summary: str) -> str:
    """규칙 기반 카테고리 분류"""
    text = f"{title} {summary}"
    best_cat, best_score = "경제", 0

    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for k in keywords if k in text)
        if score > best_score:
            best_cat, best_score = cat, score

    return best_cat


def calculate_relevance_score(title: str, summary: str, channel: str) -> int:
    """채널별 관련도 점수 계산"""
    text = f"{title} {summary}"
    filter_config = CHANNEL_FILTERS.get(channel, {})
    include_keywords = filter_config.get("include", [])
    weight = filter_config.get("weight", 1.0)

    score = 0
    for k in include_keywords:
        if k in text:
            score += 3 if k in title else 1

    return int(score * weight)


def calculate_recency_score(published_at: str, now: datetime) -> int:
    """신선도 점수 계산 (최근일수록 높음)"""
    try:
        from dateutil import parser as dtparser
    except ImportError:
        return 2

    if not published_at:
        return 2

    try:
        dt = dtparser.parse(published_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hours = (now - dt).total_seconds() / 3600
        return max(0, 10 - int(hours / 6))
    except Exception:
        return 2


def passes_channel_filter(title: str, summary: str, channel: str) -> bool:
    """채널 필터 통과 여부 (include 1개 이상 + exclude 없음)"""
    text = f"{title} {summary}"
    filter_config = CHANNEL_FILTERS.get(channel, {})

    include_keywords = filter_config.get("include", [])
    exclude_keywords = filter_config.get("exclude", [])

    for k in exclude_keywords:
        if k in text:
            return False

    return any(k in text for k in include_keywords)
