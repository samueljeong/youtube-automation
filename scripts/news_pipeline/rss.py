"""
RSS 피드 수집
"""

from datetime import datetime, timezone

from .config import NEWS_FEEDS, google_news_rss_url
from .utils import normalize_text, compute_hash

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from dateutil import parser as dtparser
except ImportError:
    dtparser = None


def ingest_rss_feeds(max_per_feed: int = 30) -> tuple[list, list]:
    """
    RSS 피드에서 기사 수집 (공용)

    반환: (raw_rows, items)
    - raw_rows: RAW_FEED 시트용 행 데이터
    - items: 후보 선정용 딕셔너리 리스트
    """
    if not feedparser:
        print("[NEWS] feedparser 모듈이 설치되지 않음")
        return [], []

    now = datetime.now(timezone.utc)
    raw_rows = []
    items = []

    for feed_name, query in NEWS_FEEDS:
        url = google_news_rss_url(query)
        print(f"[NEWS] 피드 수집 중: {feed_name}")

        try:
            d = feedparser.parse(url)
            entries = d.entries[:max_per_feed]
            print(f"[NEWS] {feed_name}: {len(entries)}개 기사 발견")

            for e in entries:
                title = normalize_text(getattr(e, "title", ""))
                link = getattr(e, "link", "")
                summary = normalize_text(getattr(e, "summary", ""))
                published = getattr(e, "published", None) or getattr(e, "updated", None)

                published_at = ""
                if published and dtparser:
                    try:
                        published_at = dtparser.parse(published).astimezone(timezone.utc).isoformat()
                    except Exception:
                        pass

                h = compute_hash(title, link)

                # 주요 키워드 추출
                hit_keywords = []
                for kw in ["금리", "대출", "연금", "세금", "건보", "부동산", "환율", "물가"]:
                    if kw in (title + summary):
                        hit_keywords.append(kw)
                kw_hit = "|".join(hit_keywords)

                raw_rows.append([
                    now.isoformat(),
                    "google_news_rss",
                    feed_name,
                    title,
                    link,
                    published_at,
                    summary,
                    kw_hit,
                    h
                ])

                items.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "published_at": published_at,
                    "hash": h,
                    "feed_name": feed_name,
                })

        except Exception as e:
            print(f"[NEWS] {feed_name} 수집 실패: {e}")

    print(f"[NEWS] 총 {len(items)}개 기사 수집 완료")
    return raw_rows, items


def deduplicate_items(items: list) -> list:
    """해시 기반 중복 제거"""
    seen = set()
    unique = []

    for item in items:
        if item["hash"] not in seen:
            seen.add(item["hash"])
            unique.append(item)

    print(f"[NEWS] 중복 제거: {len(items)} → {len(unique)}개")
    return unique
