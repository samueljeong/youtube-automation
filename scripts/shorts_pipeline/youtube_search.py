"""
쇼츠 파이프라인 - YouTube 트렌딩 검색

YouTube Data API를 사용하여 트렌딩 쇼츠 검색 및 분석
+ Google News 연동으로 원본 자료 확보
"""

import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# feedparser (뉴스 검색용)
try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    feedparser = None
    FEEDPARSER_AVAILABLE = False

try:
    from dateutil import parser as dtparser
except ImportError:
    dtparser = None


# ========== Google News 검색 ==========

def search_google_news(
    query: str,
    max_results: int = 5,
    hours_ago: int = 72,
) -> List[Dict[str, Any]]:
    """
    Google News RSS로 관련 뉴스 기사 검색

    Args:
        query: 검색어 (예: "박나래 논란")
        max_results: 최대 결과 수
        hours_ago: 최근 몇 시간 이내 기사만

    Returns:
        [
            {
                "title": "기사 제목",
                "link": "https://...",
                "summary": "기사 요약",
                "published_at": "2025-12-28T...",
                "source": "연합뉴스",
            },
            ...
        ]
    """
    if not FEEDPARSER_AVAILABLE:
        print("[NEWS] feedparser 모듈 없음 - 뉴스 검색 불가")
        return []

    # Google News RSS URL
    q = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"

    print(f"[NEWS] '{query}' 뉴스 검색 중...")

    try:
        feed = feedparser.parse(url)
        entries = feed.entries[:max_results * 2]  # 필터링 여유분

        if not entries:
            print(f"[NEWS] '{query}' 관련 뉴스 없음")
            return []

        # 시간 필터
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        results = []

        for entry in entries:
            title = getattr(entry, "title", "")
            link = getattr(entry, "link", "")
            summary = getattr(entry, "summary", "")
            published = getattr(entry, "published", None)

            # 발행 시간 파싱
            published_at = None
            if published and dtparser:
                try:
                    published_at = dtparser.parse(published).astimezone(timezone.utc)
                except Exception:
                    pass

            # 시간 필터 적용
            if published_at and published_at < cutoff_time:
                continue

            # 출처 추출 (제목에서 " - 출처명" 형태)
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2:
                    title = parts[0].strip()
                    source = parts[1].strip()

            results.append({
                "title": title,
                "link": link,
                "summary": summary.replace("<b>", "").replace("</b>", ""),  # HTML 태그 제거
                "published_at": published_at.isoformat() if published_at else "",
                "source": source,
            })

            if len(results) >= max_results:
                break

        print(f"[NEWS] '{query}': {len(results)}개 기사 발견")
        return results

    except Exception as e:
        print(f"[NEWS] 뉴스 검색 실패: {e}")
        return []


def enrich_topic_with_news(topic: Dict[str, Any]) -> Dict[str, Any]:
    """
    YouTube 트렌딩 주제에 뉴스 기사 추가

    뉴스가 없으면 None 반환 (저장 스킵용)
    """
    person = topic.get("topic", "")
    issue = topic.get("issue", "")

    if not person:
        return None

    # 검색어 구성 (인물 + 이슈)
    if issue and issue not in ["소식", "트렌딩"]:
        search_query = f"{person} {issue}"
    else:
        search_query = person

    # 뉴스 검색
    news_articles = search_google_news(search_query, max_results=3, hours_ago=72)

    if not news_articles:
        # 인물 이름만으로 재검색
        news_articles = search_google_news(person, max_results=3, hours_ago=72)

    if not news_articles:
        print(f"[NEWS] ❌ '{person}' 관련 뉴스 없음 - 스킵")
        return None

    # 뉴스 정보 추가
    topic["news_articles"] = news_articles
    topic["primary_news"] = news_articles[0]  # 대표 기사

    print(f"[NEWS] ✅ '{person}': {len(news_articles)}개 뉴스 기사 연동")
    return topic


# ========== YouTube API ==========

def get_youtube_client():
    """YouTube Data API 클라이언트 생성"""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY 환경변수가 설정되지 않았습니다")

    return build("youtube", "v3", developerKey=api_key)


# 연예인/유명인 이름 DB (자주 등장하는 인물)
CELEBRITY_NAMES = {
    # 아이돌
    "뉴진스", "아이브", "에스파", "르세라핌", "카리나", "윈터", "지젤", "닝닝",
    "민지", "하니", "다니엘", "해린", "혜인", "장원영", "안유진", "레이",
    "사쿠라", "카즈하", "홍은채", "김채원", "허윤진", "BTS", "방탄소년단",
    "지민", "정국", "뷔", "슈가", "RM", "진", "제이홉", "블랙핑크", "제니",
    "지수", "로제", "리사", "트와이스", "나연", "정연", "모모", "사나", "지효",
    "미나", "다현", "채영", "쯔위", "스트레이키즈", "방찬", "리노", "창빈",
    "현진", "한", "필릭스", "승민", "아이엔", "세븐틴", "에스쿱스", "정한",
    "조슈아", "준", "호시", "원우", "우지", "디에잇", "민규", "도겸", "승관",
    "버논", "디노", "엔시티", "태용", "도영", "재현", "마크", "해찬", "쟈니",
    "유타", "텐", "루카스", "천러", "지성", "런쥔", "제노", "샤오쥔", "헨드리",

    # 배우
    "송혜교", "전지현", "김태희", "손예진", "공유", "현빈", "이민호", "김수현",
    "박서준", "송강", "차은우", "이도현", "변우석", "김지원", "신세경", "박민영",
    "한소희", "김유정", "아이유", "수지", "박보영", "김고은", "전소민", "이광수",
    "유재석", "강호동", "신동엽", "이효리", "비", "정우성", "이정재", "하정우",
    "마동석", "황정민", "조인성", "송중기", "박보검", "이종석", "남주혁", "공효진",

    # MC/개그맨
    "박나래", "이영지", "전현무", "김종국", "하하", "지석진", "양세찬", "송지효",
    "나영석", "조세호", "남창희", "김신영", "안영미", "장도연", "이은지", "문세윤",

    # 운동선수
    "손흥민", "김민재", "이강인", "황희찬", "오타니", "류현진", "김하성", "이정후",
    "박세리", "김연아", "임영웅", "영탁", "이찬원", "정동원",

    # 유튜버/인플루언서
    "침착맨", "주호민", "풍자", "쯔양", "먹방", "뻑가", "보겸", "대도서관",
}

# 제외할 일반 단어
COMMON_WORDS_BLACKLIST = {
    # 일반 단어
    "제발", "정말", "진짜", "하지만", "그래서", "때문", "오늘", "내일", "어제",
    "예전", "처럼", "같이", "함께", "우리", "나는", "너는", "이것", "저것",
    "여기", "저기", "지금", "나중", "먼저", "다음", "마지막", "처음", "결국",
    "아직", "벌써", "이미", "계속", "다시", "또", "더", "덜", "매우", "너무",
    "완전", "진심", "사실", "근데", "그냥", "일단", "혹시", "아마", "당연",
    # 쇼츠 관련
    "쇼츠", "shorts", "영상", "뉴스", "속보", "긴급", "단독", "최초", "공개",
    "반응", "리액션", "요약", "정리", "모음", "하이라이트", "예고", "티저",
    # 감정 표현
    "충격", "감동", "웃음", "눈물", "소름", "대박", "실화", "레전드", "미쳤",
}


def search_trending_shorts(
    query: str = "연예 뉴스",
    max_results: int = 20,
    hours_ago: int = 24,
    order: str = "viewCount",
    region_code: str = "KR",
) -> List[Dict[str, Any]]:
    """
    YouTube에서 트렌딩 쇼츠 검색

    Args:
        query: 검색어
        max_results: 최대 결과 수
        hours_ago: 몇 시간 이내 영상
        order: 정렬 기준 (viewCount, date, rating, relevance)
        region_code: 지역 코드

    Returns:
        [
            {
                "video_id": "...",
                "title": "...",
                "channel_title": "...",
                "published_at": "...",
                "view_count": 123456,
                "like_count": 1234,
                "comment_count": 56,
                "duration_seconds": 45,
                "thumbnail_url": "...",
            },
            ...
        ]
    """
    try:
        youtube = get_youtube_client()

        # 검색 시간 범위 설정
        published_after = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()

        print(f"[YouTube] 검색 중: '{query}' (최근 {hours_ago}시간, {order}순)")

        # 1단계: 검색
        search_response = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            videoDuration="short",  # Shorts (60초 이하)
            order=order,
            publishedAfter=published_after,
            regionCode=region_code,
            maxResults=max_results,
            relevanceLanguage="ko",
        ).execute()

        video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]

        if not video_ids:
            print("[YouTube] 검색 결과 없음")
            return []

        # 2단계: 비디오 상세 정보 조회
        videos_response = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(video_ids),
        ).execute()

        results = []
        for item in videos_response.get("items", []):
            video_id = item["id"]
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})
            content_details = item.get("contentDetails", {})

            # 영상 길이 파싱 (PT45S → 45초)
            duration_str = content_details.get("duration", "PT0S")
            duration_seconds = parse_duration(duration_str)

            # Shorts는 60초 이하만
            if duration_seconds > 60:
                continue

            results.append({
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "channel_id": snippet.get("channelId", ""),
                "published_at": snippet.get("publishedAt", ""),
                "description": snippet.get("description", ""),
                "view_count": int(statistics.get("viewCount", 0)),
                "like_count": int(statistics.get("likeCount", 0)),
                "comment_count": int(statistics.get("commentCount", 0)),
                "duration_seconds": duration_seconds,
                "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            })

        # 조회수순 정렬
        results.sort(key=lambda x: x["view_count"], reverse=True)

        print(f"[YouTube] {len(results)}개 쇼츠 발견")
        return results

    except HttpError as e:
        print(f"[YouTube] API 오류: {e}")
        return []
    except Exception as e:
        print(f"[YouTube] 검색 실패: {e}")
        return []


def parse_duration(duration_str: str) -> int:
    """
    ISO 8601 duration을 초로 변환
    PT45S → 45, PT1M30S → 90
    """
    match = re.match(r'PT(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if match:
        minutes = int(match.group(1) or 0)
        seconds = int(match.group(2) or 0)
        return minutes * 60 + seconds
    return 0


def calculate_engagement_score(video: Dict[str, Any]) -> float:
    """
    영상 참여도 점수 계산

    - 조회수 (40%): 0~100만 → 0~100점
    - 좋아요율 (30%): 좋아요/조회수 비율
    - 댓글수 (20%): 0~1000 → 0~100점
    - 신선도 (10%): 최근일수록 높음
    """
    views = video.get("view_count", 0)
    likes = video.get("like_count", 0)
    comments = video.get("comment_count", 0)
    published_at = video.get("published_at", "")

    # 조회수 점수 (0~100)
    view_score = min(views / 10000, 100)  # 100만 = 100점

    # 좋아요율 점수 (0~100)
    like_ratio = (likes / views * 100) if views > 0 else 0
    like_score = min(like_ratio * 10, 100)  # 10% = 100점

    # 댓글수 점수 (0~100)
    comment_score = min(comments / 10, 100)  # 1000개 = 100점

    # 신선도 점수 (0~100)
    recency_score = 100
    if published_at:
        try:
            pub_time = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            hours_old = (datetime.now(timezone.utc) - pub_time).total_seconds() / 3600
            recency_score = max(0, 100 - hours_old * 4)  # 24시간 후 0점
        except:
            pass

    # 가중 평균
    total = (
        view_score * 0.4 +
        like_score * 0.3 +
        comment_score * 0.2 +
        recency_score * 0.1
    )

    return round(total, 1)


def get_video_comments(
    video_id: str,
    max_results: int = 50,
) -> List[Dict[str, Any]]:
    """
    영상 댓글 가져오기

    Returns:
        [{"text": "...", "likes": 10, "author": "..."}, ...]
    """
    try:
        youtube = get_youtube_client()

        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            order="relevance",  # 인기 댓글 우선
            maxResults=max_results,
            textFormat="plainText",
        ).execute()

        comments = []
        for item in response.get("items", []):
            snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            comments.append({
                "text": snippet.get("textDisplay", ""),
                "likes": snippet.get("likeCount", 0),
                "author": snippet.get("authorDisplayName", ""),
                "published_at": snippet.get("publishedAt", ""),
            })

        return comments

    except HttpError as e:
        # 댓글 비활성화된 영상
        if "commentsDisabled" in str(e):
            print(f"[YouTube] 댓글 비활성화: {video_id}")
        else:
            print(f"[YouTube] 댓글 조회 실패: {e}")
        return []
    except Exception as e:
        print(f"[YouTube] 댓글 조회 오류: {e}")
        return []


def extract_celebrity_from_title(title: str) -> Optional[str]:
    """
    제목에서 연예인/유명인 이름 추출

    1. CELEBRITY_NAMES DB에서 매칭
    2. 없으면 한글 이름 패턴 + 블랙리스트 필터
    """
    # 1. DB에서 직접 매칭 (가장 정확)
    for name in CELEBRITY_NAMES:
        if name in title:
            return name

    # 2. 한글 이름 패턴 (3글자 성+이름 형태)
    # "김OO", "이OO", "박OO" 등 성씨로 시작하는 3글자
    korean_surnames = "김이박최정강조윤장임한오서신권황안송류홍"
    name_pattern = rf'([{korean_surnames}][가-힣]{{2}})(?:가|이|는|의|를|에게|측|씨|,|\s|$)'

    matches = re.findall(name_pattern, title)
    for name in matches:
        # 블랙리스트 체크
        if name not in COMMON_WORDS_BLACKLIST and len(name) >= 2:
            return name

    return None


def extract_trending_topics(videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    트렌딩 쇼츠에서 주제 추출 (연예인 중심)

    Returns:
        [
            {
                "topic": "박나래",
                "video_count": 5,
                "total_views": 1234567,
                "sample_videos": [...],
                "issue": "논란",
            },
            ...
        ]
    """
    from collections import defaultdict

    # 연예인별 영상 그룹화
    celebrity_videos = defaultdict(list)

    # 이슈 키워드
    issue_keywords = [
        "논란", "갑질", "폭로", "고백", "결혼", "이혼", "열애", "파혼",
        "컴백", "사과", "해명", "근황", "복귀", "은퇴", "탈퇴", "소식",
    ]

    for video in videos:
        title = video.get("title", "")

        # 연예인 이름 추출
        celebrity = extract_celebrity_from_title(title)

        if celebrity:
            # 이슈 키워드 추출
            found_issue = None
            for kw in issue_keywords:
                if kw in title:
                    found_issue = kw
                    break

            video["detected_celebrity"] = celebrity
            video["detected_issue"] = found_issue or "소식"
            celebrity_videos[celebrity].append(video)

    # 주제별 집계
    topics = []
    seen_video_ids = set()  # 중복 영상 방지

    for celebrity, vids in celebrity_videos.items():
        # 중복 영상 제거
        unique_vids = []
        for v in vids:
            vid = v.get("video_id")
            if vid and vid not in seen_video_ids:
                seen_video_ids.add(vid)
                unique_vids.append(v)

        if not unique_vids:
            continue

        # 가장 많이 나온 이슈 찾기
        issues = [v.get("detected_issue", "소식") for v in unique_vids]
        main_issue = max(set(issues), key=issues.count)

        topics.append({
            "topic": celebrity,
            "issue": main_issue,
            "video_count": len(unique_vids),
            "total_views": sum(v.get("view_count", 0) for v in unique_vids),
            "avg_engagement": sum(calculate_engagement_score(v) for v in unique_vids) / len(unique_vids),
            "sample_videos": unique_vids[:3],
        })

    # 연예인을 못 찾은 경우: 상위 영상을 제목 기준으로 추가
    if not topics and videos:
        for video in videos[:5]:
            vid = video.get("video_id")
            if vid in seen_video_ids:
                continue
            seen_video_ids.add(vid)

            title = video.get("title", "")
            # 제목 앞부분을 주제로 사용 (최대 15자)
            topic_name = title[:15].strip()
            if not topic_name:
                continue

            topics.append({
                "topic": topic_name,
                "issue": "트렌딩",
                "video_count": 1,
                "total_views": video.get("view_count", 0),
                "avg_engagement": calculate_engagement_score(video),
                "sample_videos": [video],
            })

    # 조회수순 정렬
    topics.sort(key=lambda x: x["total_views"], reverse=True)

    return topics[:10]  # 상위 10개


def search_shorts_by_category(
    category: str = "연예인",
    hours_ago: int = 24,
    max_results: int = 30,
) -> Dict[str, Any]:
    """
    카테고리별 트렌딩 쇼츠 검색 + 주제 분석

    Args:
        category: 연예인 / 운동선수 / 국뽕
        hours_ago: 검색 시간 범위
        max_results: 최대 결과 수

    Returns:
        {
            "videos": [...],
            "topics": [...],
            "best_topic": {...},
        }
    """
    # 카테고리별 검색어
    queries = {
        "연예인": ["연예 뉴스 쇼츠", "아이돌 근황", "연예인 논란"],
        "운동선수": ["스포츠 뉴스 쇼츠", "축구 선수", "야구 선수"],
        "국뽕": ["한국 자랑", "K-문화", "외국인 반응"],
    }

    category_queries = queries.get(category, queries["연예인"])

    all_videos = []
    seen_ids = set()

    for query in category_queries:
        videos = search_trending_shorts(
            query=query,
            max_results=max_results // len(category_queries),
            hours_ago=hours_ago,
        )

        for v in videos:
            if v["video_id"] not in seen_ids:
                v["engagement_score"] = calculate_engagement_score(v)
                all_videos.append(v)
                seen_ids.add(v["video_id"])

    # 참여도순 정렬
    all_videos.sort(key=lambda x: x["engagement_score"], reverse=True)

    # 주제 추출
    topics = extract_trending_topics(all_videos)

    return {
        "videos": all_videos,
        "topics": topics,
        "best_topic": topics[0] if topics else None,
        "category": category,
        "search_time": datetime.now(timezone.utc).isoformat(),
    }


def get_best_shorts_topic(
    categories: List[str] = None,
    min_engagement: float = 30,
) -> Optional[Dict[str, Any]]:
    """
    쇼츠 제작에 가장 적합한 트렌딩 주제 찾기

    Args:
        categories: 검색할 카테고리 (None이면 전체)
        min_engagement: 최소 참여도 점수

    Returns:
        {
            "topic": "박나래 갑질",
            "category": "연예인",
            "video_count": 5,
            "total_views": 1234567,
            "sample_videos": [...],
            "top_comments": [...],
        }
    """
    if categories is None:
        categories = ["연예인"]

    best_topic = None
    best_score = 0

    for category in categories:
        print(f"[YouTube] === {category} 카테고리 검색 ===")

        result = search_shorts_by_category(category=category)

        if result["best_topic"]:
            topic = result["best_topic"]
            score = topic["avg_engagement"]

            print(f"  🔥 {topic['topic']}: {topic['video_count']}개 영상, {topic['total_views']:,}회 조회")

            if score > best_score and score >= min_engagement:
                best_score = score
                best_topic = topic
                best_topic["category"] = category

                # 상위 영상의 댓글 수집
                if topic["sample_videos"]:
                    top_video = topic["sample_videos"][0]
                    comments = get_video_comments(top_video["video_id"], max_results=20)
                    best_topic["top_comments"] = comments[:10]

    if best_topic:
        print(f"[YouTube] ✅ 최적 주제: {best_topic['topic']} (참여도 {best_score:.1f})")
    else:
        print(f"[YouTube] ❌ 적합한 주제 없음 (최소 참여도 {min_engagement} 미달)")

    return best_topic


def youtube_to_news_format(topic: Dict[str, Any]) -> Dict[str, Any]:
    """
    YouTube 주제를 기존 뉴스 형식으로 변환
    (기존 파이프라인과 호환)

    topic에 news_articles가 있으면 뉴스 기사 정보도 포함
    """
    from datetime import datetime, timezone

    # 인물 이름 (topic이 이제 연예인 이름)
    person = topic.get("topic", "연예인")

    # 이슈 타입 (새로운 issue 필드 사용)
    issue_type = topic.get("issue", "근황")

    # 샘플 영상에서 정보 추출
    sample_videos = topic.get("sample_videos", [])
    best_video = sample_videos[0] if sample_videos else {}

    # 뉴스 기사 정보 (있는 경우)
    news_articles = topic.get("news_articles", [])
    primary_news = topic.get("primary_news", {})

    # 뉴스 제목 = 뉴스 기사 제목 우선, 없으면 인물 + 이슈
    if primary_news:
        news_title = primary_news.get("title", f"{person} {issue_type}")
        news_url = primary_news.get("link", "")
        news_summary = primary_news.get("summary", "")
        news_source = primary_news.get("source", "")
    else:
        news_title = f"{person} {issue_type}"
        news_url = f"https://youtube.com/watch?v={best_video.get('video_id', '')}" if best_video else ""
        news_summary = f"{topic.get('video_count', 0)}개 쇼츠, {topic.get('total_views', 0):,}회 조회"
        news_source = "YouTube"

    return {
        "run_id": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "category": topic.get("category", "연예인"),
        "person": person,
        "issue_type": issue_type,
        "news_title": news_title,
        "news_url": news_url,
        "news_summary": news_summary,
        "news_source": news_source,
        "viral_score": {
            "total_score": topic.get("avg_engagement", 0),
            "grade": get_grade(topic.get("avg_engagement", 0)),
            "view_score": topic.get("total_views", 0) / 10000,
            "comment_score": 0,
            "controversy_score": 0,
            "recency_score": 100,
        },
        "script_hints": {
            "debate_topic": f"{person} {issue_type} 관련 논쟁",
            "hot_phrases": [c.get("text", "")[:30] for c in topic.get("top_comments", [])[:5]],
            "pro_comments": [],
            "con_comments": [],
        },
        "youtube_source": {
            "topic": person,
            "issue": issue_type,
            "video_count": topic.get("video_count", 0),
            "total_views": topic.get("total_views", 0),
            "sample_videos": sample_videos,
        },
        "news_articles": news_articles,  # 전체 뉴스 기사 목록
        "상태": "준비",
    }


def get_grade(score: float) -> str:
    """점수를 등급으로 변환"""
    if score >= 80:
        return "S"
    elif score >= 60:
        return "A"
    elif score >= 40:
        return "B"
    elif score >= 20:
        return "C"
    return "D"


# CLI 테스트
if __name__ == "__main__":
    import json

    print("=== YouTube 트렌딩 쇼츠 검색 테스트 ===\n")

    # 연예 뉴스 검색
    result = search_shorts_by_category(category="연예인", hours_ago=48)

    print(f"\n📊 검색 결과: {len(result['videos'])}개 영상")
    print(f"📈 추출된 주제: {len(result['topics'])}개")

    if result["topics"]:
        print("\n🔥 상위 트렌딩 주제:")
        for i, topic in enumerate(result["topics"][:5], 1):
            print(f"  {i}. {topic['topic']}: {topic['video_count']}개 영상, {topic['total_views']:,}회")

    # 최적 주제 찾기
    print("\n" + "="*50)
    best = get_best_shorts_topic(categories=["연예인"])

    if best:
        # 뉴스 형식으로 변환
        news_format = youtube_to_news_format(best)
        print(f"\n📋 뉴스 형식 변환:")
        print(json.dumps(news_format, ensure_ascii=False, indent=2))
