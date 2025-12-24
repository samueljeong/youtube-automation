"""
쇼츠 파이프라인 - 연예 뉴스 수집

Google News RSS에서 연예 뉴스 수집
연예인 이름 추출 및 이슈 분류
"""

import re
import hashlib
import feedparser
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import quote

from .config import (
    ENTERTAINMENT_RSS_FEEDS,
    ISSUE_TYPES,
    CELEBRITY_SILHOUETTES,
)


def google_news_rss_url(query: str) -> str:
    """Google News RSS URL 생성"""
    encoded = quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"


def fetch_rss_feed(url: str, max_items: int = 20) -> List[Dict[str, Any]]:
    """
    RSS 피드에서 뉴스 항목 가져오기

    Returns:
        [{"title": "...", "link": "...", "published": "...", "summary": "..."}, ...]
    """
    try:
        feed = feedparser.parse(url)
        items = []

        for entry in feed.entries[:max_items]:
            items.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", ""),
            })

        return items

    except Exception as e:
        print(f"[SHORTS] RSS 피드 가져오기 실패: {e}")
        return []


def extract_celebrity_name(text: str) -> Optional[str]:
    """
    텍스트에서 연예인 이름 추출

    패턴:
    - "박나래가", "박나래의", "박나래,"
    - 알려진 연예인 라이브러리 매칭

    Returns:
        연예인 이름 또는 None
    """
    # 1) 알려진 연예인 목록에서 찾기
    for celeb in CELEBRITY_SILHOUETTES.keys():
        if celeb in text and celeb not in ["default_male", "default_female"]:
            return celeb

    # 2) 한글 이름 패턴 (2-4글자 + 조사)
    patterns = [
        r'([가-힣]{2,4})(?:가|이|는|의|를|에게|측|씨)',
        r'\'([가-힣]{2,4})\'',
        r'\"([가-힣]{2,4})\"',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1)
            # 일반 명사 필터링
            exclude = ["대통령", "네티즌", "시청자", "팬들", "관계자", "매니저"]
            if name not in exclude:
                return name

    return None


def detect_issue_type(text: str) -> str:
    """
    뉴스 텍스트에서 이슈 유형 감지

    Returns:
        논란/열애/컴백/사건/근황
    """
    keywords = {
        "논란": ["논란", "갑질", "학폭", "폭로", "비판", "사과", "해명", "의혹"],
        "열애": ["열애", "결혼", "이혼", "파혼", "연인", "커플", "교제"],
        "컴백": ["컴백", "신곡", "앨범", "발매", "활동", "무대", "데뷔"],
        "사건": ["사고", "소송", "구속", "체포", "기소", "재판", "사망"],
        "근황": ["근황", "복귀", "활동", "방송", "출연", "인스타"],
    }

    for issue_type, words in keywords.items():
        for word in words:
            if word in text:
                return issue_type

    return "근황"  # 기본값


def get_silhouette_description(celebrity: str) -> str:
    """
    연예인에 맞는 실루엣 설명 반환

    Returns:
        실루엣 프롬프트 설명 (영어)
    """
    if celebrity in CELEBRITY_SILHOUETTES:
        return CELEBRITY_SILHOUETTES[celebrity]

    # 성별 추정 (간단한 휴리스틱)
    # 한국 이름에서 마지막 글자로 추정
    if celebrity:
        # 여성에 많은 끝글자
        female_endings = ["희", "영", "경", "숙", "정", "연", "아", "이", "나", "라"]
        if celebrity[-1] in female_endings:
            return CELEBRITY_SILHOUETTES["default_female"]

    return CELEBRITY_SILHOUETTES["default_male"]


def summarize_news(title: str, summary: str, max_length: int = 150) -> str:
    """
    뉴스 요약 생성 (3줄 이내)
    """
    # HTML 태그 제거
    clean_summary = re.sub(r'<[^>]+>', '', summary)
    clean_summary = re.sub(r'\s+', ' ', clean_summary).strip()

    # 제목 + 요약
    full_text = f"{title}. {clean_summary}"

    if len(full_text) > max_length:
        full_text = full_text[:max_length] + "..."

    return full_text


def generate_hook_text(celebrity: str, issue_type: str, title: str) -> str:
    """
    훅 문장 생성 (첫 3초)
    """
    hooks = {
        "논란": [
            f"{celebrity}, 이번엔 진짜 끝일 수도 있습니다",
            f"{celebrity}의 충격적인 진실이 밝혀졌습니다",
            f"{celebrity}, 결국 이렇게 됐습니다",
        ],
        "열애": [
            f"{celebrity}의 비밀 연인이 공개됐습니다",
            f"{celebrity}, 결혼 발표했습니다",
            f"{celebrity}의 새로운 시작입니다",
        ],
        "컴백": [
            f"{celebrity}가 돌아옵니다",
            f"{celebrity}의 역대급 컴백입니다",
            f"드디어 {celebrity}가 컴백합니다",
        ],
        "사건": [
            f"{celebrity}에게 무슨 일이 생겼습니다",
            f"{celebrity}, 충격적인 소식입니다",
            f"{celebrity}의 현재 상황입니다",
        ],
        "근황": [
            f"{celebrity}의 최근 모습입니다",
            f"{celebrity}, 요즘 이렇게 지냅니다",
            f"오랜만에 {celebrity} 소식입니다",
        ],
    }

    import random
    return random.choice(hooks.get(issue_type, hooks["근황"]))


def compute_hash(text: str) -> str:
    """텍스트 해시 생성 (중복 체크용)"""
    return hashlib.md5(text.encode()).hexdigest()[:12]


def collect_entertainment_news(
    max_per_feed: int = 10,
    total_limit: int = 20
) -> List[Dict[str, Any]]:
    """
    연예 뉴스 수집 메인 함수

    Returns:
        [
            {
                "run_id": "2024-12-24",
                "celebrity": "박나래",
                "issue_type": "논란",
                "news_title": "...",
                "news_url": "...",
                "news_summary": "...",
                "silhouette_desc": "...",
                "hook_text": "...",
                "상태": "대기",
                "hash": "abc123..."
            },
            ...
        ]
    """
    all_items = []
    seen_hashes = set()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for feed_config in ENTERTAINMENT_RSS_FEEDS:
        feed_name = feed_config["name"]
        feed_url = feed_config["url"]

        print(f"[SHORTS] RSS 수집 중: {feed_name}")
        items = fetch_rss_feed(feed_url, max_items=max_per_feed)

        for item in items:
            title = item["title"]
            link = item["link"]
            summary = item.get("summary", "")

            # 연예인 이름 추출
            celebrity = extract_celebrity_name(title + " " + summary)
            if not celebrity:
                continue  # 연예인 이름 없으면 스킵

            # 중복 체크
            item_hash = compute_hash(celebrity + link)
            if item_hash in seen_hashes:
                continue
            seen_hashes.add(item_hash)

            # 이슈 유형 감지
            issue_type = detect_issue_type(title + " " + summary)

            # 실루엣 설명
            silhouette_desc = get_silhouette_description(celebrity)

            # 훅 문장
            hook_text = generate_hook_text(celebrity, issue_type, title)

            # 뉴스 요약
            news_summary = summarize_news(title, summary)

            all_items.append({
                "run_id": today,
                "celebrity": celebrity,
                "issue_type": issue_type,
                "news_title": title,
                "news_url": link,
                "news_summary": news_summary,
                "silhouette_desc": silhouette_desc,
                "hook_text": hook_text,
                "상태": "대기",
                "hash": item_hash,
            })

            if len(all_items) >= total_limit:
                break

        if len(all_items) >= total_limit:
            break

    print(f"[SHORTS] 총 {len(all_items)}개 연예 뉴스 수집 완료")
    return all_items


def search_celebrity_news(
    celebrity: str,
    max_items: int = 5
) -> List[Dict[str, Any]]:
    """
    특정 연예인 관련 뉴스 검색

    Args:
        celebrity: 연예인 이름
        max_items: 최대 반환 수

    Returns:
        수집된 뉴스 목록
    """
    query = f"{celebrity} 연예"
    url = google_news_rss_url(query)

    print(f"[SHORTS] '{celebrity}' 뉴스 검색 중...")
    items = fetch_rss_feed(url, max_items=max_items)

    results = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for item in items:
        title = item["title"]
        link = item["link"]
        summary = item.get("summary", "")

        issue_type = detect_issue_type(title + " " + summary)
        silhouette_desc = get_silhouette_description(celebrity)
        hook_text = generate_hook_text(celebrity, issue_type, title)
        news_summary = summarize_news(title, summary)

        results.append({
            "run_id": today,
            "celebrity": celebrity,
            "issue_type": issue_type,
            "news_title": title,
            "news_url": link,
            "news_summary": news_summary,
            "silhouette_desc": silhouette_desc,
            "hook_text": hook_text,
            "상태": "대기",
        })

    print(f"[SHORTS] '{celebrity}' 관련 {len(results)}개 뉴스 수집 완료")
    return results
