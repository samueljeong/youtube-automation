"""
YouTube OAuth 토큰 및 할당량 관리 모듈

이 모듈은 다음 기능을 제공합니다:
1. YouTube OAuth 토큰 저장/로드 (데이터베이스)
2. API 할당량 초과 시 백업 프로젝트(_2) 전환
3. 파이프라인 시작 전 토큰/할당량 사전 체크

사용법:
    from youtube_auth import init_db, load_youtube_token_from_db, check_youtube_quota_before_pipeline

    # 초기화 (drama_server.py에서 한 번 호출)
    init_db(get_db_connection, USE_POSTGRES)
"""

import os
import json
from datetime import date

# ===== DB 연결 (drama_server에서 설정) =====
_get_db_connection = None
_use_postgres = False

def init_db(get_db_connection_func, use_postgres):
    """DB 연결 함수 초기화 - drama_server.py 시작 시 호출 필요"""
    global _get_db_connection, _use_postgres
    _get_db_connection = get_db_connection_func
    _use_postgres = use_postgres
    print("[YOUTUBE-AUTH] DB 연결 초기화 완료")

def _get_db():
    """DB 연결 획득"""
    if _get_db_connection is None:
        raise RuntimeError("[YOUTUBE-AUTH] init_db()를 먼저 호출해야 합니다")
    return _get_db_connection()


# ===== 할당량 초과 플래그 관리 =====
# 기본 프로젝트 할당량 초과 시 _2 프로젝트로 전환
# 파일 기반으로 저장하여 워커 간 공유 및 서버 재시작 후에도 유지
YOUTUBE_QUOTA_FLAG_FILE = 'data/youtube_quota_exceeded.json'

# 전역 변수 (레거시 호환용 - 실제로는 파일 기반 플래그 사용)
_youtube_quota_exceeded = False
_youtube_quota_exceeded_date = None


def _load_quota_flag():
    """파일에서 할당량 초과 플래그 로드"""
    try:
        if os.path.exists(YOUTUBE_QUOTA_FLAG_FILE):
            with open(YOUTUBE_QUOTA_FLAG_FILE, 'r') as f:
                data = json.load(f)
                exceeded_date = data.get('date')
                if exceeded_date:
                    # 날짜가 바뀌면 리셋 (할당량은 매일 Pacific Time 기준 초기화됨)
                    today_str = date.today().isoformat()
                    if exceeded_date != today_str:
                        print(f"[YOUTUBE-QUOTA] 날짜 변경 감지 - 할당량 리셋 ({exceeded_date} → {today_str})")
                        os.remove(YOUTUBE_QUOTA_FLAG_FILE)
                        return False
                    return True
    except Exception as e:
        print(f"[YOUTUBE-QUOTA] 플래그 파일 읽기 오류: {e}")
    return False


def _save_quota_flag():
    """파일에 할당량 초과 플래그 저장"""
    try:
        os.makedirs(os.path.dirname(YOUTUBE_QUOTA_FLAG_FILE), exist_ok=True)
        with open(YOUTUBE_QUOTA_FLAG_FILE, 'w') as f:
            json.dump({'exceeded': True, 'date': date.today().isoformat()}, f)
        print(f"[YOUTUBE-QUOTA] 플래그 파일 저장됨: {YOUTUBE_QUOTA_FLAG_FILE}")
    except Exception as e:
        print(f"[YOUTUBE-QUOTA] 플래그 파일 저장 오류: {e}")


def get_youtube_credentials():
    """현재 사용할 YouTube OAuth 자격증명 반환 (할당량 failover 지원)

    Returns:
        (client_id, client_secret, project_suffix)
        - project_suffix: '' (기본) 또는 '_2' (백업)
    """
    # 파일에서 할당량 초과 플래그 확인
    quota_exceeded = _load_quota_flag()

    # 할당량 초과 시 _2 프로젝트 사용
    if quota_exceeded:
        client_id = os.getenv('YOUTUBE_CLIENT_ID_2')
        client_secret = os.getenv('YOUTUBE_CLIENT_SECRET_2')
        if client_id and client_secret:
            print("[YOUTUBE-QUOTA] _2 프로젝트 사용 중 (할당량 초과로 전환됨)")
            return client_id, client_secret, "_2"
        else:
            print("[YOUTUBE-QUOTA] 경고: 할당량 초과 상태이나 _2 프로젝트 미설정")

    # 기본 프로젝트
    client_id = os.getenv('YOUTUBE_CLIENT_ID') or os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('YOUTUBE_CLIENT_SECRET') or os.getenv('GOOGLE_CLIENT_SECRET')
    return client_id, client_secret, ""


def set_youtube_quota_exceeded():
    """할당량 초과 플래그 설정 - _2 프로젝트로 전환

    Returns:
        bool: _2 프로젝트 사용 가능 여부
    """
    # 이미 초과 상태인지 확인
    if _load_quota_flag():
        print("[YOUTUBE-QUOTA] 이미 할당량 초과 상태")
        return True

    # 플래그 저장
    _save_quota_flag()
    print(f"[YOUTUBE-QUOTA] 할당량 초과 감지! _2 프로젝트로 전환")

    # _2 프로젝트가 있는지 확인
    if os.getenv('YOUTUBE_CLIENT_ID_2'):
        print("[YOUTUBE-QUOTA] _2 프로젝트 발견 - 다음 업로드부터 _2 사용")
        return True
    else:
        print("[YOUTUBE-QUOTA] _2 프로젝트 없음 - 내일까지 대기 필요")
        return False


def reset_youtube_quota_exceeded():
    """할당량 초과 플래그 수동 리셋"""
    global _youtube_quota_exceeded, _youtube_quota_exceeded_date
    _youtube_quota_exceeded = False
    _youtube_quota_exceeded_date = None

    # 파일도 삭제
    try:
        if os.path.exists(YOUTUBE_QUOTA_FLAG_FILE):
            os.remove(YOUTUBE_QUOTA_FLAG_FILE)
    except:
        pass

    print("[YOUTUBE-QUOTA] 할당량 초과 플래그 수동 리셋됨")


# ===== YouTube 토큰 저장/로드 =====
# YouTube 토큰 파일 경로 (레거시 - 데이터베이스로 마이그레이션됨)
YOUTUBE_TOKEN_FILE = 'data/youtube_token.json'


def save_youtube_token_to_db(token_data, channel_id=None, channel_info=None, project_suffix=''):
    """YouTube 토큰을 데이터베이스에 저장 (채널별로 저장)

    Args:
        token_data: OAuth 토큰 데이터
        channel_id: YouTube 채널 ID (없으면 'default')
        channel_info: 채널 정보 dict (title, thumbnail)
        project_suffix: 프로젝트 접미사 ('_2' 등, 할당량 failover용)
    """
    user_id = channel_id or 'default'
    # 프로젝트 접미사가 있으면 user_id에 추가
    if project_suffix:
        user_id = f"{user_id}{project_suffix}"
    channel_name = channel_info.get('title', '') if channel_info else ''
    channel_thumbnail = channel_info.get('thumbnail', '') if channel_info else ''

    try:
        conn = _get_db()
        cursor = conn.cursor()

        if _use_postgres:
            # channel_name, channel_thumbnail 컬럼이 없을 수 있으므로 먼저 추가 시도
            try:
                cursor.execute('ALTER TABLE youtube_tokens ADD COLUMN IF NOT EXISTS channel_name TEXT')
                cursor.execute('ALTER TABLE youtube_tokens ADD COLUMN IF NOT EXISTS channel_thumbnail TEXT')
                conn.commit()
            except:
                pass

            cursor.execute('''
                INSERT INTO youtube_tokens (user_id, token, refresh_token, token_uri, client_id, client_secret, scopes, channel_name, channel_thumbnail, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET
                    token = EXCLUDED.token,
                    refresh_token = EXCLUDED.refresh_token,
                    token_uri = EXCLUDED.token_uri,
                    client_id = EXCLUDED.client_id,
                    client_secret = EXCLUDED.client_secret,
                    scopes = EXCLUDED.scopes,
                    channel_name = EXCLUDED.channel_name,
                    channel_thumbnail = EXCLUDED.channel_thumbnail,
                    updated_at = CURRENT_TIMESTAMP
            ''', (
                user_id,
                token_data.get('token'),
                token_data.get('refresh_token'),
                token_data.get('token_uri'),
                token_data.get('client_id'),
                token_data.get('client_secret'),
                ','.join(token_data.get('scopes', [])),
                channel_name,
                channel_thumbnail
            ))
        else:
            # SQLite - 컬럼 추가 시도
            try:
                cursor.execute('ALTER TABLE youtube_tokens ADD COLUMN channel_name TEXT')
            except:
                pass
            try:
                cursor.execute('ALTER TABLE youtube_tokens ADD COLUMN channel_thumbnail TEXT')
            except:
                pass

            cursor.execute('''
                INSERT OR REPLACE INTO youtube_tokens (user_id, token, refresh_token, token_uri, client_id, client_secret, scopes, channel_name, channel_thumbnail, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (
                user_id,
                token_data.get('token'),
                token_data.get('refresh_token'),
                token_data.get('token_uri'),
                token_data.get('client_id'),
                token_data.get('client_secret'),
                ','.join(token_data.get('scopes', [])),
                channel_name,
                channel_thumbnail
            ))

        conn.commit()
        conn.close()
        print(f"[YOUTUBE-TOKEN] 데이터베이스에 저장 완료 (channel_id: {user_id}, name: {channel_name})")
        return True
    except Exception as e:
        print(f"[YOUTUBE-TOKEN] 데이터베이스 저장 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_youtube_token_from_db(channel_id='default', project_suffix=''):
    """YouTube 토큰을 데이터베이스에서 로드

    Args:
        channel_id: YouTube 채널 ID (없으면 'default')
        project_suffix: 프로젝트 접미사 ('_2' 등, 할당량 failover용)

    Returns:
        dict: 토큰 데이터 또는 None
    """
    original_channel_id = channel_id
    # 프로젝트 접미사가 있으면 channel_id에 추가
    if project_suffix:
        channel_id = f"{channel_id}{project_suffix}"
    try:
        conn = _get_db()
        cursor = conn.cursor()

        if _use_postgres:
            cursor.execute('SELECT * FROM youtube_tokens WHERE user_id = %s', (channel_id,))
        else:
            cursor.execute('SELECT * FROM youtube_tokens WHERE user_id = ?', (channel_id,))

        row = cursor.fetchone()

        # ===== Fallback 로직 제거 (2024-12-13) =====
        # 주의: 다른 채널의 토큰을 사용하면 해당 채널로 업로드됨!
        # OAuth 토큰은 인증된 채널에만 업로드 가능하므로 fallback 사용 금지
        if not row and project_suffix:
            print(f"[YOUTUBE-TOKEN] ⚠️ {channel_id} 토큰 없음 - fallback 사용하지 않음 (다른 채널로 업로드되는 버그 방지)")

        conn.close()

        if row:
            token_data = {
                'token': row['token'] if _use_postgres else row[2],
                'refresh_token': row['refresh_token'] if _use_postgres else row[3],
                'token_uri': row['token_uri'] if _use_postgres else row[4],
                'client_id': row['client_id'] if _use_postgres else row[5],
                'client_secret': row['client_secret'] if _use_postgres else row[6],
                'scopes': (row['scopes'] if _use_postgres else row[7]).split(',') if (row['scopes'] if _use_postgres else row[7]) else []
            }
            print(f"[YOUTUBE-TOKEN] 데이터베이스에서 로드 완료 (channel_id: {channel_id})")
            return token_data
        else:
            print(f"[YOUTUBE-TOKEN] 데이터베이스에 토큰 없음 (channel_id: {channel_id})")
            return None
    except Exception as e:
        print(f"[YOUTUBE-TOKEN] 데이터베이스 로드 실패: {e}")
        # 마이그레이션 전 레거시 파일에서 로드 시도
        if os.path.exists(YOUTUBE_TOKEN_FILE):
            try:
                with open(YOUTUBE_TOKEN_FILE, 'r') as f:
                    token_data = json.load(f)
                print("[YOUTUBE-TOKEN] 레거시 파일에서 로드 성공, DB로 마이그레이션 시도")
                save_youtube_token_to_db(token_data, channel_id)
                return token_data
            except Exception as file_error:
                print(f"[YOUTUBE-TOKEN] 레거시 파일 로드도 실패: {file_error}")
        return None


def load_all_youtube_channels_from_db():
    """데이터베이스에 저장된 모든 YouTube 채널 목록 반환

    Returns:
        list: [{'id': channel_id, 'title': name, 'thumbnail': url}, ...]
    """
    try:
        conn = _get_db()
        cursor = conn.cursor()

        if _use_postgres:
            cursor.execute('SELECT user_id, channel_name, channel_thumbnail, updated_at FROM youtube_tokens ORDER BY updated_at DESC')
        else:
            cursor.execute('SELECT user_id, channel_name, channel_thumbnail, updated_at FROM youtube_tokens ORDER BY updated_at DESC')

        rows = cursor.fetchall()
        conn.close()

        channels = []
        for row in rows:
            if _use_postgres:
                channel_id = row['user_id']
                channel_name = row['channel_name'] or channel_id
                channel_thumbnail = row['channel_thumbnail'] or ''
            else:
                channel_id = row[0]
                channel_name = row[1] or channel_id
                channel_thumbnail = row[2] or ''

            # 'default'는 레거시 데이터이므로 표시하지 않음 (채널 정보가 없는 경우)
            if channel_id == 'default' and not channel_name:
                continue

            channels.append({
                'id': channel_id,
                'title': channel_name,
                'thumbnail': channel_thumbnail
            })

        print(f"[YOUTUBE-TOKEN] 저장된 채널 {len(channels)}개 로드")
        return channels
    except Exception as e:
        print(f"[YOUTUBE-TOKEN] 채널 목록 로드 실패: {e}")
        import traceback
        traceback.print_exc()
        return []


def delete_youtube_channel_from_db(channel_id):
    """데이터베이스에서 특정 YouTube 채널 토큰 삭제

    Args:
        channel_id: 삭제할 채널 ID

    Returns:
        bool: 삭제 성공 여부
    """
    try:
        conn = _get_db()
        cursor = conn.cursor()

        if _use_postgres:
            cursor.execute('DELETE FROM youtube_tokens WHERE user_id = %s', (channel_id,))
        else:
            cursor.execute('DELETE FROM youtube_tokens WHERE user_id = ?', (channel_id,))

        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()

        if deleted:
            print(f"[YOUTUBE-TOKEN] 채널 삭제됨: {channel_id}")
        else:
            print(f"[YOUTUBE-TOKEN] 삭제할 채널 없음: {channel_id}")

        return deleted
    except Exception as e:
        print(f"[YOUTUBE-TOKEN] 채널 삭제 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_youtube_quota_before_pipeline(channel_id=None):
    """
    파이프라인 시작 전 YouTube API 할당량 체크

    이 함수는 파이프라인 시작 전에 호출되어:
    1. 토큰 존재 여부 확인
    2. 할당량 초과 여부 확인
    3. 사용할 프로젝트 결정 (기본 또는 _2)

    Args:
        channel_id: YouTube 채널 ID (없으면 'default')

    Returns:
        (ok, project_suffix, error_message)
        - ok: True면 업로드 가능
        - project_suffix: 사용할 프로젝트 ('', '_2')
        - error_message: 에러 시 메시지
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        def try_quota_check(project_suffix):
            """특정 프로젝트로 할당량 테스트"""
            lookup_key = f"{channel_id or 'default'}{project_suffix}"
            print(f"[YOUTUBE-QUOTA-CHECK] 토큰 조회: {lookup_key}")
            token_data = load_youtube_token_from_db(channel_id or 'default', project_suffix)
            if not token_data:
                print(f"[YOUTUBE-QUOTA-CHECK] 토큰 없음: {lookup_key}")
                return None, f"토큰 없음 (key: {lookup_key})"
            if not token_data.get('refresh_token'):
                # 디버그: 토큰 데이터의 키 확인
                print(f"[YOUTUBE-QUOTA-CHECK] 토큰 데이터 키: {list(token_data.keys())}")
                print(f"[YOUTUBE-QUOTA-CHECK] refresh_token 값: {token_data.get('refresh_token', 'MISSING')[:20] if token_data.get('refresh_token') else 'EMPTY/NONE'}...")
                return None, f"refresh_token 없음 (project: {project_suffix or '기본'})"

            # 토큰 로드 (DB 저장 시 'token' 키 사용, 'access_token'도 지원)
            creds = Credentials(
                token=token_data.get('token') or token_data.get('access_token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=os.getenv('YOUTUBE_CLIENT_ID_2' if project_suffix == '_2' else 'YOUTUBE_CLIENT_ID') or os.getenv('GOOGLE_CLIENT_ID'),
                client_secret=os.getenv('YOUTUBE_CLIENT_SECRET_2' if project_suffix == '_2' else 'YOUTUBE_CLIENT_SECRET') or os.getenv('GOOGLE_CLIENT_SECRET')
            )

            # 토큰 갱신
            if creds.expired or not creds.valid:
                creds.refresh(Request())

            # API 호출로 할당량 테스트
            # search.list (100 units)를 사용하여 더 정확한 할당량 확인
            # 업로드에 1600 units 필요하므로, 100 units도 못 쓰면 업로드 불가
            youtube = build('youtube', 'v3', credentials=creds)
            try:
                # search.list 테스트 (100 units) - 더 정확한 할당량 확인
                youtube.search().list(part='id', q='test', maxResults=1, type='video').execute()
                print(f"[YOUTUBE-QUOTA-CHECK] search.list 성공 (100 units)")
            except Exception as search_err:
                error_str = str(search_err).lower()
                if 'quota' in error_str:
                    print(f"[YOUTUBE-QUOTA-CHECK] search.list 실패 - 할당량 부족")
                    return None, f"할당량 부족 (search.list 실패)"
                # 다른 에러면 channels.list로 폴백
                print(f"[YOUTUBE-QUOTA-CHECK] search.list 에러 ({search_err}), channels.list로 폴백")
                youtube.channels().list(part='id', mine=True).execute()
            return True, None

        # 1. 먼저 플래그 파일 확인
        if _load_quota_flag():
            # 이미 기본 프로젝트 할당량 초과 상태 - _2로 시도
            print("[YOUTUBE-QUOTA-CHECK] 기본 프로젝트 할당량 초과 상태 - _2로 시도")
            ok, err = try_quota_check('_2')
            if ok:
                print("[YOUTUBE-QUOTA-CHECK] _2 프로젝트 사용 가능")
                return True, '_2', None
            else:
                # _2도 실패
                if 'quota' in str(err).lower():
                    print("[YOUTUBE-QUOTA-CHECK] _2 프로젝트도 할당량 초과!")
                    return False, '', "두 프로젝트 모두 YouTube API 할당량 초과. 내일 다시 시도하세요."
                else:
                    print(f"[YOUTUBE-QUOTA-CHECK] _2 프로젝트 오류: {err}")
                    return False, '', f"_2 프로젝트 오류: {err}"

        # 2. 기본 프로젝트로 시도
        print("[YOUTUBE-QUOTA-CHECK] 기본 프로젝트로 할당량 체크 중...")
        ok, err = try_quota_check('')
        if ok:
            print("[YOUTUBE-QUOTA-CHECK] 기본 프로젝트 사용 가능")
            return True, '', None

        # 3. 기본 프로젝트 실패 - quotaExceeded인지 확인
        if err and 'quota' in str(err).lower():
            print("[YOUTUBE-QUOTA-CHECK] 기본 프로젝트 할당량 초과 감지 - _2로 전환")
            _save_quota_flag()  # 플래그 저장

            # _2 프로젝트로 재시도
            if os.getenv('YOUTUBE_CLIENT_ID_2'):
                ok2, err2 = try_quota_check('_2')
                if ok2:
                    print("[YOUTUBE-QUOTA-CHECK] _2 프로젝트 사용 가능")
                    return True, '_2', None
                else:
                    if 'quota' in str(err2).lower():
                        return False, '', "두 프로젝트 모두 YouTube API 할당량 초과. 내일 다시 시도하세요."
                    else:
                        return False, '', f"_2 프로젝트 오류: {err2}"
            else:
                return False, '', "YouTube API 할당량 초과. 백업 프로젝트(_2) 미설정."

        # 다른 오류
        print(f"[YOUTUBE-QUOTA-CHECK] 기본 프로젝트 오류: {err}")
        return False, '', f"YouTube 인증 오류: {err}"

    except Exception as e:
        error_str = str(e).lower()
        print(f"[YOUTUBE-QUOTA-CHECK] 예외 발생: {e}")

        # quotaExceeded 예외 처리
        if 'quota' in error_str:
            _save_quota_flag()
            if os.getenv('YOUTUBE_CLIENT_ID_2'):
                # _2로 재시도
                try:
                    ok, err = try_quota_check('_2')
                    if ok:
                        return True, '_2', None
                    else:
                        # _2 체크 실패 (예외 없이 반환된 경우)
                        print(f"[YOUTUBE-QUOTA-CHECK] _2 프로젝트 체크 실패: {err}")
                        if err and 'quota' in str(err).lower():
                            return False, '', "두 프로젝트 모두 YouTube API 할당량 초과"
                        return False, '', f"_2 프로젝트 오류: {err}"
                except Exception as e2:
                    print(f"[YOUTUBE-QUOTA-CHECK] _2 프로젝트 예외: {e2}")
                    if 'quota' in str(e2).lower():
                        return False, '', "두 프로젝트 모두 YouTube API 할당량 초과"
                    return False, '', f"_2 프로젝트 오류: {e2}"
            else:
                return False, '', "YouTube API 할당량 초과. 백업 프로젝트(_2) 미설정."

        return False, '', f"YouTube 할당량 체크 실패: {e}"
