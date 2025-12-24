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
    RSS_FEEDS,
    ENTERTAINMENT_RSS_FEEDS,
    ISSUE_TYPES,
    CELEBRITY_SILHOUETTES,
    ATHLETE_SILHOUETTES,
    KOREA_PRIDE_SILHOUETTES,
    CONTENT_CATEGORIES,
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
            # 일반 명사/방송 용어 필터링
            exclude = [
                # 직함/역할
                "대통령", "네티즌", "시청자", "팬들", "관계자", "매니저", "기자",
                # 방송 용어
                "드라마", "예능", "영화", "방송", "프로그램", "콘텐츠", "유튜브",
                "채널", "시즌", "에피소드", "무대", "앨범", "뮤직비디오",
                # 일반 명사
                "연예인", "아이돌", "배우", "가수", "코미디언", "개그맨",
                "선수", "감독", "코치", "심판",
                # 추상 명사
                "논란", "사건", "이슈", "문제", "상황", "결과", "영향",
                "도파민", "나락", "트렌드", "현상",
            ]
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


def get_silhouette_description(person: str, category: str = "연예인") -> str:
    """
    인물에 맞는 실루엣 설명 반환

    Args:
        person: 인물 이름
        category: 카테고리 (연예인/운동선수/국뽕)

    Returns:
        실루엣 프롬프트 설명 (영어)
    """
    # 1) 카테고리별 라이브러리 확인
    if category == "운동선수" and person in ATHLETE_SILHOUETTES:
        return ATHLETE_SILHOUETTES[person]
    elif category == "국뽕":
        return KOREA_PRIDE_SILHOUETTES.get("default", KOREA_PRIDE_SILHOUETTES["default"])
    elif person in CELEBRITY_SILHOUETTES:
        return CELEBRITY_SILHOUETTES[person]
    elif person in ATHLETE_SILHOUETTES:
        return ATHLETE_SILHOUETTES[person]

    # 2) 성별 추정 (간단한 휴리스틱)
    if person:
        # 여성에 많은 끝글자
        female_endings = ["희", "영", "경", "숙", "정", "연", "아", "이", "나", "라"]
        if person[-1] in female_endings:
            return CELEBRITY_SILHOUETTES.get("default_female", "female figure in casual standing pose")

    return CELEBRITY_SILHOUETTES.get("default_male", "male figure in casual standing pose")


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
    total_limit: int = 20,
    categories: List[str] = None
) -> List[Dict[str, Any]]:
    """
    뉴스 수집 메인 함수 (모든 카테고리 지원)

    Args:
        max_per_feed: 피드당 최대 수집 수
        total_limit: 전체 최대 수집 수
        categories: 수집할 카테고리 목록 (None이면 전체)

    Returns:
        [
            {
                "run_id": "2024-12-24",
                "category": "연예인",
                "person": "박나래",
                "issue_type": "논란",
                "news_title": "...",
                "news_url": "...",
                "news_summary": "...",
                "silhouette_desc": "...",
                "hook_text": "...",
                "상태": "",  # 빈 값 → 사용자가 "대기"로 변경 시 처리됨
            },
            ...
        ]
    """
    all_items = []
    seen_hashes = set()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 수집할 카테고리 결정
    if categories is None:
        categories = CONTENT_CATEGORIES  # ["연예인", "운동선수", "국뽕"]

    for category in categories:
        if category not in RSS_FEEDS:
            print(f"[SHORTS] 알 수 없는 카테고리: {category}")
            continue

        feeds = RSS_FEEDS[category]
        print(f"[SHORTS] === {category} 카테고리 수집 시작 ===")

        for feed_config in feeds:
            feed_name = feed_config["name"]
            feed_url = feed_config["url"]

            print(f"[SHORTS] RSS 수집 중: {feed_name}")
            items = fetch_rss_feed(feed_url, max_items=max_per_feed)

            for item in items:
                title = item["title"]
                link = item["link"]
                summary = item.get("summary", "")

                # 인물 이름 추출
                person = extract_celebrity_name(title + " " + summary)
                if not person:
                    continue  # 인물 이름 없으면 스킵

                # 중복 체크
                item_hash = compute_hash(person + link)
                if item_hash in seen_hashes:
                    continue
                seen_hashes.add(item_hash)

                # 이슈 유형 감지
                issue_type = detect_issue_type(title + " " + summary)

                # 실루엣 설명
                silhouette_desc = get_silhouette_description(person, category)

                # 훅 문장
                hook_text = generate_hook_text(person, issue_type, title)

                # 뉴스 요약
                news_summary = summarize_news(title, summary)

                all_items.append({
                    "run_id": today,
                    "category": category,        # ✅ 카테고리 추가
                    "person": person,            # ✅ celebrity → person
                    "issue_type": issue_type,
                    "news_title": title,
                    "news_url": link,
                    "news_summary": news_summary,
                    "silhouette_desc": silhouette_desc,
                    "hook_text": hook_text,
                    "상태": "",  # 빈 값 → 사용자가 "대기"로 변경 시 처리됨
                })

                if len(all_items) >= total_limit:
                    break

            if len(all_items) >= total_limit:
                break

        if len(all_items) >= total_limit:
            break

    print(f"[SHORTS] 총 {len(all_items)}개 뉴스 수집 완료")
    return all_items


def search_celebrity_news(
    person: str,
    category: str = "연예인",
    max_items: int = 5
) -> List[Dict[str, Any]]:
    """
    특정 인물 관련 뉴스 검색

    Args:
        person: 인물 이름
        category: 카테고리 (연예인/운동선수/국뽕)
        max_items: 최대 반환 수

    Returns:
        수집된 뉴스 목록
    """
    # 카테고리별 검색 쿼리
    if category == "운동선수":
        query = f"{person} 선수"
    elif category == "국뽕":
        query = f"{person} 한국"
    else:
        query = f"{person} 연예"

    url = google_news_rss_url(query)

    print(f"[SHORTS] '{person}' ({category}) 뉴스 검색 중...")
    items = fetch_rss_feed(url, max_items=max_items)

    results = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for item in items:
        title = item["title"]
        link = item["link"]
        summary = item.get("summary", "")

        issue_type = detect_issue_type(title + " " + summary)
        silhouette_desc = get_silhouette_description(person, category)
        hook_text = generate_hook_text(person, issue_type, title)
        news_summary = summarize_news(title, summary)

        results.append({
            "run_id": today,
            "category": category,        # ✅ 카테고리 추가
            "person": person,            # ✅ celebrity → person
            "issue_type": issue_type,
            "news_title": title,
            "news_url": link,
            "news_summary": news_summary,
            "silhouette_desc": silhouette_desc,
            "hook_text": hook_text,
            "상태": "",  # 빈 값 → 사용자가 "대기"로 변경 시 처리됨
        })

    print(f"[SHORTS] '{person}' 관련 {len(results)}개 뉴스 수집 완료")
    return results
