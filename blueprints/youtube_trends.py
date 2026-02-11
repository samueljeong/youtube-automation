"""
YouTube 트렌드 검색 Blueprint
AI 대본 기반 영상 제작 가능한 카테고리에서 인기 영상/키워드 분석
"""

import os
import re
import json
import sqlite3
import isodate
from flask import Blueprint, render_template, request, jsonify
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from collections import Counter

youtube_trends_bp = Blueprint('youtube_trends', __name__)

# 캐시 DB 경로
CACHE_DB_PATH = 'data/youtube_trends_cache.db'
# 캐시 유효 시간 (시간 단위)
CACHE_HOURS = 6


def init_cache_db():
    """캐시 DB 초기화"""
    os.makedirs(os.path.dirname(CACHE_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(CACHE_DB_PATH)
    cursor = conn.cursor()

    # 검색 결과 캐시 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE,
            category TEXT,
            video_type TEXT,
            days INTEGER,
            results TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 카테고리 요약 캐시 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS category_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            days INTEGER,
            results TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 트렌드 히스토리 테이블 (변화 추적용)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trend_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            category TEXT,
            video_type TEXT,
            avg_views INTEGER,
            top_video_id TEXT,
            top_video_title TEXT,
            top_video_views INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, category, video_type)
        )
    ''')

    conn.commit()
    conn.close()


def get_cache(cache_key, max_age_hours=CACHE_HOURS):
    """캐시에서 데이터 조회"""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT results, created_at FROM search_cache
            WHERE cache_key = ?
            AND created_at > datetime('now', ?)
        ''', (cache_key, f'-{max_age_hours} hours'))

        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row[0])
        return None
    except:
        return None


def set_cache(cache_key, category, video_type, days, results):
    """캐시에 데이터 저장"""
    try:
        init_cache_db()
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO search_cache (cache_key, category, video_type, days, results, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        ''', (cache_key, category, video_type, days, json.dumps(results, ensure_ascii=False)))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[TRENDS-CACHE] 저장 오류: {e}")
        return False


def get_category_cache(days, max_age_hours=CACHE_HOURS):
    """카테고리 요약 캐시 조회"""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT results, created_at FROM category_cache
            WHERE days = ?
            AND created_at > datetime('now', ?)
            ORDER BY created_at DESC LIMIT 1
        ''', (days, f'-{max_age_hours} hours'))

        row = cursor.fetchone()
        conn.close()

        if row:
            return json.loads(row[0]), row[1]
        return None, None
    except:
        return None, None


def set_category_cache(days, results):
    """카테고리 요약 캐시 저장"""
    try:
        init_cache_db()
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO category_cache (days, results, created_at)
            VALUES (?, ?, datetime('now'))
        ''', (days, json.dumps(results, ensure_ascii=False)))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[TRENDS-CACHE] 카테고리 캐시 저장 오류: {e}")
        return False


def save_trend_history(category, video_type, avg_views, top_video):
    """트렌드 히스토리 저장 (일별 추적)"""
    try:
        init_cache_db()
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')

        cursor.execute('''
            INSERT OR REPLACE INTO trend_history
            (date, category, video_type, avg_views, top_video_id, top_video_title, top_video_views, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ''', (
            today, category, video_type, avg_views,
            top_video.get('id', '') if top_video else '',
            top_video.get('title', '') if top_video else '',
            top_video.get('viewCount', 0) if top_video else 0
        ))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[TRENDS-HISTORY] 저장 오류: {e}")


def get_trend_history(category, days=7):
    """트렌드 히스토리 조회"""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT date, video_type, avg_views, top_video_title, top_video_views
            FROM trend_history
            WHERE category = ?
            AND date > date('now', ?)
            ORDER BY date DESC
        ''', (category, f'-{days} days'))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'date': row[0],
                'videoType': row[1],
                'avgViews': row[2],
                'topVideoTitle': row[3],
                'topVideoViews': row[4]
            }
            for row in rows
        ]
    except:
        return []


# DB 초기화
init_cache_db()

# YouTube API 클라이언트 (API Key 기반 - 검색에는 OAuth 불필요)
def get_youtube_client():
    api_key = os.getenv('YOUTUBE_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("YOUTUBE_API_KEY 또는 GOOGLE_API_KEY가 필요합니다")
    return build('youtube', 'v3', developerKey=api_key)

# AI 대본 + TTS + 이미지로 제작 가능한 카테고리 (시니어/썰/낭독 채널 기반)
CATEGORIES = {
    "webnovel": {
        "name": "웹소설/낭독",
        "icon": "📖",
        "keywords": ["웹소설 낭독", "소설 읽어주는", "무협 소설 낭독", "판타지 소설", "로맨스 소설 낭독"],
        "description": "웹소설, 무협, 판타지 낭독 채널"
    },
    "ssul": {
        "name": "썰/사연",
        "icon": "💬",
        "keywords": ["레전드 썰", "실화 사연", "충격 사연", "인생 썰", "사연 읽어주는"],
        "description": "실화 썰, 사연, 이야기 채널"
    },
    "touching": {
        "name": "감동 실화",
        "icon": "😢",
        "keywords": ["감동 실화", "눈물나는 이야기", "감동 사연", "효도 사연", "가족 이야기"],
        "description": "감동적인 실화, 가족 이야기"
    },
    "horror_story": {
        "name": "무서운 이야기",
        "icon": "👻",
        "keywords": ["무서운 이야기", "괴담", "공포 썰", "귀신 이야기", "실화 공포"],
        "description": "괴담, 공포 썰, 무서운 실화"
    },
    "history_story": {
        "name": "역사 썰",
        "icon": "📜",
        "keywords": ["역사 이야기", "조선시대 썰", "역사 실화", "옛날이야기", "야사"],
        "description": "역사 이야기, 야사, 옛날 썰"
    },
    "senior": {
        "name": "시니어/인생",
        "icon": "👴",
        "keywords": ["시니어", "인생 이야기", "어르신 사연", "인생 교훈", "노년 이야기"],
        "description": "시니어 타겟, 인생 이야기"
    },
    "mystery_story": {
        "name": "미스터리 썰",
        "icon": "🔍",
        "keywords": ["미스터리 썰", "미제사건 이야기", "실화 미스터리", "의문의 사건", "충격 실화"],
        "description": "미스터리, 미제사건 이야기"
    },
    "revenge": {
        "name": "사이다/복수",
        "icon": "🥤",
        "keywords": ["사이다 썰", "복수 사연", "통쾌한 이야기", "참교육", "진상 썰"],
        "description": "사이다, 복수, 통쾌한 썰"
    },
    "love_story": {
        "name": "연애/로맨스",
        "icon": "💕",
        "keywords": ["연애 썰", "로맨스 사연", "첫사랑 이야기", "이별 사연", "연애 실화"],
        "description": "연애, 로맨스 사연"
    },
    "workplace": {
        "name": "직장/회사",
        "icon": "💼",
        "keywords": ["직장 썰", "회사 사연", "상사 썰", "퇴사 썰", "알바 썰"],
        "description": "직장, 회사, 알바 썰"
    }
}


@youtube_trends_bp.route('/youtube-trends')
def trends_page():
    """트렌드 대시보드 페이지"""
    return render_template('youtube_trends.html', categories=CATEGORIES)


def parse_duration_seconds(duration_str):
    """ISO 8601 duration을 초 단위로 변환 (예: PT1M30S -> 90)"""
    try:
        duration = isodate.parse_duration(duration_str)
        return int(duration.total_seconds())
    except:
        return 0


def format_duration(seconds):
    """초를 사람이 읽기 쉬운 형태로 변환"""
    if seconds < 60:
        return f"{seconds}초"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}분 {secs}초" if secs else f"{mins}분"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}시간 {mins}분" if mins else f"{hours}시간"


@youtube_trends_bp.route('/api/youtube/trends/search', methods=['POST'])
def search_trends():
    """카테고리별 트렌드 검색"""
    data = request.json or {}
    category_id = data.get('category')
    custom_keyword = data.get('keyword')
    days = data.get('days', 7)  # 최근 N일
    max_results = data.get('max_results', 20)
    video_type = data.get('video_type', 'all')  # 'all', 'long', 'short'
    force_refresh = data.get('force_refresh', False)  # 강제 새로고침

    # 캐시 키 생성
    cache_key = f"{category_id or custom_keyword}:{video_type}:{days}"

    # 캐시 확인 (강제 새로고침이 아닌 경우)
    if not force_refresh:
        cached = get_cache(cache_key)
        if cached:
            print(f"[TRENDS] 캐시 히트: {cache_key}")
            return jsonify({
                "ok": True,
                "videos": cached,
                "category": CATEGORIES.get(category_id, {}).get('name', custom_keyword),
                "keywords": CATEGORIES.get(category_id, {}).get('keywords', [custom_keyword])[:3] if category_id else [custom_keyword],
                "videoType": video_type,
                "cached": True
            })

    try:
        youtube = get_youtube_client()

        # 검색 키워드 결정
        if custom_keyword:
            keywords = [custom_keyword]
        elif category_id and category_id in CATEGORIES:
            keywords = CATEGORIES[category_id]['keywords'][:3]  # 상위 3개 키워드
        else:
            return jsonify({"ok": False, "error": "카테고리 또는 키워드가 필요합니다"})

        # 날짜 필터
        published_after = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'

        all_videos = []

        for keyword in keywords:
            # 숏폼 검색 시 #shorts 키워드 추가
            search_keyword = keyword
            if video_type == 'short':
                search_keyword = f"{keyword} #shorts"

            # YouTube 검색 API
            search_response = youtube.search().list(
                q=search_keyword,
                part='id,snippet',
                type='video',
                order='viewCount',  # 조회수 순
                publishedAfter=published_after,
                regionCode='KR',
                relevanceLanguage='ko',
                maxResults=max_results * 2 if video_type != 'all' else max_results  # 필터링 대비 더 많이 가져옴
            ).execute()

            video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]

            if video_ids:
                # 비디오 상세 정보 (조회수 + duration)
                videos_response = youtube.videos().list(
                    id=','.join(video_ids),
                    part='snippet,statistics,contentDetails'
                ).execute()

                for video in videos_response.get('items', []):
                    stats = video.get('statistics', {})
                    snippet = video.get('snippet', {})
                    content_details = video.get('contentDetails', {})

                    # duration 파싱
                    duration_str = content_details.get('duration', 'PT0S')
                    duration_seconds = parse_duration_seconds(duration_str)

                    # 숏폼/롱폼 분류
                    # 숏폼: 60초 이하 (유튜브 쇼츠)
                    # 롱폼: 10분(600초) 이상
                    is_short = duration_seconds <= 60
                    is_long = duration_seconds >= 600

                    # 필터링
                    if video_type == 'short' and not is_short:
                        continue
                    if video_type == 'long' and not is_long:
                        continue

                    # 업로드 후 경과 시간 계산
                    published_at = snippet.get('publishedAt', '')
                    if published_at:
                        pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                        hours_since = (datetime.now(pub_date.tzinfo) - pub_date).total_seconds() / 3600
                    else:
                        hours_since = 0

                    view_count = int(stats.get('viewCount', 0))

                    all_videos.append({
                        'id': video['id'],
                        'title': snippet.get('title', ''),
                        'channel': snippet.get('channelTitle', ''),
                        'channelId': snippet.get('channelId', ''),
                        'thumbnail': snippet.get('thumbnails', {}).get('medium', {}).get('url', ''),
                        'publishedAt': published_at,
                        'viewCount': view_count,
                        'likeCount': int(stats.get('likeCount', 0)),
                        'commentCount': int(stats.get('commentCount', 0)),
                        'hoursSinceUpload': round(hours_since, 1),
                        'viewsPerHour': round(view_count / max(hours_since, 1), 0),
                        'keyword': keyword,
                        'duration': duration_seconds,
                        'durationFormatted': format_duration(duration_seconds),
                        'isShort': is_short
                    })

        # 중복 제거 (video id 기준)
        seen_ids = set()
        unique_videos = []
        for v in all_videos:
            if v['id'] not in seen_ids:
                seen_ids.add(v['id'])
                unique_videos.append(v)

        # 시간당 조회수(성장 속도) 기준 정렬
        unique_videos.sort(key=lambda x: x['viewsPerHour'], reverse=True)

        result_videos = unique_videos[:max_results]

        # 캐시 저장
        set_cache(cache_key, category_id or custom_keyword, video_type, days, result_videos)
        print(f"[TRENDS] API 호출 완료, 캐시 저장: {cache_key}")

        # 트렌드 히스토리 저장 (일별 추적)
        if result_videos and category_id:
            avg_views = sum(v['viewCount'] for v in result_videos) // len(result_videos)
            save_trend_history(category_id, video_type, avg_views, result_videos[0])

        return jsonify({
            "ok": True,
            "videos": result_videos,
            "category": CATEGORIES.get(category_id, {}).get('name', custom_keyword),
            "keywords": keywords,
            "videoType": video_type,
            "cached": False
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@youtube_trends_bp.route('/api/youtube/trends/all-categories', methods=['GET'])
def all_categories_trends():
    """모든 카테고리의 트렌드 요약"""
    days = request.args.get('days', 7, type=int)
    force_refresh = request.args.get('force', 'false').lower() == 'true'

    # 캐시 확인
    if not force_refresh:
        cached, cached_at = get_category_cache(days)
        if cached:
            print(f"[TRENDS] 카테고리 캐시 히트 (저장: {cached_at})")
            return jsonify({
                "ok": True,
                "categories": cached,
                "period": f"최근 {days}일",
                "cached": True,
                "cachedAt": cached_at
            })

    try:
        youtube = get_youtube_client()
        published_after = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'

        results = {}

        for cat_id, cat_info in CATEGORIES.items():
            # 각 카테고리 대표 키워드 1개로 검색
            keyword = cat_info['keywords'][0]

            try:
                # 숏폼 제외를 위해 더 많은 영상을 가져옴
                search_response = youtube.search().list(
                    q=keyword,
                    part='id,snippet',
                    type='video',
                    order='viewCount',
                    publishedAfter=published_after,
                    regionCode='KR',
                    relevanceLanguage='ko',
                    maxResults=15  # 숏폼 제외 후 충분한 수 확보
                ).execute()

                video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]

                if video_ids:
                    # contentDetails 포함하여 duration 확인
                    videos_response = youtube.videos().list(
                        id=','.join(video_ids),
                        part='snippet,statistics,contentDetails'
                    ).execute()

                    top_video = None
                    max_views = 0
                    total_views = 0
                    long_video_count = 0

                    for video in videos_response.get('items', []):
                        # 숏폼 제외 (60초 이하)
                        duration_str = video.get('contentDetails', {}).get('duration', 'PT0S')
                        duration_seconds = parse_duration_seconds(duration_str)
                        if duration_seconds <= 60:
                            continue  # 숏폼 스킵

                        views = int(video.get('statistics', {}).get('viewCount', 0))
                        total_views += views
                        long_video_count += 1

                        if views > max_views:
                            max_views = views
                            top_video = {
                                'title': video['snippet']['title'],
                                'channel': video['snippet']['channelTitle'],
                                'viewCount': views,
                                'thumbnail': video['snippet'].get('thumbnails', {}).get('default', {}).get('url', ''),
                                'duration': format_duration(duration_seconds)
                            }

                    avg_views = total_views // long_video_count if long_video_count > 0 else 0
                    results[cat_id] = {
                        'name': cat_info['name'],
                        'icon': cat_info['icon'],
                        'topVideo': top_video,
                        'avgViews': avg_views,
                        'hotLevel': _calculate_hot_level(avg_views)
                    }
                else:
                    results[cat_id] = {
                        'name': cat_info['name'],
                        'icon': cat_info['icon'],
                        'topVideo': None,
                        'avgViews': 0,
                        'hotLevel': 0
                    }

            except Exception as e:
                print(f"[TRENDS] {cat_id} 검색 오류: {e}")
                results[cat_id] = {
                    'name': cat_info['name'],
                    'icon': cat_info['icon'],
                    'error': str(e)
                }

        # hotLevel 기준 정렬
        sorted_categories = sorted(
            results.items(),
            key=lambda x: x[1].get('avgViews', 0),
            reverse=True
        )

        sorted_dict = dict(sorted_categories)

        # 캐시 저장
        set_category_cache(days, sorted_dict)
        print(f"[TRENDS] 카테고리 분석 완료, 캐시 저장")

        return jsonify({
            "ok": True,
            "categories": sorted_dict,
            "period": f"최근 {days}일",
            "cached": False
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@youtube_trends_bp.route('/api/youtube/trends/keywords', methods=['POST'])
def extract_trending_keywords():
    """특정 카테고리에서 뜨는 키워드 추출"""
    data = request.json or {}
    category_id = data.get('category')
    days = data.get('days', 7)

    if not category_id or category_id not in CATEGORIES:
        return jsonify({"ok": False, "error": "유효한 카테고리가 필요합니다"})

    try:
        youtube = get_youtube_client()
        published_after = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'

        all_titles = []
        keywords = CATEGORIES[category_id]['keywords'][:5]

        for keyword in keywords:
            search_response = youtube.search().list(
                q=keyword,
                part='snippet',
                type='video',
                order='viewCount',
                publishedAfter=published_after,
                regionCode='KR',
                relevanceLanguage='ko',
                maxResults=20
            ).execute()

            for item in search_response.get('items', []):
                all_titles.append(item['snippet']['title'])

        # 제목에서 키워드 추출
        word_counter = Counter()
        stop_words = {'이', '그', '저', '의', '을', '를', '에', '에서', '와', '과', '도', '는', '가', '로', '으로',
                      '한', '된', '하는', '있는', '없는', '했던', '되는', '하고', '되고', '해서', '되어',
                      '것', '수', '등', '중', '때', '후', '전', '더', '또', '및', '다', '만', '위', '대', '내'}

        for title in all_titles:
            # 특수문자 제거, 한글/영문만 추출
            words = re.findall(r'[가-힣]+|[a-zA-Z]+', title)
            for word in words:
                if len(word) >= 2 and word.lower() not in stop_words:
                    word_counter[word] += 1

        # 상위 20개 키워드
        top_keywords = word_counter.most_common(20)

        return jsonify({
            "ok": True,
            "category": CATEGORIES[category_id]['name'],
            "keywords": [{"word": w, "count": c} for w, c in top_keywords],
            "totalTitles": len(all_titles)
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@youtube_trends_bp.route('/api/youtube/trends/channel/<channel_id>')
def channel_analysis(channel_id):
    """특정 채널의 최근 영상 분석"""
    days = request.args.get('days', 30, type=int)

    try:
        youtube = get_youtube_client()
        published_after = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'

        # 채널 정보
        channel_response = youtube.channels().list(
            id=channel_id,
            part='snippet,statistics'
        ).execute()

        if not channel_response.get('items'):
            return jsonify({"ok": False, "error": "채널을 찾을 수 없습니다"})

        channel_info = channel_response['items'][0]

        # 채널의 최근 영상
        search_response = youtube.search().list(
            channelId=channel_id,
            part='id',
            type='video',
            order='date',
            publishedAfter=published_after,
            maxResults=20
        ).execute()

        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]

        videos = []
        if video_ids:
            videos_response = youtube.videos().list(
                id=','.join(video_ids),
                part='snippet,statistics'
            ).execute()

            for video in videos_response.get('items', []):
                stats = video.get('statistics', {})
                videos.append({
                    'id': video['id'],
                    'title': video['snippet']['title'],
                    'publishedAt': video['snippet']['publishedAt'],
                    'viewCount': int(stats.get('viewCount', 0)),
                    'likeCount': int(stats.get('likeCount', 0))
                })

        # 평균 조회수 계산
        avg_views = sum(v['viewCount'] for v in videos) // len(videos) if videos else 0

        return jsonify({
            "ok": True,
            "channel": {
                'id': channel_id,
                'title': channel_info['snippet']['title'],
                'thumbnail': channel_info['snippet']['thumbnails']['default']['url'],
                'subscriberCount': int(channel_info['statistics'].get('subscriberCount', 0)),
                'videoCount': int(channel_info['statistics'].get('videoCount', 0))
            },
            "recentVideos": videos,
            "avgViews": avg_views
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


def _calculate_hot_level(avg_views):
    """평균 조회수 기반 핫 레벨 계산 (0-5)"""
    if avg_views >= 1000000:
        return 5  # 🔥🔥🔥🔥🔥
    elif avg_views >= 500000:
        return 4
    elif avg_views >= 100000:
        return 3
    elif avg_views >= 50000:
        return 2
    elif avg_views >= 10000:
        return 1
    return 0


@youtube_trends_bp.route('/api/youtube/trends/discover-channels', methods=['POST'])
def discover_channels():
    """특정 분야에서 잘 나가는 채널 자동 발견"""
    data = request.json or {}
    keywords = data.get('keywords', [])  # 검색할 키워드 리스트
    days = data.get('days', 30)  # 최근 N일
    min_subscribers = data.get('min_subscribers', 1000)  # 최소 구독자
    max_results = data.get('max_results', 15)  # 결과 채널 수
    min_duration = data.get('min_duration', 600)  # 최소 영상 길이 (초), 기본 10분

    if not keywords:
        return jsonify({"ok": False, "error": "검색 키워드가 필요합니다"})

    try:
        youtube = get_youtube_client()
        published_after = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'

        # 채널별 영상 데이터 수집
        channel_videos = {}  # {channel_id: {'videos': [], 'info': {}}}

        for keyword in keywords:
            # 영상 검색 (조회수 순)
            search_response = youtube.search().list(
                q=keyword,
                part='id,snippet',
                type='video',
                order='viewCount',
                publishedAfter=published_after,
                regionCode='KR',
                relevanceLanguage='ko',
                maxResults=50  # 키워드당 50개
            ).execute()

            video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]

            if video_ids:
                # 영상 상세 정보
                videos_response = youtube.videos().list(
                    id=','.join(video_ids),
                    part='snippet,statistics,contentDetails'
                ).execute()

                for video in videos_response.get('items', []):
                    # 최소 길이 미만 제외 (기본: 10분 미만 제외)
                    duration_str = video.get('contentDetails', {}).get('duration', 'PT0S')
                    duration_seconds = parse_duration_seconds(duration_str)
                    if duration_seconds < min_duration:
                        continue

                    channel_id = video['snippet']['channelId']
                    channel_title = video['snippet']['channelTitle']
                    view_count = int(video.get('statistics', {}).get('viewCount', 0))

                    if channel_id not in channel_videos:
                        channel_videos[channel_id] = {
                            'title': channel_title,
                            'videos': [],
                            'total_views': 0
                        }

                    channel_videos[channel_id]['videos'].append({
                        'id': video['id'],
                        'title': video['snippet']['title'],
                        'viewCount': view_count,
                        'duration': format_duration(duration_seconds),
                        'publishedAt': video['snippet']['publishedAt'],
                        'thumbnail': video['snippet'].get('thumbnails', {}).get('medium', {}).get('url', '')
                    })
                    channel_videos[channel_id]['total_views'] += view_count

        # 채널 정보 조회 (구독자 수 등)
        channel_ids = list(channel_videos.keys())
        if channel_ids:
            # 50개씩 나눠서 조회 (API 제한)
            for i in range(0, len(channel_ids), 50):
                batch_ids = channel_ids[i:i+50]
                channels_response = youtube.channels().list(
                    id=','.join(batch_ids),
                    part='snippet,statistics'
                ).execute()

                for channel in channels_response.get('items', []):
                    ch_id = channel['id']
                    if ch_id in channel_videos:
                        subs = int(channel.get('statistics', {}).get('subscriberCount', 0))
                        channel_videos[ch_id]['subscribers'] = subs
                        channel_videos[ch_id]['thumbnail'] = channel['snippet'].get('thumbnails', {}).get('default', {}).get('url', '')
                        channel_videos[ch_id]['videoCount'] = int(channel.get('statistics', {}).get('videoCount', 0))

        # 최소 구독자 필터링 & 평균 조회수 계산
        filtered_channels = []
        for ch_id, ch_data in channel_videos.items():
            subs = ch_data.get('subscribers', 0)
            if subs < min_subscribers:
                continue

            video_count = len(ch_data['videos'])
            if video_count == 0:
                continue

            avg_views = ch_data['total_views'] // video_count
            top_video = max(ch_data['videos'], key=lambda x: x['viewCount'])

            filtered_channels.append({
                'channelId': ch_id,
                'channelTitle': ch_data['title'],
                'subscribers': subs,
                'thumbnail': ch_data.get('thumbnail', ''),
                'avgViews': avg_views,
                'videoCount': video_count,
                'totalViews': ch_data['total_views'],
                'topVideo': top_video,
                'recentVideos': sorted(ch_data['videos'], key=lambda x: x['viewCount'], reverse=True)[:5]
            })

        # 평균 조회수 기준 정렬
        filtered_channels.sort(key=lambda x: x['avgViews'], reverse=True)

        return jsonify({
            "ok": True,
            "channels": filtered_channels[:max_results],
            "keywords": keywords,
            "totalFound": len(filtered_channels)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)})
