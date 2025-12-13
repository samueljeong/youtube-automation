"""
TubeLens Server - YouTube Analytics Tool
YouTube Data API v3를 사용한 영상 분석 도구
"""

from flask import Blueprint, render_template, request, jsonify
import os
import re
import math
import subprocess
import tempfile
import base64
import json
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import requests
import google.generativeai as genai
from openai import OpenAI

tubelens_bp = Blueprint('tubelens', __name__)

# YouTube Data API Base URL
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def get_youtube_api_key() -> Optional[str]:
    """환경 변수에서 YouTube API 키 가져오기"""
    return os.getenv("YOUTUBE_API_KEY")


def make_youtube_request(endpoint: str, params: Dict[str, Any], api_key: str = None) -> Dict[str, Any]:
    """YouTube API 요청 수행"""
    if not api_key:
        api_key = get_youtube_api_key()

    if not api_key:
        raise ValueError("YouTube API 키가 설정되지 않았습니다.")

    params['key'] = api_key
    url = f"{YOUTUBE_API_BASE}/{endpoint}"

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    return response.json()


def parse_duration(duration: str) -> int:
    """ISO 8601 duration을 초로 변환 (PT4M13S -> 253)"""
    if not duration:
        return 0

    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return 0

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    return hours * 3600 + minutes * 60 + seconds


def format_duration(seconds: int) -> str:
    """초를 MM:SS 또는 HH:MM:SS 형식으로 변환"""
    if seconds < 3600:
        return f"{seconds // 60}:{seconds % 60:02d}"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"


def format_number(num: int) -> str:
    """숫자를 한국어 형식으로 변환 (1000 -> 1천)"""
    if num >= 100000000:
        return f"{num / 100000000:.1f}억"
    elif num >= 10000:
        return f"{num / 10000:.1f}만"
    elif num >= 1000:
        return f"{num / 1000:.1f}천"
    return str(num)


def calculate_cii(view_count: int, subscriber_count: int, like_count: int, comment_count: int) -> Dict[str, Any]:
    """CII (Channel Impact Index) 계산"""
    if subscriber_count == 0:
        subscriber_count = 1

    # 채널 기여도: 조회수 / 구독자수 * 100
    contribution_value = (view_count / subscriber_count) * 100

    # 성과도 배율: 조회수 / 구독자수
    performance_value = view_count / subscriber_count

    # 참여율: (좋아요 + 댓글) / 조회수 * 100
    engagement_rate = 0
    if view_count > 0:
        engagement_rate = ((like_count + comment_count) / view_count) * 100

    # CII 점수 계산
    cii_score = min(100, (contribution_value * 0.4 + performance_value * 30 + engagement_rate * 10))

    # CII 등급 결정
    if cii_score >= 80:
        cii_grade = "Great!!"
    elif cii_score >= 60:
        cii_grade = "Good"
    elif cii_score >= 40:
        cii_grade = "Soso"
    elif cii_score >= 20:
        cii_grade = "Not bad"
    else:
        cii_grade = "Bad"

    return {
        "contributionValue": round(contribution_value, 2),
        "performanceValue": round(performance_value, 2),
        "engagementRate": round(engagement_rate, 4),
        "ciiScore": round(cii_score, 2),
        "cii": cii_grade
    }


def get_time_filter(time_frame: str) -> Optional[str]:
    """시간 필터 계산"""
    if not time_frame or time_frame == "":
        return None

    now = datetime.utcnow()

    time_deltas = {
        "hour": timedelta(hours=1),
        "day": timedelta(days=1),
        "week": timedelta(weeks=1),
        "month": timedelta(days=30),
        "3months": timedelta(days=90),
        "6months": timedelta(days=180),
        "year": timedelta(days=365),
    }

    if time_frame in time_deltas:
        published_after = now - time_deltas[time_frame]
        return published_after.strftime("%Y-%m-%dT%H:%M:%SZ")

    return None


def extract_video_id(url: str) -> Optional[str]:
    """YouTube URL에서 비디오 ID 추출"""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
        r'(?:shorts/)([a-zA-Z0-9_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    # URL이 아닌 ID 자체인 경우
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
        return url

    return None


def extract_channel_id(url: str) -> Optional[str]:
    """YouTube URL에서 채널 ID 추출"""
    patterns = [
        r'(?:channel/)([a-zA-Z0-9_-]+)',
        r'(?:user/)([a-zA-Z0-9_-]+)',
        r'(?:c/)([a-zA-Z0-9_-]+)',
        r'(?:@)([a-zA-Z0-9_-]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def get_channel_info(channel_id: str, api_key: str) -> Dict[str, Any]:
    """채널 정보 가져오기"""
    try:
        data = make_youtube_request("channels", {
            "id": channel_id,
            "part": "snippet,statistics,contentDetails"
        }, api_key)

        if not data.get("items"):
            return {}

        item = data["items"][0]
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        content_details = item.get("contentDetails", {})

        return {
            "channelId": channel_id,
            "channelTitle": snippet.get("title", ""),
            "subscriberCount": int(statistics.get("subscriberCount", 0)),
            "videoCount": int(statistics.get("videoCount", 0)),
            "viewCount": int(statistics.get("viewCount", 0)),
            "uploadPlaylist": content_details.get("relatedPlaylists", {}).get("uploads", ""),
            "thumbnailUrl": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            "description": snippet.get("description", ""),
            "country": snippet.get("country", ""),
            "publishedAt": snippet.get("publishedAt", ""),
        }
    except Exception as e:
        print(f"채널 정보 가져오기 실패: {e}")
        return {}


def get_video_details(video_ids: List[str], api_key: str) -> List[Dict[str, Any]]:
    """비디오 상세 정보 가져오기 (채널 정보 배치 처리로 최적화)"""
    if not video_ids:
        return []

    # 1단계: 비디오 정보 50개씩 배치로 수집
    video_items = []
    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i+50]
        try:
            data = make_youtube_request("videos", {
                "id": ",".join(batch_ids),
                "part": "snippet,statistics,contentDetails"
            }, api_key)
            video_items.extend(data.get("items", []))
        except Exception as e:
            print(f"비디오 상세 정보 가져오기 실패: {e}")

    # 2단계: 모든 고유 채널 ID 수집
    channel_ids = list(set([
        item.get("snippet", {}).get("channelId", "")
        for item in video_items
        if item.get("snippet", {}).get("channelId")
    ]))

    # 3단계: 채널 정보 배치로 가져오기 (N+1 문제 해결)
    channel_map = {}
    for i in range(0, len(channel_ids), 50):
        batch_channel_ids = channel_ids[i:i+50]
        try:
            channels_data = make_youtube_request("channels", {
                "part": "statistics",
                "id": ",".join(batch_channel_ids)
            }, api_key)
            for ch in channels_data.get("items", []):
                channel_map[ch["id"]] = {
                    "subscriberCount": int(ch["statistics"].get("subscriberCount", 0)),
                    "videoCount": int(ch["statistics"].get("videoCount", 0))
                }
        except Exception as e:
            print(f"채널 정보 배치 가져오기 실패: {e}")

    # 4단계: 비디오 데이터 조합
    all_videos = []
    for item in video_items:
        video_id = item.get("id")
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        content_details = item.get("contentDetails", {})

        channel_id = snippet.get("channelId", "")
        channel_info = channel_map.get(channel_id, {"subscriberCount": 0, "videoCount": 0})

        duration_seconds = parse_duration(content_details.get("duration", ""))
        published_at = snippet.get("publishedAt", "")

        view_count = int(statistics.get("viewCount", 0))
        like_count = int(statistics.get("likeCount", 0))
        comment_count = int(statistics.get("commentCount", 0))
        subscriber_count = channel_info.get("subscriberCount", 0)

        cii_data = calculate_cii(view_count, subscriber_count, like_count, comment_count)

        all_videos.append({
            "videoId": video_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            "channelId": channel_id,
            "channelTitle": snippet.get("channelTitle", ""),
            "publishedAt": published_at[:10] if published_at else "",
            "publishedAtRaw": published_at,
            "duration": format_duration(duration_seconds),
            "durationSeconds": duration_seconds,
            "viewCount": view_count,
            "likeCount": like_count,
            "commentCount": comment_count,
            "subscriberCount": subscriber_count,
            "totalVideos": channel_info.get("videoCount", 0),
            "categoryId": snippet.get("categoryId", ""),
            **cii_data
        })

    return all_videos


# ===== API 라우트 =====

@tubelens_bp.route('/tubelens')
def tubelens_page():
    """TubeLens 메인 페이지"""
    return render_template('tubelens.html')


@tubelens_bp.route('/api/tubelens/search', methods=['POST'])
def api_search():
    """키워드로 영상 검색"""
    try:
        data = request.get_json()

        keyword = data.get("keyword", "")
        max_results = min(int(data.get("maxResults", 50)), 500)
        time_frame = data.get("timeFrame", "")
        region_code = data.get("regionCode", "KR")
        video_type = data.get("videoType", "all")
        is_views_sort = data.get("isViewsSort", True)
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 검색 파라미터 설정
        search_params = {
            "part": "snippet",
            "type": "video",
            "maxResults": min(max_results, 50),
            "regionCode": region_code,
            "order": "viewCount" if is_views_sort else "date",
        }

        if keyword:
            search_params["q"] = keyword

        # 시간 필터
        published_after = get_time_filter(time_frame)
        if published_after:
            search_params["publishedAfter"] = published_after

        # 커스텀 날짜 필터
        if time_frame == "custom":
            start_date = data.get("startDate")
            end_date = data.get("endDate")
            if start_date:
                search_params["publishedAfter"] = f"{start_date}T00:00:00Z"
            if end_date:
                search_params["publishedBefore"] = f"{end_date}T23:59:59Z"

        # 영상 타입 필터 (쇼츠/롱폼)
        if video_type == "shorts":
            search_params["videoDuration"] = "short"
        elif video_type.startswith("longform"):
            search_params["videoDuration"] = "medium"

        # 검색 실행 (페이지네이션으로 최대 max_results까지)
        all_video_ids = []
        next_page_token = None

        while len(all_video_ids) < max_results:
            if next_page_token:
                search_params["pageToken"] = next_page_token

            search_data = make_youtube_request("search", search_params, api_key)

            video_ids = [
                item["id"]["videoId"]
                for item in search_data.get("items", [])
                if item.get("id", {}).get("videoId")
            ]
            all_video_ids.extend(video_ids)

            next_page_token = search_data.get("nextPageToken")
            if not next_page_token:
                break

        # 비디오 상세 정보 가져오기
        videos = get_video_details(all_video_ids[:max_results], api_key)

        # 영상 길이 필터링
        if video_type == "shorts":
            videos = [v for v in videos if v["durationSeconds"] <= 60]
        elif video_type == "longform_4_20":
            videos = [v for v in videos if 240 <= v["durationSeconds"] <= 1200]
        elif video_type == "longform_20_plus":
            videos = [v for v in videos if v["durationSeconds"] > 1200]

        # 인덱스 추가
        for i, video in enumerate(videos):
            video["index"] = i + 1

        return jsonify({
            "success": True,
            "data": videos,
            "message": f"{len(videos)}개 영상을 찾았습니다."
        })

    except Exception as e:
        print(f"검색 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/analyze', methods=['POST'])
def api_analyze():
    """URL로 영상/채널 분석"""
    try:
        data = request.get_json()
        url = data.get("url", "")
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 비디오 ID 추출 시도
        video_id = extract_video_id(url)
        if video_id:
            videos = get_video_details([video_id], api_key)
            if videos:
                videos[0]["index"] = 1
                return jsonify({
                    "success": True,
                    "data": videos,
                    "message": "영상 분석 완료"
                })

        # 채널 ID 추출 시도
        channel_id = extract_channel_id(url)
        if channel_id:
            # 채널 핸들(@username)인 경우 실제 채널 ID 조회
            if not channel_id.startswith("UC"):
                search_data = make_youtube_request("search", {
                    "part": "snippet",
                    "type": "channel",
                    "q": channel_id,
                    "maxResults": 1
                }, api_key)

                if search_data.get("items"):
                    channel_id = search_data["items"][0]["id"]["channelId"]

            channel_info = get_channel_info(channel_id, api_key)
            if channel_info:
                return jsonify({
                    "success": True,
                    "data": [channel_info],
                    "type": "channel",
                    "message": "채널 분석 완료"
                })

        return jsonify({"success": False, "message": "유효한 YouTube URL이 아닙니다."}), 400

    except Exception as e:
        print(f"분석 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/channel-search', methods=['POST'])
def api_channel_search():
    """채널 검색"""
    try:
        data = request.get_json()
        channel_name = data.get("channelName", "")
        region_code = data.get("regionCode", "KR")
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        if not channel_name:
            return jsonify({"success": False, "message": "채널명을 입력해주세요."}), 400

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 채널 검색
        search_data = make_youtube_request("search", {
            "part": "snippet",
            "type": "channel",
            "q": channel_name,
            "maxResults": 10,
            "regionCode": region_code
        }, api_key)

        channels = []
        for item in search_data.get("items", []):
            channel_id = item["id"]["channelId"]
            channel_info = get_channel_info(channel_id, api_key)

            if channel_info:
                # 정확 일치 여부 확인
                is_exact_match = channel_info["channelTitle"].lower() == channel_name.lower()
                channel_info["isExactMatch"] = is_exact_match
                channels.append(channel_info)

        # 정확 일치 먼저, 그 다음 구독자 수 순
        channels.sort(key=lambda x: (-x.get("isExactMatch", False), -x.get("subscriberCount", 0)))

        return jsonify({
            "success": True,
            "data": channels,
            "message": f"{len(channels)}개 채널을 찾았습니다."
        })

    except Exception as e:
        print(f"채널 검색 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/channel-videos', methods=['POST'])
def api_channel_videos():
    """채널의 영상 목록 가져오기"""
    try:
        data = request.get_json()
        channel_id = data.get("channelId", "")
        upload_playlist = data.get("uploadPlaylist", "")
        max_results = min(int(data.get("maxResults", 50)), 500)
        video_type = data.get("videoType", "all")
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        if not channel_id:
            return jsonify({"success": False, "message": "채널 ID가 필요합니다."}), 400

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 업로드 플레이리스트 ID가 없으면 채널 정보에서 가져오기
        if not upload_playlist:
            channel_info = get_channel_info(channel_id, api_key)
            upload_playlist = channel_info.get("uploadPlaylist", "")

        if not upload_playlist:
            return jsonify({"success": False, "message": "업로드 플레이리스트를 찾을 수 없습니다."}), 400

        # 플레이리스트에서 영상 ID 가져오기
        all_video_ids = []
        next_page_token = None

        while len(all_video_ids) < max_results:
            params = {
                "part": "contentDetails",
                "playlistId": upload_playlist,
                "maxResults": 50
            }

            if next_page_token:
                params["pageToken"] = next_page_token

            playlist_data = make_youtube_request("playlistItems", params, api_key)

            video_ids = [
                item["contentDetails"]["videoId"]
                for item in playlist_data.get("items", [])
            ]
            all_video_ids.extend(video_ids)

            next_page_token = playlist_data.get("nextPageToken")
            if not next_page_token:
                break

        # 비디오 상세 정보 가져오기
        videos = get_video_details(all_video_ids[:max_results], api_key)

        # 영상 타입 필터링
        if video_type == "shorts":
            videos = [v for v in videos if v["durationSeconds"] <= 60]
        elif video_type == "longform":
            videos = [v for v in videos if v["durationSeconds"] > 60]

        # 인덱스 추가
        for i, video in enumerate(videos):
            video["index"] = i + 1

        return jsonify({
            "success": True,
            "data": videos,
            "message": f"{len(videos)}개 영상을 찾았습니다."
        })

    except Exception as e:
        print(f"채널 영상 가져오기 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/filter', methods=['POST'])
def api_filter():
    """결과 필터링"""
    try:
        data = request.get_json()
        results = data.get("results", [])
        filters = data.get("filters", {})

        filtered = results.copy()

        # CII 필터
        cii_filters = []
        if filters.get("ciiGreat"):
            cii_filters.append("Great!!")
        if filters.get("ciiGood"):
            cii_filters.append("Good")
        if filters.get("ciiSoso"):
            cii_filters.append("Soso")

        if cii_filters:
            filtered = [v for v in filtered if v.get("cii") in cii_filters]

        # 조회수 필터
        view_count_min = filters.get("viewCount")
        if view_count_min:
            filtered = [v for v in filtered if v.get("viewCount", 0) >= int(view_count_min)]

        # 구독자수 필터 (이하)
        subscriber_max = filters.get("subscriberCount")
        if subscriber_max:
            filtered = [v for v in filtered if v.get("subscriberCount", 0) <= int(subscriber_max)]

        # 영상 길이 필터
        if filters.get("durationFilterActive"):
            duration_minutes = filters.get("durationFilterMinutes", 0)
            duration_condition = filters.get("durationFilterCondition", "이상")
            duration_seconds = duration_minutes * 60

            if duration_condition == "이상":
                filtered = [v for v in filtered if v.get("durationSeconds", 0) >= duration_seconds]
            else:
                filtered = [v for v in filtered if v.get("durationSeconds", 0) <= duration_seconds]

        # 인덱스 재조정
        for i, video in enumerate(filtered):
            video["index"] = i + 1

        return jsonify({
            "success": True,
            "data": filtered,
            "message": f"필터 적용 완료 - {len(filtered)}개 결과"
        })

    except Exception as e:
        print(f"필터 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# YouTube 카테고리 목록 (한국 기준)
YOUTUBE_CATEGORIES = {
    "1": "영화/애니메이션",
    "2": "자동차",
    "10": "음악",
    "15": "동물",
    "17": "스포츠",
    "19": "여행/이벤트",
    "20": "게임",
    "22": "인물/블로그",
    "23": "코미디",
    "24": "엔터테인먼트",
    "25": "뉴스/정치",
    "26": "노하우/스타일",
    "27": "교육",
    "28": "과학기술",
    "29": "비영리/사회운동"
}


@tubelens_bp.route('/api/tubelens/trending', methods=['POST'])
def api_trending():
    """트렌딩(인기) 영상 가져오기"""
    try:
        data = request.get_json()
        region_code = data.get("regionCode", "KR")
        category_id = data.get("categoryId", "")
        max_results = min(int(data.get("maxResults", 50)), 50)
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 트렌딩 영상 가져오기
        params = {
            "part": "snippet,statistics,contentDetails",
            "chart": "mostPopular",
            "regionCode": region_code,
            "maxResults": max_results
        }

        if category_id:
            params["videoCategoryId"] = category_id

        videos_data = make_youtube_request("videos", params, api_key)

        # 채널 정보 일괄 조회
        channel_ids = list(set([
            item["snippet"]["channelId"]
            for item in videos_data.get("items", [])
        ]))

        channel_map = {}
        if channel_ids:
            for i in range(0, len(channel_ids), 50):
                batch_ids = channel_ids[i:i+50]
                channels_data = make_youtube_request("channels", {
                    "part": "statistics",
                    "id": ",".join(batch_ids)
                }, api_key)

                for ch in channels_data.get("items", []):
                    channel_map[ch["id"]] = {
                        "subscriberCount": int(ch["statistics"].get("subscriberCount", 0)),
                        "videoCount": int(ch["statistics"].get("videoCount", 0))
                    }

        # 결과 가공
        videos = []
        for idx, item in enumerate(videos_data.get("items", [])):
            video_id = item["id"]
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})
            content_details = item.get("contentDetails", {})

            channel_id = snippet.get("channelId", "")
            channel_info = channel_map.get(channel_id, {"subscriberCount": 0, "videoCount": 0})

            duration_seconds = parse_duration(content_details.get("duration", ""))
            view_count = int(statistics.get("viewCount", 0))
            like_count = int(statistics.get("likeCount", 0))
            comment_count = int(statistics.get("commentCount", 0))
            subscriber_count = channel_info["subscriberCount"]

            cii_data = calculate_cii(view_count, subscriber_count, like_count, comment_count)

            videos.append({
                "index": idx + 1,
                "videoId": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                "channelId": channel_id,
                "channelTitle": snippet.get("channelTitle", ""),
                "publishedAt": snippet.get("publishedAt", "")[:10],
                "duration": format_duration(duration_seconds),
                "durationSeconds": duration_seconds,
                "viewCount": view_count,
                "likeCount": like_count,
                "commentCount": comment_count,
                "subscriberCount": subscriber_count,
                "totalVideos": channel_info["videoCount"],
                "categoryId": snippet.get("categoryId", ""),
                **cii_data
            })

        return jsonify({
            "success": True,
            "data": videos,
            "message": f"인기 영상 {len(videos)}개를 가져왔습니다."
        })

    except Exception as e:
        print(f"트렌딩 영상 가져오기 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/categories', methods=['GET'])
def api_categories():
    """YouTube 카테고리 목록 반환"""
    categories = [
        {"id": k, "name": v}
        for k, v in YOUTUBE_CATEGORIES.items()
    ]
    return jsonify({
        "success": True,
        "data": categories
    })


def calculate_rising_score(video: Dict[str, Any]) -> Dict[str, Any]:
    """
    진짜 급상승 점수 계산 - 시간당 조회수 + 구독자 대비 성과

    점수 요소:
    1. 시간당 조회수 (views_per_hour) - 최근 영상일수록 높은 가치
    2. 구독자 대비 배율 (performance_value)
    3. 신선도 보너스 (72시간 이내 영상에 가중치)
    4. 참여율 보너스 (좋아요+댓글 비율)
    """
    view_count = video.get("viewCount", 0)
    subscriber_count = video.get("subscriberCount", 1) or 1
    like_count = video.get("likeCount", 0)
    comment_count = video.get("commentCount", 0)
    published_at_raw = video.get("publishedAtRaw", "")

    # 업로드 후 경과 시간 (시간 단위)
    hours_since_upload = 1  # 최소 1시간
    if published_at_raw:
        try:
            from datetime import datetime
            published_dt = datetime.fromisoformat(published_at_raw.replace("Z", "+00:00"))
            now = datetime.now(published_dt.tzinfo) if published_dt.tzinfo else datetime.utcnow()
            hours_since_upload = max(1, (now - published_dt.replace(tzinfo=None)).total_seconds() / 3600)
        except:
            hours_since_upload = 24  # 기본값

    # 1. 시간당 조회수
    views_per_hour = view_count / hours_since_upload

    # 2. 일일 평균 조회수
    views_per_day = views_per_hour * 24

    # 3. 구독자 대비 배율
    performance_value = view_count / subscriber_count

    # 4. 신선도 보너스 (72시간 이내: 1.5배, 168시간(1주) 이내: 1.2배)
    freshness_bonus = 1.0
    if hours_since_upload <= 72:
        freshness_bonus = 1.5
    elif hours_since_upload <= 168:
        freshness_bonus = 1.2

    # 5. 참여율 (좋아요+댓글 / 조회수)
    engagement_rate = 0
    if view_count > 0:
        engagement_rate = (like_count + comment_count) / view_count * 100

    # 6. 참여율 보너스 (3% 이상이면 추가 점수)
    engagement_bonus = 1.0
    if engagement_rate >= 5:
        engagement_bonus = 1.3
    elif engagement_rate >= 3:
        engagement_bonus = 1.15

    # 급상승 점수 계산 (0-100 스케일)
    # 시간당 조회수가 높고 + 구독자 대비 성과가 좋고 + 신선하고 + 참여율 높으면 급상승
    rising_score = min(100, (
        (views_per_hour ** 0.5) * 2 +  # 시간당 조회수 (제곱근으로 스케일 조정)
        performance_value * 10 +        # 구독자 대비 배율
        engagement_rate * 5             # 참여율
    ) * freshness_bonus * engagement_bonus)

    # 급상승 등급
    if rising_score >= 70:
        rising_grade = "🔥 폭발"
    elif rising_score >= 50:
        rising_grade = "🚀 급상승"
    elif rising_score >= 30:
        rising_grade = "📈 상승중"
    else:
        rising_grade = "➡️ 보통"

    # 결과에 추가 정보 포함
    video["viewsPerHour"] = round(views_per_hour, 1)
    video["viewsPerDay"] = round(views_per_day, 0)
    video["hoursSinceUpload"] = round(hours_since_upload, 1)
    video["risingScore"] = round(rising_score, 1)
    video["risingGrade"] = rising_grade
    video["freshnessBonus"] = freshness_bonus
    video["engagementBonus"] = engagement_bonus

    return video


@tubelens_bp.route('/api/tubelens/rising', methods=['POST'])
def api_rising():
    """급상승 영상 발굴 (시간당 조회수 + 구독자 대비 성과 기반)"""
    try:
        data = request.get_json()
        region_code = data.get("regionCode", "KR")
        max_subscribers = int(data.get("maxSubscribers", 100000))  # 구독자 상한
        time_frame = data.get("timeFrame", "week")
        category_id = data.get("categoryId", "")
        video_type = data.get("videoType", "all")  # all, shorts, long
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)
        exclude_categories = data.get("excludeCategories", [])  # 제외할 카테고리

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 시간 필터 계산
        published_after = get_time_filter(time_frame)

        # 검색 파라미터 - date 순으로 검색하여 최신 영상 위주로 수집
        search_params = {
            "part": "snippet",
            "type": "video",
            "maxResults": 50,
            "regionCode": region_code,
            "order": "date",  # 최신순으로 변경 (급상승은 최신 영상에서 찾아야 함)
        }

        if published_after:
            search_params["publishedAfter"] = published_after

        if category_id:
            search_params["videoCategoryId"] = category_id

        # 영상 타입 필터
        if video_type == "shorts":
            search_params["videoDuration"] = "short"
        elif video_type == "long":
            search_params["videoDuration"] = "medium"

        # 여러 페이지에서 영상 수집 (최대 300개)
        all_video_ids = []
        next_page_token = None

        for _ in range(6):  # 최대 300개 수집
            if next_page_token:
                search_params["pageToken"] = next_page_token

            search_data = make_youtube_request("search", search_params, api_key)

            video_ids = [
                item["id"]["videoId"]
                for item in search_data.get("items", [])
                if item.get("id", {}).get("videoId")
            ]
            all_video_ids.extend(video_ids)

            next_page_token = search_data.get("nextPageToken")
            if not next_page_token:
                break

        # 비디오 상세 정보 가져오기
        videos = get_video_details(all_video_ids, api_key)

        # 급상승 필터링 및 점수 계산
        rising_videos = []
        for video in videos:
            subscriber_count = video.get("subscriberCount", 0)
            category_id_str = str(video.get("categoryId", ""))

            # 구독자 상한 체크
            if subscriber_count > max_subscribers:
                continue

            # 제외 카테고리 체크
            if category_id_str in exclude_categories:
                continue

            # 최소 조회수 체크 (노이즈 제거)
            if video.get("viewCount", 0) < 1000:
                continue

            # 급상승 점수 계산
            video = calculate_rising_score(video)

            # 급상승 점수 25 이상만 포함
            if video.get("risingScore", 0) >= 25:
                rising_videos.append(video)

        # 급상승 점수 기준 정렬
        rising_videos.sort(key=lambda x: x.get("risingScore", 0), reverse=True)

        # 상위 50개만
        rising_videos = rising_videos[:50]

        # 인덱스 재할당
        for idx, video in enumerate(rising_videos):
            video["index"] = idx + 1

        return jsonify({
            "success": True,
            "data": rising_videos,
            "message": f"급상승 영상 {len(rising_videos)}개를 발굴했습니다."
        })

    except Exception as e:
        print(f"급상승 영상 발굴 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/comments', methods=['POST'])
def api_comments():
    """영상 댓글 가져오기"""
    try:
        data = request.get_json()
        video_id = data.get("videoId", "")
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        if not video_id:
            return jsonify({"success": False, "message": "비디오 ID가 필요합니다."}), 400

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        comments_data = make_youtube_request("commentThreads", {
            "part": "snippet",
            "videoId": video_id,
            "order": "relevance",
            "maxResults": 20
        }, api_key)

        comments = []
        for item in comments_data.get("items", []):
            comment = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "author": comment.get("authorDisplayName", ""),
                "authorImage": comment.get("authorProfileImageUrl", ""),
                "text": comment.get("textDisplay", ""),
                "likeCount": comment.get("likeCount", 0),
                "publishedAt": comment.get("publishedAt", "")
            })

        return jsonify({
            "success": True,
            "data": comments,
            "message": f"{len(comments)}개 댓글을 가져왔습니다."
        })

    except Exception as e:
        print(f"댓글 가져오기 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/analyzer', methods=['POST'])
def api_analyzer():
    """콘텐츠 분석기 - 키워드+필터로 터진 영상 찾기"""
    try:
        data = request.get_json()

        keyword = data.get("keyword", "")
        region_code = data.get("regionCode", "JP")
        relevance_language = data.get("relevanceLanguage", "")
        time_frame = data.get("timeFrame", "week")
        duration = data.get("duration", "long")
        min_views = int(data.get("minViews", 10000))
        max_results = min(int(data.get("maxResults", 25)), 100)
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        if not keyword:
            return jsonify({"success": False, "message": "검색 키워드가 필요합니다."}), 400

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 검색 파라미터 설정
        search_params = {
            "part": "snippet",
            "type": "video",
            "maxResults": 50,
            "regionCode": region_code,
            "order": "viewCount",
            "q": keyword,
        }

        # 언어 필터
        if relevance_language:
            search_params["relevanceLanguage"] = relevance_language

        # 시간 필터
        published_after = get_time_filter(time_frame)
        if published_after:
            search_params["publishedAfter"] = published_after

        # 영상 길이 필터
        if duration == "short":
            search_params["videoDuration"] = "short"
        elif duration in ["medium", "long"]:
            search_params["videoDuration"] = "medium" if duration == "medium" else "long"

        # 검색 실행 (여러 페이지)
        all_video_ids = []
        next_page_token = None
        fetch_count = 0
        max_fetch = 4  # 최대 4번 페이지네이션 (200개)

        while len(all_video_ids) < max_results * 2 and fetch_count < max_fetch:
            if next_page_token:
                search_params["pageToken"] = next_page_token

            search_data = make_youtube_request("search", search_params, api_key)

            video_ids = [
                item["id"]["videoId"]
                for item in search_data.get("items", [])
                if item.get("id", {}).get("videoId")
            ]
            all_video_ids.extend(video_ids)

            next_page_token = search_data.get("nextPageToken")
            if not next_page_token:
                break
            fetch_count += 1

        # 비디오 상세 정보 가져오기
        videos = get_video_details(all_video_ids, api_key)

        # 영상 길이 필터링
        if duration == "short":
            videos = [v for v in videos if v["durationSeconds"] <= 60]
        elif duration == "medium":
            videos = [v for v in videos if 240 <= v["durationSeconds"] <= 1200]
        elif duration == "long":
            videos = [v for v in videos if v["durationSeconds"] > 1200]

        # 조회수 필터링
        videos = [v for v in videos if v["viewCount"] >= min_views]

        # 조회수 순 정렬
        videos.sort(key=lambda x: x["viewCount"], reverse=True)

        # 결과 제한
        videos = videos[:max_results]

        # 인덱스 추가
        for i, video in enumerate(videos):
            video["index"] = i + 1

        return jsonify({
            "success": True,
            "data": videos,
            "message": f"콘텐츠 분석 완료: {len(videos)}개 영상"
        })

    except Exception as e:
        print(f"콘텐츠 분석기 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ===== AI 분석 API =====

@tubelens_bp.route('/api/tubelens/analyze-titles', methods=['POST'])
def api_analyze_titles():
    """AI로 제목 패턴 분석 - 클릭 유발 요소 파악"""
    try:
        import json
        from openai import OpenAI

        data = request.get_json()
        titles = data.get("titles", [])  # [{title, viewCount, subscriberCount, ...}]

        if not titles:
            return jsonify({"success": False, "message": "분석할 제목이 없습니다."}), 400

        if len(titles) > 20:
            titles = titles[:20]  # 최대 20개

        # OpenAI API 키 확인
        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_api_key:
            return jsonify({"success": False, "message": "OpenAI API 키가 설정되지 않았습니다."}), 400

        client = OpenAI(api_key=openai_api_key)

        # 제목 데이터 준비
        titles_text = "\n".join([
            f"{i+1}. \"{t.get('title', '')}\" (조회수: {t.get('viewCount', 0):,}, 구독자: {t.get('subscriberCount', 0):,})"
            for i, t in enumerate(titles)
        ])

        prompt = f"""다음 YouTube 영상 제목들을 분석해주세요. 이 영상들은 구독자 대비 높은 조회수를 기록한 급상승 영상들입니다.

{titles_text}

다음 형식의 JSON으로 분석 결과를 제공해주세요:
{{
  "common_patterns": ["공통 패턴 1", "공통 패턴 2", ...],
  "click_triggers": ["클릭 유발 요소 1", "클릭 유발 요소 2", ...],
  "emotional_hooks": ["감정 자극 표현 1", "감정 자극 표현 2", ...],
  "title_structures": ["제목 구조 패턴 1", "제목 구조 패턴 2", ...],
  "recommended_keywords": ["추천 키워드 1", "추천 키워드 2", ...],
  "title_suggestions": [
    {{"template": "제목 템플릿 1", "example": "예시 제목 1"}},
    {{"template": "제목 템플릿 2", "example": "예시 제목 2"}},
    {{"template": "제목 템플릿 3", "example": "예시 제목 3"}}
  ],
  "summary": "전체 분석 요약 (2-3문장)"
}}

한국어로 답변해주세요."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 YouTube 콘텐츠 마케팅 전문가입니다. 제목 패턴 분석을 통해 클릭률을 높이는 인사이트를 제공합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        result_text = response.choices[0].message.content.strip()

        # JSON 파싱
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        analysis = json.loads(result_text)

        return jsonify({
            "success": True,
            "data": analysis,
            "message": "제목 패턴 분석 완료"
        })

    except json.JSONDecodeError as e:
        print(f"제목 분석 JSON 파싱 오류: {e}")
        return jsonify({"success": False, "message": "분석 결과 파싱 실패"}), 500
    except Exception as e:
        print(f"제목 분석 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/generate-ideas', methods=['POST'])
def api_generate_ideas():
    """트렌딩 영상 기반 대본 주제/아이디어 생성"""
    try:
        import json
        from openai import OpenAI

        data = request.get_json()
        videos = data.get("videos", [])  # [{title, description, ...}]
        target_category = data.get("targetCategory", "")  # 원하는 카테고리
        content_style = data.get("contentStyle", "story")  # story, news, education

        if not videos:
            return jsonify({"success": False, "message": "참고할 영상이 없습니다."}), 400

        if len(videos) > 10:
            videos = videos[:10]

        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_api_key:
            return jsonify({"success": False, "message": "OpenAI API 키가 설정되지 않았습니다."}), 400

        client = OpenAI(api_key=openai_api_key)

        # 영상 정보 준비
        videos_text = "\n".join([
            f"{i+1}. 제목: \"{v.get('title', '')}\"\n   설명: {v.get('description', '')[:200]}..."
            for i, v in enumerate(videos)
        ])

        style_guide = {
            "story": "감동적인 스토리텔링, 인간미 있는 이야기",
            "news": "시사/뉴스 형식, 팩트 기반",
            "education": "교육/정보 전달 형식",
            "entertainment": "재미있고 흥미로운 콘텐츠"
        }

        prompt = f"""다음 YouTube 인기/급상승 영상들을 참고하여 새로운 콘텐츠 아이디어를 생성해주세요.

참고 영상:
{videos_text}

콘텐츠 스타일: {style_guide.get(content_style, content_style)}
{f'타겟 카테고리: {target_category}' if target_category else ''}

다음 형식의 JSON으로 5개의 콘텐츠 아이디어를 제공해주세요:
{{
  "trend_analysis": "현재 트렌드 분석 (2-3문장)",
  "ideas": [
    {{
      "title": "추천 제목",
      "hook": "영상 시작 훅 (첫 5초)",
      "outline": "대본 개요 (3-5문장)",
      "target_emotion": "타겟 감정 (호기심/공감/분노/감동 등)",
      "viral_potential": "바이럴 가능성 (상/중/하)",
      "similar_to": "참고한 원본 영상 번호"
    }}
  ],
  "keywords": ["추천 키워드 1", "추천 키워드 2", ...],
  "avoid": ["피해야 할 요소 1", "피해야 할 요소 2", ...]
}}

한국어로 답변해주세요. 참신하고 한국 시청자에게 어필할 수 있는 아이디어로 제안해주세요."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 YouTube 콘텐츠 기획 전문가입니다. 트렌드를 분석하고 바이럴 가능성이 높은 콘텐츠 아이디어를 제안합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=3000
        )

        result_text = response.choices[0].message.content.strip()

        # JSON 파싱
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        ideas = json.loads(result_text)

        return jsonify({
            "success": True,
            "data": ideas,
            "message": f"{len(ideas.get('ideas', []))}개의 콘텐츠 아이디어가 생성되었습니다."
        })

    except json.JSONDecodeError as e:
        print(f"아이디어 생성 JSON 파싱 오류: {e}")
        return jsonify({"success": False, "message": "결과 파싱 실패"}), 500
    except Exception as e:
        print(f"아이디어 생성 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/analyze-thumbnails', methods=['POST'])
def api_analyze_thumbnails():
    """썸네일 패턴 분석 (URL 기반)"""
    try:
        import json
        from openai import OpenAI

        data = request.get_json()
        videos = data.get("videos", [])  # [{title, thumbnail, viewCount, ...}]

        if not videos:
            return jsonify({"success": False, "message": "분석할 영상이 없습니다."}), 400

        if len(videos) > 10:
            videos = videos[:10]

        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_api_key:
            return jsonify({"success": False, "message": "OpenAI API 키가 설정되지 않았습니다."}), 400

        client = OpenAI(api_key=openai_api_key)

        # GPT-5.1 Responses API용 input 구성
        system_prompt = "당신은 YouTube 썸네일 디자인 전문가입니다. 클릭률을 높이는 썸네일 패턴을 분석합니다."

        user_content = [
            {"type": "input_text", "text": """다음 YouTube 썸네일들을 분석해주세요. 이 영상들은 높은 성과를 기록한 급상승 영상들입니다.

각 썸네일의 공통 패턴과 클릭을 유발하는 요소를 분석하고, 다음 형식의 JSON으로 결과를 제공해주세요:

{
  "common_elements": ["공통 요소 1", "공통 요소 2", ...],
  "color_patterns": ["색상 패턴 1", "색상 패턴 2", ...],
  "text_usage": ["텍스트 사용 패턴 1", "텍스트 사용 패턴 2", ...],
  "face_expressions": ["표정/인물 패턴 1", "표정/인물 패턴 2", ...],
  "composition": ["구도 패턴 1", "구도 패턴 2", ...],
  "recommendations": [
    {"tip": "추천 1", "reason": "이유 1"},
    {"tip": "추천 2", "reason": "이유 2"},
    {"tip": "추천 3", "reason": "이유 3"}
  ],
  "summary": "전체 분석 요약 (2-3문장)"
}

한국어로 답변해주세요."""}
        ]

        # 썸네일 이미지 추가 (GPT-5.1 형식)
        for i, v in enumerate(videos[:6]):  # 최대 6개 이미지
            thumbnail_url = v.get("thumbnail", "")
            if thumbnail_url:
                user_content.append({"type": "input_image", "image_url": thumbnail_url})
                user_content.append({"type": "input_text", "text": f"[영상 {i+1}] 제목: {v.get('title', '')} (조회수: {v.get('viewCount', 0):,})"})

        response = client.responses.create(
            model="gpt-5.1",
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7
        )

        # GPT-5.1 응답 추출
        if getattr(response, "output_text", None):
            result_text = response.output_text.strip()
        else:
            text_chunks = []
            for item in getattr(response, "output", []) or []:
                for content_item in getattr(item, "content", []) or []:
                    if getattr(content_item, "type", "") == "text":
                        text_chunks.append(getattr(content_item, "text", ""))
            result_text = "\n".join(text_chunks).strip()

        # JSON 파싱
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        analysis = json.loads(result_text)

        return jsonify({
            "success": True,
            "data": analysis,
            "message": "썸네일 패턴 분석 완료"
        })

    except json.JSONDecodeError as e:
        print(f"썸네일 분석 JSON 파싱 오류: {e}")
        return jsonify({"success": False, "message": "분석 결과 파싱 실패"}), 500
    except Exception as e:
        print(f"썸네일 분석 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/config', methods=['GET'])
def api_get_config():
    """서버에 저장된 API 키 확인 (마스킹된 형태로)"""
    youtube_key = os.getenv("YOUTUBE_API_KEY", "")

    has_youtube_key = bool(youtube_key)
    masked_key = ""
    if youtube_key:
        masked_key = youtube_key[:8] + "••••••••" + youtube_key[-4:] if len(youtube_key) > 12 else "••••"

    return jsonify({
        "success": True,
        "data": {
            "hasYouTubeKey": has_youtube_key,
            "maskedKey": masked_key
        }
    })


# ===== 신규 기능: 경쟁 채널 비교 =====

@tubelens_bp.route('/api/tubelens/compare-channels', methods=['POST'])
def api_compare_channels():
    """여러 채널 비교 분석"""
    try:
        data = request.get_json()
        channel_ids = data.get("channelIds", [])  # 채널 ID 리스트
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        if not channel_ids or len(channel_ids) < 2:
            return jsonify({"success": False, "message": "비교할 채널을 2개 이상 입력해주세요."}), 400

        if len(channel_ids) > 5:
            channel_ids = channel_ids[:5]  # 최대 5개

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 채널 정보 일괄 조회
        channels_data = make_youtube_request("channels", {
            "part": "snippet,statistics,contentDetails,brandingSettings",
            "id": ",".join(channel_ids)
        }, api_key)

        channels = []
        for ch in channels_data.get("items", []):
            stats = ch.get("statistics", {})
            snippet = ch.get("snippet", {})

            # 최근 10개 영상 성과 분석
            upload_playlist = ch.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
            recent_videos = []
            avg_views = 0
            avg_likes = 0
            avg_comments = 0

            if upload_playlist:
                playlist_data = make_youtube_request("playlistItems", {
                    "part": "contentDetails",
                    "playlistId": upload_playlist,
                    "maxResults": 10
                }, api_key)

                video_ids = [item["contentDetails"]["videoId"] for item in playlist_data.get("items", [])]

                if video_ids:
                    videos_data = make_youtube_request("videos", {
                        "part": "statistics,snippet",
                        "id": ",".join(video_ids)
                    }, api_key)

                    for vid in videos_data.get("items", []):
                        vid_stats = vid.get("statistics", {})
                        recent_videos.append({
                            "title": vid.get("snippet", {}).get("title", ""),
                            "viewCount": int(vid_stats.get("viewCount", 0)),
                            "likeCount": int(vid_stats.get("likeCount", 0)),
                            "commentCount": int(vid_stats.get("commentCount", 0))
                        })

                    if recent_videos:
                        avg_views = sum(v["viewCount"] for v in recent_videos) // len(recent_videos)
                        avg_likes = sum(v["likeCount"] for v in recent_videos) // len(recent_videos)
                        avg_comments = sum(v["commentCount"] for v in recent_videos) // len(recent_videos)

            subscriber_count = int(stats.get("subscriberCount", 0))
            view_count = int(stats.get("viewCount", 0))
            video_count = int(stats.get("videoCount", 0))

            # 영상당 평균 조회수
            avg_views_per_video = view_count // video_count if video_count > 0 else 0

            channels.append({
                "channelId": ch.get("id"),
                "channelTitle": snippet.get("title", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                "description": snippet.get("description", "")[:200],
                "subscriberCount": subscriber_count,
                "viewCount": view_count,
                "videoCount": video_count,
                "avgViewsPerVideo": avg_views_per_video,
                "recentAvgViews": avg_views,
                "recentAvgLikes": avg_likes,
                "recentAvgComments": avg_comments,
                "engagementRate": round((avg_likes + avg_comments) / avg_views * 100, 2) if avg_views > 0 else 0,
                "recentVideos": recent_videos[:5],
                "country": snippet.get("country", ""),
                "publishedAt": snippet.get("publishedAt", "")[:10]
            })

        # 구독자수 기준 정렬
        channels.sort(key=lambda x: x["subscriberCount"], reverse=True)

        return jsonify({
            "success": True,
            "data": channels,
            "message": f"{len(channels)}개 채널 비교 분석 완료"
        })

    except Exception as e:
        print(f"채널 비교 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ===== 신규 기능: 제목 A/B 테스트 제안 =====

@tubelens_bp.route('/api/tubelens/suggest-titles', methods=['POST'])
def api_suggest_titles():
    """AI로 대안 제목 생성 (A/B 테스트용)"""
    try:
        import json
        from openai import OpenAI

        data = request.get_json()
        original_title = data.get("title", "")
        description = data.get("description", "")
        target_audience = data.get("targetAudience", "general")  # general, young, senior

        if not original_title:
            return jsonify({"success": False, "message": "원본 제목이 필요합니다."}), 400

        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_api_key:
            return jsonify({"success": False, "message": "OpenAI API 키가 설정되지 않았습니다."}), 400

        client = OpenAI(api_key=openai_api_key)

        audience_guide = {
            "general": "일반 대중",
            "young": "10-30대 젊은 층",
            "senior": "40-60대 중장년층"
        }

        prompt = f"""다음 YouTube 영상 제목의 대안을 5개 생성해주세요.

원본 제목: {original_title}
{f'영상 설명: {description[:300]}...' if description else ''}
타겟 시청자: {audience_guide.get(target_audience, "일반 대중")}

각 대안은 다른 접근법을 사용해주세요:
1. 호기심 유발형 (질문/의문)
2. 숫자/리스트형 (구체적 수치)
3. 감정 자극형 (놀라움/충격)
4. 직접 화법형 (시청자에게 말하듯)
5. 트렌드 키워드형 (검색 최적화)

다음 형식의 JSON으로 응답해주세요:
{{
  "suggestions": [
    {{
      "type": "호기심 유발형",
      "title": "대안 제목",
      "reason": "이 제목이 효과적인 이유"
    }}
  ],
  "analysis": "원본 제목 분석 (강점/약점)"
}}

한국어로 답변해주세요."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 YouTube 제목 최적화 전문가입니다. CTR을 높이는 제목을 제안합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=2000
        )

        result_text = response.choices[0].message.content.strip()

        # JSON 파싱
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        suggestions = json.loads(result_text)

        return jsonify({
            "success": True,
            "data": suggestions,
            "message": "5개의 대안 제목이 생성되었습니다."
        })

    except json.JSONDecodeError as e:
        print(f"제목 제안 JSON 파싱 오류: {e}")
        return jsonify({"success": False, "message": "결과 파싱 실패"}), 500
    except Exception as e:
        print(f"제목 제안 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ===== 신규 기능: 댓글 감성 분석 =====

@tubelens_bp.route('/api/tubelens/analyze-sentiment', methods=['POST'])
def api_analyze_sentiment():
    """댓글 감성 분석"""
    try:
        import json
        from openai import OpenAI

        data = request.get_json()
        video_id = data.get("videoId", "")
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        if not video_id:
            return jsonify({"success": False, "message": "비디오 ID가 필요합니다."}), 400

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "YouTube API 키가 필요합니다."}), 400

        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_api_key:
            return jsonify({"success": False, "message": "OpenAI API 키가 설정되지 않았습니다."}), 400

        # 댓글 가져오기
        comments_data = make_youtube_request("commentThreads", {
            "part": "snippet",
            "videoId": video_id,
            "order": "relevance",
            "maxResults": 50
        }, api_key)

        comments = []
        for item in comments_data.get("items", []):
            comment = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "text": comment.get("textDisplay", ""),
                "likeCount": comment.get("likeCount", 0)
            })

        if not comments:
            return jsonify({
                "success": True,
                "data": {
                    "summary": "댓글이 없습니다.",
                    "sentiment": {"positive": 0, "neutral": 0, "negative": 0},
                    "keywords": [],
                    "suggestions": []
                },
                "message": "댓글이 없습니다."
            })

        # AI 분석
        client = OpenAI(api_key=openai_api_key)

        comments_text = "\n".join([f"- {c['text'][:200]}" for c in comments[:30]])

        prompt = f"""다음 YouTube 영상 댓글들의 감성을 분석해주세요.

댓글 목록:
{comments_text}

다음 형식의 JSON으로 분석 결과를 제공해주세요:
{{
  "sentiment": {{
    "positive": 긍정 댓글 비율 (0-100),
    "neutral": 중립 댓글 비율 (0-100),
    "negative": 부정 댓글 비율 (0-100)
  }},
  "summary": "전체 댓글 분위기 요약 (2-3문장)",
  "keywords": ["자주 언급된 키워드 1", "키워드 2", ...],
  "positive_points": ["시청자들이 좋아하는 점 1", "점 2", ...],
  "negative_points": ["시청자들이 아쉬워하는 점 1", "점 2", ...],
  "suggestions": ["개선 제안 1", "제안 2", ...],
  "sample_comments": {{
    "positive": "대표 긍정 댓글",
    "negative": "대표 부정 댓글 (있는 경우)"
  }}
}}

한국어로 답변해주세요."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 소셜 미디어 감성 분석 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        result_text = response.choices[0].message.content.strip()

        # JSON 파싱
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        analysis = json.loads(result_text)
        analysis["totalComments"] = len(comments)

        return jsonify({
            "success": True,
            "data": analysis,
            "message": f"{len(comments)}개 댓글 감성 분석 완료"
        })

    except json.JSONDecodeError as e:
        print(f"감성 분석 JSON 파싱 오류: {e}")
        return jsonify({"success": False, "message": "분석 결과 파싱 실패"}), 500
    except Exception as e:
        print(f"감성 분석 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ===== 신규 기능: 태그 분석 =====

@tubelens_bp.route('/api/tubelens/analyze-tags', methods=['POST'])
def api_analyze_tags():
    """인기 영상들의 태그/해시태그 패턴 분석"""
    try:
        import json
        from collections import Counter

        data = request.get_json()
        video_ids = data.get("videoIds", [])
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        if not video_ids:
            return jsonify({"success": False, "message": "분석할 영상이 없습니다."}), 400

        if len(video_ids) > 20:
            video_ids = video_ids[:20]

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 영상 정보 가져오기 (태그 포함)
        videos_data = make_youtube_request("videos", {
            "part": "snippet,statistics",
            "id": ",".join(video_ids)
        }, api_key)

        all_tags = []
        all_hashtags = []
        video_tag_data = []

        for item in videos_data.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})

            tags = snippet.get("tags", [])
            title = snippet.get("title", "")
            description = snippet.get("description", "")

            # 제목과 설명에서 해시태그 추출
            import re
            hashtags_in_title = re.findall(r'#(\w+)', title)
            hashtags_in_desc = re.findall(r'#(\w+)', description)
            hashtags = list(set(hashtags_in_title + hashtags_in_desc))

            all_tags.extend(tags)
            all_hashtags.extend(hashtags)

            video_tag_data.append({
                "title": title,
                "viewCount": int(stats.get("viewCount", 0)),
                "tags": tags[:10],
                "hashtags": hashtags[:5]
            })

        # 태그 빈도 분석
        tag_counter = Counter(all_tags)
        hashtag_counter = Counter(all_hashtags)

        # 가장 많이 사용된 태그
        top_tags = [{"tag": tag, "count": count} for tag, count in tag_counter.most_common(20)]
        top_hashtags = [{"hashtag": ht, "count": count} for ht, count in hashtag_counter.most_common(10)]

        # 태그 길이 분석
        avg_tag_count = len(all_tags) / len(video_ids) if video_ids else 0
        avg_tag_length = sum(len(t) for t in all_tags) / len(all_tags) if all_tags else 0

        return jsonify({
            "success": True,
            "data": {
                "topTags": top_tags,
                "topHashtags": top_hashtags,
                "totalTagsAnalyzed": len(all_tags),
                "totalHashtagsAnalyzed": len(all_hashtags),
                "avgTagsPerVideo": round(avg_tag_count, 1),
                "avgTagLength": round(avg_tag_length, 1),
                "videoTagData": video_tag_data,
                "recommendations": [
                    f"평균 {round(avg_tag_count)}개의 태그 사용 권장",
                    f"인기 태그: {', '.join([t['tag'] for t in top_tags[:5]])}",
                    f"인기 해시태그: {', '.join(['#' + h['hashtag'] for h in top_hashtags[:3]])}" if top_hashtags else "해시태그 활용 권장"
                ]
            },
            "message": f"{len(video_ids)}개 영상의 태그 분석 완료"
        })

    except Exception as e:
        print(f"태그 분석 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ===== 신규 기능: 키워드 트렌드 (YouTube 검색 기반) =====

# ===== 신규 기능: 통합 영상 점수 계산 =====

def calculate_seo_score(title: str, description: str, tags: List[str] = None) -> Dict[str, Any]:
    """SEO 점수 계산 - 제목, 설명, 태그 최적화 분석"""
    score = 0
    details = []

    # 제목 분석 (최대 40점)
    title_len = len(title)
    if 30 <= title_len <= 60:
        score += 20
        details.append("✅ 제목 길이 적절 (30-60자)")
    elif 20 <= title_len <= 70:
        score += 10
        details.append("⚠️ 제목 길이 보통")
    else:
        details.append("❌ 제목 너무 짧거나 김")

    # 제목에 숫자 포함 (클릭률 향상)
    import re
    if re.search(r'\d+', title):
        score += 10
        details.append("✅ 숫자 포함 (클릭률 ↑)")

    # 제목에 감정 표현 포함
    emotion_words = ['충격', '놀라운', '대박', '감동', '실화', '경악', '비밀', '반전', '최초', '드디어']
    if any(word in title for word in emotion_words):
        score += 10
        details.append("✅ 감정 유발 키워드 포함")

    # 설명란 분석 (최대 30점)
    desc_len = len(description) if description else 0
    if desc_len >= 500:
        score += 15
        details.append("✅ 설명란 충분히 작성됨")
    elif desc_len >= 200:
        score += 8
        details.append("⚠️ 설명란 보통")
    else:
        details.append("❌ 설명란 너무 짧음")

    # 설명에 타임스탬프 포함
    if description and re.search(r'\d{1,2}:\d{2}', description):
        score += 10
        details.append("✅ 타임스탬프 포함")

    # 해시태그 분석
    hashtags = re.findall(r'#\w+', title + (description or ''))
    if 3 <= len(hashtags) <= 10:
        score += 5
        details.append("✅ 해시태그 적절")
    elif len(hashtags) > 0:
        score += 2
        details.append("⚠️ 해시태그 부족하거나 과다")

    # 태그 분석 (최대 30점)
    if tags:
        if len(tags) >= 10:
            score += 15
            details.append("✅ 태그 충분히 설정됨")
        elif len(tags) >= 5:
            score += 8
            details.append("⚠️ 태그 보통")
        else:
            details.append("❌ 태그 부족")

        # 태그 길이 다양성
        tag_lengths = [len(t) for t in tags]
        if min(tag_lengths, default=0) < 10 and max(tag_lengths, default=0) > 15:
            score += 10
            details.append("✅ 태그 길이 다양함")
    else:
        score += 5  # 태그 정보 없으면 기본점

    # 등급 결정
    if score >= 80:
        grade = "A+"
    elif score >= 65:
        grade = "A"
    elif score >= 50:
        grade = "B"
    elif score >= 35:
        grade = "C"
    else:
        grade = "D"

    return {
        "score": min(100, score),
        "grade": grade,
        "details": details
    }


def calculate_viral_score(video: Dict[str, Any]) -> Dict[str, Any]:
    """바이럴 예측 점수 계산 - 조회수 가속도, 참여율, 구독자 대비 성과 종합"""
    view_count = video.get("viewCount", 0)
    like_count = video.get("likeCount", 0)
    comment_count = video.get("commentCount", 0)
    subscriber_count = video.get("subscriberCount", 1) or 1
    hours_since_upload = video.get("hoursSinceUpload", 24)

    if hours_since_upload == 0:
        hours_since_upload = 1

    score = 0
    factors = []

    # 1. 시간당 조회수 (가속도) - 최대 30점
    views_per_hour = view_count / hours_since_upload
    if views_per_hour >= 10000:
        score += 30
        factors.append(("시간당 조회수", "🔥 폭발적", views_per_hour))
    elif views_per_hour >= 1000:
        score += 20
        factors.append(("시간당 조회수", "🚀 높음", views_per_hour))
    elif views_per_hour >= 100:
        score += 10
        factors.append(("시간당 조회수", "📈 보통", views_per_hour))
    else:
        factors.append(("시간당 조회수", "➡️ 낮음", views_per_hour))

    # 2. 구독자 대비 성과 - 최대 25점
    performance = view_count / subscriber_count
    if performance >= 5:
        score += 25
        factors.append(("구독자 대비", "🔥 5배 이상", performance))
    elif performance >= 2:
        score += 18
        factors.append(("구독자 대비", "✅ 2배 이상", performance))
    elif performance >= 1:
        score += 10
        factors.append(("구독자 대비", "📊 1배 이상", performance))
    else:
        factors.append(("구독자 대비", "➡️ 1배 미만", performance))

    # 3. 참여율 - 최대 25점
    engagement_rate = 0
    if view_count > 0:
        engagement_rate = ((like_count + comment_count) / view_count) * 100

    if engagement_rate >= 10:
        score += 25
        factors.append(("참여율", "🔥 매우 높음", f"{engagement_rate:.1f}%"))
    elif engagement_rate >= 5:
        score += 18
        factors.append(("참여율", "✅ 높음", f"{engagement_rate:.1f}%"))
    elif engagement_rate >= 2:
        score += 10
        factors.append(("참여율", "📊 보통", f"{engagement_rate:.1f}%"))
    else:
        factors.append(("참여율", "➡️ 낮음", f"{engagement_rate:.1f}%"))

    # 4. 좋아요/댓글 비율 - 최대 10점
    if comment_count > 0:
        like_comment_ratio = like_count / comment_count
        if 5 <= like_comment_ratio <= 50:
            score += 10
            factors.append(("좋아요/댓글 비율", "✅ 건강함", like_comment_ratio))
        elif like_comment_ratio > 50:
            score += 5
            factors.append(("좋아요/댓글 비율", "⚠️ 댓글 부족", like_comment_ratio))

    # 5. 신선도 보너스 - 최대 10점
    if hours_since_upload <= 24:
        score += 10
        factors.append(("신선도", "🆕 24시간 이내", f"{hours_since_upload:.0f}h"))
    elif hours_since_upload <= 72:
        score += 5
        factors.append(("신선도", "📅 3일 이내", f"{hours_since_upload:.0f}h"))

    # 등급 결정
    if score >= 80:
        grade = "🔥 바이럴 확실"
    elif score >= 60:
        grade = "🚀 바이럴 가능성 높음"
    elif score >= 40:
        grade = "📈 성장 중"
    else:
        grade = "➡️ 보통"

    return {
        "viralScore": min(100, score),
        "viralGrade": grade,
        "viralFactors": factors
    }


@tubelens_bp.route('/api/tubelens/upload-pattern', methods=['POST'])
def api_upload_pattern():
    """채널의 업로드 패턴 분석 - 요일/시간대별 성과"""
    try:
        data = request.get_json()
        channel_id = data.get("channelId", "")
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        if not channel_id:
            return jsonify({"success": False, "message": "채널 ID가 필요합니다."}), 400

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 채널의 업로드 플레이리스트 가져오기
        channel_info = get_channel_info(channel_id, api_key)
        upload_playlist = channel_info.get("uploadPlaylist", "")

        if not upload_playlist:
            return jsonify({"success": False, "message": "업로드 플레이리스트를 찾을 수 없습니다."}), 400

        # 최근 50개 영상 가져오기
        playlist_data = make_youtube_request("playlistItems", {
            "part": "contentDetails",
            "playlistId": upload_playlist,
            "maxResults": 50
        }, api_key)

        video_ids = [item["contentDetails"]["videoId"] for item in playlist_data.get("items", [])]

        if not video_ids:
            return jsonify({"success": False, "message": "영상이 없습니다."}), 400

        # 영상 상세 정보 가져오기
        videos_data = make_youtube_request("videos", {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(video_ids)
        }, api_key)

        # 요일별 분석
        day_stats = {0: [], 1: [], 2: [], 3: [], 4: [], 5: [], 6: []}  # 월~일
        day_names = ["월", "화", "수", "목", "금", "토", "일"]

        # 시간대별 분석
        hour_stats = {h: [] for h in range(24)}

        # 영상 길이별 성과
        duration_stats = {"short": [], "medium": [], "long": []}  # ~10분, 10~30분, 30분+

        # 제목 길이별 성과
        title_length_stats = {"short": [], "medium": [], "long": []}  # ~30자, 30~50자, 50자+

        for vid in videos_data.get("items", []):
            snippet = vid.get("snippet", {})
            stats = vid.get("statistics", {})
            content = vid.get("contentDetails", {})

            published_at = snippet.get("publishedAt", "")
            view_count = int(stats.get("viewCount", 0))

            if published_at:
                from datetime import datetime
                dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                weekday = dt.weekday()
                hour = dt.hour

                day_stats[weekday].append(view_count)
                hour_stats[hour].append(view_count)

            # 영상 길이 분석
            duration_seconds = parse_duration(content.get("duration", ""))
            if duration_seconds <= 600:  # 10분 이하
                duration_stats["short"].append(view_count)
            elif duration_seconds <= 1800:  # 30분 이하
                duration_stats["medium"].append(view_count)
            else:
                duration_stats["long"].append(view_count)

            # 제목 길이 분석
            title = snippet.get("title", "")
            title_len = len(title)
            if title_len <= 30:
                title_length_stats["short"].append(view_count)
            elif title_len <= 50:
                title_length_stats["medium"].append(view_count)
            else:
                title_length_stats["long"].append(view_count)

        # 요일별 평균 계산
        day_avg = []
        best_day = {"name": "", "avg": 0}
        for i in range(7):
            views = day_stats[i]
            avg = sum(views) / len(views) if views else 0
            day_avg.append({"day": day_names[i], "avgViews": round(avg), "videoCount": len(views)})
            if avg > best_day["avg"]:
                best_day = {"name": day_names[i], "avg": avg}

        # 시간대별 평균 (6시간 단위로 그룹핑)
        time_periods = [
            {"name": "새벽 (0-6시)", "hours": list(range(0, 6))},
            {"name": "오전 (6-12시)", "hours": list(range(6, 12))},
            {"name": "오후 (12-18시)", "hours": list(range(12, 18))},
            {"name": "저녁 (18-24시)", "hours": list(range(18, 24))}
        ]

        time_avg = []
        best_time = {"name": "", "avg": 0}
        for period in time_periods:
            views = []
            for h in period["hours"]:
                views.extend(hour_stats[h])
            avg = sum(views) / len(views) if views else 0
            time_avg.append({"period": period["name"], "avgViews": round(avg), "videoCount": len(views)})
            if avg > best_time["avg"]:
                best_time = {"name": period["name"], "avg": avg}

        # 영상 길이별 평균
        duration_avg = {}
        duration_labels = {"short": "10분 이하", "medium": "10-30분", "long": "30분 이상"}
        best_duration = {"name": "", "avg": 0}
        for key, views in duration_stats.items():
            avg = sum(views) / len(views) if views else 0
            duration_avg[key] = {"label": duration_labels[key], "avgViews": round(avg), "videoCount": len(views)}
            if avg > best_duration["avg"]:
                best_duration = {"name": duration_labels[key], "avg": avg}

        # 제목 길이별 평균
        title_avg = {}
        title_labels = {"short": "30자 이하", "medium": "30-50자", "long": "50자 이상"}
        best_title_len = {"name": "", "avg": 0}
        for key, views in title_length_stats.items():
            avg = sum(views) / len(views) if views else 0
            title_avg[key] = {"label": title_labels[key], "avgViews": round(avg), "videoCount": len(views)}
            if avg > best_title_len["avg"]:
                best_title_len = {"name": title_labels[key], "avg": avg}

        return jsonify({
            "success": True,
            "data": {
                "channelTitle": channel_info.get("channelTitle", ""),
                "analyzedVideos": len(video_ids),
                "dayPattern": {
                    "data": day_avg,
                    "bestDay": best_day["name"],
                    "recommendation": f"'{best_day['name']}요일'에 업로드하면 평균 {format_number(int(best_day['avg']))}회 조회수 기대"
                },
                "timePattern": {
                    "data": time_avg,
                    "bestTime": best_time["name"],
                    "recommendation": f"'{best_time['name']}'에 업로드하면 평균 {format_number(int(best_time['avg']))}회 조회수 기대"
                },
                "durationPattern": {
                    "data": duration_avg,
                    "bestDuration": best_duration["name"],
                    "recommendation": f"'{best_duration['name']}' 영상이 평균 {format_number(int(best_duration['avg']))}회로 가장 좋은 성과"
                },
                "titleLengthPattern": {
                    "data": title_avg,
                    "bestTitleLength": best_title_len["name"],
                    "recommendation": f"'{best_title_len['name']}' 제목이 평균 {format_number(int(best_title_len['avg']))}회로 가장 좋은 성과"
                }
            },
            "message": "업로드 패턴 분석 완료"
        })

    except Exception as e:
        print(f"업로드 패턴 분석 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/video-score', methods=['POST'])
def api_video_score():
    """영상 종합 점수 계산 - SEO + 바이럴 예측 통합"""
    try:
        data = request.get_json()
        video_id = data.get("videoId", "")
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        if not video_id:
            return jsonify({"success": False, "message": "비디오 ID가 필요합니다."}), 400

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 영상 정보 가져오기
        videos_data = make_youtube_request("videos", {
            "part": "snippet,statistics,contentDetails",
            "id": video_id
        }, api_key)

        if not videos_data.get("items"):
            return jsonify({"success": False, "message": "영상을 찾을 수 없습니다."}), 400

        video = videos_data["items"][0]
        snippet = video.get("snippet", {})
        stats = video.get("statistics", {})
        content = video.get("contentDetails", {})

        # 채널 정보 가져오기
        channel_id = snippet.get("channelId", "")
        channel_info = get_channel_info(channel_id, api_key) if channel_id else {}

        # 업로드 시간 계산
        published_at = snippet.get("publishedAt", "")
        hours_since_upload = 24
        if published_at:
            try:
                from datetime import datetime
                published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                now = datetime.now(published_dt.tzinfo) if published_dt.tzinfo else datetime.utcnow()
                hours_since_upload = max(1, (now - published_dt.replace(tzinfo=None)).total_seconds() / 3600)
            except:
                pass

        video_data = {
            "viewCount": int(stats.get("viewCount", 0)),
            "likeCount": int(stats.get("likeCount", 0)),
            "commentCount": int(stats.get("commentCount", 0)),
            "subscriberCount": channel_info.get("subscriberCount", 0),
            "hoursSinceUpload": hours_since_upload
        }

        # SEO 점수 계산
        tags = snippet.get("tags", [])
        seo_result = calculate_seo_score(
            snippet.get("title", ""),
            snippet.get("description", ""),
            tags
        )

        # 바이럴 점수 계산
        viral_result = calculate_viral_score(video_data)

        # 종합 점수 (SEO 40% + 바이럴 60%)
        total_score = seo_result["score"] * 0.4 + viral_result["viralScore"] * 0.6

        if total_score >= 80:
            total_grade = "🏆 S등급"
        elif total_score >= 65:
            total_grade = "⭐ A등급"
        elif total_score >= 50:
            total_grade = "✅ B등급"
        elif total_score >= 35:
            total_grade = "📊 C등급"
        else:
            total_grade = "➡️ D등급"

        return jsonify({
            "success": True,
            "data": {
                "videoId": video_id,
                "title": snippet.get("title", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                "seo": seo_result,
                "viral": viral_result,
                "totalScore": round(total_score, 1),
                "totalGrade": total_grade,
                "stats": video_data
            },
            "message": "영상 종합 분석 완료"
        })

    except Exception as e:
        print(f"영상 점수 계산 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/similar-channels', methods=['POST'])
def api_similar_channels():
    """유사 채널 찾기 - 비슷한 주제/규모의 채널 발굴"""
    try:
        data = request.get_json()
        channel_id = data.get("channelId", "")
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        if not channel_id:
            return jsonify({"success": False, "message": "채널 ID가 필요합니다."}), 400

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 원본 채널 정보
        base_channel = get_channel_info(channel_id, api_key)
        if not base_channel:
            return jsonify({"success": False, "message": "채널을 찾을 수 없습니다."}), 400

        base_subs = base_channel.get("subscriberCount", 0)
        channel_title = base_channel.get("channelTitle", "")

        # 채널 키워드로 유사 채널 검색
        search_data = make_youtube_request("search", {
            "part": "snippet",
            "q": channel_title,
            "type": "channel",
            "maxResults": 20,
            "regionCode": "KR"
        }, api_key)

        similar_channels = []
        for item in search_data.get("items", []):
            found_channel_id = item["id"]["channelId"]
            if found_channel_id == channel_id:  # 자기 자신 제외
                continue

            ch_info = get_channel_info(found_channel_id, api_key)
            if not ch_info:
                continue

            ch_subs = ch_info.get("subscriberCount", 0)

            # 구독자 수 유사도 계산 (0.1배 ~ 10배 범위)
            if base_subs > 0 and ch_subs > 0:
                ratio = ch_subs / base_subs if ch_subs > base_subs else base_subs / ch_subs
                if ratio <= 10:  # 10배 이내만
                    similarity = max(0, 100 - (ratio - 1) * 10)  # 비율이 가까울수록 높은 점수

                    similar_channels.append({
                        "channelId": found_channel_id,
                        "channelTitle": ch_info.get("channelTitle", ""),
                        "thumbnail": ch_info.get("thumbnailUrl", ""),
                        "subscriberCount": ch_subs,
                        "videoCount": ch_info.get("videoCount", 0),
                        "viewCount": ch_info.get("viewCount", 0),
                        "similarity": round(similarity, 1),
                        "sizeRatio": f"{ch_subs / base_subs:.1f}x" if base_subs > 0 else "N/A"
                    })

        # 유사도 순 정렬
        similar_channels.sort(key=lambda x: x["similarity"], reverse=True)

        return jsonify({
            "success": True,
            "data": {
                "baseChannel": {
                    "channelId": channel_id,
                    "channelTitle": channel_title,
                    "subscriberCount": base_subs
                },
                "similarChannels": similar_channels[:10]
            },
            "message": f"{len(similar_channels[:10])}개의 유사 채널을 찾았습니다."
        })

    except Exception as e:
        print(f"유사 채널 찾기 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/generate-description', methods=['POST'])
def api_generate_description():
    """AI로 최적화된 설명란 템플릿 생성"""
    try:
        import json
        from openai import OpenAI

        data = request.get_json()
        title = data.get("title", "")
        category = data.get("category", "general")  # general, news, story, education
        include_sections = data.get("includeSections", ["timestamps", "links", "hashtags"])

        if not title:
            return jsonify({"success": False, "message": "영상 제목이 필요합니다."}), 400

        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_api_key:
            return jsonify({"success": False, "message": "OpenAI API 키가 설정되지 않았습니다."}), 400

        client = OpenAI(api_key=openai_api_key)

        sections_guide = {
            "timestamps": "- 챕터별 타임스탬프 (00:00 형식)",
            "links": "- 관련 링크 섹션",
            "hashtags": "- SEO용 해시태그 (3-5개)",
            "cta": "- 구독/좋아요 CTA",
            "credits": "- 출처/크레딧 섹션"
        }

        selected_sections = "\n".join([sections_guide.get(s, "") for s in include_sections if s in sections_guide])

        category_style = {
            "general": "일반적인 유튜브 영상",
            "news": "뉴스/시사 콘텐츠 (정보 전달 중심)",
            "story": "스토리텔링 콘텐츠 (감성적, 몰입형)",
            "education": "교육/정보 콘텐츠 (학습 목적)"
        }

        prompt = f"""다음 YouTube 영상 제목에 맞는 최적화된 설명란 템플릿을 생성해주세요.

영상 제목: {title}
콘텐츠 스타일: {category_style.get(category, "일반적인 유튜브 영상")}

포함할 섹션:
{selected_sections}

다음 형식의 JSON으로 응답해주세요:
{{
  "description": "완성된 설명란 텍스트 (실제로 바로 사용 가능한 형태)",
  "hookLine": "첫 줄에 들어갈 훅 (검색 결과에 노출되는 부분)",
  "tips": ["설명란 작성 팁 1", "팁 2", ...]
}}

한국어로 작성해주세요. 설명란은 최소 500자 이상으로 작성하고, 검색 최적화를 고려해주세요."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 YouTube SEO 전문가입니다. 검색 최적화와 시청자 참여를 높이는 설명란을 작성합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        result_text = response.choices[0].message.content.strip()

        # JSON 파싱
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        result = json.loads(result_text)

        return jsonify({
            "success": True,
            "data": result,
            "message": "설명란 템플릿 생성 완료"
        })

    except json.JSONDecodeError as e:
        print(f"설명란 생성 JSON 파싱 오류: {e}")
        return jsonify({"success": False, "message": "결과 파싱 실패"}), 500
    except Exception as e:
        print(f"설명란 생성 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/keyword-trend', methods=['POST'])
def api_keyword_trend():
    """키워드 트렌드 분석 - 기간별 영상 수와 평균 조회수 비교"""
    try:
        data = request.get_json()
        keyword = data.get("keyword", "")
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        if not keyword:
            return jsonify({"success": False, "message": "키워드를 입력해주세요."}), 400

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]

        if not api_key:
            api_key = get_youtube_api_key()

        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 기간별 검색 (최근 7일, 30일, 90일)
        periods = [
            {"name": "7일", "days": 7},
            {"name": "30일", "days": 30},
            {"name": "90일", "days": 90}
        ]

        trend_data = []

        for period in periods:
            published_after = get_time_filter("day" if period["days"] == 1 else
                                              "week" if period["days"] == 7 else
                                              "month" if period["days"] == 30 else
                                              "3months")

            search_result = make_youtube_request("search", {
                "part": "snippet",
                "q": keyword,
                "type": "video",
                "maxResults": 20,
                "order": "date",
                "publishedAfter": published_after,
                "regionCode": "KR"
            }, api_key)

            video_count = len(search_result.get("items", []))

            # 조회수 분석
            avg_views = 0
            if video_count > 0:
                video_ids = [item["id"]["videoId"] for item in search_result.get("items", [])]
                videos_data = make_youtube_request("videos", {
                    "part": "statistics",
                    "id": ",".join(video_ids)
                }, api_key)

                total_views = sum(int(v.get("statistics", {}).get("viewCount", 0))
                                  for v in videos_data.get("items", []))
                avg_views = total_views // video_count if video_count > 0 else 0

            trend_data.append({
                "period": period["name"],
                "days": period["days"],
                "videoCount": video_count,
                "avgViews": avg_views,
                "videosPerDay": round(video_count / period["days"], 2)
            })

        # 트렌드 분석
        recent = trend_data[0]  # 7일
        older = trend_data[2]   # 90일

        trend_direction = "상승" if recent["videosPerDay"] > older["videosPerDay"] * 0.9 else "하락"
        trend_strength = "강함" if abs(recent["videosPerDay"] - older["videosPerDay"]) > older["videosPerDay"] * 0.3 else "보통"

        return jsonify({
            "success": True,
            "data": {
                "keyword": keyword,
                "trendData": trend_data,
                "trendDirection": trend_direction,
                "trendStrength": trend_strength,
                "recommendation": f"'{keyword}' 키워드는 현재 {trend_direction} 추세입니다. " +
                                 (f"경쟁이 {'치열' if recent['videosPerDay'] > 3 else '보통'} 하며, " +
                                  f"평균 조회수는 {recent['avgViews']:,}회 입니다.")
            },
            "message": f"'{keyword}' 키워드 트렌드 분석 완료"
        })

    except Exception as e:
        print(f"키워드 트렌드 분석 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/generate-ai-plan', methods=['POST'])
def api_generate_ai_plan():
    """AI 콘텐츠 기획 생성 - 떡상 영상 분석 및 기획 제안"""
    try:
        import json
        from openai import OpenAI

        data = request.get_json()

        video_id = data.get("videoId", "")
        title = data.get("title", "")
        description = data.get("description", "")[:1000]  # 최대 1000자
        channel_title = data.get("channelTitle", "")
        view_count = int(data.get("viewCount", 0))
        subscriber_count = int(data.get("subscriberCount", 1))
        like_count = int(data.get("likeCount", 0))
        comment_count = int(data.get("commentCount", 0))
        performance_value = float(data.get("performanceValue", 0))
        duration = data.get("duration", "")
        published_at = data.get("publishedAt", "")

        if not title:
            return jsonify({"success": False, "message": "영상 정보가 필요합니다."}), 400

        openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not openai_api_key:
            return jsonify({"success": False, "message": "OpenAI API 키가 설정되지 않았습니다."}), 400

        client = OpenAI(api_key=openai_api_key)

        # 성과 분석
        performance_desc = ""
        if performance_value >= 100:
            performance_desc = f"🔥 신의 간택! 구독자 대비 조회수가 무려 {int(performance_value)}배입니다!"
        elif performance_value >= 50:
            performance_desc = f"🚀 고성과 영상! 구독자 대비 조회수가 {int(performance_value)}배입니다."
        elif performance_value >= 10:
            performance_desc = f"👍 평균 이상의 성과! 구독자 대비 조회수가 {int(performance_value)}배입니다."
        else:
            performance_desc = f"📊 구독자 대비 조회수가 {performance_value:.2f}배입니다."

        prompt = f"""다음은 YouTube에서 높은 성과를 기록한 영상입니다. 이 영상을 분석하고 콘텐츠 기획 제안을 해주세요.

=== 영상 정보 ===
제목: {title}
채널: {channel_title}
조회수: {view_count:,}
구독자 수: {subscriber_count:,}
성과도 배율: {performance_value:.2f}배 ({performance_desc})
좋아요: {like_count:,}
댓글 수: {comment_count:,}
영상 길이: {duration}
게시일: {published_at}
URL: https://www.youtube.com/watch?v={video_id}

=== 영상 설명 ===
{description or '(없음)'}

=== 분석 요청 ===
다음 형식의 JSON으로 분석 결과를 제공해주세요:
{{
  "successFactors": [
    "이 영상이 터진 핵심 요인 1",
    "이 영상이 터진 핵심 요인 2",
    "이 영상이 터진 핵심 요인 3"
  ],
  "suggestedTitles": [
    "비슷한 스타일의 제목 제안 1",
    "비슷한 스타일의 제목 제안 2",
    "비슷한 스타일의 제목 제안 3"
  ],
  "thumbnailIdeas": [
    "클릭을 유도하는 썸네일 문구 1",
    "클릭을 유도하는 썸네일 문구 2"
  ],
  "hookScript": "초반 30초 후킹을 위한 멘트 예시 (3-5문장)",
  "contentIdeas": [
    "이 영상을 참고한 관련 콘텐츠 아이디어 1",
    "이 영상을 참고한 관련 콘텐츠 아이디어 2",
    "이 영상을 참고한 관련 콘텐츠 아이디어 3"
  ]
}}

한국어로 답변해주세요. 구체적이고 실제로 활용 가능한 내용으로 작성해주세요."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 YouTube 콘텐츠 기획 전문가입니다. 떡상 영상의 성공 요인을 분석하고, 유사한 성과를 낼 수 있는 콘텐츠 기획을 제안합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        result_text = response.choices[0].message.content.strip()

        # JSON 파싱
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        plan_data = json.loads(result_text)

        # 프롬프트도 함께 반환 (Gemini용)
        gemini_prompt = f"""다음은 YouTube에서 구독자 대비 {int(performance_value)}배의 조회수를 기록한 떡상 영상입니다.

=== 영상 정보 ===
제목: {title}
채널: {channel_title}
조회수: {view_count:,}
구독자 수: {subscriber_count:,}
성과도 배율: {performance_value:.2f}배
좋아요: {like_count:,}
댓글 수: {comment_count:,}
영상 길이: {duration}
URL: https://www.youtube.com/watch?v={video_id}

=== 영상 설명 ===
{description or '(없음)'}

=== 분석 요청 ===
이 영상이 터진 이유를 분석하고, 다음을 제공해주세요:

1. 이 영상이 터진 3가지 핵심 요인
2. 비슷한 스타일의 제목 3개 제안
3. 클릭을 유도하는 썸네일 문구 2개
4. 초반 30초 후킹을 위한 멘트 예시
5. 이 영상을 참고한 관련 콘텐츠 아이디어 3개"""

        plan_data["prompt"] = gemini_prompt

        return jsonify({
            "success": True,
            "data": plan_data,
            "message": "AI 콘텐츠 기획 생성 완료"
        })

    except json.JSONDecodeError as e:
        print(f"AI 기획 JSON 파싱 오류: {e}")
        return jsonify({"success": False, "message": "분석 결과 파싱 실패"}), 500
    except Exception as e:
        print(f"AI 기획 생성 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/transcript', methods=['POST'])
def api_get_transcript():
    """YouTube 영상 대본(자막) 추출 API - youtube-transcript-api v1.0+ 호환"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        data = request.get_json()
        video_id = data.get("videoId", "")
        language_codes = data.get("languages", ["ko", "ja", "en", "zh-Hans", "zh-Hant"])
        include_auto = data.get("includeAuto", True)

        if not video_id:
            return jsonify({"success": False, "message": "videoId가 필요합니다."}), 400

        # 영상 ID에서 URL 파라미터 제거
        if "&" in video_id:
            video_id = video_id.split("&")[0]

        # YouTubeTranscriptApi 인스턴스 생성 (v1.0+ API)
        ytt_api = YouTubeTranscriptApi()

        transcript_result = None
        used_language = None
        is_auto_generated = False

        try:
            # 자막 목록 조회 (v1.0+: .list() 메서드 사용)
            transcript_list = ytt_api.list(video_id)

            # 1. 수동 자막 우선 시도
            for lang_code in language_codes:
                try:
                    transcript = transcript_list.find_transcript([lang_code])
                    if not transcript.is_generated:
                        transcript_result = transcript.fetch()
                        used_language = lang_code
                        is_auto_generated = False
                        break
                except Exception:
                    continue

            # 2. 자동 생성 자막 시도
            if transcript_result is None and include_auto:
                for lang_code in language_codes:
                    try:
                        transcript = transcript_list.find_transcript([lang_code])
                        if transcript.is_generated:
                            transcript_result = transcript.fetch()
                            used_language = lang_code
                            is_auto_generated = True
                            break
                    except Exception:
                        continue

            # 3. 번역 자막 시도
            if transcript_result is None:
                try:
                    en_transcript = transcript_list.find_transcript(['en'])
                    for target_lang in ['ko', 'ja']:
                        try:
                            translated = en_transcript.translate(target_lang)
                            transcript_result = translated.fetch()
                            used_language = f"en→{target_lang}"
                            is_auto_generated = en_transcript.is_generated
                            break
                        except Exception:
                            continue
                except Exception:
                    pass

            # 4. 아무 자막이나 가져오기
            if transcript_result is None:
                try:
                    for transcript in transcript_list:
                        transcript_result = transcript.fetch()
                        used_language = transcript.language_code
                        is_auto_generated = transcript.is_generated
                        break
                except Exception:
                    pass

        except Exception as e:
            error_msg = str(e).lower()
            if "disabled" in error_msg:
                return jsonify({
                    "success": False,
                    "message": "이 영상은 자막이 비활성화되어 있습니다.",
                    "errorType": "disabled"
                }), 400
            elif "unavailable" in error_msg or "not exist" in error_msg:
                return jsonify({
                    "success": False,
                    "message": "영상을 찾을 수 없습니다.",
                    "errorType": "unavailable"
                }), 400
            elif "no transcript" in error_msg:
                return jsonify({
                    "success": False,
                    "message": "이 영상에는 자막이 없습니다.",
                    "errorType": "not_found"
                }), 400
            else:
                raise

        if transcript_result is None:
            return jsonify({
                "success": False,
                "message": "자막을 찾을 수 없습니다.",
                "errorType": "not_found"
            }), 400

        # v1.0+ FetchedTranscript 객체 처리
        full_text = ""
        segments = []

        # snippets 속성 또는 직접 이터레이션
        items = getattr(transcript_result, 'snippets', None) or transcript_result

        for entry in items:
            # FetchedTranscriptSnippet 객체 또는 dict 처리
            if hasattr(entry, 'text'):
                text = entry.text.strip()
                start = entry.start
                duration = entry.duration
            else:
                text = entry.get("text", "").strip()
                start = entry.get("start", 0)
                duration = entry.get("duration", 0)

            if text and not (text.startswith("[") and text.endswith("]")):
                segments.append({
                    "text": text,
                    "start": round(start, 2),
                    "duration": round(duration, 2)
                })
                full_text += text + " "

        full_text = full_text.strip()

        # 언어 정보 (FetchedTranscript에서 가져오기)
        if hasattr(transcript_result, 'language_code') and transcript_result.language_code:
            used_language = transcript_result.language_code
        if hasattr(transcript_result, 'is_generated'):
            is_auto_generated = transcript_result.is_generated

        char_count = len(full_text.replace(" ", ""))
        estimated_minutes = round(char_count / 300, 1)

        return jsonify({
            "success": True,
            "data": {
                "videoId": video_id,
                "language": used_language,
                "isAutoGenerated": is_auto_generated,
                "fullText": full_text,
                "segments": segments,
                "charCount": char_count,
                "estimatedMinutes": estimated_minutes,
                "segmentCount": len(segments)
            },
            "message": f"자막 추출 완료 ({used_language}, {'자동생성' if is_auto_generated else '수동'})"
        })

    except Exception as e:
        print(f"대본 추출 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"대본 추출 실패: {str(e)}"}), 500


# ===== 블루오션 카테고리 발굴 =====

def extract_keywords_from_videos(videos: List[Dict[str, Any]]) -> List[str]:
    """영상 제목에서 키워드 추출 (GPT 없이 간단한 방식)"""
    import re
    from collections import Counter

    all_words = []
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                  'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                  'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                  'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
                  'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
                  'through', 'during', 'before', 'after', 'above', 'below',
                  'between', 'under', 'again', 'further', 'then', 'once',
                  'here', 'there', 'when', 'where', 'why', 'how', 'all',
                  'each', 'few', 'more', 'most', 'other', 'some', 'such',
                  'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
                  'too', 'very', 'just', 'and', 'but', 'if', 'or', 'because',
                  'until', 'while', 'this', 'that', 'these', 'those', 'i',
                  'me', 'my', 'myself', 'we', 'our', 'ours', 'you', 'your',
                  'he', 'him', 'his', 'she', 'her', 'it', 'its', 'they',
                  'them', 'their', 'what', 'which', 'who', 'whom', 'shorts',
                  'video', 'new', 'official', 'full', '|', '-', '#', 'ep',
                  'episode', 'part', 'vol', 'vs', '&', 'feat', 'ft'}

    for video in videos:
        title = video.get('title', '').lower()
        # 특수문자 제거하고 단어 추출
        words = re.findall(r'[a-z가-힣]+', title)
        for word in words:
            if len(word) > 2 and word not in stop_words:
                all_words.append(word)

    # 빈도수 기반 상위 키워드
    word_counts = Counter(all_words)
    top_keywords = [word for word, count in word_counts.most_common(20) if count >= 2]

    return top_keywords


# 해외에서 인기 있는 니치 키워드 (블루오션 후보)
NICHE_KEYWORDS = {
    "US": [
        "stoicism", "adhd tips", "dopamine detox", "carnivore diet",
        "home gym", "biohacking", "sleep optimization", "cold plunge",
        "thrift flip", "van life", "tiny house", "off grid",
        "ai tools", "chatgpt tutorial", "midjourney", "stable diffusion",
        "true crime", "unsolved mystery", "creepypasta", "iceberg explained",
        "satisfying", "asmr", "oddly satisfying", "relaxing",
        "financial freedom", "side hustle", "passive income", "dropshipping",
        "manga recap", "anime recap", "manhwa", "webtoon",
        "90s nostalgia", "liminal spaces", "analog horror", "arg",
        "silent vlog", "study with me", "clean with me", "day in my life"
    ],
    "JP": [
        "vtuber", "hololive", "nijisanji", "voiceroid",
        "isekai", "narou", "light novel", "manga spoiler",
        "retro game", "famicom", "super famicom", "arcade",
        "japanese asmr", "ear cleaning", "whispering",
        "japan travel", "tokyo walk", "kyoto tour", "osaka food",
        "idol", "jpop", "city pop", "anime song",
        "otaku", "figure", "gunpla", "cosplay",
        "ramen", "sushi", "bento", "japanese cooking"
    ],
    "GB": [
        "british comedy", "uk drill", "grime",
        "premier league", "football highlights", "match analysis",
        "royal family", "british history", "castle tour",
        "pub culture", "british food", "full english",
        "london vlog", "uk travel", "scotland",
        "british slang", "cockney", "accent challenge"
    ],
    "DE": [
        "german lesson", "deutsch lernen", "german culture",
        "bundesliga", "german football",
        "german engineering", "made in germany",
        "berlin", "munich", "oktoberfest",
        "german history", "ww2 documentary", "cold war"
    ],
    "BR": [
        "funk brasileiro", "sertanejo", "pagode",
        "futebol brasileiro", "flamengo", "corinthians",
        "novela", "brazilian drama", "reality show",
        "brazil travel", "rio", "amazon",
        "brazilian food", "feijoada", "churrasco"
    ],
    "IN": [
        "bollywood", "south indian", "tollywood",
        "cricket", "ipl", "india match",
        "indian cooking", "curry recipe", "biryani",
        "indian wedding", "mehndi", "sangeet",
        "yoga", "meditation", "ayurveda",
        "indian history", "mythology", "mahabharata"
    ]
}


def calculate_blueocean_score(foreign_data: Dict, korea_data: Dict) -> float:
    """블루오션 점수 계산

    블루오션 = 해외에서 인기 있지만 한국에서 경쟁이 적은 시장

    점수 구성:
    - 해외 인기도 (40점): 해외 평균 조회수가 높을수록 +
    - 한국 희소성 (60점): 한국 채널이 적고, 조회수도 낮을수록 +

    핵심: 한국에 이미 많은 채널이 있고 조회수도 높으면 레드오션 (낮은 점수)
    """
    foreign_avg_views = foreign_data.get('avg_views', 0)
    korea_channel_count = korea_data.get('channel_count', 0)
    korea_avg_views = korea_data.get('avg_views', 0)

    # 1. 해외 인기도 점수 (0-40점)
    if foreign_avg_views >= 10_000_000:  # 1000만 이상
        popularity_score = 40
    elif foreign_avg_views >= 1_000_000:  # 100만 이상
        popularity_score = 30
    elif foreign_avg_views >= 100_000:  # 10만 이상
        popularity_score = 20
    else:
        popularity_score = 10

    # 2. 한국 희소성 점수 (0-60점)
    # 시작: 60점에서 채널수와 조회수에 따라 감점
    scarcity_score = 60

    # 2-1. 채널 수 감점 (최대 -30점)
    if korea_channel_count >= 50:
        scarcity_score -= 30  # 50개 이상 = 레드오션
    elif korea_channel_count >= 30:
        scarcity_score -= 25
    elif korea_channel_count >= 20:
        scarcity_score -= 20
    elif korea_channel_count >= 10:
        scarcity_score -= 15
    elif korea_channel_count >= 5:
        scarcity_score -= 5

    # 2-2. 한국 평균 조회수 감점 (최대 -30점)
    # 한국에서 이미 높은 조회수 = 레드오션
    if korea_avg_views >= 100_000_000:  # 1억 이상
        scarcity_score -= 30
    elif korea_avg_views >= 50_000_000:  # 5000만 이상
        scarcity_score -= 25
    elif korea_avg_views >= 10_000_000:  # 1000만 이상
        scarcity_score -= 20
    elif korea_avg_views >= 1_000_000:  # 100만 이상
        scarcity_score -= 10
    elif korea_avg_views >= 100_000:  # 10만 이상
        scarcity_score -= 5

    scarcity_score = max(0, scarcity_score)

    final_score = popularity_score + scarcity_score
    return round(final_score, 2)


@tubelens_bp.route('/api/tubelens/blueocean', methods=['POST'])
def api_blueocean():
    """블루오션 카테고리 발굴 API

    해외에서 인기있지만 한국에 아직 없는 카테고리를 찾습니다.
    """
    try:
        data = request.get_json()

        foreign_regions = data.get("foreignRegions", ["US"])  # 분석할 해외 국가
        video_type = data.get("videoType", "all")  # shorts, longform, all
        category_id = data.get("categoryId", "")  # YouTube 카테고리
        max_results = min(int(data.get("maxResults", 50)), 100)
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]
        if not api_key:
            api_key = get_youtube_api_key()
        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        results = []

        for region in foreign_regions:
            # 1. 해외 트렌딩 영상 수집
            try:
                trending_params = {
                    "part": "snippet",
                    "chart": "mostPopular",
                    "regionCode": region,
                    "maxResults": max_results
                }
                if category_id:
                    trending_params["videoCategoryId"] = category_id

                trending_data = make_youtube_request("videos", trending_params, api_key)
                foreign_video_ids = [item["id"] for item in trending_data.get("items", [])]

                if not foreign_video_ids:
                    continue

                # 상세 정보 가져오기
                foreign_videos = get_video_details(foreign_video_ids, api_key)

                # 영상 타입 필터링
                if video_type == "shorts":
                    foreign_videos = [v for v in foreign_videos if v["durationSeconds"] <= 60]
                elif video_type == "longform":
                    foreign_videos = [v for v in foreign_videos if v["durationSeconds"] > 60]

                if not foreign_videos:
                    continue

                # 2. 키워드 추출 (트렌딩에서 + 니치 키워드)
                extracted_keywords = extract_keywords_from_videos(foreign_videos)
                niche_keywords = NICHE_KEYWORDS.get(region, [])

                # 니치 키워드에서 랜덤 10개 선택 + 추출 키워드 5개
                import random
                selected_niche = random.sample(niche_keywords, min(10, len(niche_keywords))) if niche_keywords else []
                keywords = list(set(extracted_keywords[:5] + selected_niche))

                # 해외 통계
                foreign_avg_views = sum(v["viewCount"] for v in foreign_videos) / len(foreign_videos)
                foreign_total_views = sum(v["viewCount"] for v in foreign_videos)

                # 3. 각 키워드에 대해 해외/한국 검색 비교
                for keyword in keywords[:15]:  # 상위 15개 키워드
                    try:
                        # 해외에서 키워드 검색 (니치 키워드용)
                        foreign_search_params = {
                            "part": "snippet",
                            "type": "video",
                            "q": keyword,
                            "regionCode": region,
                            "maxResults": 20,
                            "order": "viewCount"
                        }
                        if video_type == "shorts":
                            foreign_search_params["videoDuration"] = "short"
                        elif video_type == "longform":
                            foreign_search_params["videoDuration"] = "medium"

                        foreign_search = make_youtube_request("search", foreign_search_params, api_key)
                        foreign_search_ids = [item["id"]["videoId"] for item in foreign_search.get("items", [])
                                              if item.get("id", {}).get("videoId")]

                        # 해외 키워드 검색 결과 상세 정보
                        foreign_keyword_videos = []
                        foreign_keyword_avg = 0
                        if foreign_search_ids:
                            foreign_keyword_videos = get_video_details(foreign_search_ids[:10], api_key)
                            if foreign_keyword_videos:
                                foreign_keyword_avg = sum(v["viewCount"] for v in foreign_keyword_videos) / len(foreign_keyword_videos)

                        # 해외에서 인기 없으면 스킵
                        if foreign_keyword_avg < 100000:  # 10만 미만이면 스킵
                            continue

                        # 한국 검색
                        korea_search_params = {
                            "part": "snippet",
                            "type": "video",
                            "q": keyword,
                            "regionCode": "KR",
                            "maxResults": 50,
                            "order": "viewCount"
                        }

                        if video_type == "shorts":
                            korea_search_params["videoDuration"] = "short"
                        elif video_type == "longform":
                            korea_search_params["videoDuration"] = "medium"

                        korea_search = make_youtube_request("search", korea_search_params, api_key)
                        korea_items = korea_search.get("items", [])

                        # 한국 채널 수 (고유 채널)
                        korea_channels = set()
                        korea_video_ids = []
                        for item in korea_items:
                            if item.get("id", {}).get("videoId"):
                                korea_video_ids.append(item["id"]["videoId"])
                                korea_channels.add(item["snippet"]["channelId"])

                        # 한국 영상 상세 정보
                        korea_videos = []
                        korea_avg_views = 0
                        if korea_video_ids:
                            korea_videos = get_video_details(korea_video_ids[:20], api_key)
                            if korea_videos:
                                korea_avg_views = sum(v["viewCount"] for v in korea_videos) / len(korea_videos)

                        # 4. 블루오션 점수 계산
                        foreign_data = {
                            "avg_views": foreign_keyword_avg,
                            "video_count": len(foreign_keyword_videos)
                        }
                        korea_data = {
                            "channel_count": len(korea_channels),
                            "video_count": len(korea_videos),
                            "avg_views": korea_avg_views
                        }

                        score = calculate_blueocean_score(foreign_data, korea_data)

                        # 블루오션 판정 (점수 30 이상이면 표시)
                        if score >= 30:
                            # 대표 영상 선택 (해외 키워드 검색 결과)
                            sample_videos = foreign_keyword_videos[:3]

                            results.append({
                                "keyword": keyword,
                                "region": region,
                                "blueoceanScore": score,
                                "foreignStats": {
                                    "avgViews": int(foreign_keyword_avg),
                                    "videoCount": len(foreign_keyword_videos),
                                    "totalViews": int(sum(v["viewCount"] for v in foreign_keyword_videos)) if foreign_keyword_videos else 0
                                },
                                "koreaStats": {
                                    "channelCount": len(korea_channels),
                                    "videoCount": len(korea_videos),
                                    "avgViews": int(korea_avg_views)
                                },
                                "sampleVideos": [{
                                    "videoId": v["videoId"],
                                    "title": v["title"],
                                    "thumbnail": v["thumbnail"],
                                    "viewCount": v["viewCount"],
                                    "channelTitle": v["channelTitle"]
                                } for v in sample_videos],
                                "recommendation": get_blueocean_recommendation(score, len(korea_channels))
                            })

                    except Exception as e:
                        print(f"키워드 '{keyword}' 분석 실패: {e}")
                        continue

            except Exception as e:
                print(f"지역 '{region}' 트렌딩 수집 실패: {e}")
                continue

        # 점수 순으로 정렬
        results.sort(key=lambda x: x["blueoceanScore"], reverse=True)

        # 중복 키워드 제거 (가장 높은 점수만 유지)
        seen_keywords = set()
        unique_results = []
        for r in results:
            if r["keyword"] not in seen_keywords:
                seen_keywords.add(r["keyword"])
                unique_results.append(r)

        return jsonify({
            "success": True,
            "data": unique_results[:20],  # 상위 20개
            "message": f"블루오션 카테고리 {len(unique_results)}개 발굴 완료"
        })

    except Exception as e:
        print(f"블루오션 분석 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


def get_blueocean_recommendation(score: float, korea_channels: int) -> str:
    """블루오션 점수에 따른 추천 메시지"""
    if score >= 80:
        return "🔥 초블루오션! 지금 바로 시작하세요"
    elif score >= 60:
        return "💎 매우 유망! 선점 효과 기대"
    elif score >= 40:
        return "✨ 유망! 차별화 전략 필요"
    elif score >= 30:
        if korea_channels < 5:
            return "🌱 진입 가능! 한국 채널 거의 없음"
        else:
            return "📊 검토 필요! 경쟁 분석 권장"
    else:
        return "⚠️ 레드오션 가능성"


@tubelens_bp.route('/api/tubelens/blueocean-deep', methods=['POST'])
def api_blueocean_deep():
    """블루오션 심층 분석 API

    특정 키워드에 대해 더 상세한 분석을 수행합니다.
    """
    try:
        data = request.get_json()

        keyword = data.get("keyword", "")
        foreign_region = data.get("foreignRegion", "US")
        video_type = data.get("videoType", "all")
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        if not keyword:
            return jsonify({"success": False, "message": "키워드가 필요합니다."}), 400

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]
        if not api_key:
            api_key = get_youtube_api_key()
        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 해외 검색
        foreign_params = {
            "part": "snippet",
            "type": "video",
            "q": keyword,
            "regionCode": foreign_region,
            "maxResults": 50,
            "order": "viewCount"
        }
        if video_type == "shorts":
            foreign_params["videoDuration"] = "short"
        elif video_type == "longform":
            foreign_params["videoDuration"] = "medium"

        foreign_search = make_youtube_request("search", foreign_params, api_key)
        foreign_video_ids = [item["id"]["videoId"] for item in foreign_search.get("items", [])
                           if item.get("id", {}).get("videoId")]
        foreign_videos = get_video_details(foreign_video_ids, api_key) if foreign_video_ids else []

        # 한국 검색
        korea_params = foreign_params.copy()
        korea_params["regionCode"] = "KR"

        korea_search = make_youtube_request("search", korea_params, api_key)
        korea_video_ids = [item["id"]["videoId"] for item in korea_search.get("items", [])
                         if item.get("id", {}).get("videoId")]
        korea_videos = get_video_details(korea_video_ids, api_key) if korea_video_ids else []

        # 채널 분석
        foreign_channels = {}
        for v in foreign_videos:
            ch_id = v["channelId"]
            if ch_id not in foreign_channels:
                foreign_channels[ch_id] = {
                    "title": v["channelTitle"],
                    "subscribers": v["subscriberCount"],
                    "videos": []
                }
            foreign_channels[ch_id]["videos"].append(v)

        korea_channels = {}
        for v in korea_videos:
            ch_id = v["channelId"]
            if ch_id not in korea_channels:
                korea_channels[ch_id] = {
                    "title": v["channelTitle"],
                    "subscribers": v["subscriberCount"],
                    "videos": []
                }
            korea_channels[ch_id]["videos"].append(v)

        # 통계 계산
        foreign_stats = {
            "totalVideos": len(foreign_videos),
            "totalChannels": len(foreign_channels),
            "avgViews": int(sum(v["viewCount"] for v in foreign_videos) / len(foreign_videos)) if foreign_videos else 0,
            "maxViews": max((v["viewCount"] for v in foreign_videos), default=0),
            "avgSubscribers": int(sum(v["subscriberCount"] for v in foreign_videos) / len(foreign_videos)) if foreign_videos else 0,
            "topVideos": sorted(foreign_videos, key=lambda x: x["viewCount"], reverse=True)[:5]
        }

        korea_stats = {
            "totalVideos": len(korea_videos),
            "totalChannels": len(korea_channels),
            "avgViews": int(sum(v["viewCount"] for v in korea_videos) / len(korea_videos)) if korea_videos else 0,
            "maxViews": max((v["viewCount"] for v in korea_videos), default=0),
            "avgSubscribers": int(sum(v["subscriberCount"] for v in korea_videos) / len(korea_videos)) if korea_videos else 0,
            "topVideos": sorted(korea_videos, key=lambda x: x["viewCount"], reverse=True)[:5]
        }

        # 블루오션 점수
        score = calculate_blueocean_score(
            {"avg_views": foreign_stats["avgViews"], "video_count": foreign_stats["totalVideos"]},
            {"channel_count": korea_stats["totalChannels"], "video_count": korea_stats["totalVideos"],
             "avg_views": korea_stats["avgViews"]}
        )

        # 경쟁 분석
        competition_level = "낮음" if korea_stats["totalChannels"] < 10 else "중간" if korea_stats["totalChannels"] < 30 else "높음"

        return jsonify({
            "success": True,
            "data": {
                "keyword": keyword,
                "foreignRegion": foreign_region,
                "videoType": video_type,
                "blueoceanScore": score,
                "recommendation": get_blueocean_recommendation(score, korea_stats["totalChannels"]),
                "competitionLevel": competition_level,
                "foreignStats": foreign_stats,
                "koreaStats": korea_stats,
                "gap": {
                    "viewsGap": foreign_stats["avgViews"] - korea_stats["avgViews"],
                    "channelGap": foreign_stats["totalChannels"] - korea_stats["totalChannels"],
                    "opportunityScore": round((foreign_stats["avgViews"] / max(korea_stats["avgViews"], 1)) *
                                             (1 / max(korea_stats["totalChannels"], 1)) * 100, 2)
                }
            },
            "message": f"'{keyword}' 심층 분석 완료"
        })

    except Exception as e:
        print(f"블루오션 심층 분석 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@tubelens_bp.route('/api/tubelens/my-channel-analysis', methods=['POST'])
def api_my_channel_analysis():
    """내 채널 경쟁력 분석 API

    내 채널이 블루오션인지 레드오션인지 분석하고,
    상위 경쟁 채널과 비교합니다.
    """
    try:
        data = request.get_json()

        channel_input = data.get("channelInput", "")  # 채널 URL 또는 ID
        api_keys = data.get("apiKeys", [])
        current_api_key_index = data.get("currentApiKeyIndex", 0)

        if not channel_input:
            return jsonify({"success": False, "message": "채널 URL 또는 ID가 필요합니다."}), 400

        # API 키 선택
        api_key = None
        if api_keys and len(api_keys) > current_api_key_index:
            api_key = api_keys[current_api_key_index]
        if not api_key:
            api_key = get_youtube_api_key()
        if not api_key:
            return jsonify({"success": False, "message": "API 키가 필요합니다."}), 400

        # 채널 ID 추출
        channel_id = None
        if "youtube.com" in channel_input or "youtu.be" in channel_input:
            # URL에서 채널 ID 추출
            if "/@" in channel_input:
                # 핸들 형식: youtube.com/@channelhandle
                handle = channel_input.split("/@")[1].split("/")[0].split("?")[0]
                # 핸들로 채널 검색
                search_result = make_youtube_request("search", {
                    "part": "snippet",
                    "type": "channel",
                    "q": handle,
                    "maxResults": 1
                }, api_key)
                if search_result.get("items"):
                    channel_id = search_result["items"][0]["snippet"]["channelId"]
            elif "/channel/" in channel_input:
                channel_id = channel_input.split("/channel/")[1].split("/")[0].split("?")[0]
            elif "/c/" in channel_input:
                custom_name = channel_input.split("/c/")[1].split("/")[0].split("?")[0]
                search_result = make_youtube_request("search", {
                    "part": "snippet",
                    "type": "channel",
                    "q": custom_name,
                    "maxResults": 1
                }, api_key)
                if search_result.get("items"):
                    channel_id = search_result["items"][0]["snippet"]["channelId"]
        else:
            # 직접 ID 또는 이름으로 검색
            if channel_input.startswith("UC"):
                channel_id = channel_input
            else:
                search_result = make_youtube_request("search", {
                    "part": "snippet",
                    "type": "channel",
                    "q": channel_input,
                    "maxResults": 1
                }, api_key)
                if search_result.get("items"):
                    channel_id = search_result["items"][0]["snippet"]["channelId"]

        if not channel_id:
            return jsonify({"success": False, "message": "채널을 찾을 수 없습니다."}), 404

        # 1. 내 채널 정보 가져오기
        channel_info = make_youtube_request("channels", {
            "part": "snippet,statistics,brandingSettings",
            "id": channel_id
        }, api_key)

        if not channel_info.get("items"):
            return jsonify({"success": False, "message": "채널 정보를 가져올 수 없습니다."}), 404

        my_channel = channel_info["items"][0]
        my_stats = {
            "channelId": channel_id,
            "title": my_channel["snippet"]["title"],
            "description": my_channel["snippet"].get("description", ""),
            "thumbnail": my_channel["snippet"]["thumbnails"]["default"]["url"],
            "subscriberCount": int(my_channel["statistics"].get("subscriberCount", 0)),
            "videoCount": int(my_channel["statistics"].get("videoCount", 0)),
            "viewCount": int(my_channel["statistics"].get("viewCount", 0)),
            "country": my_channel["snippet"].get("country", "KR")
        }

        # 2. 내 채널의 최근 영상 가져오기 (키워드 추출용)
        playlist_id = "UU" + channel_id[2:]  # 업로드 플레이리스트
        playlist_items = make_youtube_request("playlistItems", {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": 20
        }, api_key)

        my_video_ids = [item["snippet"]["resourceId"]["videoId"]
                       for item in playlist_items.get("items", [])
                       if item["snippet"]["resourceId"]["kind"] == "youtube#video"]

        my_videos = get_video_details(my_video_ids, api_key) if my_video_ids else []

        # 내 채널 평균 조회수
        my_avg_views = sum(v["viewCount"] for v in my_videos) / len(my_videos) if my_videos else 0
        my_max_views = max((v["viewCount"] for v in my_videos), default=0)

        # 3. 키워드 추출 (카테고리 파악)
        import re
        from collections import Counter

        all_words = []
        for video in my_videos:
            title = video.get('title', '').lower()
            # 한글 단어도 추출
            words = re.findall(r'[a-z가-힣]{2,}', title)
            all_words.extend(words)

        # 불용어 제거
        stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all',
                      'can', 'her', 'was', 'one', 'our', 'out', 'this', 'that',
                      '그리고', '하지만', '그래서', '그런데', '이것', '저것', '우리',
                      '오늘', '지금', '영상', '채널', '구독', '좋아요', '시청'}
        filtered_words = [w for w in all_words if w not in stop_words]
        word_counts = Counter(filtered_words)
        top_keywords = [word for word, count in word_counts.most_common(5)]

        # 카테고리 감지 (뉴스 키워드 체크)
        news_keywords = {'뉴스', 'news', '속보', '정치', '경제', '사회', '이슈', '논란',
                         '대통령', '국회', '정부', '장관', '기자', '보도', '취재'}
        is_news = bool(set(filtered_words) & news_keywords)
        detected_category = "뉴스/시사" if is_news else "일반"

        # 4. 경쟁 채널 검색 (한국에서 같은 카테고리)
        search_query = " ".join(top_keywords[:3]) if top_keywords else my_stats["title"]

        competitor_search = make_youtube_request("search", {
            "part": "snippet",
            "type": "channel",
            "q": search_query,
            "regionCode": "KR",
            "maxResults": 20,
            "order": "relevance"
        }, api_key)

        competitor_ids = [item["snippet"]["channelId"]
                         for item in competitor_search.get("items", [])
                         if item["snippet"]["channelId"] != channel_id][:10]

        # 경쟁 채널 상세 정보
        competitors = []
        if competitor_ids:
            comp_info = make_youtube_request("channels", {
                "part": "snippet,statistics",
                "id": ",".join(competitor_ids)
            }, api_key)

            for ch in comp_info.get("items", []):
                comp_channel_id = ch["id"]
                # 경쟁 채널의 최근 영상 조회수 가져오기
                comp_playlist_id = "UU" + comp_channel_id[2:]
                comp_playlist = make_youtube_request("playlistItems", {
                    "part": "snippet",
                    "playlistId": comp_playlist_id,
                    "maxResults": 10
                }, api_key)
                comp_video_ids = [item["snippet"]["resourceId"]["videoId"]
                                  for item in comp_playlist.get("items", [])
                                  if item["snippet"]["resourceId"]["kind"] == "youtube#video"]
                comp_videos = get_video_details(comp_video_ids[:5], api_key) if comp_video_ids else []
                comp_avg_views = sum(v["viewCount"] for v in comp_videos) / len(comp_videos) if comp_videos else 0

                # 채널 생성일 파싱
                published_at = ch["snippet"].get("publishedAt", "")
                created_date = published_at[:10] if published_at else "알 수 없음"

                # 업로드 주기 계산 (최근 10개 영상 기준)
                upload_frequency = "알 수 없음"
                if len(comp_videos) >= 2:
                    from datetime import datetime
                    dates = []
                    for v in comp_videos:
                        try:
                            d = datetime.fromisoformat(v["publishedAt"].replace("Z", "+00:00"))
                            dates.append(d)
                        except:
                            pass
                    if len(dates) >= 2:
                        dates.sort(reverse=True)
                        total_days = (dates[0] - dates[-1]).days
                        if total_days > 0:
                            avg_days = total_days / (len(dates) - 1)
                            if avg_days <= 1:
                                upload_frequency = "매일"
                            elif avg_days <= 3:
                                upload_frequency = f"주 {int(7/avg_days)}회"
                            elif avg_days <= 7:
                                upload_frequency = "주 1회"
                            elif avg_days <= 14:
                                upload_frequency = "2주 1회"
                            elif avg_days <= 30:
                                upload_frequency = "월 1회"
                            else:
                                upload_frequency = f"{int(avg_days)}일마다"

                competitors.append({
                    "channelId": comp_channel_id,
                    "title": ch["snippet"]["title"],
                    "thumbnail": ch["snippet"]["thumbnails"]["default"]["url"],
                    "subscriberCount": int(ch["statistics"].get("subscriberCount", 0)),
                    "videoCount": int(ch["statistics"].get("videoCount", 0)),
                    "viewCount": int(ch["statistics"].get("viewCount", 0)),
                    "avgRecentViews": int(comp_avg_views),
                    "createdDate": created_date,
                    "uploadFrequency": upload_frequency,
                    "topVideo": comp_videos[0] if comp_videos else None
                })

        # 구독자 순으로 정렬
        competitors.sort(key=lambda x: x["subscriberCount"], reverse=True)

        # 5. 경쟁력 분석
        total_competitor_subs = sum(c["subscriberCount"] for c in competitors)
        avg_competitor_subs = total_competitor_subs / len(competitors) if competitors else 0
        avg_competitor_views = sum(c["avgRecentViews"] for c in competitors) / len(competitors) if competitors else 0

        # 내 위치 (순위)
        my_rank = 1
        for comp in competitors:
            if comp["subscriberCount"] > my_stats["subscriberCount"]:
                my_rank += 1

        # 경쟁 강도 점수 (0-100, 높을수록 경쟁 치열)
        competition_intensity = 0

        # 경쟁 채널 수에 따른 점수
        if len(competitors) >= 10:
            competition_intensity += 30
        elif len(competitors) >= 5:
            competition_intensity += 20
        else:
            competition_intensity += 10

        # 상위 채널 구독자 수에 따른 점수
        if competitors and competitors[0]["subscriberCount"] >= 1000000:
            competition_intensity += 30
        elif competitors and competitors[0]["subscriberCount"] >= 100000:
            competition_intensity += 20
        elif competitors and competitors[0]["subscriberCount"] >= 10000:
            competition_intensity += 10

        # 평균 조회수 격차에 따른 점수
        if avg_competitor_views > 0 and my_avg_views > 0:
            view_ratio = avg_competitor_views / my_avg_views
            if view_ratio >= 10:
                competition_intensity += 40
            elif view_ratio >= 5:
                competition_intensity += 30
            elif view_ratio >= 2:
                competition_intensity += 20
            else:
                competition_intensity += 10

        competition_intensity = min(100, competition_intensity)

        # 시장 상태 판정
        if competition_intensity >= 70:
            market_status = "레드오션"
            market_color = "#dc2626"
            market_advice = "경쟁이 매우 치열합니다. 차별화된 콘텐츠 전략이 필요합니다."
        elif competition_intensity >= 50:
            market_status = "경쟁 시장"
            market_color = "#f59e0b"
            market_advice = "적당한 경쟁이 있습니다. 니치한 주제로 차별화하세요."
        elif competition_intensity >= 30:
            market_status = "성장 시장"
            market_color = "#10b981"
            market_advice = "성장 가능성이 있습니다. 꾸준한 업로드가 중요합니다."
        else:
            market_status = "블루오션"
            market_color = "#0ea5e9"
            market_advice = "경쟁이 적습니다. 선점 효과를 노려보세요!"

        # 6. 성장 팁 생성
        growth_tips = []
        if my_avg_views < avg_competitor_views:
            growth_tips.append({
                "type": "조회수",
                "tip": f"평균 조회수가 경쟁 채널 대비 낮습니다. 제목과 썸네일 최적화를 고려하세요.",
                "myValue": int(my_avg_views),
                "avgValue": int(avg_competitor_views)
            })
        if my_stats["subscriberCount"] < avg_competitor_subs:
            growth_tips.append({
                "type": "구독자",
                "tip": f"구독 유도 CTA를 영상에 추가하고, 커뮤니티 탭을 활용하세요.",
                "myValue": my_stats["subscriberCount"],
                "avgValue": int(avg_competitor_subs)
            })

        # 7. 성장 예측 (경쟁 채널 데이터 기반)
        growth_prediction = {
            "disclaimer": "경쟁 채널 데이터를 기반으로 한 예측이며, 실제 결과는 다를 수 있습니다.",
            "scenarios": []
        }

        # 업로드 주기별 성과 분석
        frequency_performance = {}
        for comp in competitors:
            freq = comp.get("uploadFrequency", "알 수 없음")
            if freq != "알 수 없음" and comp["avgRecentViews"] > 0:
                if freq not in frequency_performance:
                    frequency_performance[freq] = []
                frequency_performance[freq].append({
                    "views": comp["avgRecentViews"],
                    "subs": comp["subscriberCount"]
                })

        # 각 시나리오에 대한 예측
        scenarios = [
            {"frequency": "매일", "videos_per_month": 30},
            {"frequency": "주 3회", "videos_per_month": 12},
            {"frequency": "주 1회", "videos_per_month": 4},
        ]

        for scenario in scenarios:
            # 비슷한 업로드 주기 채널들의 평균 조회수 찾기
            matching_perfs = []
            for freq, perfs in frequency_performance.items():
                if "매일" in freq and "매일" in scenario["frequency"]:
                    matching_perfs.extend(perfs)
                elif "주" in freq and "주" in scenario["frequency"]:
                    matching_perfs.extend(perfs)

            # 없으면 전체 평균 사용
            if not matching_perfs:
                expected_views = int(avg_competitor_views * 0.7)  # 경쟁자 평균의 70%로 보수적 예측
            else:
                expected_views = int(sum(p["views"] for p in matching_perfs) / len(matching_perfs) * 0.7)

            # 월간 예상 조회수
            monthly_views = expected_views * scenario["videos_per_month"]

            # 구독 전환율 (업계 평균 1-2%)
            conversion_rate = 0.015
            monthly_new_subs = int(monthly_views * conversion_rate)

            # 목표 도달 예측 (10만 구독자)
            current_subs = my_stats["subscriberCount"]
            target_subs = 100000
            if monthly_new_subs > 0:
                months_to_100k = max(0, (target_subs - current_subs) / monthly_new_subs)
            else:
                months_to_100k = -1  # 계산 불가

            growth_prediction["scenarios"].append({
                "frequency": scenario["frequency"],
                "videosPerMonth": scenario["videos_per_month"],
                "expectedViewsPerVideo": expected_views,
                "monthlyViews": monthly_views,
                "monthlyNewSubs": monthly_new_subs,
                "monthsTo100k": round(months_to_100k, 1) if months_to_100k >= 0 else "계산 불가",
                "yearlyViews": monthly_views * 12,
                "yearlyNewSubs": monthly_new_subs * 12
            })

        # 현재 채널과 상위 채널 비교
        if competitors:
            top_channel = competitors[0]
            growth_prediction["comparison"] = {
                "topChannelName": top_channel["title"],
                "topChannelSubs": top_channel["subscriberCount"],
                "topChannelViews": top_channel["avgRecentViews"],
                "topChannelFrequency": top_channel.get("uploadFrequency", "알 수 없음"),
                "viewsGap": top_channel["avgRecentViews"] - int(my_avg_views),
                "subsGap": top_channel["subscriberCount"] - my_stats["subscriberCount"]
            }

        return jsonify({
            "success": True,
            "data": {
                "myChannel": {
                    **my_stats,
                    "avgRecentViews": int(my_avg_views),
                    "maxRecentViews": int(my_max_views),
                    "recentVideos": my_videos[:5]
                },
                "detectedCategory": detected_category,
                "topKeywords": top_keywords,
                "searchQuery": search_query,
                "competitors": competitors[:10],
                "analysis": {
                    "competitionIntensity": competition_intensity,
                    "marketStatus": market_status,
                    "marketColor": market_color,
                    "marketAdvice": market_advice,
                    "myRank": my_rank,
                    "totalCompetitors": len(competitors),
                    "avgCompetitorSubs": int(avg_competitor_subs),
                    "avgCompetitorViews": int(avg_competitor_views)
                },
                "growthTips": growth_tips,
                "growthPrediction": growth_prediction
            },
            "message": f"'{my_stats['title']}' 채널 분석 완료"
        })

    except Exception as e:
        print(f"채널 분석 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


# =====================================================
# YouTube Shorts → 이미지 프롬프트 생성 API
# =====================================================

def download_shorts_video(video_id: str, output_dir: str) -> tuple:
    """yt-dlp Python 라이브러리로 YouTube Shorts 다운로드

    Returns:
        tuple: (video_path, error_message)
               성공 시: (경로, None)
               실패 시: (None, 에러메시지)
    """
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")
    cookies_file = None

    try:
        import yt_dlp

        base_opts = {
            'format': 'best[height<=1080]',
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'geo_bypass': True,
            'socket_timeout': 30,
        }

        url = f"https://www.youtube.com/shorts/{video_id}"

        # YouTube 쿠키 설정 (환경변수에서 읽기)
        youtube_cookies = os.getenv("YOUTUBE_COOKIES", "")
        if youtube_cookies:
            cookies_file = os.path.join(output_dir, "cookies.txt")
            with open(cookies_file, "w") as f:
                f.write(youtube_cookies)
            cookie_lines = youtube_cookies.strip().split('\n')
            print(f"[SHORTS] 쿠키 파일 준비: {len(cookie_lines)}줄")

        # 다양한 클라이언트 전략 시도
        strategies = [
            # 전략 1: iOS 클라이언트 (쿠키 없이)
            {
                'name': 'iOS',
                'opts': {
                    **base_opts,
                    'extractor_args': {'youtube': {'player_client': ['ios']}},
                    'http_headers': {'User-Agent': 'com.google.ios.youtube/19.09.3 (iPhone14,3; U; CPU iOS 17_4 like Mac OS X)'},
                }
            },
            # 전략 2: TV Embed 클라이언트 (봇 감지 우회에 효과적)
            {
                'name': 'TV Embed',
                'opts': {
                    **base_opts,
                    'extractor_args': {'youtube': {'player_client': ['tv_embedded']}},
                }
            },
            # 전략 3: Android 클라이언트
            {
                'name': 'Android',
                'opts': {
                    **base_opts,
                    'extractor_args': {'youtube': {'player_client': ['android']}},
                    'http_headers': {'User-Agent': 'com.google.android.youtube/19.09.37 (Linux; U; Android 12; Pixel 6)'},
                }
            },
            # 전략 4: Mobile Web 클라이언트
            {
                'name': 'Mobile Web',
                'opts': {
                    **base_opts,
                    'extractor_args': {'youtube': {'player_client': ['mweb']}},
                    'http_headers': {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'},
                }
            },
        ]

        # 쿠키가 있으면 쿠키 버전 전략도 추가
        if cookies_file:
            strategies.append({
                'name': 'Web + Cookies',
                'opts': {
                    **base_opts,
                    'cookiefile': cookies_file,
                    'extractor_args': {'youtube': {'player_client': ['web']}},
                }
            })
            strategies.append({
                'name': 'iOS + Cookies',
                'opts': {
                    **base_opts,
                    'cookiefile': cookies_file,
                    'extractor_args': {'youtube': {'player_client': ['ios']}},
                }
            })

        for strategy in strategies:
            print(f"[SHORTS] 다운로드 시도 ({strategy['name']}): {url}")
            try:
                with yt_dlp.YoutubeDL(strategy['opts']) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if info:
                        for ext in ['mp4', 'webm', 'mkv']:
                            check_path = os.path.join(output_dir, f"{video_id}.{ext}")
                            if os.path.exists(check_path):
                                print(f"[SHORTS] {strategy['name']} 클라이언트로 다운로드 완료!")
                                return (check_path, None)
            except Exception as e:
                error_msg = str(e)
                # 봇 감지가 아닌 다른 에러면 바로 반환
                if "Sign in to confirm" not in error_msg and "bot" not in error_msg.lower():
                    if "Private video" in error_msg:
                        return (None, "비공개 영상입니다")
                    elif "Video unavailable" in error_msg:
                        return (None, "영상을 찾을 수 없습니다")
                    elif "age" in error_msg.lower():
                        return (None, "연령 제한 영상입니다")
                print(f"[SHORTS] {strategy['name']} 실패: {error_msg[:80]}...")

        # 파일 검색 (다운로드되었지만 감지 못한 경우)
        import glob
        files = glob.glob(os.path.join(output_dir, f"{video_id}.*"))
        video_files = [f for f in files if f.endswith(('.mp4', '.webm', '.mkv'))]
        if video_files:
            print(f"[SHORTS] 다운로드 완료: {video_files[0]}")
            return (video_files[0], None)

        # Fallback: cobalt.tools API 사용
        print(f"[SHORTS] yt-dlp 실패, cobalt.tools API로 시도...")
        try:
            import requests

            # YouTube 표준 URL 형식으로 변환
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"

            cobalt_response = requests.post(
                "https://api.cobalt.tools/",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={
                    "url": youtube_url,
                    "videoQuality": "720",
                    "filenameStyle": "basic",
                },
                timeout=30
            )

            print(f"[SHORTS] cobalt.tools 응답: {cobalt_response.status_code}")

            if cobalt_response.status_code == 200:
                cobalt_data = cobalt_response.json()
                print(f"[SHORTS] cobalt.tools 데이터: status={cobalt_data.get('status')}")

                if cobalt_data.get("status") in ["tunnel", "redirect", "stream"]:
                    download_url = cobalt_data.get("url")
                    if download_url:
                        print(f"[SHORTS] cobalt.tools에서 다운로드 URL 획득")
                        # 파일 다운로드
                        video_response = requests.get(download_url, timeout=120, stream=True)
                        if video_response.status_code == 200:
                            output_path = os.path.join(output_dir, f"{video_id}.mp4")
                            with open(output_path, "wb") as f:
                                for chunk in video_response.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                                print(f"[SHORTS] cobalt.tools로 다운로드 완료: {output_path}")
                                return (output_path, None)
                elif cobalt_data.get("status") == "error":
                    error_info = cobalt_data.get("error", {})
                    print(f"[SHORTS] cobalt.tools 에러: {error_info}")
                elif cobalt_data.get("status") == "picker":
                    # 여러 스트림 선택 필요한 경우
                    picker = cobalt_data.get("picker", [])
                    if picker:
                        download_url = picker[0].get("url")
                        if download_url:
                            print(f"[SHORTS] cobalt.tools picker에서 첫 번째 옵션 선택")
                            video_response = requests.get(download_url, timeout=120, stream=True)
                            if video_response.status_code == 200:
                                output_path = os.path.join(output_dir, f"{video_id}.mp4")
                                with open(output_path, "wb") as f:
                                    for chunk in video_response.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                                    print(f"[SHORTS] cobalt.tools로 다운로드 완료: {output_path}")
                                    return (output_path, None)
            else:
                # 에러 응답 내용 로깅
                try:
                    error_body = cobalt_response.json()
                    print(f"[SHORTS] cobalt.tools 에러 응답: {error_body}")
                except:
                    print(f"[SHORTS] cobalt.tools 에러: {cobalt_response.status_code}, {cobalt_response.text[:200]}")
        except Exception as cobalt_error:
            print(f"[SHORTS] cobalt.tools 실패: {cobalt_error}")

        print(f"[SHORTS] 모든 다운로드 전략 실패")
        return (None, "YouTube 봇 감지로 모든 다운로드 방식이 차단되었습니다. 잠시 후 다시 시도해주세요.")

    except Exception as e:
        error_str = str(e)
        print(f"[SHORTS] 다운로드 오류: {error_str}")
        import traceback
        traceback.print_exc()

        # 에러 타입에 따른 메시지 분류
        if "Sign in to confirm" in error_str or "bot" in error_str.lower():
            return (None, "YouTube 봇 감지로 차단되었습니다. YOUTUBE_COOKIES 환경변수를 업데이트해주세요.")
        elif "Private video" in error_str:
            return (None, "비공개 영상입니다")
        elif "Video unavailable" in error_str:
            return (None, "영상을 찾을 수 없습니다")
        elif "age" in error_str.lower():
            return (None, "연령 제한 영상입니다. 로그인이 필요합니다.")
        else:
            return (None, f"다운로드 실패: {error_str[:100]}")


def extract_frames_by_scene(video_path: str, output_dir: str, threshold: float = 0.3) -> List[Dict[str, Any]]:
    """FFmpeg로 씬 변경 감지하여 프레임 추출 (씬 기반)"""
    frames = []

    try:
        # 영상 길이 확인
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", video_path
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        probe_data = json.loads(probe_result.stdout)
        duration = float(probe_data.get("format", {}).get("duration", 60))

        print(f"[SHORTS] 영상 길이: {duration:.1f}초, 씬 감지 임계값: {threshold}")

        # 첫 프레임은 항상 포함
        first_frame_path = os.path.join(output_dir, "frame_000.jpg")
        cmd_first = [
            "ffmpeg", "-y",
            "-ss", "0",
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            first_frame_path
        ]
        subprocess.run(cmd_first, capture_output=True, text=True, timeout=30)

        if os.path.exists(first_frame_path):
            frames.append({
                "index": 0,
                "time": 0.0,
                "path": first_frame_path
            })

        # 씬 변경 감지하여 프레임 추출
        # select 필터: 씬 변화가 threshold 이상일 때만 프레임 선택
        # showinfo 필터: 타임스탬프 정보 출력
        scene_frames_pattern = os.path.join(output_dir, "scene_%03d.jpg")

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"select='gt(scene,{threshold})',showinfo",
            "-vsync", "vfr",
            "-q:v", "2",
            scene_frames_pattern
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        # showinfo 출력에서 타임스탬프 추출
        # 형식: [Parsed_showinfo_1 @ 0x...] n:   1 pts:  12345 pts_time:3.456
        import re
        timestamps = []
        for line in result.stderr.split('\n'):
            match = re.search(r'pts_time:(\d+\.?\d*)', line)
            if match:
                timestamps.append(float(match.group(1)))

        # 추출된 씬 프레임들 정리
        frame_index = 1
        for i, ts in enumerate(timestamps):
            scene_path = os.path.join(output_dir, f"scene_{i+1:03d}.jpg")
            if os.path.exists(scene_path):
                # 파일명 통일
                new_path = os.path.join(output_dir, f"frame_{frame_index:03d}.jpg")
                os.rename(scene_path, new_path)
                frames.append({
                    "index": frame_index,
                    "time": round(ts, 1),
                    "path": new_path
                })
                frame_index += 1

        # 씬이 거의 없는 경우 (단일 씬 영상) 중간 프레임 추가
        if len(frames) < 3 and duration > 10:
            print(f"[SHORTS] 씬 변화 적음, 추가 프레임 샘플링...")
            mid_times = [duration * 0.33, duration * 0.66]
            for t in mid_times:
                extra_path = os.path.join(output_dir, f"frame_{frame_index:03d}.jpg")
                cmd_extra = [
                    "ffmpeg", "-y",
                    "-ss", str(t),
                    "-i", video_path,
                    "-vframes", "1",
                    "-q:v", "2",
                    extra_path
                ]
                subprocess.run(cmd_extra, capture_output=True, text=True, timeout=30)
                if os.path.exists(extra_path):
                    frames.append({
                        "index": frame_index,
                        "time": round(t, 1),
                        "path": extra_path
                    })
                    frame_index += 1

        # 시간순 정렬
        frames.sort(key=lambda x: x["time"])
        for i, f in enumerate(frames):
            f["index"] = i

        print(f"[SHORTS] 씬 기반 프레임 추출 완료: {len(frames)}개")
        return frames

    except Exception as e:
        print(f"[SHORTS] 프레임 추출 오류: {e}")
        import traceback
        traceback.print_exc()
        return frames


def extract_frames_by_interval(video_path: str, output_dir: str, interval: int = 5) -> List[Dict[str, Any]]:
    """FFmpeg로 N초 간격으로 프레임 추출 (시간 기반)"""
    frames = []

    try:
        # 영상 길이 확인
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", video_path
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        probe_data = json.loads(probe_result.stdout)
        duration = float(probe_data.get("format", {}).get("duration", 60))

        print(f"[SHORTS] 영상 길이: {duration:.1f}초, 간격: {interval}초")

        # N초 간격으로 프레임 추출
        current_time = 0
        frame_index = 0

        while current_time < duration:
            frame_path = os.path.join(output_dir, f"frame_{frame_index:03d}.jpg")

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(current_time),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                frame_path
            ]

            subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if os.path.exists(frame_path):
                frames.append({
                    "index": frame_index,
                    "time": current_time,
                    "path": frame_path
                })
                frame_index += 1

            current_time += interval

        print(f"[SHORTS] 시간 기반 프레임 추출 완료: {len(frames)}개")
        return frames

    except Exception as e:
        print(f"[SHORTS] 프레임 추출 오류: {e}")
        return frames


def analyze_frame_with_gemini(frame_path: str) -> Optional[str]:
    """OpenRouter Gemini Vision으로 프레임 분석"""
    try:
        import requests
        import PIL.Image
        import io

        # OpenRouter API 키 설정
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print("[SHORTS] OpenRouter API 키가 없습니다")
            return None

        # 이미지 로드 및 base64 인코딩
        image = PIL.Image.open(frame_path)

        with open(frame_path, "rb") as f:
            image_bytes = f.read()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        # 이미지 포맷 감지
        img_format = image.format or 'PNG'
        mime_type = f"image/{img_format.lower()}"
        if img_format.upper() == 'JPG':
            mime_type = 'image/jpeg'

        prompt = """이 이미지를 분석하여 이미지 생성 AI에 사용할 프롬프트를 만들어주세요.

다음 요소들을 포함해주세요:
- 주요 피사체 (사람, 물체, 장면)
- 배경 및 환경
- 조명 스타일
- 색감 및 분위기
- 카메라 앵글/구도

응답 형식: 영어로 된 이미지 생성 프롬프트만 출력 (설명 없이)
예시: "Young woman in casual outfit, urban cafe background, natural window lighting, warm color palette, medium shot, candid moment"
"""

        # OpenRouter API 호출
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.7
            },
            timeout=30
        )

        if response.status_code == 200:
            response_data = response.json()
            content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                return content.strip()

        print(f"[SHORTS] OpenRouter API 오류: {response.status_code} - {response.text}")
        return None

    except Exception as e:
        print(f"[SHORTS] OpenRouter 분석 오류: {e}")
        return None


def refine_prompt_with_gpt(raw_prompt: str, context: str = "") -> Optional[str]:
    """GPT로 프롬프트 정제 (선택적)"""
    try:
        client = OpenAI()

        system_prompt = """You are an expert at creating image generation prompts.
Refine the given prompt to be more specific and effective for AI image generation.
Keep it concise (under 100 words) and in English.
Focus on visual elements, style, lighting, and composition.
Output only the refined prompt, nothing else."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Refine this prompt:\n{raw_prompt}\n\nContext: {context}"}
            ],
            temperature=0.7,
            max_tokens=200
        )

        if response.choices:
            return response.choices[0].message.content.strip()

        return raw_prompt

    except Exception as e:
        print(f"[SHORTS] GPT 정제 오류: {e}")
        return raw_prompt


@tubelens_bp.route('/api/tubelens/shorts-to-prompts', methods=['POST'])
def shorts_to_prompts():
    """YouTube Shorts URL을 분석하여 씬별 이미지 프롬프트 생성

    Request:
        {
            "url": "https://youtube.com/shorts/xxx",
            "mode": "scene",  // "scene" (씬 기반, 기본값) 또는 "interval" (시간 기반)
            "interval": 5,    // 시간 기반 모드일 때 초 단위 (기본값: 5)
            "threshold": 0.3, // 씬 기반 모드일 때 감지 민감도 (0.1~0.5, 낮을수록 민감)
            "refine": false   // GPT로 프롬프트 정제 여부 (기본값: false)
        }

    Response:
        {
            "success": true,
            "videoId": "xxx",
            "duration": 58,
            "mode": "scene",
            "prompts": [
                {"time": 0, "prompt": "..."},
                {"time": 3.5, "prompt": "..."}
            ]
        }
    """
    temp_dir = None

    try:
        data = request.get_json() or {}
        url = data.get("url", "")
        mode = data.get("mode", "scene")  # 기본값: 씬 기반
        interval = int(data.get("interval", 5))
        threshold = float(data.get("threshold", 0.3))
        refine = data.get("refine", False)

        # 파라미터 제한
        interval = max(2, min(30, interval))
        threshold = max(0.1, min(0.5, threshold))

        # Video ID 추출
        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({
                "success": False,
                "message": "유효한 YouTube Shorts URL이 아닙니다"
            }), 400

        print(f"[SHORTS] 분석 시작: {video_id}, 모드: {mode}")

        # 임시 디렉토리 생성
        temp_dir = tempfile.mkdtemp(prefix="shorts_")

        # 1. 영상 다운로드
        print(f"[SHORTS] 영상 다운로드 중...")
        video_path, download_error = download_shorts_video(video_id, temp_dir)

        if not video_path:
            return jsonify({
                "success": False,
                "message": download_error or "영상 다운로드에 실패했습니다."
            }), 400

        # 2. 프레임 추출 (모드에 따라 다른 방식 사용)
        print(f"[SHORTS] 프레임 추출 중... (모드: {mode})")
        if mode == "interval":
            frames = extract_frames_by_interval(video_path, temp_dir, interval)
        else:
            frames = extract_frames_by_scene(video_path, temp_dir, threshold)

        if not frames:
            return jsonify({
                "success": False,
                "message": "프레임 추출에 실패했습니다"
            }), 500

        # 3. 각 프레임 분석
        print(f"[SHORTS] {len(frames)}개 프레임 분석 중...")
        prompts = []

        for frame in frames:
            print(f"[SHORTS] 프레임 {frame['index']} 분석 중 ({frame['time']}초)...")

            raw_prompt = analyze_frame_with_gemini(frame["path"])

            if raw_prompt:
                # GPT로 정제 (옵션)
                if refine:
                    final_prompt = refine_prompt_with_gpt(raw_prompt)
                else:
                    final_prompt = raw_prompt

                prompts.append({
                    "time": frame["time"],
                    "prompt": final_prompt
                })
            else:
                prompts.append({
                    "time": frame["time"],
                    "prompt": "[분석 실패]"
                })

        # 영상 길이 계산
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", video_path
        ]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        probe_data = json.loads(probe_result.stdout)
        duration = float(probe_data.get("format", {}).get("duration", 0))

        print(f"[SHORTS] 분석 완료: {len(prompts)}개 프롬프트 생성")

        return jsonify({
            "success": True,
            "videoId": video_id,
            "duration": round(duration, 1),
            "mode": mode,
            "frameCount": len(prompts),
            "prompts": prompts
        })

    except Exception as e:
        print(f"[SHORTS] 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:
        # 임시 파일 정리
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as cleanup_error:
                print(f"[SHORTS] 임시 파일 정리 실패: {cleanup_error}")


@tubelens_bp.route('/tubelens/shorts-prompt-generator')
def shorts_prompt_generator_page():
    """Shorts 프롬프트 생성기 페이지"""
    return render_template('tubelens/shorts_prompt_generator.html')


@tubelens_bp.route('/api/tubelens/image-to-prompt', methods=['POST'])
def image_to_prompt():
    """이미지를 분석하여 세밀한 이미지 생성 프롬프트 생성

    Request:
        multipart/form-data with 'image' file
        또는 JSON with 'image_base64' (base64 encoded image)

    Response:
        {
            "success": true,
            "prompt": "...",
            "analysis": {
                "subject": "...",
                "background": "...",
                "lighting": "...",
                "camera": "...",
                "color": "...",
                "mood": "...",
                "style": "..."
            }
        }
    """
    try:
        import PIL.Image
        import io
        import requests

        # OpenRouter API 키 확인
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return jsonify({"success": False, "message": "OpenRouter API 키가 설정되지 않았습니다"}), 500

        # 이미지 로드 (파일 업로드 또는 base64)
        image = None
        image_base64 = None

        if request.files and 'image' in request.files:
            file = request.files['image']
            if file.filename:
                image_bytes = file.read()
                image = PIL.Image.open(io.BytesIO(image_bytes))
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        elif request.is_json:
            data = request.get_json()
            if data.get('image_base64'):
                image_base64 = data['image_base64']
                image_data = base64.b64decode(image_base64)
                image = PIL.Image.open(io.BytesIO(image_data))

        if not image or not image_base64:
            return jsonify({"success": False, "message": "이미지를 업로드해주세요"}), 400

        # 이미지 포맷 감지
        img_format = image.format or 'PNG'
        mime_type = f"image/{img_format.lower()}"
        if img_format.upper() == 'JPG':
            mime_type = 'image/jpeg'

        print(f"[IMAGE-PROMPT] 이미지 분석 시작: {image.size}, 포맷: {mime_type}")

        analysis_prompt = """이 이미지를 전문 사진작가/영상 감독의 관점에서 매우 세밀하게 분석해주세요.

다음 항목들을 각각 상세하게 분석해주세요:

1. **피사체 (Subject)**
   - 주요 피사체 (사람, 물체, 동물 등)
   - 자세, 표정, 동작
   - 의상, 액세서리, 소품

2. **배경 (Background)**
   - 장소/환경 (실내/실외, 구체적 장소)
   - 배경 요소들
   - 심도(DOF) - 배경 흐림 정도

3. **조명 (Lighting)**
   - 광원 유형 (자연광, 인공조명, 스튜디오 등)
   - 조명 방향 (정면광, 측광, 역광, 림라이트 등)
   - 조명 강도 (하드라이트, 소프트라이트)
   - 그림자 특성

4. **카메라/구도 (Camera)**
   - 카메라 앵글 (아이레벨, 하이앵글, 로우앵글, 버드아이 등)
   - 샷 타입 (클로즈업, 미디엄샷, 풀샷, 와이드샷 등)
   - 구도 (삼등분법, 중앙배치, 대칭, 리딩라인 등)
   - 초점거리 느낌 (광각, 표준, 망원)

5. **색감 (Color)**
   - 전체적인 색조 (웜톤, 쿨톤, 뉴트럴)
   - 주요 색상들
   - 채도, 대비
   - 색상 그레이딩 스타일

6. **분위기/감정 (Mood)**
   - 전체적인 분위기
   - 전달하는 감정
   - 스토리/내러티브

7. **스타일 (Style)**
   - 사진/영상 스타일 (시네마틱, 다큐멘터리, 패션, 포트레이트 등)
   - 시대/트렌드
   - 참고할 만한 작가/감독 스타일

응답은 반드시 아래 JSON 형식으로만 출력해주세요 (다른 텍스트 없이):
{
  "subject": "피사체 설명",
  "background": "배경 설명",
  "lighting": "조명 설명",
  "camera": "카메라/구도 설명",
  "color": "색감 설명",
  "mood": "분위기/감정 설명",
  "style": "스타일 설명",
  "prompt_ko": "한국어 이미지 생성 프롬프트 (위 분석을 바탕으로)",
  "prompt_en": "English image generation prompt (based on above analysis)"
}"""

        # OpenRouter API 호출
        openrouter_response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": analysis_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 2000,
                "temperature": 0.7
            },
            timeout=60
        )

        if openrouter_response.status_code != 200:
            error_msg = openrouter_response.text
            print(f"[IMAGE-PROMPT] OpenRouter API 오류: {error_msg}")
            return jsonify({"success": False, "message": f"OpenRouter API 오류: {error_msg}"}), 500

        response_data = openrouter_response.json()
        response_text = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not response_text:
            return jsonify({"success": False, "message": "이미지 분석에 실패했습니다"}), 500

        # JSON 파싱
        response_text = response_text.strip()

        # JSON 블록 추출 (```json ... ``` 형태일 경우)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        try:
            analysis = json.loads(response_text)
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 텍스트 그대로 반환
            print(f"[IMAGE-PROMPT] JSON 파싱 실패, 원본 텍스트 반환")
            return jsonify({
                "success": True,
                "prompt": response_text,
                "analysis": None,
                "raw_response": response_text
            })

        print(f"[IMAGE-PROMPT] 분석 완료")

        return jsonify({
            "success": True,
            "prompt": analysis.get("prompt_en", ""),
            "prompt_ko": analysis.get("prompt_ko", ""),
            "analysis": {
                "subject": analysis.get("subject", ""),
                "background": analysis.get("background", ""),
                "lighting": analysis.get("lighting", ""),
                "camera": analysis.get("camera", ""),
                "color": analysis.get("color", ""),
                "mood": analysis.get("mood", ""),
                "style": analysis.get("style", "")
            }
        })

    except Exception as e:
        print(f"[IMAGE-PROMPT] 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500
