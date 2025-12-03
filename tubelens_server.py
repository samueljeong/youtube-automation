"""
TubeLens Server - YouTube Analytics Tool
YouTube Data API v3를 사용한 영상 분석 도구
"""

from flask import Blueprint, render_template, request, jsonify
import os
import re
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import requests

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
    """비디오 상세 정보 가져오기"""
    if not video_ids:
        return []

    # 50개씩 배치로 처리 (API 제한)
    all_videos = []

    for i in range(0, len(video_ids), 50):
        batch_ids = video_ids[i:i+50]

        try:
            data = make_youtube_request("videos", {
                "id": ",".join(batch_ids),
                "part": "snippet,statistics,contentDetails"
            }, api_key)

            for item in data.get("items", []):
                video_id = item.get("id")
                snippet = item.get("snippet", {})
                statistics = item.get("statistics", {})
                content_details = item.get("contentDetails", {})

                # 채널 정보 가져오기
                channel_id = snippet.get("channelId", "")
                channel_info = get_channel_info(channel_id, api_key) if channel_id else {}

                # 시간 정보
                duration_seconds = parse_duration(content_details.get("duration", ""))
                published_at = snippet.get("publishedAt", "")

                # 통계 정보
                view_count = int(statistics.get("viewCount", 0))
                like_count = int(statistics.get("likeCount", 0))
                comment_count = int(statistics.get("commentCount", 0))
                subscriber_count = channel_info.get("subscriberCount", 0)

                # CII 계산
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
                    **cii_data
                })

        except Exception as e:
            print(f"비디오 상세 정보 가져오기 실패: {e}")

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
