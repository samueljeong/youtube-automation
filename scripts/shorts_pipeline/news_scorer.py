"""
쇼츠 파이프라인 - 뉴스 바이럴 점수화 및 댓글 수집

기능:
1. 뉴스 바이럴 잠재력 점수화 (댓글 수, 반응, 논쟁성)
2. 네이버/다음 뉴스 댓글 크롤링
3. 찬/반 의견 분류
4. 대본에 반영할 핵심 표현 추출
5. Google News 리다이렉트 URL 해결
"""

import re
import requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, unquote
import json
import base64

# User-Agent 설정 (차단 방지)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


# ============================================================
# Google News URL 리다이렉트 해결
# ============================================================

def resolve_google_news_url(google_url: str, timeout: int = 10) -> Optional[str]:
    """
    Google News 리다이렉트 URL을 실제 뉴스 URL로 변환

    Google News RSS는 다음 형태의 URL을 반환:
    - https://news.google.com/rss/articles/CBMi...
    - https://news.google.com/articles/CBMi...

    이를 실제 네이버/다음 URL로 변환

    Args:
        google_url: Google News URL
        timeout: 요청 타임아웃

    Returns:
        실제 뉴스 URL (실패 시 None)
    """
    if not google_url:
        return None

    # 이미 실제 뉴스 URL인 경우
    if "naver.com" in google_url or "daum.net" in google_url:
        return google_url

    # Google News URL이 아닌 경우
    if "news.google.com" not in google_url:
        return google_url

    try:
        # 방법 1: Base64 디코딩 시도 (CBMi... 패턴)
        decoded_url = _decode_google_news_url(google_url)
        if decoded_url:
            print(f"[NewsScorer] URL 디코딩 성공: {decoded_url[:50]}...")
            return decoded_url

        # 방법 2: HTTP 리다이렉트 추적
        print(f"[NewsScorer] 리다이렉트 추적 중: {google_url[:50]}...")
        response = requests.head(
            google_url,
            headers=HEADERS,
            allow_redirects=True,
            timeout=timeout
        )
        final_url = response.url

        # Google URL에서 벗어났는지 확인
        if "news.google.com" not in final_url:
            print(f"[NewsScorer] 리다이렉트 성공: {final_url[:50]}...")
            return final_url

        # 방법 3: GET 요청으로 실제 페이지에서 추출
        response = requests.get(google_url, headers=HEADERS, timeout=timeout)
        # meta refresh나 canonical URL 추출 시도
        canonical_match = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', response.text)
        if canonical_match:
            return canonical_match.group(1)

        return google_url  # 실패 시 원본 반환

    except Exception as e:
        print(f"[NewsScorer] URL 해결 실패: {e}")
        return google_url


def _decode_google_news_url(url: str) -> Optional[str]:
    """
    Google News URL에서 Base64 인코딩된 실제 URL 추출

    URL 형식: .../articles/CBMiXXXXX... 또는 .../rss/articles/CBMiXXXXX...
    CBMi... 부분이 Base64 인코딩된 원본 URL
    """
    try:
        # articles/CBMi... 패턴 추출
        match = re.search(r'/articles/([A-Za-z0-9_-]+)', url)
        if not match:
            return None

        encoded = match.group(1)

        # Base64 패딩 추가
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += "=" * padding

        # URL-safe Base64 → 표준 Base64 변환
        encoded = encoded.replace("-", "+").replace("_", "/")

        # 디코딩
        decoded_bytes = base64.b64decode(encoded)

        # URL 추출 (protobuf 형식에서 URL 문자열 찾기)
        # URL은 보통 http:// 또는 https://로 시작
        decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
        url_match = re.search(r'https?://[^\s\x00-\x1f"\'<>]+', decoded_str)
        if url_match:
            return url_match.group(0)

        return None

    except Exception as e:
        # 디코딩 실패는 흔함 - 조용히 처리
        return None


# ============================================================
# 뉴스 바이럴 점수화
# ============================================================

def calculate_viral_score(
    comment_count: int,
    reaction_count: int,
    pro_ratio: float,  # 찬성 비율 (0~1)
    hours_ago: int,
    issue_type: str = "근황"
) -> Dict[str, Any]:
    """
    뉴스 바이럴 잠재력 점수 계산

    점수 = 댓글수(40%) + 반응수(30%) + 논쟁성(20%) + 신선도(10%)

    Args:
        comment_count: 댓글 수
        reaction_count: 반응 수 (좋아요 + 싫어요 등)
        pro_ratio: 찬성 비율 (0.5에 가까울수록 논쟁적)
        hours_ago: 뉴스 발행 후 경과 시간
        issue_type: 이슈 유형

    Returns:
        {
            "total_score": 85,
            "comment_score": 35,
            "reaction_score": 25,
            "controversy_score": 18,
            "freshness_score": 7,
            "grade": "A",
            "recommendation": "강력 추천"
        }
    """
    # 1. 댓글 점수 (40점 만점)
    # 1000개 이상 = 40점, 500개 = 30점, 100개 = 20점
    if comment_count >= 1000:
        comment_score = 40
    elif comment_count >= 500:
        comment_score = 30 + (comment_count - 500) / 50
    elif comment_count >= 100:
        comment_score = 20 + (comment_count - 100) / 40
    elif comment_count >= 50:
        comment_score = 10 + (comment_count - 50) / 5
    else:
        comment_score = comment_count / 5

    # 2. 반응 점수 (30점 만점)
    if reaction_count >= 10000:
        reaction_score = 30
    elif reaction_count >= 5000:
        reaction_score = 25 + (reaction_count - 5000) / 1000
    elif reaction_count >= 1000:
        reaction_score = 15 + (reaction_count - 1000) / 400
    else:
        reaction_score = reaction_count / 100 * 1.5

    # 3. 논쟁성 점수 (20점 만점)
    # 찬반 비율이 50:50에 가까울수록 높음
    controversy = 1 - abs(pro_ratio - 0.5) * 2  # 0~1 (0.5일 때 1)
    controversy_score = controversy * 20

    # 4. 신선도 점수 (10점 만점)
    # 6시간 이내 = 10점, 24시간 = 7점, 48시간 = 3점
    if hours_ago <= 6:
        freshness_score = 10
    elif hours_ago <= 24:
        freshness_score = 10 - (hours_ago - 6) / 6
    elif hours_ago <= 48:
        freshness_score = 7 - (hours_ago - 24) / 8
    else:
        freshness_score = max(0, 3 - (hours_ago - 48) / 24)

    # 5. 이슈 타입 보너스
    issue_bonus = {
        "논란": 10,
        "사건": 8,
        "열애": 5,
        "컴백": 3,
        "근황": 0,
    }
    bonus = issue_bonus.get(issue_type, 0)

    # 총점 계산
    total_score = min(100, comment_score + reaction_score + controversy_score + freshness_score + bonus)

    # 등급 판정
    if total_score >= 80:
        grade, recommendation = "S", "🔥 즉시 제작"
    elif total_score >= 60:
        grade, recommendation = "A", "✅ 강력 추천"
    elif total_score >= 40:
        grade, recommendation = "B", "👍 추천"
    elif total_score >= 20:
        grade, recommendation = "C", "⚠️ 보통"
    else:
        grade, recommendation = "D", "❌ 비추천"

    return {
        "total_score": round(total_score, 1),
        "comment_score": round(comment_score, 1),
        "reaction_score": round(reaction_score, 1),
        "controversy_score": round(controversy_score, 1),
        "freshness_score": round(freshness_score, 1),
        "bonus": bonus,
        "grade": grade,
        "recommendation": recommendation,
    }


# ============================================================
# 네이버 뉴스 댓글 크롤링
# ============================================================

def extract_naver_article_id(url: str) -> Optional[Tuple[str, str]]:
    """
    네이버 뉴스 URL에서 oid, aid 추출

    예: https://n.news.naver.com/article/001/0014123456
    → oid=001, aid=0014123456
    """
    # 패턴 1: n.news.naver.com/article/OID/AID
    match = re.search(r'n\.news\.naver\.com/article/(\d+)/(\d+)', url)
    if match:
        return match.group(1), match.group(2)

    # 패턴 2: news.naver.com/main/read.naver?...oid=...&aid=...
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if 'oid' in params and 'aid' in params:
        return params['oid'][0], params['aid'][0]

    return None


def fetch_naver_comments(
    url: str,
    max_comments: int = 20,
    sort: str = "RECOMMEND"  # RECOMMEND (공감순) or NEW (최신순)
) -> Dict[str, Any]:
    """
    네이버 뉴스 댓글 가져오기

    Args:
        url: 네이버 뉴스 URL
        max_comments: 최대 댓글 수
        sort: 정렬 방식 (RECOMMEND=공감순, NEW=최신순)

    Returns:
        {
            "success": True,
            "comment_count": 1234,
            "comments": [
                {
                    "text": "이건 진짜 선 넘었다",
                    "likes": 3200,
                    "dislikes": 150,
                    "sentiment": "negative",  # positive/negative/neutral
                },
                ...
            ],
            "pro_ratio": 0.45,  # 긍정 비율
            "top_keywords": ["갑질", "선넘었다", "실망"],
        }
    """
    article_ids = extract_naver_article_id(url)
    if not article_ids:
        return {"success": False, "error": "네이버 뉴스 URL이 아닙니다"}

    oid, aid = article_ids

    # 네이버 댓글 API
    api_url = f"https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json"
    params = {
        "ticket": "news",
        "templateId": "default_society",
        "pool": "cbox5",
        "lang": "ko",
        "country": "KR",
        "objectId": f"news{oid},{aid}",
        "pageSize": max_comments,
        "indexSize": 10,
        "groupId": "",
        "listType": "OBJECT",
        "pageType": "more",
        "page": 1,
        "refresh": "false",
        "sort": sort,
    }

    headers = HEADERS.copy()
    headers["Referer"] = url

    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=10)

        # JSONP 응답 파싱
        text = response.text
        # _callback( ... ) 형식에서 JSON 추출
        match = re.search(r'_callback\((.*)\)', text, re.DOTALL)
        if not match:
            # 순수 JSON인 경우
            data = response.json()
        else:
            data = json.loads(match.group(1))

        result = data.get("result", {})
        comment_list = result.get("commentList", [])
        total_count = result.get("count", {}).get("total", 0)

        comments = []
        positive_count = 0
        negative_count = 0
        all_text = []

        for c in comment_list:
            text = c.get("contents", "")
            likes = c.get("sympathyCount", 0)
            dislikes = c.get("antipathyCount", 0)

            # 감정 분석 (간단한 키워드 기반)
            sentiment = analyze_sentiment(text)
            if sentiment == "positive":
                positive_count += 1
            elif sentiment == "negative":
                negative_count += 1

            comments.append({
                "text": text,
                "likes": likes,
                "dislikes": dislikes,
                "sentiment": sentiment,
            })
            all_text.append(text)

        # 찬반 비율 계산
        total_sentiment = positive_count + negative_count
        pro_ratio = positive_count / total_sentiment if total_sentiment > 0 else 0.5

        # 주요 키워드 추출
        top_keywords = extract_top_keywords(" ".join(all_text))

        return {
            "success": True,
            "comment_count": total_count,
            "fetched_count": len(comments),
            "comments": comments,
            "pro_ratio": round(pro_ratio, 2),
            "top_keywords": top_keywords,
        }

    except Exception as e:
        print(f"[NewsScorer] 네이버 댓글 가져오기 실패: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# 다음 뉴스 댓글 크롤링
# ============================================================

def fetch_daum_comments(
    url: str,
    max_comments: int = 20
) -> Dict[str, Any]:
    """
    다음 뉴스 댓글 가져오기

    다음 뉴스 댓글 API 활용
    """
    # 다음 뉴스 기사 ID 추출
    match = re.search(r'/v/(\w+)', url)
    if not match:
        return {"success": False, "error": "다음 뉴스 URL이 아닙니다"}

    article_id = match.group(1)

    # 다음 댓글 API
    api_url = f"https://comment.daum.net/apis/v1/ui/single/main/@{article_id}"
    params = {
        "limit": max_comments,
        "sort": "POPULAR",  # POPULAR (인기순) or LATEST (최신순)
    }

    try:
        response = requests.get(api_url, params=params, headers=HEADERS, timeout=10)
        data = response.json()

        comment_list = data.get("commentList", [])
        total_count = data.get("totalCount", 0)

        comments = []
        positive_count = 0
        negative_count = 0
        all_text = []

        for c in comment_list:
            text = c.get("content", "")
            likes = c.get("likeCount", 0)
            dislikes = c.get("dislikeCount", 0)

            sentiment = analyze_sentiment(text)
            if sentiment == "positive":
                positive_count += 1
            elif sentiment == "negative":
                negative_count += 1

            comments.append({
                "text": text,
                "likes": likes,
                "dislikes": dislikes,
                "sentiment": sentiment,
            })
            all_text.append(text)

        total_sentiment = positive_count + negative_count
        pro_ratio = positive_count / total_sentiment if total_sentiment > 0 else 0.5
        top_keywords = extract_top_keywords(" ".join(all_text))

        return {
            "success": True,
            "comment_count": total_count,
            "fetched_count": len(comments),
            "comments": comments,
            "pro_ratio": round(pro_ratio, 2),
            "top_keywords": top_keywords,
        }

    except Exception as e:
        print(f"[NewsScorer] 다음 댓글 가져오기 실패: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# 감정 분석 및 키워드 추출
# ============================================================

def analyze_sentiment(text: str) -> str:
    """
    간단한 감정 분석 (키워드 기반)

    Returns: "positive", "negative", "neutral"
    """
    positive_words = [
        "좋아", "최고", "응원", "대박", "멋지", "잘했", "축하", "기대", "감동",
        "사랑", "행복", "웃기", "귀엽", "예쁘", "잘생", "존경", "화이팅",
    ]

    negative_words = [
        "싫어", "최악", "실망", "별로", "쓰레기", "쓰렉", "진짜", "선넘", "선 넘",
        "갑질", "학폭", "폭로", "비판", "논란", "혐오", "역겹", "짜증", "화나",
        "실화", "헐", "에휴", "한심", "어이없", "그만", "꺼져", "나가",
    ]

    text_lower = text.lower()

    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)

    if neg_count > pos_count:
        return "negative"
    elif pos_count > neg_count:
        return "positive"
    else:
        return "neutral"


def extract_top_keywords(text: str, top_n: int = 5) -> List[str]:
    """
    텍스트에서 주요 키워드 추출
    """
    # 불용어
    stopwords = {
        "이", "그", "저", "것", "수", "등", "더", "좀", "잘", "안", "못",
        "하다", "되다", "있다", "없다", "같다", "보다", "나다", "주다",
        "ㅋㅋ", "ㅎㅎ", "ㅠㅠ", "ㅜㅜ", "...", "???", "!!!",
    }

    # 2글자 이상 한글 단어 추출
    words = re.findall(r'[가-힣]{2,}', text)

    # 빈도 계산
    word_count = {}
    for word in words:
        if word not in stopwords and len(word) >= 2:
            word_count[word] = word_count.get(word, 0) + 1

    # 상위 N개
    sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
    return [w for w, c in sorted_words[:top_n]]


# ============================================================
# 댓글 기반 대본 힌트 생성
# ============================================================

def generate_script_hints(comments_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    수집된 댓글을 바탕으로 대본 작성 힌트 생성

    Returns:
        {
            "debate_topic": "갑질이다 vs 매니저가 예민하다",
            "pro_arguments": ["이건 선 넘었다", "사과해야 한다"],
            "con_arguments": ["매니저가 과민반응", "요즘 너무 예민"],
            "hot_phrases": ["선 넘었다", "이건 좀...", "실망이다"],
            "suggested_scene4": "댓글 보니까 '선 넘었다' vs '매니저가 예민' 완전 갈렸어. 너는 어느 쪽?",
        }
    """
    if not comments_data.get("success") or not comments_data.get("comments"):
        return {
            "debate_topic": None,
            "pro_arguments": [],
            "con_arguments": [],
            "hot_phrases": [],
            "suggested_scene4": None,
        }

    comments = comments_data["comments"]

    # 찬성/반대 의견 분류
    pro_arguments = []
    con_arguments = []
    hot_phrases = []

    for c in comments:
        text = c["text"]
        sentiment = c["sentiment"]
        likes = c.get("likes", 0)

        # 공감 높은 댓글에서 핵심 문구 추출
        if likes >= 100:
            # 짧은 문구 추출 (15자 이하)
            phrases = re.findall(r'[가-힣\s]{5,15}', text)
            for phrase in phrases[:2]:
                phrase = phrase.strip()
                if phrase and phrase not in hot_phrases:
                    hot_phrases.append(phrase)

        # 찬반 분류
        if sentiment == "negative":
            # 부정적 = 비판 (당사자에게)
            short_text = text[:30] + "..." if len(text) > 30 else text
            if short_text not in pro_arguments:
                pro_arguments.append(short_text)
        elif sentiment == "positive":
            # 긍정적 = 옹호
            short_text = text[:30] + "..." if len(text) > 30 else text
            if short_text not in con_arguments:
                con_arguments.append(short_text)

    # 상위 3개만
    pro_arguments = pro_arguments[:3]
    con_arguments = con_arguments[:3]
    hot_phrases = hot_phrases[:5]

    # 논쟁 주제 생성
    keywords = comments_data.get("top_keywords", [])
    if keywords:
        debate_topic = f"'{keywords[0]}' 논란, 어떻게 생각해?"
    else:
        debate_topic = None

    # 씬4 제안
    if hot_phrases:
        suggested_scene4 = f"댓글 보니까 '{hot_phrases[0]}' 말 많더라. 너는 어떻게 생각해? 댓글로."
    else:
        suggested_scene4 = None

    return {
        "debate_topic": debate_topic,
        "pro_arguments": pro_arguments,
        "con_arguments": con_arguments,
        "hot_phrases": hot_phrases,
        "suggested_scene4": suggested_scene4,
    }


# ============================================================
# 통합 함수: 뉴스 분석
# ============================================================

def analyze_news_viral_potential(
    url: str,
    issue_type: str = "근황",
    hours_ago: int = 12
) -> Dict[str, Any]:
    """
    뉴스 바이럴 잠재력 종합 분석

    Args:
        url: 뉴스 URL (Google News, 네이버, 다음 모두 지원)
        issue_type: 이슈 유형
        hours_ago: 뉴스 발행 후 경과 시간

    Returns:
        {
            "viral_score": {...},
            "comments_data": {...},
            "script_hints": {...},
            "resolved_url": "실제 뉴스 URL"
        }
    """
    print(f"[NewsScorer] 뉴스 분석 시작: {url[:50]}...")

    # 1) Google News URL인 경우 실제 URL로 해결
    resolved_url = url
    if "news.google.com" in url:
        resolved_url = resolve_google_news_url(url) or url
        if resolved_url != url:
            print(f"[NewsScorer] 실제 URL: {resolved_url[:50]}...")

    # 2) 뉴스 소스 판별 및 댓글 수집
    if "naver.com" in resolved_url or "n.news.naver.com" in resolved_url:
        comments_data = fetch_naver_comments(resolved_url)
    elif "daum.net" in resolved_url or "v.daum.net" in resolved_url:
        comments_data = fetch_daum_comments(resolved_url)
    else:
        # 기타 소스 (연합뉴스, 조선일보 등) - 댓글 없음
        comments_data = {"success": False, "error": f"댓글 미지원 소스: {urlparse(resolved_url).netloc}"}

    # 댓글 데이터 기반 점수 계산
    if comments_data.get("success"):
        comment_count = comments_data.get("comment_count", 0)
        pro_ratio = comments_data.get("pro_ratio", 0.5)
        # 반응 수는 댓글의 좋아요 합계로 추정
        reaction_count = sum(c.get("likes", 0) for c in comments_data.get("comments", []))
    else:
        comment_count = 0
        pro_ratio = 0.5
        reaction_count = 0

    # 바이럴 점수 계산
    viral_score = calculate_viral_score(
        comment_count=comment_count,
        reaction_count=reaction_count,
        pro_ratio=pro_ratio,
        hours_ago=hours_ago,
        issue_type=issue_type,
    )

    # 대본 힌트 생성
    script_hints = generate_script_hints(comments_data)

    print(f"[NewsScorer] 분석 완료: 점수={viral_score['total_score']}, 등급={viral_score['grade']}")

    return {
        "viral_score": viral_score,
        "comments_data": comments_data,
        "script_hints": script_hints,
        "resolved_url": resolved_url,
    }


# ============================================================
# 뉴스 목록 점수화 및 정렬
# ============================================================

def rank_news_by_viral_potential(
    news_items: List[Dict[str, Any]],
    min_score: float = 30,
    top_n: int = 10
) -> List[Dict[str, Any]]:
    """
    뉴스 목록을 바이럴 잠재력 순으로 정렬

    Args:
        news_items: 뉴스 목록 (news_collector에서 수집된 형식)
        min_score: 최소 점수 (이하는 제외)
        top_n: 상위 N개만 반환

    Returns:
        점수순 정렬된 뉴스 목록 (viral_score, script_hints 추가됨)
    """
    scored_items = []

    for item in news_items:
        url = item.get("news_url", "")
        issue_type = item.get("issue_type", "근황")

        # 분석 수행
        analysis = analyze_news_viral_potential(url, issue_type)

        # 결과 병합
        item_with_score = item.copy()
        item_with_score["viral_score"] = analysis["viral_score"]
        item_with_score["script_hints"] = analysis["script_hints"]
        item_with_score["comments_summary"] = {
            "count": analysis["comments_data"].get("comment_count", 0),
            "top_keywords": analysis["comments_data"].get("top_keywords", []),
            "pro_ratio": analysis["comments_data"].get("pro_ratio", 0.5),
        }

        # 최소 점수 이상만 포함
        if analysis["viral_score"]["total_score"] >= min_score:
            scored_items.append(item_with_score)

    # 점수순 정렬
    scored_items.sort(key=lambda x: x["viral_score"]["total_score"], reverse=True)

    return scored_items[:top_n]
