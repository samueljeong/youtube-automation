"""
쇼츠 파이프라인 - YouTube 트렌딩 검색

YouTube Data API를 사용하여 트렌딩 쇼츠 검색 및 분석
"""

import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def get_youtube_client():
    """YouTube Data API 클라이언트 생성"""
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY 환경변수가 설정되지 않았습니다")

    return build("youtube", "v3", developerKey=api_key)


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


def extract_trending_topics(videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    트렌딩 쇼츠에서 주제 추출

    Returns:
        [
            {
                "topic": "박나래 갑질",
                "video_count": 5,
                "total_views": 1234567,
                "sample_videos": [...],
                "keywords": ["갑질", "논란"],
            },
            ...
        ]
    """
    from collections import defaultdict

    # 키워드 빈도 분석
    keyword_videos = defaultdict(list)

    # 연예인 이름 패턴
    name_pattern = r'([가-힣]{2,4})(?:가|이|는|의|를|에게|측|씨|,|\s)'

    # 이슈 키워드
    issue_keywords = [
        "논란", "갑질", "폭로", "고백", "결혼", "이혼", "열애", "파혼",
        "컴백", "사과", "해명", "충격", "근황", "복귀", "은퇴", "탈퇴",
    ]

    for video in videos:
        title = video.get("title", "")

        # 연예인 이름 추출
        names = re.findall(name_pattern, title)

        # 이슈 키워드 추출
        found_issues = [kw for kw in issue_keywords if kw in title]

        # 조합 (이름 + 이슈)
        for name in names:
            if len(name) >= 2:
                for issue in found_issues:
                    topic = f"{name} {issue}"
                    keyword_videos[topic].append(video)

                # 이름만도 추가
                keyword_videos[name].append(video)

    # 주제별 집계
    topics = []
    for topic, vids in keyword_videos.items():
        if len(vids) >= 1:  # 1개 이상이면 포함 (기존: 2개)
            topics.append({
                "topic": topic,
                "video_count": len(vids),
                "total_views": sum(v.get("view_count", 0) for v in vids),
                "avg_engagement": sum(calculate_engagement_score(v) for v in vids) / len(vids),
                "sample_videos": vids[:3],
            })

    # 주제가 없으면 상위 영상을 개별 주제로 추가
    if not topics and videos:
        for video in videos[:5]:
            title = video.get("title", "")
            # 제목에서 첫 번째 한글 이름 추출 시도
            names = re.findall(r'([가-힣]{2,4})', title)
            topic_name = names[0] if names else title[:20]

            topics.append({
                "topic": topic_name,
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
    """
    from datetime import datetime, timezone

    # 인물 이름 추출
    person = topic.get("topic", "").split()[0] if topic.get("topic") else "연예인"

    # 이슈 타입 추출
    issue_keywords = {
        "논란": "논란", "갑질": "논란", "폭로": "논란",
        "열애": "열애", "결혼": "열애", "이혼": "열애",
        "컴백": "컴백", "신곡": "컴백",
        "근황": "근황", "복귀": "근황",
    }

    issue_type = "근황"
    topic_text = topic.get("topic", "")
    for kw, issue in issue_keywords.items():
        if kw in topic_text:
            issue_type = issue
            break

    # 샘플 영상에서 정보 추출
    sample_videos = topic.get("sample_videos", [])
    best_video = sample_videos[0] if sample_videos else {}

    return {
        "run_id": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "category": topic.get("category", "연예인"),
        "person": person,
        "issue_type": issue_type,
        "news_title": topic.get("topic", "트렌딩 주제"),
        "news_url": f"https://youtube.com/watch?v={best_video.get('video_id', '')}" if best_video else "",
        "news_summary": f"{topic.get('video_count', 0)}개 쇼츠, {topic.get('total_views', 0):,}회 조회",
        "viral_score": {
            "total_score": topic.get("avg_engagement", 0),
            "grade": get_grade(topic.get("avg_engagement", 0)),
            "view_score": topic.get("total_views", 0) / 10000,
            "comment_score": 0,
            "controversy_score": 0,
            "recency_score": 100,
        },
        "script_hints": {
            "debate_topic": f"{person} 관련 논쟁",
            "hot_phrases": [c.get("text", "")[:30] for c in topic.get("top_comments", [])[:5]],
            "pro_comments": [],
            "con_comments": [],
        },
        "youtube_source": {
            "topic": topic.get("topic"),
            "video_count": topic.get("video_count", 0),
            "total_views": topic.get("total_views", 0),
            "sample_videos": sample_videos,
        },
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
