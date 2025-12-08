import os
import re
import json
import sqlite3
import subprocess
import threading
import queue
import uuid
import tempfile
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime as dt
from flask import Flask, render_template, request, jsonify, send_file, Response, redirect, send_from_directory
from openai import OpenAI

# Assistant Blueprint 등록
from assistant_server import assistant_bp
# TubeLens Blueprint 등록
from tubelens_server import tubelens_bp

app = Flask(__name__)

# Assistant Blueprint 등록
app.register_blueprint(assistant_bp)
# TubeLens Blueprint 등록
app.register_blueprint(tubelens_bp)

# ===== 전역 에러 핸들러 (항상 JSON 반환) =====
@app.errorhandler(500)
def handle_500_error(e):
    """500 에러 발생 시 HTML 대신 JSON 반환"""
    print(f"[FLASK-500] 내부 서버 오류: {str(e)}")
    return jsonify({
        "ok": False,
        "error": f"서버 내부 오류가 발생했습니다: {str(e)}"
    }), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """모든 예외를 JSON으로 반환"""
    print(f"[FLASK-ERROR] 예외 발생: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
    return jsonify({
        "ok": False,
        "error": f"서버 오류: {type(e).__name__}: {str(e)}"
    }), 500


# ===== favicon.ico 처리 (브라우저 자동 요청) =====
@app.route('/favicon.ico')
def favicon():
    """파비콘 요청 처리 - 204 No Content 반환"""
    return '', 204


# ===== uploads 폴더 정적 파일 서빙 =====
@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    """uploads 폴더의 파일을 제공"""
    upload_dir = os.path.join(os.getcwd(), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    return send_from_directory(upload_dir, filename)


# ===== outputs 폴더 정적 파일 서빙 =====
@app.route('/output/<path:filename>')
def serve_output(filename):
    """outputs 폴더의 파일을 제공 (썸네일, 이미지 등)"""
    output_dir = os.path.join(os.path.dirname(__file__), 'outputs')
    os.makedirs(output_dir, exist_ok=True)
    return send_from_directory(output_dir, filename)


# ===== FFmpeg 동시 실행 제한 (메모리 보호) =====
# Render 2GB 메모리에서 동시에 2개 이상의 FFmpeg 프로세스 실행 시 OOM 위험
# 세마포어로 최대 1개의 FFmpeg 작업만 동시 실행 허용
ffmpeg_semaphore = threading.Semaphore(1)

# ===== 비동기 영상 생성 작업 큐 시스템 =====
video_job_queue = queue.Queue()
video_jobs = {}  # {job_id: {status, progress, result, error, created_at}}
video_jobs_lock = threading.Lock()
VIDEO_JOBS_FILE = 'data/video_jobs.json'

# YouTube 토큰 파일 경로 (레거시 - 데이터베이스로 마이그레이션됨)
YOUTUBE_TOKEN_FILE = 'data/youtube_token.json'


# ===== 한글 숫자 → 아라비아 숫자 변환 (자막용) =====
def korean_number_to_arabic(text):
    """
    한글 숫자를 아라비아 숫자로 변환 (자막 표시용)
    TTS용 대본은 한글 숫자로 작성되어 있으므로, 자막 표시 시 아라비아 숫자로 변환
    """
    result = text

    # 1. 고유어 숫자 (나이, 개수 등에 사용)
    # 일흔여섯 살 → 76살, 여든일곱 살 → 87살
    native_tens = {
        '열': 10, '스물': 20, '서른': 30, '마흔': 40, '쉰': 50,
        '예순': 60, '일흔': 70, '여든': 80, '아흔': 90
    }
    native_ones = {
        '하나': 1, '둘': 2, '셋': 3, '넷': 4, '다섯': 5,
        '여섯': 6, '일곱': 7, '여덟': 8, '아홉': 9,
        '한': 1, '두': 2, '세': 3, '네': 4
    }

    # 고유어 십단위+일단위 패턴 (예: 일흔여섯)
    for ten_kr, ten_val in native_tens.items():
        for one_kr, one_val in native_ones.items():
            pattern = ten_kr + one_kr
            if pattern in result:
                result = result.replace(pattern, str(ten_val + one_val))

    # 고유어 십단위만 (예: 스물, 서른)
    for ten_kr, ten_val in native_tens.items():
        # "스물 " 또는 "스물살" 등의 패턴
        result = re.sub(rf'{ten_kr}(?=\s|살|세|명|개|번|년|월|일|시|분|$)', str(ten_val), result)

    # 고유어 일단위만 (한, 두, 세, 네 + 단위)
    result = re.sub(r'한(?=\s*(?:명|개|번|살|분|시간|달|해))', '1', result)
    result = re.sub(r'두(?=\s*(?:명|개|번|살|분|시간|달|해))', '2', result)
    result = re.sub(r'세(?=\s*(?:명|개|번|살|분|시간|달|해))', '3', result)
    result = re.sub(r'네(?=\s*(?:명|개|번|살|분|시간|달|해))', '4', result)
    result = re.sub(r'다섯(?=\s*(?:명|개|번|살|분|시간|달|해))', '5', result)
    result = re.sub(r'여섯(?=\s*(?:명|개|번|살|분|시간|달|해))', '6', result)
    result = re.sub(r'일곱(?=\s*(?:명|개|번|살|분|시간|달|해))', '7', result)
    result = re.sub(r'여덟(?=\s*(?:명|개|번|살|분|시간|달|해))', '8', result)
    result = re.sub(r'아홉(?=\s*(?:명|개|번|살|분|시간|달|해))', '9', result)
    result = re.sub(r'열(?=\s*(?:명|개|번|살|분|시간|달|해))', '10', result)

    # 2. 한자어 숫자 (전화번호, 연도, 금액 등)
    sino_digits = {
        '영': '0', '일': '1', '이': '2', '삼': '3', '사': '4',
        '오': '5', '육': '6', '칠': '7', '팔': '8', '구': '9'
    }

    # 전화번호 패턴 (일일이, 일일구, 일이삼사 등)
    # 연속된 한자어 숫자를 아라비아 숫자로 변환
    def convert_sino_sequence(match):
        seq = match.group(0)
        result_num = ''
        for char in seq:
            if char in sino_digits:
                result_num += sino_digits[char]
        return result_num

    # 2-4자리 연속 한자어 숫자 (전화번호 등)
    sino_pattern = '[영일이삼사오육칠팔구]{2,4}'
    result = re.sub(sino_pattern, convert_sino_sequence, result)

    # 3. 한자어 복합 숫자 (이십, 삼십, 백, 천, 만 등)
    # 이십 년 → 20년, 사십칠 년 → 47년
    sino_tens = {'이십': 20, '삼십': 30, '사십': 40, '오십': 50, '육십': 60, '칠십': 70, '팔십': 80, '구십': 90}
    sino_ones_after = {'일': 1, '이': 2, '삼': 3, '사': 4, '오': 5, '육': 6, '칠': 7, '팔': 8, '구': 9}

    # 십단위+일단위 (사십칠 → 47)
    for ten_kr, ten_val in sino_tens.items():
        for one_kr, one_val in sino_ones_after.items():
            pattern = ten_kr + one_kr
            if pattern in result:
                result = result.replace(pattern, str(ten_val + one_val))

    # 십단위만 (이십 → 20)
    for ten_kr, ten_val in sino_tens.items():
        result = result.replace(ten_kr, str(ten_val))

    # 십+일단위 (십오 → 15)
    for one_kr, one_val in sino_ones_after.items():
        pattern = f'십{one_kr}'
        if pattern in result:
            result = result.replace(pattern, str(10 + one_val))

    # 십 → 10
    result = re.sub(r'(?<![이삼사오육칠팔구])십(?![일이삼사오육칠팔구])', '10', result)

    # 4. 큰 단위 (백, 천, 만)
    # 백만 원 → 100만원, 오십만 원 → 50만원
    result = re.sub(r'(\d+)백(\d+)', lambda m: str(int(m.group(1)) * 100 + int(m.group(2))), result)
    result = re.sub(r'(\d+)백(?!\d)', lambda m: str(int(m.group(1)) * 100), result)
    result = re.sub(r'(?<!\d)백(?!\d)', '100', result)

    # 5. 공백 정리 (예: "50 만 원" → "50만원")
    result = re.sub(r'(\d+)\s*(만|천|백)\s*(원|명|개)', r'\1\2\3', result)
    result = re.sub(r'(\d+)\s+(년|월|일|살|세|명|개|번|시|분|초)', r'\1\2', result)

    return result

# YouTube 토큰 DB 저장/로드 함수
def save_youtube_token_to_db(token_data, channel_id=None, channel_info=None):
    """YouTube 토큰을 데이터베이스에 저장 (채널별로 저장)

    Args:
        token_data: OAuth 토큰 데이터
        channel_id: YouTube 채널 ID (없으면 'default')
        channel_info: 채널 정보 dict (title, thumbnail)
    """
    user_id = channel_id or 'default'
    channel_name = channel_info.get('title', '') if channel_info else ''
    channel_thumbnail = channel_info.get('thumbnail', '') if channel_info else ''

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
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


def load_youtube_token_from_db(channel_id='default'):
    """YouTube 토큰을 데이터베이스에서 로드

    Args:
        channel_id: YouTube 채널 ID (없으면 'default')
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('SELECT * FROM youtube_tokens WHERE user_id = %s', (channel_id,))
        else:
            cursor.execute('SELECT * FROM youtube_tokens WHERE user_id = ?', (channel_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            token_data = {
                'token': row['token'] if USE_POSTGRES else row[2],
                'refresh_token': row['refresh_token'] if USE_POSTGRES else row[3],
                'token_uri': row['token_uri'] if USE_POSTGRES else row[4],
                'client_id': row['client_id'] if USE_POSTGRES else row[5],
                'client_secret': row['client_secret'] if USE_POSTGRES else row[6],
                'scopes': (row['scopes'] if USE_POSTGRES else row[7]).split(',') if (row['scopes'] if USE_POSTGRES else row[7]) else []
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
                import json as json_module
                with open(YOUTUBE_TOKEN_FILE, 'r') as f:
                    token_data = json_module.load(f)
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
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('SELECT user_id, channel_name, channel_thumbnail, updated_at FROM youtube_tokens ORDER BY updated_at DESC')
        else:
            cursor.execute('SELECT user_id, channel_name, channel_thumbnail, updated_at FROM youtube_tokens ORDER BY updated_at DESC')

        rows = cursor.fetchall()
        conn.close()

        channels = []
        for row in rows:
            if USE_POSTGRES:
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
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
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

# Job 파일 저장/로드 함수 (Render 재시작 대비)
def save_video_jobs():
    """video_jobs를 파일에 저장"""
    try:
        os.makedirs('data', exist_ok=True)
        with open(VIDEO_JOBS_FILE, 'w', encoding='utf-8') as f:
            json.dump(video_jobs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[VIDEO-JOBS] 저장 실패: {e}")

def load_video_jobs():
    """파일에서 video_jobs 로드"""
    global video_jobs
    try:
        if os.path.exists(VIDEO_JOBS_FILE):
            with open(VIDEO_JOBS_FILE, 'r', encoding='utf-8') as f:
                video_jobs = json.load(f)
            print(f"[VIDEO-JOBS] {len(video_jobs)}개 작업 로드됨")
        else:
            video_jobs = {}
            print("[VIDEO-JOBS] 새로운 작업 저장소 생성")
    except Exception as e:
        print(f"[VIDEO-JOBS] 로드 실패: {e}")
        video_jobs = {}

def video_worker():
    """백그라운드 워커: 영상 생성 작업 처리

    큐에서 작업을 가져와 비동기적으로 영상 생성.
    Render 등 타임아웃 환경에서도 안정적으로 동작.
    """
    print(f"[VIDEO-WORKER] 워커 루프 시작")
    while True:
        try:
            job = video_job_queue.get()
            if job is None:  # 종료 신호
                print(f"[VIDEO-WORKER] 종료 신호 수신")
                break

            job_id = job['job_id']
            print(f"[VIDEO-WORKER] 작업 시작: {job_id}")

            # 디버깅: 작업 데이터 상세 출력
            print(f"[VIDEO-WORKER] 작업 데이터:")
            print(f"  - images: {len(job.get('images', []))}개")
            print(f"  - cuts: {len(job.get('cuts', []))}개")
            print(f"  - audio_url: {'있음' if job.get('audio_url') else '없음'}")
            print(f"  - resolution: {job.get('resolution', 'N/A')}")
            print(f"  - fps: {job.get('fps', 'N/A')}")

            # 상태 업데이트: processing
            with video_jobs_lock:
                if job_id in video_jobs:
                    video_jobs[job_id]['status'] = 'processing'
                    video_jobs[job_id]['progress'] = 0
                    video_jobs[job_id]['message'] = '영상 생성 시작...'
                    save_video_jobs()

            try:
                # 실제 영상 생성 로직 실행 (cuts 지원)
                result = _generate_video_sync(
                    images=job.get('images', []),
                    audio_url=job.get('audio_url', ''),
                    cuts=job.get('cuts', []),  # cuts 배열 전달
                    subtitle_data=job.get('subtitle_data'),
                    burn_subtitle=job.get('burn_subtitle', False),
                    resolution=job.get('resolution', '1920x1080'),
                    fps=job.get('fps', 30),
                    transition=job.get('transition', 'fade'),
                    job_id=job_id
                )

                # 성공
                with video_jobs_lock:
                    if job_id in video_jobs:
                        video_jobs[job_id]['status'] = 'completed'
                        video_jobs[job_id]['progress'] = 100
                        video_jobs[job_id]['message'] = '영상 생성 완료'
                        video_jobs[job_id]['result'] = result
                        video_jobs[job_id]['completed_at'] = dt.now().isoformat()
                        save_video_jobs()

                print(f"[VIDEO-WORKER] 작업 완료: {job_id}")

            except Exception as e:
                # 실패
                import traceback
                error_msg = str(e)
                print(f"[VIDEO-WORKER] 작업 실패: {job_id} - {error_msg}")
                traceback.print_exc()

                with video_jobs_lock:
                    if job_id in video_jobs:
                        video_jobs[job_id]['status'] = 'failed'
                        video_jobs[job_id]['error'] = error_msg
                        video_jobs[job_id]['message'] = f'실패: {error_msg}'
                        save_video_jobs()

            video_job_queue.task_done()

        except Exception as e:
            import traceback
            print(f"[VIDEO-WORKER] 워커 루프 오류: {str(e)}")
            traceback.print_exc()

# 서버 시작 시 저장된 jobs 로드
load_video_jobs()

# 서버 재시작 시 pending/processing 작업 정리
# (큐가 비어있으므로 이 작업들은 처리되지 않음 → 실패 처리)
def cleanup_stale_jobs():
    """서버 재시작 시 처리되지 않은 작업들을 실패 처리"""
    with video_jobs_lock:
        stale_count = 0
        for job_id, job in video_jobs.items():
            if job['status'] in ['pending', 'processing']:
                job['status'] = 'failed'
                job['error'] = '서버 재시작으로 인해 작업이 중단되었습니다. 다시 시도해주세요.'
                stale_count += 1
        if stale_count > 0:
            save_video_jobs()
            print(f"[VIDEO-JOBS] 서버 재시작: {stale_count}개 미완료 작업 실패 처리됨")

cleanup_stale_jobs()

# 워커 스레드 시작
video_worker_thread = threading.Thread(target=video_worker, daemon=True)
video_worker_thread.start()
print(f"[VIDEO-WORKER] 워커 스레드 시작됨 (alive: {video_worker_thread.is_alive()})")

# ===== JSON 지침 파일 로드 =====
GUIDES_DIR = os.path.join(os.path.dirname(__file__), 'guides')
_drama_guidelines_cache = None

def load_drama_guidelines(force_reload=False):
    """JSON 지침 파일 로드 (캐싱 지원)"""
    global _drama_guidelines_cache

    if _drama_guidelines_cache is not None and not force_reload:
        return _drama_guidelines_cache

    json_path = os.path.join(GUIDES_DIR, 'drama.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            _drama_guidelines_cache = json.load(f)
            print(f"[GUIDELINES] drama.json 로드 완료 (version: {_drama_guidelines_cache.get('version', 'unknown')})")
            return _drama_guidelines_cache
    except FileNotFoundError:
        print(f"[GUIDELINES] 경고: {json_path} 파일을 찾을 수 없습니다. 기본 프롬프트를 사용합니다.")
        return None
    except json.JSONDecodeError as e:
        print(f"[GUIDELINES] 경고: JSON 파싱 오류: {e}")
        return None

def get_guideline(path, default=None):
    """
    점 표기법으로 JSON 지침에서 값 가져오기
    예: get_guideline('contentTypes.testimony.systemPrompt')
    """
    guidelines = load_drama_guidelines()
    if guidelines is None:
        return default

    keys = path.split('.')
    value = guidelines
    try:
        for key in keys:
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default

def build_testimony_prompt_from_guide(custom_guide=None, duration_minutes=20, test_mode=False):
    """
    guides/drama.json의 스타일 가이드를 기반으로 간증 대본 생성용 프롬프트 구축
    custom_guide: 클라이언트에서 보낸 커스텀 JSON 가이드 (있으면 우선 사용)
    duration_minutes: 영상 길이 (10, 20, 30분)
    test_mode: 테스트 모드 (True일 경우 최소 분량으로 생성)
    """
    # 커스텀 가이드가 있으면 우선 사용, 없으면 서버 파일에서 로드
    guide = custom_guide if custom_guide else load_drama_guidelines()
    if not guide:
        return None, None

    # Step1 가이드라인 가져오기
    step1_guidelines = guide.get('step1_script_guidelines', {})
    duration_key = f"{duration_minutes}min"
    duration_settings = step1_guidelines.get('duration_settings', {}).get(duration_key, {
        'target_length': 6000,
        'max_characters': 4,  # 최대 4명으로 제한
        'max_scenes': 6,
        'highlight_scenes': 3
    })

    # 🧪 테스트 모드: 비용 최소화를 위해 최소 분량으로 설정
    if test_mode:
        print("[DRAMA] 🧪 테스트 모드 활성화 - 최소 분량으로 생성")
        duration_settings = {
            'target_length': 500,      # 500자 (기존 3000~9000자)
            'max_characters': 2,       # 2명 (기존 2~4명)
            'max_scenes': 2,           # 2개 씬 (기존 4~8개)
            'highlight_scenes': 1      # 1개 하이라이트 (기존 2~3개)
        }
        duration_minutes = 3  # 3분 영상으로 설정

    character_rules = step1_guidelines.get('character_rules', {})
    highlight_rules = step1_guidelines.get('highlight_rules', {})
    output_format = step1_guidelines.get('output_format', {})

    # 기존 스타일 가이드도 참조
    script_style = guide.get('script_style', {})
    structure = guide.get('structure', {})
    dialogue_ratio = guide.get('dialogue_ratio', {})
    detail_req = guide.get('detail_requirements', {})
    emotional = guide.get('emotional_expressions', {})
    mandatory = guide.get('mandatory_elements', {})
    honorific_rules = guide.get('honorific_rules', {})
    number_rules = guide.get('number_expression_rules', {})

    system_prompt = f"""당신은 기독교 간증/드라마 콘텐츠 전문 작가입니다.
반드시 JSON 형식으로 대본을 출력해야 합니다.

═══════════════════════════════════════════════════
【 ⚠️ 대본 작성 전 필수 확인 사항 】
═══════════════════════════════════════════════════
- 영상 길이: {duration_minutes}분
- 목표 글자수: {duration_settings.get('target_length', 6000)}자
- 최대 인물 수: {duration_settings.get('max_characters', 4)}명 ⚠️ 절대 4명 초과 금지! (주인공 1명 + 조연 최대 3명)
- 최대 씬 개수: {duration_settings.get('max_scenes', 6)}개
- 씬당 이미지: 1-2개

═══════════════════════════════════════════════════
【 🎬 하이라이트 (영상 시작 1분) - 매우 중요! 】
═══════════════════════════════════════════════════
목적: 시청자 이탈 방지
- 최대 {highlight_rules.get('max_scenes', 3)}개 장면으로 구성
- 유형 선택:
  * climax_preview: 극적인 클라이맥스 미리보기
  * curiosity_hook: 결말 암시하며 궁금증 유발
- 대본 내용에 따라 더 효과적인 방식을 선택하세요
- 스포일러는 피하되, 시청자가 끝까지 보고 싶게 만들어야 합니다

═══════════════════════════════════════════════════
【 👤 인물 설정 규칙 - 매우 중요! 】
═══════════════════════════════════════════════════
- 최소 {character_rules.get('min_count', 1)}명 ~ 최대 {character_rules.get('max_count', 4)}명
- 이유: TTS 음성 다양성 한계로 인물이 많으면 목소리 중복 발생
- 각 인물은 명확한 역할과 목적이 있어야 함
- 억지로 인물을 늘리지 말 것!

⭐ 【 주인공 나이 필수 조건 - 절대 규칙! 】
🚫🚫🚫 젊은 인물 절대 금지! 🚫🚫🚫
- 주인공은 반드시 60대 이상이어야 합니다! (60세~85세 사이)
- 20대, 30대, 40대 인물을 주인공으로 설정하면 안 됩니다!
- 시청자 대부분이 시니어이므로 공감할 수 있는 연령대 설정 필수
- 62세, 67세, 71세, 75세, 78세, 82세 등 구체적인 나이 명시
- 조연도 가급적 50대 이상으로 설정 (가족 외)

⭐ 【 매번 다른 인물 생성 - 최우선 규칙! 】
🚫 절대 사용 금지 이름 (너무 흔하거나 이전에 사용됨):
  - 지선, 민수, 영희, 철수, 수진, 민지, 현수, 지영, 준호, 미영
  - 영수, 정희, 미숙, 순자, 옥순, 말자, 길동

✅ 반드시 사용할 이름 스타일 (매번 다양하게 선택!):
  - 교회 직분 + 성씨 형태 (예: 김집사(가명), 박권사(가명), 이장로(가명), 정집사(가명), 최권사(가명), 송장로(가명))
  - 독특한 한국식 이름 + (가명) (예: 복순(가명), 갑돌(가명), 순임(가명), 용팔(가명), 분이(가명))
  - 지역별 특색 이름 + (가명) (예: 순덕(가명), 옥녀(가명), 춘자(가명), 판수(가명))
  - 세대감이 느껴지는 이름 (60-80대에 어울리는)
  ⚠️ 중요: 모든 이름 뒤에 반드시 "(가명)"을 붙일 것!

- 이 채널에는 계속해서 새로운 영상이 업로드됩니다
- 따라서 매번 완전히 새롭고 독특한 인물을 창조해야 합니다!
- 반드시 다르게 설정할 항목:
  * 이름: 매번 새롭고 독특한 한국식 이름 (위 금지 목록 제외!)
  * 직업/역할: 다양한 직업군 (목사, 농부, 어부, 상인, 교사, 간호사, 요리사, 운전사, 경비원, 청소부, 봉사자, 한의사, 목수, 대장장이, 떡집 주인, 철물점 주인, 미용사, 이발사, 약사, 운송업 등)
  * 거주지: 매번 다른 지역 (강원도 정선, 전남 곡성, 경북 영덕, 충북 단양, 제주 서귀포, 전북 남원, 경남 하동 등 구체적 지명)
  * 가족 구성: 배우자 유무, 자녀 수(1~5명), 손자녀 등 다양하게
  * 성격과 말투: 독특한 개성 부여 (무뚝뚝, 과묵, 수다스러움, 호탕함 등)
  * 외모: 체형, 얼굴 특징, 머리 스타일 등 구체적으로
  * 배경 스토리: 전혀 다른 인생 경험
- 절대 금지: 전형적이거나 이전에 사용된 듯한 설정, 젊은 인물

【 인물 외모 상세 작성 (Step2 이미지 생성용) 】
각 인물에 대해 다음을 상세히 기술:
- appearance.height: 키와 자세 (예: "170cm 정도, 약간 굽은 자세")
- appearance.body_type: 체형 (예: "마른 체형", "건장한 체격")
- appearance.face: 얼굴 특징 상세히 (예: "깊은 주름, 온화한 눈매, 처진 눈꼬리")
- appearance.hair: 머리 스타일과 색상 (예: "백발, 짧게 정돈된 머리")
- appearance.skin: 피부 상태/톤 (예: "햇볕에 그을린 검은 피부")
- appearance.distinctive_features: 특징적인 외모 요소
- clothing_style: 주로 입는 옷차림
- voice_characteristics: 목소리 특징 (TTS 참고용)

═══════════════════════════════════════════════════
【 🎭 씬 메타데이터 (나레이션이 읽지 않음!) 】
═══════════════════════════════════════════════════
각 씬의 scene_meta는 Step2 이미지 생성용이며, TTS가 읽지 않습니다.
반드시 다음 정보를 포함하세요:

- location: 장소명, 세부 설정, 실내/실외
- time: 시간대, 계절, 날씨
- atmosphere: 분위기, 조명 상태, 배경 소리
- visual_direction: 카메라 제안, 핵심 시각 요소, 색감/톤
- character_states: 각 인물의 현재 감정, 표정, 자세, 행동

═══════════════════════════════════════════════════
【 📖 대본 스타일 】
═══════════════════════════════════════════════════
- 화자 유형: {script_style.get('perspective', '주인공이 직접 고백하는 형식')}
- 시작 형식: "{script_style.get('opening', '안녕하세요. 저는...')}"
- 마무리: 시청자에게 공감 질문 + 좋아요/구독 유도

【 대화 비율 】
- 서술/나레이션: {dialogue_ratio.get('narration', 55)}%
- 내면 독백: {dialogue_ratio.get('inner_monologue', 15)}%
- 직접 대화: {dialogue_ratio.get('direct_dialogue', 30)}%

【 호칭 규칙 - 매우 중요! 】
🚨 핵심 원칙: {honorific_rules.get('core_principle', '60대 이상 인물들은 서로 이름을 직접 부르지 않음')}

✅ 부부 간 호칭 (반드시 사용):
- 남편→아내: {', '.join(honorific_rules.get('spouse_terms', {}).get('husband_calls_wife', ['여보', '당신', '아이 엄마']))}
- 아내→남편: {', '.join(honorific_rules.get('spouse_terms', {}).get('wife_calls_husband', ['여보', '당신', '아이 아빠']))}

🚫 절대 금지:
{chr(10).join('- ' + x for x in honorific_rules.get('forbidden_patterns', ['부부가 서로 이름 부르기 (순자야, 영수야)', '60대 이상끼리 이름으로 호칭', '대화 중 상대방 이름 직접 언급']))}

예시:
❌ 잘못된 표현: "순자야, 밥 먹었어?" / "영수 씨, 어디 가세요?"
✅ 올바른 표현: "여보, 진지 드셨어요?" / "당신, 어디 가시는 거예요?"

【 숫자 표현 규칙 - TTS 필수! 】
🚨 중요: {number_rules.get('tts_narration', {}).get('rule', '모든 숫자는 한글로 표기')}
이유: {number_rules.get('tts_narration', {}).get('reason', 'TTS가 숫자를 잘못 읽는 문제 방지')}

예시:
❌ 잘못: 76세, 20년, 112, 3명
✅ 올바름: 일흔여섯 살, 이십 년, 일일이, 세 명

【 감정 표현 】
신체 반응: {', '.join(emotional.get('physical_reactions', [])[:5])}
감정 상태: {', '.join(emotional.get('emotional_states', [])[:4])}

═══════════════════════════════════════════════════
【 ❌ 절대 금지 - 위반 시 재생성! 】
═══════════════════════════════════════════════════
🚫 인물 관련 금지:
- 60세 미만 주인공 (20대, 30대, 40대 절대 금지!)
- 흔한 이름: 지선, 민수, 영희, 철수, 수진, 민지, 현수 등
- 4명 초과 인물 등장

🚫 서술 관련 금지:
- 3인칭 서술 (그는, 그녀는) → 반드시 1인칭 (저는, 제가)
- 마크다운 기호 (#, *, -, **)
- 설교조의 일반적 교훈만 나열

🚫 구조 관련 금지:
- 씬 개수 초과 ({duration_settings.get('max_scenes', 6)}개 이하!)
- 하이라이트 없이 시작

═══════════════════════════════════════════════════
【 📋 출력 JSON 형식 (반드시 준수!) 】
═══════════════════════════════════════════════════
```json
{{
  "metadata": {{
    "title": "대본 제목",
    "duration_minutes": {duration_minutes},
    "target_length": {duration_settings.get('target_length', 6000)},
    "genre": "testimony",
    "total_scenes": 씬개수,
    "total_characters": 인물수
  }},
  "characters": [
    {{
      "id": "char_01",
      "name": "독특한 이름 (금지: 지선,민수,영희,철수 등)",
      "age": "반드시 60세 이상! (예: 67세, 72세, 78세, 82세)",
      "gender": "남성/여성",
      "role": "주인공/조연/단역",
      "occupation": "직업",
      "relationship_to_protagonist": "관계",
      "appearance": {{
        "height": "키와 자세",
        "body_type": "체형",
        "face": "얼굴 특징",
        "hair": "머리 스타일",
        "skin": "피부 상태",
        "distinctive_features": "특징"
      }},
      "clothing_style": "옷차림",
      "personality": "성격",
      "speaking_style": "말투",
      "voice_characteristics": "목소리 특징"
    }}
  ],
  "highlight": {{
    "purpose": "시청자 이탈 방지",
    "duration_seconds": 60,
    "type": "climax_preview 또는 curiosity_hook",
    "scenes": [
      {{
        "order": 1,
        "preview_text": "하이라이트 텍스트",
        "scene_hint": "장면 힌트",
        "emotion": "감정"
      }}
    ]
  }},
  "script": {{
    "scenes": [
      {{
        "scene_meta": {{
          "scene_id": 1,
          "scene_title": "씬 제목",
          "structure_phase": "7단계 중 해당 단계",
          "location": {{
            "place": "장소명",
            "setting": "세부 설정",
            "indoor_outdoor": "실내/실외"
          }},
          "time": {{
            "period": "시간대",
            "season": "계절",
            "weather": "날씨"
          }},
          "atmosphere": {{
            "mood": "분위기",
            "lighting": "조명 상태",
            "sound_ambience": "배경 소리"
          }},
          "visual_direction": {{
            "camera_suggestion": "카메라 앵글",
            "key_visual": "핵심 시각 요소",
            "color_tone": "색감"
          }},
          "characters_in_scene": ["char_01"],
          "character_states": {{
            "char_01": {{
              "emotion": "감정",
              "expression": "표정",
              "posture": "자세",
              "action": "행동"
            }}
          }}
        }},
        "narration": "실제 나레이션 텍스트 (TTS가 읽을 내용)",
        "tts_text": "TTS가 읽을 순수 텍스트만 (장면 제목, 인물 소개, 지문 제외)"
      }}
    ]
  }}
}}
```
"""

    # 2. 사용자 프롬프트 suffix
    user_suffix = f"""

═══════════════════════════════════════════════════
⚠️ 최종 점검 사항 (반드시 확인!)
═══════════════════════════════════════════════════
1. ✅ 영상 길이 {duration_minutes}분에 맞는 분량인가? (목표: {duration_settings.get('target_length', 6000)}자)
2. ✅ 인물이 {duration_settings.get('max_characters', 3)}명 이하인가?
3. ✅ 씬이 {duration_settings.get('max_scenes', 6)}개 이하인가?
4. ✅ 하이라이트가 영상 시작부에 있는가?
5. ✅ JSON 형식으로 출력했는가?
6. ✅ scene_meta에 모든 시각 정보가 있는가?
7. ✅ 각 인물의 외모가 상세히 기술되었는가?
8. ✅ 1인칭 시점으로 작성했는가?

═══════════════════════════════════════════════════
🎙️ TTS 텍스트 작성 규칙 (매우 중요!)
═══════════════════════════════════════════════════
각 씬의 tts_text 필드에는 TTS가 읽을 순수 대사/나레이션만 작성하세요.

❌ tts_text에 포함하면 안 되는 것:
- 장면 번호나 제목 ("장면 1:", "Scene 1:", "[병원]" 등)
- 인물 소개 ("김영희(45세, 교사)" 등)
- 지문이나 연출 ("(슬픈 표정으로)", "[눈물을 흘리며]" 등)
- 화자 표시 ("영희:", "나레이션:" 등)

✅ tts_text에 포함할 것:
- 주인공이 직접 말하는 대사와 독백만
- "안녕하세요. 저는..." 형식의 순수 텍스트

반드시 유효한 JSON 형식으로 출력하세요!
"""

    return system_prompt, user_suffix


def build_testimony_prompt_from_guide_legacy(custom_guide=None):
    """
    [레거시] 기존 텍스트 형식 대본용 프롬프트 (하위 호환성 유지)
    """
    guide = custom_guide if custom_guide else load_drama_guidelines()
    if not guide:
        return None, None

    script_style = guide.get('script_style', {})
    structure = guide.get('structure', {})
    dialogue_ratio = guide.get('dialogue_ratio', {})
    detail_req = guide.get('detail_requirements', {})
    emotional = guide.get('emotional_expressions', {})
    mandatory = guide.get('mandatory_elements', {})

    system_prompt = f"""당신은 기독교 간증 콘텐츠 전문 작가입니다.

【 핵심 원칙 】
- 화자 유형: {script_style.get('perspective', '주인공이 직접 고백하는 형식')}
- 시작 형식: "{script_style.get('opening', '안녕하세요. 저는...')}"
- 마무리 형식: 시청자에게 공감 질문 + 좋아요/구독 유도

【 필수 분량 】
총 {structure.get('total_length', 15000)}자 이상 (매우 중요!)

【 7단계 구조 (반드시 준수) 】
"""

    sections = structure.get('sections', [])
    for sec in sections:
        ratio_percent = int(sec.get('length_ratio', 0) * 100)
        system_prompt += f"""
{sec.get('id')}. {sec.get('korean_name', sec.get('name'))} ({ratio_percent}%)
   - 목적: {sec.get('purpose', '')}
   - 필수 포함: {', '.join(sec.get('must_include', []))}
   - 예시: "{sec.get('example', '')[:100]}..."
"""

    system_prompt += f"""
【 대화 비율 】
- 서술/나레이션: {dialogue_ratio.get('narration', 55)}%
- 내면 독백: {dialogue_ratio.get('inner_monologue', 15)}%
- 직접 대화: {dialogue_ratio.get('direct_dialogue', 30)}%

【 필수 디테일 】
- 이름: 최소 {detail_req.get('naming', {}).get('min_count', 5)}개
- 나이: 최소 {detail_req.get('ages', {}).get('min_count', 3)}개
- 장소: 최소 {detail_req.get('locations', {}).get('min_count', 3)}개
- 숫자/기간: 최소 {detail_req.get('amounts', {}).get('min_count', 10)}개

【 감정 표현 】
신체 반응: {', '.join(emotional.get('physical_reactions', [])[:5])}

【 절대 금지 】
- 3인칭 서술 → 반드시 1인칭
- 마크다운 기호
- 짧은 분량
"""

    user_suffix = f"""

⚠️ 최종 점검:
1. 첫 문장이 "안녕하세요. 저는..."으로 시작하는가?
2. 전체가 1인칭으로 작성되었는가?
3. 총 글자수가 {structure.get('total_length', 15000)}자 이상인가?
"""

    return system_prompt, user_suffix


def get_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        print("[WARNING] OPENAI_API_KEY가 설정되지 않았습니다. API 호출 시 오류가 발생할 수 있습니다.")
        return None
    return OpenAI(api_key=key)

client = get_client()

# OpenRouter 클라이언트 (Step3 Claude용)
def get_openrouter_client():
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        print("[OPENROUTER] API 키가 설정되지 않았습니다.")
        return None
    try:
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=key
        )
    except Exception as e:
        print(f"[OPENROUTER] 클라이언트 초기화 실패: {e}")
        return None

openrouter_client = get_openrouter_client()

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    # PostgreSQL 사용
    import psycopg2
    from psycopg2.extras import RealDictCursor

    # Render의 postgres:// URL을 postgresql://로 변경
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    def get_db_connection():
        """Create a PostgreSQL database connection"""
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
else:
    # SQLite 사용 (로컬 개발용)
    DB_PATH = os.path.join(os.path.dirname(__file__), 'drama_data.db')

    def get_db_connection():
        """Create a SQLite database connection"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

# DB 초기화
def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS benchmark_analyses (
                id SERIAL PRIMARY KEY,
                script_text TEXT NOT NULL,
                script_hash VARCHAR(100) UNIQUE,
                upload_date VARCHAR(50),
                view_count INTEGER,
                category VARCHAR(100),
                analysis_result TEXT NOT NULL,
                story_structure TEXT,
                character_elements TEXT,
                dialogue_style TEXT,
                success_factors TEXT,
                ai_model VARCHAR(50) DEFAULT 'gpt-5',
                analysis_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_view_count
            ON benchmark_analyses(view_count DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_created_at
            ON benchmark_analyses(created_at DESC)
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS benchmark_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_text TEXT NOT NULL,
                script_hash TEXT UNIQUE,
                upload_date TEXT,
                view_count INTEGER,
                category TEXT,
                analysis_result TEXT NOT NULL,
                story_structure TEXT,
                character_elements TEXT,
                dialogue_style TEXT,
                success_factors TEXT,
                ai_model TEXT DEFAULT 'gpt-5',
                analysis_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_view_count
            ON benchmark_analyses(view_count DESC)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_created_at
            ON benchmark_analyses(created_at DESC)
        ''')

    # YouTube 토큰 테이블 생성
    if USE_POSTGRES:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS youtube_tokens (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(100) UNIQUE DEFAULT 'default',
                token TEXT,
                refresh_token TEXT,
                token_uri TEXT,
                client_id TEXT,
                client_secret TEXT,
                scopes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS youtube_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE DEFAULT 'default',
                token TEXT,
                refresh_token TEXT,
                token_uri TEXT,
                client_id TEXT,
                client_secret TEXT,
                scopes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    # 상품관리 테이블 생성
    if USE_POSTGRES:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id VARCHAR(100) PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                cny_price REAL,
                sell_price INTEGER,
                quantity INTEGER DEFAULT 1,
                stock INTEGER DEFAULT 0,
                platform TEXT,
                sale_type TEXT,
                hs_code TEXT,
                duty_rate REAL,
                link TEXT,
                image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales_logs (
                id SERIAL PRIMARY KEY,
                product_id VARCHAR(100) REFERENCES products(id) ON DELETE CASCADE,
                product_name TEXT,
                change_amount INTEGER,
                log_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                cny_price REAL,
                sell_price INTEGER,
                quantity INTEGER DEFAULT 1,
                stock INTEGER DEFAULT 0,
                platform TEXT,
                sale_type TEXT,
                hs_code TEXT,
                duty_rate REAL,
                link TEXT,
                image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                product_name TEXT,
                change_amount INTEGER,
                log_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
        ''')

    # Video Jobs 테이블 생성 (영상 생성 작업 상태 추적 - 서버 재시작에도 유지됨)
    if USE_POSTGRES:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS video_jobs (
                job_id VARCHAR(100) PRIMARY KEY,
                status VARCHAR(50) DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                message TEXT,
                video_url TEXT,
                error TEXT,
                session_id VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_video_jobs_created_at
            ON video_jobs(created_at DESC)
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS video_jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                message TEXT,
                video_url TEXT,
                error TEXT,
                session_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_video_jobs_created_at
            ON video_jobs(created_at DESC)
        ''')

    conn.commit()
    cursor.close()
    conn.close()
    print("[DRAMA-DB] Database initialized (including youtube_tokens, products)")

# 앱 시작 시 DB 초기화
init_db()

# ===== DB 가이드 조회 함수 =====
def get_relevant_guide_from_db(box_name, category="", limit=5):
    """
    Step 박스 이름에 따라 DB에서 관련 가이드를 가져옴

    Args:
        box_name: Step 박스 이름 (예: "캐릭터 설정", "스토리 구성")
        category: 영상 시간/카테고리 (선택적)
        limit: 가져올 분석 결과 개수

    Returns:
        str: 관련 가이드 텍스트
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Step 타입에 따른 필드 매핑
        field_mapping = {
            '캐릭터': 'character_elements',
            '인물': 'character_elements',
            '스토리': 'story_structure',
            '줄거리': 'story_structure',
            '구성': 'story_structure',
            '대사': 'dialogue_style',
            '분석': 'analysis_result',
            '성공': 'success_factors'
        }

        # box_name에서 해당하는 필드 찾기
        target_field = 'analysis_result'  # 기본값
        for keyword, field in field_mapping.items():
            if keyword in box_name:
                target_field = field
                break

        # 고조회수 대본들의 분석 결과 조회
        if USE_POSTGRES:
            query = f"""
                SELECT {target_field}, view_count, upload_date
                FROM benchmark_analyses
                WHERE {target_field} IS NOT NULL AND {target_field} != ''
                ORDER BY view_count DESC
                LIMIT %s
            """
            cursor.execute(query, (limit,))
        else:
            query = f"""
                SELECT {target_field}, view_count, upload_date
                FROM benchmark_analyses
                WHERE {target_field} IS NOT NULL AND {target_field} != ''
                ORDER BY view_count DESC
                LIMIT ?
            """
            cursor.execute(query, (limit,))

        results = cursor.fetchall()
        conn.close()

        if not results:
            print(f"[DRAMA-DB-GUIDE] DB에 축적된 데이터 없음 (필드: {target_field})")
            return None

        # 결과를 가이드 형식으로 포맷팅
        guide_parts = [f"【 축적된 성공 사례 분석 - {box_name} 】\n"]
        guide_parts.append(f"고조회수 대본 {len(results)}개의 분석 결과를 바탕으로 한 가이드:\n")

        for idx, row in enumerate(results, 1):
            if USE_POSTGRES:
                content = row[target_field]
                view_count = row['view_count']
            else:
                content = row[0]
                view_count = row[1]

            if content:
                view_str = f"{view_count:,}회" if view_count else "정보없음"
                guide_parts.append(f"\n━━━ 사례 {idx} (조회수: {view_str}) ━━━")
                guide_parts.append(content.strip())

        guide_text = "\n".join(guide_parts)
        print(f"[DRAMA-DB-GUIDE] {len(results)}개 사례 가져옴 (필드: {target_field})")
        return guide_text

    except Exception as e:
        print(f"[DRAMA-DB-GUIDE][ERROR] {str(e)}")
        return None

def format_json_result(json_data, indent=0):
    """JSON 데이터를 보기 좋은 텍스트 형식으로 변환 (재귀적 처리)"""
    result = []
    indent_str = "  " * indent

    # JSON의 각 키-값 쌍을 보기 좋게 포맷팅
    for key, value in json_data.items():
        # 키를 한국어로 변환 (필요시)
        key_display = key.replace('_', ' ').title()

        # 값이 리스트인 경우
        if isinstance(value, list):
            result.append(f"{indent_str}【 {key_display} 】")
            for item in value:
                if isinstance(item, dict):
                    # 리스트 안의 딕셔너리 재귀 처리
                    for sub_line in format_json_result(item, indent + 1).split('\n'):
                        if sub_line.strip():
                            result.append(f"  {indent_str}{sub_line}")
                else:
                    result.append(f"{indent_str}  - {item}")
            if indent == 0:
                result.append("")
        # 값이 딕셔너리인 경우 (재귀 처리)
        elif isinstance(value, dict):
            result.append(f"{indent_str}【 {key_display} 】")
            # 중첩 딕셔너리를 재귀적으로 처리
            for sub_key, sub_value in value.items():
                sub_key_display = sub_key.replace('_', ' ')
                if isinstance(sub_value, dict):
                    # 더 깊은 중첩 딕셔너리
                    result.append(f"{indent_str}  {sub_key_display}:")
                    for nested_line in format_json_result(sub_value, indent + 2).split('\n'):
                        if nested_line.strip() and not nested_line.strip().startswith('【'):
                            result.append(f"  {nested_line}")
                        elif nested_line.strip().startswith('【'):
                            # 섹션 헤더는 건너뛰기
                            pass
                elif isinstance(sub_value, list):
                    result.append(f"{indent_str}  {sub_key_display}:")
                    for item in sub_value:
                        result.append(f"{indent_str}    - {item}")
                else:
                    result.append(f"{indent_str}  {sub_key_display}: {sub_value}")
            if indent == 0:
                result.append("")
        # 값이 문자열 또는 기타인 경우
        else:
            result.append(f"{indent_str}【 {key_display} 】")
            result.append(f"{indent_str}{str(value)}")
            if indent == 0:
                result.append("")

    return "\n".join(result).strip()

def remove_markdown(text):
    """마크다운 기호 제거 (#, *, -, **, ###, 등)"""
    # 헤더 제거 (##, ###, #### 등)
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

    # 볼드 제거 (**, __)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)

    # 이탤릭 제거 (*, _)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)

    # 리스트 마커 제거 (-, *, +)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)

    # 코드 블록 제거 (```)
    text = re.sub(r'```[\s\S]*?```', '', text)

    # 인라인 코드 제거 (`)
    text = re.sub(r'`(.+?)`', r'\1', text)

    return text.strip()

def get_system_prompt_for_step(step_name):
    """
    드라마 단계별로 최적화된 system prompt 반환 (JSON 지침 기반)
    mini는 개요와 자료만 생성, 완성된 대본 작성 금지
    """
    step_lower = step_name.lower()

    # JSON에서 프롬프트 가져오기 시도
    step2_prompts = get_guideline('steps.step2.systemPrompts', {})

    # 캐릭터 설정 단계
    if '캐릭터' in step_name or 'character' in step_lower:
        prompt = step2_prompts.get('캐릭터')
        if prompt:
            return f"{prompt}\n\n현재 단계: {step_name}"

    # 스토리라인 / 줄거리 단계
    elif '스토리' in step_name or '줄거리' in step_name or 'storyline' in step_lower or 'plot' in step_lower:
        prompt = step2_prompts.get('스토리')
        if prompt:
            return f"{prompt}\n\n현재 단계: {step_name}"

    # 장면 구성 단계
    elif '장면' in step_name or 'scene' in step_lower:
        prompt = step2_prompts.get('장면')
        if prompt:
            return f"{prompt}\n\n현재 단계: {step_name}"

    # 대사 / 대본 작성 단계
    elif '대사' in step_name or '대본' in step_name or 'dialogue' in step_lower or 'script' in step_lower:
        prompt = step2_prompts.get('대사')
        if prompt:
            return f"{prompt}\n\n현재 단계: {step_name}"

    # 기타 단계 또는 fallback
    default_prompt = step2_prompts.get('default')
    if default_prompt:
        return f"{default_prompt}\n\n현재 단계: {step_name}"

    # JSON 로드 실패 시 기본 프롬프트
    return f"""당신은 gpt-4o-mini로서 드라마 '초안 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

기본 역할:
- 완성된 대본이 아닌, 자료와 구조만 제공
- 사용자가 제공하는 세부 지침을 최우선으로 따름
- 지침이 없는 경우에만 일반적인 드라마 자료 형식 사용

⚠️ 중요: 사용자의 세부 지침이 제공되면 그것을 절대적으로 우선하여 따라야 합니다."""

@app.route("/")
def home():
    return render_template("image.html")

@app.route("/product")
def product():
    return render_template("product.html")

@app.route("/image")
def image():
    return render_template("image.html")

@app.route("/product-manage")
def product_manage():
    return render_template("product-manage.html")

# ===== 상품관리 API =====
@app.route("/api/products", methods=["GET"])
def get_products():
    """모든 상품 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, category, cny_price, sell_price, quantity, stock,
                   platform, sale_type, hs_code, duty_rate, link, image_url, created_at
            FROM products ORDER BY created_at DESC
        ''')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        products = []
        for row in rows:
            if USE_POSTGRES:
                products.append({
                    'id': row['id'],
                    'name': row['name'],
                    'category': row['category'],
                    'cnyPrice': row['cny_price'],
                    'sellPrice': row['sell_price'],
                    'quantity': row['quantity'],
                    'stock': row['stock'],
                    'platform': row['platform'],
                    'saleType': row['sale_type'],
                    'hsCode': row['hs_code'],
                    'dutyRate': row['duty_rate'],
                    'link': row['link'],
                    'imageUrl': row['image_url'],
                    'createdAt': str(row['created_at']) if row['created_at'] else None
                })
            else:
                products.append({
                    'id': row[0],
                    'name': row[1],
                    'category': row[2],
                    'cnyPrice': row[3],
                    'sellPrice': row[4],
                    'quantity': row[5],
                    'stock': row[6],
                    'platform': row[7],
                    'saleType': row[8],
                    'hsCode': row[9],
                    'dutyRate': row[10],
                    'link': row[11],
                    'imageUrl': row[12],
                    'createdAt': row[13]
                })
        return jsonify({'ok': True, 'products': products})
    except Exception as e:
        print(f"[PRODUCTS] Error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route("/api/products", methods=["POST"])
def add_product():
    """상품 추가"""
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                INSERT INTO products (id, name, category, cny_price, sell_price, quantity, stock,
                                      platform, sale_type, hs_code, duty_rate, link, image_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                data.get('id'),
                data.get('name'),
                data.get('category', '미분류'),
                data.get('cnyPrice'),
                data.get('sellPrice'),
                data.get('quantity', 1),
                data.get('stock', 0),
                data.get('platform'),
                data.get('saleType'),
                data.get('hsCode'),
                data.get('dutyRate'),
                data.get('link', ''),
                data.get('imageUrl', '')
            ))
        else:
            cursor.execute('''
                INSERT INTO products (id, name, category, cny_price, sell_price, quantity, stock,
                                      platform, sale_type, hs_code, duty_rate, link, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('id'),
                data.get('name'),
                data.get('category', '미분류'),
                data.get('cnyPrice'),
                data.get('sellPrice'),
                data.get('quantity', 1),
                data.get('stock', 0),
                data.get('platform'),
                data.get('saleType'),
                data.get('hsCode'),
                data.get('dutyRate'),
                data.get('link', ''),
                data.get('imageUrl', '')
            ))

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True, 'message': '상품이 등록되었습니다.'})
    except Exception as e:
        print(f"[PRODUCTS] Add error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route("/api/products/<product_id>", methods=["PUT"])
def update_product(product_id):
    """상품 수정"""
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                UPDATE products SET name=%s, category=%s, cny_price=%s, sell_price=%s,
                                   stock=%s, image_url=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
            ''', (
                data.get('name'),
                data.get('category'),
                data.get('cnyPrice'),
                data.get('sellPrice'),
                data.get('stock', 0),
                data.get('imageUrl', ''),
                product_id
            ))
        else:
            cursor.execute('''
                UPDATE products SET name=?, category=?, cny_price=?, sell_price=?,
                                   stock=?, image_url=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (
                data.get('name'),
                data.get('category'),
                data.get('cnyPrice'),
                data.get('sellPrice'),
                data.get('stock', 0),
                data.get('imageUrl', ''),
                product_id
            ))

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True, 'message': '상품이 수정되었습니다.'})
    except Exception as e:
        print(f"[PRODUCTS] Update error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route("/api/products/<product_id>", methods=["DELETE"])
def delete_product(product_id):
    """상품 삭제"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('DELETE FROM products WHERE id=%s', (product_id,))
        else:
            cursor.execute('DELETE FROM products WHERE id=?', (product_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True, 'message': '상품이 삭제되었습니다.'})
    except Exception as e:
        print(f"[PRODUCTS] Delete error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route("/api/products/<product_id>/stock", methods=["PATCH"])
def update_stock(product_id):
    """재고 업데이트 + 로그 기록"""
    try:
        data = request.json
        new_stock = data.get('stock', 0)

        conn = get_db_connection()
        cursor = conn.cursor()

        # 기존 재고 조회
        if USE_POSTGRES:
            cursor.execute('SELECT stock, name FROM products WHERE id=%s', (product_id,))
        else:
            cursor.execute('SELECT stock, name FROM products WHERE id=?', (product_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'ok': False, 'error': '상품을 찾을 수 없습니다.'}), 404

        if USE_POSTGRES:
            old_stock = row['stock']
            product_name = row['name']
        else:
            old_stock = row[0]
            product_name = row[1]
        change = new_stock - old_stock

        # 재고 업데이트
        if USE_POSTGRES:
            cursor.execute('UPDATE products SET stock=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s',
                          (new_stock, product_id))
        else:
            cursor.execute('UPDATE products SET stock=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                          (new_stock, product_id))

        # 변동이 있으면 로그 기록
        if change != 0:
            if USE_POSTGRES:
                cursor.execute('''
                    INSERT INTO sales_logs (product_id, product_name, change_amount)
                    VALUES (%s, %s, %s)
                ''', (product_id, product_name, change))
            else:
                cursor.execute('''
                    INSERT INTO sales_logs (product_id, product_name, change_amount)
                    VALUES (?, ?, ?)
                ''', (product_id, product_name, change))

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True, 'change': change})
    except Exception as e:
        print(f"[PRODUCTS] Stock update error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route("/api/products/sales-logs", methods=["GET"])
def get_sales_logs():
    """판매/재고 변동 로그 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT product_name, change_amount, log_date
            FROM sales_logs ORDER BY log_date DESC LIMIT 50
        ''')
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        logs = []
        for row in rows:
            if USE_POSTGRES:
                logs.append({
                    'productName': row['product_name'],
                    'change': row['change_amount'],
                    'date': str(row['log_date']) if row['log_date'] else None
                })
            else:
                logs.append({
                    'productName': row[0],
                    'change': row[1],
                    'date': row[2]
                })
        return jsonify({'ok': True, 'logs': logs})
    except Exception as e:
        print(f"[PRODUCTS] Logs error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"ok": True})

# ===== JSON 지침 API =====
@app.route("/api/drama/guidelines", methods=["GET"])
def api_get_guidelines():
    """JSON 지침 전체 반환"""
    guidelines = load_drama_guidelines()
    if guidelines:
        return jsonify({"ok": True, "guidelines": guidelines})
    return jsonify({"ok": False, "error": "지침 파일을 로드할 수 없습니다"}), 500

@app.route("/api/drama/guidelines/<path:key_path>", methods=["GET"])
def api_get_guideline_by_path(key_path):
    """특정 경로의 지침만 반환 (예: /api/drama/guidelines/contentTypes/testimony)"""
    # URL 경로를 점 표기법으로 변환
    dot_path = key_path.replace('/', '.')
    value = get_guideline(dot_path)
    if value is not None:
        return jsonify({"ok": True, "path": dot_path, "value": value})
    return jsonify({"ok": False, "error": f"'{dot_path}' 경로를 찾을 수 없습니다"}), 404

@app.route("/api/drama/guidelines/reload", methods=["POST"])
def api_reload_guidelines():
    """JSON 지침 강제 리로드 (개발/테스트용)"""
    guidelines = load_drama_guidelines(force_reload=True)
    if guidelines:
        return jsonify({
            "ok": True,
            "message": "지침 파일이 리로드되었습니다",
            "version": guidelines.get("version", "unknown")
        })
    return jsonify({"ok": False, "error": "지침 파일을 로드할 수 없습니다"}), 500

# ===== 처리 단계 실행 API (gpt-4o-mini) =====
@app.route("/api/drama/process", methods=["POST"])
def api_process_step():
    """단일 처리 단계 실행 (gpt-4o-mini 사용)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        category = data.get("category", "")
        step_id = data.get("stepId", "")
        step_name = data.get("stepName", "")
        benchmark_script = data.get("text", "")  # 벤치마킹 대본
        main_character = data.get("mainCharacter", "")  # 주인공 정보
        guide = data.get("guide", "")
        master_guide = data.get("masterGuide", "")
        previous_results = data.get("previousResults", {})

        print(f"[DRAMA-PROCESS] {category} - {step_name}")

        # 시스템 메시지 구성 (단계별 최적화)
        system_content = get_system_prompt_for_step(step_name)

        # 총괄 지침이 있으면 추가
        if master_guide:
            system_content += f"\n\n【 카테고리 총괄 지침 】\n{master_guide}\n\n"
            system_content += f"【 현재 단계 역할 】\n{step_name}\n\n"
            system_content += "위 총괄 지침을 참고하여, 현재 단계의 역할과 비중에 맞게 '자료만' 작성하세요."

        # ★ 중요: 단계별 세부 지침을 시스템 프롬프트에 포함 (최우선 지침)
        if guide:
            system_content += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            system_content += f"【 최우선 지침: {step_name} 단계 세부 지침 】\n"
            system_content += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            system_content += guide
            system_content += f"\n\n위 지침을 절대적으로 우선하여 따라야 합니다."
            system_content += f"\n이 지침이 기본 역할과 충돌하면, 이 지침을 따르세요."

        # 사용자 메시지 구성
        user_content = f"[영상 시간]\n{category}\n\n"

        if main_character:
            user_content += f"[주인공/대상]\n{main_character}\n\n"

        if benchmark_script:
            user_content += f"[벤치마킹 대본 (참고용)]\n{benchmark_script}\n\n"

        # 이전 단계 결과 추가
        if previous_results:
            user_content += "[이전 단계 결과 (참고용)]\n"
            for prev_id, prev_data in previous_results.items():
                user_content += f"\n### {prev_data['name']}\n{prev_data['result']}\n"
            user_content += "\n"

        user_content += f"위 내용을 바탕으로 '{step_name}' 단계를 작성해주세요.\n"
        user_content += "⚠️ 중요: 완성된 대본이 아닌, 자료와 구조만 제공하세요."

        # GPT 호출 (gpt-4o-mini)
        # JSON 형식 강제하지 않음 - guide에 따라 자유롭게 출력
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": system_content
                },
                {
                    "role": "user",
                    "content": user_content
                }
            ],
            temperature=0.7,
        )

        result = completion.choices[0].message.content.strip()

        # JSON 파싱 시도 (선택적)
        try:
            # JSON 코드 블록 제거 (```json ... ``` 형태)
            cleaned_result = result
            if cleaned_result.startswith('```'):
                # ```json 또는 ``` 로 시작하는 경우
                lines = cleaned_result.split('\n')
                # 첫 줄과 마지막 줄 제거
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                cleaned_result = '\n'.join(lines).strip()

            # JSON 파싱
            json_data = json.loads(cleaned_result)

            # JSON을 보기 좋은 텍스트로 변환
            formatted_result = format_json_result(json_data)

            print(f"[DRAMA-PROCESS][SUCCESS] JSON 형식으로 응답받아 포맷팅 완료")
            return jsonify({"ok": True, "result": formatted_result})

        except json.JSONDecodeError as je:
            # JSON 파싱 실패 시 원본 텍스트를 반환 (정상 처리)
            # guide에서 텍스트 형식을 요구했을 수 있으므로 오류가 아님
            print(f"[DRAMA-PROCESS][INFO] 텍스트 형식으로 응답받음 (JSON 아님)")
            result = remove_markdown(result)
            return jsonify({"ok": True, "result": result})

    except Exception as e:
        print(f"[DRAMA-PROCESS][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== GPT PRO 처리 API (gpt-5.1) =====
@app.route("/api/drama/gpt-pro", methods=["POST"])
def api_gpt_pro():
    """GPT-5.1 드라마 대본 완성"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        style_name = data.get("styleName", "")
        style_description = data.get("styleDescription", "")
        category = data.get("category", "")
        draft_content = data.get("draftContent", "")

        print(f"[DRAMA-GPT-PRO] 처리 시작 - 스타일: {style_name}")

        # GPT-5.1 시스템 프롬프트 (드라마 전용)
        system_content = (
            "당신은 GPT-5.1 기반의 전문 드라마 대본 작가입니다."
            " 자료는 참고용으로만 활용하고 대본은 처음부터 새로 구성하며,"
            " 자연스럽고 생동감 있는 대사와 지문으로 실제 촬영 가능한 완성도 높은 대본을 작성하세요."
            " 마크다운 기호 대신 순수 텍스트만 사용합니다."
        )

        # 사용자 메시지 구성
        meta_lines = []
        if category:
            meta_lines.append(f"- 드라마 유형: {category}")
        if style_name:
            meta_lines.append(f"- 드라마 스타일: {style_name}")
        if style_description:
            meta_lines.append(f"- 스타일 설명: {style_description}")

        meta_section = "\n".join(meta_lines)

        user_content = (
            "아래는 gpt-4o-mini가 정리한 드라마 기획 자료입니다."
            " 참고만 하고, 대본은 처음부터 새로 작성해주세요."
        )
        if meta_section:
            user_content += f"\n\n[기본 정보]\n{meta_section}"
        user_content += "\n\n[드라마 초안 자료]\n"
        user_content += draft_content

        # 드라마 대본 작성 요청
        user_content += "\n\n【요청 사항】\n"
        user_content += (
            "1. 실제 촬영이 가능한 형식으로 대본을 작성하세요:\n"
            "   - 장면 번호, 장소, 시간 명시\n"
            "   - 지문 (인물의 행동, 표정, 분위기 등)\n"
            "   - 대사 (인물명: 대사 형식)\n"
            "   - 필요시 (  ) 안에 감정이나 상황 묘사\n"
            "2. 자연스럽고 현실적인 대화를 작성하세요.\n"
            "3. 각 장면의 목적과 전개가 명확하도록 구성하세요.\n"
            "4. 캐릭터의 성격과 동기가 대사와 행동에 잘 드러나도록 하세요.\n"
            "5. 전체적인 흐름과 템포를 고려하여 작성하세요.\n"
            "6. 마크다운, 불릿 기호 대신 순수 텍스트로 작성하고, 중복되는 문장은 피하세요.\n"
            "7. 충분히 길고 상세하며 풍성한 내용으로 작성해주세요 (최대 16000 토큰)."
        )

        # 최신 Responses API (gpt-5.1) 호출
        completion = client.responses.create(
            model="gpt-5.1",
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": system_content
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_content
                        }
                    ]
                }
            ],
            temperature=0.8,
            max_output_tokens=16000
        )

        if getattr(completion, "output_text", None):
            result = completion.output_text.strip()
        else:
            text_chunks = []
            for item in getattr(completion, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    if getattr(content, "type", "") == "text":
                        text_chunks.append(getattr(content, "text", ""))
            result = "\n".join(text_chunks).strip()

        if not result:
            raise RuntimeError("GPT-5.1 API로부터 결과를 받지 못했습니다.")

        # 마크다운 제거
        result = remove_markdown(result)

        # 결과 앞에 기본 정보 추가
        final_result = ""

        if style_name:
            final_result += f"드라마 스타일: {style_name}\n"

        if category:
            final_result += f"드라마 유형: {category}\n"

        if style_name or category:
            final_result += "\n" + "="*50 + "\n\n"

        final_result += result

        print(f"[DRAMA-GPT-PRO] 완료")

        return jsonify({"ok": True, "result": final_result})

    except Exception as e:
        print(f"[DRAMA-GPT-PRO][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 벤치마킹 대본 분석 API =====
@app.route("/api/drama/analyze-benchmark", methods=["POST"])
def api_analyze_benchmark():
    """벤치마킹 대본 분석 및 저장"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        benchmark_script = data.get("benchmarkScript", "")
        upload_date = data.get("uploadDate", "")
        view_count = data.get("viewCount", "")
        category = data.get("category", "")
        video_category = data.get("videoCategory", "간증")  # 영상 카테고리 (간증, 드라마, 명언 등)
        script_hash = data.get("scriptHash", "")

        if not benchmark_script:
            return jsonify({"ok": False, "error": "벤치마킹 대본이 없습니다."}), 400

        # DB 기반 중복 체크
        is_duplicate = False
        if script_hash:
            conn = get_db_connection()
            cursor = conn.cursor()
            if USE_POSTGRES:
                cursor.execute("SELECT id FROM benchmark_analyses WHERE script_hash = %s", (script_hash,))
            else:
                cursor.execute("SELECT id FROM benchmark_analyses WHERE script_hash = ?", (script_hash,))
            existing = cursor.fetchone()
            conn.close()

            if existing:
                is_duplicate = True
                print(f"[DRAMA-ANALYZE] 중복 대본 감지 (해시: {script_hash}) - 분석만 수행")

        print(f"[DRAMA-ANALYZE] 벤치마킹 대본 분석 시작 - {view_count} 조회수, 카테고리: {video_category} - 중복: {is_duplicate}")

        # GPT로 대본 분석
        system_content = """당신은 드라마 대본 분석 전문가입니다.

제공된 벤치마킹 대본을 분석하여 다음 요소들을 추출하고 정리하세요:

1. **스토리 구조 패턴**
   - 도입, 전개, 위기, 절정, 결말의 구성 방식
   - 각 파트의 비중과 전환 타이밍

2. **캐릭터 구성 요소**
   - 주인공의 성격과 동기
   - 갈등의 원천과 해결 방식

3. **대사 스타일**
   - 톤과 분위기
   - 핵심 메시지 전달 방식

4. **시청자 반응 요소**
   - 공감을 유도하는 요소
   - 감정적 몰입 포인트

5. **성공 요인 분석**
   - 조회수 관점에서 본 강점
   - 차별화 포인트

분석 결과는 구조화되고 명확하게 작성하세요."""

        user_content = f"""[벤치마킹 대본 정보]
- 업로드 날짜: {upload_date}
- 조회수: {view_count}
- 영상 시간: {category}

[대본 내용]
{benchmark_script}

위 대본을 분석하여 핵심 패턴과 성공 요인을 추출해주세요."""

        completion = client.chat.completions.create(
            model="gpt-4o",  # GPT-4o로 분석 (비용 효율적)
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ]
        )

        analysis = completion.choices[0].message.content.strip()
        total_tokens = completion.usage.total_tokens if hasattr(completion, 'usage') else 0

        # 분석 결과를 섹션별로 파싱 (간단한 구조화)
        story_structure = ""
        character_elements = ""
        dialogue_style = ""
        success_factors = ""

        # 섹션별 추출 (간단한 패턴 매칭)
        sections = analysis.split('\n\n')
        for section in sections:
            if '스토리 구조' in section or '구조 패턴' in section:
                story_structure = section
            elif '캐릭터' in section:
                character_elements = section
            elif '대사' in section:
                dialogue_style = section
            elif '성공 요인' in section:
                success_factors = section

        # 중복이 아닌 경우에만 DB에 저장
        if not is_duplicate and script_hash:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                # 조회수를 숫자로 변환 (예: "12만" -> 120000)
                view_count_num = 0
                if view_count:
                    view_count_str = view_count.replace(',', '').strip()
                    if '만' in view_count_str:
                        view_count_num = int(float(view_count_str.replace('만', '')) * 10000)
                    elif '천' in view_count_str:
                        view_count_num = int(float(view_count_str.replace('천', '')) * 1000)
                    else:
                        try:
                            view_count_num = int(view_count_str)
                        except:
                            view_count_num = 0

                if USE_POSTGRES:
                    cursor.execute('''
                        INSERT INTO benchmark_analyses
                        (script_text, script_hash, upload_date, view_count, category, video_category,
                         analysis_result, story_structure, character_elements,
                         dialogue_style, success_factors, ai_model, analysis_tokens)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (benchmark_script, script_hash, upload_date, view_count_num, category, video_category,
                          analysis, story_structure, character_elements,
                          dialogue_style, success_factors, 'gpt-4o', total_tokens))
                else:
                    cursor.execute('''
                        INSERT INTO benchmark_analyses
                        (script_text, script_hash, upload_date, view_count, category, video_category,
                         analysis_result, story_structure, character_elements,
                         dialogue_style, success_factors, ai_model, analysis_tokens)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (benchmark_script, script_hash, upload_date, view_count_num, category, video_category,
                          analysis, story_structure, character_elements,
                          dialogue_style, success_factors, 'gpt-4o', total_tokens))

                conn.commit()
                conn.close()
                print(f"[DRAMA-ANALYZE] DB 저장 완료 (해시: {script_hash}, 토큰: {total_tokens})")
            except Exception as e:
                print(f"[DRAMA-ANALYZE] DB 저장 실패: {str(e)}")

        print(f"[DRAMA-ANALYZE] 분석 완료 - 저장 여부: {not is_duplicate}, 모델: gpt-4o, 카테고리: {video_category}")

        return jsonify({"ok": True, "analysis": analysis, "isDuplicate": is_duplicate})

    except Exception as e:
        print(f"[DRAMA-ANALYZE][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 개선 제안 API =====
@app.route("/api/drama/get-suggestions", methods=["POST"])
def api_get_suggestions():
    """현재 대본에 대한 개선 제안"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        current_draft = data.get("currentDraft", "")
        category = data.get("category", "")

        if not current_draft:
            return jsonify({"ok": False, "error": "현재 작업 중인 대본이 없습니다."}), 400

        print(f"[DRAMA-SUGGEST] 개선 제안 생성 시작")

        # GPT로 개선 제안 생성
        system_content = """당신은 드라마 대본 컨설턴트입니다.

제공된 초안 대본을 분석하고, 다음 관점에서 구체적인 개선 제안을 제공하세요:

1. **스토리 흐름 개선**
   - 더 강력한 도입부 만들기
   - 긴장감을 높이는 방법
   - 결말의 임팩트 강화

2. **캐릭터 깊이 추가**
   - 주인공의 동기 명확화
   - 감정선 강화 방법

3. **시청자 몰입 요소**
   - 공감 포인트 강화
   - 예상을 뛰어넘는 전개

4. **대사와 연출**
   - 핵심 메시지 전달력 향상
   - 감정적 호소력 강화

각 제안은 구체적이고 실행 가능해야 합니다."""

        user_content = f"""[영상 시간]
{category}

[현재 작업 중인 초안]
{current_draft}

위 초안을 분석하고, 시청자 반응을 극대화할 수 있는 구체적인 개선 제안을 해주세요."""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ]
        )

        suggestions = completion.choices[0].message.content.strip()

        print(f"[DRAMA-SUGGEST] 제안 생성 완료 (모델: gpt-4o-mini)")

        return jsonify({"ok": True, "suggestions": suggestions})

    except Exception as e:
        print(f"[DRAMA-SUGGEST][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 워크플로우 박스 실행 API =====
@app.route("/api/drama/workflow-execute", methods=["POST"])
def api_workflow_execute():
    """워크플로우 박스 실행 (선택된 입력 소스 기반)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        box_id = data.get("boxId", "")
        box_name = data.get("boxName", "")
        box_number = data.get("boxNumber", 0)
        step_type = data.get("stepType", "step1")  # step1 or step2
        guide = data.get("guide", "")
        inputs = data.get("inputs", {})  # dict with selected input sources
        category = data.get("category", "")
        main_character = data.get("mainCharacter", "")
        selected_model = data.get("model", "")  # 프론트엔드에서 선택한 모델

        # Step 타입에 따른 모델 선택 (프론트엔드에서 선택한 모델 우선)
        if selected_model:
            model_name = selected_model
            use_temperature = True  # 사용자가 모델을 선택한 경우 temperature 사용
        elif step_type == "step1":
            model_name = "gpt-4o-mini"
            use_temperature = False
        else:  # step2
            model_name = "gpt-4o-mini"
            use_temperature = True

        print(f"[DRAMA-WORKFLOW] Box [{box_number}] {box_name} 실행 시작 (모델: {model_name}, Step: {step_type})")

        # 선택된 입력 소스들을 조합
        input_content_parts = []

        # 벤치마킹 대본이 선택된 경우
        if inputs.get("benchmarkScript"):
            input_content_parts.append(f"[벤치마킹 대본]\n{inputs['benchmarkScript']}")

        # AI 분석 자료가 선택된 경우
        if inputs.get("aiAnalysis"):
            input_content_parts.append(f"[AI 대본 분석 자료]\n{inputs['aiAnalysis']}")

        # DB에서 관련 가이드 가져오기 (자동 추가)
        db_guide = get_relevant_guide_from_db(box_name, category, limit=3)
        if db_guide:
            input_content_parts.append(f"[축적된 성공 사례 가이드]\n{db_guide}")

        # 이전 박스 결과들이 선택된 경우
        for key, value in inputs.items():
            if key.startswith("box") and key.endswith("Result"):
                # box1Result, box2Result 등
                box_num = key.replace("box", "").replace("Result", "")
                input_content_parts.append(f"[박스 {box_num} 결과]\n{value}")

        # 입력이 없는 경우 오류 반환
        if not input_content_parts:
            return jsonify({"ok": False, "error": "선택된 입력 소스가 없습니다. 체크박스를 선택해주세요."}), 400

        # 시스템 프롬프트 구성
        system_content = f"""당신은 드라마 제작 워크플로우 시스템의 작업 박스 [{box_number}] '{box_name}'를 처리하는 AI 어시스턴트입니다.

사용자가 제공하는 작업 지침을 절대적으로 우선하여 따라야 합니다.
지침이 명확하면 그대로 수행하고, 지침이 없거나 불명확하면 일반적인 드라마 제작 원칙에 따라 처리하세요.

현재 작업: [{box_number}] {box_name}
영상 시간: {category}"""

        # 주인공 정보 추가
        if main_character:
            system_content += f"\n주인공 설정: {main_character}"
            system_content += "\n\n⚠️ 중요: 위에 지정된 주인공을 반드시 사용하여 대본을 구성하세요."

        # 작업 지침 추가
        if guide:
            system_content += f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【 작업 지침 (최우선) 】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{guide}

위 지침을 절대적으로 우선하여 따라야 합니다."""
        else:
            system_content += "\n\n⚠️ 작업 지침이 제공되지 않았습니다. 일반적인 드라마 제작 원칙에 따라 처리하세요."

        # 사용자 메시지 구성 (선택된 입력 소스들)
        user_content = "다음은 선택된 입력 자료들입니다:\n\n"
        user_content += "\n\n".join(input_content_parts)
        user_content += "\n\n위 자료를 바탕으로 작업 지침에 따라 처리해주세요."

        # GPT 호출 (모델 및 temperature 동적 설정)
        if use_temperature:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.7,
            )
        else:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content}
                ]
            )

        result = completion.choices[0].message.content.strip()

        # 마크다운 제거
        result = remove_markdown(result)

        # 토큰 사용량 추출
        input_tokens = completion.usage.prompt_tokens if hasattr(completion, 'usage') and completion.usage else 0
        output_tokens = completion.usage.completion_tokens if hasattr(completion, 'usage') and completion.usage else 0

        print(f"[DRAMA-WORKFLOW] Box [{box_number}] {box_name} 실행 완료 (모델: {model_name}, 토큰: {input_tokens}/{output_tokens})")

        return jsonify({
            "ok": True,
            "result": result,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": model_name
            }
        })

    except Exception as e:
        print(f"[DRAMA-WORKFLOW][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 축적된 작성 가이드 조회 API =====
@app.route("/api/drama/get-accumulated-guide", methods=["POST"])
def api_get_accumulated_guide():
    """축적된 대본 분석 결과를 기반으로 작성 가이드 제공"""
    try:
        data = request.get_json()
        category = data.get("category", "") if data else ""

        print(f"[DRAMA-GUIDE] 축적된 가이드 조회 시작")

        # DB에서 축적된 데이터 확인
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            if USE_POSTGRES:
                cursor.execute("SELECT COUNT(*) as cnt FROM benchmark_analyses")
                count_result = cursor.fetchone()
                db_count = count_result['cnt'] if count_result else 0
            else:
                cursor.execute("SELECT COUNT(*) FROM benchmark_analyses")
                db_count = cursor.fetchone()[0]
            conn.close()

            if db_count > 0:
                # DB에 데이터가 있으면 실제 분석 결과 기반 가이드 생성
                print(f"[DRAMA-GUIDE] DB에 {db_count}개 분석 데이터 발견 - 실제 데이터 기반 가이드 생성")

                # 각 카테고리별 TOP 분석 결과 가져오기
                guide_parts = ["【 축적된 대본 분석 기반 작성 가이드 】\n"]
                guide_parts.append(f"총 {db_count}개의 대본 분석 결과를 바탕으로 작성되었습니다.\n\n")

                # 1. 스토리 구조 가이드
                story_guide = get_relevant_guide_from_db("스토리 구성", category, limit=3)
                if story_guide:
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    guide_parts.append("📖 스토리 구조 성공 사례")
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    guide_parts.append(story_guide)
                    guide_parts.append("\n")

                # 2. 캐릭터 설계 가이드
                character_guide = get_relevant_guide_from_db("캐릭터 설정", category, limit=3)
                if character_guide:
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    guide_parts.append("👥 캐릭터 설계 성공 사례")
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    guide_parts.append(character_guide)
                    guide_parts.append("\n")

                # 3. 대사 작성 가이드
                dialogue_guide = get_relevant_guide_from_db("대사 작성", category, limit=3)
                if dialogue_guide:
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    guide_parts.append("💬 대사 작성 성공 사례")
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    guide_parts.append(dialogue_guide)
                    guide_parts.append("\n")

                # 4. 성공 요인 종합
                success_guide = get_relevant_guide_from_db("성공 요인", category, limit=5)
                if success_guide:
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    guide_parts.append("🏆 고조회수 대본의 성공 요인")
                    guide_parts.append("━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                    guide_parts.append(success_guide)

                guide = "\n".join(guide_parts)
                print(f"[DRAMA-GUIDE] DB 기반 가이드 생성 완료")
                return jsonify({"ok": True, "guide": guide, "source": "database"})

        except Exception as db_err:
            print(f"[DRAMA-GUIDE] DB 조회 실패, GPT 가이드로 폴백: {str(db_err)}")

        # DB에 데이터가 없거나 오류 시 GPT로 일반 가이드 생성
        print(f"[DRAMA-GUIDE] DB 데이터 없음 - GPT 일반 가이드 생성")

        system_content = """당신은 드라마 대본 작성 전문가입니다.

수많은 성공적인 드라마 대본들을 분석하여 얻은 보편적인 작성 가이드를 제공하세요.

다음 요소들을 포함하여 구조화된 가이드를 작성하세요:

1. **스토리 구조 모범 사례**
   - 효과적인 도입부 구성법
   - 긴장감을 유지하는 전개 방식
   - 강렬한 클라이맥스 만들기
   - 여운 남는 결말 작성법

2. **캐릭터 설계 원칙**
   - 공감 가는 주인공 만들기
   - 명확한 동기와 목표 설정
   - 성장 아크 디자인
   - 갈등의 원천 설정

3. **대사 작성 기법**
   - 자연스러운 대화 만들기
   - 캐릭터 개성 드러내기
   - 핵심 메시지 전달 방법
   - 감정적 호소력 강화

4. **시청자 몰입 전략**
   - 공감 포인트 배치
   - 예상을 뛰어넘는 전개
   - 감정적 카타르시스 제공
   - 보편적 주제 다루기

5. **장르별 차별화 요소**
   - 기독교 드라마의 특성
   - 감동 드라마의 핵심
   - 멜로/로맨스의 포인트
   - 스릴러/서스펜스의 긴장감

각 항목은 실전에서 바로 적용 가능하도록 구체적이고 명확하게 작성하세요."""

        user_content = "드라마 대본 작성 시 참고할 수 있는 보편적이고 실용적인 가이드를 제공해주세요."

        if category:
            user_content += f"\n\n특히 '{category}' 길이의 드라마에 적합한 가이드를 포함해주세요."

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ]
        )

        guide = completion.choices[0].message.content.strip()

        print(f"[DRAMA-GUIDE] GPT 가이드 생성 완료 (모델: gpt-4o-mini)")

        return jsonify({"ok": True, "guide": guide, "source": "gpt"})

    except Exception as e:
        print(f"[DRAMA-GUIDE][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Q&A 대화 API =====
@app.route('/api/drama/qa', methods=['POST'])
def api_drama_qa():
    """대본/작업에 대한 Q&A 대화"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        question = data.get("question", "")
        script = data.get("script", "")
        session_context = data.get("sessionContext", "")
        history = data.get("history", [])

        if not question:
            return jsonify({"ok": False, "error": "질문이 없습니다."}), 400

        print(f"[Q&A] 질문: {question[:100]}...")

        # 대화 히스토리 구성
        history_text = ""
        if history:
            history_text = "\n\n【 이전 대화 】\n"
            for item in history[-5:]:  # 최근 5개만
                if item.get('question') and item.get('answer') and item.get('answer') != '답변을 생성 중입니다...':
                    history_text += f"Q: {item['question'][:200]}\n"
                    history_text += f"A: {item['answer'][:500]}\n\n"

        # 대본 컨텍스트 (앞부분만)
        script_context = ""
        if script:
            script_preview = script[:3000] if len(script) > 3000 else script
            script_context = f"\n\n【 현재 대본 (일부) 】\n{script_preview}"

        system_prompt = f"""당신은 드라마/간증 대본 제작 전문 AI 어시스턴트입니다.
사용자의 질문에 친절하고 전문적으로 답변해주세요.

{session_context}
{script_context}
{history_text}

【 답변 가이드 】
- 대본 구조, 캐릭터, 스토리에 대한 전문적 조언 제공
- 구체적이고 실행 가능한 제안
- 한국어로 자연스럽게 답변
- 필요시 예시 제공
"""

        user_prompt = f"질문: {question}"

        # OpenRouter API 호출 (GPT-4o-mini 사용)
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not openrouter_api_key:
            return jsonify({"ok": False, "error": "OpenRouter API 키가 설정되지 않았습니다."}), 200

        import requests as req

        headers = {
            "Authorization": f"Bearer {openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://drama-lab.app",
            "X-Title": "Drama Lab Q&A"
        }

        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1500
        }

        response = req.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            answer = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            if answer:
                print(f"[Q&A] 답변 생성 완료: {len(answer)}자")
                return jsonify({
                    "ok": True,
                    "answer": answer,
                    "model": "gpt-4o-mini"
                })
            else:
                return jsonify({"ok": False, "error": "답변 생성 실패"}), 200
        else:
            error_text = response.text
            print(f"[Q&A][ERROR] OpenRouter 응답: {response.status_code} - {error_text}")
            return jsonify({"ok": False, "error": f"API 오류: {response.status_code}"}), 200

    except Exception as e:
        print(f"[Q&A][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Step3: OpenRouter를 통한 Claude 대본 완성 =====
def _generate_senior_nostalgia_metadata(script_preview):
    """시니어 향수 채널 전용 메타데이터 생성 - CTR/Watch Time/구독률 최적화"""
    system_prompt = """당신은 시니어 향수 YouTube 채널의 메타데이터 전문가입니다.
60-80대 시니어 시청자를 위한 따뜻하고 공감되는 메타데이터를 생성하세요.

반드시 아래 JSON 형식으로만 응답하세요:
{
  "title": "제목 (4~12자, 조용하지만 마음 건드리는)",
  "thumbnailTitle": "썸네일 문구 (4~6단어, 줄바꿈 구분)",
  "description": "설명문 (3~7줄, 짧은 문장)",
  "tags": ["태그1", "태그2", ...] (15-20개)
}

【 제목 규칙 - 시니어 향수 채널 최적화 】
★ 전체 톤: 과장 NO, 숫자 과다 NO, 유행어 NO
★ 조용하지만 강하게 마음 건드리는 제목
★ 시니어의 기억, 공감, 감정, 잔향 자극

■ 제목 패턴 10가지 중 1개 선택:

① '그 시절' 회상형
- "그 시절, 겨울이면 들리던 그 소리"
- "그때 우리 동네에는 항상 이런 풍경이 있었죠"

② '한 장면' 포착형
- "밤마다 골목을 비추던 노란 가로등 아래에서"
- "연탄 재 날리던 부엌 한켠의 따뜻함"

③ '보자마자 공감되는 물건/장소'
- "요즘 아이들은 모르는 그 구멍가게의 냄새"
- "시장 입구에서 들리던 이 소리, 기억하시나요"

④ '우리 세대만 아는 은근한 표현'
- "참 소박했던 그 시절, 우리의 하루"
- "마음이 괜히 따뜻해지는 옛날 동네 풍경"

⑤ '감정 자극형'
- "들으면 가만히 눈물이 나는 그 이야기"
- "오래 묵혀둔 기억이 새어 나오는 밤"

⑥ '상황 회상형'
- "겨울만 되면 이렇게 모여 있었죠"
- "비 오던 날, 마루 끝에 앉아 바라보던 그 풍경"

⑦ '사라져버린 것들'
- "이제는 어디에서도 볼 수 없는 풍경"
- "사라진 줄도 몰랐던 그 시절의 하루"

⑧ '그때와 지금을 자연 비교'
- "그때는 당연했던 것들, 이제는 추억이 되었습니다"
- "아무렇지 않던 평범한 날들이 더 그리운 요즘"

⑨ '한 문장 감성형'
- "그날, 바람 냄새까지 기억납니다"
- "어쩌면 가장 따뜻했던 시간들"

⑩ '사람 중심형'
- "엄마가 내 손 잡고 다니던 그 시장 길"
- "아버지가 늘 앉아 계시던 골목 입구"

【 썸네일 문구 규칙 】
★ 4~6단어 한국어만
★ 노란색/갈색 감성에 어울리는 문구
★ scene의 핵심 요소 + 감정 결합

예시:
- "그 시절 그 골목"
- "따뜻했던 하루"
- "기억나시나요?"
- "그때의 풍경들"
- "그 겨울, 우리 골목"
- "엄마와 시장길"

【 설명문 규칙 】
★ 짧고 따뜻하게 (3~7줄)
★ 시니어가 읽기 편한 짧은 문장
★ 광고 문구, 외부링크 절대 금지
★ 구조: 영상 분위기 소개 → 감정 회상 → 감사 인사

템플릿 예시:
"오늘은 그 시절 우리가 함께 지나왔던 풍경을 이야기합니다.
따뜻했던 날들, 사소해서 잊고 지냈던 순간들…
다시 떠올려보면 참 소중했던 기억들입니다.

편안한 마음으로 천천히 들어주세요.
혹시 영상 속 장면이 마음에 닿으셨다면
댓글로 그 시절의 이야기도 들려주세요.

시청해 주셔서 감사합니다."

【 태그 규칙 】
★ 필수 기본 태그:
옛날이야기, 그시절, 향수, 시니어유튜브, 감성사운드, 회상, 추억, 70년대, 80년대, 옛풍경, 편안한영상, 라디오같은영상

★ 시니어 검색 패턴 태그:
그때그시절, 옛날이야기듣기, 시니어힐링영상, 옛날감성

★ 대본 내용 기반 맞춤 태그 3~5개 추가"""

    user_prompt = f"다음 시니어 향수 콘텐츠 대본의 메타데이터를 생성하세요:\n\n{script_preview}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=600
        )

        result_text = response.choices[0].message.content.strip()

        import re
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            metadata = json.loads(json_match.group())
            # 필수 태그 보장
            required_tags = ["옛날이야기", "그시절", "향수", "시니어유튜브", "추억", "회상", "70년대", "80년대", "옛풍경", "편안한영상"]
            existing_tags = set(metadata.get("tags", []))
            for tag in required_tags:
                if tag not in existing_tags:
                    metadata["tags"].append(tag)

            return jsonify({
                "ok": True,
                "metadata": metadata,
                "channelType": "senior-nostalgia",
                "usage": {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens
                }
            })
        else:
            return jsonify({"ok": False, "error": "메타데이터 파싱 실패", "raw": result_text})
    except Exception as e:
        print(f"[METADATA-NOSTALGIA] 오류: {e}")
        return jsonify({"ok": False, "error": str(e)})


@app.route('/api/drama/generate-metadata', methods=['POST'])
def api_generate_metadata():
    """대본에서 YouTube 메타데이터 자동 생성 (제목, 설명, 태그)"""
    try:
        data = request.get_json()
        script = data.get('script', '')
        content_type = data.get('contentType', 'testimony')
        channel_type = data.get('channelType', 'default')  # 'default', 'senior-nostalgia'

        if not script:
            return jsonify({"ok": False, "error": "대본이 없습니다"}), 400

        # 대본 앞부분만 사용 (토큰 절약)
        script_preview = script[:2000] if len(script) > 2000 else script

        # ⭐ 시니어 향수 채널 전용 메타데이터 생성
        if channel_type == "senior-nostalgia" or content_type == "nostalgia":
            return _generate_senior_nostalgia_metadata(script_preview)

        content_type_name = "간증" if content_type == "testimony" else "드라마"

        # ⭐ contentType에 따른 동적 태그 및 예시 설정
        if content_type == "testimony":
            title_tag = "[신앙간증]"
            title_examples = '''- "[신앙간증] 시한부 3개월, 죽음의 문턱에서 살려주신 하나님 | 꿈에서 만난 주님, 그리고 기적"
- "[신앙간증] 교회 개척 5번이나 막으신 하나님의 진짜 이유 | 막힌 길 뒤에 열린 기적"
- "[신앙간증] 왜 잘 사는 사람들의 기도만 빨리 응답될까요? | 하나님을 믿어도 여전히 힘든 분들에게..."
- "[신앙간증] 새벽 2시 30분의 심방 | 대리 운전 중 일어난 놀라운 기적"'''
        else:
            title_tag = ""  # 드라마는 태그 없이 시작
            title_examples = '''- "1970년대 충무로 사진관, 그 시절 우리 가족 이야기 | 아버지의 카메라가 담은 추억"
- "78세 할머니의 첫사랑 | 50년 만에 다시 만난 그 사람"
- "시골 마을에서 펼쳐진 작은 기적 | 이웃의 따뜻한 손길"
- "6.25 전쟁 속 우리 가족 | 아버지가 남기신 마지막 편지"'''

        system_prompt = f"""당신은 YouTube 콘텐츠 메타데이터 전문가입니다.
주어진 {content_type_name} 대본을 분석하여 YouTube 업로드용 메타데이터를 생성하세요.

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "title": "{title_tag + ' ' if title_tag else ''}시청자의 호기심을 자극하는 제목 (60자 이내)",
  "thumbnailTitle": "썸네일용 제목 (3~4줄, 줄바꿈으로 구분)",
  "description": "영상 설명 (스토리형 구조)",
  "tags": ["태그1", "태그2", "태그3", ...] (10-15개)
}}

【 제목 작성 가이드 - 고성과 패턴 】
{f'★ 필수: {title_tag} 태그로 시작' if title_tag else '★ 태그 없이 바로 제목으로 시작'}

■ 패턴 A: 질문형 후킹
- "왜 잘 사는 사람들의 기도만 빨리 응답될까요?"
- "왜 나만 이렇게 힘들까?" 하고 좌절하시는 분
- "그때 그 순간, 무슨 일이 있었을까요?"

■ 패턴 B: 서사형 대비 - 조회수 높음
- "화려한 시절에서 쫓겨나 다시 시작한 이야기"
- Before(고난/과거) → After(극복/현재)의 극적 대비

■ 필수 요소:
1. 구체적 숫자: "6년간", "3개월", "5번이나", "300만원", "78세"
2. 인물+구체적 상황: "47세 건설 현장소장", "평생 까막눈으로 살다"
3. 감정 키워드: "처절한", "막힌 길", "기적", "놀라운", "그리운"
4. | 구분자로 부제목 추가: "| 그때 그 시절의 이야기"

■ 실제 고성과 제목 예시:
{title_examples}

【 썸네일 제목 가이드 】
- 3~4줄로 나누어 작성 (줄바꿈 \\n 사용)
- 1줄: 시간/숫자 + 상황 훅 (극적 상황)
- 2줄: 핵심 인물/사건 (구체적 묘사)
- 3줄: 감정 강조 (색상 강조될 부분) - "처절한", "막막한", "기적"
- 4줄: 반전/결과 또는 궁금증

예시:
"시한부 3개월\\n죽음의 문턱에서\\n꿈에서 만난 주님\\n그리고 일어난 기적"
"대형교회에서 쫓겨나\\n상가 7층에서 다시 시작\\n단 10명의 성도\\n하나님이 세우신 교회"

【 설명 작성 가이드 - 스토리형 구조 】
■ 구조:
1. 스토리 도입 (짧은 문장으로 상황 설정)
2. 갈등/위기 묘사 (구체적 숫자와 상황)
3. 궁금증 유발 질문 2-3개
4. 타겟 시청자 명시
5. CTA (댓글, 구독, 좋아요)

■ 예시:
"47세 건설 현장소장 박진수.
20년간 성실하게 일하며 가족을 책임지던 평범한 가장이었습니다.

2023년 가을, 간암 말기 진단.
이미 폐까지 전이된 4기 암.
의사는 3개월 시한부를 선고했습니다.

절망 속에서 처음으로 하나님께 간절히 부르짖었고,
꿈에서 주님을 만났습니다.

과연 그에게 무슨 일이 일어났을까요?
의사들도 믿을 수 없어 했던 그 결과는?

💬 이런 분들께 추천합니다:
✔ 오랫동안 기도해도 응답이 없어 힘드신 분
✔ '왜 나만 이렇게 힘들까?' 하고 좌절하시는 분
✔ 가난과 고통 속에서 하나님을 원망하게 되시는 분

🙏 영상이 도움이 되셨다면 댓글로 은혜를 나눠주세요.
📌 구독과 좋아요, 알림 설정 부탁드립니다!"

【 태그 가이드 】
{f'필수 태그: #신앙간증 #기도응답 #은혜간증 #감동간증 #교회이야기' if content_type == 'testimony' else '필수 태그: #감동영상 #힐링 #추억 #가족이야기 #인생드라마'}
{f'상황별 태그: #목회자간증 #암투병 #기적 #하나님의인도하심 #새벽기도 #금식기도' if content_type == 'testimony' else '상황별 태그: #그시절 #70년대 #80년대 #레트로 #빈티지 #옛날이야기'}
{f'감정 태그: #희망이야기 #위로 #구원 #회개' if content_type == 'testimony' else '감정 태그: #희망이야기 #위로 #그리움 #감동'}"""

        user_prompt = f"다음 {content_type_name} 대본의 메타데이터를 생성하세요:\n\n{script_preview}"

        response = client.chat.completions.create(
            model="gpt-4o",  # gpt-4o 사용 (제목, 설명, 태그 품질 향상)
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )

        result_text = response.choices[0].message.content.strip()

        # JSON 파싱 시도
        import re
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            metadata = json.loads(json_match.group())
            return jsonify({
                "ok": True,
                "metadata": metadata,
                "usage": {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens
                }
            })
        else:
            return jsonify({"ok": False, "error": "메타데이터 파싱 실패", "raw": result_text})

    except json.JSONDecodeError as e:
        return jsonify({"ok": False, "error": f"JSON 파싱 오류: {str(e)}"})
    except Exception as e:
        print(f"[METADATA] 오류: {e}")
        return jsonify({"ok": False, "error": str(e)})

@app.route('/api/drama/step3-test', methods=['GET'])
def api_drama_step3_test():
    """Step3 테스트 엔드포인트"""
    return jsonify({
        "ok": True,
        "openrouter_configured": openrouter_client is not None,
        "message": "Step3 endpoint is reachable"
    })


@app.route('/api/drama/claude-step3', methods=['POST'])
def api_drama_claude_step3():
    """Step3: OpenRouter를 통한 드라마 대본 완성"""
    try:
        print("[DRAMA-STEP3] 요청 받음")

        if not openrouter_client:
            print("[DRAMA-STEP3] OpenRouter 클라이언트 없음")
            return jsonify({"ok": False, "error": "OpenRouter API key not configured. Render 환경변수에 OPENROUTER_API_KEY를 설정해주세요."}), 200

        data = request.get_json()
        if not data:
            print("[DRAMA-STEP3] 데이터 없음")
            return jsonify({"ok": False, "error": "No data received"}), 200

        category = data.get("category", "")
        video_category = data.get("videoCategory", "간증")  # 영상 카테고리 (간증, 드라마, 명언, 마음, 철학, 인간관계)
        custom_directive = data.get("customDirective", "")  # 사용자 지침 (선택) - 최우선 반영
        style_name = data.get("styleName", "")
        style_description = data.get("styleDescription", "")
        draft_content = data.get("draftContent", "")
        main_character = data.get("mainCharacter", {})
        benchmark_script = data.get("benchmarkScript", "")
        ai_analysis = data.get("aiAnalysis", "")
        step3_guide = data.get("step3Guide", "")
        selected_model = data.get("model", "anthropic/claude-sonnet-4.5")
        content_type = data.get("contentType", "testimony")  # 콘텐츠 유형 (testimony/drama)
        content_type_prompt = data.get("contentTypePrompt", {})  # 클라이언트에서 보낸 프롬프트
        duration_text = (data.get("durationText") or "").strip()
        auto_story_mode = bool(data.get("autoStoryMode", False))
        custom_json_guide_str = data.get("customJsonGuide", "")  # 클라이언트에서 보낸 커스텀 JSON 지침
        test_mode = bool(data.get("testMode", False))  # 🧪 테스트 모드 (비용 최소화)

        # 커스텀 JSON 지침 파싱
        custom_json_guide = None
        if custom_json_guide_str:
            try:
                custom_json_guide = json.loads(custom_json_guide_str)
                print(f"[DRAMA-STEP3] 커스텀 JSON 지침 사용 (v{custom_json_guide.get('version', '?')})")
            except json.JSONDecodeError as e:
                print(f"[DRAMA-STEP3] 커스텀 JSON 파싱 실패: {e}, 서버 기본 지침 사용")

        effective_category = duration_text or category
        if effective_category:
            category = effective_category

        print(f"[DRAMA-STEP3-OPENROUTER] 처리 시작 - 시간: {category}, 영상카테고리: {video_category}, 지침: {custom_directive or '(없음)'}, 모델: {selected_model}, 테스트모드: {test_mode}")
        print(f"[DRAMA-STEP3-DEBUG] step3_guide 길이: {len(step3_guide)}, 내용: {step3_guide[:100] if step3_guide else '(없음)'}...")
        print(f"[DRAMA-STEP3-DEBUG] draft_content 길이: {len(draft_content)}, 내용: {draft_content[:300] if draft_content else '(없음)'}...")

        # 콘텐츠 유형별 시스템 프롬프트 결정
        # video_category에 따라 다른 프롬프트 사용
        user_prompt_suffix = ""

        # 영상 카테고리별 기본 프롬프트 매핑
        video_category_prompts = {
            "명언": """당신은 깊은 울림을 주는 명언 콘텐츠 전문 작가입니다.

【 명언 콘텐츠의 핵심 】
삶의 지혜와 통찰을 담은 명언을 중심으로, 시청자에게 생각할 거리와 영감을 주는 콘텐츠입니다.

【 필수 요소 】
1. 명언의 의미를 실생활 사례로 풀어서 설명
2. 1인칭 서술로 개인적 경험과 연결
3. 짧은 문장과 강렬한 메시지
4. 시청자가 공감할 수 있는 보편적 주제

【 금지 사항 】
- 추상적이고 모호한 표현
- 마크다운 기호(#, *, -, **) 사용 금지""",
            "마음": """당신은 마음 치유 콘텐츠 전문 작가입니다.

【 마음 콘텐츠의 핵심 】
지친 마음을 위로하고 치유하는 감성적인 이야기입니다. 시청자가 "나도 그랬어"라고 공감하며 위안을 받을 수 있어야 합니다.

【 필수 요소 】
1. 부드럽고 따뜻한 어조
2. 감정의 구체적 묘사
3. 희망과 치유의 메시지
4. 공감을 이끌어내는 일상 소재

【 금지 사항 】
- 설교하거나 가르치려는 톤
- 마크다운 기호(#, *, -, **) 사용 금지""",
            "철학": """당신은 철학적 사유 콘텐츠 전문 작가입니다.

【 철학 콘텐츠의 핵심 】
인생, 존재, 의미에 대한 깊은 성찰을 담은 콘텐츠입니다. 시청자가 생각에 잠기게 만드는 질문을 던집니다.

【 필수 요소 】
1. 깊이 있는 질문 제시
2. 일상에서 철학적 의미 발견
3. 다양한 관점 제시
4. 열린 결말로 사유 유도

【 금지 사항 】
- 너무 어려운 철학 용어
- 마크다운 기호(#, *, -, **) 사용 금지""",
            "인간관계": """당신은 인간관계 콘텐츠 전문 작가입니다.

【 인간관계 콘텐츠의 핵심 】
가족, 친구, 연인, 동료 등 다양한 관계에서 일어나는 이야기입니다. 관계의 소중함과 어려움을 함께 다룹니다.

【 필수 요소 】
1. 구체적인 관계 상황 묘사
2. 갈등과 화해의 과정
3. 대화를 통한 감정 전달
4. 관계 속 성장 이야기

【 금지 사항 】
- 일방적인 조언이나 훈계
- 마크다운 기호(#, *, -, **) 사용 금지""",

            # ===== 시니어 타겟 신규 카테고리 =====
            "옛날이야기": """당신은 시니어를 위한 향수 콘텐츠 전문 작가입니다.

반드시 JSON 형식으로 대본을 출력해야 합니다.

═══════════════════════════════════════════════════
【 옛날이야기 대본 작성 핵심 원칙 】
═══════════════════════════════════════════════════

1. 화자: 60-70대 어르신이 회상하며 들려주는 형식
   - "그때는 말이야...", "지금 젊은 사람들은 모르겠지만..."
   - 친근하고 따뜻한 말투 (구어체)

2. 시대 고증:
   - 1960s-1980s 한국의 실제 모습
   - 당시 물가, 풍습, 생활용품 정확히
   - 지역별 특색 (서울, 부산, 시골 등)

3. 오감 묘사 필수:
   - 소리: 새마을호 기적소리, 두부장수 종소리
   - 냄새: 연탄 냄새, 어머니 된장국 냄새
   - 촉감: 한여름 멍석 위, 겨울 화롯불 온기
   - 시각: 흑백TV, 달동네 골목
   - 맛: 쫀드기, 아이스께끼, 군고구마

4. 감정 곡선:
   - 시작: 호기심/그리움 유발 (강렬한 후킹)
   - 중반: 구체적 추억으로 몰입
   - 끝: 따뜻한 여운 + 긍정 마무리

5. 금지:
   - 정치적 내용
   - 세대 비하/갈등 조장
   - 우울하거나 비관적 결말
   - 마크다운 기호(#, *, -, **) 사용 금지

【 후킹 예시 】
- "혹시 기억하시나요? 새벽 다섯 시, 연탄 가스 냄새에 잠이 깨던 그 시절..."
- "지금 젊은 사람들은 모르겠지만, 우리는 전화기 한 대에 온 동네가 모여들었습니다."
- "칠십 년대 여름, 선풍기도 귀하던 시절. 우리는 어떻게 더위를 이겼을까요?"

【 출력 형식 】
반드시 JSON으로 출력. metadata, highlight, script, closing 구조 준수.""",

            "마음위로": """당신은 잠들기 전 마음 위로 콘텐츠 전문 작가입니다.

반드시 JSON 형식으로 대본을 출력해야 합니다.

═══════════════════════════════════════════════════
【 마음위로 대본 작성 핵심 원칙 】
═══════════════════════════════════════════════════

1. 화자: 친근한 이웃 어르신이 따뜻하게 말해주는 형식
   - 부드럽고 차분한 어조
   - "괜찮아요", "수고했어요" 같은 위로의 말

2. 목적: 잠들기 전 편안함 제공
   - ASMR 느낌의 차분한 나레이션
   - 긴장을 풀어주는 내용
   - 내일에 대한 희망

3. 구성:
   - 시작: 부드러운 인사와 공감
   - 중반: 위로가 되는 이야기/생각
   - 끝: 평안한 잠자리 기원

4. 감정:
   - 따뜻함, 평온함, 안정감
   - 시청자를 판단하지 않음
   - 있는 그대로 인정

5. 금지:
   - 자극적이거나 긴장되는 내용
   - 슬프거나 우울한 결말
   - 빠른 전개
   - 마크다운 기호(#, *, -, **) 사용 금지""",

            "인생명언": """당신은 인생 지혜와 명언 콘텐츠 전문 작가입니다.

반드시 JSON 형식으로 대본을 출력해야 합니다.

═══════════════════════════════════════════════════
【 인생명언 대본 작성 핵심 원칙 】
═══════════════════════════════════════════════════

1. 화자: 인생 경험 많은 어르신이 지혜를 나누는 형식
   - "살다 보니 이런 걸 알게 됐어요"
   - 설교가 아닌 나눔의 톤

2. 명언 활용:
   - 유명 명언 + 개인적 해석
   - 또는 삶에서 깨달은 나만의 명언
   - 추상적이지 않고 구체적 사례와 함께

3. 구성:
   - 시작: 공감되는 상황 제시
   - 중반: 명언/지혜 소개 + 실제 사례
   - 끝: 시청자에게 적용할 수 있는 메시지

4. 명언 출처 예시:
   - 동양 고전 (논어, 도덕경, 명심보감)
   - 서양 철학자 (소크라테스, 니체, 쇼펜하우어)
   - 한국 속담, 어르신 말씀
   - 시청자 스스로 깨달을 수 있게 유도

5. 금지:
   - 너무 어려운 철학 용어
   - 일방적 설교/훈계
   - 특정 종교 강요
   - 마크다운 기호(#, *, -, **) 사용 금지"""
        }

        # video_category가 특별한 카테고리면 해당 프롬프트 사용
        if video_category in video_category_prompts:
            system_content = video_category_prompts[video_category]
            print(f"[DRAMA-STEP3] 영상카테고리 '{video_category}' 전용 프롬프트 사용")
        elif video_category == "간증" or content_type == "testimony":
            # category에서 duration_minutes 추출 (예: "10min" -> 10, "20min" -> 20)
            duration_minutes = 20  # 기본값
            if category:
                duration_match = re.search(r'(\d+)', category)
                if duration_match:
                    duration_minutes = int(duration_match.group(1))

            # JSON 스타일 가이드에서 프롬프트 구축 (커스텀 가이드 우선 사용)
            guide_system, guide_suffix = build_testimony_prompt_from_guide(custom_json_guide, duration_minutes, test_mode)
            if guide_system:
                system_content = guide_system
                user_prompt_suffix = guide_suffix or ""
                guide_version = custom_json_guide.get('version', '?') if custom_json_guide else load_drama_guidelines().get('version', '?')
                guide_source = "커스텀" if custom_json_guide else "서버"
                print(f"[DRAMA-STEP3] {guide_source} JSON 스타일 가이드 프롬프트 사용 (v{guide_version})")
            else:
                # JSON 로드 실패 시 기본 프롬프트 (폴백)
                print(f"[DRAMA-STEP3] JSON 로드 실패, 기본 프롬프트 사용")
                system_content = """당신은 감동적인 간증 콘텐츠 전문 작가입니다.

【 간증 콘텐츠의 핵심 】
간증은 실제 경험을 바탕으로 한 이야기입니다. 시청자가 "이건 진짜 이야기구나"라고 느끼도록 생생하고 구체적으로 작성해야 합니다.

【 필수 요소 】
1. 반드시 1인칭 서술 ("저는", "제가") - 절대 3인칭 금지
2. 총 15,000자 이상 분량
3. 구체적 이름 5개, 숫자 10개, 장소 3개 이상
4. 직접 대화 30% 포함
5. 가족 반응 필수 포함

【 금지 사항 】
- 3인칭 서술 (그는, 그녀는) 절대 금지
- 마크다운 기호(#, *, -, **) 사용 금지
- 짧은 분량"""
        elif content_type_prompt and content_type_prompt.get("systemPrompt"):
            # 클라이언트에서 보낸 콘텐츠 유형별 프롬프트 사용
            system_content = content_type_prompt.get("systemPrompt", "")
            user_prompt_suffix = content_type_prompt.get("userPromptSuffix", "")
            print(f"[DRAMA-STEP3] 클라이언트 프롬프트 사용 ({content_type})")
        else:
            # 드라마 기본 프롬프트
            system_content = """당신은 전문 드라마 대본 작가입니다.

【 드라마 대본의 핵심 】
시청자를 화면 속으로 끌어들이는 몰입감 있는 스토리를 만들어야 합니다.

【 필수 요소 】
1. 캐릭터의 입체성 - 명확한 목표와 내면의 갈등
2. 장면 구성 - 각 장면의 목적이 분명
3. 대사의 힘 - 캐릭터의 성격이 드러나는 대사
4. 갈등과 긴장 - 예상치 못한 반전과 전개

【 금지 사항 】
- 마크다운 기호(#, *, -, **) 사용 금지
- 지루한 설명이나 독백"""

        # 사용자 지침이 있으면 시스템 프롬프트에 추가
        if step3_guide:
            system_content += """

【 중요: 사용자 지침 최우선 】
⚠️ 사용자가 제공하는 '작성 지침'이 있다면, 해당 지침의 형식과 규칙을 반드시 따르세요.
⚠️ 기본 형식보다 사용자 지침이 우선합니다.
⚠️ 사용자 지침에서 금지하는 표현은 절대 사용하지 마세요."""

        # 사용자 메시지 구성
        user_content = ""

        # 🔥 사용자 지침 (최우선 적용)
        if custom_directive:
            user_content += "【 🔥 사용자 지침 (최우선 적용) 】\n"
            user_content += f"{custom_directive}\n"
            user_content += "→ 이 지침을 가장 우선적으로 반영하여 대본을 작성하세요.\n\n"

        # 메타 정보 추가
        meta_lines = []
        if category:
            meta_lines.append(f"- 드라마 유형/영상 시간: {category}")
        if style_name:
            meta_lines.append(f"- 드라마 스타일: {style_name}")
        if style_description:
            meta_lines.append(f"- 스타일 설명: {style_description}")

        # 주인공 정보 추가
        if main_character:
            char_info = []
            if main_character.get("name"):
                char_info.append(f"이름: {main_character['name']}")
            if main_character.get("age"):
                char_info.append(f"나이: {main_character['age']}")
            if main_character.get("personality"):
                char_info.append(f"성격: {main_character['personality']}")
            if char_info:
                meta_lines.append(f"- 주인공: {', '.join(char_info)}")

        if meta_lines:
            user_content += "【 기본 정보 】\n"
            user_content += "\n".join(meta_lines)
            user_content += "\n\n"

        # 벤치마킹 대본 (있다면)
        if benchmark_script:
            user_content += "【 벤치마킹 대본 (참고용) 】\n"
            user_content += benchmark_script[:3000] + ("..." if len(benchmark_script) > 3000 else "")
            user_content += "\n\n"

        # AI 분석 결과 (있다면)
        if ai_analysis:
            user_content += "【 AI 분석 결과 】\n"
            user_content += ai_analysis[:2000] + ("..." if len(ai_analysis) > 2000 else "")
            user_content += "\n\n"

        # Step2 결과 (드라마 초안 자료)
        if draft_content:
            user_content += "【 Step2 작업 결과 (참고 자료) 】\n"
            user_content += draft_content
            user_content += "\n\n"
        elif auto_story_mode:
            user_content += "【 Step2 자료 없이 작성 지시 】\n"
            user_content += "입력된 영상 시간과 지침만을 기반으로 완전히 새로운 드라마를 작성하세요."
            user_content += " 주인공, 배경, 갈등, 전환점을 자유롭게 설계하고, 참고 자료가 없더라도 자연스럽게 이어지는 스토리라인을 만들어주세요."
            user_content += "\n\n"

        # Step3 사용자 지침 (있다면)
        if step3_guide:
            user_content += "【 ⭐ 작성 지침 (최우선 적용) 】\n"
            user_content += step3_guide
            user_content += "\n\n위 지침을 반드시 우선적으로 따라 대본을 작성해주세요.\n\n"

        # 대본 작성 요청 - 영상 시간 기반 분량 지시 (모든 콘텐츠 유형에 적용!)
        content_type_name = "간증" if content_type == "testimony" else "드라마"

        # 영상 시간(분) 추출 - category에서 숫자 파싱
        minutes_match = re.search(r"(\d+)\s*분?", category) or re.search(r"(\d+)", category)
        minutes_value = int(minutes_match.group(1)) if minutes_match else None

        print(f"[DRAMA-STEP3] 분량 계산 - category: '{category}', 추출된 시간: {minutes_value}분, 테스트모드: {test_mode}")

        # 🧪 테스트 모드: 최소 분량 (모든 콘텐츠 유형에 적용!)
        if test_mode:
            length_guide = "약 500자 내외로 (테스트용 최소 분량 - 절대 초과 금지!)"
            target_chars = 500
            print(f"[DRAMA-STEP3] 🧪 테스트 모드: 분량 제한 500자")
        else:
            # ⚠️ 모든 콘텐츠 유형에 영상 시간 설정 적용! (간증도 예외 없음)
            if minutes_value and minutes_value <= 2:
                length_guide = "약 500~800자 분량으로 (2분 영상)"
                target_chars = 700
            elif minutes_value and minutes_value <= 5:
                length_guide = "약 1500~2000자 분량으로 (5분 영상)"
                target_chars = 1800
            elif minutes_value and minutes_value <= 10:
                length_guide = "약 3000~4000자 분량으로 (10분 영상)"
                target_chars = 3500
            elif minutes_value and minutes_value <= 15:
                length_guide = "약 5000~6000자 분량으로 (15분 영상)"
                target_chars = 5500
            elif minutes_value and minutes_value <= 20:
                length_guide = "약 6000~8000자 분량으로 (20분 영상)"
                target_chars = 7000
            elif minutes_value and minutes_value <= 30:
                length_guide = "약 9000~12000자 분량으로 (30분 영상)"
                target_chars = 10000
            elif minutes_value:
                length_guide = f"약 {minutes_value * 400}자 분량으로 ({minutes_value}분 영상)"
                target_chars = minutes_value * 400
            else:
                # 시간 설정이 없으면 기본 10분
                length_guide = "약 3000~4000자 분량으로 (기본 10분 영상)"
                target_chars = 3500
                print(f"[DRAMA-STEP3] ⚠️ 영상 시간 설정 없음 → 기본 10분(3500자) 적용")

            print(f"[DRAMA-STEP3] 분량 설정: {length_guide} (목표: {target_chars}자)")

        # 분량 지시 (테스트 모드 여부에 따라 다르게)
        if test_mode:
            length_instruction = f"🧪 테스트 모드: {length_guide} - 절대 초과하지 마세요!"
        else:
            length_instruction = f"⚠️ 분량: {length_guide} - 이 분량을 정확히 맞춰주세요!"

        # 간증 콘텐츠 전용 요청 사항
        if content_type == "testimony":
            user_content += f"""【 요청 사항 】
위 자료를 참고하여 완성된 {content_type_name} 콘텐츠를 작성해주세요.

🚨 필수 요구사항 (반드시 준수!):
1. 첫 문장: "안녕하세요. 저는 [장소]에서 [역할]을 하고 있는 [이름]입니다." 형식
2. {length_instruction}
3. 시점: 반드시 1인칭 (저는, 제가) - 3인칭(그는, 그녀는) 절대 금지!
4. 마크다운 기호(#, *, -, **) 대신 순수 텍스트로 작성하세요.

{user_prompt_suffix}"""
        else:
            user_content += f"""【 요청 사항 】
위 자료를 참고하여 완성된 {content_type_name} 콘텐츠를 작성해주세요.

{length_instruction}

작성 시 주의사항:
1. 자료는 참고만 하고, 콘텐츠는 처음부터 새로 구성하세요.
2. 자연스럽고 몰입감 있게 작성하세요.
3. 감정선이 점진적으로 발전하도록 구성하세요.
4. 인트로 → 갈등/전개 → 터닝포인트 → 회복/결말 구조를 따르세요.
5. 마크다운 기호(#, *, -, **) 대신 순수 텍스트로 작성하세요.
{user_prompt_suffix}"""

        # OpenRouter API 호출 (OpenAI 호환)
        # max_tokens는 목표 글자수 기반으로 계산 (한글 1자 ≈ 2~3토큰, JSON 오버헤드 고려)
        if test_mode:
            max_output_tokens = 8000  # 테스트 모드: JSON 대본 생성에 충분하게
        else:
            # 목표 글자수 * 4 (JSON 메타데이터 + 한글 토큰 오버헤드) + 여유분
            max_output_tokens = min(32000, max(8000, int(target_chars * 4)))

        print(f"[DRAMA-STEP3] max_output_tokens: {max_output_tokens}")

        # 타임아웃 설정 (Render 무료 티어 30초 제한 대응)
        # 테스트 모드: 25초 / 일반 모드: 120초 (유료 티어 필요)
        api_timeout = 25 if test_mode else 120
        print(f"[DRAMA-STEP3] API 타임아웃: {api_timeout}초")

        try:
            response = openrouter_client.chat.completions.create(
                model=selected_model,
                max_tokens=max_output_tokens,
                messages=[
                    {
                        "role": "system",
                        "content": system_content
                    },
                    {
                        "role": "user",
                        "content": user_content
                    }
                ],
                temperature=0.8,
                timeout=api_timeout
            )
        except Exception as api_error:
            error_str = str(api_error).lower()
            if 'timeout' in error_str or 'timed out' in error_str:
                print(f"[DRAMA-STEP3] API 타임아웃 발생: {api_error}")
                raise RuntimeError(
                    f"대본 생성 시간이 {api_timeout}초를 초과했습니다. "
                    "영상 시간을 줄이거나(2분/5분) 테스트 모드를 사용해주세요."
                )
            raise

        # 응답 추출 (상세 로깅 추가)
        print(f"[DRAMA-STEP3] OpenRouter 응답 수신")
        print(f"[DRAMA-STEP3] choices 개수: {len(response.choices) if response.choices else 0}")

        if not response.choices:
            print(f"[DRAMA-STEP3] 전체 응답: {response}")
            raise RuntimeError("OpenRouter API 응답에 choices가 없습니다. API 키나 모델 설정을 확인하세요.")

        # finish_reason 확인
        finish_reason = response.choices[0].finish_reason if response.choices else None
        print(f"[DRAMA-STEP3] finish_reason: {finish_reason}")

        if finish_reason == "content_filter":
            raise RuntimeError("OpenRouter 콘텐츠 필터에 의해 차단되었습니다. 주제를 변경해보세요.")

        result = response.choices[0].message.content if response.choices else ""
        print(f"[DRAMA-STEP3] 응답 길이: {len(result) if result else 0}자")
        result = result.strip() if result else ""

        # finish_reason: length인 경우 - 응답이 잘렸지만 부분 응답이라도 사용
        if finish_reason == "length" and result:
            print(f"[DRAMA-STEP3] ⚠️ 응답이 max_tokens에서 잘림, 부분 응답 사용 ({len(result)}자)")
            # JSON이 불완전할 수 있으므로 복구 시도
            if result.startswith('{') and not result.endswith('}'):
                # 불완전한 JSON 복구 시도
                result = result + '"}]}'
                print(f"[DRAMA-STEP3] JSON 복구 시도")

        if not result:
            print(f"[DRAMA-STEP3] 빈 응답, finish_reason: {finish_reason}")
            if finish_reason == "length":
                raise RuntimeError(f"응답이 토큰 제한으로 잘렸습니다. 대본 길이를 줄이거나 다시 시도해주세요.")
            else:
                raise RuntimeError(f"OpenRouter API로부터 빈 응답. finish_reason: {finish_reason}")

        # JSON 응답에서 불필요한 마크다운 코드블록 제거 (```json ... ``` 형식)
        import re as re_temp
        json_block_pattern = r'^```(?:json)?\s*\n?(.*?)\n?```$'
        json_match = re_temp.search(json_block_pattern, result.strip(), re_temp.DOTALL)
        if json_match:
            result = json_match.group(1).strip()

        # ⚠️ 중요: JSON 형식 결과에는 앞에 추가 정보를 붙이면 안 됨!
        # JSON 파싱이 실패하여 대본 뷰어가 작동하지 않게 됨
        # 기존에 추가하던 "드라마 스타일:", "드라마 유형:" 정보는 JSON metadata에 이미 포함됨
        final_result = result

        # 토큰 사용량 추출
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        # Claude Sonnet 4.5 비용 계산 (원화): input $3/1M, output $15/1M → 환율 1400원
        # input: 3 * 1400 / 1000000 = 0.0042원/token
        # output: 15 * 1400 / 1000000 = 0.021원/token
        cost = round(input_tokens * 0.0042 + output_tokens * 0.021, 2)

        print(f"[DRAMA-STEP3-OPENROUTER] 완료 - 토큰: {input_tokens}/{output_tokens}, 비용: ₩{cost}")

        return jsonify({
            "ok": True,
            "result": final_result,
            "cost": cost,
            "tokens": input_tokens + output_tokens,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens
            }
        })

    except Exception as e:
        print(f"[DRAMA-STEP3-OPENROUTER][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== AI 챗봇 API =====
@app.route('/api/drama/chat', methods=['POST'])
def api_drama_chat():
    """드라마 페이지 AI 챗봇 - 현재 작업 상황에 대해 질문/답변"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        question = data.get("question", "")
        context = data.get("context", {})  # 현재 작업 상태
        selected_model = data.get("model", "gpt-4o-mini")  # 선택된 모델

        # 허용된 모델 목록 (비용 절감을 위해 gpt-4o-mini 권장)
        allowed_models = ["gpt-4o-mini", "gpt-4o"]
        if selected_model not in allowed_models:
            selected_model = "gpt-4o-mini"

        if not question:
            return jsonify({"ok": False, "error": "질문을 입력해주세요."}), 400

        print(f"[DRAMA-CHAT] 모델: {selected_model}, 질문: {question[:100]}...")

        # 컨텍스트 구성
        context_text = ""

        # 워크플로우 박스 결과들
        if context.get("workflowResults"):
            context_text += "【현재 작업 상태】\n"
            for box in context.get("workflowResults", []):
                if box.get("result"):
                    context_text += f"\n## {box.get('name', '작업 박스')}\n{box.get('result', '')[:2000]}\n"

        # Step3 결과
        if context.get("step3Result"):
            context_text += f"\n【Step3 최종 결과】\n{context.get('step3Result', '')[:3000]}\n"

        # 벤치마크 스크립트
        if context.get("benchmarkScript"):
            context_text += f"\n【벤치마크 대본 (참고용)】\n{context.get('benchmarkScript', '')[:1500]}\n"

        # 오류 정보
        if context.get("lastError"):
            context_text += f"\n【최근 오류】\n{context.get('lastError', '')}\n"

        # 시스템 프롬프트
        system_prompt = """당신은 드라마 대본 작성을 돕는 AI 어시스턴트입니다.
사용자가 현재 작업 중인 드라마 대본에 대해 질문하면, 주어진 컨텍스트를 바탕으로 도움이 되는 답변을 제공합니다.

역할:
1. 현재 작업 상황 분석 및 설명
2. 개선 제안 및 아이디어 제공
3. 오류나 문제점 해결 도움
4. 스토리, 캐릭터, 대사 등에 대한 피드백
5. 다음 단계 진행 가이드

답변 시 유의사항:
- 간결하고 실용적인 답변을 제공하세요
- 구체적인 예시나 제안을 포함하세요
- 한국어로 친절하게 답변하세요
- 현재 작업 상태를 고려하여 맥락에 맞는 답변을 하세요"""

        # 사용자 메시지 구성
        user_content = ""
        if context_text:
            user_content += f"{context_text}\n\n"
        user_content += f"【질문】\n{question}"

        # GPT 호출 (선택된 모델 사용)
        completion = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7,
            max_tokens=4000 if selected_model in ["gpt-4o", "gpt-5"] else 2000
        )

        answer = completion.choices[0].message.content.strip()

        # 토큰 사용량
        usage = {
            "input_tokens": completion.usage.prompt_tokens,
            "output_tokens": completion.usage.completion_tokens,
            "model": selected_model
        }

        print(f"[DRAMA-CHAT][SUCCESS] {selected_model}로 답변 생성 완료")
        return jsonify({"ok": True, "answer": answer, "usage": usage})

    except Exception as e:
        print(f"[DRAMA-CHAT][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== Step4: 이미지 프롬프트 생성 API =====
@app.route('/api/drama/generate-image-prompts', methods=['POST'])
def api_generate_image_prompts():
    """대본을 분석하여 인물/배경/통합 이미지 프롬프트 생성"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        script = data.get("script", "")
        main_character = data.get("mainCharacter", "")

        if not script:
            return jsonify({"ok": False, "error": "대본이 없습니다."}), 400

        print(f"[DRAMA-STEP4-PROMPT] 이미지 프롬프트 생성 시작")

        # GPT를 사용하여 이미지 프롬프트 생성
        system_content = """당신은 드라마 대본을 분석하여 DALL-E 3 이미지 생성을 위한 프롬프트를 작성하는 전문가입니다.

대본을 읽고 다음 세 가지 프롬프트를 영어로 작성해주세요:

1. 인물 프롬프트 (Character Prompt)
   - 주인공의 외모, 표정, 의상, 자세를 묘사
   - 나이, 성별, 분위기를 포함
   - 🚨 반드시 프롬프트 맨 앞에 한국인 특징을 배치: "Korean person from South Korea with authentic Korean/East Asian ethnicity, Korean facial bone structure, Korean skin tone"
   - 예: "Korean woman from South Korea with authentic Korean ethnicity, Korean facial features, Korean skin tone, in her late 20s, gentle and warm expression, wearing a soft beige cardigan"

2. 배경 프롬프트 (Background Prompt)
   - 장면의 배경, 장소, 시간대, 분위기를 묘사
   - 조명, 색감, 분위기를 포함
   - 예: "A cozy Korean cafe interior, warm afternoon sunlight streaming through large windows, wooden furniture, soft ambient lighting"

3. 통합 장면 프롬프트 (Combined Scene Prompt)
   - 인물이 배경에 자연스럽게 어울리는 완전한 장면 묘사
   - 영화적이고 시각적으로 매력적인 구도
   - 🚨 반드시 프롬프트 맨 앞에 한국인 특징을 배치
   - 예: "Korean woman from South Korea with authentic Korean ethnicity and Korean facial features, in her late 20s, sitting by the window in a cozy cafe, warm afternoon sunlight illuminating her gentle smile"

응답 형식:
CHARACTER_PROMPT: [인물 프롬프트]
BACKGROUND_PROMPT: [배경 프롬프트]
COMBINED_PROMPT: [통합 프롬프트]

🚨 매우 중요 - 한국인 외모 필수:
- 모든 인물 프롬프트는 반드시 맨 앞에 "Korean person from South Korea with authentic Korean/East Asian ethnicity, Korean facial bone structure, Korean skin tone"를 포함
- 절대로 "Asian" 단독 사용 금지 - 반드시 "Korean"을 명시
- DALL-E 3에 최적화된 상세하고 시각적인 묘사
- 부정적이거나 폭력적인 내용 제외"""

        user_content = f"""다음 드라마 대본을 분석하여 이미지 프롬프트를 생성해주세요.

[주인공 정보]
{main_character if main_character else '(별도 정보 없음 - 대본에서 추출)'}

[드라마 대본]
{script[:4000]}

위 대본의 핵심 장면에 대한 이미지 프롬프트를 생성해주세요."""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7
        )

        result = completion.choices[0].message.content.strip()

        # 프롬프트 파싱
        character_prompt = ""
        background_prompt = ""
        combined_prompt = ""

        lines = result.split('\n')
        current_type = None

        for line in lines:
            line = line.strip()
            if line.startswith('CHARACTER_PROMPT:'):
                current_type = 'character'
                character_prompt = line.replace('CHARACTER_PROMPT:', '').strip()
            elif line.startswith('BACKGROUND_PROMPT:'):
                current_type = 'background'
                background_prompt = line.replace('BACKGROUND_PROMPT:', '').strip()
            elif line.startswith('COMBINED_PROMPT:'):
                current_type = 'combined'
                combined_prompt = line.replace('COMBINED_PROMPT:', '').strip()
            elif current_type and line:
                # 여러 줄에 걸친 프롬프트 처리
                if current_type == 'character':
                    character_prompt += ' ' + line
                elif current_type == 'background':
                    background_prompt += ' ' + line
                elif current_type == 'combined':
                    combined_prompt += ' ' + line

        print(f"[DRAMA-STEP4-PROMPT] 프롬프트 생성 완료")

        return jsonify({
            "ok": True,
            "characterPrompt": character_prompt,
            "backgroundPrompt": background_prompt,
            "combinedPrompt": combined_prompt
        })

    except Exception as e:
        print(f"[DRAMA-STEP4-PROMPT][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Step4: 등장인물 및 씬 분석 API =====
@app.route('/api/drama/analyze-characters', methods=['POST'])
def api_analyze_characters():
    """대본을 분석하여 등장인물과 씬 정보 추출"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        script = data.get("script", "")
        duration = data.get("duration", "10min")  # 영상 길이 (기본값: 10분)
        content_type = data.get("content_type", "drama")  # 콘텐츠 타입

        if not script:
            return jsonify({"ok": False, "error": "대본이 없습니다."}), 400

        # duration에 따른 최대 씬 개수 설정
        max_scenes_map = {
            "30s": 1,     # 쇼츠
            "60s": 2,     # 쇼츠
            "3min": 2,
            "5min": 3,
            "10min": 4,
            "20min": 6,
            "30min": 8
        }
        max_scenes = max_scenes_map.get(duration, 4)

        # 쇼츠 여부 판단 (content_type이 shorts이거나 duration이 60s 이하)
        is_shorts = content_type == 'shorts' or duration in ['30s', '60s']

        print(f"[DRAMA-STEP4-ANALYZE] 등장인물 및 씬 분석 시작 (duration: {duration}, max_scenes: {max_scenes}, content_type: {content_type}, is_shorts: {is_shorts})")

        # 콘텐츠 타입별 시스템 프롬프트 분기
        if content_type == 'shorts' or is_shorts:
            # 쇼츠/릴스 콘텐츠 (세로 9:16, 60초 이하)
            system_content = """당신은 YouTube Shorts / Instagram Reels 대본을 분석하여 핵심 장면을 추출하는 전문가입니다.

쇼츠는 세로 형식(9:16)이며 60초 이하의 짧은 영상입니다.
대본을 분석하여 다음 정보를 JSON 형식으로 추출해주세요:

1. 등장인물/요소 (characters): 각 항목에 대해
   - name: 이름 (한글)
   - description: 설명 (한글)
   - imagePrompt: 세로 형식에 최적화된 영어 이미지 프롬프트

2. 씬 (scenes): 각 씬에 대해 (최대 2개)
   - title: 씬 제목 (한글)
   - location: 장소 (한글)
   - description: 씬 설명 (한글)
   - characters: 등장하는 항목들
   - backgroundPrompt: 세로 구도에 맞는 영어 배경 프롬프트

응답 형식은 JSON으로:
{
  "characters": [...],
  "scenes": [...]
}

🚨 쇼츠 이미지 프롬프트 핵심 규칙:
- **세로 구도 (9:16)**: 모든 이미지는 세로 형식, 피사체를 화면 중앙에 배치
- **클로즈업/미디엄샷**: 작은 화면에서 잘 보이도록 가까이 촬영
- **심플한 배경**: 복잡한 배경은 피하고 피사체가 돋보이게
- **강렬한 첫인상**: 첫 씬이 썸네일이 되므로 시선을 끄는 구도
- **텍스트 오버레이 공간**: 상단/하단에 텍스트 영역 확보
- 프롬프트 예시: "Vertical portrait composition (9:16 aspect ratio), [주제] centered in frame, close-up shot, simple blurred background, mobile-optimized framing, high contrast, eye-catching visual"
- ⚠️ 가로 구도 금지, 복잡한 배경 금지, 너무 멀리서 찍은 샷 금지"""

        elif content_type == 'product':
            # 상품 소개 콘텐츠
            system_content = """당신은 상품 소개 대본을 분석하여 제품과 씬 정보를 추출하는 전문가입니다.

대본을 분석하여 다음 정보를 JSON 형식으로 추출해주세요:

1. 등장물 (characters): 제품/상품에 대해
   - name: 제품 이름 (한글)
   - description: 제품 설명 (특징, 기능, 장점 등 - 한글)
   - imagePrompt: 영어 이미지 프롬프트 (제품 외관, 디테일, 사용 장면 묘사)

2. 씬 (scenes): 각 씬에 대해
   - title: 씬 제목 또는 요약 (한글)
   - location: 장소/배경 (한글)
   - description: 씬 설명 (한글)
   - characters: 등장하는 제품들 이름 배열
   - backgroundPrompt: 영어 배경 프롬프트 (제품을 돋보이게 하는 배경, 조명)

응답은 반드시 다음 JSON 형식으로:
{
  "characters": [
    {"name": "스마트워치 X1", "description": "최신 건강 모니터링 기능이 탑재된 프리미엄 스마트워치", "imagePrompt": "Premium smartwatch with sleek metallic design, crystal clear OLED display, health monitoring interface visible, professional product photography, studio lighting..."},
    ...
  ],
  "scenes": [
    {"title": "제품 소개", "location": "스튜디오", "description": "스마트워치의 외관과 디자인을 소개하는 장면", "characters": ["스마트워치 X1"], "backgroundPrompt": "Clean white studio background, soft gradient lighting, professional product photography setup..."},
    ...
  ]
}

🚨 매우 중요 - 상품 이미지 프롬프트 규칙:
- **제품이 주인공**: 모든 이미지 프롬프트에서 제품이 화면의 중심
- **제품 클로즈업**: 제품의 디테일, 질감, 기능을 강조
- **사용 장면**: 제품이 실제 사용되는 모습 (사람 손/몸 일부만 노출, 얼굴 없음)
- **광고 품질**: 고급스러운 상업 사진 스타일 (studio lighting, soft shadows)
- **배경은 심플하게**: 제품을 돋보이게 하는 단순한 배경 (그라데이션, 단색, 자연 배경)
- **사람 얼굴 절대 금지**: 제품 홍보 이미지에 인물 얼굴이 나오면 안 됨
- 프롬프트 예시: "Close-up product shot of [제품명], professional commercial photography, soft studio lighting, clean background, high-end advertising quality"
- ⚠️ 절대 금지: 인물 초상화, 사람 얼굴 클로즈업, 드라마 장면"""

        elif content_type == 'education':
            # 교육/정보 콘텐츠
            system_content = """당신은 교육/정보 콘텐츠 대본을 분석하여 핵심 개념과 씬 정보를 추출하는 전문가입니다.

대본을 분석하여 다음 정보를 JSON 형식으로 추출해주세요:

1. 핵심 요소 (characters): 주요 개념/요소에 대해
   - name: 개념/요소 이름 (한글)
   - description: 설명 (한글)
   - imagePrompt: 영어 이미지 프롬프트 (개념을 시각화하는 인포그래픽/일러스트 스타일)

2. 씬 (scenes): 각 씬에 대해
   - title: 씬 제목 (한글)
   - location: 배경 컨텍스트 (한글)
   - description: 씬 설명 (한글)
   - characters: 관련 개념들 배열
   - backgroundPrompt: 영어 배경 프롬프트 (교육적 시각 자료 스타일)

응답 형식은 JSON으로:
{
  "characters": [...],
  "scenes": [...]
}

🚨 매우 중요 - 교육 콘텐츠 이미지 프롬프트 규칙:
- **인포그래픽 스타일**: 깔끔한 다이어그램, 차트, 시각화
- **개념 시각화**: 추상적 개념을 이해하기 쉽게 시각화
- **아이콘과 심볼**: 핵심 포인트를 상징하는 아이콘 사용
- **깔끔한 레이아웃**: 정보 전달에 집중하는 깔끔한 구성
- 프롬프트 예시: "Clean infographic style illustration of [개념], modern flat design, educational visual, clear icons and diagrams"
- ⚠️ 인물 사진보다는 개념 시각화에 집중"""

        else:
            # 드라마/스토리 콘텐츠 (기본값)
            system_content = """당신은 드라마 대본을 분석하여 등장인물과 씬 정보를 추출하는 전문가입니다.

대본을 분석하여 다음 정보를 JSON 형식으로 추출해주세요:

1. 등장인물 (characters): 각 인물에 대해
   - name: 인물 이름 (한글)
   - description: 인물 설명 (나이, 성격, 역할 등 - 한글)
   - imagePrompt: DALL-E용 영어 이미지 프롬프트 (외모, 의상, 분위기 묘사)

2. 씬 (scenes): 각 씬에 대해
   - title: 씬 제목 또는 요약 (한글)
   - location: 장소 (한글)
   - description: 씬 설명 (한글)
   - characters: 등장하는 인물들 이름 배열
   - backgroundPrompt: DALL-E용 영어 배경 프롬프트 (장소, 분위기, 조명 묘사)

응답은 반드시 다음 JSON 형식으로:
{
  "characters": [
    {"name": "수진", "description": "28세 여성, 밝고 활발한 성격의 카페 사장", "imagePrompt": "A Korean woman in her late 20s with East Asian features, Korean ethnicity, bright and cheerful expression, casual smart outfit..."},
    ...
  ],
  "scenes": [
    {"title": "첫 만남", "location": "카페", "description": "수진이 처음 민수를 만나는 장면", "characters": ["수진", "민수"], "backgroundPrompt": "A cozy Korean cafe interior, warm afternoon light..."},
    ...
  ]
}

중요:
- imagePrompt와 backgroundPrompt는 반드시 영어로 작성
- 프롬프트는 AI 이미지 생성에 최적화되도록 상세하게 작성

🚨 매우 중요 - 스틱맨(Stickman) 캐릭터 사용 필수:

- ⚠️⚠️⚠️ 실사 인물 절대 금지! 할아버지, 할머니, 노인, 실제 사람 얼굴 모두 사용 금지!

- ⚠️ 스틱맨 캐릭터 (모든 인물은 이걸로 표현):
  "Simple white stickman character with round head, two black dot eyes, small mouth, thin eyebrows, black outline body"

- ⚠️ 배경 스타일:
  "Detailed anime-style background, Ghibli-inspired, warm colors, slice-of-life environment"

- ⚠️ 전체 스타일:
  "Contrast collage style - simple stickman against detailed anime background"

- ⚠️ 감정 표현: 스틱맨의 간단한 표정과 포즈로 표현 (점 눈, 곡선 입)"""

        user_content = f"""다음 드라마 대본을 분석해주세요:

{script[:15000]}

⚠️ 매우 중요 - 씬 개수 제한:
- 이 영상은 {duration} 길이입니다.
- 씬은 반드시 **최대 {max_scenes}개**까지만 추출해주세요.
- 대본에 씬이 많더라도 가장 핵심적인 {max_scenes}개만 선별하세요.
- 비슷한 장면은 하나로 통합하세요.

등장인물과 씬 정보를 JSON 형식으로 추출해주세요."""

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        result = completion.choices[0].message.content.strip()

        import json as json_module
        parsed = json_module.loads(result)

        characters = parsed.get("characters", [])
        scenes = parsed.get("scenes", [])

        print(f"[DRAMA-STEP4-ANALYZE] 분석 완료 - 인물: {len(characters)}명, 씬: {len(scenes)}개")

        return jsonify({
            "ok": True,
            "characters": characters,
            "scenes": scenes
        })

    except Exception as e:
        print(f"[DRAMA-STEP4-ANALYZE][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Step4: 씬 프롬프트 생성 API =====
@app.route('/api/drama/generate-scene-prompt', methods=['POST'])
def api_generate_scene_prompt():
    """씬에 등장하는 인물들과 배경을 결합한 통합 프롬프트 생성"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        scene = data.get("scene", {})
        characters = data.get("characters", [])
        background_prompt = data.get("backgroundPrompt", "")

        print(f"[DRAMA-STEP4-SCENE] 씬 프롬프트 생성 시작")

        # 인물 프롬프트 조합
        character_descriptions = []
        for char in characters:
            if char.get("prompt"):
                character_descriptions.append(f"{char['name']}: {char['prompt']}")

        system_content = """당신은 드라마 씬을 위한 DALL-E 3 이미지 프롬프트를 작성하는 전문가입니다.

주어진 씬 정보와 등장인물 정보를 바탕으로, 인물들이 배경에 자연스럽게 어울리는 통합 장면 프롬프트를 영어로 작성해주세요.

프롬프트 작성 원칙:
1. 씬의 분위기와 감정을 반영
2. 등장인물들의 위치와 상호작용 묘사
3. 조명, 색감, 구도 등 영화적 요소 포함
4. 한국 드라마 스타일의 시각적 요소
5. DALL-E 3에 최적화된 상세하고 명확한 묘사

🚨 매우 중요 - 스틱맨(Stickman) 캐릭터만 사용:
- 실사 인물(할아버지, 할머니, 노인, 사람 얼굴) 절대 금지!
- 모든 인물은 스틱맨으로 표현
- 스틱맨: "Simple white stickman character with round head, two black dot eyes, small mouth, thin eyebrows, black outline body"
- 감정 표현: 스틱맨의 간단한 표정과 포즈로 표현

🚨 배경 스타일:
- 배경: "Detailed anime-style background, Ghibli-inspired, warm colors, slice-of-life environment"
- 전체 스타일: "Contrast collage style - simple stickman against detailed anime background"

응답 형식:
BACKGROUND_PROMPT: [배경 프롬프트 - 영어, 1970~80년대 한국 배경 스타일 포함]
COMBINED_PROMPT: [통합 장면 프롬프트 - 영어, 맨 앞에 한국인 특징 포함, 마지막에 빈티지 필름 스타일 추가, 등장인물 외모는 정확히 유지]"""

        scene_info = f"""
씬 정보:
- 제목: {scene.get('title', '')}
- 장소: {scene.get('location', '')}
- 설명: {scene.get('description', '')}
- 기존 배경 프롬프트: {background_prompt or scene.get('backgroundPrompt', '')}

등장 인물:
{chr(10).join(character_descriptions) if character_descriptions else '(인물 정보 없음)'}

위 정보를 바탕으로 통합 씬 프롬프트를 생성해주세요."""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": scene_info}
            ],
            temperature=0.7
        )

        result = completion.choices[0].message.content.strip()

        # 프롬프트 파싱
        new_background_prompt = ""
        combined_prompt = ""

        lines = result.split('\n')
        current_type = None

        for line in lines:
            line = line.strip()
            if line.startswith('BACKGROUND_PROMPT:'):
                current_type = 'background'
                new_background_prompt = line.replace('BACKGROUND_PROMPT:', '').strip()
            elif line.startswith('COMBINED_PROMPT:'):
                current_type = 'combined'
                combined_prompt = line.replace('COMBINED_PROMPT:', '').strip()
            elif current_type and line:
                if current_type == 'background':
                    new_background_prompt += ' ' + line
                elif current_type == 'combined':
                    combined_prompt += ' ' + line

        print(f"[DRAMA-STEP4-SCENE] 씬 프롬프트 생성 완료")

        return jsonify({
            "ok": True,
            "backgroundPrompt": new_background_prompt or background_prompt,
            "combinedPrompt": combined_prompt
        })

    except Exception as e:
        print(f"[DRAMA-STEP4-SCENE][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Step4: 이미지 생성 API (Gemini / FLUX.1 Pro / DALL-E 3 선택) =====
@app.route('/api/drama/generate-image', methods=['POST'])
def api_generate_image():
    """이미지 생성 - Gemini (기본, OpenRouter) / FLUX.1 Pro / DALL-E 3"""
    try:
        import requests as req

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        prompt = data.get("prompt", "")
        size = data.get("size", "1024x1024")
        image_provider = data.get("imageProvider", "gemini")  # gemini, flux, dalle

        print(f"[DRAMA-STEP4-IMAGE] 요청 수신 - Provider: {image_provider}, Size: {size}")
        print(f"[DRAMA-STEP4-IMAGE] 프롬프트 길이: {len(prompt)} 글자")

        if not prompt:
            return jsonify({"ok": False, "error": "프롬프트가 없습니다."}), 400

        # Gemini 2.5 Flash Image (OpenRouter API) - 기본값
        if image_provider == "gemini":
            openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")

            if not openrouter_api_key:
                return jsonify({"ok": False, "error": "OpenRouter API 키가 설정되지 않았습니다. 환경변수 OPENROUTER_API_KEY를 설정해주세요."}), 200

            print(f"[DRAMA-STEP4-IMAGE] Gemini 2.5 Flash Image 생성 시작 - 요청 사이즈: {size}")

            # 사이즈에 따른 비율 결정 - 매우 강력하게 명시
            if size == "1792x1024" or "16:9" in size:
                aspect_instruction = "CRITICAL: You MUST generate the image in EXACT 16:9 WIDESCREEN LANDSCAPE aspect ratio. The width MUST be 1.78 times the height. Target dimensions: 1920x1080 pixels or 1280x720 pixels. This is MANDATORY for YouTube video format. DO NOT generate square or portrait images."
                target_width, target_height = 1280, 720
            elif size == "1024x1792" or "9:16" in size:
                aspect_instruction = "CRITICAL: You MUST generate the image in EXACT 9:16 VERTICAL PORTRAIT aspect ratio. The height MUST be 1.78 times the width. Target dimensions: 1080x1920 pixels or 720x1280 pixels. This is MANDATORY for YouTube Shorts format. DO NOT generate square or landscape images."
                target_width, target_height = 720, 1280
            else:
                aspect_instruction = "CRITICAL: You MUST generate the image in EXACT 16:9 WIDESCREEN LANDSCAPE aspect ratio. Target dimensions: 1920x1080 or 1280x720 pixels. MANDATORY for YouTube."
                target_width, target_height = 1280, 720

            # 프롬프트에 16:9 비율 지시만 추가
            # 스타일은 /api/image/analyze-script에서 이미 지정됨 (스틱맨+애니배경)
            enhanced_prompt = f"{aspect_instruction}\n\n{prompt}"
            print(f"[IMAGE-GEN] 프롬프트 그대로 사용 (분석 API에서 스타일 지정됨)")

            # OpenRouter API 호출 (Chat Completions 형식)
            headers = {
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://drama-generator.app",
                "X-Title": "Drama Image Generator"
            }

            payload = {
                "model": "google/gemini-2.5-flash-image-preview",
                "modalities": ["text", "image"],
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": enhanced_prompt
                            }
                        ]
                    }
                ]
            }

            # 재시도 로직 (quota 오류 대응)
            import time
            max_retries = 3
            retry_delay = 5  # 초

            response = None
            last_error = None

            for attempt in range(max_retries):
                try:
                    response = req.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=90
                    )

                    # 성공 또는 quota 외 오류
                    if response.status_code == 200:
                        break
                    elif response.status_code in [429, 502, 503, 504] or "quota" in response.text.lower() or "rate" in response.text.lower():
                        # Rate limit / Quota / 서버 오류 (502, 503, 504) - 재시도
                        last_error = response.text
                        error_type = "서버 오류" if response.status_code in [502, 503, 504] else "quota/rate limit"
                        print(f"[DRAMA-STEP4-IMAGE][RETRY] Gemini {error_type} ({response.status_code}) (시도 {attempt + 1}/{max_retries}), {retry_delay}초 후 재시도...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 지수 백오프
                        continue
                    else:
                        # 다른 오류
                        break

                except req.exceptions.Timeout:
                    last_error = "요청 시간 초과"
                    print(f"[DRAMA-STEP4-IMAGE][RETRY] 타임아웃 (시도 {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue
                except Exception as e:
                    last_error = str(e)
                    print(f"[DRAMA-STEP4-IMAGE][RETRY] 오류: {e} (시도 {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue

            if response is None or response.status_code != 200:
                error_text = last_error or (response.text if response else "알 수 없는 오류")
                print(f"[DRAMA-STEP4-IMAGE][ERROR] OpenRouter API 최종 실패: {error_text}")
                return jsonify({"ok": False, "error": f"Gemini API 오류 (재시도 실패): {error_text[:200]}"}), 200

            result = response.json()

            # 디버그: 전체 응답 로깅
            print(f"[DRAMA-STEP4-IMAGE][DEBUG] Gemini 응답: {json.dumps(result, ensure_ascii=False)[:1000]}")

            # 응답에서 이미지 추출 (base64 data URL)
            image_url = None
            base64_image_data = None  # 파일로 저장할 base64 데이터
            try:
                choices = result.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})

                    # 1. images 배열 먼저 확인 (OpenRouter 표준 형식)
                    images = message.get("images", [])
                    if images:
                        for img in images:
                            if isinstance(img, str):
                                # base64 문자열 또는 data URL
                                if img.startswith("data:"):
                                    base64_image_data = img.split(",", 1)[1] if "," in img else img
                                else:
                                    base64_image_data = img
                                break
                            elif isinstance(img, dict):
                                if img.get("type") == "image_url":
                                    url = img.get("image_url", {}).get("url", "")
                                    if url.startswith("data:"):
                                        base64_image_data = url.split(",", 1)[1] if "," in url else url
                                    else:
                                        image_url = url
                                elif "url" in img:
                                    url = img.get("url", "")
                                    if url.startswith("data:"):
                                        base64_image_data = url.split(",", 1)[1] if "," in url else url
                                    else:
                                        image_url = url
                                elif "data" in img:
                                    base64_image_data = img.get("data")
                                elif "b64_json" in img:
                                    base64_image_data = img.get("b64_json")
                                if base64_image_data or image_url:
                                    break

                    # 2. content 배열 확인
                    if not image_url and not base64_image_data:
                        content = message.get("content", [])
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict):
                                    item_type = item.get("type", "")

                                    # image_url 타입
                                    if item_type == "image_url":
                                        url = item.get("image_url", {}).get("url", "")
                                        if url.startswith("data:"):
                                            base64_image_data = url.split(",", 1)[1] if "," in url else url
                                        else:
                                            image_url = url
                                        if base64_image_data or image_url:
                                            break

                                    # image 타입 (inline_data)
                                    elif item_type == "image":
                                        image_data = item.get("image", {})
                                        if isinstance(image_data, dict):
                                            base64_image_data = image_data.get("data") or image_data.get("base64") or image_data.get("b64_json")
                                            if base64_image_data:
                                                break
                                        elif isinstance(image_data, str):
                                            base64_image_data = image_data
                                            break

                                    # inline_data 타입 (Google 형식)
                                    elif "inline_data" in item:
                                        inline = item.get("inline_data", {})
                                        base64_image_data = inline.get("data", "")
                                        if base64_image_data:
                                            break

                                    # source 타입 (Claude API 형식)
                                    elif "source" in item:
                                        source = item.get("source", {})
                                        if source.get("type") == "base64":
                                            base64_image_data = source.get("data", "")
                                            if base64_image_data:
                                                break

                        elif isinstance(content, str):
                            print(f"[DRAMA-STEP4-IMAGE][WARN] Gemini가 텍스트만 반환: {content[:200]}")

                # base64 데이터가 있으면 파일로 저장 (+ 16:9 리사이즈 및 압축)
                if base64_image_data and not image_url:
                    import base64 as b64
                    from PIL import Image as PILImage
                    from io import BytesIO
                    try:
                        # base64 디코딩
                        image_bytes = b64.b64decode(base64_image_data)

                        # PIL로 이미지 열기
                        img = PILImage.open(BytesIO(image_bytes))
                        original_size = len(image_bytes)
                        original_dimensions = f"{img.width}x{img.height}"
                        print(f"[DRAMA-STEP4-IMAGE] 원본 이미지: {original_dimensions}, {original_size/1024:.1f}KB")

                        # 16:9 비율로 리사이즈/크롭 (target_width, target_height 사용)
                        target_ratio = target_width / target_height
                        current_ratio = img.width / img.height

                        if abs(current_ratio - target_ratio) > 0.05:  # 비율 차이가 5% 이상이면 크롭
                            if current_ratio > target_ratio:
                                # 이미지가 더 넓음 - 좌우 크롭
                                new_width = int(img.height * target_ratio)
                                left = (img.width - new_width) // 2
                                img = img.crop((left, 0, left + new_width, img.height))
                            else:
                                # 이미지가 더 높음 - 상하 크롭
                                new_height = int(img.width / target_ratio)
                                top = (img.height - new_height) // 2
                                img = img.crop((0, top, img.width, top + new_height))
                            print(f"[DRAMA-STEP4-IMAGE] 16:9 크롭 완료: {img.width}x{img.height}")

                        # 타겟 크기로 리사이즈 (YouTube HD: 1280x720)
                        if img.width > target_width or img.height > target_height:
                            img = img.resize((target_width, target_height), PILImage.Resampling.LANCZOS)
                            print(f"[DRAMA-STEP4-IMAGE] 리사이즈 완료: {target_width}x{target_height}")

                        # RGB 변환 (RGBA 이미지인 경우)
                        if img.mode == 'RGBA':
                            background = PILImage.new('RGB', img.size, (255, 255, 255))
                            background.paste(img, mask=img.split()[3])
                            img = background
                        elif img.mode != 'RGB':
                            img = img.convert('RGB')

                        # JPEG로 압축 저장 (품질 85)
                        static_dir = os.path.join(os.path.dirname(__file__), 'static', 'images')
                        os.makedirs(static_dir, exist_ok=True)

                        timestamp = dt.now().strftime("%Y%m%d_%H%M%S_%f")
                        filename = f"gemini_{timestamp}.jpg"
                        filepath = os.path.join(static_dir, filename)

                        img.save(filepath, 'JPEG', quality=85, optimize=True)

                        final_size = os.path.getsize(filepath)
                        compression_ratio = (1 - final_size / original_size) * 100
                        print(f"[DRAMA-STEP4-IMAGE] 최종 이미지: {target_width}x{target_height}, {final_size/1024:.1f}KB (압축률: {compression_ratio:.1f}%)")

                        image_url = f"/static/images/{filename}"
                        print(f"[DRAMA-STEP4-IMAGE] 이미지 저장 완료: {image_url}")
                    except Exception as save_err:
                        print(f"[DRAMA-STEP4-IMAGE][ERROR] 이미지 저장 실패: {save_err}")
                        # 저장 실패 시 base64 URL로 반환
                        image_url = f"data:image/png;base64,{base64_image_data}"

            except Exception as parse_error:
                print(f"[DRAMA-STEP4-IMAGE][ERROR] 응답 파싱 오류: {parse_error}")
                import traceback
                traceback.print_exc()

            if not image_url:
                # 에러 메시지에 더 많은 정보 포함
                error_detail = ""
                if choices:
                    msg = choices[0].get("message", {})
                    if msg.get("content"):
                        content = msg.get("content")
                        if isinstance(content, str):
                            error_detail = f" 응답: {content[:100]}"
                return jsonify({"ok": False, "error": f"Gemini에서 이미지를 생성하지 못했습니다.{error_detail} 프롬프트를 수정해주세요."}), 200

            # Gemini 비용: ~$0.039/장 (1290 output tokens * $30/1M)
            cost_usd = 0.039
            cost_krw = int(cost_usd * 1350)

            print(f"[DRAMA-STEP4-IMAGE] Gemini 완료 - 비용: ${cost_usd}")

            return jsonify({
                "ok": True,
                "imageUrl": image_url,
                "cost": cost_krw,
                "costUsd": cost_usd,
                "provider": "gemini"
            })

        # FLUX.1 Pro (Replicate API)
        elif image_provider == "flux":
            replicate_api_key = os.getenv("REPLICATE_API_TOKEN", "")

            if not replicate_api_key:
                return jsonify({"ok": False, "error": "Replicate API 키가 설정되지 않았습니다. 환경변수 REPLICATE_API_TOKEN을 설정해주세요."}), 200

            # 사이즈 변환 (FLUX는 aspect_ratio 사용)
            if size == "1792x1024":
                aspect_ratio = "16:9"
                width, height = 1344, 768
            elif size == "1024x1792":
                aspect_ratio = "9:16"
                width, height = 768, 1344
            else:
                aspect_ratio = "1:1"
                width, height = 1024, 1024

            print(f"[DRAMA-STEP4-IMAGE] FLUX.1 Pro 이미지 생성 시작 - 사이즈: {aspect_ratio}")

            # 프롬프트에 스타일 가이드 추가 및 한국 인종 강조
            if "Korean" in prompt or "korean" in prompt:
                # 한국인 외모 특징을 프롬프트 시작 부분에 최우선 배치
                korean_features = "CRITICAL: authentic Korean person from South Korea with Korean/East Asian ethnicity, Korean facial bone structure, Korean skin tone."
                enhanced_prompt = f"{korean_features} {prompt}, cinematic Korean drama style, professional photography, 8k resolution, detailed"
            else:
                enhanced_prompt = f"{prompt}, high quality, photorealistic, cinematic lighting, professional photography, 8k resolution, detailed"

            # Replicate API 호출 (FLUX.1 Pro)
            headers = {
                "Authorization": f"Token {replicate_api_key}",
                "Content-Type": "application/json"
            }

            # FLUX.1 Pro 모델
            payload = {
                "version": "black-forest-labs/flux-pro",
                "input": {
                    "prompt": enhanced_prompt,
                    "aspect_ratio": aspect_ratio,
                    "output_format": "png",
                    "output_quality": 90,
                    "safety_tolerance": 2
                }
            }

            # 예측 생성
            response = req.post(
                "https://api.replicate.com/v1/models/black-forest-labs/flux-pro/predictions",
                headers=headers,
                json={"input": payload["input"]}
            )

            if response.status_code != 201:
                error_text = response.text
                print(f"[DRAMA-STEP4-IMAGE][ERROR] Replicate API 응답: {response.status_code} - {error_text}")
                return jsonify({"ok": False, "error": f"FLUX API 오류: {error_text}"}), 200

            prediction = response.json()
            prediction_id = prediction.get("id")

            # 결과 폴링 (최대 60초)
            import time
            max_wait = 60
            waited = 0
            image_url = None

            while waited < max_wait:
                status_response = req.get(
                    f"https://api.replicate.com/v1/predictions/{prediction_id}",
                    headers=headers
                )
                status_data = status_response.json()
                status = status_data.get("status")

                if status == "succeeded":
                    output = status_data.get("output")
                    if isinstance(output, list) and len(output) > 0:
                        image_url = output[0]
                    elif isinstance(output, str):
                        image_url = output
                    break
                elif status == "failed":
                    error = status_data.get("error", "알 수 없는 오류")
                    return jsonify({"ok": False, "error": f"FLUX 생성 실패: {error}"}), 200

                time.sleep(2)
                waited += 2

            if not image_url:
                return jsonify({"ok": False, "error": "이미지 생성 시간 초과"}), 200

            # FLUX.1 Pro 비용: $0.055/장
            cost_usd = 0.055
            cost_krw = int(cost_usd * 1350)

            print(f"[DRAMA-STEP4-IMAGE] FLUX.1 Pro 완료 - 비용: ${cost_usd}")

            return jsonify({
                "ok": True,
                "imageUrl": image_url,
                "cost": cost_krw,
                "costUsd": cost_usd,
                "provider": "flux"
            })

        # DALL-E 3 (기존 코드)
        else:
            print(f"[DRAMA-STEP4-IMAGE] DALL-E 3 분기 진입 (provider: {image_provider})")

            # 허용된 사이즈 검증
            allowed_sizes = ["1024x1024", "1792x1024", "1024x1792"]
            if size not in allowed_sizes:
                size = "1024x1024"

            print(f"[DRAMA-STEP4-IMAGE] DALL-E 3 이미지 생성 시작 - 사이즈: {size}")

            # 프롬프트에 스타일 가이드 추가 및 한국 인종 강조
            if "Korean" in prompt or "korean" in prompt:
                # 한국인 외모 특징을 프롬프트 시작 부분에 최우선 배치
                korean_features = "CRITICAL: authentic Korean person from South Korea with Korean/East Asian ethnicity, Korean facial bone structure, Korean skin tone."
                enhanced_prompt = f"{korean_features} {prompt}, cinematic Korean drama style, professional photography, 8k resolution"
            else:
                enhanced_prompt = f"{prompt}, high quality, photorealistic, cinematic lighting, professional photography, 8k resolution"

            # DALL-E 3 API 호출
            response = client.images.generate(
                model="dall-e-3",
                prompt=enhanced_prompt,
                size=size,
                quality="standard",
                n=1
            )

            image_url = response.data[0].url

            # DALL-E 3 비용 계산
            cost_usd = 0.04 if size == "1024x1024" else 0.08
            cost_krw = int(cost_usd * 1350)

            print(f"[DRAMA-STEP4-IMAGE] DALL-E 3 완료 - 비용: ${cost_usd}")

            return jsonify({
                "ok": True,
                "imageUrl": image_url,
                "cost": cost_krw,
                "costUsd": cost_usd,
                "provider": "dalle"
            })

    except Exception as e:
        error_msg = str(e)
        print(f"[DRAMA-STEP4-IMAGE][ERROR] {error_msg}")

        if "content_policy" in error_msg.lower():
            return jsonify({"ok": False, "error": "이미지 생성이 콘텐츠 정책에 위배됩니다. 프롬프트를 수정해주세요."}), 200
        elif "rate_limit" in error_msg.lower():
            return jsonify({"ok": False, "error": "API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."}), 200

        return jsonify({"ok": False, "error": error_msg}), 200


# ===== MP3 청크 병합 (FFmpeg 기반) =====
def merge_audio_chunks_ffmpeg(audio_data_list):
    """여러 MP3 바이트 데이터를 FFmpeg로 병합"""
    import tempfile
    import subprocess
    import shutil
    import gc  # 메모리 정리용

    if not audio_data_list:
        return b''

    if len(audio_data_list) == 1:
        return audio_data_list[0]

    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        # FFmpeg 없으면 단순 결합 (폴백)
        print("[TTS-MERGE][WARN] FFmpeg 없음, 단순 바이트 결합 사용")
        return b''.join(audio_data_list)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # 각 청크를 임시 파일로 저장
            chunk_files = []
            for i, chunk_data in enumerate(audio_data_list):
                chunk_path = os.path.join(tmpdir, f"chunk_{i:03d}.mp3")
                with open(chunk_path, 'wb') as f:
                    f.write(chunk_data)
                chunk_files.append(chunk_path)

            # FFmpeg concat 리스트 파일 생성
            list_path = os.path.join(tmpdir, "concat_list.txt")
            with open(list_path, 'w') as f:
                for chunk_path in chunk_files:
                    f.write(f"file '{chunk_path}'\n")

            # 출력 파일
            output_path = os.path.join(tmpdir, "merged.mp3")

            # FFmpeg concat 실행
            cmd = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_path,
                '-c', 'copy',  # 재인코딩 없이 병합
                output_path
            ]

            # 메모리 최적화: stdout DEVNULL, stderr만 PIPE (OOM 방지)
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=60
            )

            if result.returncode != 0:
                stderr_msg = result.stderr[:200].decode('utf-8', errors='ignore') if result.stderr else '(stderr 없음)'
                print(f"[TTS-MERGE][ERROR] FFmpeg 실패: {stderr_msg}")
                del result
                gc.collect()
                # 폴백: 단순 바이트 결합
                return b''.join(audio_data_list)
            del result
            gc.collect()

            # 병합된 파일 읽기
            with open(output_path, 'rb') as f:
                merged_audio = f.read()

            print(f"[TTS-MERGE] FFmpeg 병합 완료: {len(audio_data_list)}개 청크 → {len(merged_audio)} bytes")
            return merged_audio

    except Exception as e:
        print(f"[TTS-MERGE][ERROR] 병합 실패: {e}")
        # 폴백: 단순 바이트 결합
        return b''.join(audio_data_list)


# ===== Step5: TTS API (Google Cloud / 네이버 클로바 선택) =====
@app.route('/api/drama/generate-tts', methods=['POST'])
def api_generate_tts():
    """TTS 음성 생성 - Google Cloud TTS (기본) 또는 네이버 클로바"""
    try:
        import requests
        import base64

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        text = data.get("text", "")
        speaker = data.get("speaker", "ko-KR-Wavenet-A")
        speed = data.get("speed", 1.0)
        pitch = data.get("pitch", 0)
        volume = data.get("volume", 0)
        tts_provider = data.get("ttsProvider", "google")  # google 또는 naver

        if not text:
            return jsonify({"ok": False, "error": "텍스트가 없습니다."}), 400

        char_count = len(text)

        # Google Cloud TTS
        if tts_provider == "google":
            google_api_key = os.getenv("GOOGLE_CLOUD_API_KEY", "")

            if not google_api_key:
                return jsonify({"ok": False, "error": "Google Cloud API 키가 설정되지 않았습니다. 환경변수 GOOGLE_CLOUD_API_KEY를 설정해주세요."}), 200

            print(f"[DRAMA-STEP5-TTS] Google TTS 생성 시작 - 음성: {speaker}, 텍스트 길이: {char_count}자")

            # 감정 표현 키워드 (이 표현이 포함된 문장은 더 천천히 읽음)
            emotional_keywords = [
                # 신체 반응
                "눈물이", "눈시울", "손이 떨", "목이 메", "가슴이 먹먹",
                "잠이 오지", "밥이 넘어가지", "숨이 막", "몸이 굳",
                # 감정 상태
                "마음이 무거", "희망이", "미안", "허무", "믿기지 않",
                "슬", "아프", "고통", "절망", "두려", "무서",
                "감사", "감격", "벅차", "뭉클", "찡",
                # 강조 표현
                "정말", "진심으로", "간절히", "애타게", "처절하게",
                # 특수 상황
                "마지막", "이별", "죽음", "떠나", "영원히"
            ]

            def apply_emotion_ssml(text_chunk, base_rate):
                """감정 표현이 있는 문장에 SSML 속도 조절 적용"""
                import re
                import html

                def escape_for_ssml(text):
                    """SSML에서 사용할 수 있도록 XML 특수 문자 이스케이프"""
                    return html.escape(text, quote=False)

                # 문장 단위로 분할
                sentences = re.split(r'([.!?。！？])', text_chunk)
                merged = []
                i = 0
                while i < len(sentences):
                    if i + 1 < len(sentences) and sentences[i+1] in '.!?。！？':
                        merged.append(sentences[i] + sentences[i+1])
                        i += 2
                    else:
                        if sentences[i].strip():
                            merged.append(sentences[i])
                        i += 1

                result_parts = []
                has_emotion = False

                for sentence in merged:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    # 감정 키워드 체크
                    is_emotional = any(kw in sentence for kw in emotional_keywords)

                    if is_emotional:
                        has_emotion = True
                        # 감정 문장: 기본 속도의 90% (더 천천히)
                        emotion_rate = max(0.25, base_rate * 0.9)
                        # 감정 문장 전에 짧은 휴지, 더 느린 속도로 읽기
                        escaped_sentence = escape_for_ssml(sentence)
                        result_parts.append(f'<break time="300ms"/><prosody rate="{emotion_rate:.2f}">{escaped_sentence}</prosody><break time="200ms"/>')
                    else:
                        result_parts.append(escape_for_ssml(sentence))

                if has_emotion:
                    ssml_text = f'<speak>{" ".join(result_parts)}</speak>'
                    return ssml_text, True
                else:
                    return text_chunk, False

            # Google Cloud TTS는 최대 5000바이트 제한
            # SSML 태그 오버헤드를 고려하여 보수적으로 설정:
            # - SSML 기본 태그: <speak></speak> = 15바이트
            # - 감정 문장당 SSML 태그: <break time="300ms"/><prosody rate="0.90">...</prosody><break time="200ms"/> = 약 75바이트
            # - 최대 10개 감정 문장 가정 시 약 750바이트 추가
            # 안전 마진을 위해 2500바이트로 설정 (최악의 경우에도 5000 미만 보장)
            GOOGLE_TTS_MAX_BYTES = 5000
            max_bytes_for_plain_text = 2500  # SSML 오버헤드 고려하여 보수적 설정
            text_chunks = []

            def get_byte_length(s):
                return len(s.encode('utf-8'))

            def split_text_by_bytes(text, max_bytes):
                """텍스트를 바이트 제한에 맞게 분할"""
                chunks = []
                # 문장 단위로 먼저 분할 (마침표, 느낌표, 물음표 기준)
                import re
                sentences = re.split(r'([.!?。！？])', text)
                # 구분자를 문장에 다시 붙이기
                merged_sentences = []
                i = 0
                while i < len(sentences):
                    if i + 1 < len(sentences) and sentences[i+1] in '.!?。！？':
                        merged_sentences.append(sentences[i] + sentences[i+1])
                        i += 2
                    else:
                        if sentences[i].strip():
                            merged_sentences.append(sentences[i])
                        i += 1

                current_chunk = ""
                for sentence in merged_sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    # 문장 자체가 너무 길면 더 작게 분할
                    if get_byte_length(sentence) > max_bytes:
                        # 현재 청크 저장
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = ""
                        # 긴 문장을 쉼표나 공백으로 분할
                        sub_parts = re.split(r'([,，、\s])', sentence)
                        sub_chunk = ""
                        for part in sub_parts:
                            if get_byte_length(sub_chunk + part) < max_bytes:
                                sub_chunk += part
                            else:
                                if sub_chunk:
                                    chunks.append(sub_chunk.strip())
                                sub_chunk = part
                        if sub_chunk:
                            current_chunk = sub_chunk
                    elif get_byte_length(current_chunk + " " + sentence) < max_bytes:
                        current_chunk = (current_chunk + " " + sentence).strip()
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence

                if current_chunk:
                    chunks.append(current_chunk.strip())

                return chunks if chunks else [text[:1000]]  # 최소 하나의 청크 보장 (더 보수적)

            text_chunks = split_text_by_bytes(text, max_bytes_for_plain_text)
            print(f"[DRAMA-STEP5-TTS] 텍스트를 {len(text_chunks)}개 청크로 분할 (바이트 제한: {max_bytes_for_plain_text})")

            audio_data_list = []
            url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={google_api_key}"

            # 속도 변환: 배율(0.85~1.1) 또는 네이버(-5~5) -> Google(0.25~4.0)
            if isinstance(speed, (int, float)):
                if 0.1 <= speed <= 2.0:
                    # 배율 형식 (0.85x, 0.95x, 1.0x, 1.1x 등) - 그대로 사용
                    google_speed = speed
                elif speed == 0:
                    google_speed = 1.0
                else:
                    # 네이버 형식 (-5~5)
                    google_speed = 1.0 + (speed * 0.1)  # -5->0.5, 0->1.0, 5->1.5
                google_speed = max(0.25, min(4.0, google_speed))
            else:
                google_speed = 1.0

            print(f"[DRAMA-STEP5-TTS] 속도 설정: 입력={speed}, Google TTS={google_speed}")

            # 피치 변환: 네이버(-5~5) -> Google(-20~20)
            google_pitch = pitch * 4 if isinstance(pitch, (int, float)) else 0

            emotion_chunk_count = 0
            ssml_fallback_count = 0  # SSML이 너무 커서 plain text로 폴백한 횟수

            for chunk in text_chunks:
                # 감정 표현 SSML 적용
                processed_chunk, is_ssml = apply_emotion_ssml(chunk, google_speed)

                # SSML 적용 후 바이트 체크 - 5000바이트 초과시 plain text로 폴백
                if is_ssml:
                    ssml_byte_length = get_byte_length(processed_chunk)
                    if ssml_byte_length >= GOOGLE_TTS_MAX_BYTES:
                        # SSML이 너무 큼 - plain text로 폴백
                        print(f"[DRAMA-STEP5-TTS][WARN] SSML 바이트 초과 ({ssml_byte_length}), plain text로 폴백")
                        is_ssml = False
                        ssml_fallback_count += 1
                    else:
                        emotion_chunk_count += 1

                if is_ssml:
                    payload = {
                        "input": {"ssml": processed_chunk},
                        "voice": {
                            "languageCode": "ko-KR",
                            "name": speaker
                        },
                        "audioConfig": {
                            "audioEncoding": "MP3",
                            "speakingRate": google_speed,
                            "pitch": google_pitch
                        }
                    }
                else:
                    # plain text도 5000바이트 제한 체크
                    chunk_byte_length = get_byte_length(chunk)
                    if chunk_byte_length >= GOOGLE_TTS_MAX_BYTES:
                        # 청크 자체가 너무 큼 - 강제 분할 (이 경우는 거의 없어야 함)
                        print(f"[DRAMA-STEP5-TTS][WARN] 청크가 너무 큼 ({chunk_byte_length}), 강제 절단")
                        chunk = chunk[:1500]  # 약 4500바이트 (한글 3바이트)

                    payload = {
                        "input": {"text": chunk},
                        "voice": {
                            "languageCode": "ko-KR",
                            "name": speaker
                        },
                        "audioConfig": {
                            "audioEncoding": "MP3",
                            "speakingRate": google_speed,
                            "pitch": google_pitch
                        }
                    }

                response = requests.post(url, json=payload, timeout=90)

                if response.status_code == 200:
                    result = response.json()
                    audio_content = base64.b64decode(result.get("audioContent", ""))
                    audio_data_list.append(audio_content)
                else:
                    error_text = response.text
                    print(f"[DRAMA-STEP5-TTS][ERROR] Google API 응답: {response.status_code} - {error_text}")

                    # 403 에러에 대한 특별한 안내
                    if response.status_code == 403:
                        error_msg = "Google TTS API 접근 권한이 없습니다. Google Cloud Console에서 'Cloud Text-to-Speech API'가 활성화되어 있는지 확인하고, API 키에 해당 API 접근 권한이 있는지 확인해주세요."
                        print(f"[DRAMA-STEP5-TTS][ERROR] 403 Forbidden - API 활성화 필요 또는 API 키 권한 부족")
                        return jsonify({"ok": False, "error": error_msg, "statusCode": 403}), 200

                    return jsonify({"ok": False, "error": f"Google TTS API 오류 ({response.status_code}): {error_text}"}), 200

            # FFmpeg로 MP3 청크 병합 (단순 바이트 결합 대신 - 헤더 중복 방지)
            if len(audio_data_list) == 1:
                # 청크가 하나면 그대로 사용
                combined_audio = audio_data_list[0]
            else:
                # 여러 청크면 FFmpeg로 병합
                combined_audio = merge_audio_chunks_ffmpeg(audio_data_list)

            audio_base64 = base64.b64encode(combined_audio).decode('utf-8')
            audio_url = f"data:audio/mp3;base64,{audio_base64}"

            # Google Cloud TTS 비용: $4/100만 글자 (Wavenet), $16/100만 글자 (Neural2)
            # 약 0.0054원/글자 (Wavenet 기준, 환율 1350원)
            cost_per_char = 0.0054 if "Wavenet" in speaker else 0.0216
            cost_krw = int(char_count * cost_per_char)

            print(f"[DRAMA-STEP5-TTS] Google TTS 완료 - 글자 수: {char_count}, 비용: ₩{cost_krw}, 감정 SSML 적용: {emotion_chunk_count}/{len(text_chunks)}청크, 폴백: {ssml_fallback_count}회")

            return jsonify({
                "ok": True,
                "audioUrl": audio_url,
                "charCount": char_count,
                "cost": cost_krw,
                "provider": "google",
                "emotionChunks": emotion_chunk_count,
                "totalChunks": len(text_chunks)
            })

        # 네이버 클로바 TTS (기존 코드)
        else:
            ncp_client_id = os.getenv("NCP_CLIENT_ID", "")
            ncp_client_secret = os.getenv("NCP_CLIENT_SECRET", "")

            if not ncp_client_id or not ncp_client_secret:
                return jsonify({"ok": False, "error": "네이버 클라우드 API 키가 설정되지 않았습니다. 환경변수 NCP_CLIENT_ID, NCP_CLIENT_SECRET을 설정해주세요."}), 200

            print(f"[DRAMA-STEP5-TTS] 네이버 TTS 생성 시작 - 음성: {speaker}, 텍스트 길이: {char_count}자")

            max_chars = 1000
            text_chunks = []

            if len(text) > max_chars:
                sentences = text.replace('\n', ' ').split('. ')
                current_chunk = ""
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 2 < max_chars:
                        current_chunk += sentence + ". "
                    else:
                        if current_chunk:
                            text_chunks.append(current_chunk.strip())
                        current_chunk = sentence + ". "
                if current_chunk:
                    text_chunks.append(current_chunk.strip())
            else:
                text_chunks = [text]

            audio_data_list = []

            for chunk in text_chunks:
                url = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"
                headers = {
                    "X-NCP-APIGW-API-KEY-ID": ncp_client_id,
                    "X-NCP-APIGW-API-KEY": ncp_client_secret,
                    "Content-Type": "application/x-www-form-urlencoded"
                }

                payload = {
                    "speaker": speaker,
                    "volume": str(volume),
                    "speed": str(speed),
                    "pitch": str(pitch),
                    "format": "mp3",
                    "text": chunk
                }

                response = requests.post(url, headers=headers, data=payload)

                if response.status_code == 200:
                    audio_data_list.append(response.content)
                else:
                    error_text = response.text
                    print(f"[DRAMA-STEP5-TTS][ERROR] 네이버 API 응답: {response.status_code} - {error_text}")

                    # 403 에러에 대한 특별한 안내
                    if response.status_code == 403:
                        error_msg = "네이버 TTS API 접근 권한이 없습니다. 네이버 클라우드 플랫폼에서 CLOVA Voice API가 활성화되어 있는지, API 키가 유효한지 확인해주세요."
                        print(f"[DRAMA-STEP5-TTS][ERROR] 403 Forbidden - 네이버 API 키 또는 권한 문제")
                        return jsonify({"ok": False, "error": error_msg, "statusCode": 403}), 200

                    return jsonify({"ok": False, "error": f"네이버 TTS API 오류 ({response.status_code}): {error_text}"}), 200

            # FFmpeg로 MP3 청크 병합 (네이버 TTS)
            if len(audio_data_list) == 1:
                combined_audio = audio_data_list[0]
            else:
                combined_audio = merge_audio_chunks_ffmpeg(audio_data_list)

            audio_base64 = base64.b64encode(combined_audio).decode('utf-8')
            audio_url = f"data:audio/mp3;base64,{audio_base64}"

            cost_krw = int(char_count * 4)

            print(f"[DRAMA-STEP5-TTS] 네이버 TTS 완료 - 글자 수: {char_count}, 비용: ₩{cost_krw}")

            return jsonify({
                "ok": True,
                "audioUrl": audio_url,
                "charCount": char_count,
                "cost": cost_krw,
                "provider": "naver"
            })

    except Exception as e:
        print(f"[DRAMA-STEP5-TTS][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Step3 TTS 새 파이프라인 (5000바이트 제한 해결 + SRT 자막) =====
@app.route('/api/drama/step3/tts', methods=['POST'])
def api_step3_tts_pipeline():
    """
    새로운 Step3 TTS 파이프라인
    - 5000바이트 제한 자동 해결 (청킹)
    - FFmpeg로 오디오 병합
    - SRT 자막 자동 생성

    Input:
    {
        "episode_id": "xxx",
        "language": "ko-KR",
        "voice": { "gender": "MALE", "name": "ko-KR-Neural2-B", "speaking_rate": 0.9 },
        "scenes": [{ "id": "scene1", "narration": "..." }, ...]
    }

    Output:
    {
        "ok": true,
        "episode_id": "xxx",
        "audio_file": "outputs/audio/xxx_full.mp3",
        "audio_url": "/outputs/audio/xxx_full.mp3",
        "srt_file": "outputs/subtitles/xxx.srt",
        "timeline": [...],
        "stats": {...}
    }
    """
    try:
        from step3_tts_and_subtitles import run_tts_pipeline

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        scenes = data.get("scenes", [])
        if not scenes:
            return jsonify({"ok": False, "error": "씬 데이터가 없습니다."}), 400

        print(f"[STEP3-TTS] 새 파이프라인 시작: {len(scenes)}개 씬")

        result = run_tts_pipeline(data)

        # 파일 경로를 URL로 변환
        if result.get("ok") and result.get("audio_file"):
            audio_file = result["audio_file"]
            result["audio_url"] = "/" + audio_file

        if result.get("ok") and result.get("srt_file"):
            srt_file = result["srt_file"]
            result["srt_url"] = "/" + srt_file

        return jsonify(result)

    except Exception as e:
        print(f"[STEP3-TTS][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Step5: 자막 생성 API =====
@app.route('/api/drama/generate-subtitle', methods=['POST'])
def api_generate_subtitle():
    """텍스트를 SRT/VTT 자막 형식으로 변환"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        text = data.get("text", "")
        speed = data.get("speed", 0)  # TTS 속도 (-5 ~ 5)
        audio_duration = data.get("audioDuration", 0)  # 실제 TTS 오디오 길이 (초)

        if not text:
            return jsonify({"ok": False, "error": "텍스트가 없습니다."}), 400

        print(f"[DRAMA-STEP5-SUBTITLE] 자막 생성 시작 - 텍스트 길이: {len(text)}자, 오디오 길이: {audio_duration}초")

        # 글자당 시간 계산
        # 1. 실제 오디오 길이가 있으면 그에 맞게 계산
        # 2. 없으면 속도 기반으로 추정
        if audio_duration and audio_duration > 0:
            # 실제 오디오 길이 기반 계산 (여유 시간 고려)
            char_duration = audio_duration / max(len(text), 1)
            print(f"[DRAMA-STEP5-SUBTITLE] 오디오 기반 글자당 시간: {char_duration:.4f}초")
        else:
            # 속도에 따른 글자당 시간 계산 (기본: 글자당 약 0.15초)
            # 속도가 빠르면 시간 감소, 느리면 시간 증가
            base_char_duration = 0.15
            speed_factor = 1 - (speed * 0.1)  # speed가 5면 0.5배, -5면 1.5배
            char_duration = base_char_duration * speed_factor
            print(f"[DRAMA-STEP5-SUBTITLE] 속도 기반 글자당 시간: {char_duration:.4f}초")

        # 문장 단위로 분할 (개선된 로직)
        import re

        # 1단계: 줄바꿈으로 먼저 분할
        lines = text.split('\n')
        raw_sentences = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 2단계: 문장 종결 부호로 분할 (.!?。)
            # 한국어 문장 종료 어미도 고려 (~요, ~다, ~죠, ~네요 등)
            parts = re.split(r'([.!?。])', line)

            current = ""
            for i, part in enumerate(parts):
                if part in '.!?。':
                    current += part
                    if current.strip():
                        raw_sentences.append(current.strip())
                    current = ""
                else:
                    current += part

            # 마지막 남은 부분 추가
            if current.strip():
                raw_sentences.append(current.strip())

        # 3단계: 긴 문장은 쉼표나 적절한 위치에서 분할
        MAX_CHARS = 35  # 자막 한 줄 최대 글자 수
        sentences = []

        for sentence in raw_sentences:
            if len(sentence) <= MAX_CHARS:
                sentences.append(sentence)
            else:
                # 쉼표, 조사 위치에서 분할 시도
                # 한국어 분할 포인트: 쉼표, ~고, ~며, ~면, ~서, ~니, ~는데
                split_pattern = r'(,\s*|(?<=[가-힣])고\s+|(?<=[가-힣])며\s+|(?<=[가-힣])면\s+|(?<=[가-힣])서\s+|(?<=[가-힣])는데\s+)'
                sub_parts = re.split(split_pattern, sentence)

                current_part = ""
                for sub in sub_parts:
                    if not sub:
                        continue
                    # 분할 패턴인 경우 현재 부분에 붙임
                    if re.match(split_pattern, sub):
                        current_part += sub
                    elif len(current_part) + len(sub) <= MAX_CHARS:
                        current_part += sub
                    else:
                        if current_part.strip():
                            sentences.append(current_part.strip())
                        current_part = sub

                if current_part.strip():
                    sentences.append(current_part.strip())

        # 4단계: 여전히 긴 문장은 강제 분할
        final_sentences = []
        for sentence in sentences:
            if len(sentence) <= MAX_CHARS:
                final_sentences.append(sentence)
            else:
                # 공백 기준 분할
                words = sentence.split()
                current = ""
                for word in words:
                    if len(current) + len(word) + 1 <= MAX_CHARS:
                        current = current + " " + word if current else word
                    else:
                        if current:
                            final_sentences.append(current)
                        current = word
                if current:
                    final_sentences.append(current)

        sentences = [s for s in final_sentences if s.strip()]

        # 문장이 없으면 전체 텍스트를 하나의 문장으로
        if not sentences and text.strip():
            sentences = [text.strip()[:MAX_CHARS]]

        # SRT 형식 생성
        srt_lines = []
        vtt_lines = ["WEBVTT", ""]

        current_time = 0.0

        for idx, sentence in enumerate(sentences, 1):
            # 문장 길이에 따른 표시 시간 계산
            sentence_duration = len(sentence) * char_duration
            # 최소 1초, 최대 10초
            sentence_duration = max(1.0, min(10.0, sentence_duration))

            start_time = current_time
            end_time = current_time + sentence_duration

            # 시간 포맷팅 함수
            def format_time_srt(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                millis = int((seconds % 1) * 1000)
                return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

            def format_time_vtt(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                millis = int((seconds % 1) * 1000)
                return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

            # 자막용 텍스트: 한글 숫자 → 아라비아 숫자 변환
            subtitle_text = korean_number_to_arabic(sentence)

            # SRT 형식
            srt_lines.append(str(idx))
            srt_lines.append(f"{format_time_srt(start_time)} --> {format_time_srt(end_time)}")
            srt_lines.append(subtitle_text)
            srt_lines.append("")

            # VTT 형식
            vtt_lines.append(f"{format_time_vtt(start_time)} --> {format_time_vtt(end_time)}")
            vtt_lines.append(subtitle_text)
            vtt_lines.append("")

            current_time = end_time + 0.2  # 문장 사이 간격

        srt_content = "\n".join(srt_lines)
        vtt_content = "\n".join(vtt_lines)

        print(f"[DRAMA-STEP5-SUBTITLE] 자막 생성 완료 - {len(sentences)}개 문장")

        return jsonify({
            "ok": True,
            "srt": srt_content,
            "vtt": vtt_content,
            "sentenceCount": len(sentences),
            "totalDuration": current_time
        })

    except Exception as e:
        print(f"[DRAMA-STEP5-SUBTITLE][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== BGM 파일 업로드 API =====
@app.route('/api/bgm/upload', methods=['POST'])
def api_upload_bgm():
    """BGM 파일 업로드 (MP3)"""
    try:
        if 'file' not in request.files:
            return jsonify({"ok": False, "error": "파일이 없습니다"}), 400

        file = request.files['file']
        mood = request.form.get('mood', '')

        if not file.filename:
            return jsonify({"ok": False, "error": "파일명이 없습니다"}), 400

        if not mood:
            return jsonify({"ok": False, "error": "분위기(mood)를 선택하세요"}), 400

        # BGM 디렉토리 확인/생성 (스크립트 위치 기준 절대 경로)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        bgm_dir = os.path.join(script_dir, "static", "audio", "bgm")
        os.makedirs(bgm_dir, exist_ok=True)
        print(f"[BGM-UPLOAD] 디렉토리: {bgm_dir}")

        # 기존 파일 확인하여 번호 부여
        import glob
        existing = glob.glob(os.path.join(bgm_dir, f"{mood}*.mp3"))
        num = len(existing) + 1
        filename = f"{mood}_{num:02d}.mp3"
        filepath = os.path.join(bgm_dir, filename)

        file.save(filepath)
        print(f"[BGM-UPLOAD] 저장됨: {filepath}")

        # Git에 자동 커밋 (배포 후에도 파일 유지)
        try:
            import subprocess
            subprocess.run(["git", "add", filepath], cwd=script_dir, timeout=30)
            subprocess.run(["git", "commit", "-m", f"Add BGM: {filename}"], cwd=script_dir, timeout=30)
            subprocess.run(["git", "push"], cwd=script_dir, timeout=60)
            print(f"[BGM-UPLOAD] Git 커밋 완료: {filename}")
        except Exception as git_err:
            print(f"[BGM-UPLOAD] Git 커밋 실패 (파일은 저장됨): {git_err}")

        return jsonify({
            "ok": True,
            "filename": filename,
            "path": filepath,
            "mood": mood,
            "count": num
        })

    except Exception as e:
        print(f"[BGM-UPLOAD] 오류: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/bgm/list', methods=['GET'])
def api_list_bgm():
    """업로드된 BGM 파일 목록"""
    try:
        import glob
        script_dir = os.path.dirname(os.path.abspath(__file__))
        bgm_dir = os.path.join(script_dir, "static", "audio", "bgm")
        os.makedirs(bgm_dir, exist_ok=True)

        files = glob.glob(os.path.join(bgm_dir, "*.mp3"))
        print(f"[BGM-LIST] 디렉토리: {bgm_dir}, 파일 수: {len(files)}")
        moods = {}

        for f in files:
            filename = os.path.basename(f)
            # mood 추출: hopeful_01.mp3 -> hopeful
            mood = filename.split('_')[0].split('.')[0].split(' ')[0]
            if mood not in moods:
                moods[mood] = []
            moods[mood].append(filename)

        return jsonify({"ok": True, "moods": moods, "total": len(files)})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/bgm-upload')
def bgm_upload_page():
    """BGM 업로드 페이지"""
    return '''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BGM 업로드</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; background: #1a1a2e; color: #eee; }
h1 { color: #00d4ff; }
.upload-box { border: 2px dashed #444; padding: 40px; text-align: center; margin: 20px 0; border-radius: 10px; }
.upload-box.dragover { border-color: #00d4ff; background: rgba(0,212,255,0.1); }
select, button { padding: 12px 24px; font-size: 16px; margin: 10px 5px; border-radius: 5px; border: none; cursor: pointer; }
select { background: #333; color: #fff; }
button { background: #00d4ff; color: #000; font-weight: bold; }
button:hover { background: #00b8e6; }
.file-list { background: #2a2a4e; padding: 15px; border-radius: 10px; margin-top: 20px; }
.file-item { padding: 8px; border-bottom: 1px solid #444; }
.mood-tag { display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; margin-right: 10px; }
.hopeful { background: #4CAF50; } .sad { background: #2196F3; } .tense { background: #f44336; }
.dramatic { background: #9C27B0; } .calm { background: #00BCD4; } .inspiring { background: #FF9800; }
.mysterious { background: #607D8B; } .nostalgic { background: #795548; }
#status { margin-top: 15px; padding: 10px; border-radius: 5px; }
.success { background: #1b5e20; } .error { background: #b71c1c; }
</style>
</head><body>
<h1>🎵 BGM 업로드</h1>
<p>MP3 파일을 분위기별로 업로드하세요</p>

<select id="mood">
<option value="">-- 분위기 선택 --</option>
<option value="hopeful">😊 hopeful (희망적)</option>
<option value="sad">😢 sad (슬픔)</option>
<option value="tense">😰 tense (긴장)</option>
<option value="dramatic">🎭 dramatic (극적)</option>
<option value="calm">😌 calm (평화)</option>
<option value="inspiring">✨ inspiring (감동)</option>
<option value="mysterious">🔮 mysterious (미스터리)</option>
<option value="nostalgic">🌅 nostalgic (향수)</option>
</select>

<div class="upload-box" id="dropzone">
<p>📁 MP3 파일을 여기에 드래그하거나 클릭하여 선택</p>
<input type="file" id="fileInput" accept=".mp3,audio/mpeg" multiple style="display:none">
</div>

<div id="status"></div>

<h3>📋 업로드된 BGM</h3>
<div class="file-list" id="fileList">로딩 중...</div>

<script>
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const moodSelect = document.getElementById('mood');
const status = document.getElementById('status');

dropzone.onclick = () => fileInput.click();
dropzone.ondragover = (e) => { e.preventDefault(); dropzone.classList.add('dragover'); };
dropzone.ondragleave = () => dropzone.classList.remove('dragover');
dropzone.ondrop = (e) => { e.preventDefault(); dropzone.classList.remove('dragover'); handleFiles(e.dataTransfer.files); };
fileInput.onchange = () => handleFiles(fileInput.files);

async function handleFiles(files) {
    const mood = moodSelect.value;
    if (!mood) { alert('분위기를 먼저 선택하세요!'); return; }

    for (const file of files) {
        if (!file.name.endsWith('.mp3')) { alert(file.name + ' - MP3 파일만 가능합니다'); continue; }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('mood', mood);

        status.innerHTML = '⏳ 업로드 중: ' + file.name;
        status.className = '';

        try {
            const res = await fetch('/api/bgm/upload', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.ok) {
                status.innerHTML = '✅ 업로드 완료: ' + data.filename;
                status.className = 'success';
                loadFileList();
            } else {
                status.innerHTML = '❌ 실패: ' + data.error;
                status.className = 'error';
            }
        } catch (e) {
            status.innerHTML = '❌ 오류: ' + e.message;
            status.className = 'error';
        }
    }
}

async function loadFileList() {
    try {
        const res = await fetch('/api/bgm/list');
        const data = await res.json();
        if (data.ok) {
            let html = '<p>총 ' + data.total + '개 파일</p>';
            for (const [mood, files] of Object.entries(data.moods)) {
                html += '<div class="file-item"><span class="mood-tag ' + mood + '">' + mood + '</span> ' + files.join(', ') + '</div>';
            }
            document.getElementById('fileList').innerHTML = html || '<p>업로드된 파일 없음</p>';
        }
    } catch (e) { document.getElementById('fileList').innerHTML = '로드 실패'; }
}
loadFileList();
</script>
</body></html>'''


# ===== 효과음 파일 업로드 API =====
@app.route('/api/sfx/upload', methods=['POST'])
def api_upload_sfx():
    """효과음 파일 업로드 (MP3)"""
    try:
        if 'file' not in request.files:
            return jsonify({"ok": False, "error": "파일이 없습니다"}), 400

        file = request.files['file']
        sfx_type = request.form.get('type', '')

        if not file.filename:
            return jsonify({"ok": False, "error": "파일명이 없습니다"}), 400

        if not sfx_type:
            return jsonify({"ok": False, "error": "효과음 타입을 선택하세요"}), 400

        # 효과음 디렉토리 확인/생성 (스크립트 위치 기준 절대 경로)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sfx_dir = os.path.join(script_dir, "static", "audio", "sfx")
        os.makedirs(sfx_dir, exist_ok=True)
        print(f"[SFX-UPLOAD] 디렉토리: {sfx_dir}")

        # 기존 파일 확인하여 번호 부여
        import glob
        existing = glob.glob(os.path.join(sfx_dir, f"{sfx_type}*.mp3"))
        num = len(existing) + 1
        filename = f"{sfx_type}_{num:02d}.mp3"
        filepath = os.path.join(sfx_dir, filename)

        file.save(filepath)
        print(f"[SFX-UPLOAD] 저장됨: {filepath}")

        # Git에 자동 커밋 (배포 후에도 파일 유지)
        try:
            import subprocess
            subprocess.run(["git", "add", filepath], cwd=script_dir, timeout=30)
            subprocess.run(["git", "commit", "-m", f"Add SFX: {filename}"], cwd=script_dir, timeout=30)
            subprocess.run(["git", "push"], cwd=script_dir, timeout=60)
            print(f"[SFX-UPLOAD] Git 커밋 완료: {filename}")
        except Exception as git_err:
            print(f"[SFX-UPLOAD] Git 커밋 실패 (파일은 저장됨): {git_err}")

        return jsonify({
            "ok": True,
            "filename": filename,
            "path": filepath,
            "type": sfx_type,
            "count": num
        })

    except Exception as e:
        print(f"[SFX-UPLOAD] 오류: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/sfx/list', methods=['GET'])
def api_list_sfx():
    """업로드된 효과음 파일 목록"""
    try:
        import glob
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sfx_dir = os.path.join(script_dir, "static", "audio", "sfx")
        os.makedirs(sfx_dir, exist_ok=True)

        files = glob.glob(os.path.join(sfx_dir, "*.mp3"))
        print(f"[SFX-LIST] 디렉토리: {sfx_dir}, 파일 수: {len(files)}")
        types = {}

        for f in files:
            filename = os.path.basename(f)
            sfx_type = filename.split('_')[0].split('.')[0]
            if sfx_type not in types:
                types[sfx_type] = []
            types[sfx_type].append(filename)

        return jsonify({"ok": True, "types": types, "total": len(files)})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/sfx-upload')
def sfx_upload_page():
    """효과음 업로드 페이지"""
    return '''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>효과음 업로드</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; background: #1a1a2e; color: #eee; }
h1 { color: #ff6b6b; }
.upload-box { border: 2px dashed #444; padding: 40px; text-align: center; margin: 20px 0; border-radius: 10px; }
.upload-box.dragover { border-color: #ff6b6b; background: rgba(255,107,107,0.1); }
select, button { padding: 12px 24px; font-size: 16px; margin: 10px 5px; border-radius: 5px; border: none; cursor: pointer; }
select { background: #333; color: #fff; }
button { background: #ff6b6b; color: #fff; font-weight: bold; }
button:hover { background: #ee5a5a; }
.file-list { background: #2a2a4e; padding: 15px; border-radius: 10px; margin-top: 20px; }
.file-item { padding: 8px; border-bottom: 1px solid #444; }
.type-tag { display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; margin-right: 10px; background: #ff6b6b; }
#status { margin-top: 15px; padding: 10px; border-radius: 5px; }
.success { background: #1b5e20; } .error { background: #b71c1c; }
.info { background: #2a2a4e; padding: 15px; border-radius: 10px; margin-bottom: 20px; font-size: 14px; }
</style>
</head><body>
<h1>🔊 효과음 업로드</h1>

<div class="info">
<strong>필요한 효과음 6종류:</strong><br>
• impact - 충격/반전 (쿵!)<br>
• whoosh - 장면전환 (휙~)<br>
• ding - 강조/깨달음 (띵!)<br>
• tension - 긴장감 (드르르)<br>
• emotional - 감동 (피아노)<br>
• success - 성공/해피엔딩 (짠!)
</div>

<select id="sfxType">
<option value="">-- 효과음 타입 선택 --</option>
<option value="impact">💥 impact (충격/반전)</option>
<option value="whoosh">💨 whoosh (장면전환)</option>
<option value="ding">🔔 ding (강조/깨달음)</option>
<option value="tension">😰 tension (긴장감)</option>
<option value="emotional">🎹 emotional (감동)</option>
<option value="success">🎉 success (성공)</option>
</select>

<div class="upload-box" id="dropzone">
<p>📁 MP3 파일을 여기에 드래그하거나 클릭하여 선택</p>
<input type="file" id="fileInput" accept=".mp3,audio/mpeg" multiple style="display:none">
</div>

<div id="status"></div>

<h3>📋 업로드된 효과음</h3>
<div class="file-list" id="fileList">로딩 중...</div>

<script>
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const typeSelect = document.getElementById('sfxType');
const status = document.getElementById('status');

dropzone.onclick = () => fileInput.click();
dropzone.ondragover = (e) => { e.preventDefault(); dropzone.classList.add('dragover'); };
dropzone.ondragleave = () => dropzone.classList.remove('dragover');
dropzone.ondrop = (e) => { e.preventDefault(); dropzone.classList.remove('dragover'); handleFiles(e.dataTransfer.files); };
fileInput.onchange = () => handleFiles(fileInput.files);

async function handleFiles(files) {
    const sfxType = typeSelect.value;
    if (!sfxType) { alert('효과음 타입을 먼저 선택하세요!'); return; }

    for (const file of files) {
        if (!file.name.endsWith('.mp3')) { alert(file.name + ' - MP3 파일만 가능합니다'); continue; }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('type', sfxType);

        status.innerHTML = '⏳ 업로드 중: ' + file.name;
        status.className = '';

        try {
            const res = await fetch('/api/sfx/upload', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.ok) {
                status.innerHTML = '✅ 업로드 완료: ' + data.filename;
                status.className = 'success';
                loadFileList();
            } else {
                status.innerHTML = '❌ 실패: ' + data.error;
                status.className = 'error';
            }
        } catch (e) {
            status.innerHTML = '❌ 오류: ' + e.message;
            status.className = 'error';
        }
    }
}

async function loadFileList() {
    try {
        const res = await fetch('/api/sfx/list');
        const data = await res.json();
        if (data.ok) {
            let html = '<p>총 ' + data.total + '개 파일</p>';
            for (const [type, files] of Object.entries(data.types)) {
                html += '<div class="file-item"><span class="type-tag">' + type + '</span> ' + files.join(', ') + '</div>';
            }
            document.getElementById('fileList').innerHTML = html || '<p>업로드된 파일 없음</p>';
        }
    } catch (e) { document.getElementById('fileList').innerHTML = '로드 실패'; }
}
loadFileList();
</script>
</body></html>'''


# ===== Step6: 이미지 업로드 API =====
@app.route('/api/drama/upload-image', methods=['POST'])
def api_upload_image():
    """Base64 이미지를 서버에 업로드하고 URL 반환 (영상 생성 전 요청 크기 줄이기 위함)"""
    try:
        import base64
        from datetime import datetime as dt

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        image_data = data.get("imageData", "")

        if not image_data:
            return jsonify({"ok": False, "error": "이미지 데이터가 없습니다."}), 400

        # 이미 HTTP URL인 경우 그대로 반환
        if image_data.startswith('http://') or image_data.startswith('https://') or image_data.startswith('/'):
            return jsonify({"ok": True, "imageUrl": image_data})

        # Base64 데이터 URL인 경우 디코딩하여 저장
        if image_data.startswith('data:'):
            try:
                header, encoded = image_data.split(',', 1)
                img_bytes = base64.b64decode(encoded)

                # 이미지 형식 확인
                if 'png' in header:
                    ext = 'png'
                elif 'jpeg' in header or 'jpg' in header:
                    ext = 'jpg'
                elif 'webp' in header:
                    ext = 'webp'
                else:
                    ext = 'png'  # 기본값

                # 저장 디렉토리 생성
                static_image_dir = os.path.join(os.path.dirname(__file__), 'static', 'drama_images')
                os.makedirs(static_image_dir, exist_ok=True)

                # 고유한 파일명 생성
                timestamp = dt.now().strftime("%Y%m%d_%H%M%S_%f")
                image_filename = f"drama_{timestamp}.{ext}"
                image_path = os.path.join(static_image_dir, image_filename)

                # 이미지 저장
                with open(image_path, 'wb') as f:
                    f.write(img_bytes)

                image_url = f"/static/drama_images/{image_filename}"
                print(f"[DRAMA-UPLOAD] 이미지 업로드 완료: {image_filename} ({len(img_bytes) / 1024:.1f}KB)")

                return jsonify({"ok": True, "imageUrl": image_url})

            except Exception as e:
                print(f"[DRAMA-UPLOAD][ERROR] Base64 디코딩 실패: {str(e)}")
                return jsonify({"ok": False, "error": f"이미지 처리 실패: {str(e)}"}), 200

        return jsonify({"ok": False, "error": "지원하지 않는 이미지 형식입니다."}), 400

    except Exception as e:
        print(f"[DRAMA-UPLOAD][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Step6: 이미지 존재 여부 확인 API =====
@app.route('/api/drama/check-images', methods=['POST'])
def api_check_images():
    """영상 생성 전 이미지 파일 존재 여부 확인

    프론트엔드에서 영상 생성 요청 전에 이미지가 서버에 존재하는지 확인.
    /static/ 경로의 로컬 파일만 확인 (HTTP URL은 항상 valid로 처리).
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        image_urls = data.get("imageUrls", [])
        if not image_urls:
            return jsonify({"ok": False, "error": "이미지 URL 목록이 없습니다."}), 400

        results = []
        valid_count = 0
        missing_files = []

        for idx, img_url in enumerate(image_urls):
            result = {
                "index": idx,
                "url": img_url[:100] if img_url else "(empty)",
                "type": "unknown",
                "exists": False
            }

            if not img_url:
                result["type"] = "empty"
                result["error"] = "URL이 비어있습니다"
            elif img_url.startswith('data:'):
                result["type"] = "base64"
                result["exists"] = True  # Base64는 항상 유효
                valid_count += 1
            elif img_url.startswith('http://') or img_url.startswith('https://'):
                result["type"] = "http_url"
                result["exists"] = True  # HTTP URL은 사전 검증 불가, 유효로 처리
                valid_count += 1
            elif img_url.startswith('/static/'):
                result["type"] = "local_path"
                local_path = os.path.join(os.path.dirname(__file__), img_url.lstrip('/'))
                if os.path.exists(local_path):
                    result["exists"] = True
                    result["local_path"] = local_path
                    valid_count += 1
                else:
                    result["exists"] = False
                    result["error"] = f"파일이 존재하지 않습니다: {local_path}"
                    missing_files.append(img_url)
            else:
                result["type"] = "unknown"
                result["error"] = f"알 수 없는 URL 형식: {img_url[:50]}..."

            results.append(result)

        all_valid = valid_count == len(image_urls)

        print(f"[DRAMA-CHECK-IMAGES] 이미지 검증 완료: {valid_count}/{len(image_urls)} 유효")
        if missing_files:
            print(f"[DRAMA-CHECK-IMAGES] 누락된 파일: {missing_files}")

        return jsonify({
            "ok": True,
            "allValid": all_valid,
            "totalCount": len(image_urls),
            "validCount": valid_count,
            "missingFiles": missing_files,
            "results": results
        })

    except Exception as e:
        import traceback
        print(f"[DRAMA-CHECK-IMAGES][ERROR] {str(e)}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Step6: 씬별 클립 생성 헬퍼 함수 (병렬 처리용) =====
def _create_scene_clip(args):
    """
    단일 씬의 클립을 생성하는 헬퍼 함수 (ThreadPoolExecutor용)

    Args:
        args: (idx, cut, temp_dir, width, height, fps)

    Returns:
        (idx, segment_path, duration) 또는 (idx, None, 0) on failure
    """
    import requests
    import base64
    import subprocess
    import shutil
    import gc

    idx, cut, temp_dir, width, height, fps = args
    cut_id = cut.get('cutId', idx + 1)
    img_url = cut.get('imageUrl', '')
    audio_url = cut.get('audioUrl', '')
    cut_duration = cut.get('duration', 10)

    print(f"[DRAMA-PARALLEL] 씬 {cut_id} 병렬 처리 시작 (worker)")

    # 이미지 다운로드/처리
    img_path = os.path.join(temp_dir, f"image_{idx:03d}.png")
    if img_url:
        try:
            if img_url.startswith('data:'):
                header, encoded = img_url.split(',', 1)
                img_data = base64.b64decode(encoded)
                with open(img_path, 'wb') as f:
                    f.write(img_data)
                del img_data  # 메모리 즉시 해제
                gc.collect()
            elif img_url.startswith('/static/'):
                local_path = os.path.join(os.path.dirname(__file__), img_url.lstrip('/'))
                if os.path.exists(local_path):
                    shutil.copy2(local_path, img_path)
                else:
                    print(f"[DRAMA-PARALLEL] 씬 {cut_id} 로컬 이미지 없음: {local_path}")
                    return (idx, None, 0)
            else:
                response = requests.get(img_url, timeout=60)
                if response.status_code == 200:
                    with open(img_path, 'wb') as f:
                        f.write(response.content)
                else:
                    print(f"[DRAMA-PARALLEL] 씬 {cut_id} 이미지 다운로드 실패: {img_url}")
                    return (idx, None, 0)
        except Exception as e:
            print(f"[DRAMA-PARALLEL] 씬 {cut_id} 이미지 처리 오류: {e}")
            return (idx, None, 0)
    else:
        print(f"[DRAMA-PARALLEL] 씬 {cut_id} 이미지 URL 없음")
        return (idx, None, 0)

    # 오디오 다운로드/처리
    audio_path = os.path.join(temp_dir, f"audio_{idx:03d}.mp3")
    actual_duration = cut_duration
    has_audio = False

    if audio_url:
        try:
            if audio_url.startswith('data:'):
                header, encoded = audio_url.split(',', 1)
                audio_data = base64.b64decode(encoded)
                with open(audio_path, 'wb') as f:
                    f.write(audio_data)
                del audio_data  # 메모리 즉시 해제
                gc.collect()
                has_audio = True
            elif audio_url.startswith('/static/'):
                local_path = os.path.join(os.path.dirname(__file__), audio_url.lstrip('/'))
                if os.path.exists(local_path):
                    shutil.copy2(local_path, audio_path)
                    has_audio = True
            else:
                response = requests.get(audio_url, timeout=60)
                if response.status_code == 200:
                    with open(audio_path, 'wb') as f:
                        f.write(response.content)
                    has_audio = True
        except Exception as e:
            print(f"[DRAMA-PARALLEL] 씬 {cut_id} 오디오 처리 오류: {e}")

    # 오디오가 있으면 실제 길이 확인
    if has_audio and os.path.exists(audio_path):
        try:
            probe_cmd = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', audio_path
            ]
            result = subprocess.run(probe_cmd, capture_output=True, text=True)
            if result.stdout.strip():
                actual_duration = float(result.stdout.strip())
        except Exception as e:
            print(f"[DRAMA-PARALLEL] 씬 {cut_id} 오디오 길이 확인 오류: {e}")

    print(f"[DRAMA-PARALLEL] 씬 {cut_id}: 오디오={has_audio}, 길이={actual_duration:.1f}초")

    # 씬별 클립 생성
    segment_path = os.path.join(temp_dir, f"segment_{idx:03d}.mp4")

    # CPU 최적화: FPS 24, CRF 32, threads 1 (1 CPU 환경용)
    target_fps = min(fps, 24)  # 최대 24 FPS로 제한

    if has_audio:
        # 이미지 + 오디오로 클립 생성
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-threads', '1',  # CPU 스파이크 방지
            '-loop', '1',
            '-i', img_path,
            '-i', audio_path,
            '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '32', '-threads', '1',
            '-c:a', 'aac', '-b:a', '96k',
            '-r', str(target_fps),
            '-t', str(actual_duration),
            '-shortest',
            '-pix_fmt', 'yuv420p',
            segment_path
        ]
    else:
        # 오디오 없이 이미지만으로 클립 생성 (무음)
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-threads', '1',  # CPU 스파이크 방지
            '-loop', '1',
            '-i', img_path,
            '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
            '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '32', '-threads', '1',
            '-c:a', 'aac',
            '-r', str(target_fps),
            '-t', str(actual_duration),
            '-shortest',
            '-pix_fmt', 'yuv420p',
            segment_path
        ]

    try:
        print(f"[DRAMA-PARALLEL] 씬 {cut_id} FFmpeg 시작...")
        # 메모리 최적화: stdout DEVNULL, stderr만 PIPE로 캡처 (OOM 방지)
        process = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=180
        )
        if process.returncode == 0 and os.path.exists(segment_path):
            print(f"[DRAMA-PARALLEL] 씬 {cut_id} 클립 생성 완료: {actual_duration:.1f}초")
            del process  # 명시적 해제
            gc.collect()
            return (idx, segment_path, actual_duration)
        else:
            # 에러 시에만 stderr 읽기 (최대 500바이트)
            stderr_msg = process.stderr[:500].decode('utf-8', errors='ignore') if process.stderr else '(stderr 없음)'
            del process
            gc.collect()
            print(f"[DRAMA-PARALLEL] 씬 {cut_id} FFmpeg 오류: {stderr_msg[:200]}")
            return (idx, None, 0)
    except subprocess.TimeoutExpired:
        print(f"[DRAMA-PARALLEL] 씬 {cut_id} 타임아웃 (180초 초과)")
        return (idx, None, 0)
    except Exception as e:
        print(f"[DRAMA-PARALLEL] 씬 {cut_id} 클립 생성 오류: {e}")
        return (idx, None, 0)


# ===== Step6: 씬별 클립 생성 후 concat 방식 영상 제작 (병렬 처리) =====
def _generate_video_with_cuts(cuts, subtitle_data, burn_subtitle, resolution, fps, update_progress):
    """
    cuts 배열을 사용하여 각 씬별로 클립을 병렬 생성하고 concat하여 최종 영상 생성.
    이 방식은 각 씬의 이미지와 오디오가 정확히 매칭됨.

    Args:
        cuts: [{'cutId': 1, 'imageUrl': '...', 'audioUrl': '...', 'duration': 10}, ...]
        subtitle_data: 자막 데이터
        burn_subtitle: 자막 하드코딩 여부
        resolution: 해상도 (예: '1920x1080')
        fps: 프레임 레이트
        update_progress: 진행률 업데이트 함수
    """
    import requests
    import base64
    import tempfile
    import subprocess
    import shutil
    import gc

    print(f"[DRAMA-CUTS-VIDEO] 씬별 영상 생성 시작 - {len(cuts)}개 씬")
    print(f"[DRAMA-CUTS-VIDEO] 입력 데이터 - resolution: {resolution}, fps: {fps}, burn_subtitle: {burn_subtitle}")

    # 상세 디버깅: 각 cut의 audio URL 상태 확인
    for i, cut in enumerate(cuts):
        audio_url = cut.get('audioUrl', '')
        has_audio = bool(audio_url and len(audio_url) > 0)
        print(f"[DRAMA-CUTS-VIDEO] cut[{i}] - imageUrl: {'있음' if cut.get('imageUrl') else '없음'}, audioUrl: {'있음' if has_audio else '없음 ⚠️'}, duration: {cut.get('duration', 'N/A')}")

    # 해상도 파싱 및 최적화 (512MB 환경)
    try:
        width, height = resolution.split('x')
        width, height = int(width), int(height)
    except Exception as e:
        print(f"[DRAMA-CUTS-VIDEO] ❌ 해상도 파싱 오류: resolution='{resolution}', error={e}")
        raise Exception(f"해상도 형식 오류: '{resolution}' (예상 형식: '1920x1080')")

    # Render Standard 1 CPU: 480p로 제한 (CPU 부하 감소)
    MAX_WIDTH = 854    # 480p (1 CPU 환경)
    MAX_HEIGHT = 480
    if width > MAX_WIDTH or height > MAX_HEIGHT:
        aspect_ratio = width / height
        if aspect_ratio > 16/9:
            width = MAX_WIDTH
            height = int(MAX_WIDTH / aspect_ratio)
        else:
            height = MAX_HEIGHT
            width = int(MAX_HEIGHT * aspect_ratio)
        resolution = f"{width}x{height}"
        print(f"[DRAMA-CUTS-VIDEO] 메모리 최적화 - 해상도 조정: {resolution}")

    with tempfile.TemporaryDirectory() as temp_dir:
        update_progress(10, "씬별 영상 순차 생성 중...")

        segment_files = []
        total_duration = 0.0

        # 완전 순차 처리 (ThreadPoolExecutor 제거 - OOM 방지)
        print(f"[DRAMA-SEQUENTIAL] 순차 처리 시작 - {len(cuts)}개 씬 (메모리 절약 모드)")

        for idx, cut in enumerate(cuts):
            update_progress(15 + int((idx / len(cuts)) * 55), f"씬 {idx+1}/{len(cuts)} 클립 생성 중...")

            try:
                # 씬 클립 생성
                task = (idx, cut, temp_dir, width, height, fps)
                result_idx, segment_path, duration = _create_scene_clip(task)

                if segment_path and os.path.exists(segment_path):
                    segment_files.append(segment_path)
                    total_duration += duration
                    print(f"[DRAMA-SEQUENTIAL] 씬 {idx+1} 완료: {duration:.1f}초")
                else:
                    print(f"[DRAMA-SEQUENTIAL] 씬 {idx+1} 실패")

            except Exception as e:
                print(f"[DRAMA-SEQUENTIAL] 씬 {idx+1} 오류: {e}")

            # 각 씬 처리 후 강제 메모리 정리
            gc.collect()

        print(f"[DRAMA-SEQUENTIAL] 순차 처리 완료 - 성공: {len(segment_files)}/{len(cuts)}, 총 길이: {total_duration:.1f}초")

        # 메모리 정리
        gc.collect()

        if not segment_files:
            raise Exception("클립을 생성하지 못했습니다. 이미지와 오디오 파일을 확인해주세요.")

        # 모든 세그먼트 concat
        update_progress(75, f"영상 병합 중... ({len(segment_files)}개 클립)")

        concat_list_path = os.path.join(temp_dir, "concat.txt")
        with open(concat_list_path, 'w', encoding='utf-8') as f:
            for seg in segment_files:
                f.write(f"file '{seg}'\n")

        output_path = os.path.join(temp_dir, "output.mp4")
        concat_cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_list_path,
            '-c', 'copy',
            output_path
        ]

        try:
            print(f"[DRAMA-CUTS-VIDEO] Concat 명령: {' '.join(concat_cmd)}")
            print(f"[DRAMA-CUTS-VIDEO] concat.txt 내용:")
            with open(concat_list_path, 'r') as f:
                print(f.read())
            # 메모리 최적화: stdout DEVNULL, stderr만 PIPE (OOM 방지)
            process = subprocess.run(
                concat_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=600
            )
            if process.returncode != 0:
                stderr_msg = process.stderr[:500].decode('utf-8', errors='ignore') if process.stderr else '(stderr 없음)'
                print(f"[DRAMA-CUTS-VIDEO] Concat 오류 (returncode={process.returncode}): {stderr_msg}")
                del process
                gc.collect()
                raise Exception(f"영상 병합 실패: {stderr_msg[:200]}")
            del process
            gc.collect()
            print(f"[DRAMA-CUTS-VIDEO] Concat 완료, 파일 존재: {os.path.exists(output_path)}")
        except subprocess.TimeoutExpired:
            raise Exception("영상 병합 타임아웃 (10분)")

        update_progress(90, "영상 저장 중...")

        # 최종 영상을 static 폴더에 저장
        static_video_dir = os.path.join(os.path.dirname(__file__), 'static', 'videos')
        os.makedirs(static_video_dir, exist_ok=True)

        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        video_filename = f"drama_{timestamp}.mp4"
        final_video_path = os.path.join(static_video_dir, video_filename)

        shutil.copy2(output_path, final_video_path)

        # 파일 크기 확인
        file_size = os.path.getsize(final_video_path)
        file_size_mb = file_size / (1024 * 1024)

        video_url = f"/static/videos/{video_filename}"

        # Base64 인코딩 (10MB 이하만 - 2GB 환경 메모리 최적화)
        # 10MB 영상 + Base64 오버헤드(33%) = ~13MB 메모리 사용
        if file_size_mb <= 10:
            with open(final_video_path, 'rb') as f:
                video_data = f.read()
            video_base64 = base64.b64encode(video_data).decode('utf-8')
            video_url_base64 = f"data:video/mp4;base64,{video_base64}"
            del video_data
            del video_base64
            gc.collect()
        else:
            video_url_base64 = None

        print(f"[DRAMA-CUTS-VIDEO] 영상 생성 완료 - {len(segment_files)}개 씬, 총 {total_duration:.1f}초, {file_size_mb:.2f}MB")

        update_progress(100, "완료!")

        return {
            "videoUrl": video_url_base64 or video_url,
            "videoFileUrl": video_url,
            "duration": total_duration,
            "fileSize": file_size,
            "fileSizeMB": round(file_size_mb, 2),
            "cutsCount": len(segment_files)
        }


# ===== Step6: 영상 제작 (동기 함수) =====
def _generate_video_sync(images, audio_url, subtitle_data, burn_subtitle, resolution, fps, transition, job_id=None, cuts=None):
    """
    실제 영상 생성 로직 (동기)
    백그라운드 워커에서 호출됨
    메모리 최적화: 512MB 제한 환경에서 작동

    Args:
        cuts: 씬별 이미지-오디오 매칭 배열 (선택적)
              [{'cutId': 1, 'imageUrl': '...', 'audioUrl': '...', 'duration': 10}, ...]
    """
    import requests
    import base64
    import tempfile
    import subprocess
    import shutil
    import gc

    # 의존성 체크: Pillow
    try:
        from PIL import Image
    except ImportError:
        raise Exception("Pillow 라이브러리가 설치되어 있지 않습니다. 'pip install Pillow' 명령으로 설치해주세요.")

    # 의존성 체크: FFmpeg
    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        raise Exception("FFmpeg가 설치되어 있지 않습니다. 'apt-get install ffmpeg' 명령으로 설치해주세요.")

    # 메모리 최적화: 해상도 자동 제한 (512MB 환경)
    try:
        width, height = resolution.split('x')
        width, height = int(width), int(height)
    except Exception as e:
        print(f"[DRAMA-STEP6-VIDEO] ❌ 해상도 파싱 오류: resolution='{resolution}', error={e}")
        raise Exception(f"해상도 형식 오류: '{resolution}' (예상 형식: '1920x1080')")

    # Render Standard 1 CPU: 480p로 제한 (CPU 부하 감소)
    MAX_WIDTH = 854
    MAX_HEIGHT = 480
    if width > MAX_WIDTH or height > MAX_HEIGHT:
        aspect_ratio = width / height
        if aspect_ratio > 16/9:  # 와이드
            width = MAX_WIDTH
            height = int(MAX_WIDTH / aspect_ratio)
        else:
            height = MAX_HEIGHT
            width = int(MAX_HEIGHT * aspect_ratio)
        resolution = f"{width}x{height}"
        print(f"[DRAMA-STEP6-VIDEO][메모리 최적화] 해상도 조정: {resolution}")

    print(f"[DRAMA-STEP6-VIDEO] 영상 생성 시작 - 이미지: {len(images)}개, 해상도: {resolution}, job_id: {job_id}")

    # 진행률 업데이트 함수
    def update_progress(progress, message=""):
        if job_id:
            with video_jobs_lock:
                if job_id in video_jobs:
                    video_jobs[job_id]['progress'] = progress
                    if message:
                        video_jobs[job_id]['message'] = message
                    save_video_jobs()  # 파일에 저장

    update_progress(5, "의존성 확인 완료, 영상 생성 준비 중...")

    # ===== cuts 배열이 있으면 씬별 클립 생성 후 concat 방식 사용 =====
    if cuts and len(cuts) > 0:
        print(f"[DRAMA-STEP6-VIDEO] cuts 기반 영상 생성 ({len(cuts)}개 씬)")
        return _generate_video_with_cuts(cuts, subtitle_data, burn_subtitle, resolution, fps, update_progress)

    # 임시 디렉토리 생성
    with tempfile.TemporaryDirectory() as temp_dir:
        update_progress(10, "이미지 다운로드 중...")
        # 1. 이미지 다운로드
        image_paths = []
        failed_images = []

        for idx, img_url in enumerate(images):
            img_path = os.path.join(temp_dir, f"image_{idx:03d}.png")
            update_progress(10 + (idx / len(images)) * 15, f"이미지 다운로드 중... ({idx+1}/{len(images)})")

            try:
                # 임시 원본 이미지 경로
                temp_img_path = os.path.join(temp_dir, f"temp_{idx:03d}.png")

                if img_url.startswith('data:'):
                    # Base64 데이터 URL
                    header, encoded = img_url.split(',', 1)
                    img_data = base64.b64decode(encoded)
                    with open(temp_img_path, 'wb') as f:
                        f.write(img_data)
                elif img_url.startswith('/static/'):
                    # 로컬 static 파일 경로
                    local_path = os.path.join(os.path.dirname(__file__), img_url.lstrip('/'))
                    if os.path.exists(local_path):
                        shutil.copy2(local_path, temp_img_path)
                    else:
                        print(f"[DRAMA-STEP6-VIDEO] 로컬 이미지 파일 없음: {local_path}")
                        failed_images.append(f"이미지 {idx+1}")
                        continue
                else:
                    # HTTP URL (재시도 로직 추가)
                    max_retries = 3
                    for retry in range(max_retries):
                        try:
                            response = requests.get(img_url, timeout=60)
                            if response.status_code == 200:
                                with open(temp_img_path, 'wb') as f:
                                    f.write(response.content)
                                break
                            else:
                                if retry == max_retries - 1:
                                    print(f"[DRAMA-STEP6-VIDEO] 이미지 다운로드 실패: {img_url} (상태: {response.status_code})")
                                    failed_images.append(f"이미지 {idx+1}")
                                    continue
                        except requests.exceptions.RequestException as e:
                            if retry == max_retries - 1:
                                print(f"[DRAMA-STEP6-VIDEO] 이미지 다운로드 오류: {img_url} - {str(e)}")
                                failed_images.append(f"이미지 {idx+1}")
                                continue
                            import time
                            time.sleep(1)

                # 메모리 최적화: 이미지 리사이즈 (메모리 사용량 감소)
                if os.path.exists(temp_img_path):
                    try:
                        img = Image.open(temp_img_path)
                        # 목표 해상도로 리사이즈 (aspect ratio 유지)
                        img.thumbnail((width, height), Image.Resampling.LANCZOS)
                        # 최적화된 이미지 저장
                        img.save(img_path, 'PNG', optimize=True)
                        img.close()
                        # 임시 파일 즉시 삭제
                        os.remove(temp_img_path)
                        # 가비지 컬렉션
                        gc.collect()
                    except Exception as resize_err:
                        print(f"[DRAMA-STEP6-VIDEO] 이미지 리사이즈 실패, 원본 사용: {resize_err}")
                        if os.path.exists(temp_img_path):
                            shutil.move(temp_img_path, img_path)

                image_paths.append(img_path)
            except Exception as e:
                print(f"[DRAMA-STEP6-VIDEO] 이미지 처리 오류 ({idx+1}): {str(e)}")
                failed_images.append(f"이미지 {idx+1}")

        if not image_paths:
            raise Exception(f"모든 이미지 다운로드 실패. 실패한 이미지: {', '.join(failed_images)}")

        if failed_images:
            print(f"[DRAMA-STEP6-VIDEO] 일부 이미지 실패 ({len(failed_images)}개): {', '.join(failed_images)}")

        update_progress(30, "오디오 처리 중...")

        # 2. 오디오 저장 (재시도 로직 추가)
        audio_path = os.path.join(temp_dir, "audio.mp3")
        if audio_url.startswith('data:'):
            header, encoded = audio_url.split(',', 1)
            audio_data = base64.b64decode(encoded)
            with open(audio_path, 'wb') as f:
                f.write(audio_data)
        elif audio_url.startswith('/static/'):
            # 로컬 static 파일 경로
            local_audio_path = os.path.join(os.path.dirname(__file__), audio_url.lstrip('/'))
            if os.path.exists(local_audio_path):
                shutil.copy2(local_audio_path, audio_path)
            else:
                raise Exception(f"오디오 파일을 찾을 수 없습니다: {audio_url}")
        else:
            # HTTP URL (재시도 로직 추가)
            max_retries = 3
            audio_downloaded = False
            for retry in range(max_retries):
                try:
                    response = requests.get(audio_url, timeout=60)
                    if response.status_code == 200:
                        with open(audio_path, 'wb') as f:
                            f.write(response.content)
                        audio_downloaded = True
                        break
                    else:
                        if retry == max_retries - 1:
                            raise Exception(f"오디오 다운로드 실패 (HTTP {response.status_code})")
                except requests.exceptions.RequestException as e:
                    if retry == max_retries - 1:
                        raise Exception(f"오디오 다운로드 오류: {str(e)}")
                    import time
                    time.sleep(1)

            if not audio_downloaded:
                raise Exception("오디오를 다운로드할 수 없습니다.")

        update_progress(40, "영상 인코딩 준비 중...")

        # 3. 오디오 길이 확인
        probe_cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', audio_path
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        audio_duration = float(result.stdout.strip()) if result.stdout.strip() else 60.0

        # 4. 이미지당 표시 시간 계산
        image_duration = audio_duration / len(image_paths)

        # 5. 이미지 리스트 파일 생성 (FFmpeg용)
        list_path = os.path.join(temp_dir, "images.txt")
        with open(list_path, 'w') as f:
            for img_path in image_paths:
                f.write(f"file '{img_path}'\n")
                f.write(f"duration {image_duration}\n")
            # 마지막 이미지 한번 더 (FFmpeg concat demuxer 요구사항)
            f.write(f"file '{image_paths[-1]}'\n")

        # 6. 해상도 파싱
        width, height = resolution.split('x')

        # 7. FFmpeg로 영상 생성
        output_path = os.path.join(temp_dir, "output.mp4")

        # 기본 FFmpeg 명령어 (메모리 최적화)
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-f', 'concat', '-safe', '0', '-i', list_path,
            '-i', audio_path,
            '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',  # 메모리 최적화: ultrafast preset, 높은 CRF
            '-c:a', 'aac', '-b:a', '96k',  # 오디오 비트레이트 감소
            '-r', str(fps),
            '-shortest',
            '-pix_fmt', 'yuv420p',
            '-threads', '2',  # 스레드 수 제한 (메모리 절약)
            output_path
        ]

        # 자막 하드코딩 옵션
        if burn_subtitle and subtitle_data and subtitle_data.get('srt'):
            # SRT를 ASS로 변환하여 한글 폰트 명시적 지정
            ass_path = os.path.join(temp_dir, "subtitle.ass")
            srt_content = subtitle_data['srt']

            # 한글 폰트 확인 (ASS 자막은 폰트 이름만 사용)
            base_dir = os.path.dirname(os.path.abspath(__file__))
            project_font = os.path.join(base_dir, 'fonts', 'Pretendard-Bold.ttf')

            font_found = False
            font_location = None
            if os.path.exists(project_font):
                font_found = True
                font_location = project_font
            else:
                # 시스템 폰트 폴백
                system_fonts = [
                    os.path.join(base_dir, 'fonts', 'Pretendard-SemiBold.ttf'),
                    os.path.join(base_dir, 'fonts', 'NanumGothicBold.ttf'),
                    '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
                ]
                for sf in system_fonts:
                    if os.path.exists(sf):
                        font_found = True
                        font_location = sf
                        break

            # ASS 자막에는 폰트 경로가 아닌 폰트 이름을 사용해야 함
            subtitle_font = 'Pretendard' if font_found else 'Arial'

            print(f"[VIDEO-SUBTITLE] 자막 폰트: {subtitle_font} (found: {font_found}, location: {font_location if font_found else 'N/A'})")

            # ASS 헤더 생성 (한글 폰트 명시)
            ass_header = f"""[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{subtitle_font},40,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,20,20,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

            # SRT를 ASS 이벤트로 변환
            import re

            def srt_to_ass_time(srt_time):
                """SRT 타임스탬프(00:00:00,000)를 ASS 형식(0:00:00.00)으로 변환"""
                # SRT: HH:MM:SS,mmm (밀리초 3자리)
                # ASS: H:MM:SS.cc (센티초 2자리, 시간은 앞의 0 제거)
                hours, minutes, seconds_ms = srt_time.split(':')
                seconds, milliseconds = seconds_ms.split(',')
                centiseconds = int(milliseconds) // 10  # 밀리초를 센티초로 변환
                return f"{int(hours)}:{minutes}:{seconds}.{centiseconds:02d}"

            ass_events = []

            # SRT 블록 분할 개선: \r\n, \n 모두 처리하고, 빈 줄 여러 개도 대응
            srt_normalized = srt_content.replace('\r\n', '\n').strip()
            # 빈 줄 1개 이상으로 분할 (정규식 사용)
            srt_blocks = re.split(r'\n\s*\n', srt_normalized)

            print(f"[VIDEO-SUBTITLE] SRT 블록 수: {len(srt_blocks)}")

            for idx, block in enumerate(srt_blocks):
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    # 타임코드 파싱 (00:00:00,000 --> 00:00:03,000)
                    time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
                    if time_match:
                        start_time = srt_to_ass_time(time_match.group(1))
                        end_time = srt_to_ass_time(time_match.group(2))
                        text = '\\N'.join(lines[2:])  # ASS는 \N으로 줄바꿈
                        ass_events.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}")
                    else:
                        print(f"[VIDEO-SUBTITLE] 블록 {idx+1} 타임코드 파싱 실패: {lines[1][:50] if len(lines) > 1 else 'N/A'}")
                elif len(lines) >= 2:
                    # 2줄인 경우 - 숫자 + 타임코드만 있고 텍스트가 없는 경우일 수 있음
                    print(f"[VIDEO-SUBTITLE] 블록 {idx+1} 라인 부족 ({len(lines)}줄): {lines}")

            print(f"[VIDEO-SUBTITLE] ASS 이벤트 생성 완료: {len(ass_events)}개")

            # ASS 파일 작성
            with open(ass_path, 'w', encoding='utf-8') as f:
                f.write(ass_header)
                # 이벤트 줄 사이에 줄바꿈 추가
                for event in ass_events:
                    f.write(event + '\n')

            # ASS 자막 필터 추가 (경로 이스케이프 처리)
            # FFmpeg ass 필터는 경로에서 콜론(:)과 백슬래시(\)를 이스케이프해야 함
            escaped_ass_path = ass_path.replace('\\', '\\\\').replace(':', '\\:')

            # 폰트 디렉토리 설정 (프로젝트 내 fonts 폴더 사용)
            fonts_dir = os.path.join(base_dir, 'fonts')
            escaped_fonts_dir = fonts_dir.replace('\\', '\\\\').replace(':', '\\:')

            # fontsdir 옵션으로 FFmpeg이 프로젝트 내 폰트를 인식하도록 설정
            if font_found and os.path.exists(fonts_dir):
                vf_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,ass={escaped_ass_path}:fontsdir={escaped_fonts_dir}"
            else:
                vf_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,ass={escaped_ass_path}"
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-f', 'concat', '-safe', '0', '-i', list_path,
                '-i', audio_path,
                '-vf', vf_filter,
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',  # 메모리 최적화
                '-c:a', 'aac', '-b:a', '96k',  # 오디오 비트레이트 감소
                '-r', str(fps),
                '-shortest',
                '-pix_fmt', 'yuv420p',
                '-threads', '2',  # 스레드 수 제한
                output_path
            ]

        print(f"[DRAMA-STEP6-VIDEO] FFmpeg 명령어 실행: {' '.join(ffmpeg_cmd[:5])}...")
        update_progress(50, "영상 인코딩 중...")

        # FFmpeg 실행 (타임아웃 30분 - 10분 이상 영상 지원)
        # 메모리 최적화: stdout DEVNULL, stderr만 PIPE (OOM 방지 - 30분 인코딩 시 수백MB 출력 가능)
        try:
            process = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=1800
            )
        except subprocess.TimeoutExpired:
            print(f"[DRAMA-STEP6-VIDEO][ERROR] FFmpeg 타임아웃 (30분)")
            raise Exception("영상 인코딩 시간 초과 (30분). 이미지 수를 줄이거나 해상도를 낮춰주세요.")

        if process.returncode != 0:
            # 에러 시에만 stderr 읽기 (최대 1000바이트)
            error_msg = process.stderr[:1000].decode('utf-8', errors='ignore').strip() if process.stderr else ''
            print(f"[DRAMA-STEP6-VIDEO][ERROR] FFmpeg 오류: {error_msg}")
            del process
            gc.collect()

            # 일반적인 오류 메시지 개선
            if "No such file or directory" in error_msg:
                raise Exception("파일을 찾을 수 없습니다. 이미지나 오디오 파일이 손상되었을 수 있습니다.")
            elif "Invalid data" in error_msg or "corrupt" in error_msg:
                raise Exception("손상된 파일이 감지되었습니다. 이미지나 오디오를 다시 생성해주세요.")
            elif "Permission denied" in error_msg:
                raise Exception("파일 권한 오류. 서버 관리자에게 문의하세요.")
            else:
                raise Exception(f"영상 인코딩 실패: {error_msg[:300]}")

        del process
        gc.collect()

        update_progress(80, "영상 저장 중...")

        # 8. 생성된 영상을 static 폴더에 저장
        static_video_dir = os.path.join(os.path.dirname(__file__), 'static', 'videos')
        os.makedirs(static_video_dir, exist_ok=True)

        # 고유한 파일명 생성
        timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
        video_filename = f"drama_{timestamp}.mp4"
        final_video_path = os.path.join(static_video_dir, video_filename)

        # 영상 파일 복사
        shutil.copy2(output_path, final_video_path)

        # 파일 크기 확인
        file_size = os.path.getsize(final_video_path)
        file_size_mb = file_size / (1024 * 1024)

        # 메모리 최적화: Base64 인코딩 제한을 10MB로 낮춤 (2GB 환경)
        # 10MB 영상 + Base64 오버헤드(33%) = ~13MB 메모리 사용
        video_url = f"/static/videos/{video_filename}"
        if file_size_mb <= 10:
            with open(final_video_path, 'rb') as f:
                video_data = f.read()
            video_base64 = base64.b64encode(video_data).decode('utf-8')
            video_url_base64 = f"data:video/mp4;base64,{video_base64}"
            # 즉시 메모리 해제
            del video_data
            del video_base64
            gc.collect()
        else:
            video_url_base64 = None

        print(f"[DRAMA-STEP6-VIDEO] 영상 생성 완료 - 크기: {file_size_mb:.2f}MB, 길이: {audio_duration:.1f}초, 파일: {video_filename}")

        # 메모리 정리
        gc.collect()

        # 결과를 dict로 반환 (jsonify 대신)
        return {
            "ok": True,
            "videoUrl": video_url_base64 if video_url_base64 else video_url,
            "videoFileUrl": video_url,
            "duration": audio_duration,
            "fileSize": file_size,
            "fileSizeMB": round(file_size_mb, 2)
        }


# ===== Step4: 씬별 MP4 클립 생성 (개별 다운로드용) =====
@app.route('/api/drama/generate-scene-clip', methods=['POST'])
def api_generate_scene_clip():
    """단일 씬 클립 생성 (이미지 + 오디오 → MP4)

    가벼운 작업이므로 CPU 부하가 낮습니다.
    """
    import base64
    import tempfile
    import subprocess
    import shutil

    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        scene_id = data.get("sceneId", "scene_1")
        image_url = data.get("imageUrl", "")
        audio_url = data.get("audioUrl", "")

        print(f"[SCENE-CLIP] 씬 클립 생성 시작: {scene_id}")

        if not image_url:
            return jsonify({"ok": False, "error": "이미지가 없습니다."}), 400
        if not audio_url:
            return jsonify({"ok": False, "error": "오디오가 없습니다."}), 400

        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. 이미지 저장
            img_path = os.path.join(temp_dir, "image.png")
            if image_url.startswith('data:'):
                header, encoded = image_url.split(',', 1)
                img_data = base64.b64decode(encoded)
                with open(img_path, 'wb') as f:
                    f.write(img_data)
            else:
                response = requests.get(image_url, timeout=60)
                with open(img_path, 'wb') as f:
                    f.write(response.content)

            # 2. 오디오 저장
            audio_path = os.path.join(temp_dir, "audio.mp3")
            if audio_url.startswith('data:'):
                header, encoded = audio_url.split(',', 1)
                audio_data = base64.b64decode(encoded)
                with open(audio_path, 'wb') as f:
                    f.write(audio_data)
            else:
                response = requests.get(audio_url, timeout=60)
                with open(audio_path, 'wb') as f:
                    f.write(response.content)

            # 3. 오디오 길이 확인
            probe_cmd = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', audio_path
            ]
            result = subprocess.run(probe_cmd, capture_output=True, text=True)
            duration = float(result.stdout.strip()) if result.stdout.strip() else 10.0

            print(f"[SCENE-CLIP] {scene_id}: 오디오 길이 {duration:.1f}초")

            # 4. MP4 생성 (720p, 가벼운 설정)
            output_path = os.path.join(temp_dir, f"{scene_id}.mp4")
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-threads', '1',
                '-loop', '1',
                '-i', img_path,
                '-i', audio_path,
                '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28', '-threads', '1',
                '-c:a', 'aac', '-b:a', '128k',
                '-r', '24',
                '-t', str(duration),
                '-shortest',
                '-pix_fmt', 'yuv420p',
                output_path
            ]

            # 메모리 최적화: stdout DEVNULL, stderr만 PIPE (OOM 방지)
            process = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=120
            )

            if process.returncode != 0 or not os.path.exists(output_path):
                stderr_msg = process.stderr[:300].decode('utf-8', errors='ignore') if process.stderr else '(stderr 없음)'
                print(f"[SCENE-CLIP] FFmpeg 오류: {stderr_msg}")
                del process
                gc.collect()
                return jsonify({"ok": False, "error": "클립 생성 실패"}), 500
            del process
            gc.collect()

            # 5. 결과 반환 (Base64)
            with open(output_path, 'rb') as f:
                video_data = f.read()

            video_base64 = base64.b64encode(video_data).decode('utf-8')
            file_size = len(video_data)

            print(f"[SCENE-CLIP] {scene_id} 완료: {duration:.1f}초, {file_size/(1024*1024):.2f}MB")

            return jsonify({
                "ok": True,
                "sceneId": scene_id,
                "videoUrl": f"data:video/mp4;base64,{video_base64}",
                "duration": duration,
                "fileSize": file_size,
                "fileSizeMB": round(file_size / (1024 * 1024), 2)
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/drama/generate-scene-clips-zip', methods=['POST'])
def api_generate_scene_clips_zip():
    """모든 씬 클립을 생성하고 ZIP으로 반환

    씬별로 순차 처리하여 메모리/CPU 부하 최소화
    """
    import base64
    import tempfile
    import subprocess
    import shutil
    import zipfile
    import gc

    print(f"[SCENE-ZIP] === API 진입 ===")
    print(f"[SCENE-ZIP] Content-Length: {request.content_length}")

    try:
        print(f"[SCENE-ZIP] JSON 파싱 시작...")
        data = request.get_json()
        print(f"[SCENE-ZIP] JSON 파싱 완료")

        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        cuts = data.get("cuts", [])
        if not cuts:
            return jsonify({"ok": False, "error": "씬 데이터가 없습니다."}), 400

        print(f"[SCENE-ZIP] 씬 클립 ZIP 생성 시작: {len(cuts)}개 씬")

        # 각 cut의 데이터 크기 확인 (디버깅)
        for idx, cut in enumerate(cuts):
            img_size = len(cut.get("imageUrl", "")) // 1024
            audio_size = len(cut.get("audioUrl", "")) // 1024
            print(f"[SCENE-ZIP] cut[{idx}] - 이미지: {img_size}KB, 오디오: {audio_size}KB")

        with tempfile.TemporaryDirectory() as temp_dir:
            clip_paths = []

            for idx, cut in enumerate(cuts):
                scene_id = cut.get("sceneId", f"scene_{idx+1}")
                image_url = cut.get("imageUrl", "")
                audio_url = cut.get("audioUrl", "")

                if not image_url or not audio_url:
                    print(f"[SCENE-ZIP] {scene_id} 스킵 (이미지/오디오 없음)")
                    continue

                print(f"[SCENE-ZIP] {scene_id} 처리 중...")

                # 이미지 저장
                img_path = os.path.join(temp_dir, f"img_{idx}.png")
                if image_url.startswith('data:'):
                    header, encoded = image_url.split(',', 1)
                    img_data = base64.b64decode(encoded)
                    with open(img_path, 'wb') as f:
                        f.write(img_data)
                    del img_data
                else:
                    response = requests.get(image_url, timeout=60)
                    with open(img_path, 'wb') as f:
                        f.write(response.content)

                # 오디오 저장
                audio_path = os.path.join(temp_dir, f"audio_{idx}.mp3")
                if audio_url.startswith('data:'):
                    header, encoded = audio_url.split(',', 1)
                    audio_data = base64.b64decode(encoded)
                    with open(audio_path, 'wb') as f:
                        f.write(audio_data)
                    del audio_data
                else:
                    response = requests.get(audio_url, timeout=60)
                    with open(audio_path, 'wb') as f:
                        f.write(response.content)

                # 오디오 길이
                probe_cmd = [
                    'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1', audio_path
                ]
                result = subprocess.run(probe_cmd, capture_output=True, text=True)
                duration = float(result.stdout.strip()) if result.stdout.strip() else 10.0

                # MP4 생성
                clip_path = os.path.join(temp_dir, f"{scene_id}.mp4")
                ffmpeg_cmd = [
                    'ffmpeg', '-y',
                    '-threads', '1',
                    '-loop', '1',
                    '-i', img_path,
                    '-i', audio_path,
                    '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28', '-threads', '1',
                    '-c:a', 'aac', '-b:a', '128k',
                    '-r', '24',
                    '-t', str(duration),
                    '-shortest',
                    '-pix_fmt', 'yuv420p',
                    clip_path
                ]

                # 메모리 최적화: stdout DEVNULL, stderr만 PIPE (OOM 방지)
                process = subprocess.run(
                    ffmpeg_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=180
                )

                if process.returncode == 0 and os.path.exists(clip_path):
                    clip_paths.append((scene_id, clip_path))
                    print(f"[SCENE-ZIP] {scene_id} 완료: {duration:.1f}초")
                else:
                    stderr_msg = process.stderr[:200].decode('utf-8', errors='ignore') if process.stderr else '(stderr 없음)'
                    print(f"[SCENE-ZIP] {scene_id} 실패: {stderr_msg}")

                # 메모리 정리
                del process
                gc.collect()

            if not clip_paths:
                return jsonify({"ok": False, "error": "생성된 클립이 없습니다."}), 500

            # ZIP 생성
            zip_path = os.path.join(temp_dir, "drama_scenes.zip")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for scene_id, clip_path in clip_paths:
                    zf.write(clip_path, f"{scene_id}.mp4")

            # ZIP 파일 읽기
            with open(zip_path, 'rb') as f:
                zip_data = f.read()

            zip_base64 = base64.b64encode(zip_data).decode('utf-8')

            print(f"[SCENE-ZIP] ZIP 생성 완료: {len(clip_paths)}개 클립, {len(zip_data)/(1024*1024):.2f}MB")

            return jsonify({
                "ok": True,
                "clipCount": len(clip_paths),
                "zipUrl": f"data:application/zip;base64,{zip_base64}",
                "fileSize": len(zip_data),
                "fileSizeMB": round(len(zip_data) / (1024 * 1024), 2)
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== Step6: 영상 제작 API (비동기 큐 방식) =====
@app.route('/api/drama/generate-video', methods=['POST'])
def api_generate_video():
    """이미지와 오디오를 합쳐서 영상 생성 (동기/비동기 모드 지원)

    - syncMode=true: 동기식 처리 (Render 백그라운드 워커 문제 우회)
    - syncMode=false (기본): 비동기 워커 큐 사용
    """
    try:
        data = request.get_json()
        if not data:
            print(f"[DRAMA-STEP6-VIDEO] 요청 데이터 없음")
            return jsonify({"ok": False, "error": "No data received"}), 400

        # 동기 모드 여부 확인
        sync_mode = data.get("syncMode", False)
        print(f"[DRAMA-STEP6-VIDEO] === API 호출 시작 ({'동기 모드' if sync_mode else '비동기 모드'}) ===")

        # 디버깅: 요청 데이터 출력
        print(f"[DRAMA-STEP6-VIDEO] === DEBUG: 요청 데이터 ===")
        print(f"[DRAMA-STEP6-VIDEO] data keys: {list(data.keys())}")

        images = data.get("images", [])
        cuts = data.get("cuts", [])  # 씬별 이미지-오디오 매칭 배열
        audio_url = data.get("audioUrl", "")
        subtitle_data = data.get("subtitleData")
        burn_subtitle = data.get("burnSubtitle", False)
        resolution = data.get("resolution", "1920x1080")
        fps = data.get("fps", 30)
        transition = data.get("transition", "fade")

        # 디버깅: 상세 정보 출력
        print(f"[DRAMA-STEP6-VIDEO] images 개수: {len(images)}")
        print(f"[DRAMA-STEP6-VIDEO] cuts 개수: {len(cuts)}")
        print(f"[DRAMA-STEP6-VIDEO] audio_url: {audio_url[:100] if audio_url else 'N/A'}...")
        print(f"[DRAMA-STEP6-VIDEO] resolution: {resolution}, fps: {fps}")

        if cuts:
            for i, cut in enumerate(cuts[:3]):  # 처음 3개만 출력
                print(f"[DRAMA-STEP6-VIDEO] cuts[{i}]: imageUrl={cut.get('imageUrl', 'N/A')[:50]}..., audioUrl={cut.get('audioUrl', 'N/A')[:50] if cut.get('audioUrl') else 'N/A'}..., duration={cut.get('duration', 'N/A')}")

        # cuts 배열이 있으면 그것을 사용, 없으면 기존 방식
        if cuts and len(cuts) > 0:
            print(f"[DRAMA-STEP6-VIDEO] cuts 배열 사용: {len(cuts)}개 씬")
            # cuts에서 이미지와 오디오 추출
            images = [cut.get('imageUrl', '') for cut in cuts]
            # 오디오가 없으면 첫 번째 cut의 오디오 사용
            if not audio_url:
                audio_url = cuts[0].get('audioUrl', '')

        if not images:
            return jsonify({"ok": False, "error": "이미지가 없습니다."}), 400

        if not audio_url and not cuts:
            return jsonify({"ok": False, "error": "오디오가 없습니다."}), 400

        # Job ID 생성
        job_id = str(uuid.uuid4())

        # ===== 동기 모드: 직접 처리하고 결과 반환 =====
        if sync_mode:
            print(f"[DRAMA-STEP6-VIDEO] 동기식 영상 생성 시작: {job_id}")

            # Job 상태 초기화
            with video_jobs_lock:
                video_jobs[job_id] = {
                    'status': 'processing',
                    'progress': 0,
                    'message': '영상 생성 시작...',
                    'result': None,
                    'error': None,
                    'created_at': dt.now().isoformat()
                }
                save_video_jobs()

            try:
                # 직접 영상 생성 실행
                result = _generate_video_sync(
                    images=images,
                    audio_url=audio_url,
                    cuts=cuts,
                    subtitle_data=subtitle_data,
                    burn_subtitle=burn_subtitle,
                    resolution=resolution,
                    fps=fps,
                    transition=transition,
                    job_id=job_id
                )

                # 성공
                with video_jobs_lock:
                    if job_id in video_jobs:
                        video_jobs[job_id]['status'] = 'completed'
                        video_jobs[job_id]['progress'] = 100
                        video_jobs[job_id]['result'] = result
                        save_video_jobs()

                print(f"[DRAMA-STEP6-VIDEO] 동기식 영상 생성 완료: {job_id}")
                return jsonify({
                    "ok": True,
                    "jobId": job_id,
                    "status": "completed",
                    "progress": 100,
                    "videoUrl": result.get('videoUrl'),
                    "videoPath": result.get('videoFileUrl'),
                    "duration": result.get('duration'),
                    "fileSize": result.get('fileSize'),
                    "message": "영상 생성 완료"
                })

            except Exception as e:
                import traceback
                error_msg = str(e)
                print(f"[DRAMA-STEP6-VIDEO] 동기식 영상 생성 실패: {error_msg}")
                traceback.print_exc()

                with video_jobs_lock:
                    if job_id in video_jobs:
                        video_jobs[job_id]['status'] = 'failed'
                        video_jobs[job_id]['error'] = error_msg
                        save_video_jobs()

                return jsonify({
                    "ok": False,
                    "jobId": job_id,
                    "status": "failed",
                    "error": error_msg
                })

        # ===== 비동기 모드: 워커 큐 사용 =====
        print(f"[DRAMA-STEP6-VIDEO] 비동기 영상 생성 작업 등록: {job_id}, 이미지: {len(images)}개, cuts: {len(cuts)}개")

        # Job 상태 초기화 - pending 상태로 시작
        with video_jobs_lock:
            video_jobs[job_id] = {
                'status': 'pending',
                'progress': 0,
                'message': '작업 대기 중...',
                'result': None,
                'error': None,
                'created_at': dt.now().isoformat()
            }
            save_video_jobs()

        # 작업을 큐에 추가 (백그라운드 워커가 처리)
        job_data = {
            'job_id': job_id,
            'images': images,
            'audio_url': audio_url,
            'cuts': cuts,
            'subtitle_data': subtitle_data,
            'burn_subtitle': burn_subtitle,
            'resolution': resolution,
            'fps': fps,
            'transition': transition
        }
        video_job_queue.put(job_data)

        print(f"[DRAMA-STEP6-VIDEO] 작업 큐에 추가됨: {job_id}, 큐 크기: {video_job_queue.qsize()}")

        # 즉시 응답 반환 (프론트엔드에서 폴링으로 상태 확인)
        return jsonify({
            "ok": True,
            "jobId": job_id,
            "status": "pending",
            "progress": 0,
            "workerAlive": video_worker_thread.is_alive(),
            "message": "영상 생성 작업이 시작되었습니다. 상태를 확인해주세요."
        })

    except Exception as e:
        import traceback
        print(f"[DRAMA-STEP6-VIDEO][ERROR] {str(e)}")
        print(f"[DRAMA-STEP6-VIDEO][TRACEBACK]")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Step6: 영상 제작 API (SSE 스트리밍) =====
@app.route('/api/drama/generate-video-stream', methods=['POST'])
def api_generate_video_stream():
    """영상 생성 - SSE 스트리밍 방식 (Render 타임아웃 우회)

    연결을 유지하면서 진행률을 스트리밍합니다.
    클라이언트는 fetch API의 ReadableStream으로 응답을 읽습니다.
    """
    print(f"[DRAMA-VIDEO-STREAM] === SSE 스트리밍 API 호출 ===")

    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        images = data.get("images", [])
        cuts = data.get("cuts", [])
        audio_url = data.get("audioUrl", "")
        subtitle_data = data.get("subtitleData")
        burn_subtitle = data.get("burnSubtitle", False)
        resolution = data.get("resolution", "1920x1080")
        fps = data.get("fps", 30)

        print(f"[DRAMA-VIDEO-STREAM] cuts: {len(cuts)}개, images: {len(images)}개")

        # cuts 배열 처리
        if cuts and len(cuts) > 0:
            images = [cut.get('imageUrl', '') for cut in cuts]
            if not audio_url:
                audio_url = cuts[0].get('audioUrl', '')

        if not images:
            return jsonify({"ok": False, "error": "이미지가 없습니다."}), 400

        job_id = str(uuid.uuid4())

        def generate():
            """SSE 스트리밍 제너레이터"""
            try:
                # 시작 이벤트
                yield f"data: {json.dumps({'event': 'start', 'jobId': job_id, 'progress': 0, 'message': '영상 생성 시작...'})}\n\n"

                # 진행률 업데이트 함수 (yield를 통해 클라이언트에 전송)
                progress_updates = []

                def update_progress(progress, message=""):
                    progress_updates.append({'progress': progress, 'message': message})

                # Job 상태 저장
                with video_jobs_lock:
                    video_jobs[job_id] = {
                        'status': 'processing',
                        'progress': 0,
                        'message': '영상 생성 시작...',
                        'result': None,
                        'error': None,
                        'created_at': dt.now().isoformat()
                    }
                    save_video_jobs()

                yield f"data: {json.dumps({'event': 'progress', 'progress': 5, 'message': '의존성 확인 중...'})}\n\n"

                # 영상 생성 실행 (별도 스레드에서)
                result_holder = {'result': None, 'error': None}

                def run_video_generation():
                    try:
                        result = _generate_video_sync(
                            images=images,
                            audio_url=audio_url,
                            cuts=cuts,
                            subtitle_data=subtitle_data,
                            burn_subtitle=burn_subtitle,
                            resolution=resolution,
                            fps=fps,
                            transition='fade',
                            job_id=job_id
                        )
                        result_holder['result'] = result
                    except Exception as e:
                        result_holder['error'] = str(e)
                        import traceback
                        traceback.print_exc()

                # 스레드 시작
                import time
                gen_thread = threading.Thread(target=run_video_generation)
                gen_thread.start()

                # 진행률 모니터링 (3초마다 확인, 최대 10분)
                max_wait = 600  # 10분
                elapsed = 0
                last_progress = 0

                while gen_thread.is_alive() and elapsed < max_wait:
                    time.sleep(3)
                    elapsed += 3

                    # job 상태에서 진행률 읽기
                    with video_jobs_lock:
                        if job_id in video_jobs:
                            current_progress = video_jobs[job_id].get('progress', 0)
                            current_message = video_jobs[job_id].get('message', '')

                            if current_progress > last_progress:
                                last_progress = current_progress
                                yield f"data: {json.dumps({'event': 'progress', 'progress': current_progress, 'message': current_message})}\n\n"

                    # 하트비트 (연결 유지)
                    yield f": heartbeat\n\n"

                # 스레드 종료 대기
                gen_thread.join(timeout=30)

                if result_holder['error']:
                    # 실패
                    with video_jobs_lock:
                        if job_id in video_jobs:
                            video_jobs[job_id]['status'] = 'failed'
                            video_jobs[job_id]['error'] = result_holder['error']
                            save_video_jobs()

                    yield f"data: {json.dumps({'event': 'error', 'error': result_holder['error']})}\n\n"

                elif result_holder['result']:
                    # 성공
                    result = result_holder['result']
                    with video_jobs_lock:
                        if job_id in video_jobs:
                            video_jobs[job_id]['status'] = 'completed'
                            video_jobs[job_id]['progress'] = 100
                            video_jobs[job_id]['result'] = result
                            save_video_jobs()

                    yield f"data: {json.dumps({'event': 'complete', 'progress': 100, 'videoUrl': result.get('videoUrl'), 'videoPath': result.get('videoFileUrl'), 'duration': result.get('duration'), 'fileSize': result.get('fileSize')})}\n\n"

                else:
                    # 타임아웃
                    yield f"data: {json.dumps({'event': 'error', 'error': '영상 생성 시간 초과 (10분)'})}\n\n"

            except Exception as e:
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"

        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'  # nginx 버퍼링 비활성화
            }
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 작업 상태 조회 API =====
@app.route('/api/drama/video-status/<job_id>', methods=['GET'])
def api_video_status(job_id):
    """영상 생성 작업 상태 조회"""
    with video_jobs_lock:
        # 메모리에 없으면 파일에서 다시 로드 시도 (다중 인스턴스/재시작 대응)
        if job_id not in video_jobs:
            print(f"[VIDEO-STATUS] job_id {job_id} 메모리에 없음, 파일에서 로드 시도...")
            try:
                if os.path.exists(VIDEO_JOBS_FILE):
                    with open(VIDEO_JOBS_FILE, 'r', encoding='utf-8') as f:
                        loaded_jobs = json.load(f)
                        video_jobs.update(loaded_jobs)
                        print(f"[VIDEO-STATUS] 파일에서 {len(loaded_jobs)}개 작업 로드됨")
            except Exception as e:
                print(f"[VIDEO-STATUS] 파일 로드 실패: {e}")

        if job_id not in video_jobs:
            print(f"[VIDEO-STATUS] job_id {job_id} 여전히 찾을 수 없음")
            return jsonify({"ok": False, "error": "작업을 찾을 수 없습니다."}), 404

        job = video_jobs[job_id]

        # pending 상태가 5분 이상 지속되면 실패 처리
        if job['status'] == 'pending':
            created_at = dt.fromisoformat(job['created_at'])
            elapsed = (dt.now() - created_at).total_seconds()
            if elapsed > 300:  # 5분 = 300초
                job['status'] = 'failed'
                job['error'] = f'작업 처리 시간 초과 (워커 상태 확인 필요). 경과 시간: {int(elapsed)}초'
                save_video_jobs()
                print(f"[VIDEO-STATUS] 작업 {job_id} pending 타임아웃으로 실패 처리")

        response = {
            "ok": True,
            "jobId": job_id,
            "status": job['status'],  # pending, processing, completed, failed
            "progress": job['progress'],
            "message": job.get('message', ''),
            "workerAlive": True  # 동기식으로 변경됨 - 항상 True
        }

        if job['status'] == 'completed':
            result = job['result']
            # 프론트엔드 호환성을 위해 result 내용을 최상위로 펼침
            if result:
                response['videoUrl'] = result.get('videoUrl')
                response['videoFileUrl'] = result.get('videoFileUrl')
                response['duration'] = result.get('duration')
                response['fileSize'] = result.get('fileSize')
                response['fileSizeMB'] = result.get('fileSizeMB')
            response['result'] = result  # 기존 호환성 유지
        elif job['status'] == 'failed':
            response['error'] = job['error']

        return jsonify(response)


# ===== 워커 상태 디버깅 API =====
@app.route('/api/drama/worker-status', methods=['GET'])
def api_worker_status():
    """영상 워커 상태 확인 (디버깅용) - 동기식 모드"""
    with video_jobs_lock:
        pending_jobs = [jid for jid, j in video_jobs.items() if j['status'] == 'pending']
        processing_jobs = [jid for jid, j in video_jobs.items() if j['status'] == 'processing']

    return jsonify({
        "ok": True,
        "workerAlive": True,  # 동기식 모드 - 항상 True
        "mode": "synchronous",  # 동기식 모드 표시
        "queueSize": 0,  # 동기식이므로 큐 없음
        "pendingJobs": pending_jobs,
        "processingJobs": processing_jobs,
        "totalJobs": len(video_jobs)
    })


# ===== Step7: 유튜브 업로드 API =====

@app.route('/api/drama/generate-metadata', methods=['POST'])
def generate_metadata():
    """대본 기반 YouTube 메타데이터 자동 생성"""
    try:
        data = request.get_json()
        script = data.get('script', '')

        if not script.strip():
            return jsonify({"ok": False, "error": "대본이 비어있습니다."})

        # OpenAI API 호출하여 메타데이터 생성
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            return jsonify({"ok": False, "error": "OpenAI API 키가 설정되지 않았습니다."})

        import requests as req

        prompt = f"""다음 드라마 대본을 분석하여 YouTube 업로드용 메타데이터를 생성해주세요.

대본:
{script[:3000]}

다음 형식으로 응답해주세요:
제목: (50자 이내의 흥미로운 제목, 시청자의 관심을 끌 수 있도록)
설명: (200자 이내의 영상 설명, 줄거리 요약과 해시태그 포함)
태그: (쉼표로 구분된 10개 이내의 관련 태그)

응답 예시:
제목: 그녀가 떠난 이유 | 감동 단편 드라마
설명: 10년을 함께한 연인이 갑자기 떠났다. 남겨진 그는 그녀의 마지막 편지를 발견하고...

#단편드라마 #감동 #사랑 #이별
태그: 단편드라마, 감동, 사랑, 이별, 로맨스, AI드라마, 한국드라마, 감성, 눈물, 스토리"""

        response = req.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {openai_api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gpt-4o',
                'messages': [
                    {'role': 'system', 'content': 'YouTube 영상 메타데이터 전문가입니다. 드라마 대본을 분석하여 시청자의 관심을 끌 수 있는 제목, 설명, 태그를 생성합니다.'},
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 500,
                'temperature': 0.7
            },
            timeout=30
        )

        if response.status_code != 200:
            return jsonify({"ok": False, "error": f"OpenAI API 오류: {response.text}"})

        result = response.json()
        content = result['choices'][0]['message']['content']

        # 응답 파싱
        title = ''
        description = ''
        tags = ''

        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('제목:'):
                title = line[3:].strip()
            elif line.startswith('설명:'):
                description = line[3:].strip()
            elif line.startswith('태그:'):
                tags = line[3:].strip()
            elif description and not line.startswith('태그:') and not title:
                # 설명이 여러 줄일 경우
                description += '\n' + line

        # 설명에 해시태그 라인이 있으면 합치기
        desc_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith('#') or (description and line and not line.startswith('태그:')):
                if not line.startswith('제목:') and not line.startswith('설명:') and not line.startswith('태그:'):
                    if '#' in line:
                        desc_lines.append(line)

        if desc_lines:
            description = description + '\n\n' + '\n'.join(desc_lines)

        print(f"[GENERATE-METADATA] 생성 완료 - 제목: {title[:30]}...")
        return jsonify({
            "ok": True,
            "metadata": {
                "title": title,
                "description": description,
                "tags": tags
            }
        })

    except Exception as e:
        print(f"[GENERATE-METADATA][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)})


@app.route('/api/drama/generate-thumbnail', methods=['POST'])
def generate_thumbnail():
    """유튜브 썸네일 자동 생성 (인물 + 강렬한 문구)"""
    try:
        data = request.get_json()
        script = data.get('script', '')
        title = data.get('title', '')
        provider = data.get('provider', 'gemini')  # gemini, dalle, flux

        if not script.strip():
            return jsonify({"ok": False, "error": "대본이 비어있습니다."})

        print(f"[THUMBNAIL] 썸네일 생성 시작 - 제공자: {provider}")

        # OpenAI API 키 확인
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            return jsonify({"ok": False, "error": "OpenAI API 키가 설정되지 않았습니다."})

        import requests as req

        # 1. GPT로 썸네일 콘셉트 생성 (주인공 + 클릭 유도 문구)
        concept_prompt = f"""다음 드라마 대본을 분석하여 유튜브 썸네일을 만들어주세요.

🎯 목표: 시청자가 클릭하고 싶게 만드는 썸네일

⚠️ 중요: 캐릭터는 반드시 스틱맨(Stickman)으로만 표현하세요!
- 실사 인물(할아버지, 할머니, 노인 등) 절대 사용 금지!
- 스틱맨: 하얀 막대 인간, 둥근 머리, 검은 점 눈, 작은 입
- 배경은 애니메이션 스타일 (지브리풍, 따뜻한 색감)

대본:
{script[:3000]}

제목: {title}

【필수 형식】으로 응답해주세요:

1. 주인공 정보: (대본의 주인공 상황/감정 - 스틱맨으로 표현됨)
2. 이미지 프롬프트: (영어로, 아래 조건 포함)
   - 스틱맨 캐릭터: "Simple white stickman with round head, black dot eyes, small mouth"
   - 감정 표현: 스틱맨의 표정과 포즈로 표현
   - 배경: 애니메이션 스타일 (Ghibli-inspired, warm colors)
   - 구도: 스틱맨 + 배경 대비 스타일
3. 썸네일 텍스트: (3~4줄로 구성, 각 줄 \\n으로 구분)
   - 1줄: 훅 (충격적인 숫자/상황)
   - 2줄: 핵심 인물/사건
   - 3줄: 감정 강조 (강조색으로 표시될 부분)
   - 4줄: 궁금증 유발
4. 강조 줄 번호: (3줄 중 강조할 줄 번호, 예: 3)

【예시】
1. 주인공 정보: 외로운 노인, 교회를 혼자 지키다 희망을 찾는 순간 (스틱맨으로 표현)
2. 이미지 프롬프트: Simple white stickman with round head, black dot eyes, small sad mouth, thin eyebrows, standing alone in detailed anime-style church interior, Ghibli-inspired warm lighting through stained glass windows, contrast collage style, emotional atmosphere
3. 썸네일 텍스트: 1년간 혼자 예배드리던\\n작은 교회\\n문 닫으려던 그날\\n한 청년이 나타났습니다
4. 강조 줄 번호: 3"""

        response = req.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {openai_api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gpt-4o',
                'messages': [
                    {'role': 'system', 'content': '유튜브 썸네일 전문가입니다. 클릭률을 높이는 썸네일 콘셉트를 생성합니다.'},
                    {'role': 'user', 'content': concept_prompt}
                ],
                'max_tokens': 500,
                'temperature': 0.8
            },
            timeout=30
        )

        if response.status_code != 200:
            return jsonify({"ok": False, "error": f"콘셉트 생성 실패: {response.text}"})

        concept_result = response.json()
        concept_content = concept_result['choices'][0]['message']['content']
        print(f"[THUMBNAIL] 콘셉트 생성 완료:\n{concept_content}")

        # 콘셉트 파싱
        image_prompt = ""
        thumbnail_text = title[:30] if title else "드라마"
        highlight_line = 2  # 기본값: 3번째 줄 강조 (0-indexed)

        lines = concept_content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if '이미지 프롬프트:' in line or 'Image Prompt:' in line.lower():
                image_prompt = line.split(':', 1)[1].strip()
            elif '썸네일 텍스트:' in line:
                thumbnail_text = line.split(':', 1)[1].strip()
            elif '강조 줄 번호:' in line:
                try:
                    highlight_line = int(line.split(':', 1)[1].strip()) - 1  # 0-indexed
                except:
                    highlight_line = 2

        if not image_prompt:
            # 파싱 실패 시 기본 프롬프트 생성
            image_prompt = f"Dramatic close-up portrait of Korean drama character, emotional expression, cinematic lighting, YouTube thumbnail style, high quality"

        # 썸네일 최적화 프롬프트 추가
        image_prompt += ", 1280x720 resolution, YouTube thumbnail, eye-catching, professional"

        print(f"[THUMBNAIL] 이미지 프롬프트: {image_prompt}")
        print(f"[THUMBNAIL] 텍스트: {thumbnail_text}")

        # 2. 이미지 생성
        image_url = None

        if provider == 'gemini':
            # Gemini 이미지 생성 (OpenRouter API 사용)
            openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
            if not openrouter_api_key:
                return jsonify({"ok": False, "error": "OpenRouter API 키가 설정되지 않았습니다. 환경변수 OPENROUTER_API_KEY를 설정해주세요."})

            import time
            import base64

            # OpenRouter API 호출 설정
            headers = {
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://drama-generator.app",
                "X-Title": "Drama Thumbnail Generator"
            }

            # 스틱맨 스타일 강제 적용 (항상!)
            # 절대 사실적인 인물이나 할아버지/할머니 등장 금지
            enhanced_prompt = f"""CRITICAL REQUIREMENTS:
1. 16:9 WIDESCREEN aspect ratio
2. ONLY simple white stickman character - round head, two black dot eyes, small mouth, thin eyebrows, black outline body
3. ABSOLUTELY NO realistic humans, NO grandpa, NO grandma, NO elderly people, NO anime characters with detailed faces
4. Detailed anime/Ghibli-style background ONLY
5. The stickman should be the ONLY character in the scene

Original request: {image_prompt}

FINAL STYLE: Detailed anime background (Ghibli-inspired, warm colors) + Simple white stickman character. Eye-catching YouTube thumbnail composition. The background is detailed and beautiful, but the character MUST be a simple stickman, NOT a realistic person."""

            payload = {
                "model": "google/gemini-2.5-flash-image-preview",
                "modalities": ["text", "image"],
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": enhanced_prompt
                            }
                        ]
                    }
                ]
            }

            # 재시도 로직
            max_retries = 3
            retry_delay = 5

            response = None
            last_error = None

            for attempt in range(max_retries):
                try:
                    response = req.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=90
                    )

                    if response.status_code == 200:
                        break
                    elif response.status_code in [429, 502, 503, 504]:
                        last_error = response.text
                        print(f"[THUMBNAIL][RETRY] OpenRouter 오류 ({response.status_code}) (시도 {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        break
                except Exception as e:
                    last_error = str(e)
                    print(f"[THUMBNAIL][RETRY] 오류: {e} (시도 {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    continue

            if response is None or response.status_code != 200:
                error_text = last_error or (response.text if response else "알 수 없는 오류")
                return jsonify({"ok": False, "error": f"Gemini API 오류: {error_text[:200]}"})

            result = response.json()
            print(f"[THUMBNAIL][DEBUG] OpenRouter 응답: {json.dumps(result, ensure_ascii=False)[:500]}")

            # 응답에서 이미지 추출
            base64_image_data = None
            try:
                choices = result.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})

                    # images 배열 확인
                    images = message.get("images", [])
                    if images:
                        for img in images:
                            if isinstance(img, str):
                                # base64 문자열 또는 data URL
                                if img.startswith("data:"):
                                    base64_image_data = img.split(",", 1)[1] if "," in img else img
                                else:
                                    base64_image_data = img
                                break
                            elif isinstance(img, dict):
                                # dict 형태의 이미지 데이터 처리
                                if img.get("type") == "image_url":
                                    url = img.get("image_url", {}).get("url", "")
                                    if url.startswith("data:"):
                                        base64_image_data = url.split(",", 1)[1] if "," in url else url
                                elif "url" in img:
                                    url = img.get("url", "")
                                    if url.startswith("data:"):
                                        base64_image_data = url.split(",", 1)[1] if "," in url else url
                                elif "data" in img:
                                    base64_image_data = img.get("data")
                                elif "b64_json" in img:
                                    base64_image_data = img.get("b64_json")
                                if base64_image_data:
                                    break

                    # content 배열 확인
                    if not base64_image_data:
                        content = message.get("content", [])
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict):
                                    item_type = item.get("type", "")

                                    if item_type == "image_url":
                                        url = item.get("image_url", {}).get("url", "")
                                        if url.startswith("data:"):
                                            base64_image_data = url.split(",", 1)[1] if "," in url else url
                                            break

                                    elif item_type == "image":
                                        image_data = item.get("image", {})
                                        if isinstance(image_data, dict):
                                            base64_image_data = image_data.get("data") or image_data.get("base64") or image_data.get("b64_json")
                                        elif isinstance(image_data, str):
                                            base64_image_data = image_data
                                        if base64_image_data:
                                            break

                                    elif "inline_data" in item:
                                        inline = item.get("inline_data", {})
                                        base64_image_data = inline.get("data", "")
                                        if base64_image_data:
                                            break

                    # base64 데이터가 있으면 파일로 저장
                    if base64_image_data:
                        image_bytes = base64.b64decode(base64_image_data)

                        static_dir = os.path.join(os.path.dirname(__file__), 'static', 'thumbnails')
                        os.makedirs(static_dir, exist_ok=True)

                        timestamp = dt.now().strftime("%Y%m%d_%H%M%S_%f")
                        filename = f"thumbnail_{timestamp}.png"
                        filepath = os.path.join(static_dir, filename)

                        with open(filepath, 'wb') as f:
                            f.write(image_bytes)

                        image_url = f"/static/thumbnails/{filename}"
                        print(f"[THUMBNAIL] 이미지 저장 완료: {image_url}")

            except Exception as e:
                print(f"[THUMBNAIL][ERROR] 이미지 추출 오류: {e}")
                import traceback
                traceback.print_exc()

        elif provider == 'dalle':
            # DALL-E 3 이미지 생성
            dalle_response = req.post(
                'https://api.openai.com/v1/images/generations',
                headers={
                    'Authorization': f'Bearer {openai_api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'dall-e-3',
                    'prompt': image_prompt,
                    'n': 1,
                    'size': '1792x1024',  # 가로형
                    'quality': 'hd'
                },
                timeout=60
            )

            if dalle_response.status_code == 200:
                dalle_result = dalle_response.json()
                temp_image_url = dalle_result['data'][0]['url']

                # 이미지 다운로드
                img_response = req.get(temp_image_url, timeout=30)
                if img_response.status_code == 200:
                    static_dir = os.path.join(os.path.dirname(__file__), 'static', 'thumbnails')
                    os.makedirs(static_dir, exist_ok=True)

                    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"thumbnail_{timestamp}.png"
                    filepath = os.path.join(static_dir, filename)

                    with open(filepath, 'wb') as f:
                        f.write(img_response.content)

                    image_url = f"/static/thumbnails/{filename}"

        if not image_url:
            return jsonify({"ok": False, "error": "이미지 생성 실패"})

        # 3. PIL로 텍스트 오버레이 (강조색 포함)
        try:
            from PIL import Image, ImageDraw, ImageFont
            from io import BytesIO
            import os as os_module

            # 이미지 로드
            static_dir = os.path.dirname(__file__)
            img_path = os.path.join(static_dir, image_url.lstrip('/'))
            img = Image.open(img_path)

            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            width, height = img.size
            draw = ImageDraw.Draw(img)

            # 폰트 로드
            font_size = int(height * 0.08)  # 이미지 높이의 8%
            font = None
            font_paths = [
                os.path.join(static_dir, 'fonts', 'Pretendard-Bold.ttf'),
                os.path.join(static_dir, 'fonts', 'Pretendard-SemiBold.ttf'),
                os.path.join(static_dir, 'fonts', 'NanumSquareRoundB.ttf'),
                os.path.join(static_dir, 'fonts', 'NanumGothicBold.ttf'),
                "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            ]
            for fp in font_paths:
                if os.path.exists(fp):
                    try:
                        font = ImageFont.truetype(fp, font_size)
                        print(f"[THUMBNAIL] 폰트 로드: {fp}")
                        break
                    except:
                        continue
            if not font:
                font = ImageFont.load_default()
                print("[THUMBNAIL] 기본 폰트 사용 (한글 미지원 가능)")

            # 텍스트 줄 분리
            text_lines = thumbnail_text.replace('\\n', '\n').split('\n')

            # 색상 설정
            normal_color = (255, 255, 255)  # 흰색
            highlight_color = (255, 215, 0)  # 노란색 (골드)
            outline_color = (0, 0, 0)  # 검정 외곽선

            # 텍스트 위치 (왼쪽 정렬, 상단 10%)
            x_margin = int(width * 0.05)
            y_start = int(height * 0.08)
            line_height = int(font_size * 1.3)

            for i, line_text in enumerate(text_lines):
                y = y_start + (i * line_height)
                color = highlight_color if i == highlight_line else normal_color

                # 외곽선 그리기 (검정)
                for dx in [-3, -2, -1, 0, 1, 2, 3]:
                    for dy in [-3, -2, -1, 0, 1, 2, 3]:
                        draw.text((x_margin + dx, y + dy), line_text, font=font, fill=outline_color)

                # 메인 텍스트
                draw.text((x_margin, y), line_text, font=font, fill=color)

            # 저장
            img.save(img_path)
            print(f"[THUMBNAIL] 텍스트 오버레이 완료: {image_url}")

        except Exception as overlay_error:
            print(f"[THUMBNAIL] 텍스트 오버레이 실패 (무시): {overlay_error}")

        print(f"[THUMBNAIL] 썸네일 생성 완료: {image_url}")

        return jsonify({
            "ok": True,
            "thumbnailUrl": image_url,
            "thumbnailText": thumbnail_text,
            "textLines": thumbnail_text.replace('\\n', '\n').split('\n'),
            "highlightLine": highlight_line,
            "imagePrompt": image_prompt
        })

    except Exception as e:
        print(f"[THUMBNAIL][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)})


# YouTube OAuth 인증 상태 저장 (DB 기반 - Render 환경에서 안정적)
OAUTH_STATE_FILE = 'data/oauth_state.json'  # 폴백용

def save_oauth_state(state_data):
    """OAuth 상태를 데이터베이스에 저장 (파일 폴백)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        state_json = json.dumps(state_data, ensure_ascii=False)

        if USE_POSTGRES:
            # PostgreSQL: UPSERT
            cursor.execute('''
                INSERT INTO youtube_tokens (user_id, scopes, updated_at)
                VALUES ('oauth_state', %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET
                    scopes = EXCLUDED.scopes,
                    updated_at = CURRENT_TIMESTAMP
            ''', (state_json,))
        else:
            # SQLite: INSERT OR REPLACE
            cursor.execute('''
                INSERT OR REPLACE INTO youtube_tokens (user_id, scopes, updated_at)
                VALUES ('oauth_state', ?, datetime('now'))
            ''', (state_json,))

        conn.commit()
        conn.close()
        print(f"[OAUTH-STATE] DB 저장 완료: {list(state_data.keys())}")
    except Exception as e:
        print(f"[OAUTH-STATE] DB 저장 실패, 파일로 폴백: {e}")
        # 파일 폴백
        try:
            os.makedirs('data', exist_ok=True)
            with open(OAUTH_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False)
            print(f"[OAUTH-STATE] 파일 저장 완료")
        except Exception as file_error:
            print(f"[OAUTH-STATE] 파일 저장도 실패: {file_error}")

def load_oauth_state():
    """OAuth 상태를 데이터베이스에서 로드 (파일 폴백)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute("SELECT scopes FROM youtube_tokens WHERE user_id = 'oauth_state'")
        else:
            cursor.execute("SELECT scopes FROM youtube_tokens WHERE user_id = 'oauth_state'")

        row = cursor.fetchone()
        conn.close()

        if row:
            state_json = row[0] if not USE_POSTGRES else row['scopes']
            if state_json:
                state_data = json.loads(state_json)
                print(f"[OAUTH-STATE] DB 로드 완료: {list(state_data.keys())}")
                return state_data
    except Exception as e:
        print(f"[OAUTH-STATE] DB 로드 실패, 파일로 폴백: {e}")

    # 파일 폴백
    try:
        if os.path.exists(OAUTH_STATE_FILE):
            with open(OAUTH_STATE_FILE, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            print(f"[OAUTH-STATE] 파일 로드 완료: {list(state_data.keys())}")
            return state_data
    except Exception as e:
        print(f"[OAUTH-STATE] 파일 로드도 실패: {e}")
    return {}

@app.route('/api/drama/youtube-auth', methods=['POST'])
def youtube_auth():
    """YouTube OAuth 인증 시작"""
    try:
        from google_auth_oauthlib.flow import Flow
        from google.oauth2.credentials import Credentials
        import json as json_module

        # 환경 변수에서 OAuth 클라이언트 정보 가져오기
        # YOUTUBE_CLIENT_ID가 없으면 GOOGLE_CLIENT_ID를 사용 (같은 Google Cloud Project의 OAuth 클라이언트)
        client_id = os.getenv('YOUTUBE_CLIENT_ID') or os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('YOUTUBE_CLIENT_SECRET') or os.getenv('GOOGLE_CLIENT_SECRET')

        # Render 환경에서는 반드시 HTTPS URL 사용
        redirect_uri = os.getenv('YOUTUBE_REDIRECT_URI')
        if not redirect_uri:
            # 요청 URL에서 자동 추출
            redirect_uri = request.url_root.rstrip('/') + '/api/drama/youtube-callback'
            # HTTP를 HTTPS로 변환 (Render는 HTTPS 사용)
            if redirect_uri.startswith('http://') and 'onrender.com' in redirect_uri:
                redirect_uri = redirect_uri.replace('http://', 'https://')

        print(f"[YOUTUBE-AUTH] Redirect URI: {redirect_uri}")

        if not client_id or not client_secret:
            return jsonify({
                "success": False,
                "error": "YouTube API 인증 정보가 설정되지 않았습니다. YOUTUBE_CLIENT_ID/GOOGLE_CLIENT_ID와 YOUTUBE_CLIENT_SECRET/GOOGLE_CLIENT_SECRET 환경 변수를 설정해주세요."
            })

        # 이미 인증된 토큰이 있는지 확인 (데이터베이스에서)
        token_data = load_youtube_token_from_db()
        if token_data and token_data.get('refresh_token'):
            try:
                from google.auth.transport.requests import Request
                credentials = Credentials.from_authorized_user_info(token_data)
                if credentials:
                    # 토큰이 만료되었으면 갱신 시도
                    if credentials.expired and credentials.refresh_token:
                        try:
                            credentials.refresh(Request())
                            # 갱신된 토큰 저장
                            token_data['token'] = credentials.token
                            save_youtube_token_to_db(token_data)
                            print(f"[YOUTUBE-AUTH] 토큰 갱신 성공")
                        except Exception as refresh_error:
                            print(f"[YOUTUBE-AUTH] 토큰 갱신 실패: {refresh_error}")
                            # 갱신 실패 시 새로운 인증 필요
                            pass

                    # 유효한 토큰이 있으면 성공 반환
                    if credentials.valid or (credentials.refresh_token and not credentials.expired):
                        return jsonify({"success": True, "message": "이미 인증되어 있습니다."})
            except Exception as e:
                print(f"[YOUTUBE-AUTH] 기존 토큰 검증 실패: {e}")

        # OAuth 플로우 생성
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=[
                'https://www.googleapis.com/auth/youtube.upload',
                'https://www.googleapis.com/auth/youtube.readonly'
            ],
            redirect_uri=redirect_uri
        )

        # prompt='consent'는 매번 동의 화면을 강제로 표시하므로 제거
        # access_type='offline'만으로 refresh_token을 받을 수 있음
        # 단, 이미 권한을 부여한 사용자는 자동으로 승인됨
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )

        # 상태를 파일에 저장 (멀티 워커 대응)
        save_oauth_state({
            'state': state,
            'redirect_uri': redirect_uri,
            'client_id': client_id,
            'client_secret': client_secret
        })

        return jsonify({
            "success": False,
            "auth_url": auth_url,
            "message": "인증 URL로 이동하여 권한을 승인해주세요."
        })

    except ImportError:
        return jsonify({
            "success": False,
            "error": "Google 인증 라이브러리가 설치되지 않았습니다. pip install google-auth-oauthlib google-api-python-client를 실행해주세요."
        })
    except Exception as e:
        print(f"[YOUTUBE-AUTH][ERROR] {str(e)}")
        return jsonify({"success": False, "error": str(e)})


@app.route('/api/drama/youtube-callback')
def youtube_callback():
    """YouTube OAuth 콜백 처리"""
    try:
        from google_auth_oauthlib.flow import Flow

        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        error_description = request.args.get('error_description', '')

        print(f"[YOUTUBE-CALLBACK] 콜백 수신 - code: {bool(code)}, state: {state[:20] if state else 'None'}...")
        print(f"[YOUTUBE-CALLBACK] Error: {error}, Description: {error_description}")

        if error:
            # 사용자 친화적인 에러 페이지 반환
            return f"""
            <!DOCTYPE html>
            <html>
            <head><title>YouTube 연결 오류</title>
            <style>body{{font-family:Arial;padding:50px;text-align:center}}.error{{background:#ffebee;padding:20px;border-radius:8px;margin:20px auto;max-width:500px;color:#c62828}}.back-btn{{margin-top:20px;padding:10px 20px;background:#1a73e8;color:white;border:none;border-radius:4px;cursor:pointer;text-decoration:none;display:inline-block}}</style>
            </head>
            <body>
                <h1>⚠️ YouTube 연결 오류</h1>
                <div class="error">
                    <p><strong>오류:</strong> {error}</p>
                    <p>{error_description}</p>
                </div>
                <a href="/image" class="back-btn">← Image Lab으로 돌아가기</a>
            </body>
            </html>
            """, 400

        if not code:
            return "인증 코드가 없습니다.", 400

        # 저장된 상태 로드
        oauth_state = load_oauth_state()
        print(f"[YOUTUBE-CALLBACK] 저장된 OAuth 상태: {list(oauth_state.keys()) if oauth_state else 'None'}")
        if not oauth_state:
            return """
            <!DOCTYPE html>
            <html>
            <head><title>YouTube 연결 오류</title>
            <style>body{font-family:Arial;padding:50px;text-align:center}.error{background:#ffebee;padding:20px;border-radius:8px;margin:20px auto;max-width:500px}.back-btn{margin-top:20px;padding:10px 20px;background:#1a73e8;color:white;border:none;border-radius:4px;cursor:pointer;text-decoration:none;display:inline-block}</style>
            </head>
            <body>
                <h1>⚠️ 인증 세션 만료</h1>
                <div class="error">
                    <p>인증 세션이 만료되었습니다.</p>
                    <p>다시 시도해주세요.</p>
                </div>
                <a href="/image" class="back-btn">← 다시 시도</a>
            </body>
            </html>
            """, 400

        # Flow 재생성
        client_config = {
            "web": {
                "client_id": oauth_state['client_id'],
                "client_secret": oauth_state['client_secret'],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [oauth_state['redirect_uri']]
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=[
                'https://www.googleapis.com/auth/youtube.upload',
                'https://www.googleapis.com/auth/youtube.readonly'
            ],
            redirect_uri=oauth_state['redirect_uri']
        )

        flow.fetch_token(code=code)
        credentials = flow.credentials

        # 토큰 데이터 준비
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': list(credentials.scopes) if credentials.scopes else []
        }

        # 채널 정보 조회
        channel_id = None
        channel_info = None
        try:
            from googleapiclient.discovery import build
            youtube = build('youtube', 'v3', credentials=credentials)
            channels_response = youtube.channels().list(
                part='snippet',
                mine=True
            ).execute()

            items = channels_response.get('items', [])
            if items:
                channel = items[0]
                channel_id = channel['id']
                channel_info = {
                    'title': channel['snippet']['title'],
                    'thumbnail': channel['snippet']['thumbnails'].get('default', {}).get('url', '')
                }
                print(f"[YOUTUBE-CALLBACK] 채널 정보: {channel_id} - {channel_info['title']}")
        except Exception as channel_error:
            print(f"[YOUTUBE-CALLBACK] 채널 정보 조회 실패 (토큰은 저장): {channel_error}")

        # 채널별로 토큰 저장
        save_youtube_token_to_db(token_data, channel_id=channel_id, channel_info=channel_info)

        print(f"[YOUTUBE-CALLBACK] 인증 완료, /image 페이지로 리다이렉트")
        # Image Lab 페이지로 리다이렉트 (인증 완료)
        return redirect('/image?youtube_auth=success')

    except Exception as e:
        print(f"[YOUTUBE-CALLBACK][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>YouTube 연결 오류</title>
        <style>body{{font-family:Arial;padding:50px;text-align:center}}.error{{background:#ffebee;padding:20px;border-radius:8px;margin:20px auto;max-width:500px;color:#c62828}}.back-btn{{margin-top:20px;padding:10px 20px;background:#1a73e8;color:white;border:none;border-radius:4px;cursor:pointer;text-decoration:none;display:inline-block}}</style>
        </head>
        <body>
            <h1>⚠️ YouTube 연결 오류</h1>
            <div class="error">
                <p>인증 처리 중 오류가 발생했습니다.</p>
                <p style="font-size:12px;color:#666;">{str(e)[:200]}</p>
            </div>
            <a href="/image" class="back-btn">← 다시 시도</a>
        </body>
        </html>
        """, 500


@app.route('/api/drama/youtube-auth-status')
def youtube_auth_status():
    """YouTube 인증 상태 확인"""
    try:
        # 데이터베이스에서 토큰 로드
        token_data = load_youtube_token_from_db()

        if token_data:
            # refresh_token이 있으면 인증된 것으로 간주 (자동 갱신 가능)
            if token_data.get('refresh_token'):
                print(f"[YOUTUBE-AUTH-STATUS] 인증됨 (refresh_token 존재)")
                return jsonify({"authenticated": True})
            # token만 있어도 일단 인증된 것으로 처리
            elif token_data.get('token'):
                print(f"[YOUTUBE-AUTH-STATUS] 인증됨 (token만 존재, refresh_token 없음)")
                return jsonify({"authenticated": True, "warning": "refresh_token 없음"})

        print(f"[YOUTUBE-AUTH-STATUS] 인증 안됨 (토큰 없음)")
        return jsonify({"authenticated": False})

    except Exception as e:
        print(f"[YOUTUBE-AUTH-STATUS] 오류: {e}")
        return jsonify({"authenticated": False, "error": str(e)})


@app.route('/api/drama/youtube-channels')
def youtube_channels():
    """YouTube 채널 목록 가져오기 (저장된 모든 채널 반환)"""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        # 데이터베이스에 저장된 모든 채널 가져오기
        saved_channels = load_all_youtube_channels_from_db()

        # 저장된 채널이 있으면 각 채널의 토큰 유효성 검사
        valid_channels = []
        for ch in saved_channels:
            channel_id = ch['id']
            token_data = load_youtube_token_from_db(channel_id)
            if token_data:
                try:
                    credentials = Credentials.from_authorized_user_info(token_data)
                    # 토큰 갱신 필요시
                    if credentials.expired and credentials.refresh_token:
                        credentials.refresh(Request())
                        token_data['token'] = credentials.token
                        save_youtube_token_to_db(token_data, channel_id=channel_id, channel_info={
                            'title': ch['title'],
                            'thumbnail': ch['thumbnail']
                        })
                    valid_channels.append(ch)
                except Exception as token_error:
                    print(f"[YOUTUBE-CHANNELS] 채널 {channel_id} 토큰 만료/무효: {token_error}")
                    # 만료된 채널도 목록에는 표시 (재인증 유도)
                    ch['expired'] = True
                    valid_channels.append(ch)

        if valid_channels:
            return jsonify({
                "success": True,
                "channels": valid_channels
            })

        # 저장된 채널이 없으면 기존 방식으로 시도 (레거시 호환)
        token_data = load_youtube_token_from_db()
        if not token_data:
            return jsonify({
                "success": False,
                "error": "YouTube 인증이 필요합니다.",
                "channels": []
            })

        credentials = Credentials.from_authorized_user_info(token_data)

        # 토큰 갱신 필요시
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            token_data['token'] = credentials.token
            save_youtube_token_to_db(token_data)

        # YouTube API 클라이언트 생성
        youtube = build('youtube', 'v3', credentials=credentials)

        # 내 채널 목록 가져오기
        channels_response = youtube.channels().list(
            part='snippet,contentDetails',
            mine=True
        ).execute()

        channels = []
        for channel in channels_response.get('items', []):
            channels.append({
                'id': channel['id'],
                'title': channel['snippet']['title'],
                'description': channel['snippet']['description'],
                'thumbnail': channel['snippet']['thumbnails'].get('default', {}).get('url', '')
            })

        return jsonify({
            "success": True,
            "channels": channels
        })

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[YOUTUBE-CHANNELS][ERROR] {str(e)}")
        print(f"[YOUTUBE-CHANNELS][ERROR] Traceback: {error_detail}")

        # 더 구체적인 에러 메시지
        if "invalid_grant" in str(e).lower():
            return jsonify({
                "success": False,
                "error": "YouTube 인증이 만료되었습니다. 다시 인증해주세요.",
                "need_reauth": True,
                "channels": []
            })
        elif "credentials" in str(e).lower():
            return jsonify({
                "success": False,
                "error": "YouTube 인증 정보가 올바르지 않습니다. 다시 인증해주세요.",
                "need_reauth": True,
                "channels": []
            })
        else:
            return jsonify({
                "success": False,
                "error": f"채널 목록을 가져오는 데 실패했습니다: {str(e)}",
                "channels": []
            })


@app.route('/api/youtube/channel/<channel_id>', methods=['DELETE'])
def delete_youtube_channel(channel_id):
    """YouTube 채널 토큰 삭제"""
    try:
        print(f"[YOUTUBE-DELETE] 채널 삭제 요청: {channel_id}")

        deleted = delete_youtube_channel_from_db(channel_id)

        if deleted:
            return jsonify({
                "ok": True,
                "message": f"채널 {channel_id} 삭제됨"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "삭제할 채널을 찾을 수 없습니다."
            }), 404

    except Exception as e:
        print(f"[YOUTUBE-DELETE] 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


@app.route('/api/drama/upload-youtube', methods=['POST'])
def upload_youtube():
    """YouTube에 비디오 업로드"""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        data = request.get_json()
        video_data = data.get('video_data')
        title = data.get('title', 'AI 드라마')
        description = data.get('description', '')
        tags = data.get('tags', [])
        category_id = data.get('category_id', '22')  # 22 = People & Blogs
        privacy_status = data.get('privacy_status') or 'private'  # 빈 문자열도 기본값 처리
        publish_at = data.get('publish_at')  # ISO 8601 형식의 예약 공개 시간
        channel_id = data.get('channel_id')  # 선택된 채널 ID

        if not video_data:
            return jsonify({"success": False, "error": "비디오 데이터가 없습니다."})

        print(f"[YOUTUBE-UPLOAD] 선택된 채널 ID: {channel_id or 'default'}")

        # 선택된 채널의 토큰 로드 (없으면 default)
        token_data = load_youtube_token_from_db(channel_id) if channel_id else load_youtube_token_from_db()
        if not token_data:
            return jsonify({"success": False, "error": "YouTube 인증이 필요합니다."})

        credentials = Credentials.from_authorized_user_info(token_data)

        # 토큰 갱신
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            # 갱신된 토큰 저장 (데이터베이스에)
            token_data['token'] = credentials.token
            save_youtube_token_to_db(token_data, channel_id=channel_id)

        # 비디오 파일 임시 저장
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = os.path.join(temp_dir, 'upload_video.mp4')

            # Base64 디코딩
            video_bytes = base64.b64decode(video_data)
            with open(video_path, 'wb') as f:
                f.write(video_bytes)

            print(f"[YOUTUBE-UPLOAD] 비디오 파일 준비 완료: {len(video_bytes)} bytes")

            # YouTube API 클라이언트 생성
            youtube = build('youtube', 'v3', credentials=credentials)

            # 비디오 메타데이터
            status_data = {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False
            }

            # 예약 업로드 설정 (publishAt이 있으면 예약 공개)
            if publish_at:
                status_data['publishAt'] = publish_at
                # 예약 업로드 시 privacyStatus는 반드시 private이어야 함
                status_data['privacyStatus'] = 'private'
                print(f"[YOUTUBE-UPLOAD] 예약 업로드 설정: {publish_at}")

            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags,
                    'categoryId': category_id
                },
                'status': status_data
            }

            # 업로드 실행
            media = MediaFileUpload(
                video_path,
                mimetype='video/mp4',
                resumable=True,
                chunksize=1024*1024  # 1MB chunks
            )

            insert_request = youtube.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = insert_request.next_chunk()
                if status:
                    print(f"[YOUTUBE-UPLOAD] 업로드 진행률: {int(status.progress() * 100)}%")

            video_id = response['id']
            video_url = f"https://www.youtube.com/watch?v={video_id}"

            if publish_at:
                print(f"[YOUTUBE-UPLOAD] 예약 업로드 완료! Video ID: {video_id}, 공개 예정: {publish_at}")
                message = f"YouTube 예약 업로드가 완료되었습니다! ({publish_at}에 공개 예정)"
            else:
                print(f"[YOUTUBE-UPLOAD] 업로드 완료! Video ID: {video_id}")
                message = "YouTube 업로드가 완료되었습니다!"

            return jsonify({
                "success": True,
                "video_id": video_id,
                "video_url": video_url,
                "publish_at": publish_at,
                "message": message
            })

    except ImportError:
        return jsonify({
            "success": False,
            "error": "Google API 라이브러리가 설치되지 않았습니다. pip install google-auth-oauthlib google-api-python-client를 실행해주세요."
        })
    except Exception as e:
        print(f"[YOUTUBE-UPLOAD][ERROR] {str(e)}")
        return jsonify({"success": False, "error": str(e)})


# ===== 썸네일 텍스트 오버레이 API (별도) =====
@app.route('/api/drama/thumbnail-overlay', methods=['POST'])
def api_thumbnail_overlay():
    """이미지에 텍스트 오버레이하여 썸네일 생성"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        from io import BytesIO
        import requests as req
        import base64
        import urllib.request
        import os as os_module

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        # 입력 파라미터
        image_url = data.get("imageUrl", "")  # base64 data URL 또는 HTTP URL
        text_lines = data.get("textLines", [])  # ["1줄", "2줄", "3줄", "4줄"]
        highlight_lines = data.get("highlightLines", [2])  # 강조할 줄 인덱스 (0부터 시작)
        text_color = data.get("textColor", "#FFFFFF")  # 기본 텍스트 색상
        highlight_color = data.get("highlightColor", "#FFD700")  # 강조 텍스트 색상 (노란색)
        outline_color = data.get("outlineColor", "#000000")  # 외곽선 색상
        outline_width = data.get("outlineWidth", 4)  # 외곽선 두께
        font_size = data.get("fontSize", 60)  # 폰트 크기
        position = data.get("position", "left")  # 텍스트 위치: left, center, right

        # 줄별 스타일 지원 (새 기능)
        # lineStyles: [{"color": "#FFD700", "fontSize": 80}, {"color": "#FFFFFF", "fontSize": 60}]
        line_styles = data.get("lineStyles", [])  # 줄별 색상/크기 개별 지정

        print(f"[THUMBNAIL] 썸네일 생성 시작 - 텍스트 {len(text_lines)}줄")

        if not image_url:
            return jsonify({"ok": False, "error": "이미지 URL이 필요합니다."}), 400

        if not text_lines:
            return jsonify({"ok": False, "error": "텍스트가 필요합니다."}), 400

        # base_dir 먼저 정의 (로컬 경로 처리용)
        base_dir = os_module.path.dirname(os_module.path.abspath(__file__))

        # 이미지 로드
        if image_url.startswith("data:"):
            # Base64 data URL
            header, encoded = image_url.split(",", 1)
            image_data = base64.b64decode(encoded)
            img = Image.open(BytesIO(image_data))
        elif image_url.startswith("/static/"):
            # 로컬 상대 경로 (서버 내 파일)
            local_path = os_module.path.join(base_dir, image_url.lstrip("/"))
            print(f"[THUMBNAIL] 로컬 파일 로드: {local_path}")
            img = Image.open(local_path)
        elif image_url.startswith("http"):
            # HTTP URL
            response = req.get(image_url, timeout=30)
            img = Image.open(BytesIO(response.content))
        else:
            # 기타 로컬 경로
            img = Image.open(image_url)

        # RGBA로 변환 (투명도 지원)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # 이미지 크기 (유튜브 썸네일: 1280x720 권장)
        width, height = img.size
        print(f"[THUMBNAIL] 이미지 크기: {width}x{height}")

        # 폰트 로드 (한글 지원 폰트)
        font = None
        base_dir = os_module.path.dirname(os_module.path.abspath(__file__))
        font_paths = [
            # Pretendard (최우선)
            os_module.path.join(base_dir, "fonts/Pretendard-Bold.ttf"),
            os_module.path.join(base_dir, "fonts/Pretendard-SemiBold.ttf"),
            # 프로젝트 로컬 폰트 (폴백)
            os_module.path.join(base_dir, "fonts/NanumSquareB.ttf"),
            os_module.path.join(base_dir, "fonts/NanumGothicBold.ttf"),
            # Linux (Render)
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]

        for font_path in font_paths:
            if os_module.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    print(f"[THUMBNAIL] 폰트 로드: {font_path}")
                    break
                except Exception:
                    continue

        if font is None:
            # 기본 폰트 사용 (한글 지원 안 될 수 있음)
            font = ImageFont.load_default()
            print(f"[THUMBNAIL] 기본 폰트 사용 (한글 미지원 가능)")

        # 드로잉 객체 생성
        draw = ImageDraw.Draw(img)

        # 텍스트 위치 계산
        line_height = font_size + 20  # 줄 간격
        total_text_height = len(text_lines) * line_height

        # Y 시작 위치 (상단 여백 고려)
        y_start = int(height * 0.1)  # 상단 10%부터 시작

        # X 위치
        x_margin = int(width * 0.05)  # 좌우 여백 5%

        # 줄별 폰트 캐시 (서로 다른 크기 지원)
        font_cache = {font_size: font}

        def get_font_for_size(size):
            """주어진 크기의 폰트 반환 (캐싱)"""
            if size in font_cache:
                return font_cache[size]
            # 새 크기 폰트 로드
            for font_path in font_paths:
                if os_module.path.exists(font_path):
                    try:
                        new_font = ImageFont.truetype(font_path, size)
                        font_cache[size] = new_font
                        return new_font
                    except Exception:
                        continue
            return font  # 기본 폰트 반환

        y_current = y_start
        for i, line in enumerate(text_lines):
            # 줄별 스타일 가져오기
            line_style = line_styles[i] if i < len(line_styles) else {}
            line_font_size = line_style.get("fontSize", font_size)
            line_color = line_style.get("color", None)

            # 이 줄의 폰트 가져오기
            current_font = get_font_for_size(line_font_size)
            current_line_height = line_font_size + 20

            # 텍스트 크기 측정
            bbox = draw.textbbox((0, 0), line, font=current_font)
            text_width = bbox[2] - bbox[0]

            # X 위치 결정
            if position == "center":
                x = (width - text_width) // 2
            elif position == "right":
                x = width - text_width - x_margin
            else:  # left
                x = x_margin

            # 색상 결정 (우선순위: lineStyles > highlightLines > textColor)
            if line_color:
                fill_color = line_color
            elif i in highlight_lines:
                fill_color = highlight_color
            else:
                fill_color = text_color

            # 외곽선 그리기 (8방향)
            for dx in range(-outline_width, outline_width + 1):
                for dy in range(-outline_width, outline_width + 1):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y_current + dy), line, font=current_font, fill=outline_color)

            # 메인 텍스트 그리기
            draw.text((x, y_current), line, font=current_font, fill=fill_color)

            # 다음 줄 Y 위치
            y_current += current_line_height

        # 결과 이미지를 base64로 인코딩
        output_buffer = BytesIO()
        img_rgb = img.convert('RGB')  # JPEG는 RGB 필요
        img_rgb.save(output_buffer, format='JPEG', quality=95)
        output_buffer.seek(0)
        result_base64 = base64.b64encode(output_buffer.read()).decode('utf-8')
        result_url = f"data:image/jpeg;base64,{result_base64}"

        print(f"[THUMBNAIL] 썸네일 생성 완료")

        return jsonify({
            "ok": True,
            "imageUrl": result_url,  # 클라이언트 호환성을 위해 imageUrl 사용
            "thumbnailUrl": result_url,  # 레거시 호환
            "width": width,
            "height": height
        })

    except Exception as e:
        print(f"[THUMBNAIL][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 카테고리별 벤치마킹 대본 조회 API =====
@app.route('/api/drama/benchmarks', methods=['GET'])
def api_get_benchmarks():
    """카테고리별 벤치마킹 대본 목록 조회"""
    try:
        video_category = request.args.get('videoCategory', '')
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))

        conn = get_db_connection()
        cursor = conn.cursor()

        if video_category:
            if USE_POSTGRES:
                cursor.execute('''
                    SELECT id, script_text, upload_date, view_count, category, video_category,
                           analysis_result, created_at
                    FROM benchmark_analyses
                    WHERE video_category = %s
                    ORDER BY view_count DESC, created_at DESC
                    LIMIT %s OFFSET %s
                ''', (video_category, limit, offset))
            else:
                cursor.execute('''
                    SELECT id, script_text, upload_date, view_count, category, video_category,
                           analysis_result, created_at
                    FROM benchmark_analyses
                    WHERE video_category = ?
                    ORDER BY view_count DESC, created_at DESC
                    LIMIT ? OFFSET ?
                ''', (video_category, limit, offset))
        else:
            if USE_POSTGRES:
                cursor.execute('''
                    SELECT id, script_text, upload_date, view_count, category, video_category,
                           analysis_result, created_at
                    FROM benchmark_analyses
                    ORDER BY view_count DESC, created_at DESC
                    LIMIT %s OFFSET %s
                ''', (limit, offset))
            else:
                cursor.execute('''
                    SELECT id, script_text, upload_date, view_count, category, video_category,
                           analysis_result, created_at
                    FROM benchmark_analyses
                    ORDER BY view_count DESC, created_at DESC
                    LIMIT ? OFFSET ?
                ''', (limit, offset))

        rows = cursor.fetchall()

        # 카테고리별 개수 조회
        if USE_POSTGRES:
            cursor.execute('''
                SELECT video_category, COUNT(*) as cnt
                FROM benchmark_analyses
                GROUP BY video_category
            ''')
        else:
            cursor.execute('''
                SELECT video_category, COUNT(*) as cnt
                FROM benchmark_analyses
                GROUP BY video_category
            ''')
        category_counts = {row[0] or '미분류': row[1] for row in cursor.fetchall()}

        conn.close()

        benchmarks = []
        for row in rows:
            benchmarks.append({
                'id': row[0],
                'scriptPreview': row[1][:200] + '...' if len(row[1]) > 200 else row[1],
                'uploadDate': row[2],
                'viewCount': row[3],
                'category': row[4],
                'videoCategory': row[5] or '미분류',
                'analysisPreview': row[6][:300] + '...' if row[6] and len(row[6]) > 300 else row[6],
                'createdAt': str(row[7]) if row[7] else ''
            })

        return jsonify({
            'ok': True,
            'benchmarks': benchmarks,
            'categoryCounts': category_counts,
            'total': sum(category_counts.values())
        })

    except Exception as e:
        print(f"[BENCHMARKS][ERROR] {str(e)}")
        return jsonify({'ok': False, 'error': str(e)}), 200


@app.route('/api/drama/benchmark/<int:benchmark_id>', methods=['GET'])
def api_get_benchmark_detail(benchmark_id):
    """벤치마킹 대본 상세 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('SELECT * FROM benchmark_analyses WHERE id = %s', (benchmark_id,))
        else:
            cursor.execute('SELECT * FROM benchmark_analyses WHERE id = ?', (benchmark_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({'ok': False, 'error': '벤치마킹 대본을 찾을 수 없습니다.'}), 404

        return jsonify({
            'ok': True,
            'benchmark': {
                'id': row[0],
                'scriptText': row[1],
                'uploadDate': row[3],
                'viewCount': row[4],
                'category': row[5],
                'videoCategory': row[6] if len(row) > 6 else '미분류',
                'analysisResult': row[7] if len(row) > 7 else row[6],
                'storyStructure': row[8] if len(row) > 8 else '',
                'characterElements': row[9] if len(row) > 9 else '',
                'dialogueStyle': row[10] if len(row) > 10 else '',
                'successFactors': row[11] if len(row) > 11 else ''
            }
        })

    except Exception as e:
        print(f"[BENCHMARK-DETAIL][ERROR] {str(e)}")
        return jsonify({'ok': False, 'error': str(e)}), 200


# ===== 한국어 → 중국어 번역 API =====
@app.route('/api/translate/ko-to-zh', methods=['POST'])
def api_translate_ko_to_zh():
    """한국어를 중국어(간체)로 번역

    샤오홍수 검색을 위한 번역 API
    """
    try:
        data = request.get_json()
        text = data.get('text', '').strip()

        if not text:
            return jsonify({'ok': False, 'error': '번역할 텍스트가 없습니다.'}), 400

        print(f"[TRANSLATE] 한국어 → 중국어: {text}")

        from openai import OpenAI
        client = OpenAI()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "你是一个翻译专家。将韩语翻译成简体中文。只输出翻译结果，不要解释。如果是产品名称，翻译成中国消费者常用的搜索词。"
                },
                {
                    "role": "user",
                    "content": f"翻译: {text}"
                }
            ],
            temperature=0.3,
            max_tokens=100
        )

        translated = response.choices[0].message.content.strip()
        print(f"[TRANSLATE] 번역 결과: {translated}")

        return jsonify({
            'ok': True,
            'original': text,
            'translated': translated
        })

    except Exception as e:
        print(f"[TRANSLATE][ERROR] {str(e)}")
        return jsonify({'ok': False, 'error': str(e)}), 500


# ===== 쿠팡파트너스 상품 대본 생성 API =====
@app.route('/api/drama/generate-coupang-script', methods=['POST'])
def api_generate_coupang_script():
    """상품 정보로 쿠팡파트너스 쇼츠 대본 생성

    Input:
    {
        "productName": "샤오미 무선 청소기 V12",
        "productPrice": "89,000원",
        "productFeatures": ["강력한 흡입력", "긴 배터리"]
    }

    Output:
    {
        "ok": true,
        "script": "생성된 대본..."
    }
    """
    try:
        data = request.get_json()
        product_name = data.get('productName', '').strip()
        product_price = data.get('productPrice', '')
        product_features = data.get('productFeatures', [])

        if not product_name:
            return jsonify({'ok': False, 'error': '상품명이 비어있습니다.'}), 400

        print(f"[COUPANG-SCRIPT] 대본 생성 시작 - 상품: {product_name}")

        # OpenAI API로 대본 생성
        from openai import OpenAI
        client = OpenAI()

        system_prompt = """당신은 쿠팡파트너스 제휴 마케팅 전문가입니다.
상품 정보를 받아 60초 이하의 세로형 쇼츠 대본을 작성합니다.

## 대본 작성 규칙
1. **첫 3초 훅**: 가격/효과/놀람으로 시작 ("이게 만원대?", "써보고 놀랐습니다")
2. **본문 (40초)**: 핵심 장점 1-2개만 간결하게 설명
3. **CTA (마지막)**: "링크는 프로필에 있어요" 또는 "쿠팡에서 [상품명] 검색하세요"

## 대본 형식
- 나레이션 형식으로 작성 (1인칭 시점)
- 총 150자 이내
- 짧은 문장, 임팩트 있게
- 상품명 언급 필수

## 예시 대본
"이게 8만원대라고요?
샤오미 무선 청소기 써봤는데, 진짜 놀랐습니다.
흡입력? 유선 못지않아요.
배터리? 40분 넘게 가더라고요.
링크는 프로필에 있어요."
"""

        features_text = ', '.join(product_features) if product_features else '미입력'
        user_prompt = f"""다음 상품의 60초 쇼츠 대본을 작성해주세요:

상품명: {product_name}
가격: {product_price if product_price else '미입력'}
핵심 장점: {features_text}

대본만 출력해주세요 (설명 없이)."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )

        script = response.choices[0].message.content.strip()
        print(f"[COUPANG-SCRIPT] 대본 생성 완료 - 길이: {len(script)}자")

        return jsonify({
            'ok': True,
            'script': script,
            'productName': product_name
        })

    except Exception as e:
        print(f"[COUPANG-SCRIPT][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


# ===== AI 대본 분석 API (씬/샷 자동 분리) =====
@app.route('/api/drama/analyze-script', methods=['POST'])
def api_analyze_script():
    """전체 대본을 분석하여 씬과 샷으로 자동 분리

    Input:
    {
        "script": "전체 대본 텍스트...",
        "channelType": "senior-nostalgia",
        "protagonistGender": "female"
    }

    Output:
    {
        "ok": true,
        "character": { "name": "이순자", "age": 70, "description": "..." },
        "scenes": [
            {
                "sceneId": "scene_1",
                "title": "식당에서의 만남",
                "shots": [
                    {
                        "shotId": "shot_1_1",
                        "imagePrompt": "Night, small Korean restaurant...",
                        "narration": "그날 밤이었습니다..."
                    },
                    ...
                ]
            },
            ...
        ],
        "thumbnailSuggestion": {
            "mainEmotion": "눈물의 재회",
            "textSuggestion": "46년만에 찾은 아버지"
        }
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'ok': False, 'error': 'No data received'}), 400

        script = data.get('script', '').strip()
        channel_type = data.get('channelType', 'senior-nostalgia')
        protagonist_gender = data.get('protagonistGender', 'female')
        content_type = data.get('contentType', 'drama')
        duration = data.get('duration', '5min')
        video_format = data.get('videoFormat', 'horizontal')

        # 쇼츠 여부 판단
        is_shorts = content_type in ['shorts', 'coupang-shorts'] or duration in ['30s', '60s']
        is_coupang = content_type == 'coupang-shorts'

        if not script:
            return jsonify({'ok': False, 'error': '대본이 비어있습니다.'}), 400

        # 쇼츠는 짧은 대본도 허용
        min_length = 30 if is_shorts else 100
        if len(script) < min_length:
            return jsonify({'ok': False, 'error': f'대본이 너무 짧습니다. (최소 {min_length}자)'}), 400

        print(f"[ANALYZE-SCRIPT] 대본 분석 시작 - 길이: {len(script)}자, 채널: {channel_type}, is_shorts: {is_shorts}, is_coupang: {is_coupang}")

        # OpenAI API 호출
        from openai import OpenAI
        client = OpenAI()

        # 쿠팡파트너스 쇼츠용 시스템 프롬프트
        if is_coupang:
            system_prompt = """당신은 쿠팡파트너스 제휴 마케팅용 상품 리뷰 쇼츠 전문가입니다.
주어진 상품 정보/리뷰를 60초 이하의 세로 영상(9:16)에 맞게 분석합니다.

## 🛒 쿠팡파트너스 쇼츠 핵심 규칙
1. **상품이 주인공** - 사람 얼굴 X, 상품 클로즈업 O
2. **가격/효과 훅** - 첫 3초에 가격 또는 효과로 후킹
3. **간결한 리뷰** - 장점 1-2개만 강조
4. **구매 유도 CTA** - "링크는 프로필에", "쿠팡에서 검색"

## 🎬 쿠팡 쇼츠 구성 공식 (60초)
1. **HOOK (0-3초)**: 가격/효과/놀람 훅
   - "이게 만원대라고?"
   - "써보고 깜짝 놀랐습니다"
   - "이거 안 사면 후회합니다"
   - "00 고민이시라면 이거 하나면 끝"
2. **PRODUCT (3-40초)**: 상품 소개
   - 상품 클로즈업 이미지
   - 핵심 장점 1-2개
   - 사용 장면 (손만 나오게)
3. **CTA (40-60초)**: 구매 유도
   - "링크는 프로필에 있어요"
   - "쿠팡에서 [상품명] 검색하세요"
   - "지금 할인 중이에요"

## 📱 상품 이미지 프롬프트 규칙
- **세로 구도 필수**: "vertical composition (9:16 aspect ratio)" 항상 포함
- **상품 클로즈업**: "product close-up shot", "detailed product photography"
- **깔끔한 배경**: "clean white background", "minimal studio setup", "soft gradient background"
- **손/사용 장면**: "hands holding product", "product in use" (얼굴 없이)
- **고급 광고 느낌**: "professional commercial photography", "high-end product shot"
- ⚠️ **사람 얼굴 절대 금지** - 제품만 보여주거나 손만 나오게

## 프롬프트 예시 (쿠팡 쇼츠용)
"Vertical composition (9:16), professional product photography of [상품명], clean white studio background, soft diffused lighting, product centered in frame, high-end commercial quality, minimal and elegant, text-safe area at top and bottom."

"Vertical composition (9:16), close-up of hands holding [상품명], product in use demonstration, soft natural lighting, blurred simple background, focus on product details, no face visible, mobile-optimized framing."

## 출력 형식 (JSON)
```json
{
  "product": {
    "name": "상품명",
    "category": "카테고리 (생활용품/가전/뷰티/식품 등)",
    "priceRange": "가격대 (예: 만원대, 2만원대)",
    "keyFeatures": ["핵심 장점 1", "핵심 장점 2"]
  },
  "scenes": [
    {
      "sceneId": "scene_1",
      "title": "씬 제목",
      "shots": [
        {
          "shotId": "shot_1_1",
          "shotType": "hook/product/cta",
          "imagePrompt": "상품 중심 세로 구도 프롬프트 (얼굴 없음)",
          "narration": "짧고 임팩트있는 나레이션"
        }
      ]
    }
  ],
  "thumbnailSuggestion": {
    "mainEmotion": "핵심 후킹 포인트",
    "textSuggestion": "썸네일 텍스트 (가격/효과 강조)"
  },
  "hookLine": "첫 3초 훅 멘트",
  "ctaLine": "CTA 멘트 (구매 유도)"
}
```

⚠️ 중요: 상품 쇼츠는 최대 1개 씬, 3개 샷! 나레이션 총합 100자 이내! 사람 얼굴 절대 금지!"""

        # 일반 쇼츠용 시스템 프롬프트
        elif is_shorts:
            system_prompt = """당신은 YouTube Shorts / Instagram Reels 전문 콘텐츠 분석가입니다.
주어진 대본을 60초 이하의 세로 영상(9:16)에 맞게 분석합니다.

## 🎯 쇼츠 핵심 규칙
1. **첫 3초가 생명** - 강렬한 훅(Hook)으로 시작해야 스크롤을 멈춤
2. **짧고 임팩트있게** - 전체 나레이션 150자 이내 권장
3. **세로 구도** - 모든 이미지 프롬프트는 세로(9:16) 최적화
4. **1-2개 씬, 2-3개 샷** - 쇼츠는 간결해야 함

## 🎬 쇼츠 구성 공식
1. **HOOK (0-3초)**: 질문/충격적 사실/감정적 장면으로 시작
2. **CONTENT (3-50초)**: 핵심 메시지 1개만 전달
3. **CTA (50-60초)**: 좋아요/구독/다음 영상 유도

## 📱 쇼츠 이미지 프롬프트 규칙
- **세로 구도 필수**: "vertical composition (9:16 aspect ratio)" 항상 포함
- **클로즈업 선호**: 작은 화면에서 잘 보이게
- **주인공 중앙 배치**: 피사체를 화면 가운데에
- **심플한 배경**: 복잡한 배경은 시선 분산
- **텍스트 공간 확보**: 상단/하단에 자막 들어갈 공간

## 프롬프트 예시 (쇼츠용)
"Vertical composition (9:16), simple white stickman character with round head, black dot eyes showing sadness, emotional pose with head down, detailed anime-style background Ghibli-inspired with soft warm lighting, contrast collage style, text-safe area at top and bottom, mobile-optimized framing."

## 출력 형식 (JSON)
```json
{
  "character": {
    "name": "주인공 이름",
    "age": 나이,
    "gender": "female/male",
    "appearance": "외모 설명 (영문)"
  },
  "scenes": [
    {
      "sceneId": "scene_1",
      "title": "씬 제목 (한글)",
      "shots": [
        {
          "shotId": "shot_1_1",
          "shotType": "hook/content/cta",
          "imagePrompt": "세로 구도 영문 프롬프트 (vertical composition 포함)",
          "narration": "짧고 임팩트있는 나레이션 (한글, 1-2문장)"
        }
      ]
    }
  ],
  "thumbnailSuggestion": {
    "mainEmotion": "핵심 감정",
    "textSuggestion": "썸네일 텍스트 (2-4글자, 임팩트있게)"
  },
  "hookLine": "첫 3초 훅 멘트"
}
```

⚠️ 중요: 쇼츠는 최대 2개 씬, 3개 샷까지만! 나레이션 총합 150자 이내!"""

        else:
            # 기존 드라마용 시스템 프롬프트
            system_prompt = """당신은 드라마 대본 분석 전문가이자, AI 이미지/영상용 프롬프트 전문 작성가입니다.
주어진 대본을 분석하여 씬(Scene)과 샷(Shot)으로 나누고, 각 샷에 대한 전문가급 이미지 프롬프트를 생성합니다.

## 분석 규칙
1. **씬(Scene)**: 장소나 시간이 크게 바뀔 때 새로운 씬
2. **샷(Shot)**: 같은 씬 내에서 카메라 앵글/구도가 바뀔 때, 또는 중요한 감정 변화가 있을 때 새로운 샷
3. 각 샷은 10-30초 정도의 나레이션을 담당
4. 이미지 프롬프트는 반드시 영어로, 한국인 시니어 캐릭터에 맞게 작성

## 이미지 프롬프트 작성 원칙
1. **출력 프롬프트는 항상 영어**로 작성합니다.
2. 프롬프트는 **짧지만 정보 밀도가 높은 한 문단**으로 작성합니다.
3. 핵심 피사체를 앞으로: "A / An / The ..."로 무엇을 보여줄지부터 명확히 씁니다.
4. 한 프롬프트에는 한 장면만: 여러 장면을 섞지 말고, 한 화면에 들어갈 장면만 설계합니다.
5. 명사+형용사 조합 선호: "soft golden sunlight", "dramatic side lighting" 처럼 구체적 묘사.

## 이미지 프롬프트 필수 요소 (가능한 모두 포함)
- **[subject]** 피사체 / 주인공 / 행동
- **[environment]** 배경, 장소, 시대
- **[lighting]** 조명 방향·세기·분위기 (soft natural light, warm golden-hour, dramatic side lighting 등)
- **[color]** 색감·톤 (warm pastel, faded vintage colors, high contrast 등)
- **[camera]** 샷 종류(wide/medium/close-up), 렌즈(24mm/50mm/85mm), depth of field, angle
- **[style]** 스타일 (cinematic, photorealistic, nostalgic film photography, 1970s Korean film aesthetic 등)
- **[mood]** 감정·분위기 (peaceful, dramatic, nostalgic, tearful, hopeful 등)

## 스틱맨(Stickman) 캐릭터 가이드
- ⚠️ 실사 인물 절대 금지! 할아버지, 할머니, 노인 등 사람 얼굴 생성 금지!
- 모든 인물은 스틱맨으로만 표현
- 스틱맨 특징: "Simple white stickman with round head, black dot eyes, small mouth, thin eyebrows, black outline body"
- 감정 표현: 스틱맨의 표정(점 눈, 곡선 입)과 포즈로 표현
- 배경: 애니메이션 스타일 (Ghibli-inspired, warm colors)
- 전체 스타일: "Contrast collage style - simple stickman against detailed anime background"

## 프롬프트 예시
좋은 예시:
"Simple white stickman with round head, black dot eyes looking sad, small frowning mouth, sitting alone at a detailed anime-style wooden kitchen table, Ghibli-inspired soft morning light through window, warm cup of tea nearby, contrast collage style, nostalgic and contemplative atmosphere."

"Two simple white stickmen embracing in emotional reunion pose, one larger one smaller, detailed anime-style humble restaurant background, Ghibli-inspired warm lighting, contrast collage style, emotional and hopeful atmosphere."

## 출력 형식 (반드시 JSON)
```json
{
  "character": {
    "name": "주인공 이름",
    "age": 나이,
    "gender": "female/male",
    "appearance": "외모 설명 (영문) - 한국인 시니어 특징 포함"
  },
  "scenes": [
    {
      "sceneId": "scene_1",
      "title": "씬 제목 (한글)",
      "shots": [
        {
          "shotId": "shot_1_1",
          "imagePrompt": "전문가급 영문 이미지 프롬프트 (위 가이드 준수)",
          "narration": "해당 샷의 나레이션 텍스트 (한글)"
        }
      ]
    }
  ],
  "thumbnailSuggestion": {
    "mainEmotion": "핵심 감정 (예: 눈물의 재회)",
    "textSuggestion": "썸네일 텍스트 제안 (2-5글자)"
  }
}
```"""

        if is_coupang:
            user_prompt = f"""🛒 쿠팡파트너스 상품 쇼츠 분석:

---
{script}
---

⚡ 영상 형식: 세로 (9:16) 상품 쇼츠
⏱️ 영상 길이: 60초 이내

🎯 요청사항:
1. 첫 3초에 가격/효과 훅 ("이게 만원대?", "써보고 놀람")
2. 상품 클로즈업 이미지 프롬프트 (사람 얼굴 절대 금지!)
3. 나레이션 총합 100자 이내로 압축
4. 1개 씬, 3개 샷 (hook → product → cta)
5. 모든 이미지 프롬프트는 세로 구도 + 상품 중심
6. CTA: "링크는 프로필에" 또는 "쿠팡에서 검색"

JSON 형식으로 출력해주세요."""

        elif is_shorts:
            user_prompt = f"""📱 쇼츠/릴스용 콘텐츠 분석:

---
{script}
---

⚡ 영상 형식: 세로 (9:16) 쇼츠
⏱️ 영상 길이: {duration}
👤 주인공 성별: {"여성" if protagonist_gender == "female" else "남성"}

🎯 요청사항:
1. 첫 3초에 강렬한 훅(Hook)으로 시작
2. 나레이션 총합 150자 이내로 압축
3. 씬 1-2개, 샷 2-3개로 간결하게
4. 모든 이미지 프롬프트는 세로 구도(vertical composition) 포함
5. CTA(구독/좋아요 유도) 포함

JSON 형식으로 출력해주세요."""
        else:
            user_prompt = f"""다음 대본을 분석해주세요:

---
{script}
---

주인공 성별: {"여성" if protagonist_gender == "female" else "남성"} (⚠️ 스틱맨으로만 표현, 실사 인물 금지!)
채널 타입: {channel_type}

대본을 씬과 샷으로 나누고, 각 샷에 대한 이미지 프롬프트와 나레이션을 JSON 형식으로 출력해주세요."""

        print(f"[ANALYZE-SCRIPT] GPT API 호출 중...")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=4000,
            response_format={"type": "json_object"}
        )

        result_text = response.choices[0].message.content
        print(f"[ANALYZE-SCRIPT] GPT 응답 길이: {len(result_text)}자")

        # JSON 파싱
        import json
        result = json.loads(result_text)

        # 샷 개수 계산
        total_shots = sum(len(scene.get('shots', [])) for scene in result.get('scenes', []))
        print(f"[ANALYZE-SCRIPT] 분석 완료 - 씬: {len(result.get('scenes', []))}개, 샷: {total_shots}개")

        return jsonify({
            'ok': True,
            'character': result.get('character', {}),
            'scenes': result.get('scenes', []),
            'thumbnailSuggestion': result.get('thumbnailSuggestion', {}),
            'totalShots': total_shots
        })

    except json.JSONDecodeError as e:
        print(f"[ANALYZE-SCRIPT] JSON 파싱 오류: {e}")
        return jsonify({'ok': False, 'error': f'AI 응답 파싱 오류: {str(e)}'}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ANALYZE-SCRIPT] 오류: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500


# ===== GPT-4o-mini 2단계 기획 API =====
@app.route('/api/drama/gpt-plan-step1', methods=['POST'])
def api_gpt_plan_step1():
    """GPT-4o-mini 기획 1단계: 스토리 컨셉 생성"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'ok': False, 'error': 'No data received'}), 400

        video_category = data.get('videoCategory', '간증')
        duration = data.get('duration', '2분')
        custom_directive = data.get('customDirective', '')
        test_mode = bool(data.get('testMode', False))  # 🧪 테스트 모드

        # 테스트 모드: 시간을 3분으로 강제 설정
        if test_mode:
            duration = '3분'
            print(f"[GPT-PLAN-1] 🧪 테스트 모드 - 최소 분량으로 기획")

        # duration에서 분 숫자 추출 (예: "2분" -> 2, "10분" -> 10)
        duration_match = re.search(r'(\d+)', duration)
        duration_minutes = int(duration_match.group(1)) if duration_match else 10

        # guides/drama.json에서 duration_settings 로드
        duration_settings = {
            2: {"target_length": 600, "max_characters": 1, "max_scenes": 2},
            5: {"target_length": 1500, "max_characters": 2, "max_scenes": 3},
            10: {"target_length": 3000, "max_characters": 2, "max_scenes": 4},
            20: {"target_length": 6000, "max_characters": 3, "max_scenes": 6},
            30: {"target_length": 9000, "max_characters": 4, "max_scenes": 8}
        }
        settings = duration_settings.get(duration_minutes, duration_settings[10])

        print(f"[GPT-PLAN-1] 기획 시작 - 카테고리: {video_category}, 시간: {duration}, 목표글자수: {settings['target_length']}, 테스트모드: {test_mode}")

        system_prompt = f"""당신은 영상 콘텐츠 기획 전문가입니다.

【 역할 】
주어진 카테고리와 시간에 맞는 스토리 컨셉을 기획합니다.

【 ⚠️ 분량 규칙 - 반드시 준수 】
- 영상 길이: {duration_minutes}분
- 목표 대본 글자수: {settings['target_length']}자 (TTS 기준 1분당 약 300자)
- 최대 등장인물: {settings['max_characters']}명
- 최대 씬 개수: {settings['max_scenes']}개

【 출력 형식 】
1. 주인공 설정
   - 이름, 나이, 직업
   - 성격 특징 (2-3가지)
   - 현재 상황/고민

2. 스토리 컨셉
   - 한 줄 요약
   - 핵심 메시지
   - 감정 흐름 (시작 → 전환점 → 결말)

3. 배경
   - 시대/장소
   - 분위기

4. 씬 구성 (최대 {settings['max_scenes']}개)
   - 각 씬별 핵심 내용 1줄 요약

【 주의사항 】
- 구체적인 이름, 숫자, 장소 사용
- 공감할 수 있는 보편적 상황 선택
- {duration_minutes}분 영상에 맞는 간결한 스토리 (너무 복잡하면 안됨)"""

        user_prompt = f"""【 영상 정보 】
- 카테고리: {video_category}
- 영상 길이: {duration_minutes}분
- 목표 대본 분량: 약 {settings['target_length']}자
- 최대 등장인물: {settings['max_characters']}명
- 최대 씬 개수: {settings['max_scenes']}개
"""
        if custom_directive:
            user_prompt += f"""
【 🔥 사용자 지침 (최우선) 】
{custom_directive}
→ 이 지침을 반드시 반영하여 기획하세요.
"""

        user_prompt += "\n위 정보를 바탕으로 스토리 컨셉을 기획해주세요."

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1000
        )

        result = completion.choices[0].message.content.strip()
        input_tokens = completion.usage.prompt_tokens if hasattr(completion, 'usage') and completion.usage else 0
        output_tokens = completion.usage.completion_tokens if hasattr(completion, 'usage') and completion.usage else 0

        # GPT-4o-mini 비용 계산 (원화): input $0.15/1M, output $0.6/1M → 환율 1400원
        # input: 0.15 * 1400 / 1000000 = 0.00021원/token
        # output: 0.6 * 1400 / 1000000 = 0.00084원/token
        cost = round(input_tokens * 0.00021 + output_tokens * 0.00084, 2)

        print(f"[GPT-PLAN-1] 기획 완료 - 토큰: {input_tokens}/{output_tokens}, 비용: ₩{cost}")

        return jsonify({
            'ok': True,
            'result': result,
            'tokens': input_tokens + output_tokens,
            'cost': cost,
            'step': 1
        })

    except Exception as e:
        print(f"[GPT-PLAN-1][ERROR] {str(e)}")
        return jsonify({'ok': False, 'error': str(e)}), 200


@app.route('/api/drama/gpt-plan-step2', methods=['POST'])
def api_gpt_plan_step2():
    """GPT-4o-mini 기획 2단계: 장면 구조화"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'ok': False, 'error': 'No data received'}), 400

        video_category = data.get('videoCategory', '간증')
        duration = data.get('duration', '2분')
        custom_directive = data.get('customDirective', '')
        step1_result = data.get('step1Result', '')
        test_mode = bool(data.get('testMode', False))  # 🧪 테스트 모드

        if not step1_result:
            return jsonify({'ok': False, 'error': 'Step1 결과가 필요합니다.'}), 400

        # 테스트 모드: 시간을 3분으로 강제 설정
        if test_mode:
            duration = '3분'
            print(f"[GPT-PLAN-2] 🧪 테스트 모드 - 최소 분량으로 구조화")

        # duration에서 분 숫자 추출
        duration_match = re.search(r'(\d+)', duration)
        duration_minutes = int(duration_match.group(1)) if duration_match else 10

        # duration_settings 로드
        duration_settings = {
            2: {"target_length": 600, "max_characters": 1, "max_scenes": 2},
            5: {"target_length": 1500, "max_characters": 2, "max_scenes": 3},
            10: {"target_length": 3000, "max_characters": 2, "max_scenes": 4},
            20: {"target_length": 6000, "max_characters": 3, "max_scenes": 6},
            30: {"target_length": 9000, "max_characters": 4, "max_scenes": 8}
        }
        settings = duration_settings.get(duration_minutes, duration_settings[10])

        print(f"[GPT-PLAN-2] 구조화 시작 - 카테고리: {video_category}, 시간: {duration_minutes}분, 씬: {settings['max_scenes']}개, 테스트모드: {test_mode}")

        system_prompt = f"""당신은 스토리 구조화 전문가입니다.

【 역할 】
기획된 컨셉을 바탕으로 상세한 장면 구성을 만듭니다.

【 ⚠️ 분량 규칙 - 반드시 준수 】
- 영상 길이: {duration_minutes}분
- 목표 대본 글자수: {settings['target_length']}자
- 최대 등장인물: {settings['max_characters']}명
- 장면 개수: 정확히 {settings['max_scenes']}개 (초과/미달 금지!)

【 출력 형식 - {settings['max_scenes']}개 장면만 작성 】
## 장면 구성

"""
        # 씬 개수에 따라 동적으로 장면 구성 안내
        scene_structure = {
            2: [("도입", 50), ("결말", 50)],
            3: [("도입", 30), ("전개/전환", 40), ("결말", 30)],
            4: [("도입", 20), ("전개", 30), ("전환점", 30), ("결말", 20)],
            6: [("도입", 15), ("전개1", 20), ("전개2", 20), ("전환점", 20), ("절정", 15), ("결말", 10)],
            8: [("도입", 10), ("전개1", 15), ("전개2", 15), ("갈등심화", 15), ("전환점", 15), ("절정1", 10), ("절정2", 10), ("결말", 10)]
        }
        scenes = scene_structure.get(settings['max_scenes'], scene_structure[4])
        for i, (name, ratio) in enumerate(scenes, 1):
            system_prompt += f"""### 장면 {i}: {name} (약 {ratio}%)
- 핵심 내용
- 대사 1-2개

"""

        system_prompt += """【 주의사항 】
- 각 장면의 목적 명확히
- 대사는 실제 사용할 수 있는 형태로
- 감정 흐름이 자연스럽게 연결되도록
- 장면 개수를 정확히 지킬 것!"""

        user_prompt = f"""【 영상 정보 】
- 카테고리: {video_category}
- 영상 길이: {duration_minutes}분
- 목표 분량: 약 {settings['target_length']}자
- 장면 개수: 정확히 {settings['max_scenes']}개

【 Step1 기획 결과 】
{step1_result}
"""
        if custom_directive:
            user_prompt += f"""
【 🔥 사용자 지침 (최우선) 】
{custom_directive}
"""

        user_prompt += "\n위 기획을 바탕으로 상세한 장면 구성을 만들어주세요."

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1500
        )

        result = completion.choices[0].message.content.strip()
        input_tokens = completion.usage.prompt_tokens if hasattr(completion, 'usage') and completion.usage else 0
        output_tokens = completion.usage.completion_tokens if hasattr(completion, 'usage') and completion.usage else 0

        # GPT-4o-mini 비용 계산 (원화)
        cost = round(input_tokens * 0.00021 + output_tokens * 0.00084, 2)

        print(f"[GPT-PLAN-2] 구조화 완료 - 토큰: {input_tokens}/{output_tokens}, 비용: ₩{cost}")

        return jsonify({
            'ok': True,
            'result': result,
            'tokens': input_tokens + output_tokens,
            'cost': cost,
            'step': 2
        })

    except Exception as e:
        print(f"[GPT-PLAN-2][ERROR] {str(e)}")
        return jsonify({'ok': False, 'error': str(e)}), 200


# ===== GPT-4o-mini 이미지 프롬프트 분석 API =====
@app.route('/api/drama/gpt-analyze-prompts', methods=['POST'])
def api_gpt_analyze_prompts():
    """GPT-4o-mini: 대본 분석 → 이미지 프롬프트 생성"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'ok': False, 'error': 'No data received'}), 400

        script = data.get('script', '')
        video_category = data.get('videoCategory', '간증')
        style_guide = data.get('styleGuide', '')
        narrator_metadata = data.get('narratorMetadata', {})

        if not script:
            return jsonify({'ok': False, 'error': '대본이 필요합니다.'}), 400

        # 화자 메타데이터 추출
        narrator_name = narrator_metadata.get('narrator_name', '')
        narrator_age = narrator_metadata.get('narrator_age')
        era = narrator_metadata.get('era', '')
        region = narrator_metadata.get('region', '')

        print(f"[GPT-ANALYZE-PROMPTS] 시작 - 카테고리: {video_category}, 대본 길이: {len(script)}자")
        if narrator_age:
            print(f"[GPT-ANALYZE-PROMPTS] 화자 정보: {narrator_name}, 현재 {narrator_age}세, 시대: {era}")

        system_prompt = """당신은 영상 제작을 위한 이미지 프롬프트 전문가입니다.

【 역할 】
주어진 대본을 분석하여 AI 이미지 생성에 최적화된 프롬프트를 생성합니다.

【 출력 형식 - 반드시 JSON 형태로 출력 】
```json
{
  "visualStyle": "전체 영상의 시각적 스타일 설명 (예: cinematic, warm lighting, soft focus)",
  "characters": [
    {
      "name": "캐릭터명 (한국어)",
      "nameEn": "캐릭터명 (영문)",
      "gender": "male 또는 female",
      "currentAge": 현재 나이 (숫자),
      "description": "캐릭터 설명 (한국어)",
      "imagePrompt": "영문 이미지 프롬프트 - 나이, 성별, 외모, 표정, 의상 등 상세히"
    }
  ],
  "scenes": [
    {
      "sceneNumber": 1,
      "timeContext": "현재 또는 회상 (예: 'present', 'flashback_childhood', 'flashback_youth', 'flashback_30s')",
      "characterAge": "이 장면에서 캐릭터의 나이 (회상이면 과거 나이)",
      "description": "장면 설명 (한국어)",
      "backgroundPrompt": "영문 배경 프롬프트 - 장소, 조명, 분위기, 시간대 등",
      "characterPrompt": "이 장면에서 캐릭터의 나이에 맞는 영문 외모 프롬프트 (회상 씬이면 젊은 외모로!)",
      "characterAction": "이 장면에서 캐릭터의 동작/표정"
    }
  ],
  "thumbnail": {
    "concept": "썸네일 콘셉트 요약 (한국어, 1문장)",
    "mainCharacter": "주인공 정보 (나이, 성별, 상황)",
    "emotion": "표현할 핵심 감정 (예: 눈물, 절망, 희망, 분노 등)",
    "imagePrompt": "영문 썸네일 이미지 프롬프트 (상세 작성 필수)",
    "textLines": ["1줄: 숫자/시간 + 충격적 상황", "2줄: 구체적 인물/사건", "3줄: 감정적 핵심 (강조색)", "4줄: 결말 암시/여운"],
    "highlightLine": 3,
    "colorScheme": "추천 색상 조합 (예: 따뜻한 금색 vs 차가운 파랑)"
  },
  "youtubeMetadata": {
    "title": "유튜브 제목 (50자 이내, 호기심 유발)",
    "description": "유튜브 설명 (200자 이내, 줄거리 요약 + 해시태그)",
    "tags": "쉼표로 구분된 10개 태그"
  }
}
```

【 프롬프트 작성 규칙 】
1. 캐릭터 프롬프트:
   - 일관된 외모 묘사 (같은 캐릭터는 항상 동일하게)
   - 구체적인 나이, 헤어스타일, 의상 색상
   - 표정과 포즈 기본값 포함
   - gender 필드는 반드시 "male" 또는 "female"로 명시
   - 예: "Korean woman, 35 years old, shoulder-length black hair, gentle smile, wearing navy cardigan over white blouse"

2. 배경 프롬프트:
   - 장면의 분위기를 살리는 조명
   - 구체적인 장소 설명
   - 시간대와 날씨 정보
   - 예: "cozy Korean apartment living room, warm evening light through window, wooden furniture, family photos on wall"

3. 🎯 회상 씬의 나이 처리 (매우 중요!):
   - 화자가 과거를 회상하면, 회상 씬에서는 그 시절 나이로 이미지를 생성해야 함!
   - 대본에서 언급된 시대(예: 1970년대)와 현재 화자 나이를 기준으로 회상 시점의 나이를 계산
   - 예: 현재 68세 화자가 1970년대(약 50년 전)를 회상 → 회상 씬에서는 15-18세로 표현
   - flashback_childhood: 어린이 (8-12세)
   - flashback_youth: 청소년/청년 (15-25세)
   - flashback_30s: 중년 (30-40세)
   - 예시:
     * 현재(present): "elderly Korean man, 68 years old, gray hair, wrinkled face"
     * 회상(flashback_youth, 1970년대): "young Korean man, 15 years old, short black hair, youthful face, wearing 1970s Korean clothing"
   - characterPrompt는 반드시 해당 장면의 나이에 맞게 작성!
   - 시대 배경도 반영: 1970년대면 그 시대 의상/배경으로

4. 일관성 유지:
   - 같은 시점의 캐릭터는 동일한 외모 유지
   - 전체적인 색감과 분위기 통일
   - 한 영상 내에서 스타일 일관성

4. 🎯 유튜브 썸네일 (thumbnail) - 매우 중요!:

   📸 이미지 프롬프트 필수 요소:
   - 구도: 클로즈업(얼굴 위주) 또는 미디엄 샷(상반신)
   - 주인공: 대본의 주인공 나이/성별/외모 정확히 반영
   - 표정: 극적인 감정 표현 (눈물, 절규, 눈을 감고 기도, 놀람 등)
   - 조명: 드라마틱한 조명 (림라이트, 역광, 황금빛, 명암 대비)
   - 배경: 블러 처리된 관련 장소 (교회, 병실, 집 등)
   - 품질: "cinematic, high quality, 4K, YouTube thumbnail style" 필수 포함

   📝 imagePrompt 작성 예시:
   "Dramatic close-up portrait of 72-year-old Korean elderly woman, gray hair in a neat bun, tears streaming down wrinkled cheeks, eyes looking up with desperate hope, wearing simple hanbok, warm golden rim lighting from behind, blurred church interior background, emotional cinematic lighting, high quality, 4K, YouTube thumbnail style, hyperrealistic"

   ✏️ textLines 작성 규칙 (4줄 필수):
   - 1줄: 숫자/시간 훅 (예: "53년간", "새벽 3시", "월급 200만원")
   - 2줄: 구체적 상황 (예: "믿음 없는 남편이", "암 선고를 받은 날")
   - 3줄: 감정 강조 ★이 줄이 강조색! (예: "무릎 꿇고 울었습니다", "기적이 일어났습니다")
   - 4줄: 결말 암시 (예: "그날 이후...", "하나님은 응답하셨습니다")

   🎨 colorScheme: 감정에 맞는 색상
   - 희망/감사: 따뜻한 금색, 주황
   - 슬픔/절망: 차가운 파랑, 회색
   - 기적/변화: 보라색, 핑크 → 금색 그라데이션

【 주의사항 】
- 모든 이미지 프롬프트는 반드시 영어로 작성
- 설명(description)은 한국어로 작성
- JSON 형식만 출력 (다른 텍스트 없이)
- 장면 수는 대본에 맞게 조절
- 썸네일은 반드시 포함"""

        user_prompt = f"""【 영상 카테고리 】
{video_category}

【 분석할 대본 】
{script}
"""
        # 화자 메타데이터가 있으면 추가
        if narrator_age:
            current_year = 2025
            if era and "년대" in str(era):
                # "1970s" 또는 "1970년대" 형식 파싱
                import re
                era_match = re.search(r'(\d{4})', str(era))
                if era_match:
                    era_year = int(era_match.group(1))
                    years_ago = current_year - era_year
                    flashback_age = narrator_age - years_ago
                    if flashback_age < 0:
                        flashback_age = 10  # 기본값
                else:
                    flashback_age = 15  # 기본값
            else:
                flashback_age = 15  # 기본값

            user_prompt += f"""
【 🎯 화자 정보 (매우 중요!) 】
- 화자 이름: {narrator_name or '주인공'}
- 화자 현재 나이: {narrator_age}세
- 회상 시대: {era or '과거'}
- 회상 시점 추정 나이: 약 {flashback_age}세
- 지역: {region or '한국'}

⚠️ 중요: 회상 씬에서는 화자를 {flashback_age}세 전후의 젊은 모습으로 표현해야 합니다!
현재 씬에서만 {narrator_age}세의 노인으로 표현하세요.
"""

        if style_guide:
            user_prompt += f"""
【 스타일 가이드 】
{style_guide}
"""

        user_prompt += """
위 대본을 분석하여 각 캐릭터와 장면에 대한 이미지 프롬프트를 JSON 형식으로 생성해주세요.
반드시 위에서 지정한 JSON 형식을 정확히 따라주세요.
회상 씬에서는 반드시 화자의 과거 나이에 맞는 젊은 외모로 프롬프트를 작성하세요!"""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=3000,
            temperature=0.7
        )

        result = completion.choices[0].message.content.strip()
        input_tokens = completion.usage.prompt_tokens if hasattr(completion, 'usage') and completion.usage else 0
        output_tokens = completion.usage.completion_tokens if hasattr(completion, 'usage') and completion.usage else 0

        # GPT-4o-mini 비용 계산 (원화)
        cost = round(input_tokens * 0.00021 + output_tokens * 0.00084, 2)

        # JSON 파싱 시도
        import re
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', result)
        if json_match:
            json_str = json_match.group(1)
        else:
            # JSON 블록이 없으면 전체를 JSON으로 시도
            json_str = result

        try:
            parsed_result = json.loads(json_str)
        except json.JSONDecodeError:
            # JSON 파싱 실패시 원본 반환
            parsed_result = None

        print(f"[GPT-ANALYZE-PROMPTS] 완료 - 토큰: {input_tokens}/{output_tokens}, 비용: ₩{cost}, JSON 파싱: {'성공' if parsed_result else '실패'}")

        return jsonify({
            'ok': True,
            'result': parsed_result if parsed_result else result,
            'rawResult': result,
            'tokens': input_tokens + output_tokens,
            'cost': cost,
            'parsed': parsed_result is not None
        })

    except Exception as e:
        print(f"[GPT-ANALYZE-PROMPTS][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 200


# ===== Step5: YouTube API =====

@app.route('/api/youtube/auth-status', methods=['GET'])
def api_youtube_auth_status_test():
    """
    YouTube 인증 상태 확인.
    데이터베이스에 저장된 OAuth 토큰을 확인합니다.
    """
    try:
        # 데이터베이스에서 토큰 로드
        token_data = load_youtube_token_from_db()

        if not token_data or not token_data.get('refresh_token'):
            print("[YOUTUBE-AUTH-STATUS] 토큰 없음 - 인증 필요")
            return jsonify({
                "ok": True,
                "authenticated": False,
                "connected": False,
                "mode": "setup",
                "channelName": None,
                "channelId": None,
                "message": "YouTube 계정을 연결해주세요."
            })

        # 토큰 유효성 검사 및 채널 정보 조회
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            creds = Credentials.from_authorized_user_info(token_data)

            # 토큰 만료 시 갱신
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # 갱신된 토큰 저장
                updated_token = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': list(creds.scopes) if creds.scopes else []
                }
                save_youtube_token_to_db(updated_token)
                print("[YOUTUBE-AUTH-STATUS] 토큰 갱신 완료")

            # YouTube API로 채널 정보 조회
            youtube = build('youtube', 'v3', credentials=creds)
            channel_response = youtube.channels().list(part="snippet", mine=True).execute()

            items = channel_response.get("items", [])
            if items:
                channel = items[0]
                channel_name = channel.get("snippet", {}).get("title", "채널")
                channel_id = channel.get("id")

                print(f"[YOUTUBE-AUTH-STATUS] 연결됨: {channel_name}")
                return jsonify({
                    "ok": True,
                    "authenticated": True,
                    "connected": True,
                    "mode": "live",
                    "channelName": channel_name,
                    "channelId": channel_id,
                    "message": "YouTube 연결됨"
                })
            else:
                print("[YOUTUBE-AUTH-STATUS] 채널 없음")
                return jsonify({
                    "ok": True,
                    "authenticated": True,
                    "connected": False,
                    "mode": "live",
                    "channelName": None,
                    "channelId": None,
                    "message": "연결된 채널이 없습니다."
                })

        except Exception as api_error:
            print(f"[YOUTUBE-AUTH-STATUS] API 오류: {api_error}")
            # 토큰은 있지만 API 호출 실패 - 일시적 오류일 수 있으므로 인증 상태는 유지
            # refresh_token이 있으면 나중에 갱신 가능하므로 authenticated: True 유지
            return jsonify({
                "ok": True,
                "authenticated": True,  # 토큰이 있으면 인증된 것으로 처리
                "connected": True,
                "mode": "live",
                "channelName": "YouTube 채널",  # 임시 이름 (API 호출 실패로 조회 불가)
                "channelId": None,
                "message": f"연결됨 (채널 정보 조회 중 오류: {str(api_error)[:50]})"
            })

    except Exception as e:
        print(f"[YOUTUBE-AUTH-STATUS] 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "ok": True,
            "authenticated": False,
            "connected": False,
            "mode": "test",
            "channelName": None,
            "channelId": None,
            "message": f"인증 확인 오류: {str(e)}"
        })


@app.route('/api/openrouter/credits', methods=['GET'])
def api_openrouter_credits():
    """
    OpenRouter 크레딧 잔액 조회
    """
    try:
        import requests as req

        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not openrouter_api_key:
            return jsonify({
                "ok": False,
                "error": "OpenRouter API 키가 설정되지 않았습니다."
            })

        # OpenRouter API로 크레딧 조회
        response = req.get(
            "https://openrouter.ai/api/v1/auth/key",
            headers={
                "Authorization": f"Bearer {openrouter_api_key}"
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            # data.data.limit (총 크레딧), data.data.usage (사용량)
            credit_data = data.get("data", {})
            limit = credit_data.get("limit", 0)  # 총 크레딧
            usage = credit_data.get("usage", 0)  # 사용량
            balance = limit - usage  # 잔액

            return jsonify({
                "ok": True,
                "balance": round(balance, 2),
                "limit": round(limit, 2),
                "usage": round(usage, 2),
                "formatted": f"${balance:.2f}"
            })
        else:
            return jsonify({
                "ok": False,
                "error": f"OpenRouter API 오류: {response.status_code}"
            })

    except Exception as e:
        print(f"[OPENROUTER-CREDITS] 오류: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        })


@app.route('/api/youtube/auth', methods=['GET'])
def api_youtube_auth_page():
    """
    YouTube OAuth 인증 시작 (GET 방식).
    Google OAuth URL로 직접 리다이렉트합니다.
    """
    try:
        from google_auth_oauthlib.flow import Flow
        from google.oauth2.credentials import Credentials

        # 환경 변수에서 OAuth 클라이언트 정보 가져오기
        client_id = os.getenv('YOUTUBE_CLIENT_ID') or os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('YOUTUBE_CLIENT_SECRET') or os.getenv('GOOGLE_CLIENT_SECRET')

        # Redirect URI 설정 - 기존 콜백 엔드포인트 사용
        redirect_uri = os.getenv('YOUTUBE_REDIRECT_URI')
        if not redirect_uri:
            redirect_uri = request.url_root.rstrip('/') + '/api/drama/youtube-callback'
            if redirect_uri.startswith('http://') and 'onrender.com' in redirect_uri:
                redirect_uri = redirect_uri.replace('http://', 'https://')

        print(f"[YOUTUBE-AUTH-GET] Redirect URI: {redirect_uri}")
        print(f"[YOUTUBE-AUTH-GET] Client ID: {client_id[:20] if client_id else 'None'}...")

        if not client_id or not client_secret:
            return """
            <!DOCTYPE html>
            <html>
            <head><title>YouTube 연결</title>
            <style>body{font-family:Arial;padding:50px;text-align:center}.error{background:#ffebee;padding:20px;border-radius:8px;margin:20px auto;max-width:500px;color:#c62828}.back-btn{margin-top:20px;padding:10px 20px;background:#1a73e8;color:white;border:none;border-radius:4px;cursor:pointer;text-decoration:none;display:inline-block}</style>
            </head>
            <body>
                <h1>⚠️ YouTube 연결 오류</h1>
                <div class="error">
                    <p>YouTube API 인증 정보가 설정되지 않았습니다.</p>
                    <p>Render 환경 변수에 <code>GOOGLE_CLIENT_ID</code>와 <code>GOOGLE_CLIENT_SECRET</code>을 설정해주세요.</p>
                </div>
                <a href="/image" class="back-btn">← Image Lab으로 돌아가기</a>
            </body>
            </html>
            """

        # force 파라미터 확인 (다른 계정 연결 시 사용)
        force_new_auth = request.args.get('force', '0') == '1'

        if force_new_auth:
            print("[YOUTUBE-AUTH-GET] force=1 - 새 계정 인증 강제 진행")

        # 이미 인증된 토큰 확인 (refresh_token이 있으면 재인증 불필요)
        # force=1이면 기존 토큰 무시하고 새 인증 진행
        token_data = load_youtube_token_from_db() if not force_new_auth else None
        if token_data and token_data.get('refresh_token'):
            try:
                from google.auth.transport.requests import Request
                credentials = Credentials.from_authorized_user_info(token_data)

                # refresh_token이 있으면 항상 갱신 가능 - 바로 리다이렉트
                if credentials.refresh_token:
                    # 만료된 경우 갱신 시도
                    if credentials.expired:
                        try:
                            credentials.refresh(Request())
                            # 갱신된 토큰 저장
                            updated_token = {
                                'token': credentials.token,
                                'refresh_token': credentials.refresh_token,
                                'token_uri': credentials.token_uri,
                                'client_id': credentials.client_id,
                                'client_secret': credentials.client_secret,
                                'scopes': list(credentials.scopes) if credentials.scopes else []
                            }
                            save_youtube_token_to_db(updated_token)
                            print("[YOUTUBE-AUTH-GET] 토큰 갱신 완료")
                        except Exception as refresh_err:
                            print(f"[YOUTUBE-AUTH-GET] 토큰 갱신 실패 (재인증 필요): {refresh_err}")
                            # 갱신 실패 시 재인증 필요 - 아래 OAuth 플로우로 진행
                            token_data = None

                    if token_data:  # 갱신 성공 또는 아직 유효한 경우
                        print("[YOUTUBE-AUTH-GET] 기존 토큰 유효 - 바로 리다이렉트")
                        return redirect('/image?youtube_auth=success')
            except Exception as e:
                print(f"[YOUTUBE-AUTH-GET] 기존 토큰 검증 실패 (재인증 진행): {e}")

        # OAuth 플로우 생성
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=[
                'https://www.googleapis.com/auth/youtube.upload',
                'https://www.googleapis.com/auth/youtube.readonly'
            ],
            redirect_uri=redirect_uri
        )

        # force=1이면 계정 선택 화면 표시, 아니면 동의 화면만
        oauth_prompt = 'select_account consent' if force_new_auth else 'consent'

        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt=oauth_prompt  # select_account: 계정 선택, consent: 동의 화면 (refresh_token 확보)
        )

        # 상태 저장
        save_oauth_state({
            'state': state,
            'redirect_uri': redirect_uri,
            'client_id': client_id,
            'client_secret': client_secret
        })

        print(f"[YOUTUBE-AUTH-GET] Google OAuth URL로 리다이렉트")
        print(f"[YOUTUBE-AUTH-GET] Auth URL: {auth_url[:100]}...")
        print(f"[YOUTUBE-AUTH-GET] State: {state}")
        return redirect(auth_url)

    except ImportError as e:
        print(f"[YOUTUBE-AUTH-GET] Import 오류: {e}")
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>YouTube 연결</title>
        <style>body{{font-family:Arial;padding:50px;text-align:center}}.error{{background:#ffebee;padding:20px;border-radius:8px;margin:20px auto;max-width:500px}}</style>
        </head>
        <body>
            <h1>⚠️ 라이브러리 오류</h1>
            <div class="error"><p>Google 인증 라이브러리가 설치되지 않았습니다.</p><p>{str(e)}</p></div>
            <a href="/image">← Image Lab으로 돌아가기</a>
        </body>
        </html>
        """
    except Exception as e:
        print(f"[YOUTUBE-AUTH-GET] 오류: {e}")
        import traceback
        traceback.print_exc()
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>YouTube 연결</title>
        <style>body{{font-family:Arial;padding:50px;text-align:center}}.error{{background:#ffebee;padding:20px;border-radius:8px;margin:20px auto;max-width:500px}}</style>
        </head>
        <body>
            <h1>⚠️ 연결 오류</h1>
            <div class="error"><p>{str(e)}</p></div>
            <a href="/image">← Image Lab으로 돌아가기</a>
        </body>
        </html>
        """


@app.route('/api/youtube/upload', methods=['POST'])
def youtube_upload():
    """
    YouTube 업로드 API.
    OAuth가 설정되어 있으면 실제 업로드, 아니면 테스트 모드로 동작
    """
    try:
        data = request.get_json() or {}

        video_path = data.get('videoPath', '')
        title = data.get('title', '제목 없음')
        description = data.get('description', '')
        tags = data.get('tags', [])
        category_id = data.get('categoryId', '22')  # People & Blogs
        privacy_status = data.get('privacyStatus') or 'private'  # 빈 문자열도 기본값 처리
        thumbnail_path = data.get('thumbnailPath')
        publish_at = data.get('publish_at')  # ISO 8601 예약 공개 시간
        channel_id = data.get('channelId')  # 선택된 채널 ID

        print(f"[YOUTUBE-UPLOAD] 업로드 요청 수신")
        print(f"  - 영상: {video_path}")
        print(f"  - 제목: {title}")
        print(f"  - 공개 설정: {privacy_status}")
        print(f"  - 예약 시간: {publish_at}")
        print(f"  - 채널 ID: {channel_id}")
        print(f"  - 썸네일: {thumbnail_path}")

        # 영상 파일 경로 처리
        if video_path and not video_path.startswith('http'):
            # 상대 경로를 절대 경로로 변환 (앞에 /가 있으면 제거)
            full_path = os.path.join(os.path.dirname(__file__), video_path.lstrip('/'))

            if not os.path.exists(full_path):
                print(f"[YOUTUBE-UPLOAD][WARN] 영상 파일 없음: {full_path}")
                return jsonify({
                    "ok": False,
                    "error": f"영상 파일을 찾을 수 없습니다: {video_path}"
                }), 200

            # 영상 파일 유효성 검사 (강화된 검증)
            try:
                import subprocess
                import json as json_module

                # 1단계: ffprobe로 메타데이터 확인 (코덱 정보 포함)
                probe_result = subprocess.run([
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration,size:stream=codec_type,codec_name,width,height',
                    '-of', 'json', full_path
                ], capture_output=True, text=True, timeout=30)

                if probe_result.returncode != 0:
                    print(f"[YOUTUBE-UPLOAD][ERROR] 손상된 영상 파일: {full_path}")
                    print(f"[YOUTUBE-UPLOAD][ERROR] ffprobe stderr: {probe_result.stderr[:500]}")
                    return jsonify({
                        "ok": False,
                        "error": f"손상된 영상 파일입니다. FFmpeg 인코딩 오류가 발생했을 수 있습니다."
                    }), 200

                probe_data = json_module.loads(probe_result.stdout)
                video_duration = float(probe_data.get('format', {}).get('duration', 0))
                video_size = int(probe_data.get('format', {}).get('size', 0))

                # 스트림 확인 (비디오/오디오 있는지 + 코덱 정보)
                streams = probe_data.get('streams', [])
                video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
                audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
                has_video = video_stream is not None
                has_audio = audio_stream is not None

                video_codec = video_stream.get('codec_name', 'unknown') if video_stream else 'none'
                audio_codec = audio_stream.get('codec_name', 'unknown') if audio_stream else 'none'
                video_width = video_stream.get('width', 0) if video_stream else 0
                video_height = video_stream.get('height', 0) if video_stream else 0

                print(f"[YOUTUBE-UPLOAD] 영상 검증: duration={video_duration:.1f}s, size={video_size/1024/1024:.1f}MB")
                print(f"[YOUTUBE-UPLOAD] 영상 검증: video={has_video} ({video_codec}, {video_width}x{video_height}), audio={has_audio} ({audio_codec})")

                # 파일 크기 최소값 검사 (100KB 미만은 손상 가능성)
                if video_size < 100 * 1024:
                    print(f"[YOUTUBE-UPLOAD][ERROR] 파일 크기가 너무 작음: {video_size/1024:.1f}KB")
                    return jsonify({
                        "ok": False,
                        "error": f"영상 파일 크기가 너무 작습니다 ({video_size/1024:.1f}KB). 인코딩이 실패했을 수 있습니다."
                    }), 200

                if video_duration < 1:
                    print(f"[YOUTUBE-UPLOAD][ERROR] 영상 길이가 너무 짧음: {video_duration}초")
                    return jsonify({
                        "ok": False,
                        "error": f"영상 길이가 너무 짧습니다 ({video_duration:.1f}초). 인코딩 오류가 발생했을 수 있습니다."
                    }), 200

                if not has_video:
                    print(f"[YOUTUBE-UPLOAD][ERROR] 비디오 스트림 없음")
                    return jsonify({
                        "ok": False,
                        "error": "영상에 비디오 스트림이 없습니다. 인코딩 오류가 발생했을 수 있습니다."
                    }), 200

                if not has_audio:
                    print(f"[YOUTUBE-UPLOAD][ERROR] 오디오 스트림 없음")
                    return jsonify({
                        "ok": False,
                        "error": "영상에 오디오 스트림이 없습니다. YouTube 업로드에는 오디오가 필요합니다."
                    }), 200

                # 해상도 검사 (너무 작거나 0이면 문제)
                if video_width < 100 or video_height < 100:
                    print(f"[YOUTUBE-UPLOAD][ERROR] 비정상 해상도: {video_width}x{video_height}")
                    return jsonify({
                        "ok": False,
                        "error": f"영상 해상도가 비정상입니다 ({video_width}x{video_height}). 인코딩 오류가 발생했을 수 있습니다."
                    }), 200

                # 2단계: 실제 프레임 디코딩 테스트 (ffmpeg로 첫 1초 읽기)
                print(f"[YOUTUBE-UPLOAD] 프레임 디코딩 테스트 시작...")
                decode_result = subprocess.run([
                    'ffmpeg', '-v', 'error',
                    '-i', full_path,
                    '-t', '1',  # 첫 1초만
                    '-f', 'null', '-'  # 출력 없이 디코딩만
                ], capture_output=True, text=True, timeout=60)

                if decode_result.returncode != 0:
                    print(f"[YOUTUBE-UPLOAD][ERROR] 프레임 디코딩 실패")
                    print(f"[YOUTUBE-UPLOAD][ERROR] ffmpeg stderr: {decode_result.stderr[:500]}")
                    return jsonify({
                        "ok": False,
                        "error": f"영상 프레임 디코딩에 실패했습니다. 파일이 손상되었을 수 있습니다."
                    }), 200

                print(f"[YOUTUBE-UPLOAD] 영상 검증 통과!")

            except subprocess.TimeoutExpired:
                print(f"[YOUTUBE-UPLOAD][ERROR] 영상 검증 타임아웃")
                return jsonify({
                    "ok": False,
                    "error": "영상 파일 검증 타임아웃. 파일이 손상되었을 수 있습니다."
                }), 200
            except Exception as e:
                print(f"[YOUTUBE-UPLOAD][ERROR] 영상 검증 실패: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({
                    "ok": False,
                    "error": f"영상 파일 검증 중 오류 발생: {str(e)}"
                }), 200
        else:
            full_path = video_path

        # 썸네일 경로 처리
        full_thumbnail_path = None
        if thumbnail_path:
            if thumbnail_path.startswith('http'):
                full_thumbnail_path = thumbnail_path
            else:
                # 상대 경로를 절대 경로로 변환 (앞에 /가 있으면 제거)
                full_thumbnail_path = os.path.join(os.path.dirname(__file__), thumbnail_path.lstrip('/'))

        # 실제 업로드 시도 (DB 토큰 직접 사용)
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload

            # DB에서 토큰 로드 (선택된 채널의 토큰 우선)
            token_data = load_youtube_token_from_db(channel_id) if channel_id else load_youtube_token_from_db()

            if not token_data or not token_data.get('refresh_token'):
                print(f"[YOUTUBE-UPLOAD] 테스트 모드 - DB에 토큰 없음 (channel_id: {channel_id})")
            else:
                # Credentials 객체 생성
                creds = Credentials(
                    token=token_data.get('token'),
                    refresh_token=token_data.get('refresh_token'),
                    token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                    client_id=token_data.get('client_id') or os.getenv('YOUTUBE_CLIENT_ID'),
                    client_secret=token_data.get('client_secret') or os.getenv('YOUTUBE_CLIENT_SECRET'),
                    scopes=token_data.get('scopes', ['https://www.googleapis.com/auth/youtube.upload'])
                )

                # 토큰 만료 시 갱신
                if creds.expired and creds.refresh_token:
                    print("[YOUTUBE-UPLOAD] 토큰 갱신 중...")
                    creds.refresh(Request())
                    # 갱신된 토큰 저장
                    updated_token = {
                        'token': creds.token,
                        'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri,
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'scopes': list(creds.scopes) if creds.scopes else []
                    }
                    save_youtube_token_to_db(updated_token, channel_id=channel_id)

                # YouTube API 클라이언트 생성
                youtube = build('youtube', 'v3', credentials=creds)

                # 업로드 실행
                print(f"[YOUTUBE-UPLOAD] 실제 업로드 시작 - 파일: {full_path}")

                body = {
                    'snippet': {
                        'title': title,
                        'description': description,
                        'tags': tags if tags else [],
                        'categoryId': category_id
                    },
                    'status': {
                        'privacyStatus': privacy_status,
                        'selfDeclaredMadeForKids': False
                    }
                }

                # 예약 공개 설정 (publish_at이 있으면 적용)
                if publish_at:
                    body['status']['publishAt'] = publish_at
                    body['status']['privacyStatus'] = 'private'  # 예약 시 반드시 비공개
                    print(f"[YOUTUBE-UPLOAD] 예약 공개 설정: {publish_at}")

                media = MediaFileUpload(
                    full_path,
                    mimetype='video/mp4',
                    resumable=True,
                    chunksize=1024*1024  # 1MB chunks
                )

                request_obj = youtube.videos().insert(
                    part='snippet,status',
                    body=body,
                    media_body=media
                )

                response = None
                while response is None:
                    status, response = request_obj.next_chunk()
                    if status:
                        print(f"[YOUTUBE-UPLOAD] 진행률: {int(status.progress() * 100)}%")

                video_id = response.get('id')
                video_url = f"https://www.youtube.com/watch?v={video_id}"

                print(f"[YOUTUBE-UPLOAD] 업로드 완료, 영상 상태 확인 중...")

                # 업로드 후 영상 상태 확인 (YouTube가 영상을 거부했는지)
                try:
                    video_check = youtube.videos().list(
                        part='status,processingDetails',
                        id=video_id
                    ).execute()

                    if video_check.get('items'):
                        item = video_check['items'][0]
                        upload_status = item.get('status', {}).get('uploadStatus', 'unknown')
                        rejection_reason = item.get('status', {}).get('rejectionReason', '')
                        failure_reason = item.get('status', {}).get('failureReason', '')
                        processing_status = item.get('processingDetails', {}).get('processingStatus', 'unknown')

                        print(f"[YOUTUBE-UPLOAD] 상태: uploadStatus={upload_status}, processingStatus={processing_status}")

                        if rejection_reason:
                            print(f"[YOUTUBE-UPLOAD][ERROR] 거부됨: {rejection_reason}")
                            return jsonify({
                                "ok": False,
                                "error": f"YouTube가 영상을 거부했습니다: {rejection_reason}"
                            }), 200

                        if failure_reason:
                            print(f"[YOUTUBE-UPLOAD][ERROR] 실패: {failure_reason}")
                            return jsonify({
                                "ok": False,
                                "error": f"YouTube 처리 실패: {failure_reason}"
                            }), 200

                        if upload_status == 'rejected':
                            print(f"[YOUTUBE-UPLOAD][ERROR] 영상이 거부됨")
                            return jsonify({
                                "ok": False,
                                "error": "YouTube가 영상을 거부했습니다. 영상 형식을 확인해주세요."
                            }), 200

                        if upload_status == 'failed':
                            print(f"[YOUTUBE-UPLOAD][ERROR] 업로드 실패 상태")
                            return jsonify({
                                "ok": False,
                                "error": "YouTube 업로드가 실패했습니다. 영상 파일을 확인해주세요."
                            }), 200
                    else:
                        print(f"[YOUTUBE-UPLOAD][WARN] 영상 정보 조회 실패 - items 없음")
                except Exception as check_error:
                    print(f"[YOUTUBE-UPLOAD][WARN] 상태 확인 실패 (계속 진행): {check_error}")

                print(f"[YOUTUBE-UPLOAD] 업로드 성공: {video_url}")

                # 썸네일 업로드 (썸네일 경로가 있는 경우)
                thumbnail_uploaded = False
                if thumbnail_path:
                    try:
                        # 썸네일 전체 경로 (상대 경로인 경우 처리)
                        if thumbnail_path.startswith('/'):
                            thumb_full_path = thumbnail_path[1:]  # 앞의 / 제거
                        else:
                            thumb_full_path = thumbnail_path

                        # /output/ → outputs/ 경로 변환 (AI 썸네일용)
                        if thumb_full_path.startswith('output/'):
                            thumb_full_path = 'outputs/' + thumb_full_path[7:]  # output/ 제거 후 outputs/ 추가

                        print(f"[YOUTUBE-UPLOAD] 썸네일 경로 변환: {thumbnail_path} → {thumb_full_path}")

                        # 파일 존재 확인
                        if os.path.exists(thumb_full_path):
                            print(f"[YOUTUBE-UPLOAD] 썸네일 업로드 시작: {thumb_full_path}")

                            # 썸네일 MIME 타입 결정
                            thumb_ext = os.path.splitext(thumb_full_path)[1].lower()
                            thumb_mime = {
                                '.jpg': 'image/jpeg',
                                '.jpeg': 'image/jpeg',
                                '.png': 'image/png',
                                '.gif': 'image/gif'
                            }.get(thumb_ext, 'image/jpeg')

                            thumb_media = MediaFileUpload(
                                thumb_full_path,
                                mimetype=thumb_mime,
                                resumable=True
                            )

                            thumb_request = youtube.thumbnails().set(
                                videoId=video_id,
                                media_body=thumb_media
                            )
                            thumb_response = thumb_request.execute()
                            thumbnail_uploaded = True
                            print(f"[YOUTUBE-UPLOAD] 썸네일 업로드 성공!")
                        else:
                            print(f"[YOUTUBE-UPLOAD] 썸네일 파일 없음: {thumb_full_path}")
                    except Exception as thumb_error:
                        print(f"[YOUTUBE-UPLOAD] 썸네일 업로드 실패: {thumb_error}")
                        import traceback
                        traceback.print_exc()

                return jsonify({
                    "ok": True,
                    "mode": "live",
                    "videoId": video_id,
                    "videoUrl": video_url,
                    "status": "uploaded",
                    "thumbnailUploaded": thumbnail_uploaded,
                    "message": "YouTube 업로드 완료!" + (" (썸네일 포함)" if thumbnail_uploaded else ""),
                    "metadata": {
                        "title": title,
                        "privacyStatus": privacy_status
                    }
                })

        except ImportError as e:
            print(f"[YOUTUBE-UPLOAD] 라이브러리 없음: {e}")
        except Exception as upload_error:
            print(f"[YOUTUBE-UPLOAD] 업로드 오류: {upload_error}")
            import traceback
            traceback.print_exc()

        # 테스트 모드: 가상의 videoId 생성
        import random
        import string
        fake_video_id = ''.join(random.choices(string.ascii_letters + string.digits, k=11))

        return jsonify({
            "ok": True,
            "mode": "test",
            "videoId": fake_video_id,
            "videoUrl": f"https://www.youtube.com/watch?v={fake_video_id}",
            "status": "uploaded",
            "message": "테스트 모드: 실제 업로드는 수행되지 않았습니다. OAuth 설정 후 실제 업로드가 가능합니다.",
            "metadata": {
                "title": title,
                "description": description[:100] + "..." if len(description) > 100 else description,
                "tags": tags,
                "categoryId": category_id,
                "privacyStatus": privacy_status
            }
        })

    except Exception as e:
        print(f"[YOUTUBE-UPLOAD][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 200


@app.route('/api/drama/generate-thumbnails', methods=['POST'])
def generate_thumbnails():
    """
    썸네일 3종 생성 API.
    Step4에서 생성된 이미지를 기반으로 썸네일 후보 생성
    """
    try:
        data = request.get_json() or {}

        base_image_url = data.get('baseImageUrl')
        title = data.get('title', '')
        channel_type = data.get('channelType', 'nostalgia')
        styles = data.get('styles', ['warm', 'dramatic', 'nostalgic'])

        print(f"[DRAMA-THUMBNAIL] 썸네일 생성 요청 - 스타일: {styles}")

        # outputs 폴더에서 기존 썸네일 확인
        outputs_dir = os.path.join(os.path.dirname(__file__), 'outputs')
        thumbnail_file = os.path.join(outputs_dir, 'thumbnail_output.json')

        if os.path.exists(thumbnail_file):
            with open(thumbnail_file, 'r', encoding='utf-8') as f:
                thumb_data = json.load(f)

            candidates = thumb_data.get('candidates', [])
            if candidates:
                print(f"[DRAMA-THUMBNAIL] 기존 썸네일 {len(candidates)}개 발견")

                thumbnails = []
                for idx, candidate in enumerate(candidates):
                    thumb_url = candidate.get('url') or candidate.get('image_url')
                    if thumb_url:
                        thumbnails.append({
                            "url": thumb_url,
                            "style": styles[idx] if idx < len(styles) else "default",
                            "path": candidate.get('path')
                        })

                if thumbnails:
                    return jsonify({
                        "ok": True,
                        "thumbnails": thumbnails,
                        "source": "cached"
                    })

        # 기존 썸네일이 없으면 Step2 이미지를 썸네일로 사용
        if base_image_url:
            thumbnails = [
                {"url": base_image_url, "style": "warm", "path": None},
                {"url": base_image_url, "style": "dramatic", "path": None},
                {"url": base_image_url, "style": "nostalgic", "path": None}
            ]

            return jsonify({
                "ok": True,
                "thumbnails": thumbnails,
                "source": "base_image",
                "message": "기본 이미지를 썸네일로 사용합니다. 전용 썸네일 생성은 추후 지원 예정입니다."
            })

        # 이미지도 없으면 플레이스홀더
        return jsonify({
            "ok": True,
            "thumbnails": [
                {"url": "/static/images/placeholder-thumbnail.png", "style": "warm", "path": None},
                {"url": "/static/images/placeholder-thumbnail.png", "style": "dramatic", "path": None},
                {"url": "/static/images/placeholder-thumbnail.png", "style": "nostalgic", "path": None}
            ],
            "source": "placeholder",
            "message": "썸네일 이미지가 없습니다. Step2에서 이미지를 먼저 생성해주세요."
        })

    except Exception as e:
        print(f"[DRAMA-THUMBNAIL][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== Product Lab API =====
@app.route('/api/product/analyze-script', methods=['POST'])
def api_product_analyze_script():
    """상품 대본 분석 - AI가 씬과 이미지 프롬프트를 자동 생성"""
    try:
        from openai import OpenAI
        client = OpenAI()

        data = request.get_json()
        product_name = data.get('product_name', '상품')
        category = data.get('category', 'etc')
        script = data.get('script', '')

        if not script:
            return jsonify({"ok": False, "error": "대본이 필요합니다"}), 400

        # GPT-4o-mini로 대본 분석
        system_prompt = """당신은 상품 홍보 영상 제작 전문가입니다.
사용자가 제공한 상품 설명 대본을 분석하여 영상 씬으로 분리하고, 각 씬에 맞는 이미지 프롬프트를 생성합니다.

응답은 반드시 다음 JSON 형식으로 해주세요:
{
  "scenes": [
    {
      "scene_number": 1,
      "narration": "한국어 나레이션 텍스트",
      "image_prompt": "English image generation prompt for this scene"
    }
  ]
}

이미지 프롬프트 작성 규칙:
1. 영문으로 작성
2. 상품을 돋보이게 하는 프로페셔널한 제품 사진 스타일
3. 밝고 깨끗한 배경, 좋은 조명
4. 상품 카테고리에 맞는 분위기 (전자제품=모던/미니멀, 뷰티=소프트/엘레강스, 식품=신선/맛있는)"""

        user_prompt = f"""상품명: {product_name}
카테고리: {category}

대본:
{script}

위 대본을 3~6개의 씬으로 분리하고, 각 씬에 맞는 이미지 프롬프트를 생성해주세요.
나레이션은 원본 대본의 문장을 그대로 사용하거나 약간 다듬어서 사용하세요."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        return jsonify({
            "ok": True,
            "scenes": result.get("scenes", []),
            "product_name": product_name,
            "category": category
        })

    except Exception as e:
        print(f"[PRODUCT-ANALYZE][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== Image Lab API =====
def load_prompt_guides():
    """프롬프트 가이드 파일들 로드"""
    guides = {}

    # 전문가 프롬프트 가이드
    try:
        with open('guides/prompt-expert-guide.json', 'r', encoding='utf-8') as f:
            guides['expert'] = json.load(f)
    except:
        guides['expert'] = None

    # 한국인 시니어 이미지 가이드
    try:
        with open('guides/korean-senior-image-prompts.json', 'r', encoding='utf-8') as f:
            guides['korean_senior'] = json.load(f)
    except:
        guides['korean_senior'] = None

    return guides


@app.route('/api/image/analyze-script', methods=['POST'])
def api_image_analyze_script():
    """이미지 제작용 대본 분석 - 씬 분리 + 썸네일/이미지 프롬프트 생성"""
    try:
        from openai import OpenAI
        client = OpenAI()

        data = request.get_json()
        script = data.get('script', '')
        content_type = data.get('content_type', 'drama')
        image_style = data.get('image_style', 'realistic')
        image_count = data.get('image_count', 4)  # 기본 4개
        audience = data.get('audience', 'senior')  # 시니어/일반 타겟
        category = data.get('category', '').strip()  # 카테고리 (뉴스 등)
        output_language = data.get('output_language', 'ko')  # 출력 언어 (ko/en/ja/auto)

        # 언어 설정 매핑
        language_config = {
            'ko': {'name': 'Korean', 'native': '한국어', 'instruction': 'Write ALL titles, description, thumbnail text, and narration in Korean (한국어).'},
            'en': {'name': 'English', 'native': 'English', 'instruction': 'Write ALL titles, description, thumbnail text, and narration in English.'},
            'ja': {'name': 'Japanese', 'native': '日本語', 'instruction': 'Write ALL titles, description, thumbnail text, and narration in Japanese (日本語).'},
        }

        # 자동 감지 시 스크립트 언어 분석
        if output_language == 'auto':
            import re as re_module  # 스코프 문제 해결

            def detect_script_language(text):
                """스크립트 언어 감지 (한국어/영어/일본어)"""
                if not text:
                    return 'en'
                korean_chars = len(re_module.findall(r'[가-힣]', text))
                japanese_chars = len(re_module.findall(r'[\u3040-\u309F\u30A0-\u30FF]', text))
                total_chars = len(re_module.sub(r'\s', '', text))
                if total_chars == 0:
                    return 'en'
                korean_ratio = korean_chars / total_chars
                japanese_ratio = japanese_chars / total_chars
                if korean_ratio > 0.3:
                    return 'ko'
                elif japanese_ratio > 0.2:
                    return 'ja'
                return 'en'

            detected_lang = detect_script_language(script)
            print(f"[IMAGE-ANALYZE] Auto-detected language: {detected_lang} (from script)")
            output_language = detected_lang  # 감지된 언어로 변경

        lang_config = language_config.get(output_language, language_config['ko'])

        if not script:
            return jsonify({"ok": False, "error": "대본이 필요합니다"}), 400

        # 시니어 썸네일 가이드 로드
        senior_thumbnail_guide = None
        try:
            with open('guides/senior-thumbnail-guide.json', 'r', encoding='utf-8') as f:
                senior_thumbnail_guide = json.load(f)
        except:
            pass

        # 가이드 파일 로드
        guides = load_prompt_guides()
        korean_senior = guides.get('korean_senior', {})
        expert_guide = guides.get('expert', {})

        # 시대 감성 스타일 가이드
        era_guide = korean_senior.get('era_1970s_1980s', {}).get('visual_style', {}) if korean_senior else {}
        style_guides = {
            'realistic': 'photorealistic, high quality photography, natural lighting, sharp focus, cinematic composition',
            'animation': 'STICKMAN_STYLE'  # 특별 처리 필요
        }

        style_desc = style_guides.get(image_style, 'photorealistic')

        # GPT-5.1이 대본 내용을 분석해서 카테고리를 자동 감지하도록 함
        # (더 이상 Google Sheets의 category 컬럼에 의존하지 않음)

        # 애니메이션(스틱맨) 스타일 전용 시스템 프롬프트 - audience 반영
        if image_style == 'animation':
            # audience별 썸네일 규칙 설정
            if audience == 'general':
                thumb_length = "4-7자"
                thumb_color = "#FFFFFF"
                thumb_outline = "#000000"
                thumb_style = "자극형/충격형 (결국 터졌다, 이게 실화?, 소름 돋았다)"
            else:  # senior
                thumb_length = "8-12자"
                thumb_color = "#FFD700"
                thumb_outline = "#000000"
                thumb_style = "회상형/후회형 (그날을 잊지 않는다, 하는게 아니었다, 늦게 알았다)"

            # GPT가 자동으로 카테고리를 감지하고 적절한 썸네일 스타일을 선택하도록 함
            # 뉴스/시사 vs 일반 스토리 두 가지 스타일 모두 제공
            ai_prompts_section = f'''    "detected_category": "news 또는 story 중 하나 선택 (대본 분석 결과)",
    "ai_prompts": {{
      // ★ detected_category가 "news"일 때 사용 (정치, 경제, 시사, 사회 이슈, 뉴스 보도 형식의 대본)
      // 뉴스 스타일: KBS/MBC/SBS 뉴스 방송 썸네일처럼 실제 사진 + 뉴스 그래픽
      "A": {{
        "description": "뉴스 스타일 A: 실제 한국 뉴스 방송 썸네일 - KBS/MBC/SBS 스타일",
        "prompt": "Korean TV news broadcast YouTube thumbnail exactly like KBS MBC SBS news. 16:9 aspect ratio. Real photo of news anchor or reporter in professional attire on one side. Large bold Korean headline text in WHITE or YELLOW with quotation marks. Dark blue or navy gradient background. RED accent bar with '단독' or '속보' badge at top. Multiple text layers - main headline + sub headline. News ticker style bar at bottom. Professional broadcast journalism aesthetic. Photorealistic news studio look.",
        "text_overlay": {{"main": "따옴표 헤드라인", "sub": "핵심 요약"}},
        "style": "korean-tv-news, broadcast, photorealistic"
      }},
      "B": {{
        "description": "뉴스 스타일 B: 인터뷰/발언 강조",
        "prompt": "Korean news interview thumbnail with real person photo. 16:9 aspect ratio. Split layout - interviewee photo on left, large Korean quote text on right in quotation marks. White/yellow bold text on dark navy background. Red accent. Lower-third name tag. Professional broadcast news look. NO cartoon, photorealistic only.",
        "text_overlay": {{"main": "인용문", "sub": "발언자"}},
        "style": "interview-quote, broadcast"
      }},
      "C": {{
        "description": "뉴스 스타일 C: 속보/이슈 중심",
        "prompt": "Korean breaking news style thumbnail with event photo. 16:9 aspect ratio. Background photo (blurred/darkened). VERY LARGE white/yellow Korean headline. Red '속보' badge prominent. News channel style graphics. Photojournalism aesthetic.",
        "text_overlay": {{"main": "대형 헤드라인", "sub": "추가 정보"}},
        "style": "breaking-news, headline"
      }}

      // ★ detected_category가 "story"일 때 사용 (드라마, 감성, 인간관계, 일상 이야기)
      // 스토리 스타일: 웹툰/만화 일러스트 + 감정 표현
      "A": {{
        "description": "스토리 스타일 A: 감정/표정 중심",
        "prompt": "Cartoon illustration style YouTube thumbnail, 16:9 aspect ratio. Character with exaggerated emotional expression (shock, surprise, joy). Vibrant colors, high contrast. NO realistic humans, comic/cartoon style only.",
        "text_overlay": {{"main": "{thumb_length} 감정 텍스트", "sub": "optional"}},
        "style": "emotional, cartoon"
      }},
      "B": {{
        "description": "스토리 스타일 B: Before/After 대비",
        "prompt": "Split screen YouTube thumbnail, 16:9 aspect ratio. Before/After comparison layout. Cartoon style, vibrant contrasting colors. Clear visual storytelling. NO realistic photos.",
        "text_overlay": {{"main": "대비 텍스트", "sub": "optional"}},
        "style": "narrative, contrast"
      }},
      "C": {{
        "description": "스토리 스타일 C: 타이포그래피 중심",
        "prompt": "Typography-focused YouTube thumbnail, 16:9 aspect ratio. Large bold Korean text. Gradient background. Minimal illustration. High contrast colors.",
        "text_overlay": {{"main": "{thumb_length} 메인 문구", "sub": "optional"}},
        "style": "typography, bold"
      }}
    }}'''

            ai_prompts_rules = f"""## ⚠️ CRITICAL: 카테고리 자동 감지 및 썸네일 스타일 선택 ⚠️

### 1단계: 대본 내용 분석하여 카테고리 감지
대본을 읽고 아래 기준으로 "detected_category"를 결정하세요:

**"news" 선택 기준** (하나라도 해당되면 news):
- 정치인, 대통령, 국회, 정당 언급
- 경제 지표, 주가, 환율, 부동산 언급
- 사건/사고 보도 형식 (누가, 언제, 어디서, 무엇을)
- 사회 이슈, 논쟁, 갈등 다룸
- 인터뷰, 발언, 기자회견 형식
- 법원, 검찰, 재판 관련

**"story" 선택 기준**:
- 개인의 감정, 경험, 회고
- 인간관계, 가족, 사랑 이야기
- 일상적인 에피소드
- 교훈, 깨달음, 감동 스토리
- 드라마/영화 같은 서사 구조

### 2단계: 카테고리에 맞는 썸네일 생성

**detected_category = "news"일 때:**
- ai_prompts에 뉴스 스타일 A/B/C 사용
- 실제 사진 + 뉴스 그래픽 (KBS/MBC/SBS 스타일)
- 따옴표 헤드라인, 빨간 '속보' 배지
- ⚠️ 절대 만화/일러스트 금지!

**detected_category = "story"일 때:**
- ai_prompts에 스토리 스타일 A/B/C 사용
- 웹툰/만화 일러스트 스타일
- 감정 표현, 캐릭터 중심
- ⚠️ 실사 사진 금지!

### 출력 형식 (중요!)
"detected_category": "news" 또는 "story",
"ai_prompts": {{
  "A": {{ ... 선택된 스타일의 A ... }},
  "B": {{ ... 선택된 스타일의 B ... }},
  "C": {{ ... 선택된 스타일의 C ... }}
}}"""

            system_prompt = f"""You are an AI that generates image prompts for COLLAGE STYLE: Detailed Anime Background + 2D Stickman Character.

## ⚠️ LANGUAGE RULE (CRITICAL!) ⚠️
Output Language: {lang_config['name']} ({lang_config['native']})
{lang_config['instruction']}
- YouTube titles, description → {lang_config['name']}
- Thumbnail text → {lang_config['name']}
- Narration → {lang_config['name']}
- ONLY image_prompt → Always in English (for AI image generation)

Target Audience: {'General (20-40s)' if audience == 'general' else 'Senior (50-70s)'}

## CORE CONCEPT (CRITICAL!)
The key visual style is:
1. Background = DETAILED ANIME STYLE (slice-of-life anime, Ghibli-inspired, warm colors, soft lighting)
2. Stickman = SIMPLE WHITE BODY + CONSISTENT FACE (round head, TWO DOT EYES, small mouth, thin eyebrows)
3. Combination = "CONTRAST COLLAGE" - simple stickman contrasts against detailed anime background
4. ABSOLUTELY NO OTHER CHARACTERS - NO anime characters, NO realistic humans, NO elderly people, NO grandpa, NO grandma, NO senior citizens, ONLY the simple white stickman!

⚠️ FORBIDDEN ELEMENTS (NEVER INCLUDE):
- ANY realistic human faces or bodies
- ANY elderly/senior/grandpa/grandma characters
- ANY anime-style human characters
- ANY silhouettes of people other than the stickman

This creates contrast between the detailed anime world and the simple stickman.

## PROMPT STRUCTURE (ALWAYS FOLLOW THIS ORDER)
(detailed anime background, slice-of-life style, Ghibli-inspired) +
(simple white stickman with round head, two black dot eyes, small mouth, thin eyebrows, black outline body) +
(contrast collage style) +
(no other characters)

## STICKMAN CHARACTER DESCRIPTION (USE THIS EXACT PHRASE - CRITICAL FOR CONSISTENCY!)
"simple white stickman with round head, two black dot eyes, small curved mouth, thin eyebrows, black outline body, [pose/emotion]. NO other characters."

The stickman MUST ALWAYS have these facial features in EVERY image:
- Round white head
- TWO BLACK DOT EYES (always visible)
- Small curved mouth (can show emotion: smile, frown, neutral)
- Thin eyebrows (can show emotion: raised, lowered)

## MANDATORY STYLE KEYWORDS (MUST INCLUDE IN EVERY PROMPT)
- detailed anime background, slice-of-life style
- Ghibli-inspired warm colors and soft lighting
- simple white stickman with round head, two black dot eyes, small mouth, thin eyebrows
- black outline body, clean minimal flat style
- contrast between detailed background and minimal character
- NO anime characters, NO realistic humans, NO elderly, NO grandpa, NO grandma, ONLY stickman
- seamless composition
- CHARACTER FACE MUST BE CLEARLY VISIBLE

## 🎨 썸네일 전략 규칙 (중요!)

너는 유튜브 썸네일 전략가이자 카피라이터다.
역할:
1) 영상의 핵심 메시지를 가장 짧고 강하게 요약하는 썸네일 문구를 만든다.
2) 썸네일 문구 + 영상 제목 + 영상 도입부가 하나의 스토리처럼 이어지도록 설계한다.
3) 단순 클릭(CTR)뿐 아니라, 클릭 후 시청 지속 시간(watch time)까지 좋아지도록 돕는다.

### 기본 원칙
1. **어그로 금지**
   - 썸네일이 약속한 내용은 영상 내용과 실제로 일치해야 한다.
   - 썸네일에서 던진 메시지/질문/약속은 영상 초반 10초 안에 등장해야 한다.
   - 시청자가 "속았다"는 느낌을 받으면 안 된다.

2. **성과 기준**
   - CTR은 5~10%면 보통~양호, 10% 이상이면 매우 좋다고 가정한다.
   - 클릭률만이 아니라, "썸네일-제목-내용 일치"를 통해 시청 지속에도 도움을 줘야 한다.
   - 목표: "정직한 어그로" = 시선을 잡되, 내용이 충분히 그 기대를 채우도록 설계.

### 썸네일 문구(카피) 규칙
1. **길이와 줄 수**
   - 썸네일 문구는 **10~15자 이내** (한글 기준)
   - 최대 2줄까지 허용
   - 줄바꿈이 필요하면 "\\n"을 사용해 최대 1번까지만 줄을 나눈다.

2. **문장 스타일** (우선 고려)
   - 질문형: "왜 다 여기서 망하냐?"
   - 문제제기형: "이 구간에서 다 털린다"
   - 해결/이점형: "퇴근 후 3시간, 이걸로 버는 법"
   - 숫자 + 위험/기회형: "3가지만 몰라서 손해 본다"

3. **단어 선택**
   - 감정을 자극하지만 과한 선정성은 피한다.
   - 사용할 수 있는 강한 단어: "망한다", "손해 본다", "끝판왕", "미쳤다", "절대", "필수"
   - 단, 실제 내용이 받쳐줄 때만 사용. 과장/왜곡 금지.

4. **제목과의 관계**
   - 썸네일 문구는 영상 제목과 똑같이 쓰지 않는다.
   - 썸네일 문구 = 감정, 호기심, 위기감, 기회감을 압축적으로 표현
   - 영상 제목 = 검색 키워드와 정보성을 포함한 설명형 문장
   - 같은 의미를 다른 각도에서 말하도록 한다.

### 레이아웃 패턴 (5가지 중 선택)
1. **top_text_bottom_image**: 상단 텍스트, 하단 인물/핵심 장면
2. **left_text_right_image**: 좌측 텍스트 1~2줄, 우측 인물/제품/장면
3. **center_text_background_image**: 중앙 짧은 텍스트 크게, 전면 배경 분위기 강조
4. **split_before_after**: 좌우 분할 Before vs After 또는 A vs B 비교
5. **collage**: 인물 1명 + 그래프/아이콘/장면 2~3개 콜라주 형태

### 이미지 프롬프트 규칙
- 유튜브 썸네일용, **16:9 비율**, high resolution
- **"no text", "without any words or letters"** 조건 명시
- 배경은 썸네일 문구의 의미를 직관적으로 보여주는 장면
  - 예: "망하는 시장" = 텅 빈 매장, 어두운 조명, 닫힌 셔터
  - 예: "폭발적 성장" = 상승 그래프, 도시 야경, 강한 조명
- 인물 사용 시: 감정이 분명한 표정(놀람, 충격, 안도, 분노, 기쁨 등)

### 디자인 규칙
- 폰트: 굵고 단순한 고딕 계열
- 기본 텍스트: 흰색 또는 매우 밝은 색
- 강조 단어: 노랑/빨강/형광 등 강한 색을 1~2개 단어에만 사용
- 배경은 눌러주고 텍스트/인물만 튀게 만든다
- 작게 축소했을 때도 글자가 읽히는지 기준으로 설계

### 성과 체크 (JSON에 포함)
- **ctr_score**: 클릭 유도 가능성 (1~10)
- **watchtime_score**: 썸네일·제목·내용 일치 정도 (1~10)
- **consistency_note**: 썸네일 문구가 영상 내용과 어떻게 연결되는지 설명

## EMOTION THROUGH FACE + POSTURE (얼굴 표정 + 자세로 감정 표현)
- 긴장/걱정: worried small mouth, raised thin eyebrows, hunched shoulders
- 기쁨: happy curved smile mouth, relaxed eyebrows, arms raised
- 슬픔: small frown mouth, lowered eyebrows, head down, drooping posture
- 분노: tight mouth, angled eyebrows, arms spread wide, body tensed
- 놀람: open small mouth, raised eyebrows, arms up, leaning back
- 중립: small neutral mouth, relaxed thin eyebrows, standing calmly

## 🎯 유튜브 제목 생성 규칙 (중요!)

### 기본 규칙
- 길이: **18-32자** (공백 포함, 모바일에서 잘리지 않도록)
- **숫자 1개 이상 필수** (연도, 개수, 기간, 금액 등)
- 심리 트리거 **2개 이상** 사용
- 낚시성/과장/선정성 **절대 금지** ("충격", "소름", "멸망", "난리" 금지)

### 타겟별 스타일
- **시니어 (50-70대)**: 회상형, 감성적, 신뢰감
  - 예: "그때 알았더라면...", "60년 인생이 가르쳐준 3가지"
- **일반 (20-40대)**: 정보형, 해결형, 구체적
  - 예: "2025년 꼭 알아야 할 변화 3가지", "5분 만에 정리하는 핵심"

### 심리 트리거 (2개 이상 조합)
1. **호기심 갭**: "대부분이 놓치는", "뉴스에 안 나온"
2. **긴급성/시의성**: "2025년 전에 알아야 할", "지금 바로"
3. **구체적 숫자**: "3가지 변화", "7일 안에"
4. **타깃 명시**: "직장인이라면", "40대 필수"
5. **결과/이득**: "한 번에 정리", "헷갈림 끝"

### 3가지 스타일 제목 생성
1. **curiosity** (호기심형): 숨겨진 핵심/반전 느낌
2. **solution** (해결형): 혼란을 정리해주는 느낌
3. **authority** (권위형): 데이터/전문성 기반 느낌

## 🎯 유튜브 설명란 생성 규칙 (중요!)

### 목표
- 검색·추천 노출에 유리한 설명란 작성
- 알고리즘 정책 준수
- 조회수와 시청 유지율 동시 향상
- 낚시성, 과장, 허위 정보, 키워드 스팸 절대 금지

### 첫 2-3줄 (프리뷰 영역 - 가장 중요!)
- 검색 결과·추천 피드에 노출되는 구간
- 반드시 포함할 내용:
  - 이 영상이 다루는 핵심 주제
  - 시청자가 얻는 "이득/결과" 한 줄
  - main_keywords 중 1-2개를 자연스럽게 포함
- 외부 링크 넣지 말고, 오직 내용과 후킹에만 집중

### 본문 요약 (핵심 내용 설명)
- 3-6문단, 한국어 기준 **600-1200자**
- 영상에서 다루는 핵심 쟁점·데이터·결론을 정리·해석
- 키워드를 자연스럽게 섞되 스팸처럼 반복 금지
- "누가 보면 좋은지(타깃) + 어떤 상황에 유용한지" 언급
- 감정 과장보다 **사실 + 해석 + 인사이트**에 집중
- 출처가 있으면 짧게 명시

### 타임스탬프·챕터 (5분 이상 영상)
- 각 씬의 chapter_title을 활용해 자동 생성
- "00:00 형식 타임스탬프 + 짧은 제목" 구조
- 챕터 제목에 키워드 자연스럽게 포함

### 톤 & 스타일
- 과도한 유머, 속어, 자극적 표현 피함
- "팩트 → 의미 → 시청자 액션" 순서
- 마지막에 질문 1개 (댓글 유도용)

### 해시태그 규칙 (3-5개)
- 채널/브랜드 태그: 예) #채널명
- 주제 태그: 예) #부동산세금, #세제개편
- 카테고리 태그: 예) #경제뉴스, #시사해설
- 영상 내용과 직접 관련 없는 태그 금지

### 태그(Tags) 규칙 (5-12개)
- broad_tags (넓은 키워드): 예) "부동산 세금", "경제 뉴스"
- specific_tags (구체 키워드): 예) "2025 부동산 세제 개편"
- variant_tags (표기/철자 변형): 예) "부동산세금", "부동산 세금 2025"
- channel_tags (채널 고유 태그): 예) 채널명, 시리즈명
- 영상과 무관한 인기 키워드 넣기 금지

## OUTPUT FORMAT (MUST BE JSON)
{{
  "detected_category": "news 또는 story (대본 분석 결과 - 반드시 먼저 결정!)",
  "youtube": {{
    "title": "메인 제목 (18-32자, 숫자 포함, 심리 트리거 2개 이상)",
    "title_options": [
      {{"style": "curiosity", "title": "호기심형 제목 (18-32자)"}},
      {{"style": "solution", "title": "해결형 제목 (18-32자)"}},
      {{"style": "authority", "title": "권위형 제목 (18-32자)"}}
    ],
    "description": {{
      "full_text": "유튜브 설명란 전체 텍스트 (600-1200자, 프리뷰 + 본문 + 타임스탬프 + CTA)",
      "preview_2_lines": "검색 결과에 노출되는 첫 2줄 요약",
      "chapters": [
        {{"time": "00:00", "title": "인트로 · 핵심 한 줄"}},
        {{"time": "01:30", "title": "첫 번째 포인트"}},
        {{"time": "03:00", "title": "두 번째 포인트"}}
      ]
    }},
    "hashtags": ["#주제태그1", "#주제태그2", "#카테고리태그"],
    "tags": ["넓은 키워드", "구체 키워드", "변형 키워드", "채널 태그"],
    "pin_comment": "고정 댓글 문구 (핵심 요약 + 질문 1개)"
  }},
  "thumbnail": {{
    "thumbnail_text_candidates": [
      "썸네일 문구 후보 1 (10~15자, 최대 2줄, 줄바꿈 시 \\n 사용)",
      "썸네일 문구 후보 2",
      "썸네일 문구 후보 3"
    ],
    "best_combo": {{
      "chosen_title": "youtube.title_options 중 가장 적합한 제목",
      "chosen_thumbnail_text": "thumbnail_text_candidates 중 가장 적합한 문구",
      "reason": "이 조합을 선택한 이유를 2~4문장으로 설명"
    }},
    "layout_suggestion": {{
      "layout_type": "top_text_bottom_image | left_text_right_image | center_text_background_image | split_before_after | collage 중 하나",
      "layout_description": "텍스트 위치, 인물/이미지 위치, 사용할 아이콘 등을 3~6문장으로 구체적으로 설명"
    }},
    "image_prompt": "영어로 작성된 이미지 프롬프트 (16:9, high resolution, no text, without any words or letters 조건 포함)",
    "design_notes": "폰트 굵기, 색상 대비, 강조 색, 그라데이션/비네팅 사용 등 디자이너에게 줄 구체적인 지침을 4~8문장으로",
    "consistency_check": {{
      "ctr_score": 7,
      "watchtime_score": 8,
      "consistency_note": "썸네일·제목·영상 내용의 연결성을 3~6문장으로 설명"
    }},
    "ai_prompts": {{
      "A": {{"description": "스타일 A 설명", "prompt": "영문 이미지 프롬프트", "text_overlay": {{"main": "메인 텍스트 (최대 6자)", "sub": "서브 텍스트 (최대 15자)"}}, "style": "news 또는 story"}},
      "B": {{"description": "스타일 B 설명", "prompt": "영문 이미지 프롬프트", "text_overlay": {{"main": "메인 텍스트", "sub": "서브 텍스트"}}, "style": "news 또는 story"}},
      "C": {{"description": "스타일 C 설명", "prompt": "영문 이미지 프롬프트", "text_overlay": {{"main": "메인 텍스트", "sub": "서브 텍스트"}}, "style": "news 또는 story"}}
    }}
  }},
  "video_effects": {{
    "bgm_mood": "ONE of: hopeful, sad, tense, dramatic, calm, inspiring, mysterious, nostalgic",
    "subtitle_highlights": [
      {{"keyword": "강조할 단어1", "color": "#FF0000"}},
      {{"keyword": "강조할 단어2", "color": "#FFFF00"}}
    ],
    "screen_overlays": [
      {{"scene": 3, "text": "대박!", "duration": 3, "style": "impact"}},
      {{"scene": 7, "text": "반전", "duration": 2, "style": "dramatic"}}
    ],
    "sound_effects": [
      {{"scene": 1, "type": "impact", "moment": "description of when to play"}},
      {{"scene": 3, "type": "emotional", "moment": "description of when to play"}}
    ],
    "lower_thirds": [
      {{"scene": 2, "text": "화자명 또는 출처", "position": "bottom-left"}}
    ],
    "news_ticker": {{
      "enabled": true,
      "headlines": ["속보: 첫 번째 헤드라인", "이슈: 두 번째 헤드라인", "핵심: 세 번째 헤드라인"]
    }},
    "shorts": {{
      "highlight_scenes": [1, 2],
      "hook_text": "충격적인 한 마디로 시작하는 훅 (15자 이내)",
      "title": "쇼츠용 짧은 제목 #Shorts"
    }},
    "transitions": {{
      "style": "crossfade",
      "duration": 0.5
    }}
  }},
  "scenes": [
    {{
      "scene_number": 1,
      "chapter_title": "Short chapter title for YouTube (5-15 chars)",
      "narration": "<speak>원본 대본의 정확한 문장.<break time='300ms'/><prosody rate='slow'>감정 표현이 필요한 부분</prosody>에 SSML 태그 추가.</speak>",
      "image_prompt": "[Detailed anime background, slice-of-life style, Ghibli-inspired, soft lighting]. Simple white stickman character with round head, two black dot eyes, small mouth, thin eyebrows, black outline body, [action], face clearly visible. NO anime characters, NO realistic humans, NO elderly, NO grandpa, NO grandma, ONLY stickman. Contrast collage.",
      "ken_burns": "zoom_in / zoom_out / pan_left / pan_right / pan_up / pan_down"
    }}
  ]
}}

{ai_prompts_rules}

## ⚠️ CRITICAL: TEXT_OVERLAY RULES (한글 텍스트 규칙) ⚠️
The "text_overlay" field contains Korean text that will be rendered ON the thumbnail image.
⚠️ IMAGE GENERATION MODELS STRUGGLE WITH LONG TEXT! Keep it SHORT!

**MAIN TEXT RULES:**
- MAXIMUM 6 Korean characters (e.g., "그날의 선택", "운명의 순간", "충격 반전")
- Use SIMPLE, COMMON Korean words only
- NO typos, NO made-up words
- Must be grammatically correct Korean

**SUB TEXT RULES:**
- MAXIMUM 15 Korean characters
- Can be a short phrase or subtitle
- Use proper Korean spacing (띄어쓰기)
- NO English, NO special characters

**GOOD EXAMPLES:**
- main: "운명의 선택" (4자), sub: "그 날의 결정이 모든 걸 바꿨다"
- main: "충격 결말" (4자), sub: "아무도 예상 못한 반전"
- main: "눈물의 재회" (5자), sub: "10년 만에 다시 만난 그 사람"

**BAD EXAMPLES (절대 금지):**
- main: "쫓이 쫓아가던" ❌ (오타, 너무 김)
- main: "그날을 잊지 못해요 정말로" ❌ (너무 김)
- sub: "투자, 그 후의 이야..." ❌ (불완전한 문장)

## ⚠️ CRITICAL: NARRATION RULE ⚠️
The "narration" field MUST contain the EXACT ORIGINAL TEXT from the script + SSML emotion tags!
- DO NOT summarize or paraphrase the actual content
- COPY-PASTE the exact sentences from the script that this scene covers
- ADD SSML tags (<speak>, <prosody>, <emphasis>, <break>) for emotional expression
- Wrap the entire narration in <speak>...</speak> tags
- Use SSML sparingly (20-30% of text) for natural delivery

**Example with SSML:**
"narration": "<speak>그날 아침, 평소와 같은 하루가 시작될 줄 알았습니다.<break time='300ms'/><prosody rate='slow'>하지만</prosody>...<emphasis level='strong'>충격적인</emphasis> 소식이 전해졌습니다.</speak>"

## ⚠️ VIDEO EFFECTS RULES ⚠️

### BGM Mood (배경음악 분위기)
Choose ONE mood that best fits the overall video tone:
- hopeful: 희망적, 긍정적 결말
- sad: 슬픔, 이별, 상실
- tense: 긴장감, 위기
- dramatic: 충격, 반전, 클라이맥스
- calm: 평화, 일상
- inspiring: 감동, 성공
- mysterious: 미스터리, 의문
- nostalgic: 회상, 추억

### Subtitle Highlights (자막 강조) - 자동 선정
GPT가 대본 흐름을 분석하여 자동으로 강조할 키워드를 선정합니다.
⚠️ 중요: 색상을 남발하면 조잡해 보입니다! 신중하게 선택하세요!

**규칙:**
- 전체 영상에서 **최대 3-5개** 키워드만 선정 (너무 많으면 효과 없음)
- 정말 **임팩트 있는 순간**에만 사용
- 키워드는 나레이션 텍스트에서 **정확히 일치**해야 함

**색상 가이드:**
- #FF0000 (빨강): 충격/반전 순간 - "충격", "실화", "경악", "폭로"
- #FFFF00 (노랑): 강조/결론 - "결국", "드디어", "마침내", "바로"
- #00FFFF (청록): 감정/감동 - "눈물", "감동", "사랑", "희망"

**❌ 하지 마세요:**
- 모든 문장에 색상 넣기
- 한 씬에 여러 색상 사용
- 일반적인 단어 강조 (그래서, 그런데, 하지만 등)

### Screen Text Overlays (화면 텍스트 오버레이) - 새 기능!
특정 순간에 화면에 큰 텍스트를 띄워 임팩트를 줍니다.
예: "대박!" "충격!" "반전!" 같은 텍스트가 화면 중앙에 3초간 표시

**규칙:**
- 전체 영상에서 **최대 2-3개**만 사용 (과하면 유치해 보임)
- 정말 **클라이맥스 순간**에만 사용
- 텍스트는 **1-4글자** 짧게 (대박, 충격, 반전, 실화 등)

**출력 형식:**
"screen_overlays": [
  {{"scene": 3, "text": "대박!", "duration": 3, "style": "impact"}},
  {{"scene": 7, "text": "반전", "duration": 2, "style": "dramatic"}}
]

**스타일 옵션:**
- impact: 빨간 테두리, 흰 텍스트, 펄스 효과
- dramatic: 검정 배경, 노란 텍스트, 페이드인
- emotional: 부드러운 그라데이션, 감성적

### Sound Effects (효과음)
Add sound effects at dramatic moments (max 3-5 per video):
- impact: 충격적 사실 공개, 반전 순간 (쿵/둥)
- whoosh: 장면 전환, 시간 이동 (휙)
- ding: 포인트 강조, 깨달음 (띵)
- tension: 긴장감 고조 (드르르)
- emotional: 감동/슬픔 포인트 (피아노)
- success: 긍정적 결과, 해피엔딩 (짠)

### Lower Thirds (하단 자막)
Add source/speaker info when quoting or citing:
- Use for: 전문가 발언, 뉴스 인용, 통계 출처
- Format: "김OO 교수", "OO일보", "2024년 통계"
- Position: bottom-left (default)

### News Ticker (뉴스 티커) - 뉴스/시사 콘텐츠 전용
화면 하단에 스크롤되는 뉴스 헤드라인을 추가합니다.
⚠️ 뉴스, 시사, 정치, 경제 카테고리 영상에만 사용!

**형식:**
"news_ticker": {{
  "enabled": true,
  "headlines": ["속보: 핵심 내용 1", "이슈: 핵심 내용 2", "핵심: 핵심 내용 3"]
}}

**규칙:**
- enabled: 뉴스 스타일 영상에만 true, 그 외 false
- headlines: 3-5개의 짧은 헤드라인 (각 15-25자)
- 대본의 핵심 포인트를 뉴스 헤드라인 스타일로 작성
- 접두어 사용: "속보:", "이슈:", "핵심:", "주목:", "화제:"

### ⚠️ Shorts (YouTube 쇼츠 자동 생성) - 필수! ⚠️
메인 영상에서 가장 흥미로운 부분을 추출하여 60초 이하의 쇼츠를 자동 생성합니다.
쇼츠 설명에 원본 영상 링크가 포함되어 본 영상으로 트래픽을 유도합니다.

🚨 **반드시 생성해야 합니다!** 쇼츠는 유튜브 노출에 매우 중요합니다.

**형식:**
"shorts": {{
  "highlight_scenes": [2, 3],
  "hook_text": "이 한마디가 모든 걸 바꿨다",
  "title": "충격적인 고백 #Shorts"
}}

**규칙:**
- highlight_scenes: 🚨 **필수!** 가장 임팩트 있는 1-3개 씬 번호 선택 (총 60초 이하가 되도록). 비어있으면 안됨!
- hook_text: 시청자를 사로잡는 첫 문장 (15자 이내, 궁금증 유발)
- title: 쇼츠 전용 제목 (클릭 유도, 반드시 #Shorts 포함)

**하이라이트 씬 선택 기준:**
- 반전/충격 순간
- 감정적 클라이맥스
- 핵심 메시지가 담긴 씬
- 시청자가 "더 보고 싶다"고 느낄 부분

⚠️ **highlight_scenes가 비어있으면 쇼츠가 생성되지 않습니다!**
⚠️ **무조건 1개 이상의 씬 번호를 선택하세요!**

### Transitions (장면 전환 효과) - 신규!
씬과 씬 사이에 부드러운 전환 효과를 적용합니다.

**형식:**
"transitions": {{
  "style": "crossfade",
  "duration": 0.5
}}

**스타일 옵션:**
- crossfade: 페이드 인/아웃 (기본값, 가장 자연스러움)
- fade_black: 검은 화면으로 페이드 (장면 전환)
- fade_white: 흰 화면으로 페이드 (회상, 꿈)
- none: 전환 효과 없음 (빠른 컷)

**duration:** 0.3 ~ 1.0초 권장 (기본 0.5초)

### Ken Burns Effect (이미지 움직임)
Each scene should have a different Ken Burns effect for visual variety:
- zoom_in: 서서히 확대 (감정적 순간, 클로즈업)
- zoom_out: 서서히 축소 (전체 상황 보여줄 때)
- pan_left: 왼쪽으로 이동
- pan_right: 오른쪽으로 이동
- pan_up: 위로 이동 (희망적)
- pan_down: 아래로 이동 (슬픔, 실망)
⚠️ Alternate effects between scenes for dynamic feel!

### Chapter Titles (챕터 제목)
Each scene needs a short chapter title for YouTube chapters:
- Length: 5-15 characters in Korean
- Style: 간결하고 흥미 유발
- Examples: "충격적 발견", "반전의 시작", "눈물의 재회"

### 🎭 SSML 감정 표현 (TTS 나레이션용) - 중요!
나레이션 텍스트에 SSML 태그를 추가하여 TTS가 감정을 담아 읽도록 합니다.
대본 텍스트는 그대로 유지하되, 감정 표현이 필요한 부분에 SSML 태그를 추가하세요.

**사용 가능한 SSML 태그:**

1. **<prosody> - 속도/높낮이 조절**
   - rate: x-slow, slow, medium, fast, x-fast (또는 50%-200%)
   - pitch: x-low, low, medium, high, x-high (또는 -20st~+20st)
   ```
   <prosody rate="slow" pitch="low">천천히 낮게</prosody>
   <prosody rate="fast">빠르게 긴박하게</prosody>
   <prosody pitch="high">높은 톤으로</prosody>
   ```

2. **<emphasis> - 강조**
   - level: strong, moderate, reduced
   ```
   <emphasis level="strong">충격적인</emphasis> 사실이 밝혀졌습니다.
   ```

3. **<break> - 휴지(쉬기)**
   - time: 100ms ~ 1000ms
   ```
   그리고...<break time="500ms"/>반전이 시작됩니다.
   ```

**감정별 SSML 패턴:**
- 😨 긴장/충격: `<prosody rate="fast" pitch="high">긴박한 내용</prosody>`
- 😢 슬픔: `<prosody rate="slow" pitch="low">슬픈 내용</prosody>`
- 🎉 기쁨/희망: `<prosody rate="medium" pitch="high">밝은 내용</prosody>`
- 🤔 생각/회상: `<prosody rate="slow">회상 내용</prosody><break time="300ms"/>`
- ❗ 강조: `<emphasis level="strong">중요한 포인트</emphasis>`
- 😲 반전: `<break time="500ms"/><prosody rate="slow" pitch="low">그런데...</prosody>`

**⚠️ 주의사항:**
- 모든 나레이션을 `<speak>` 태그로 감싸세요
- 과도한 태그 사용 금지 - 자연스러움이 중요!
- 매 문장마다 태그를 넣지 말고, 감정 변화가 필요한 핵심 순간에만 사용
- 전체 나레이션의 20-30%에만 SSML 태그 적용

**예시:**
```
<speak>
그날 아침, 평소와 같은 하루가 시작될 줄 알았습니다.
<break time="300ms"/>
<prosody rate="slow">하지만</prosody>...
<emphasis level="strong">충격적인</emphasis> 소식이 전해졌습니다.
<prosody rate="fast" pitch="high">급히 달려간 그곳에서 본 것은</prosody>
<break time="500ms"/>
<prosody rate="slow" pitch="low">아무도 예상치 못한 광경이었습니다.</prosody>
</speak>
```

## EXAMPLE PROMPTS (스틱맨은 항상 동일한 얼굴: 점 눈 2개, 작은 입, 얇은 눈썹)

### 신문 읽는 스틱맨
"Detailed anime background of office building stairs in warm morning sunlight, slice-of-life anime style, Ghibli-inspired warm colors. Simple white stickman with round head, two black dot eyes, small curved mouth, thin eyebrows, black outline body, reading a newspaper with curious expression. NO other characters. Contrast collage style."

### 주식 시장 혼돈
"Detailed anime style trading floor background, monitors with stock charts, dramatic lighting, slice-of-life anime aesthetic. Simple white stickman with round head, two black dot eyes, small worried mouth, raised thin eyebrows showing concern, black outline body, standing in the center. NO anime characters, NO realistic humans. Contrast collage."

### 한국 진료소 스타일
"Anime style spring morning in front of a small Korean clinic, cherry blossoms falling, Ghibli-inspired soft pastel colors. Simple white stickman with round head, two black dot eyes, gentle smile mouth, thin eyebrows, wearing a white coat, black outline body. NO other characters. Contrast collage style."

### 도시 거리 스타일
"Detailed anime style Korean city street background, warm colors, Ghibli-inspired slice-of-life aesthetic. Simple white stickman with round head, two black dot eyes, small neutral mouth, thin eyebrows, black outline body, standing in the foreground. NO anime characters, NO realistic humans. Contrast collage composition."
"""

        # 콘텐츠 타입별 시스템 프롬프트 분기 (실사 스타일)
        elif content_type == 'product':
            # 상품 소개 콘텐츠
            system_prompt = f"""당신의 역할은 상품 소개 대본을 분석하여 AI 이미지용 프롬프트를 전문적으로 작성하는 비서입니다.

## 핵심 작업
1. 대본에서 소개하는 **제품/상품**을 파악합니다.
2. 제품 중심의 이미지 프롬프트를 생성합니다. (인물은 필요한 경우에만 최소한으로)

## 상품 이미지 프롬프트 규칙
- **제품이 주인공**: 제품을 프롬프트 맨 앞에 배치
- **제품 클로즈업**: 제품의 디테일, 질감, 기능을 강조
- **사용 장면**: 제품이 사용되는 환경/상황 (손이나 일부 신체만 등장 가능)
- **인포그래픽 스타일**: 제품 기능 설명에는 다이어그램, 도표 스타일
- **깔끔한 배경**: 흰색, 그라데이션, 또는 제품과 어울리는 배경

## 상품별 프롬프트 예시
- 가전제품: "Modern [product name], sleek design, studio lighting, white background, product photography, sharp focus, 4K detail"
- 식품: "[food product] beautifully plated, appetizing presentation, natural lighting, shallow depth of field"
- 전자기기: "Close-up of [device], highlighting key features, tech product photography, clean minimal background"
- 생활용품: "[product] in use, lifestyle photography, cozy home setting, soft natural light"

## 프롬프트 작성 원칙
1. 출력 프롬프트는 항상 영어로 작성합니다.
2. 제품명, 제품 특징을 정확히 포함합니다.
3. 다음 요소를 포함합니다:
   - [product] 제품명과 특징 - 프롬프트 맨 앞에 배치
   - [angle] 촬영 각도 (top-down, eye-level, 45-degree, close-up)
   - [lighting] 조명 (studio lighting, soft box, natural light)
   - [background] 배경 (white, gradient, lifestyle setting)
   - [style] 스타일 (product photography, commercial, lifestyle)

## 이미지 스타일
{style_desc}

## 출력 형식 (반드시 JSON)
{{
  "thumbnail": {{
    "title": "유튜브 썸네일용 한글 제목 (제품명 + 핵심 기능/혜택)",
    "text_lines": ["1줄: 제품명/브랜드", "2줄: 핵심 기능", "3줄: 혜택 강조", "4줄: 행동 유도"],
    "highlight_line": 2,
    "prompt": "Product hero shot - [product] with dramatic lighting, premium feel, commercial photography"
  }},
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "한국어 나레이션 (원본 대본 기반)",
      "image_prompt": "Product-focused prompt: [product details], [angle], [lighting], [background], [style]"
    }}
  ]
}}"""
        else:
            # 드라마/스토리 콘텐츠 (기본값) - audience에 따라 다른 규칙 적용
            # audience별 썸네일 규칙 설정
            if audience == 'general':
                thumbnail_rules = """## 일반용 썸네일 문구 규칙 (중요!)
일반 타겟(20-40대) 썸네일은 "궁금증/자극"을 유발해야 합니다.

1. **문구 길이**: 4-7자 (짧고 강렬하게!)
2. **문구 유형**:
   - 자극형: "결국 터졌다", "이게 실화?", "완전 미쳤다"
   - 궁금증형: "왜 아무도 안알려줬지?", "이것만 알면", "진짜 이유"
   - 충격형: "소름 돋았다", "역대급 반전", "충격 실화"
3. **색상 조합**: 흰색+검정, 빨강+검정 (강한 대비)
4. **구도**: 중앙 텍스트 + 어두운 배경/실루엣"""
                thumbnail_color = "#FFFFFF"
                outline_color = "#000000"
            else:
                thumbnail_rules = """## 시니어용 썸네일 문구 규칙 (중요!)
시니어 타겟(50-70대) 썸네일은 "경험을 떠올리게" 해야 합니다.

1. **문구 길이**: 8-12자 (노안 고려, 읽기 쉽게)
2. **문구 유형**:
   - 회상형: "그날을 잊지 않는다", "처음엔 몰랐다", "돌아보면 눈물이 난다"
   - 후회/교훈형: "하는 게 아니었다", "늦게 알았다", "왜 그랬을까"
   - 경험 공유형: "다 겪어봤다", "나도 그랬다", "누구나 그런 날 있다"
3. **색상 조합**: 노랑+검정이 최고 CTR (text_color에 반영)
4. **구도**: 왼쪽 상단 텍스트 + 오른쪽 인물/상황"""
                thumbnail_color = "#FFD700"
                outline_color = "#000000"

            system_prompt = f"""You are an AI assistant that analyzes scripts and generates image prompts.

## ⚠️ LANGUAGE RULE (CRITICAL!) ⚠️
Output Language: {lang_config['name']} ({lang_config['native']})
{lang_config['instruction']}
- YouTube titles, description → {lang_config['name']}
- Thumbnail text → {lang_config['name']}
- Narration → {lang_config['name']}
- ONLY image_prompt → Always in English (for AI image generation)

Target audience: {'General (20-40s)' if audience == 'general' else 'Senior (50-70s)'}

## ⚠️⚠️⚠️ CRITICAL: STICKMAN CHARACTER ONLY (MUST FOLLOW!) ⚠️⚠️⚠️
- ABSOLUTELY NO realistic human faces! Use STICKMAN character style only!
- Stickman description: "Simple white stickman character with round head, two black dot eyes, small mouth, thin eyebrows, black outline body"
- Background: Use detailed anime-style backgrounds (Ghibli-inspired, warm colors, detailed environments)
- NO grandfather, grandmother, halmeoni, harabeoji, elderly man, elderly woman - ONLY stickman!
- Style: "Contrast collage style" - simple stickman against detailed anime background

## Core Tasks
1. Extract protagonist's age, gender, occupation, appearance from the script.
2. Generate consistent image prompts based on extracted character info.
3. Generate YouTube thumbnail text and prompts for the target audience.

## Character Prompt Rules (for image_prompt - always in English)
- ⚠️ ALL CHARACTERS = STICKMAN ONLY! No realistic human faces!
- Stickman: "Simple white stickman with round head, black dot eyes, small mouth, thin eyebrows, black outline body"
- Background: Detailed anime-style (Ghibli-inspired, warm colors, slice-of-life environments)
- Combine: Simple stickman + detailed background = "Contrast collage style"
- Actions/poses should be shown through stickman body language
- Emotions shown through simple facial expressions on stickman (dot eyes, curved mouth)

{thumbnail_rules}

## Prompt Writing Principles
1. **image_prompt is ALWAYS in English** (for AI image generation)
2. Write concise but information-dense prompts.
3. Include these elements:
   - [subject] Main subject - place at the beginning (detailed character features)
   - [environment] Background, location
   - [lighting] Lighting (soft natural light, warm golden hour, dramatic side lighting)
   - [color] Color tone (warm tones, muted colors, film color grading)
   - [camera] Shot type (wide/medium/close-up), lens (50mm/85mm), depth of field
   - [style] Style
   - [mood] Emotion/atmosphere

## Image Style
{style_desc}

## 🎯 유튜브 제목 생성 규칙
- 길이: **18-32자** (공백 포함)
- **숫자 1개 이상 필수**
- 심리 트리거 **2개 이상**: 호기심갭, 긴급성, 숫자, 타깃명시, 결과제시
- 낚시성/과장 **금지** ("충격", "소름" 등 금지)
- 타겟별: 시니어=회상형/감성적, 일반=정보형/해결형
- **3가지 스타일**: curiosity(호기심), solution(해결), authority(권위)

## 🎯 유튜브 설명란 생성 규칙
- **첫 2줄**: 검색 노출 구간 - 핵심 주제 + 시청자 이득 + 키워드 포함
- **본문**: 600-1200자, 사실 + 해석 + 인사이트 중심
- **챕터**: 씬별 chapter_title 활용, "00:00 제목" 형식
- **해시태그**: 3-5개 (주제태그 + 카테고리태그)
- **태그**: 5-12개 (넓은/구체/변형/채널 키워드)
- **톤**: 과장 금지, 팩트 → 의미 → 액션 순서

## Output Format (MUST be valid JSON)
{{
  "youtube": {{
    "title": "메인 제목 (18-32자, 숫자 포함, 심리 트리거 2개 이상)",
    "title_options": [
      {{"style": "curiosity", "title": "호기심형 제목"}},
      {{"style": "solution", "title": "해결형 제목"}},
      {{"style": "authority", "title": "권위형 제목"}}
    ],
    "description": {{
      "full_text": "유튜브 설명란 전체 텍스트 (600-1200자)",
      "preview_2_lines": "검색 결과에 노출되는 첫 2줄 요약",
      "chapters": [{{"time": "00:00", "title": "챕터 제목"}}]
    }},
    "hashtags": ["#주제태그1", "#주제태그2", "#카테고리태그"],
    "tags": ["넓은 키워드", "구체 키워드", "변형 키워드"],
    "pin_comment": "고정 댓글 (핵심 요약 + 질문)"
  }},
  "thumbnail": {{
    "thumbnail_text_candidates": [
      "썸네일 문구 후보 1 (10~15자, 최대 2줄, 줄바꿈 시 \\n 사용)",
      "썸네일 문구 후보 2",
      "썸네일 문구 후보 3"
    ],
    "best_combo": {{
      "chosen_title": "youtube.title_options 중 가장 적합한 제목",
      "chosen_thumbnail_text": "thumbnail_text_candidates 중 가장 적합한 문구",
      "reason": "이 조합을 선택한 이유를 2~4문장으로 설명"
    }},
    "layout_suggestion": {{
      "layout_type": "top_text_bottom_image | left_text_right_image | center_text_background_image | split_before_after | collage 중 하나",
      "layout_description": "텍스트 위치, 인물/이미지 위치, 사용할 아이콘 등을 3~6문장으로 구체적으로 설명"
    }},
    "image_prompt": "영어로 작성된 이미지 프롬프트 (16:9, high resolution, no text, without any words or letters 조건 포함)",
    "design_notes": "폰트 굵기, 색상 대비, 강조 색, 그라데이션/비네팅 사용 등 디자이너에게 줄 구체적인 지침을 4~8문장으로",
    "consistency_check": {{
      "ctr_score": 7,
      "watchtime_score": 8,
      "consistency_note": "썸네일·제목·영상 내용의 연결성을 3~6문장으로 설명"
    }},
    "ai_prompts": {{
      "A": {{"description": "스타일 A 설명", "prompt": "영문 이미지 프롬프트", "text_overlay": {{"main": "메인 텍스트 (최대 6자)", "sub": "서브 텍스트 (최대 15자)"}}, "style": "news 또는 story"}},
      "B": {{"description": "스타일 B 설명", "prompt": "영문 이미지 프롬프트", "text_overlay": {{"main": "메인 텍스트", "sub": "서브 텍스트"}}, "style": "news 또는 story"}},
      "C": {{"description": "스타일 C 설명", "prompt": "영문 이미지 프롬프트", "text_overlay": {{"main": "메인 텍스트", "sub": "서브 텍스트"}}, "style": "news 또는 story"}}
    }}
  }},
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "⚠️ EXACT TEXT from the script - COPY-PASTE the original sentences, DO NOT summarize!",
      "image_prompt": "English image prompt..."
    }}
  ]
}}

## ⚠️ CRITICAL: AI THUMBNAIL PROMPTS RULES ⚠️
The "ai_prompts" field generates 3 different YouTube thumbnails for A/B testing.
⚠️ THUMBNAILS ARE NOT STICKMAN! Use webtoon/manhwa cartoon style with expressive characters!
- A: Emotion/expression focused - Korean webtoon style character with exaggerated emotion (surprise, shock, joy)
- B: Story/situation focused - show before/after contrast or key scene moment in cartoon style
- C: Typography focused - bold text with minimal background, graphic design style
- All 3 prompts MUST use cartoon/webtoon/manhwa illustration style, NOT stickman!
- All 3 prompts MUST be different styles/compositions!
- NEVER use realistic human faces or stickman - use Korean webtoon/manhwa cartoon style only!

## ⚠️ CRITICAL: TEXT_OVERLAY RULES (한글 텍스트 규칙) ⚠️
The "text_overlay" field contains Korean text that will be rendered ON the thumbnail image.
⚠️ IMAGE GENERATION MODELS STRUGGLE WITH LONG TEXT! Keep it SHORT!

**MAIN TEXT RULES:**
- MAXIMUM 6 Korean characters (e.g., "그날의 선택", "운명의 순간", "충격 반전")
- Use SIMPLE, COMMON Korean words only
- NO typos, NO made-up words
- Must be grammatically correct Korean

**SUB TEXT RULES:**
- MAXIMUM 15 Korean characters
- Can be a short phrase or subtitle
- Use proper Korean spacing (띄어쓰기)
- NO English, NO special characters

**GOOD EXAMPLES:**
- main: "운명의 선택" (4자), sub: "그 날의 결정이 모든 걸 바꿨다"
- main: "충격 결말" (4자), sub: "아무도 예상 못한 반전"
- main: "눈물의 재회" (5자), sub: "10년 만에 다시 만난 그 사람"

**BAD EXAMPLES (절대 금지):**
- main: "쫓이 쫓아가던" ❌ (오타, 너무 김)
- main: "그날을 잊지 못해요 정말로" ❌ (너무 김)
- sub: "투자, 그 후의 이야..." ❌ (불완전한 문장)

## ⚠️ CRITICAL: NARRATION RULE ⚠️
The "narration" field MUST contain the EXACT ORIGINAL TEXT from the script!
- DO NOT summarize or paraphrase - COPY-PASTE the exact sentences
- This helps the user know EXACTLY where to place each image in the video"""

        # Style-specific user prompt
        if image_style == 'animation':
            # Thumbnail rules by audience
            if audience == 'general':
                thumb_instruction = "Thumbnail text for General audience (4-7 chars, provocative/shocking style)"
            else:
                thumb_instruction = "Thumbnail text for Senior audience (8-12 chars, nostalgic/reflective style)"

            user_prompt = f"""Script:
{script}

★★★ OUTPUT LANGUAGE: {lang_config['name']} ({lang_config['native']}) ★★★
{lang_config['instruction']}
- ONLY image_prompt should be in English

Split this script into exactly {image_count} scenes and generate "CONTRAST COLLAGE: Anime background + Stickman" image prompts.
Target audience: {'General (20-40s)' if audience == 'general' else 'Senior (50-70s)'}

Core Style (MUST follow):
- Background = Detailed anime style (slice-of-life anime, Ghibli-inspired, warm colors, soft lighting)
- Stickman = Simple white body + Face required (round head with TWO DOT EYES, SMALL CURVED MOUTH, THIN EYEBROWS)
- Combination = "contrast collage" - simple stickman contrasts against detailed anime background

Rules:
1. Generate exactly {image_count} scenes (no more, no less)
2. Background MUST be DETAILED ANIME STYLE - NO photorealistic!
3. Character is ONLY "simple white stickman with round head, TWO BLACK DOT EYES, small curved mouth, thin eyebrows, black outline body"
4. Stickman face MUST have: round head, two black dot eyes, small curved mouth, thin eyebrows - SAME in every scene!
5. NO anime characters, NO realistic humans - ONLY the simple white stickman!
6. Express emotion through eyebrows, mouth shape, and body posture
7. Add these tags to every image_prompt: detailed anime background, slice-of-life style, simple white stickman, NO other characters, contrast collage
8. {thumb_instruction}
9. ⚠️ NARRATION = EXACT SCRIPT TEXT! Copy-paste the original sentences from the script. DO NOT summarize or paraphrase!

image_prompt MUST be in English."""
        else:
            # Thumbnail rules by audience
            if audience == 'general':
                thumbnail_instruction = "Thumbnail text for General audience (4-7 chars, provocative/curiosity/shocking style)"
            else:
                thumbnail_instruction = "Thumbnail text for Senior audience (8-12 chars, nostalgic/reflective/experience-sharing style)"

            user_prompt = f"""Script:
{script}

★★★ OUTPUT LANGUAGE: {lang_config['name']} ({lang_config['native']}) ★★★
{lang_config['instruction']}
- ONLY image_prompt should be in English

Split this script into exactly {image_count} scenes and generate professional image prompts.
Target audience: {'General (20-40s)' if audience == 'general' else 'Senior (50-70s)'}

Rules:
1. Generate exactly {image_count} scenes (no more, no less)
2. {thumbnail_instruction}
3. image_prompt MUST be in English, following the prompt writing principles above.
4. ⚠️ NARRATION = EXACT SCRIPT TEXT! Copy-paste the original sentences from the script. DO NOT summarize or paraphrase!
5. ⚠️ ALL CHARACTERS = STICKMAN ONLY! No realistic humans (no grandfather, grandmother, elderly people). Use simple stickman with anime background."""

        print(f"[IMAGE-ANALYZE] GPT-5.1 generating prompts... (style: {image_style}, content: {content_type}, audience: {audience}, language: {output_language})")

        # GPT-5.1은 Responses API 사용
        response = client.responses.create(
            model="gpt-5.1",
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": system_prompt
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON. No other text, just pure JSON output."
                        }
                    ]
                }
            ],
            temperature=0.7
        )

        print(f"[IMAGE-ANALYZE] GPT-5.1 응답 완료")

        # Responses API 결과 추출
        if getattr(response, "output_text", None):
            result_text = response.output_text.strip()
        else:
            text_chunks = []
            for item in getattr(response, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    if getattr(content, "type", "") == "text":
                        text_chunks.append(getattr(content, "text", ""))
            result_text = "\n".join(text_chunks).strip()

        # JSON 파싱 (마크다운 코드블록 제거)
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()

        # Trailing comma 제거 (LLM이 자주 실수하는 패턴)
        import re
        # ,] → ]
        result_text = re.sub(r',\s*\]', ']', result_text)
        # ,} → }
        result_text = re.sub(r',\s*\}', '}', result_text)

        result = json.loads(result_text)

        # video_effects 추출 및 로깅
        video_effects = result.get("video_effects", {})
        detected_category = result.get("detected_category", "story")

        print(f"[IMAGE-ANALYZE] detected_category: {detected_category}")
        print(f"[IMAGE-ANALYZE] video_effects keys: {list(video_effects.keys())}")
        if video_effects:
            print(f"[IMAGE-ANALYZE] bgm_mood: {video_effects.get('bgm_mood', '(없음)')}")
            print(f"[IMAGE-ANALYZE] subtitle_highlights: {len(video_effects.get('subtitle_highlights', []))}개")
            print(f"[IMAGE-ANALYZE] screen_overlays: {len(video_effects.get('screen_overlays', []))}개")
            print(f"[IMAGE-ANALYZE] sound_effects: {len(video_effects.get('sound_effects', []))}개")
            print(f"[IMAGE-ANALYZE] shorts highlight_scenes: {video_effects.get('shorts', {}).get('highlight_scenes', [])}")

        # 유튜브 메타데이터 로깅
        youtube_meta = result.get("youtube", {})
        desc = youtube_meta.get("description", {})
        if isinstance(desc, dict):
            print(f"[IMAGE-ANALYZE] description.full_text 길이: {len(desc.get('full_text', ''))}자")
            print(f"[IMAGE-ANALYZE] description.chapters: {len(desc.get('chapters', []))}개")
        print(f"[IMAGE-ANALYZE] hashtags: {youtube_meta.get('hashtags', [])}")
        print(f"[IMAGE-ANALYZE] tags: {len(youtube_meta.get('tags', []))}개")
        print(f"[IMAGE-ANALYZE] pin_comment: {'있음' if youtube_meta.get('pin_comment') else '없음'}")

        return jsonify({
            "ok": True,
            "youtube": result.get("youtube", {}),
            "thumbnail": result.get("thumbnail", {}),
            "scenes": result.get("scenes", []),
            "video_effects": video_effects,
            "detected_category": detected_category,
            "settings": {
                "content_type": content_type,
                "image_style": image_style,
                "image_count": image_count,
                "audience": audience
            }
        })

    except Exception as e:
        print(f"[IMAGE-ANALYZE][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/image/download-zip', methods=['POST'])
def api_image_download_zip():
    """이미지들을 ZIP으로 묶어 다운로드"""
    try:
        import zipfile
        import io
        import urllib.request

        data = request.get_json()
        images = data.get('images', [])

        if not images:
            return jsonify({"ok": False, "error": "다운로드할 이미지가 없습니다"}), 400

        # ZIP 파일 생성
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for img in images:
                try:
                    name = img.get('name', 'image.png')
                    url = img.get('url', '')

                    if url.startswith('http'):
                        # 외부 URL에서 이미지 다운로드
                        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=30) as response:
                            img_data = response.read()
                            zip_file.writestr(name, img_data)
                    elif url.startswith('/'):
                        # 로컬 파일
                        local_path = url.lstrip('/')
                        if os.path.exists(local_path):
                            with open(local_path, 'rb') as f:
                                zip_file.writestr(name, f.read())
                except Exception as e:
                    print(f"[IMAGE-ZIP] Failed to add {img.get('name')}: {e}")
                    continue

        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='images.zip'
        )

    except Exception as e:
        print(f"[IMAGE-ZIP][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/image/generate-assets-zip', methods=['POST'])
def api_image_generate_assets_zip():
    """CapCut용 에셋 ZIP 생성 (이미지 + TTS 오디오 + SRT 자막) - 문장별 정확한 싱크"""
    try:
        import zipfile
        import io
        import urllib.request
        import requests
        import base64
        import uuid
        import subprocess
        import gc  # 메모리 정리용
        from datetime import datetime

        def detect_language(text):
            """텍스트의 주요 언어 감지 (한국어/영어/일본어)"""
            if not text:
                return 'en'
            korean_chars = len(re.findall(r'[가-힣]', text))
            japanese_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF]', text))
            total_chars = len(re.sub(r'\s', '', text))
            if total_chars == 0:
                return 'en'
            if korean_chars / total_chars > 0.3:
                return 'ko'
            elif japanese_chars / total_chars > 0.2:
                return 'ja'
            return 'en'

        def get_voice_for_language(lang, base_voice):
            """언어에 맞는 TTS 음성 반환"""
            is_female = 'Neural2-A' in base_voice or 'Neural2-B' in base_voice or 'Wavenet-A' in base_voice
            voice_map = {
                'ko': {'female': 'ko-KR-Neural2-A', 'male': 'ko-KR-Neural2-C'},
                'en': {'female': 'en-US-Neural2-F', 'male': 'en-US-Neural2-D'},
                'ja': {'female': 'ja-JP-Neural2-B', 'male': 'ja-JP-Neural2-C'}
            }
            gender = 'female' if is_female else 'male'
            return voice_map.get(lang, voice_map['en'])[gender]

        def get_language_code(lang):
            return {'ko': 'ko-KR', 'en': 'en-US', 'ja': 'ja-JP'}.get(lang, 'en-US')

        def split_sentences_with_gpt(text, lang='ko'):
            """GPT-5.1을 사용해 자연스러운 자막 단위로 분리"""
            try:
                openai_api_key = os.getenv("OPENAI_API_KEY")
                if not openai_api_key:
                    print("[SUBTITLE-SPLIT] OpenAI API 키 없음, 폴백 사용")
                    return split_korean_semantic_fallback(text)

                from openai import OpenAI
                client = OpenAI(api_key=openai_api_key)

                prompt = f"""다음 나레이션을 TTS 자막용으로 자연스럽게 분리해주세요.

규칙:
1. 한 줄은 10~20자 사이로 (의미가 끊기지 않으면 15자도 OK)
2. 말의 흐름이 자연스럽게 끊어지는 곳에서 분리 (조사 뒤, 쉼표 뒤 등)
3. 절대로 단어 중간에서 끊지 마세요
4. 문장이 진행 중인데 강제로 20자에서 자르지 마세요
5. 의미 단위로 자연스럽게 끊으세요

예시:
입력: "오늘은 그 시절 우리 동네 작은 구멍가게 이야기를 나눠보려고 합니다."
출력:
오늘은 그 시절
우리 동네
작은 구멍가게 이야기를
나눠보려고 합니다.

나레이션:
{text}

분리된 자막 (한 줄에 하나씩, 다른 설명 없이):"""

                response = client.responses.create(
                    model="gpt-5.1",
                    input=[
                        {
                            "role": "user",
                            "content": [{"type": "input_text", "text": prompt}]
                        }
                    ],
                    temperature=0.3
                )

                # 응답 추출
                result_text = ""
                if getattr(response, "output_text", None):
                    result_text = response.output_text.strip()
                else:
                    for item in getattr(response, "output", []) or []:
                        for content in getattr(item, "content", []) or []:
                            if getattr(content, "type", "") == "text":
                                result_text += getattr(content, "text", "")

                # 줄 단위로 분리
                lines = [line.strip() for line in result_text.strip().split('\n') if line.strip()]

                if lines:
                    print(f"[SUBTITLE-SPLIT] GPT-5.1 분리 완료: {len(lines)}줄")
                    return lines
                else:
                    print("[SUBTITLE-SPLIT] GPT 응답 비어있음, 폴백 사용")
                    return split_korean_semantic_fallback(text)

            except Exception as e:
                print(f"[SUBTITLE-SPLIT] GPT 오류: {e}, 폴백 사용")
                return split_korean_semantic_fallback(text)

        def split_sentences(text, lang='en'):
            """텍스트를 자막 단위로 분리 - 문장 부호 기준 (모든 언어 동일)"""
            # 소수점(7.5)은 문장 끝이 아니므로 임시로 치환
            # 숫자.숫자 패턴을 임시 마커로 교체
            decimal_pattern = r'(\d)\.(\d)'
            text_safe = re.sub(decimal_pattern, r'\1<DECIMAL>\2', text.strip())

            # 문장 부호(. ! ?)로 분리
            sentences = re.split(r'(?<=[.!?。])\s*', text_safe)

            # 임시 마커를 다시 소수점으로 복원
            sentences = [s.replace('<DECIMAL>', '.').strip() for s in sentences if s.strip()]
            return sentences

        def split_korean_semantic_fallback(text, max_chars=20):
            """GPT 실패 시 폴백: 한국어 의미 기준 분리"""
            # 먼저 문장 단위로 분리
            sentences = re.split(r'(?<=[.!?])\s*', text.strip())
            sentences = [s.strip() for s in sentences if s.strip()]

            result = []
            for sentence in sentences:
                if len(sentence) <= max_chars:
                    result.append(sentence)
                else:
                    # 의미 단위로 분리 (조사, 접속사, 쉼표 등)
                    chunks = split_by_meaning_fallback(sentence, max_chars)
                    result.extend(chunks)

            return result

        def split_by_meaning_fallback(text, max_chars=20):
            """GPT 실패 시 폴백: 의미 단위로 텍스트 분리"""
            # 분리 우선순위: 쉼표 > 조사+공백 > 접속부사 > 강제 분리
            chunks = []
            remaining = text.strip()

            while remaining:
                if len(remaining) <= max_chars:
                    chunks.append(remaining)
                    break

                # 최대 길이 내에서 분리점 찾기
                search_range = remaining[:max_chars + 5]  # 약간 여유

                # 1. 쉼표에서 분리
                comma_pos = search_range.rfind(',')
                if comma_pos > 5:
                    chunks.append(remaining[:comma_pos + 1].strip())
                    remaining = remaining[comma_pos + 1:].strip()
                    continue

                # 2. 조사 + 공백에서 분리 (은/는/이/가/을/를/에/의/와/과/로/으로 등)
                patterns = [
                    r'(.{5,}?(?:은|는|이|가|을|를|에서|에게|으로|로|와|과|의|도|만|까지|부터|처럼|보다))\s',
                    r'(.{5,}?(?:하고|하면|하지만|그리고|그래서|하여|해서|했고|했지만))\s',
                ]
                found = False
                for pattern in patterns:
                    match = re.search(pattern, search_range)
                    if match and len(match.group(1)) <= max_chars:
                        split_pos = match.end(1)
                        chunks.append(remaining[:split_pos].strip())
                        remaining = remaining[split_pos:].strip()
                        found = True
                        break

                if found:
                    continue

                # 3. 공백에서 분리 (최대한 max_chars에 가깝게)
                space_pos = search_range[:max_chars].rfind(' ')
                if space_pos > 5:
                    chunks.append(remaining[:space_pos].strip())
                    remaining = remaining[space_pos:].strip()
                    continue

                # 4. 강제 분리 (max_chars에서 자르기)
                chunks.append(remaining[:max_chars].strip())
                remaining = remaining[max_chars:].strip()

            return chunks

        def get_mp3_duration(audio_bytes):
            """MP3 오디오 길이 측정 (초)"""
            # 임시 파일에 저장 후 ffprobe로 측정
            try:
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name

                cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    tmp_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                os.unlink(tmp_path)

                if result.returncode == 0 and result.stdout.strip():
                    return float(result.stdout.strip())
            except Exception as e:
                print(f"[ASSETS-ZIP] ffprobe failed: {e}")

            # 폴백: MP3 128kbps 기준 추정 (16KB/초)
            return len(audio_bytes) / 16000

        def convert_numbers_to_korean(text):
            """숫자를 한글로 변환 (TTS 자연스러운 읽기용)

            - 고유어 단위 (번, 개, 명, 살, 시, 마리, 잔, 병, 권, 대, 채, 장, 벌, 켤레, 그루, 송이):
              15번 → 열다섯번, 3개 → 세개
            - 한자어 단위 (원, 층, 년, 월, 일, 분, 초, 도, 호, 회, 배, km, m, kg, g):
              200원 → 이백원, 15층 → 십오층
            """
            import re

            # 고유어 숫자 (1~99)
            native_units = ['번', '개', '명', '살', '시', '마리', '잔', '병', '권', '대', '채', '장', '벌', '켤레', '그루', '송이', '군데', '가지', '줄', '쌍']
            native_ones = ['', '한', '두', '세', '네', '다섯', '여섯', '일곱', '여덟', '아홉']
            native_tens = ['', '열', '스물', '서른', '마흔', '쉰', '예순', '일흔', '여든', '아흔']

            def num_to_native(n):
                """숫자를 고유어로 변환 (1~99)"""
                if n <= 0 or n >= 100:
                    return str(n)
                tens = n // 10
                ones = n % 10
                return native_tens[tens] + native_ones[ones]

            # 한자어 숫자
            sino_digits = ['', '일', '이', '삼', '사', '오', '육', '칠', '팔', '구']

            def num_to_sino(n):
                """숫자를 한자어로 변환"""
                if n == 0:
                    return '영'
                if n < 0:
                    return '마이너스 ' + num_to_sino(-n)

                result = ''

                # 억 단위
                if n >= 100000000:
                    result += num_to_sino(n // 100000000) + '억'
                    n %= 100000000

                # 만 단위
                if n >= 10000:
                    man = n // 10000
                    if man == 1:
                        result += '만'
                    else:
                        result += num_to_sino(man) + '만'
                    n %= 10000

                # 천 단위
                if n >= 1000:
                    cheon = n // 1000
                    if cheon == 1:
                        result += '천'
                    else:
                        result += sino_digits[cheon] + '천'
                    n %= 1000

                # 백 단위
                if n >= 100:
                    baek = n // 100
                    if baek == 1:
                        result += '백'
                    else:
                        result += sino_digits[baek] + '백'
                    n %= 100

                # 십 단위
                if n >= 10:
                    sip = n // 10
                    if sip == 1:
                        result += '십'
                    else:
                        result += sino_digits[sip] + '십'
                    n %= 10

                # 일 단위
                if n > 0:
                    result += sino_digits[n]

                return result

            # 고유어 단위 패턴 (숫자 + 고유어단위)
            for unit in native_units:
                pattern = r'(\d+)' + re.escape(unit)
                def replace_native(match, u=unit):
                    num = int(match.group(1))
                    if 1 <= num <= 99:
                        return num_to_native(num) + u
                    else:
                        return num_to_sino(num) + u
                text = re.sub(pattern, replace_native, text)

            # 한자어 단위 패턴 (숫자 + 한자어단위) - 남은 숫자+단위
            sino_units = ['원', '층', '년', '월', '일', '분', '초', '도', '호', '회', '배', '위', '등', '점', '퍼센트', '%', 'km', 'm', 'kg', 'g', 'cm', 'mm', '원짜리', '달러', '엔', '유로']
            for unit in sino_units:
                pattern = r'(\d+)' + re.escape(unit)
                def replace_sino(match, u=unit):
                    num = int(match.group(1))
                    converted = num_to_sino(num)
                    # % → 퍼센트로 읽기
                    if u == '%':
                        u = '퍼센트'
                    return converted + u
                text = re.sub(pattern, replace_sino, text)

            # 곱하기/나누기 표현
            text = re.sub(r'(\d+)\s*[xX×]\s*(\d+)', lambda m: num_to_sino(int(m.group(1))) + ' 곱하기 ' + num_to_sino(int(m.group(2))), text)
            text = re.sub(r'(\d+)\s*[/÷]\s*(\d+)', lambda m: num_to_sino(int(m.group(1))) + ' 나누기 ' + num_to_sino(int(m.group(2))), text)

            # 소수점 숫자 (7.5 → 칠점오, 3.14 → 삼점일사)
            def convert_decimal(match):
                integer_part = match.group(1)
                decimal_part = match.group(2)
                unit = match.group(3) if match.lastindex >= 3 else ''

                # 정수 부분 변환
                result = num_to_sino(int(integer_part)) + '점'

                # 소수점 이하 각 자릿수 변환 (0.5 → 영점오)
                decimal_digits = ['영', '일', '이', '삼', '사', '오', '육', '칠', '팔', '구']
                for digit in decimal_part:
                    result += decimal_digits[int(digit)]

                return result + unit

            # 소수점 + 단위 패턴 (7.5일, 3.5kg 등)
            text = re.sub(r'(\d+)\.(\d+)(일|시간|분|초|km|m|kg|g|cm|mm|%|퍼센트|배|도|리터|L|ml)', convert_decimal, text)

            # 단위 없는 소수점 (그냥 7.5 등)
            text = re.sub(r'(\d+)\.(\d+)(?![가-힣a-zA-Z])', lambda m: convert_decimal(m), text)

            return text

        def generate_tts_for_sentence(text, voice_name, language_code, api_key):
            """단일 문장에 대한 TTS 생성 (SSML 자동 감지)"""
            # SSML 태그 감지
            ssml_tags = ['<speak>', '<prosody', '<emphasis', '<break']
            is_ssml = any(tag in text for tag in ssml_tags)

            if is_ssml:
                # SSML 모드: <speak> 태그가 없으면 추가
                if not text.strip().startswith('<speak>'):
                    text = f"<speak>{text}</speak>"
                # SSML 내부의 텍스트에서 숫자 변환 (태그 바깥만)
                if language_code.startswith('ko'):
                    # SSML 태그를 보존하면서 텍스트만 변환
                    def convert_text_in_ssml(ssml_text):
                        import re
                        # 태그를 플레이스홀더로 대체
                        tag_pattern = r'(<[^>]+>)'
                        parts = re.split(tag_pattern, ssml_text)
                        converted_parts = []
                        for part in parts:
                            if part.startswith('<'):
                                converted_parts.append(part)  # 태그는 그대로
                            else:
                                converted_parts.append(convert_numbers_to_korean(part))  # 텍스트만 변환
                        return ''.join(converted_parts)
                    text = convert_text_in_ssml(text)
                print(f"[TTS-SSML] 감정 표현 TTS: {text[:80]}...")
                tts_url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
                payload = {
                    "input": {"ssml": text},  # SSML 입력
                    "voice": {"languageCode": language_code, "name": voice_name},
                    "audioConfig": {"audioEncoding": "MP3"}  # SSML은 prosody로 속도/피치 제어
                }
            else:
                # 일반 텍스트 모드
                if language_code.startswith('ko'):
                    text = convert_numbers_to_korean(text)
                    print(f"[TTS] 숫자 변환 후: {text[:50]}...")
                tts_url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
                payload = {
                    "input": {"text": text},
                    "voice": {"languageCode": language_code, "name": voice_name},
                    "audioConfig": {"audioEncoding": "MP3", "speakingRate": 0.95, "pitch": 0}
                }

            response = requests.post(tts_url, json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                return base64.b64decode(result.get("audioContent", ""))
            else:
                print(f"[TTS] 에러: {response.status_code} - {response.text[:200]}")
            return None

        data = request.get_json()
        session_id = data.get('session_id', str(uuid.uuid4())[:8])
        base_voice = data.get('voice', 'ko-KR-Neural2-A')
        scenes = data.get('scenes', [])

        if not scenes:
            return jsonify({"ok": False, "error": "씬 데이터가 없습니다"}), 400

        api_key = os.getenv("GOOGLE_CLOUD_API_KEY", "")
        if not api_key:
            return jsonify({"ok": False, "error": "GOOGLE_CLOUD_API_KEY가 설정되지 않았습니다"}), 500

        print(f"[ASSETS-ZIP] Starting sentence-by-sentence TTS for {len(scenes)} scenes")

        # 결과 저장용
        all_sentence_audios = []  # [(scene_idx, sent_idx, audio_bytes, duration, text), ...]
        srt_entries = []
        current_time = 0.0

        # 씬별 메타데이터 (영상 생성용)
        scene_metadata = []  # [{image_url, audio_url, duration, subtitles: [{start, end, text}], language}]
        detected_lang_global = 'ko'  # 전체 언어 (마지막 감지된 언어)

        def strip_ssml_tags(text):
            """SSML 태그를 제거하고 순수 텍스트만 추출"""
            import re
            # 모든 SSML 태그 제거
            clean_text = re.sub(r'<[^>]+>', '', text)
            # 연속 공백 정리
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            return clean_text

        def is_ssml_content(text):
            """SSML 태그가 포함된 텍스트인지 확인"""
            ssml_tags = ['<speak>', '<prosody', '<emphasis', '<break']
            return any(tag in text for tag in ssml_tags)

        # 1. 각 씬의 문장별 TTS 생성
        for scene_idx, scene in enumerate(scenes):
            narration = scene.get('text', '')
            image_url = scene.get('image_url', '')
            if not narration:
                continue

            detected_lang = detect_language(narration)
            detected_lang_global = detected_lang  # 전체 언어 업데이트
            voice_name = get_voice_for_language(detected_lang, base_voice)
            language_code = get_language_code(detected_lang)

            # SSML 감지: SSML이면 TTS는 전체로 처리하여 감정 표현 유지
            has_ssml = is_ssml_content(narration)

            # 자막용 텍스트 분할 (SSML 태그 제거 후)
            plain_narration = strip_ssml_tags(narration) if has_ssml else narration
            subtitle_sentences = split_sentences(plain_narration, detected_lang)
            if not subtitle_sentences:
                subtitle_sentences = [plain_narration]

            scene_audios = []
            scene_start_time = current_time  # 씬 시작 시간
            scene_subtitles = []  # 씬 내 상대적 자막 타이밍
            scene_relative_time = 0.0

            if has_ssml:
                # ★ SSML 모드: 전체 나레이션을 하나의 TTS로 처리 (감정 표현 유지!)
                print(f"[ASSETS-ZIP] Scene {scene_idx + 1}: SSML 감정 표현 TTS (전체 처리)")

                # 전체 SSML 나레이션으로 TTS 생성
                audio_bytes = generate_tts_for_sentence(narration, voice_name, language_code, api_key)

                if audio_bytes:
                    total_duration = get_mp3_duration(audio_bytes)
                    scene_audios.append(audio_bytes)
                    all_sentence_audios.append((scene_idx, 0, audio_bytes))

                    # 자막 타이밍: 문장 글자 수 비율로 분배
                    total_chars = sum(len(s) for s in subtitle_sentences)
                    if total_chars == 0:
                        total_chars = 1

                    for sent_idx, sentence in enumerate(subtitle_sentences):
                        # 글자 수 비율로 duration 계산
                        char_ratio = len(sentence) / total_chars
                        sent_duration = total_duration * char_ratio

                        srt_entries.append({
                            'index': len(srt_entries) + 1,
                            'start': current_time,
                            'end': current_time + sent_duration,
                            'text': sentence
                        })
                        scene_subtitles.append({
                            'start': scene_relative_time,
                            'end': scene_relative_time + sent_duration,
                            'text': sentence
                        })

                        print(f"  Sent {sent_idx + 1}: {sent_duration:.2f}s (비례) - {sentence[:30]}...")
                        current_time += sent_duration
                        scene_relative_time += sent_duration
                else:
                    print(f"[ASSETS-ZIP] Scene {scene_idx + 1}: SSML TTS 실패, 문장별 폴백")
                    has_ssml = False  # 폴백하여 아래 문장별 처리로

            if not has_ssml:
                # 일반 모드: 문장별 TTS 생성 (정확한 싱크)
                sentences = subtitle_sentences
                print(f"[ASSETS-ZIP] Scene {scene_idx + 1}: {len(sentences)} sentences, lang={detected_lang}")

                for sent_idx, sentence in enumerate(sentences):
                    audio_bytes = generate_tts_for_sentence(sentence, voice_name, language_code, api_key)

                    if audio_bytes:
                        duration = get_mp3_duration(audio_bytes)
                        scene_audios.append(audio_bytes)

                        srt_entries.append({
                            'index': len(srt_entries) + 1,
                            'start': current_time,
                            'end': current_time + duration,
                            'text': sentence
                        })
                        scene_subtitles.append({
                            'start': scene_relative_time,
                            'end': scene_relative_time + duration,
                            'text': sentence
                        })

                        print(f"  Sent {sent_idx + 1}: {duration:.2f}s - {sentence[:30]}...")
                        current_time += duration
                        scene_relative_time += duration

                        all_sentence_audios.append((scene_idx, sent_idx, audio_bytes))

            # 씬 메타데이터 저장
            scene_duration = current_time - scene_start_time
            scene_metadata.append({
                'scene_idx': scene_idx,
                'image_url': image_url,
                'duration': scene_duration,
                'subtitles': scene_subtitles,
                'language': detected_lang
            })

            # 씬 간 짧은 간격 (무음 0.3초 추가 가능, 여기서는 시간만 조정)
            current_time += 0.3

        print(f"[ASSETS-ZIP] Total: {len(srt_entries)} sentences, {current_time:.1f}s")

        # 2. ZIP 파일 생성
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:

            # 이미지 다운로드 및 추가
            image_count = 0
            for idx, scene in enumerate(scenes):
                image_url = scene.get('image_url', '')
                if not image_url:
                    continue

                try:
                    if image_url.startswith('http'):
                        req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=30) as response:
                            img_data = response.read()
                    elif image_url.startswith('/'):
                        local_path = image_url.lstrip('/')
                        if os.path.exists(local_path):
                            with open(local_path, 'rb') as f:
                                img_data = f.read()
                        else:
                            continue
                    else:
                        continue

                    # 파일명: 01_scene.jpg, 02_scene.jpg, ...
                    filename = f"{str(idx + 1).zfill(2)}_scene.jpg"
                    zip_file.writestr(f"images/{filename}", img_data)
                    image_count += 1

                except Exception as e:
                    print(f"[ASSETS-ZIP] Failed to add image {idx + 1}: {e}")

            # 오디오 파일 추가 (문장별 + 씬별 병합 + 전체 병합)
            if all_sentence_audios:
                # 1. 문장별 개별 오디오 저장
                for scene_idx, sent_idx, audio_bytes in all_sentence_audios:
                    filename = f"{str(scene_idx + 1).zfill(2)}_{str(sent_idx + 1).zfill(2)}_sent.mp3"
                    zip_file.writestr(f"audio/sentences/{filename}", audio_bytes)

                # 2. 씬별 오디오 병합 (FFmpeg 사용) + uploads/ 저장
                scene_audio_map = {}  # {scene_idx: [audio_bytes, ...]}
                for scene_idx, sent_idx, audio_bytes in all_sentence_audios:
                    if scene_idx not in scene_audio_map:
                        scene_audio_map[scene_idx] = []
                    scene_audio_map[scene_idx].append(audio_bytes)

                # uploads 디렉토리 생성
                upload_dir = "uploads"
                os.makedirs(upload_dir, exist_ok=True)

                scene_merged_files = []
                for scene_idx in sorted(scene_audio_map.keys()):
                    audios = scene_audio_map[scene_idx]
                    try:
                        # 임시 파일들 생성
                        temp_files = []
                        for i, audio in enumerate(audios):
                            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                                tmp.write(audio)
                                temp_files.append(tmp.name)

                        # FFmpeg concat으로 병합
                        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w') as list_file:
                            for tf in temp_files:
                                list_file.write(f"file '{tf}'\n")
                            list_path = list_file.name

                        merged_path = tempfile.mktemp(suffix='.mp3')
                        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", merged_path]
                        # 메모리 최적화: stdout/stderr DEVNULL (OOM 방지)
                        merge_result = subprocess.run(
                            cmd,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=60
                        )
                        del merge_result
                        gc.collect()

                        if os.path.exists(merged_path):
                            with open(merged_path, 'rb') as f:
                                merged_audio = f.read()
                            filename = f"{str(scene_idx + 1).zfill(2)}_scene.mp3"
                            zip_file.writestr(f"audio/{filename}", merged_audio)

                            # uploads/에도 개별 저장 (영상 생성용)
                            audio_filename = f"{session_id}_scene_{str(scene_idx + 1).zfill(2)}.mp3"
                            audio_path = os.path.join(upload_dir, audio_filename)
                            with open(audio_path, 'wb') as f:
                                f.write(merged_audio)

                            # scene_metadata에 audio_url 추가
                            for sm in scene_metadata:
                                if sm['scene_idx'] == scene_idx:
                                    sm['audio_url'] = f"/uploads/{audio_filename}"
                                    break

                            scene_merged_files.append(merged_path)
                            os.unlink(merged_path)

                        # 임시 파일 정리
                        for tf in temp_files:
                            if os.path.exists(tf):
                                os.unlink(tf)
                        if os.path.exists(list_path):
                            os.unlink(list_path)

                    except Exception as e:
                        print(f"[ASSETS-ZIP] Scene {scene_idx + 1} merge failed: {e}")

                # 3. 전체 오디오 병합
                try:
                    all_audios = [audio for _, _, audio in all_sentence_audios]
                    temp_files = []
                    for audio in all_audios:
                        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                            tmp.write(audio)
                            temp_files.append(tmp.name)

                    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w') as list_file:
                        for tf in temp_files:
                            list_file.write(f"file '{tf}'\n")
                        list_path = list_file.name

                    full_merged_path = tempfile.mktemp(suffix='.mp3')
                    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", full_merged_path]
                    # 메모리 최적화: stdout/stderr DEVNULL (OOM 방지)
                    full_merge_result = subprocess.run(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=120
                    )
                    del full_merge_result
                    gc.collect()

                    if os.path.exists(full_merged_path):
                        with open(full_merged_path, 'rb') as f:
                            full_audio = f.read()
                        zip_file.writestr("audio/narration_full.mp3", full_audio)
                        os.unlink(full_merged_path)

                    for tf in temp_files:
                        if os.path.exists(tf):
                            os.unlink(tf)
                    if os.path.exists(list_path):
                        os.unlink(list_path)

                except Exception as e:
                    print(f"[ASSETS-ZIP] Full audio merge failed: {e}")

            # SRT 자막 파일 생성
            srt_content = ""
            for entry in srt_entries:
                start = format_srt_time(entry['start'])
                end = format_srt_time(entry['end'])
                srt_content += f"{entry['index']}\n{start} --> {end}\n{entry['text']}\n\n"

            zip_file.writestr("subtitles.srt", srt_content.encode('utf-8'))

            # 가이드 파일 추가
            guide_content = f"""CapCut 에셋 가이드
==================

📁 폴더 구조:
- images/ : 씬별 이미지 ({image_count}개)
- audio/narration_full.mp3 : 전체 나레이션 (싱크용)
- audio/01_scene.mp3, 02_scene.mp3... : 씬별 오디오
- audio/sentences/ : 문장별 개별 오디오
- subtitles.srt : 자막 파일 (정확한 싱크!)

🎬 CapCut 임포트 방법:
1. audio/narration_full.mp3를 오디오 트랙에 드래그
2. subtitles.srt를 자막으로 임포트 → 자동 싱크!
3. images 폴더의 이미지들을 타임라인에 배치

✨ 자막 싱크 정보:
- 문장별 TTS를 개별 생성하여 정확한 타이밍 측정
- SRT 파일의 시간이 실제 오디오와 정확히 일치합니다
- 총 {len(srt_entries)}개 자막, {current_time:.1f}초

생성일: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            zip_file.writestr("README.txt", guide_content.encode('utf-8'))

        # 3. ZIP 파일 저장
        zip_buffer.seek(0)
        zip_filename = f"capcut_assets_{session_id}.zip"
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        zip_path = os.path.join(upload_dir, zip_filename)

        with open(zip_path, 'wb') as f:
            f.write(zip_buffer.read())

        # 오디오 총 길이 계산
        total_duration = current_time
        minutes = int(total_duration // 60)
        seconds = int(total_duration % 60)
        duration_str = f"{minutes}분 {seconds}초"

        print(f"[ASSETS-ZIP] ZIP created: {zip_path}, images: {image_count}, duration: {duration_str}")

        return jsonify({
            "ok": True,
            "zip_url": f"/uploads/{zip_filename}",
            "image_count": image_count,
            "audio_duration": duration_str,
            "scene_metadata": scene_metadata,  # 영상 생성용 메타데이터
            "detected_language": detected_lang_global  # 감지된 언어
        })

    except Exception as e:
        print(f"[ASSETS-ZIP][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


def format_srt_time(seconds):
    """초를 SRT 시간 형식으로 변환 (00:00:00,000)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# ===== Image Lab 영상 생성 API (백그라운드 처리) =====

# 영상 생성 작업 상태 저장 (PostgreSQL 또는 파일 기반)
# PostgreSQL: 서버 재시작에도 작업 상태 유지됨
# 파일: 로컬 개발용 폴백
VIDEO_JOBS_DIR = "uploads/video_jobs"
os.makedirs(VIDEO_JOBS_DIR, exist_ok=True)

def _save_job_status(job_id, status_data):
    """작업 상태를 DB 또는 파일로 저장"""
    if USE_POSTGRES:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO video_jobs (job_id, status, progress, message, video_url, error, session_id, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (job_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    progress = EXCLUDED.progress,
                    message = EXCLUDED.message,
                    video_url = EXCLUDED.video_url,
                    error = EXCLUDED.error,
                    session_id = EXCLUDED.session_id,
                    updated_at = CURRENT_TIMESTAMP
            ''', (
                job_id,
                status_data.get('status', 'pending'),
                status_data.get('progress', 0),
                status_data.get('message', ''),
                status_data.get('video_url', ''),
                status_data.get('error', ''),
                status_data.get('session_id', '')
            ))
            conn.commit()
            cursor.close()
            conn.close()
            print(f"[VIDEO-JOB-DB] Saved job {job_id} to PostgreSQL")
        except Exception as e:
            print(f"[VIDEO-JOB-DB] Error saving to PostgreSQL: {e}, falling back to file")
            # 폴백: 파일 저장
            job_file = os.path.join(VIDEO_JOBS_DIR, f"{job_id}.json")
            with open(job_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False)
    else:
        job_file = os.path.join(VIDEO_JOBS_DIR, f"{job_id}.json")
        with open(job_file, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, ensure_ascii=False)

def _load_job_status(job_id):
    """작업 상태를 DB 또는 파일에서 로드"""
    if USE_POSTGRES:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT job_id, status, progress, message, video_url, error, session_id
                FROM video_jobs WHERE job_id = %s
            ''', (job_id,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if row:
                return {
                    'job_id': row['job_id'],
                    'status': row['status'],
                    'progress': row['progress'],
                    'message': row['message'],
                    'video_url': row['video_url'],
                    'error': row['error'],
                    'session_id': row['session_id']
                }
            return None
        except Exception as e:
            print(f"[VIDEO-JOB-DB] Error loading from PostgreSQL: {e}, falling back to file")
            # 폴백: 파일에서 로드
            job_file = os.path.join(VIDEO_JOBS_DIR, f"{job_id}.json")
            if os.path.exists(job_file):
                with open(job_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
    else:
        job_file = os.path.join(VIDEO_JOBS_DIR, f"{job_id}.json")
        if os.path.exists(job_file):
            with open(job_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

def _update_job_status(job_id, **kwargs):
    """작업 상태 부분 업데이트"""
    if USE_POSTGRES:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 동적 UPDATE 쿼리 생성
            update_fields = []
            values = []
            for key, value in kwargs.items():
                if key in ['status', 'progress', 'message', 'video_url', 'error', 'session_id']:
                    update_fields.append(f"{key} = %s")
                    values.append(value)

            if update_fields:
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                values.append(job_id)
                query = f"UPDATE video_jobs SET {', '.join(update_fields)} WHERE job_id = %s"
                cursor.execute(query, values)
                conn.commit()

            cursor.close()
            conn.close()
        except Exception as e:
            print(f"[VIDEO-JOB-DB] Error updating PostgreSQL: {e}, falling back to file")
            # 폴백: 파일 업데이트
            status = _load_job_status(job_id)
            if status:
                status.update(kwargs)
                job_file = os.path.join(VIDEO_JOBS_DIR, f"{job_id}.json")
                with open(job_file, 'w', encoding='utf-8') as f:
                    json.dump(status, f, ensure_ascii=False)
    else:
        status = _load_job_status(job_id)
        if status:
            status.update(kwargs)
            job_file = os.path.join(VIDEO_JOBS_DIR, f"{job_id}.json")
            with open(job_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False)

def _get_subtitle_style(lang):
    """언어별 자막 스타일 반환 (ASS 형식) - 폰트28 기준"""
    # 유튜브 스타일: 흰색 텍스트 + 검은색 외곽선 + 그림자
    if lang == 'ko':
        # Pretendard - 프리텐다드 (한글 전용)
        # Outline=2 (두꺼운 외곽선), MarginV=40 (하단 여백)
        return (
            "FontName=Pretendard,FontSize=28,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BackColour=&H80000000,"
            "BorderStyle=1,Outline=2,Shadow=1,MarginV=40,Bold=1"
        )
    elif lang == 'ja':
        # 일본어 - Pretendard 사용 (CJK 지원)
        return (
            "FontName=Pretendard,FontSize=26,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BackColour=&H80000000,"
            "BorderStyle=1,Outline=2,Shadow=1,MarginV=40,Bold=1"
        )
    else:
        # 영어/기타 언어
        return (
            "FontName=Pretendard,FontSize=22,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BackColour=&H80000000,"
            "BorderStyle=1,Outline=2,Shadow=1,MarginV=40,Bold=1"
        )

def _hex_to_ass_color(hex_color):
    """HEX 색상을 ASS 포맷으로 변환 (#RRGGBB -> &HBBGGRR&)"""
    if not hex_color or not hex_color.startswith('#'):
        return "&H00FFFF&"  # 기본 노란색
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        return f"&H{b}{g}{r}&"
    return "&H00FFFF&"


def _apply_subtitle_highlights(text, highlights):
    """자막 텍스트에 키워드 색상 강조 적용

    Args:
        text: 원본 자막 텍스트
        highlights: [{"keyword": "단어", "color": "#FF0000"}, ...]

    Returns:
        색상 태그가 적용된 텍스트 (ASS override tags)
    """
    if not highlights:
        return text

    result = text
    for h in highlights:
        keyword = h.get('keyword', '')
        color = h.get('color', '#FFFF00')
        if keyword and keyword in result:
            ass_color = _hex_to_ass_color(color)
            # ASS 색상 태그 적용: {\c&HBBGGRR&}텍스트{\c&HFFFFFF&}
            colored_keyword = f"{{\\c{ass_color}}}{keyword}{{\\c&HFFFFFF&}}"
            result = result.replace(keyword, colored_keyword)

    return result


def _format_ass_time(seconds):
    """초를 ASS 시간 형식으로 변환 (H:MM:SS.cc)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def _generate_ass_subtitles(subtitles, highlights, output_path, lang='ko'):
    """ASS 형식 자막 파일 생성 (색상 강조 지원)

    Args:
        subtitles: [{"start": 0.0, "end": 3.0, "text": "자막"}, ...]
        highlights: [{"keyword": "단어", "color": "#FF0000"}, ...]
        output_path: ASS 파일 출력 경로
        lang: 언어 코드

    Returns:
        성공 여부
    """
    try:
        # 언어별 폰트 설정 (큰 자막 - 50대+ 시청자 가독성)
        if lang == 'ko':
            font_name = "Pretendard"
            font_size = 48  # 24 → 48 (2배 크기)
        else:
            font_name = "Pretendard"
            font_size = 44  # 22 → 44 (2배 크기)

        # ASS 헤더 (큰 폰트, 두꺼운 테두리, 하단 중앙 정렬)
        # Outline: 2 → 4 (더 두꺼운 테두리)
        # Shadow: 1 → 2 (더 진한 그림자)
        # MarginV: 40 → 50 (하단 여백)
        ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,30,30,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        # 이벤트 생성
        events = []
        for sub in subtitles:
            start = _format_ass_time(sub['start'])
            end = _format_ass_time(sub['end'])
            text = sub.get('text', '')

            # 색상 강조 적용
            if highlights:
                text = _apply_subtitle_highlights(text, highlights)

            # ASS에서는 \N이 줄바꿈
            text = text.replace('\n', '\\N')

            events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_header)
            f.write('\n'.join(events))

        print(f"[ASS] 자막 생성 완료: {len(subtitles)}개 자막, {len(highlights)}개 강조 키워드")
        return True

    except Exception as e:
        print(f"[ASS] 자막 생성 오류: {e}")
        return False


def _generate_screen_overlay_filter(screen_overlays, scenes, fonts_dir):
    """화면 텍스트 오버레이용 FFmpeg drawtext 필터 생성

    Args:
        screen_overlays: [{"scene": 3, "text": "대박!", "duration": 3, "style": "impact"}, ...]
        scenes: 씬 목록 (duration 계산용)
        fonts_dir: 폰트 디렉토리 경로

    Returns:
        FFmpeg drawtext 필터 문자열 또는 None
    """
    if not screen_overlays:
        return None

    # 씬별 시작 시간 계산
    scene_start_times = {}
    current_time = 0
    for idx, scene in enumerate(scenes):
        scene_start_times[idx + 1] = current_time  # 1-based index
        current_time += scene.get('duration', 0)

    filters = []
    font_path = os.path.join(fonts_dir, "Pretendard-Bold.ttf")
    font_escaped = font_path.replace('\\', '/').replace(':', '\\:')

    for overlay in screen_overlays:
        scene_num = overlay.get('scene', 1)
        text = overlay.get('text', '')
        duration = overlay.get('duration', 3)
        style = overlay.get('style', 'impact')

        if not text or scene_num not in scene_start_times:
            print(f"[OVERLAY] 스킵: text='{text}', scene={scene_num}, available_scenes={list(scene_start_times.keys())}")
            continue

        start_time = scene_start_times[scene_num]
        end_time = start_time + duration

        # 스타일별 설정
        if style == 'impact':
            # 빨간 테두리, 흰 텍스트, 큰 글씨
            fontcolor = "white"
            bordercolor = "red"
            fontsize = 80
            borderw = 4
        elif style == 'dramatic':
            # 노란 텍스트, 검정 배경
            fontcolor = "yellow"
            bordercolor = "black"
            fontsize = 70
            borderw = 3
        elif style == 'emotional':
            # 부드러운 파란 텍스트
            fontcolor = "cyan"
            bordercolor = "darkblue"
            fontsize = 60
            borderw = 2
        else:
            fontcolor = "white"
            bordercolor = "black"
            fontsize = 70
            borderw = 3

        # FFmpeg drawtext 텍스트 이스케이프
        # 특수 문자 이스케이프: : = ' \ 를 백슬래시로 이스케이프
        text_escaped = text.replace('\\', '\\\\').replace("'", "\\'").replace(':', '\\:').replace('=', '\\=')

        print(f"[OVERLAY] 추가: scene={scene_num}, text='{text}', style={style}, time={start_time:.1f}-{end_time:.1f}s")

        # drawtext 필터 생성 (화면 중앙에 표시)
        drawtext = (
            f"drawtext=text='{text_escaped}':"
            f"fontfile='{font_escaped}':"
            f"fontsize={fontsize}:"
            f"fontcolor={fontcolor}:"
            f"bordercolor={bordercolor}:"
            f"borderw={borderw}:"
            f"x=(w-text_w)/2:"
            f"y=(h-text_h)/2:"
            f"enable='between(t,{start_time},{end_time})'"
        )
        filters.append(drawtext)

    if filters:
        return ",".join(filters)
    return None


def _generate_lower_thirds_filter(lower_thirds, scenes, fonts_dir):
    """로워서드(하단 자막) 오버레이용 FFmpeg drawtext 필터 생성

    Args:
        lower_thirds: [{"scene": 2, "text": "출처: OO일보", "position": "bottom-left"}, ...]
        scenes: 씬 목록 (duration 계산용)
        fonts_dir: 폰트 디렉토리 경로

    Returns:
        FFmpeg drawtext 필터 문자열 또는 None
    """
    if not lower_thirds:
        return None

    # 씬별 시작 시간 계산
    scene_start_times = {}
    scene_durations = {}
    current_time = 0
    for idx, scene in enumerate(scenes):
        scene_start_times[idx + 1] = current_time  # 1-based index
        scene_durations[idx + 1] = scene.get('duration', 0)
        current_time += scene.get('duration', 0)

    filters = []
    font_path = os.path.join(fonts_dir, "Pretendard-SemiBold.ttf")
    font_escaped = font_path.replace('\\', '/').replace(':', '\\:')

    for lt in lower_thirds:
        scene_num = lt.get('scene', 1)
        text = lt.get('text', '')
        position = lt.get('position', 'bottom-left')

        if not text or scene_num not in scene_start_times:
            continue

        start_time = scene_start_times[scene_num]
        # 로워서드는 씬 전체 동안 표시 (페이드인/아웃)
        scene_duration = scene_durations.get(scene_num, 5)
        end_time = start_time + scene_duration

        # 위치별 좌표 설정
        if position == 'bottom-left':
            x_pos = "30"
            y_pos = "h-th-80"  # 하단에서 80px 위
        elif position == 'bottom-right':
            x_pos = "w-tw-30"
            y_pos = "h-th-80"
        elif position == 'bottom-center':
            x_pos = "(w-tw)/2"
            y_pos = "h-th-80"
        else:  # default: bottom-left
            x_pos = "30"
            y_pos = "h-th-80"

        # 반투명 배경 박스 + 텍스트 (뉴스 스타일)
        # 배경 박스 필터 (drawbox)
        box_filter = (
            f"drawbox=x={x_pos}-10:y={y_pos}-10:"
            f"w=tw+20:h=th+20:"
            f"color=black@0.7:t=fill:"
            f"enable='between(t,{start_time},{end_time})'"
        )

        # 텍스트 필터
        text_escaped = text.replace("'", "'\\''").replace(":", "\\:")
        text_filter = (
            f"drawtext=text='{text_escaped}':"
            f"fontfile='{font_escaped}':"
            f"fontsize=28:"
            f"fontcolor=white:"
            f"x={x_pos}:"
            f"y={y_pos}:"
            f"enable='between(t,{start_time},{end_time})'"
        )

        # drawbox는 text_w를 모르므로 대략적인 크기 사용
        # 더 정확한 방법: 텍스트만 표시 (배경 없이)
        # 또는 box=1:boxcolor=black@0.7:boxborderw=10 사용
        text_with_bg = (
            f"drawtext=text='{text_escaped}':"
            f"fontfile='{font_escaped}':"
            f"fontsize=28:"
            f"fontcolor=white:"
            f"box=1:"
            f"boxcolor=black@0.7:"
            f"boxborderw=10:"
            f"x={x_pos}:"
            f"y={y_pos}:"
            f"enable='between(t,{start_time},{end_time})'"
        )

        filters.append(text_with_bg)

    if filters:
        return ",".join(filters)
    return None


def _generate_news_ticker_filter(news_ticker, total_duration, fonts_dir):
    """뉴스 티커(스크롤 헤드라인) 필터 생성

    Args:
        news_ticker: {"enabled": true, "headlines": ["속보: ...", "이슈: ..."]}
        total_duration: 전체 영상 길이 (초)
        fonts_dir: 폰트 디렉토리 경로

    Returns:
        FFmpeg drawtext 필터 문자열 또는 None
    """
    if not news_ticker or not news_ticker.get('enabled'):
        return None

    headlines = news_ticker.get('headlines', [])
    if not headlines:
        return None

    # 헤드라인을 하나의 긴 텍스트로 연결 (구분자: ●)
    ticker_text = "   ●   ".join(headlines) + "   ●   " + headlines[0]  # 반복을 위해 첫 번째 추가
    ticker_text = ticker_text.replace("'", "'\\''").replace(":", "\\:")

    font_path = os.path.join(fonts_dir, "Pretendard-Bold.ttf")
    font_escaped = font_path.replace('\\', '/').replace(':', '\\:')

    # 스크롤 속도: 전체 영상 동안 텍스트가 2-3번 정도 지나가도록
    # x = w - (mod(t * speed, tw + w))
    # speed = (tw + w) / (total_duration / scroll_cycles)
    scroll_speed = 100  # 초당 100픽셀 이동

    # 뉴스 티커 스타일: 하단에 빨간 배경 + 흰 텍스트
    # 참고: drawbox에서 w=w는 순환 참조 에러 발생, iw(입력 너비) 사용
    ticker_filter = (
        f"drawbox=x=0:y=ih-40:w=iw:h=40:color=red@0.9:t=fill,"
        f"drawtext=text='{ticker_text}':"
        f"fontfile='{font_escaped}':"
        f"fontsize=24:"
        f"fontcolor=white:"
        f"x=w-mod(t*{scroll_speed}\\,tw+w):"
        f"y=h-35"
    )

    return ticker_filter


def _get_bgm_file(mood, bgm_dir=None):
    """분위기에 맞는 BGM 파일 선택 (여러 개면 랜덤)

    Args:
        mood: hopeful, sad, tense, dramatic, calm, inspiring, mysterious, nostalgic
        bgm_dir: BGM 파일 디렉토리 (없으면 스크립트 위치 기준)

    Returns:
        BGM 파일 경로 또는 None
    """
    import glob
    import random

    # 스크립트 위치 기준 절대 경로 사용
    if bgm_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        bgm_dir = os.path.join(script_dir, "static", "audio", "bgm")

    print(f"[BGM] 검색 시작: mood='{mood}', dir='{bgm_dir}'")

    if not mood:
        print(f"[BGM] mood가 비어있음")
        return None

    if not os.path.exists(bgm_dir):
        print(f"[BGM] 디렉토리 없음: {bgm_dir}")
        print(f"[BGM] ⚠️ BGM 파일을 {bgm_dir}에 업로드하세요. 예: {mood}.mp3, {mood}_01.mp3")
        return None

    # 파일명 패턴: mood.mp3, mood_01.mp3, mood (1).mp3 등
    patterns = [
        os.path.join(bgm_dir, f"{mood}.mp3"),
        os.path.join(bgm_dir, f"{mood}_*.mp3"),
        os.path.join(bgm_dir, f"{mood} *.mp3"),  # 공백 포함
        os.path.join(bgm_dir, f"{mood}*.mp3"),
    ]

    matching_files = []
    for pattern in patterns:
        found = glob.glob(pattern)
        matching_files.extend(found)

    # 중복 제거
    matching_files = list(set(matching_files))

    # 디렉토리 내 모든 파일 출력 (디버그용)
    all_files = glob.glob(os.path.join(bgm_dir, "*.mp3"))
    print(f"[BGM] 디렉토리 내 전체 파일: {[os.path.basename(f) for f in all_files]}")

    if not matching_files:
        print(f"[BGM] '{mood}' 분위기 BGM 파일 없음")
        print(f"[BGM] ⚠️ {bgm_dir}/{mood}.mp3 또는 {mood}_01.mp3 형식으로 파일을 업로드하세요")
        return None

    # 랜덤 선택
    selected = random.choice(matching_files)
    print(f"[BGM] 선택된 BGM: {selected} (후보 {len(matching_files)}개 중)")
    return selected


def _mix_bgm_with_video(video_path, bgm_path, output_path, bgm_volume=0.15):
    """비디오에 BGM 믹싱 (나레이션 유지, BGM은 작게)

    Args:
        video_path: 원본 비디오 경로
        bgm_path: BGM 오디오 경로
        output_path: 출력 비디오 경로
        bgm_volume: BGM 볼륨 (0.0~1.0, 기본 0.15 = 15%)

    Returns:
        성공 여부 (bool)
    """
    try:
        # 비디오 길이 확인
        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", video_path]
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        video_duration = float(result.stdout.strip())

        print(f"[BGM] 비디오 길이: {video_duration:.1f}초")

        # FFmpeg 명령: BGM 루프 + 볼륨 조절 + 믹싱 + 페이드아웃
        # -stream_loop -1: BGM 무한 루프
        # volume: BGM 볼륨 낮춤
        # amix: 오디오 믹싱
        # afade: 마지막 3초 페이드아웃

        fade_start = max(0, video_duration - 3)  # 마지막 3초

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", video_path,                          # 원본 비디오 (오디오 포함)
            "-stream_loop", "-1", "-i", bgm_path,      # BGM 루프
            "-filter_complex",
            f"[1:a]volume={bgm_volume},afade=t=in:st=0:d=2,afade=t=out:st={fade_start}:d=3[bgm];"  # BGM 볼륨+페이드
            f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",  # 믹싱
            "-map", "0:v",                             # 비디오 스트림
            "-map", "[aout]",                          # 믹싱된 오디오
            "-c:v", "copy",                            # 비디오 재인코딩 안함
            "-c:a", "aac", "-b:a", "128k",            # 오디오 인코딩
            "-shortest",                               # 비디오 길이에 맞춤
            output_path
        ]

        print(f"[BGM] 믹싱 시작...")
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, timeout=600)

        if result.returncode == 0:
            print(f"[BGM] 믹싱 완료: {output_path}")
            return True
        else:
            stderr = result.stderr.decode('utf-8', errors='ignore')[:300]
            print(f"[BGM] 믹싱 실패: {stderr}")
            return False

    except Exception as e:
        print(f"[BGM] 믹싱 오류: {e}")
        return False


def _get_sfx_file(sfx_type, sfx_dir=None):
    """효과음 타입에 맞는 파일 선택 (여러 개면 랜덤)

    Args:
        sfx_type: impact, whoosh, ding, tension, emotional, success
        sfx_dir: 효과음 파일 디렉토리 (없으면 스크립트 위치 기준)

    Returns:
        효과음 파일 경로 또는 None
    """
    import glob
    import random

    # 스크립트 위치 기준 절대 경로 사용
    if sfx_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sfx_dir = os.path.join(script_dir, "static", "audio", "sfx")

    print(f"[SFX] 검색 시작: type='{sfx_type}', dir='{sfx_dir}'")

    if not sfx_type:
        print(f"[SFX] sfx_type이 비어있음")
        return None

    if not os.path.exists(sfx_dir):
        print(f"[SFX] 디렉토리 없음: {sfx_dir}")
        print(f"[SFX] ⚠️ 효과음 파일을 {sfx_dir}에 업로드하세요. 예: {sfx_type}.mp3")
        return None

    patterns = [
        os.path.join(sfx_dir, f"{sfx_type}.mp3"),
        os.path.join(sfx_dir, f"{sfx_type}_*.mp3"),
        os.path.join(sfx_dir, f"{sfx_type}*.mp3"),
    ]

    matching_files = []
    for pattern in patterns:
        matching_files.extend(glob.glob(pattern))

    matching_files = list(set(matching_files))

    # 디렉토리 내 모든 파일 출력 (디버그용)
    all_files = glob.glob(os.path.join(sfx_dir, "*.mp3"))
    print(f"[SFX] 디렉토리 내 전체 파일: {[os.path.basename(f) for f in all_files]}")

    if not matching_files:
        print(f"[SFX] '{sfx_type}' 효과음 파일 없음")
        print(f"[SFX] ⚠️ {sfx_dir}/{sfx_type}.mp3 형식으로 파일을 업로드하세요")
        return None

    selected = random.choice(matching_files)
    print(f"[SFX] 선택된 효과음: {selected}")
    return selected


def _trim_sfx(input_path, output_path, max_duration=2.5, fade_out=0.5):
    """효과음을 지정 길이로 자르고 페이드아웃 적용

    Args:
        input_path: 원본 효과음 경로
        output_path: 출력 경로
        max_duration: 최대 길이 (초)
        fade_out: 페이드아웃 길이 (초)

    Returns:
        성공 여부 (bool)
    """
    try:
        fade_start = max(0, max_duration - fade_out)
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-t", str(max_duration),
            "-af", f"afade=t=out:st={fade_start}:d={fade_out}",
            "-c:a", "libmp3lame", "-q:a", "2",
            output_path
        ]
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, timeout=30)
        return result.returncode == 0
    except Exception as e:
        print(f"[SFX] 트림 오류: {e}")
        return False


def _mix_sfx_into_video(video_path, sound_effects, scenes, output_path, sfx_dir=None):
    """비디오에 효과음 믹싱

    Args:
        video_path: 원본 비디오 경로
        sound_effects: [{"scene": 1, "type": "impact"}, ...]
        scenes: 씬 목록 (타이밍 계산용)
        output_path: 출력 비디오 경로
        sfx_dir: 효과음 디렉토리 (없으면 스크립트 위치 기준)

    Returns:
        성공 여부 (bool)
    """
    if not sound_effects:
        return False

    try:
        import tempfile

        # 스크립트 위치 기준 절대 경로 사용
        if sfx_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            sfx_dir = os.path.join(script_dir, "static", "audio", "sfx")

        print(f"[SFX] 효과음 디렉토리: {sfx_dir}")
        print(f"[SFX] 디렉토리 존재 여부: {os.path.exists(sfx_dir)}")
        if os.path.exists(sfx_dir):
            import glob
            all_sfx = glob.glob(os.path.join(sfx_dir, "*.mp3"))
            print(f"[SFX] 디렉토리 내 전체 파일: {[os.path.basename(f) for f in all_sfx]}")

        # 씬별 시작 시간 계산
        scene_start_times = {}
        current_time = 0
        for idx, scene in enumerate(scenes):
            scene_start_times[idx + 1] = current_time
            current_time += scene.get('duration', 0)

        # 효과음 파일 준비 및 타이밍 계산
        sfx_inputs = []
        adelay_filters = []

        temp_dir = tempfile.mkdtemp()

        for i, sfx in enumerate(sound_effects):
            scene_num = sfx.get('scene', 1)
            sfx_type = sfx.get('type', '')

            if scene_num not in scene_start_times:
                continue

            # 효과음 파일 찾기 (None 전달 시 절대 경로 사용)
            sfx_file = _get_sfx_file(sfx_type)
            if not sfx_file:
                continue

            # 효과음 트림 (2.5초로 자르기)
            trimmed_path = os.path.join(temp_dir, f"sfx_{i}.mp3")
            if not _trim_sfx(sfx_file, trimmed_path, max_duration=2.5, fade_out=0.5):
                continue

            # 딜레이 계산 (씬 시작 + 0.5초)
            delay_ms = int((scene_start_times[scene_num] + 0.5) * 1000)

            sfx_inputs.append(trimmed_path)
            adelay_filters.append(f"[{i+1}:a]adelay={delay_ms}|{delay_ms},volume=0.8[sfx{i}]")

        if not sfx_inputs:
            print(f"[SFX] 사용 가능한 효과음 없음")
            return False

        # FFmpeg 명령 구성
        input_args = ["-i", video_path]
        for sfx_path in sfx_inputs:
            input_args.extend(["-i", sfx_path])

        # 필터 구성: 모든 효과음 + 원본 오디오 믹싱
        filter_parts = adelay_filters.copy()

        # amix로 모든 오디오 합치기
        sfx_labels = "".join([f"[sfx{i}]" for i in range(len(sfx_inputs))])
        mix_inputs = len(sfx_inputs) + 1  # 효과음 개수 + 원본 오디오
        filter_parts.append(f"[0:a]{sfx_labels}amix=inputs={mix_inputs}:duration=first:dropout_transition=2[aout]")

        filter_complex = ";".join(filter_parts)

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            *input_args,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            output_path
        ]

        print(f"[SFX] 효과음 {len(sfx_inputs)}개 믹싱 중...")
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, timeout=600)

        # 임시 파일 정리
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

        if result.returncode == 0:
            print(f"[SFX] 효과음 믹싱 완료")
            return True
        else:
            stderr = result.stderr.decode('utf-8', errors='ignore')[:300]
            print(f"[SFX] 믹싱 실패: {stderr}")
            return False

    except Exception as e:
        print(f"[SFX] 믹싱 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


def _generate_outro_video(output_path, duration=5, fonts_dir=None):
    """공용 아웃트로 영상 생성 (구독/좋아요 요청)

    Args:
        output_path: 출력 파일 경로
        duration: 아웃트로 길이 (초)
        fonts_dir: 폰트 디렉토리 (없으면 스크립트 위치 기준)

    Returns:
        성공 여부 (bool)
    """
    try:
        # 스크립트 위치 기준 절대 경로 사용
        if fonts_dir is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            fonts_dir = os.path.join(script_dir, "fonts")

        print(f"[OUTRO] 폰트 디렉토리: {fonts_dir}")
        print(f"[OUTRO] 디렉토리 존재: {os.path.exists(fonts_dir)}")

        # 폰트 우선순위: Pretendard-Bold > Pretendard-SemiBold > NanumGothicBold
        font_path = os.path.join(fonts_dir, "Pretendard-Bold.ttf")
        if not os.path.exists(font_path):
            font_path = os.path.join(fonts_dir, "Pretendard-SemiBold.ttf")
        if not os.path.exists(font_path):
            font_path = os.path.join(fonts_dir, "NanumGothicBold.ttf")
        if not os.path.exists(font_path):
            print(f"[OUTRO] 폰트 파일 없음: {fonts_dir}")
            return False

        print(f"[OUTRO] 사용 폰트: {font_path}")
        font_escaped = font_path.replace('\\', '/').replace(':', '\\:')

        # 그라데이션 배경 + 텍스트 아웃트로
        # 메인 영상과 동일한 1280x720 해상도 사용 (concat 호환성)
        # 이모지 제거 (FFmpeg drawtext 호환성 문제)
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x1a1a2e:s=1280x720:d={duration}",
            "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
            "-vf", (
                f"drawtext=text='시청해 주셔서 감사합니다':"
                f"fontfile='{font_escaped}':fontsize=48:fontcolor=white:"
                f"x=(w-text_w)/2:y=(h-text_h)/2-70,"
                f"drawtext=text='좋아요와 구독 부탁드려요':"
                f"fontfile='{font_escaped}':fontsize=38:fontcolor=yellow:"
                f"x=(w-text_w)/2:y=(h-text_h)/2+15,"
                f"drawtext=text='알림 설정도 잊지 마세요':"
                f"fontfile='{font_escaped}':fontsize=30:fontcolor=#aaaaaa:"
                f"x=(w-text_w)/2:y=(h-text_h)/2+80,"
                f"fade=t=in:st=0:d=0.5,fade=t=out:st={duration-0.5}:d=0.5"
            ),
            # 메인 영상과 동일한 인코딩 설정 (concat demuxer 호환)
            "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.0",
            "-pix_fmt", "yuv420p", "-r", "24",  # 24fps (메인 영상과 동일)
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-movflags", "+faststart",
            "-t", str(duration),
            output_path
        ]

        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, timeout=60)

        if result.returncode == 0:
            print(f"[OUTRO] 아웃트로 생성 완료 (1280x720, 24fps): {output_path}")
            return True
        else:
            stderr = result.stderr.decode('utf-8', errors='ignore')[:300]
            print(f"[OUTRO] 생성 실패: {stderr}")
            return False

    except Exception as e:
        print(f"[OUTRO] 오류: {e}")
        return False


def _append_outro_to_video(video_path, outro_path, output_path):
    """비디오에 아웃트로 연결 (concat demuxer 사용 - 재인코딩 없이 빠름)

    Args:
        video_path: 원본 비디오 경로
        outro_path: 아웃트로 비디오 경로
        output_path: 출력 비디오 경로

    Returns:
        성공 여부 (bool)
    """
    try:
        # concat demuxer 방식 사용 (재인코딩 없이 스트림 복사 - 매우 빠름)
        # 단, 두 파일의 코덱/해상도/프레임레이트가 동일해야 함
        work_dir = os.path.dirname(output_path)
        concat_list_path = os.path.join(work_dir, "concat_list.txt")

        # concat 리스트 파일 생성
        with open(concat_list_path, 'w', encoding='utf-8') as f:
            f.write(f"file '{os.path.abspath(video_path)}'\n")
            f.write(f"file '{os.path.abspath(outro_path)}'\n")

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",  # 스트림 복사 (재인코딩 없음)
            "-movflags", "+faststart",
            output_path
        ]

        # concat demuxer + copy는 매우 빠름 (60초면 충분)
        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, timeout=60)

        # 임시 파일 삭제
        if os.path.exists(concat_list_path):
            os.remove(concat_list_path)

        if result.returncode == 0:
            print(f"[OUTRO] 아웃트로 연결 완료 (concat demuxer): {output_path}")
            return True
        else:
            stderr = result.stderr.decode('utf-8', errors='ignore')[-500:]
            print(f"[OUTRO] concat demuxer 실패: {stderr}")

            # Fallback: concat filter 사용 (재인코딩 필요하지만 호환성 높음)
            print(f"[OUTRO] Fallback: concat filter 사용...")
            ffmpeg_cmd_fallback = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", outro_path,
                "-filter_complex",
                "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]",
                "-map", "[outv]", "-map", "[outa]",
                "-c:v", "libx264", "-preset", "ultrafast",  # 더 빠른 프리셋
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]

            result_fallback = subprocess.run(ffmpeg_cmd_fallback, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.PIPE, timeout=1200)  # 20분 타임아웃

            if result_fallback.returncode == 0:
                print(f"[OUTRO] 아웃트로 연결 완료 (concat filter fallback): {output_path}")
                return True
            else:
                stderr_fb = result_fallback.stderr.decode('utf-8', errors='ignore')[-300:]
                print(f"[OUTRO] concat filter도 실패: {stderr_fb}")
                return False

    except Exception as e:
        print(f"[OUTRO] 연결 오류: {e}")
        return False


def _analyze_shorts_content_gpt(highlight_narrations, title, detected_category, audience="general", duration_target=45):
    """GPT-5.1로 쇼츠 전용 콘텐츠 분석 및 beats 구조 생성

    Args:
        highlight_narrations: 하이라이트 씬들의 나레이션 목록
        title: 원본 영상 제목
        detected_category: news 또는 story
        audience: general 또는 senior
        duration_target: 목표 길이 (초)

    Returns:
        dict: beats 구조, meta, design_guide 등
    """
    try:
        from openai import OpenAI
        client = OpenAI()

        # 나레이션에서 핵심 포인트 추출
        combined_narration = "\n".join(highlight_narrations)
        main_points = highlight_narrations[:3] if len(highlight_narrations) >= 3 else highlight_narrations

        # short_type 결정
        short_type = "해설" if detected_category == "news" else "사례소개"

        # audience_needs 설정
        if audience == "senior":
            audience_desc = "50-70대 시니어"
            audience_needs = ["짧은 시간에 핵심만 알고 싶다", "복잡한 설명 없이 요점만"]
        else:
            audience_desc = "20-40대 직장인"
            audience_needs = ["출퇴근 1분 안에 핵심만", "지금 당장 뭘 해야 하는지"]

        system_prompt = f'''너는 "유튜브 쇼츠 전담 PD + 편집 디렉터 + 각본가"다.
뉴스·시사·경제·정보 콘텐츠를 쇼츠 포맷(60초 이하)으로 최적화하는 전문가다.

목표:
1) 1.5초 안에 스크롤을 멈추는 강력한 훅
2) 완주율 80-90% 목표의 구조 설계
3) 편집자가 그대로 따라 만들 수 있는 씬 단위 설계서(JSON)

## 포맷 규격
- 방향: 세로 9:16 (1080x1920)
- 길이: 35-60초 (정보/해설형)
- 첫 1.5-3초 안에 스크롤 멈추는 훅 필수

## 입력값
- short_topic: "{title}"
- short_type: "{short_type}"
- main_audience: "{audience_desc}"
- audience_needs: {audience_needs}
- main_point_1: "{main_points[0] if len(main_points) > 0 else ''}"
- main_point_2: "{main_points[1] if len(main_points) > 1 else ''}"
- main_point_3: "{main_points[2] if len(main_points) > 2 else ''}"
- duration_target_sec: {duration_target}
- hook_angle_preference: "숫자, 솔루션"

## beats 설계 규칙
- 1.0-3.0초 단위의 beat를 연속 설계
- 기본 구조:
  - Beat 1: hook (0-2초) - 12-18자, 3초 이내 낭독
  - Beat 2: 상황/문제 제기 (2-6초)
  - Beat 3-4: 핵심 포인트 1,2 (6-18초)
  - Beat 5-6: 핵심 포인트 3 + 반전/경고 (18-35초)
  - Beat 7: 요약 + CTA or loop (마지막 3-5초)

## 각 beat 필수 포함
- voiceover: TTS용 자연스러운 구어체
- on_screen_text: 핵심 1-2줄 (16자 내외)
- visual_type: A-roll_talking_head / B-roll / infographic / text_only
- visual_direction: 화면 구성 설명
- broll_idea_or_prompt: AI 이미지 생성용 영어 프롬프트
- caption_style: {{ use_captions, emphasis_words, position }}
- sound_direction: {{ bgm_mood, sfx, pause_hint }}

## 출력 형식 (JSON ONLY)
JSON 외부에 어떤 텍스트도 쓰지 말 것.'''

        user_prompt = f'''원본 영상의 하이라이트 나레이션:
{combined_narration}

위 내용을 기반으로 {duration_target}초 쇼츠를 설계해줘.
훅은 "숫자 + 위험/기회 + 타깃"을 조합해서 강력하게 만들어.

JSON 형식으로만 출력해. 다른 텍스트 없이 순수 JSON만.'''

        print(f"[SHORTS-GPT] 쇼츠 콘텐츠 분석 시작...")

        response = client.responses.create(
            model="gpt-5.1",
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]}
            ],
            temperature=0.7
        )

        # 결과 추출
        if getattr(response, "output_text", None):
            result_text = response.output_text.strip()
        else:
            text_chunks = []
            for item in getattr(response, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    if getattr(content, "type", "") == "text":
                        text_chunks.append(getattr(content, "text", ""))
            result_text = "\n".join(text_chunks).strip()

        # JSON 파싱
        print(f"[SHORTS-GPT] GPT 응답 길이: {len(result_text)}자")
        print(f"[SHORTS-GPT] GPT 응답 (처음 500자): {result_text[:500]}")

        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()

        import re
        result_text = re.sub(r',\s*\]', ']', result_text)
        result_text = re.sub(r',\s*\}', '}', result_text)

        try:
            result = json.loads(result_text)
        except json.JSONDecodeError as je:
            print(f"[SHORTS-GPT] JSON 파싱 실패: {je}")
            print(f"[SHORTS-GPT] 파싱 시도한 텍스트: {result_text[:1000]}")
            return None

        beats = result.get("structure", {}).get("beats", [])
        print(f"[SHORTS-GPT] 분석 완료: {len(beats)}개 beats 생성")
        if len(beats) == 0:
            print(f"[SHORTS-GPT] 경고: beats 없음. result keys: {list(result.keys())}")

        return result

    except Exception as e:
        print(f"[SHORTS-GPT] 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


def _generate_shorts_video_v2(shorts_analysis, voice_name, output_path, base_url="http://localhost:5000"):
    """쇼츠 전용 영상 생성 (새 TTS + 새 9:16 이미지 + 세로 자막)

    Args:
        shorts_analysis: GPT-5.1 쇼츠 분석 결과 (beats 포함)
        voice_name: TTS 음성 이름
        output_path: 출력 파일 경로
        base_url: API 서버 URL

    Returns:
        dict: {ok, shorts_path, duration, cost}
    """
    import requests as req
    import tempfile
    import shutil

    print(f"[SHORTS-V2] 쇼츠 영상 생성 시작 (방법 2: 새 TTS + 새 이미지)")

    try:
        beats = shorts_analysis.get("structure", {}).get("beats", [])
        if not beats:
            return {"ok": False, "error": "beats 데이터 없음"}

        print(f"[SHORTS-V2] {len(beats)}개 beats 처리 시작")

        temp_dir = tempfile.mkdtemp()
        total_cost = 0.0
        beat_data = []  # [{audio_path, image_path, duration, subtitles, on_screen_text}]

        try:
            # ========== 1. 각 beat별 TTS + 이미지 생성 ==========
            for idx, beat in enumerate(beats):
                beat_id = beat.get("id", idx + 1)
                voiceover = beat.get("voiceover", "")
                on_screen_text = beat.get("on_screen_text", "")
                visual_direction = beat.get("visual_direction", "")
                broll_prompt = beat.get("broll_idea_or_prompt", "")
                caption_style = beat.get("caption_style", {})

                print(f"[SHORTS-V2] Beat {beat_id}: {voiceover[:30]}...")

                # 1-1. TTS 생성
                audio_path = os.path.join(temp_dir, f"beat_{beat_id:02d}_audio.mp3")
                try:
                    tts_resp = req.post(f"{base_url}/api/tts/generate", json={
                        "text": voiceover,
                        "voice": voice_name,
                        "language": "ko"
                    }, timeout=60)

                    if tts_resp.status_code == 200:
                        tts_data = tts_resp.json()
                        if tts_data.get("ok"):
                            # 오디오 URL에서 다운로드
                            audio_url = tts_data.get("audio_url", "")
                            if audio_url:
                                audio_resp = req.get(f"{base_url}{audio_url}", timeout=30)
                                with open(audio_path, "wb") as f:
                                    f.write(audio_resp.content)
                                total_cost += len(voiceover) * 0.000004
                                print(f"[SHORTS-V2] Beat {beat_id} TTS 완료")
                except Exception as tts_err:
                    print(f"[SHORTS-V2] Beat {beat_id} TTS 실패: {tts_err}")
                    # TTS 실패 시 무음 생성
                    subprocess.run([
                        "ffmpeg", "-y", "-f", "lavfi",
                        "-i", f"anullsrc=r=44100:cl=mono",
                        "-t", "3", audio_path
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # 오디오 길이 측정
                duration = 3.0  # 기본값
                if os.path.exists(audio_path):
                    probe_result = subprocess.run([
                        "ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
                    ], capture_output=True, text=True)
                    if probe_result.returncode == 0:
                        try:
                            duration = float(probe_result.stdout.strip())
                        except:
                            pass

                # 1-2. 9:16 세로 이미지 생성
                image_path = os.path.join(temp_dir, f"beat_{beat_id:02d}_image.png")
                try:
                    # 세로 이미지용 프롬프트 구성
                    image_prompt = broll_prompt if broll_prompt else f"Vertical 9:16 background for: {visual_direction}"
                    image_prompt += ", vertical 9:16 aspect ratio, 1080x1920, mobile-optimized, high contrast"

                    img_resp = req.post(f"{base_url}/api/drama/generate-image", json={
                        "prompt": image_prompt,
                        "size": "1080x1920",  # 세로 크기
                        "imageProvider": "gemini"
                    }, timeout=120)

                    if img_resp.status_code == 200:
                        img_data = img_resp.json()
                        if img_data.get("ok"):
                            img_url = img_data.get("image_url", "")
                            if img_url:
                                if img_url.startswith("http"):
                                    img_download = req.get(img_url, timeout=30)
                                else:
                                    img_download = req.get(f"{base_url}{img_url}", timeout=30)
                                with open(image_path, "wb") as f:
                                    f.write(img_download.content)
                                total_cost += 0.02
                                print(f"[SHORTS-V2] Beat {beat_id} 이미지 완료")
                except Exception as img_err:
                    print(f"[SHORTS-V2] Beat {beat_id} 이미지 실패: {img_err}")
                    # 이미지 실패 시 단색 배경 생성
                    subprocess.run([
                        "ffmpeg", "-y", "-f", "lavfi",
                        "-i", "color=c=0x1a1a2e:s=1080x1920:d=1",
                        "-frames:v", "1", image_path
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # 자막 정보 저장
                emphasis_words = caption_style.get("emphasis_words", [])

                beat_data.append({
                    "beat_id": beat_id,
                    "audio_path": audio_path,
                    "image_path": image_path,
                    "duration": duration,
                    "voiceover": voiceover,
                    "on_screen_text": on_screen_text,
                    "emphasis_words": emphasis_words
                })

            # ========== 2. 각 beat를 클립으로 합성 ==========
            print(f"[SHORTS-V2] 클립 합성 시작...")
            clip_paths = []

            for bd in beat_data:
                clip_path = os.path.join(temp_dir, f"clip_{bd['beat_id']:02d}.mp4")

                # 이미지 + 오디오 + 자막 합성
                # 자막 필터 (하단 safe zone)
                voiceover_escaped = bd['voiceover'].replace("'", "'\\''").replace(":", "\\:")

                # 폰트 경로
                font_path = "fonts/Pretendard-Bold.ttf"
                if not os.path.exists(font_path):
                    font_path = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
                font_escaped = font_path.replace("\\", "/").replace(":", "\\:")

                # 자막 필터 (하단 20% 영역)
                subtitle_filter = (
                    f"drawtext=text='{voiceover_escaped}':"
                    f"fontfile='{font_escaped}':fontsize=42:fontcolor=white:"
                    f"borderw=3:bordercolor=black:"
                    f"x=(w-text_w)/2:y=h*0.82:"
                    f"line_spacing=10"
                )

                # on_screen_text 오버레이 (상단 15% 영역)
                if bd['on_screen_text']:
                    text_escaped = bd['on_screen_text'].replace("'", "'\\''").replace(":", "\\:")
                    subtitle_filter += (
                        f",drawtext=text='{text_escaped}':"
                        f"fontfile='{font_escaped}':fontsize=56:fontcolor=yellow:"
                        f"borderw=4:bordercolor=black:"
                        f"x=(w-text_w)/2:y=h*0.08"
                    )

                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", bd['image_path'],
                    "-i", bd['audio_path'],
                    "-vf", subtitle_filter,
                    "-c:v", "libx264", "-preset", "fast",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                    "-pix_fmt", "yuv420p",
                    "-t", str(bd['duration']),
                    "-shortest",
                    clip_path
                ]

                result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
                if result.returncode == 0 and os.path.exists(clip_path):
                    clip_paths.append(clip_path)
                    print(f"[SHORTS-V2] 클립 {bd['beat_id']} 완료 ({bd['duration']:.1f}초)")
                else:
                    stderr = result.stderr.decode('utf-8', errors='ignore')[:200]
                    print(f"[SHORTS-V2] 클립 {bd['beat_id']} 실패: {stderr}")

            if not clip_paths:
                return {"ok": False, "error": "클립 생성 실패"}

            # ========== 3. 클립 병합 ==========
            print(f"[SHORTS-V2] {len(clip_paths)}개 클립 병합...")
            concat_list = os.path.join(temp_dir, "concat.txt")
            with open(concat_list, 'w') as f:
                for clip_path in clip_paths:
                    f.write(f"file '{os.path.abspath(clip_path)}'\n")

            # 병합
            concat_cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-c:v", "libx264", "-preset", "fast",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]

            result = subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180)

            if result.returncode == 0 and os.path.exists(output_path):
                # 최종 영상 길이 확인
                probe_result = subprocess.run([
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", output_path
                ], capture_output=True, text=True)

                final_duration = 0
                if probe_result.returncode == 0:
                    try:
                        final_duration = float(probe_result.stdout.strip())
                    except:
                        pass

                print(f"[SHORTS-V2] 쇼츠 생성 완료: {output_path} ({final_duration:.1f}초)")

                return {
                    "ok": True,
                    "shorts_path": output_path,
                    "duration": final_duration,
                    "cost": total_cost,
                    "beats_count": len(beats)
                }
            else:
                stderr = result.stderr.decode('utf-8', errors='ignore')[:300]
                return {"ok": False, "error": f"병합 실패: {stderr}"}

        finally:
            # 임시 파일 정리
            shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        print(f"[SHORTS-V2] 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


def _generate_shorts_video(main_video_path, scenes, highlight_scenes, hook_text, output_path):
    """메인 영상에서 쇼츠용 세로 영상(9:16) 생성 [레거시 - 크롭 방식]

    Args:
        main_video_path: 원본 메인 영상 경로
        scenes: 씬 정보 목록 (duration 포함)
        highlight_scenes: 하이라이트 씬 번호 목록 [1, 2, 3]
        hook_text: 쇼츠 시작 훅 텍스트
        output_path: 출력 경로

    Returns:
        성공 여부 (bool)
    """
    print(f"[SHORTS] 쇼츠 생성 시작")
    print(f"[SHORTS] 메인 영상: {main_video_path}, 존재: {os.path.exists(main_video_path)}")
    print(f"[SHORTS] 씬 수: {len(scenes) if scenes else 0}")
    print(f"[SHORTS] 하이라이트 씬: {highlight_scenes}")
    print(f"[SHORTS] 훅 텍스트: {hook_text}")
    print(f"[SHORTS] 출력 경로: {output_path}")

    try:
        import tempfile
        import shutil

        # 씬별 시작/종료 시간 계산
        scene_times = []
        current_time = 0
        for idx, scene in enumerate(scenes):
            duration = scene.get('duration', 5)
            scene_times.append({
                'scene_num': idx + 1,
                'start': current_time,
                'end': current_time + duration,
                'duration': duration
            })
            current_time += duration

        # 하이라이트 씬 추출 (60초 이하로 제한)
        selected_clips = []
        total_duration = 0
        max_duration = 58  # 60초 제한 (여유 2초)

        for scene_num in highlight_scenes:
            if scene_num < 1 or scene_num > len(scene_times):
                continue
            scene_info = scene_times[scene_num - 1]
            if total_duration + scene_info['duration'] <= max_duration:
                selected_clips.append(scene_info)
                total_duration += scene_info['duration']
            else:
                # 남은 시간만큼만 추가
                remaining = max_duration - total_duration
                if remaining > 3:  # 최소 3초 이상일 때만 추가
                    selected_clips.append({
                        **scene_info,
                        'end': scene_info['start'] + remaining,
                        'duration': remaining
                    })
                    total_duration += remaining
                break

        if not selected_clips:
            print(f"[SHORTS] 선택된 클립 없음")
            return False

        print(f"[SHORTS] {len(selected_clips)}개 클립 선택, 총 {total_duration:.1f}초")

        # 임시 디렉토리 생성
        temp_dir = tempfile.mkdtemp()
        concat_list = os.path.join(temp_dir, "concat.txt")

        try:
            # 각 하이라이트 클립 추출 및 세로 변환
            clip_paths = []
            for i, clip in enumerate(selected_clips):
                clip_path = os.path.join(temp_dir, f"clip_{i:03d}.mp4")

                # 가로(16:9) → 세로(9:16) 변환 + 클립 추출
                # 중앙 크롭 + 블러 배경 방식
                vf_filter = (
                    # 원본을 1080x1920 세로 비율로 크롭 (중앙)
                    "scale=1080:1920:force_original_aspect_ratio=increase,"
                    "crop=1080:1920,"
                    # 자막 위치 조정 (하단)
                    "setsar=1"
                )

                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(clip['start']),
                    "-i", main_video_path,
                    "-t", str(clip['duration']),
                    "-vf", vf_filter,
                    "-c:v", "libx264", "-preset", "fast",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                    "-pix_fmt", "yuv420p",
                    clip_path
                ]

                result = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.PIPE, timeout=120)
                if result.returncode == 0 and os.path.exists(clip_path):
                    clip_paths.append(clip_path)
                    print(f"[SHORTS] 클립 {i+1}/{len(selected_clips)} 추출 완료")
                else:
                    stderr = result.stderr.decode('utf-8', errors='ignore')[:200]
                    print(f"[SHORTS] 클립 {i+1} 추출 실패: {stderr}")

            if not clip_paths:
                print(f"[SHORTS] 클립 추출 실패")
                return False

            # concat 파일 생성
            with open(concat_list, 'w') as f:
                for clip_path in clip_paths:
                    f.write(f"file '{os.path.abspath(clip_path)}'\n")

            # 클립 병합
            merged_path = os.path.join(temp_dir, "merged.mp4")
            concat_cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-c", "copy",
                merged_path
            ]
            result = subprocess.run(concat_cmd, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, timeout=120)

            if result.returncode != 0:
                stderr = result.stderr.decode('utf-8', errors='ignore')[:200]
                print(f"[SHORTS] 클립 병합 실패: {stderr}")
                return False

            # 훅 텍스트 오버레이 추가 (처음 3초)
            if hook_text:
                font_path = "fonts/Pretendard-Bold.ttf"
                font_escaped = font_path.replace('\\', '/').replace(':', '\\:')

                hook_filter = (
                    f"drawtext=text='{hook_text}':"
                    f"fontfile='{font_escaped}':fontsize=48:fontcolor=white:"
                    f"borderw=3:bordercolor=black:"
                    f"x=(w-text_w)/2:y=h*0.15:"
                    f"enable='lt(t,3)'"  # 처음 3초만 표시
                )

                final_cmd = [
                    "ffmpeg", "-y",
                    "-i", merged_path,
                    "-vf", hook_filter,
                    "-c:v", "libx264", "-preset", "fast",
                    "-c:a", "copy",
                    output_path
                ]
            else:
                final_cmd = ["cp", merged_path, output_path]

            result = subprocess.run(final_cmd, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, timeout=120)

            if result.returncode == 0 and os.path.exists(output_path):
                print(f"[SHORTS] 쇼츠 생성 완료: {output_path}")
                return True
            else:
                stderr = result.stderr.decode('utf-8', errors='ignore')[:200]
                print(f"[SHORTS] 최종 생성 실패: {stderr}")
                return False

        finally:
            # 임시 파일 정리
            shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        print(f"[SHORTS] 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


def _apply_transitions(clip_paths, output_path, transition_style="crossfade", duration=0.5):
    """클립들 사이에 전환 효과 적용

    Args:
        clip_paths: 클립 파일 경로 목록
        output_path: 출력 파일 경로
        transition_style: crossfade, fade_black, fade_white, none
        duration: 전환 효과 길이 (초)

    Returns:
        성공 여부 (bool)
    """
    if not clip_paths or len(clip_paths) < 2:
        # 클립이 1개 이하면 전환 효과 불필요
        if clip_paths:
            import shutil
            shutil.copy(clip_paths[0], output_path)
            return True
        return False

    try:
        if transition_style == "none":
            # 전환 효과 없이 단순 concat
            import tempfile
            concat_list = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
            for clip_path in clip_paths:
                concat_list.write(f"file '{os.path.abspath(clip_path)}'\n")
            concat_list.close()

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list.name,
                "-c", "copy",
                output_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, timeout=300)
            os.unlink(concat_list.name)
            return result.returncode == 0

        # xfade 필터로 전환 효과 적용
        n = len(clip_paths)

        # 입력 파일 옵션
        input_args = []
        for clip_path in clip_paths:
            input_args.extend(["-i", clip_path])

        # xfade 필터 체인 구성
        # fade 색상 설정
        fade_color = "black" if transition_style == "fade_black" else "white" if transition_style == "fade_white" else None

        if n == 2:
            # 2개 클립: 단일 xfade
            if fade_color:
                filter_complex = f"[0:v]fade=t=out:st=0:d={duration}:color={fade_color}[v0];[1:v]fade=t=in:st=0:d={duration}:color={fade_color}[v1];[v0][v1]concat=n=2:v=1:a=0[outv];[0:a][1:a]concat=n=2:v=0:a=1[outa]"
            else:
                # crossfade
                filter_complex = f"[0:v][1:v]xfade=transition=fade:duration={duration}:offset=0[outv];[0:a][1:a]acrossfade=d={duration}[outa]"
        else:
            # 3개 이상: 체인 xfade (복잡, 단순화)
            # 간단하게 각 클립에 fade in/out 적용 후 concat
            filter_parts = []
            for i in range(n):
                if fade_color:
                    filter_parts.append(f"[{i}:v]fade=t=in:st=0:d={duration/2}:color={fade_color},fade=t=out:st=0:d={duration/2}:color={fade_color}[v{i}]")
                else:
                    filter_parts.append(f"[{i}:v]fade=t=in:st=0:d={duration/2},fade=t=out:st=0:d={duration/2}[v{i}]")

            video_concat = "".join([f"[v{i}]" for i in range(n)]) + f"concat=n={n}:v=1:a=0[outv]"
            audio_concat = "".join([f"[{i}:a]" for i in range(n)]) + f"concat=n={n}:v=0:a=1[outa]"

            filter_complex = ";".join(filter_parts) + ";" + video_concat + ";" + audio_concat

        cmd = [
            "ffmpeg", "-y",
            *input_args,
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k",
            output_path
        ]

        print(f"[TRANSITIONS] {transition_style} 효과 적용 중 ({n}개 클립)...")
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, timeout=600)

        if result.returncode == 0:
            print(f"[TRANSITIONS] 전환 효과 적용 완료")
            return True
        else:
            stderr = result.stderr.decode('utf-8', errors='ignore')[:300]
            print(f"[TRANSITIONS] 실패: {stderr}")
            # 실패 시 단순 concat으로 폴백
            print(f"[TRANSITIONS] 단순 concat으로 폴백...")
            return _apply_transitions(clip_paths, output_path, "none", 0)

    except Exception as e:
        print(f"[TRANSITIONS] 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


def _upload_youtube_captions(video_id, srt_path, language="ko", credentials=None):
    """YouTube에 자막 파일(.srt) 업로드

    Args:
        video_id: YouTube 비디오 ID
        srt_path: SRT 자막 파일 경로
        language: 자막 언어 코드 (ko, en, ja 등)
        credentials: Google OAuth 자격 증명

    Returns:
        성공 여부 (bool)
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        if not credentials:
            print(f"[CAPTIONS] 자격 증명 없음")
            return False

        if not os.path.exists(srt_path):
            print(f"[CAPTIONS] 자막 파일 없음: {srt_path}")
            return False

        youtube = build('youtube', 'v3', credentials=credentials)

        # 자막 삽입 요청
        caption_body = {
            "snippet": {
                "videoId": video_id,
                "language": language,
                "name": "Korean" if language == "ko" else language.upper(),
                "isDraft": False
            }
        }

        media = MediaFileUpload(srt_path, mimetype='application/x-subrip', resumable=True)

        request = youtube.captions().insert(
            part="snippet",
            body=caption_body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[CAPTIONS] 업로드 진행률: {int(status.progress() * 100)}%")

        print(f"[CAPTIONS] 자막 업로드 완료: {response.get('id')}")
        return True

    except Exception as e:
        print(f"[CAPTIONS] 업로드 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


def _get_ken_burns_filter(effect_type, duration, fps=24, output_size="1280x720"):
    """Ken Burns 효과용 zoompan 필터 생성 - 부드러운 sin/cos 모션

    Args:
        effect_type: zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down
        duration: 클립 길이 (초)
        fps: 프레임 레이트
        output_size: 출력 해상도

    Returns:
        FFmpeg vf filter string (scale + zoompan + fade)
    """
    total_frames = int(duration * fps)
    w, h = map(int, output_size.split('x'))

    # 부드러운 움직임을 위한 설정
    # 이미지를 크게 스케일해서 패닝/줌 시 검정 테두리 방지
    scale_w = int(w * 1.4)  # 40% 더 크게
    scale_h = int(h * 1.4)

    fade_in = min(0.5, duration * 0.1)  # 페이드인 (최대 0.5초)
    fade_out = min(0.5, duration * 0.1)  # 페이드아웃 (최대 0.5초)
    fade_out_start = max(0, duration - fade_out)

    # 각 효과별 설정 (sin/cos로 매우 부드러운 움직임)
    # on: 현재 프레임 번호, total_frames: 전체 프레임 수
    # ★ 느린 움직임: sin/cos 주기 2배, 움직임 범위 1/2
    if effect_type == 'zoom_in':
        # 천천히 줌인 + 아주 미세한 패닝
        zoom_expr = f"1.0+0.08*on/{total_frames}"  # 1.0 → 1.08로 (더 작은 줌)
        x_expr = f"(iw-{w})/2+8*sin(on/120)"  # 좌우 아주 미세 (주기 120)
        y_expr = f"(ih-{h})/2+6*cos(on/150)"  # 상하 아주 미세 (주기 150)
    elif effect_type == 'zoom_out':
        # 천천히 줌아웃 + 아주 미세한 패닝
        zoom_expr = f"1.08-0.08*on/{total_frames}"  # 1.08 → 1.0으로
        x_expr = f"(iw-{w})/2-8*sin(on/120)"
        y_expr = f"(ih-{h})/2-6*cos(on/150)"
    elif effect_type == 'pan_left':
        # 오른쪽에서 왼쪽으로 아주 천천히 패닝
        zoom_expr = "1.03"  # 줌 거의 없음
        x_expr = f"(iw-{w})*0.6*(1-on/{total_frames})+5*sin(on/100)"  # 부드러운 패닝
        y_expr = f"(ih-{h})/2+4*cos(on/140)"
    elif effect_type == 'pan_right':
        # 왼쪽에서 오른쪽으로 아주 천천히 패닝
        zoom_expr = "1.03"
        x_expr = f"(iw-{w})*0.4+(iw-{w})*0.2*on/{total_frames}+5*sin(on/100)"
        y_expr = f"(ih-{h})/2+4*cos(on/140)"
    elif effect_type == 'pan_up':
        # 아래에서 위로 아주 천천히 패닝
        zoom_expr = "1.03"
        x_expr = f"(iw-{w})/2+5*sin(on/120)"
        y_expr = f"(ih-{h})*0.6*(1-on/{total_frames})+4*cos(on/100)"
    elif effect_type == 'pan_down':
        # 위에서 아래로 아주 천천히 패닝
        zoom_expr = "1.03"
        x_expr = f"(iw-{w})/2+5*sin(on/120)"
        y_expr = f"(ih-{h})*0.4+(ih-{h})*0.2*on/{total_frames}+4*cos(on/100)"
    else:
        # 기본: 줌인 + 아주 미세한 움직임
        zoom_expr = f"1.0+0.08*on/{total_frames}"
        x_expr = f"(iw-{w})/2+8*sin(on/120)"
        y_expr = f"(ih-{h})/2+6*cos(on/150)"

    # 필터 체인: scale(크게) → zoompan(부드러운 움직임) → fade(페이드인/아웃)
    vf_filter = (
        f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
        f"crop={scale_w}:{scale_h},"
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={total_frames}:s={output_size}:fps={fps},"
        f"fade=t=in:st=0:d={fade_in},fade=t=out:st={fade_out_start}:d={fade_out}"
    )

    return vf_filter


def _generate_video_worker(job_id, session_id, scenes, detected_lang, video_effects=None):
    """백그라운드 영상 생성 워커

    video_effects 구조:
    {
        "bgm_mood": "hopeful/sad/tense/dramatic/calm/inspiring/mysterious/nostalgic",
        "subtitle_highlights": [{"keyword": "단어", "color": "#FF0000"}],
        "sound_effects": [{"scene": 1, "type": "impact", "moment": "..."}],
        "lower_thirds": [{"scene": 2, "text": "출처", "position": "bottom-left"}]
    }
    """
    import subprocess
    import shutil
    import urllib.request
    import gc  # 메모리 정리용

    if video_effects is None:
        video_effects = {}

    # FFmpeg 세마포어 획득 (다른 FFmpeg 작업과 동시 실행 방지 - 메모리 보호)
    print(f"[VIDEO-WORKER] FFmpeg 세마포어 대기 중...")
    ffmpeg_semaphore.acquire()
    print(f"[VIDEO-WORKER] FFmpeg 세마포어 획득, 영상 생성 시작...")

    try:
        _update_job_status(job_id, status='processing', message='영상 생성 시작...')

        # === video_effects 디버그 로깅 ===
        print(f"[VIDEO-WORKER] ========== VIDEO EFFECTS 설정 ==========")
        print(f"[VIDEO-WORKER] bgm_mood: {video_effects.get('bgm_mood', '(없음)')}")
        print(f"[VIDEO-WORKER] subtitle_highlights: {len(video_effects.get('subtitle_highlights', []))}개")
        print(f"[VIDEO-WORKER] screen_overlays: {len(video_effects.get('screen_overlays', []))}개")
        print(f"[VIDEO-WORKER] sound_effects: {len(video_effects.get('sound_effects', []))}개")
        print(f"[VIDEO-WORKER] lower_thirds: {len(video_effects.get('lower_thirds', []))}개")
        print(f"[VIDEO-WORKER] news_ticker enabled: {video_effects.get('news_ticker', {}).get('enabled', False)}")
        print(f"[VIDEO-WORKER] shorts highlight_scenes: {video_effects.get('shorts', {}).get('highlight_scenes', [])}")
        print(f"[VIDEO-WORKER] transitions style: {video_effects.get('transitions', {}).get('style', 'none')}")
        print(f"[VIDEO-WORKER] add_outro: {video_effects.get('add_outro', True)}")
        print(f"[VIDEO-WORKER] ============================================")

        total_scenes = len(scenes)
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)

        # 작업 디렉토리 생성 (tempfile 대신 직접 관리)
        work_dir = os.path.join(upload_dir, f"work_{job_id}")
        os.makedirs(work_dir, exist_ok=True)

        try:
            scene_videos = []
            all_subtitles = []
            current_time = 0.0

            # 1. 각 씬별 영상 클립 생성
            for idx, scene in enumerate(scenes):
                progress = int((idx / total_scenes) * 70)
                _update_job_status(job_id, progress=progress, message=f'씬 {idx + 1}/{total_scenes} 처리 중...')

                image_url = scene.get('image_url', '')
                audio_url = scene.get('audio_url', '')
                duration = scene.get('duration', 5.0)
                subtitles = scene.get('subtitles', [])

                print(f"[VIDEO-WORKER] Scene {idx + 1}: duration={duration:.2f}s")

                if not image_url:
                    continue

                # 이미지 다운로드
                img_path = os.path.join(work_dir, f"scene_{idx:03d}.jpg")
                print(f"[VIDEO-WORKER] Scene {idx + 1} image_url: {image_url[:100]}...")
                try:
                    if image_url.startswith('http'):
                        req = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=30) as response:
                            with open(img_path, 'wb') as f:
                                f.write(response.read())
                    elif image_url.startswith('/'):
                        local_path = image_url.lstrip('/')
                        if os.path.exists(local_path):
                            shutil.copy(local_path, img_path)
                        else:
                            print(f"[VIDEO-WORKER] Local image not found: {local_path}")
                            continue
                except Exception as e:
                    print(f"[VIDEO-WORKER] Image download failed: {e}")
                    continue

                # 이미지 파일 검증
                if not os.path.exists(img_path):
                    print(f"[VIDEO-WORKER] Image file not created: {img_path}")
                    continue
                img_size = os.path.getsize(img_path)
                print(f"[VIDEO-WORKER] Scene {idx + 1} image saved: {img_size} bytes")

                # 오디오 다운로드
                audio_path = None
                if audio_url:
                    audio_path = os.path.join(work_dir, f"audio_{idx:03d}.mp3")
                    try:
                        if audio_url.startswith('http'):
                            req = urllib.request.Request(audio_url, headers={'User-Agent': 'Mozilla/5.0'})
                            with urllib.request.urlopen(req, timeout=30) as response:
                                with open(audio_path, 'wb') as f:
                                    f.write(response.read())
                        elif audio_url.startswith('/'):
                            local_path = audio_url.lstrip('/')
                            if os.path.exists(local_path):
                                shutil.copy(local_path, audio_path)
                    except Exception as e:
                        print(f"[VIDEO-WORKER] Audio download failed: {e}")
                        audio_path = None

                # 자막 시간 조정
                for sub in subtitles:
                    all_subtitles.append({
                        'start': current_time + sub.get('start', 0),
                        'end': current_time + sub.get('end', duration),
                        'text': sub.get('text', '')
                    })
                current_time += duration

                # Ken Burns 효과 가져오기 (씬별로 다른 효과 적용)
                ken_burns_effect = scene.get('ken_burns', None)
                if not ken_burns_effect:
                    # 씬별로 다양한 효과 자동 배정 (다이나믹한 영상을 위해)
                    effects_cycle = ['zoom_in', 'pan_right', 'zoom_out', 'pan_left', 'zoom_in', 'pan_up']
                    ken_burns_effect = effects_cycle[idx % len(effects_cycle)]

                ken_burns_filter = _get_ken_burns_filter(ken_burns_effect, duration)
                print(f"[VIDEO-WORKER] Scene {idx + 1} Ken Burns: {ken_burns_effect}")
                print(f"[VIDEO-WORKER] Scene {idx + 1} VF filter: {ken_burns_filter[:200]}...")

                # 씬 클립 생성 (Ken Burns 효과 포함)
                clip_path = os.path.join(work_dir, f"clip_{idx:03d}.mp4")
                if audio_path and os.path.exists(audio_path):
                    cmd = [
                        "ffmpeg", "-y",
                        "-loop", "1",  # 이미지 루프
                        "-framerate", "24",  # 입력 프레임레이트 지정
                        "-i", img_path,
                        "-i", audio_path,
                        "-vf", ken_burns_filter,
                        "-c:v", "libx264", "-preset", "fast",
                        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                        "-pix_fmt", "yuv420p",
                        "-shortest", "-t", str(duration),
                        clip_path
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-y",
                        "-loop", "1",  # 이미지 루프
                        "-framerate", "24",  # 입력 프레임레이트 지정
                        "-i", img_path,
                        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-vf", ken_burns_filter,
                        "-c:v", "libx264", "-preset", "fast",
                        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                        "-pix_fmt", "yuv420p",
                        "-t", str(duration), "-shortest",
                        clip_path
                    ]

                # 디버깅: 실제 실행 명령어 출력
                print(f"[VIDEO-WORKER] FFmpeg cmd: {' '.join(cmd[:15])}...")

                # 메모리 최적화: stdout DEVNULL, stderr만 PIPE (OOM 방지)
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=600
                )
                if result.returncode == 0 and os.path.exists(clip_path):
                    scene_videos.append(clip_path)
                    print(f"[VIDEO-WORKER] Clip {idx+1} created successfully")
                    del result
                    gc.collect()
                else:
                    stderr = result.stderr.decode('utf-8', errors='ignore')[:1500] if result.stderr else 'no stderr'
                    print(f"[VIDEO-WORKER] Clip {idx+1} FAILED (code {result.returncode})")
                    print(f"[VIDEO-WORKER] FFmpeg stderr: {stderr}")
                    del result
                    gc.collect()

                    # Ken Burns 실패 시 단순 방식으로 재시도 (이미지 + 오디오만)
                    print(f"[VIDEO-WORKER] Clip {idx+1} 단순 방식으로 재시도...")
                    simple_filter = f"scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2"
                    if audio_path and os.path.exists(audio_path):
                        fallback_cmd = [
                            "ffmpeg", "-y",
                            "-loop", "1",
                            "-i", img_path,
                            "-i", audio_path,
                            "-vf", simple_filter,
                            "-c:v", "libx264", "-preset", "fast",
                            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                            "-pix_fmt", "yuv420p",
                            "-shortest", "-t", str(duration),
                            clip_path
                        ]
                    else:
                        fallback_cmd = [
                            "ffmpeg", "-y",
                            "-loop", "1",
                            "-i", img_path,
                            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                            "-vf", simple_filter,
                            "-c:v", "libx264", "-preset", "fast",
                            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                            "-pix_fmt", "yuv420p",
                            "-t", str(duration), "-shortest",
                            clip_path
                        ]

                    fallback_result = subprocess.run(
                        fallback_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        timeout=600
                    )
                    if fallback_result.returncode == 0 and os.path.exists(clip_path):
                        scene_videos.append(clip_path)
                        print(f"[VIDEO-WORKER] Clip {idx+1} 단순 방식 성공")
                    else:
                        fallback_stderr = fallback_result.stderr.decode('utf-8', errors='ignore')[:500] if fallback_result.stderr else ''
                        print(f"[VIDEO-WORKER] Clip {idx+1} 단순 방식도 실패: {fallback_stderr}")
                    del fallback_result
                    gc.collect()

            print(f"[VIDEO-WORKER] Total clips created: {len(scene_videos)} / {total_scenes}")

            if not scene_videos:
                raise Exception("영상 클립 생성 실패")

            # 2. 클립 병합 (전환 효과 옵션)
            _update_job_status(job_id, progress=75, message='클립 병합 중...')

            merged_path = os.path.join(work_dir, "merged.mp4")

            # 전환 효과 설정 확인
            transitions_config = video_effects.get('transitions', {})
            transition_style = transitions_config.get('style', 'none')  # 기본값: none (빠른 처리)
            transition_duration = transitions_config.get('duration', 0.5)

            if transition_style and transition_style != 'none' and len(scene_videos) > 1:
                # 전환 효과 적용
                print(f"[VIDEO-WORKER] 전환 효과 적용: {transition_style}, {transition_duration}초")
                _update_job_status(job_id, progress=76, message=f'전환 효과 적용 중 ({transition_style})...')

                if _apply_transitions(scene_videos, merged_path, transition_style, transition_duration):
                    print(f"[VIDEO-WORKER] 전환 효과 적용 완료")
                else:
                    # 전환 효과 실패 시 단순 concat으로 폴백
                    print(f"[VIDEO-WORKER] 전환 효과 실패, 단순 concat으로 폴백")
                    transition_style = 'none'

            if transition_style == 'none' or not os.path.exists(merged_path):
                # 전환 효과 없이 단순 concat
                concat_list = os.path.join(work_dir, "concat.txt")
                with open(concat_list, 'w') as f:
                    for clip in scene_videos:
                        # 절대 경로 사용
                        abs_clip = os.path.abspath(clip)
                        f.write(f"file '{abs_clip}'\n")

                print(f"[VIDEO-WORKER] Concat list created with {len(scene_videos)} clips")

                # 클립 파일 존재 확인
                for clip in scene_videos:
                    if os.path.exists(clip):
                        file_size = os.path.getsize(clip)
                        print(f"[VIDEO-WORKER] Clip exists: {clip} ({file_size} bytes)")
                    else:
                        print(f"[VIDEO-WORKER] Clip MISSING: {clip}")

                # IMPORTANT: stdout=DEVNULL, stderr=PIPE to avoid OOM from buffering all FFmpeg output
                concat_result = subprocess.run(
                    ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", merged_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=600
                )

                if concat_result.returncode != 0:
                    stderr = concat_result.stderr.decode('utf-8', errors='ignore') if concat_result.stderr else ""
                    print(f"[VIDEO-WORKER] Concat FAILED (code {concat_result.returncode}): {stderr[:500]}")
                    del concat_result
                    gc.collect()
                    raise Exception(f"클립 병합 실패: {stderr[:200]}")

                del concat_result
                gc.collect()

            if not os.path.exists(merged_path):
                raise Exception("merged.mp4 파일이 생성되지 않음")

            # 3. ASS 자막 생성 (색상 강조 지원)
            _update_job_status(job_id, progress=85, message='자막 처리 중...')

            # 자막 강조 키워드 가져오기
            subtitle_highlights = video_effects.get('subtitle_highlights', [])
            if subtitle_highlights:
                print(f"[VIDEO-WORKER] 자막 강조 키워드: {[h.get('keyword') for h in subtitle_highlights]}")
                print(f"[VIDEO-WORKER] 자막 강조 색상: {[h.get('color') for h in subtitle_highlights]}")
            else:
                print(f"[VIDEO-WORKER] ⚠️ 자막 강조 키워드 없음 - GPT가 subtitle_highlights를 생성하지 않음")

            # ASS 형식 사용 (색상 강조 지원)
            ass_path = os.path.join(work_dir, "subtitles.ass")
            _generate_ass_subtitles(all_subtitles, subtitle_highlights, ass_path, lang=detected_lang)

            # 4. 자막 burn-in + 화면 텍스트 오버레이
            _update_job_status(job_id, progress=90, message='자막 및 효과 삽입 중...')

            final_path = os.path.join(work_dir, "final.mp4")

            # 폰트 디렉토리 절대 경로 설정 (스크립트 위치 기준)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            fonts_dir = os.path.join(script_dir, "fonts")
            print(f"[VIDEO-WORKER] 폰트 디렉토리: {fonts_dir}, 존재: {os.path.exists(fonts_dir)}")

            # ASS 파일 절대 경로로 변환하고 FFmpeg용 이스케이프
            ass_abs_path = os.path.abspath(ass_path)
            # FFmpeg subtitle filter는 : \ ' 등을 이스케이프해야 함
            ass_escaped = ass_abs_path.replace('\\', '/').replace(':', '\\:')
            fonts_escaped = fonts_dir.replace('\\', '/').replace(':', '\\:')

            # 기본 자막 필터 (ASS 형식은 force_style 불필요 - 파일에 스타일 포함)
            vf_filter = f"ass={ass_escaped}:fontsdir={fonts_escaped}"

            # 화면 텍스트 오버레이 추가 (screen_overlays)
            screen_overlays = video_effects.get('screen_overlays', [])
            if screen_overlays:
                overlay_filter = _generate_screen_overlay_filter(screen_overlays, scenes, fonts_dir)
                if overlay_filter:
                    vf_filter = f"{vf_filter},{overlay_filter}"
                    print(f"[VIDEO-WORKER] 화면 오버레이 {len(screen_overlays)}개 추가")

            # 로워서드 오버레이 추가 (lower_thirds)
            lower_thirds = video_effects.get('lower_thirds', [])
            if lower_thirds:
                lt_filter = _generate_lower_thirds_filter(lower_thirds, scenes, fonts_dir)
                if lt_filter:
                    vf_filter = f"{vf_filter},{lt_filter}"
                    print(f"[VIDEO-WORKER] 로워서드 {len(lower_thirds)}개 추가")

            # 뉴스 티커 추가 (news_ticker)
            news_ticker = video_effects.get('news_ticker', {})
            if news_ticker and news_ticker.get('enabled'):
                ticker_filter = _generate_news_ticker_filter(news_ticker, current_time, fonts_dir)
                if ticker_filter:
                    vf_filter = f"{vf_filter},{ticker_filter}"
                    print(f"[VIDEO-WORKER] 뉴스 티커 추가 (헤드라인 {len(news_ticker.get('headlines', []))}개)")

            print(f"[VIDEO-WORKER] ASS path: {ass_abs_path}")
            print(f"[VIDEO-WORKER] VF filter 길이: {len(vf_filter)} chars")
            print(f"[VIDEO-WORKER] VF filter (처음 500자): {vf_filter[:500]}")
            print(f"[VIDEO-WORKER] Fonts directory: {fonts_dir}")

            # IMPORTANT: stdout=DEVNULL, stderr=PIPE to avoid OOM from buffering FFmpeg output
            # FFmpeg video encoding generates massive amounts of progress output to stderr
            # YouTube 호환 설정: -profile:v high -level 4.0, AAC 오디오, +faststart
            result = subprocess.run([
                "ffmpeg", "-y", "-i", merged_path,
                "-vf", vf_filter,
                "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.0",
                "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                "-movflags", "+faststart",
                final_path
            ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=1800)  # 30분 타임아웃

            if result.returncode != 0:
                # stderr 전체에서 실제 에러 메시지 추출 (FFmpeg는 마지막에 에러 출력)
                stderr_full = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ""
                # 마지막 800자 출력 (실제 에러 메시지 포함)
                stderr_tail = stderr_full[-800:] if len(stderr_full) > 800 else stderr_full
                print(f"[VIDEO-WORKER] Subtitle burn-in failed (code {result.returncode})")
                print(f"[VIDEO-WORKER] stderr (마지막 800자): {stderr_tail}")

                # 자막 burn-in 실패 시 자막 없이 YouTube 호환 인코딩 시도
                print(f"[VIDEO-WORKER] 자막 없이 YouTube 호환 재인코딩 시도...")
                fallback_result = subprocess.run([
                    "ffmpeg", "-y", "-i", merged_path,
                    "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.0",
                    "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                    "-movflags", "+faststart",
                    final_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=1800)

                if fallback_result.returncode != 0:
                    print(f"[VIDEO-WORKER] Fallback 인코딩도 실패, 원본 사용")
                    final_path = merged_path
                else:
                    print(f"[VIDEO-WORKER] Fallback 인코딩 성공 (자막 없음)")

            del result
            gc.collect()

            # 5. BGM 믹싱 (옵션)
            bgm_mood = video_effects.get('bgm_mood', '')
            if bgm_mood:
                _update_job_status(job_id, progress=95, message='BGM 믹싱 중...')
                bgm_file = _get_bgm_file(bgm_mood)
                if bgm_file:
                    bgm_output_path = os.path.join(work_dir, "with_bgm.mp4")
                    if _mix_bgm_with_video(final_path, bgm_file, bgm_output_path):
                        final_path = bgm_output_path
                        print(f"[VIDEO-WORKER] BGM 믹싱 완료: {bgm_mood}")
                    else:
                        print(f"[VIDEO-WORKER] BGM 믹싱 실패, BGM 없이 진행")
                else:
                    print(f"[VIDEO-WORKER] BGM 파일 없음: {bgm_mood}")

            # 6. 효과음 믹싱 (옵션)
            sound_effects = video_effects.get('sound_effects', [])
            if sound_effects:
                _update_job_status(job_id, progress=96, message='효과음 추가 중...')
                sfx_output_path = os.path.join(work_dir, "with_sfx.mp4")
                if _mix_sfx_into_video(final_path, sound_effects, scenes, sfx_output_path):
                    final_path = sfx_output_path
                    print(f"[VIDEO-WORKER] 효과음 {len(sound_effects)}개 추가 완료")
                else:
                    print(f"[VIDEO-WORKER] 효과음 믹싱 실패, 효과음 없이 진행")

            # 7. 아웃트로 추가 (옵션)
            add_outro = video_effects.get('add_outro', True)  # 기본값: 추가
            if add_outro:
                _update_job_status(job_id, progress=98, message='아웃트로 추가 중...')
                outro_path = os.path.join(work_dir, "outro.mp4")
                if _generate_outro_video(outro_path, duration=5, fonts_dir=fonts_dir):
                    outro_output_path = os.path.join(work_dir, "with_outro.mp4")
                    if _append_outro_to_video(final_path, outro_path, outro_output_path):
                        final_path = outro_output_path
                        print(f"[VIDEO-WORKER] 아웃트로 추가 완료")
                    else:
                        print(f"[VIDEO-WORKER] 아웃트로 연결 실패, 아웃트로 없이 진행")
                else:
                    print(f"[VIDEO-WORKER] 아웃트로 생성 실패")

            # 8. 결과 저장
            output_filename = f"video_{session_id}.mp4"
            output_path = os.path.join(upload_dir, output_filename)
            shutil.copy(final_path, output_path)

            # 작업 디렉토리 정리
            shutil.rmtree(work_dir, ignore_errors=True)

            minutes = int(current_time // 60)
            seconds = int(current_time % 60)

            _update_job_status(job_id,
                status='completed',
                progress=100,
                message='완료!',
                video_url=f"/uploads/{output_filename}",
                duration=f"{minutes}분 {seconds}초",
                subtitle_count=len(all_subtitles)
            )

            print(f"[VIDEO-WORKER] Completed: {output_path}")

        except Exception as e:
            shutil.rmtree(work_dir, ignore_errors=True)
            raise e

    except Exception as e:
        print(f"[VIDEO-WORKER] Error: {e}")
        import traceback
        traceback.print_exc()
        _update_job_status(job_id, status='failed', error=str(e), message=f'오류: {str(e)}')
    finally:
        # 세마포어 해제 (다음 FFmpeg 작업 허용)
        ffmpeg_semaphore.release()
        print(f"[VIDEO-WORKER] FFmpeg 세마포어 해제됨")


@app.route('/api/image/generate-video', methods=['POST'])
def api_image_generate_video():
    """영상 생성 시작 (백그라운드) - job_id 반환"""
    import threading
    import uuid as uuid_module
    from datetime import datetime

    data = request.get_json()
    session_id = data.get('session_id', str(uuid_module.uuid4())[:8])
    scenes = data.get('scenes', [])
    detected_lang = data.get('language', 'en')
    video_effects = data.get('video_effects', {})  # 새 기능: BGM, 효과음, 자막 강조, Ken Burns 등

    if not scenes:
        return jsonify({"ok": False, "error": "씬 데이터가 없습니다"}), 400

    total_duration = sum(s.get('duration', 0) for s in scenes)
    job_id = f"vj_{uuid_module.uuid4().hex[:12]}"

    # 작업 상태 초기화 (파일 기반)
    _save_job_status(job_id, {
        'status': 'queued',
        'progress': 0,
        'message': '대기 중...',
        'video_url': None,
        'error': None,
        'duration': None,
        'subtitle_count': 0,
        'created_at': datetime.now().isoformat(),
        'total_duration': total_duration
    })

    # 백그라운드 스레드 시작
    thread = threading.Thread(
        target=_generate_video_worker,
        args=(job_id, session_id, scenes, detected_lang, video_effects),
        daemon=True
    )
    thread.start()

    print(f"[IMAGE-VIDEO] Job started: {job_id}, {len(scenes)} scenes, {total_duration:.1f}s")

    return jsonify({
        "ok": True,
        "job_id": job_id,
        "message": "영상 생성이 시작되었습니다. 상태를 확인해주세요.",
        "estimated_time": f"{int(total_duration // 60)}분 {int(total_duration % 60)}초 예상"
    })


@app.route('/api/image/video-status/<job_id>', methods=['GET'])
def api_image_video_status(job_id):
    """영상 생성 작업 상태 확인 (파일 기반)"""
    job = _load_job_status(job_id)
    if not job:
        return jsonify({"ok": False, "error": "작업을 찾을 수 없습니다"}), 404

    return jsonify({
        "ok": True,
        "job_id": job_id,
        "status": job.get('status', 'unknown'),
        "progress": job.get('progress', 0),
        "message": job.get('message', ''),
        "video_url": job.get('video_url'),
        "duration": job.get('duration'),
        "subtitle_count": job.get('subtitle_count', 0),
        "error": job.get('error')
    })


# ===== 쿠팡파트너스 쇼츠 API =====

@app.route('/shorts')
def shorts_page():
    """쿠팡파트너스 쇼츠 제작 페이지"""
    return render_template('shorts.html')


@app.route('/api/shorts/fetch-coupang', methods=['POST'])
def api_fetch_coupang():
    """쿠팡 상품 URL에서 상품 정보 추출"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()

        if not url or 'coupang.com' not in url:
            return jsonify({'ok': False, 'error': '올바른 쿠팡 URL이 아닙니다.'}), 400

        print(f"[SHORTS] 쿠팡 상품 정보 추출: {url}")

        # 쿠팡 페이지 크롤링
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')

        # 상품명 추출
        name = ''
        name_el = soup.select_one('h2.prod-buy-header__title') or soup.select_one('.prod-buy-header__title') or soup.select_one('h1')
        if name_el:
            name = name_el.get_text(strip=True)

        # 가격 추출
        price = ''
        price_el = soup.select_one('.total-price strong') or soup.select_one('.prod-sale-price .total-price') or soup.select_one('.prod-price')
        if price_el:
            price = price_el.get_text(strip=True)

        # 이미지 추출
        images = []
        # 메인 이미지
        main_img = soup.select_one('.prod-image__detail img') or soup.select_one('.prod-image img') or soup.select_one('#repImageContainer img')
        if main_img:
            src = main_img.get('src') or main_img.get('data-src')
            if src:
                if src.startswith('//'):
                    src = 'https:' + src
                images.append(src)

        # 추가 이미지
        thumb_imgs = soup.select('.prod-image__items img') or soup.select('.prod-image__item img') or soup.select('.subType-IMAGE img')
        for img in thumb_imgs[:10]:
            src = img.get('src') or img.get('data-src')
            if src:
                if src.startswith('//'):
                    src = 'https:' + src
                # 작은 썸네일은 큰 이미지로 변환
                src = src.replace('_230x230', '_500x500').replace('_100x100', '_500x500')
                if src not in images:
                    images.append(src)

        # 평점 추출
        rating = '0.0'
        rating_el = soup.select_one('.rating-star-num') or soup.select_one('.prod-rating__number')
        if rating_el:
            rating_text = rating_el.get_text(strip=True)
            try:
                rating = str(float(rating_text))
            except:
                pass

        # 리뷰 수 추출
        review_count = 0
        review_el = soup.select_one('.count') or soup.select_one('.prod-review__count')
        if review_el:
            review_text = review_el.get_text(strip=True)
            numbers = re.findall(r'\d+', review_text.replace(',', ''))
            if numbers:
                review_count = int(numbers[0])

        product = {
            'name': name or '상품명을 가져올 수 없습니다',
            'price': price or '가격 정보 없음',
            'images': images[:10],
            'rating': rating,
            'reviewCount': review_count,
            'url': url
        }

        print(f"[SHORTS] 상품 정보 추출 완료: {name[:30]}..., 이미지 {len(images)}개")

        return jsonify({'ok': True, 'product': product})

    except requests.RequestException as e:
        print(f"[SHORTS] 쿠팡 요청 오류: {e}")
        return jsonify({'ok': False, 'error': f'쿠팡 페이지를 가져올 수 없습니다: {str(e)}'}), 500
    except Exception as e:
        print(f"[SHORTS] 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/shorts/generate-script', methods=['POST'])
def api_generate_shorts_script():
    """상품 정보 기반 쇼츠 대본 자동 생성 (Hook 라이브러리 연동)"""
    try:
        import random

        data = request.get_json()
        product_name = data.get('productName', '')
        price = data.get('price', '')
        rating = data.get('rating', '')
        review_count = data.get('reviewCount', 0)

        # 새로운 옵션들
        hook_style = data.get('hookStyle', 'random')  # 훅 스타일
        category = data.get('category', 'auto')  # 카테고리
        length_preset = data.get('lengthPreset', 'medium')  # 길이 프리셋

        if not product_name:
            return jsonify({'ok': False, 'error': '상품명이 필요합니다.'}), 400

        print(f"[SHORTS] 대본 생성: {product_name[:30]}...")
        print(f"[SHORTS] 옵션 - 훅스타일: {hook_style}, 카테고리: {category}, 길이: {length_preset}")

        # Hook 라이브러리 로드
        hook_library_path = os.path.join(os.path.dirname(__file__), 'guides', 'shorts-hook-library.json')
        try:
            with open(hook_library_path, 'r', encoding='utf-8') as f:
                hook_library = json.load(f)
        except:
            hook_library = None
            print("[SHORTS] Hook 라이브러리 로드 실패, 기본 모드로 진행")

        # 훅 예시 선택
        hook_examples = []
        if hook_library:
            hooks_data = hook_library.get('hooks', {})

            if hook_style == 'random':
                # 랜덤으로 여러 스타일에서 선택
                all_hooks = []
                for style_data in hooks_data.values():
                    all_hooks.extend(style_data.get('templates', [])[:3])
                hook_examples = random.sample(all_hooks, min(5, len(all_hooks)))
            elif hook_style in hooks_data:
                hook_examples = hooks_data[hook_style].get('templates', [])[:5]

            # 카테고리 Pain/Solution 예시
            category_data = hook_library.get('categories', {}).get(category, {})
            category_pains = category_data.get('pains', [])[:3]
            category_solutions = category_data.get('solutions', [])[:3]

            # CTA 예시
            cta_examples = []
            for cta_list in hook_library.get('cta', {}).values():
                cta_examples.extend(cta_list[:2])

            # 길이 프리셋
            length_info = hook_library.get('length_presets', {}).get(length_preset, {})
            total_seconds = length_info.get('total_seconds', 38)
        else:
            hook_examples = ["이 가격에 이 스펙?", "솔직히 이건 사야 됩니다"]
            category_pains = []
            category_solutions = []
            cta_examples = ["링크는 프로필에서 확인하세요"]
            total_seconds = 38

        # 가격 정보 처리
        price_text = price.replace('원', '').replace(',', '') if price else ''

        system_prompt = f"""당신은 쿠팡파트너스 쇼츠 콘텐츠 전문 카피라이터입니다.
{total_seconds}초 이내의 상품 리뷰 쇼츠 대본을 작성합니다.

## 핵심 원칙
1. **첫 2-3초가 80%**: Hook에 모든 것을 걸어라
2. **짧고 끊어치는 문장**: 쉼표 대신 줄바꿈
3. **3개 이상 말하지 마라**: 특징은 딱 3가지만

## 대본 구성
1. **Hook (2-3초)**: 스크롤 멈추게 하는 첫 문장
   예시: {', '.join(hook_examples[:3]) if hook_examples else '이 가격 실화?'}

2. **Pain → Solution (10-25초)**: 문제 공감 → 해결책 제시
   {f'Pain 예시: {category_pains[0] if category_pains else "매일 이런 문제 겪으셨죠?"}' }
   {f'Solution 예시: {category_solutions[0] if category_solutions else "이 제품이 해결합니다"}' }

3. **Key Features (10-20초)**: 핵심 특징 딱 3개만
   형식: "첫째, OO. 둘째, OO. 셋째, OO."

4. **CTA (3-5초)**: 클릭 유도
   예시: {cta_examples[0] if cta_examples else '아래 링크에서 확인하세요'}

## 문장 스타일
- 길게 쓰지 마라. 끊어라.
- "이 제품은 가격 대비 성능이 좋습니다" (X)
- "가격? 미쳤다. 성능? 더 미쳤다." (O)

## 출력 형식 (JSON)
{{
  "hook": "훅 문장 (최대 30자)",
  "pain": "문제 공감 문장",
  "solution": "해결책 문장",
  "features": ["특징1", "특징2", "특징3"],
  "cta": "CTA 문장",
  "disclosure": "쿠팡파트너스 고지 문구"
}}

⚠️ 반드시 JSON 형식으로만 출력하세요."""

        user_prompt = f"""다음 상품에 대한 쇼츠 대본을 작성해주세요:

상품명: {product_name}
가격: {price}
평점: {rating}
리뷰 수: {review_count}개
영상 길이: {total_seconds}초

{f'선호 훅 스타일: {hooks_data.get(hook_style, {}).get("name", "랜덤")}' if hook_library and hook_style != 'random' else ''}
{f'카테고리: {category_data.get("name", "일반")}' if category_data else ''}

위 정보를 바탕으로 쇼츠 대본을 작성해주세요.
문장은 짧고 끊어서. 쉼표 대신 마침표.
특징은 반드시 3개만."""

        # 3개 대본 변형 생성 옵션
        generate_variations = data.get('variations', False)
        variation_count = 3 if generate_variations else 1

        scripts = []
        variation_styles = ['price_shock', 'pain_trigger', 'shock_surprise'] if generate_variations else [hook_style]

        for i in range(variation_count):
            # 각 변형별로 다른 Hook 스타일 사용
            current_style = variation_styles[i] if i < len(variation_styles) else 'random'

            # Hook 예시 업데이트
            if hook_library and current_style != 'random':
                style_hooks = hooks_data.get(current_style, {}).get('templates', [])[:5]
                hook_hint = f"\n\n이번 대본의 훅 스타일: {hooks_data.get(current_style, {}).get('name', current_style)}\n예시: {', '.join(style_hooks[:3])}"
            else:
                hook_hint = ""

            var_user_prompt = user_prompt + hook_hint
            if generate_variations:
                var_user_prompt += f"\n\n[버전 {i+1}] 다른 버전과 차별화된 독특한 훅과 접근 방식으로 작성해주세요."

            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": var_user_prompt}
                ],
                temperature=0.9 + (i * 0.05),  # 변형별로 다른 temperature
                max_tokens=700,
                response_format={"type": "json_object"}
            )

            result_text = completion.choices[0].message.content
            script = json.loads(result_text)

            # 호환성을 위해 content 필드도 생성
            if 'content' not in script:
                parts = []
                if script.get('pain'):
                    parts.append(script['pain'])
                if script.get('solution'):
                    parts.append(script['solution'])
                if script.get('features'):
                    features = script['features']
                    if isinstance(features, list):
                        parts.append(f"첫째, {features[0]}." if len(features) > 0 else '')
                        parts.append(f"둘째, {features[1]}." if len(features) > 1 else '')
                        parts.append(f"셋째, {features[2]}." if len(features) > 2 else '')
                script['content'] = ' '.join(filter(None, parts))

            # 버전 정보 추가
            script['version'] = i + 1
            script['style'] = current_style

            scripts.append(script)
            print(f"[SHORTS] 대본 {i+1} 생성 완료: 훅={script.get('hook', '')[:20]}...")

        # 단일/다중 응답 처리
        if generate_variations:
            return jsonify({'ok': True, 'scripts': scripts, 'count': len(scripts)})
        else:
            return jsonify({'ok': True, 'script': scripts[0]})

    except Exception as e:
        print(f"[SHORTS] 대본 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/shorts/generate-tts', methods=['POST'])
def api_generate_shorts_tts():
    """쇼츠용 TTS 음성 생성"""
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        voice = data.get('voice', 'ko-KR-Neural2-C')
        speed = float(data.get('speed', 1.2))

        if not text:
            return jsonify({'ok': False, 'error': '텍스트가 필요합니다.'}), 400

        print(f"[SHORTS-TTS] 음성 생성: {len(text)}자, 속도: {speed}x")

        from google.cloud import texttospeech

        tts_client = texttospeech.TextToSpeechClient()

        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice_params = texttospeech.VoiceSelectionParams(
            language_code="ko-KR",
            name=voice
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speed,
            pitch=0.0
        )

        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config
        )

        # 오디오 파일 저장
        audio_dir = 'static/audio/shorts'
        os.makedirs(audio_dir, exist_ok=True)
        audio_filename = f'shorts_tts_{uuid.uuid4().hex[:8]}.mp3'
        audio_path = os.path.join(audio_dir, audio_filename)

        with open(audio_path, 'wb') as f:
            f.write(response.audio_content)

        audio_url = f'/{audio_path}'
        print(f"[SHORTS-TTS] 저장 완료: {audio_path}")

        return jsonify({'ok': True, 'audioUrl': audio_url})

    except Exception as e:
        print(f"[SHORTS-TTS] 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/shorts/generate-video', methods=['POST'])
def api_generate_shorts_video():
    """쇼츠 영상 생성 (이미지 슬라이드쇼 + TTS)"""
    try:
        data = request.get_json()
        images = data.get('images', [])
        audio_url = data.get('audioUrl', '')
        effect = data.get('effect', 'kenburns')
        image_duration = int(data.get('imageDuration', 4))

        if not images:
            return jsonify({'ok': False, 'error': '이미지가 필요합니다.'}), 400

        if not audio_url:
            return jsonify({'ok': False, 'error': '오디오가 필요합니다.'}), 400

        print(f"[SHORTS-VIDEO] 영상 생성: 이미지 {len(images)}개, 효과: {effect}")

        from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip
        from PIL import Image
        import io

        # 오디오 파일 경로
        audio_path = audio_url.lstrip('/')

        if not os.path.exists(audio_path):
            return jsonify({'ok': False, 'error': '오디오 파일을 찾을 수 없습니다.'}), 400

        # 오디오 길이 확인
        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration

        # 이미지당 시간 계산 (오디오 길이에 맞춤)
        actual_image_duration = audio_duration / len(images) if len(images) > 0 else image_duration

        # 세로 영상 크기 (9:16)
        VIDEO_WIDTH = 1080
        VIDEO_HEIGHT = 1920

        clips = []

        for idx, img_url in enumerate(images):
            try:
                print(f"[SHORTS-VIDEO] 이미지 {idx+1}/{len(images)} 처리 중...")

                # 이미지 다운로드
                headers = {'User-Agent': 'Mozilla/5.0'}
                img_response = requests.get(img_url, headers=headers, timeout=15)
                img_response.raise_for_status()

                # PIL로 이미지 열기
                img = Image.open(io.BytesIO(img_response.content))
                img = img.convert('RGB')

                # 세로 비율에 맞게 리사이즈 (중앙 크롭)
                img_ratio = img.width / img.height
                target_ratio = VIDEO_WIDTH / VIDEO_HEIGHT

                if img_ratio > target_ratio:
                    # 이미지가 더 넓음 -> 좌우 크롭
                    new_width = int(img.height * target_ratio)
                    left = (img.width - new_width) // 2
                    img = img.crop((left, 0, left + new_width, img.height))
                else:
                    # 이미지가 더 높음 -> 상하 크롭
                    new_height = int(img.width / target_ratio)
                    top = (img.height - new_height) // 2
                    img = img.crop((0, top, img.width, top + new_height))

                img = img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.Resampling.LANCZOS)

                # numpy 배열로 변환
                import numpy as np
                img_array = np.array(img)

                # ImageClip 생성
                clip = ImageClip(img_array).set_duration(actual_image_duration)

                # Ken Burns 효과 (줌인)
                if effect == 'kenburns':
                    def zoom_effect(get_frame, t):
                        frame = get_frame(t)
                        zoom = 1 + 0.1 * (t / actual_image_duration)  # 1.0 -> 1.1 줌
                        h, w = frame.shape[:2]
                        new_h, new_w = int(h * zoom), int(w * zoom)

                        # 리사이즈
                        from PIL import Image as PILImage
                        pil_img = PILImage.fromarray(frame)
                        pil_img = pil_img.resize((new_w, new_h), PILImage.Resampling.LANCZOS)

                        # 중앙 크롭
                        left = (new_w - w) // 2
                        top = (new_h - h) // 2
                        pil_img = pil_img.crop((left, top, left + w, top + h))

                        return np.array(pil_img)

                    clip = clip.fl(zoom_effect)

                clips.append(clip)

            except Exception as e:
                print(f"[SHORTS-VIDEO] 이미지 {idx+1} 처리 오류: {e}")
                continue

        if not clips:
            return jsonify({'ok': False, 'error': '처리 가능한 이미지가 없습니다.'}), 500

        # 클립 연결
        final_clip = concatenate_videoclips(clips, method="compose")

        # 오디오 추가
        final_clip = final_clip.set_audio(audio_clip)

        # 영상 저장
        video_dir = 'static/video/shorts'
        os.makedirs(video_dir, exist_ok=True)
        video_filename = f'shorts_{uuid.uuid4().hex[:8]}.mp4'
        video_path = os.path.join(video_dir, video_filename)

        final_clip.write_videofile(
            video_path,
            fps=30,
            codec='libx264',
            audio_codec='aac',
            threads=4,
            preset='fast',
            verbose=False,
            logger=None
        )

        # 리소스 정리
        final_clip.close()
        audio_clip.close()

        video_url = f'/{video_path}'
        print(f"[SHORTS-VIDEO] 영상 생성 완료: {video_path}")

        return jsonify({'ok': True, 'videoUrl': video_url})

    except Exception as e:
        print(f"[SHORTS-VIDEO] 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


# ===== 상세페이지 제작 API =====

@app.route('/detail-page')
def detail_page():
    """상세페이지 제작 페이지"""
    return render_template('detail-page.html')


@app.route('/api/detail-page/generate-copy', methods=['POST'])
def generate_detail_copy():
    """상세페이지 카피 생성 API"""
    try:
        data = request.json
        product_name = data.get('productName', '')
        category = data.get('category', '생활용품')
        target_audience = data.get('targetAudience', '전체')
        features = data.get('features', '')
        price_point = data.get('pricePoint', '')
        page_style = data.get('pageStyle', 'modern')
        sections = data.get('sections', ['hero', 'features', 'cta'])

        print(f"[DETAIL-COPY] 상품명: {product_name}, 카테고리: {category}")
        print(f"[DETAIL-COPY] 섹션: {sections}")

        # 스타일별 톤 설정
        style_tones = {
            'modern': '깔끔하고 세련된 톤. 짧고 임팩트 있는 문장 사용.',
            'premium': '고급스럽고 신뢰감 있는 톤. 품격있는 표현 사용.',
            'cute': '친근하고 귀여운 톤. 이모티콘과 재미있는 표현 사용.',
            'professional': '전문적이고 객관적인 톤. 데이터와 근거 중심.'
        }

        # 섹션별 프롬프트 가이드
        section_guides = {
            'hero': '메인 헤드라인과 서브 헤드라인. 한 줄로 제품의 핵심 가치 전달.',
            'problem': '타겟 고객이 공감할 수 있는 문제점 3-4가지 나열.',
            'solution': '이 제품이 문제를 어떻게 해결하는지 설명.',
            'features': '제품의 주요 특징 3-4가지를 각각 제목+설명 형태로.',
            'usage': '사용 방법을 단계별로 간단히 설명.',
            'review': '가상의 고객 후기 2-3개 작성. 실감나게.',
            'spec': '제품 스펙/사양 정리. 표 형태 텍스트.',
            'cta': '구매를 유도하는 마무리 문구. 긴박감 또는 혜택 강조.'
        }

        # 선택된 섹션만 포함
        selected_guides = {k: v for k, v in section_guides.items() if k in sections}

        system_prompt = f"""당신은 쿠팡, 스마트스토어 등 이커머스 상세페이지 전문 카피라이터입니다.
{style_tones.get(page_style, style_tones['modern'])}

타겟 고객: {target_audience}
가격대: {price_point if price_point else '미정'}

각 섹션별로 판매력 있는 카피를 작성해주세요.
응답은 반드시 JSON 형식으로, 각 섹션을 key로 하여 작성해주세요."""

        user_prompt = f"""상품명: {product_name}
카테고리: {category}
핵심 특징: {features if features else '(자유롭게 추론)'}

다음 섹션들의 카피를 작성해주세요:
{chr(10).join([f'- {k}: {v}' for k, v in selected_guides.items()])}

JSON 형식으로 응답해주세요. 예시:
{{"hero": "헤드라인 텍스트", "features": "특징1\\n특징2\\n...", ...}}"""

        # OpenAI API 호출
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.8
        )

        copy_text = response.choices[0].message.content
        copy_data = json.loads(copy_text)

        print(f"[DETAIL-COPY] 카피 생성 완료: {list(copy_data.keys())}")

        return jsonify({'ok': True, 'copy': copy_data})

    except Exception as e:
        print(f"[DETAIL-COPY] 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/detail-page/generate-images', methods=['POST'])
def generate_detail_images():
    """상세페이지 이미지 생성 API"""
    try:
        data = request.json
        product_name = data.get('productName', '')
        category = data.get('category', '생활용품')
        page_style = data.get('pageStyle', 'modern')
        sections = data.get('sections', ['hero'])
        copy_data = data.get('copy', {})

        print(f"[DETAIL-IMAGE] 상품명: {product_name}, 섹션 수: {len(sections)}")

        # 스타일별 이미지 스타일
        style_visuals = {
            'modern': 'minimalist, clean white background, modern design, professional product photography',
            'premium': 'luxury, elegant, dark background with gold accents, premium feel',
            'cute': 'pastel colors, playful, kawaii style, soft lighting',
            'professional': 'corporate style, clean lines, trustworthy, infographic style'
        }

        visual_style = style_visuals.get(page_style, style_visuals['modern'])

        # 섹션별 이미지 프롬프트 생성
        section_prompts = {
            'hero': f'Hero banner for {product_name}, {category} product, {visual_style}, eye-catching main visual, no text',
            'problem': f'Problem illustration, frustrated person concept, {visual_style}, emotional visual',
            'solution': f'Solution concept, happy person with {product_name}, {visual_style}, positive mood',
            'features': f'Product features showcase, {product_name} details, {visual_style}, multiple angle view',
            'usage': f'Product usage demonstration, step by step visual, {product_name}, {visual_style}',
            'review': f'Happy customer testimonial concept, satisfied person, {visual_style}',
            'spec': f'Product specification infographic style, {product_name}, {visual_style}, clean layout',
            'cta': f'Call to action banner, {product_name}, {visual_style}, promotional feel, urgent mood'
        }

        generated_images = []

        # Gemini로 이미지 생성
        for section in sections:
            if section not in section_prompts:
                continue

            prompt = section_prompts[section]
            print(f"[DETAIL-IMAGE] {section} 이미지 생성 중...")

            try:
                # Gemini imagen 사용
                imagen = genai.ImageGenerationModel("imagen-3.0-generate-002")
                result = imagen.generate_images(
                    prompt=prompt,
                    number_of_images=1,
                    aspect_ratio="1:1",
                    safety_filter_level="block_only_high",
                    person_generation="allow_adult"
                )

                if result.images:
                    # 이미지 저장
                    timestamp = int(time.time() * 1000)
                    filename = f"detail_{section}_{timestamp}.png"
                    filepath = os.path.join(OUTPUT_DIR, filename)

                    result.images[0].save(filepath)
                    image_url = f'/output/{filename}'

                    generated_images.append({
                        'section': section,
                        'url': image_url,
                        'prompt': prompt
                    })
                    print(f"[DETAIL-IMAGE] {section} 완료: {image_url}")

            except Exception as img_error:
                print(f"[DETAIL-IMAGE] {section} 이미지 생성 실패: {img_error}")
                # 실패한 섹션은 건너뛰기
                continue

        if not generated_images:
            return jsonify({'ok': False, 'error': '이미지 생성에 실패했습니다'}), 500

        return jsonify({'ok': True, 'images': generated_images})

    except Exception as e:
        print(f"[DETAIL-IMAGE] 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/detail-page/download-zip', methods=['POST'])
def download_detail_zip():
    """상세페이지 전체 다운로드 (ZIP)"""
    try:
        data = request.json
        images = data.get('images', [])
        copy_data = data.get('copy', {})

        print(f"[DETAIL-ZIP] 이미지 {len(images)}개, 카피 섹션 {len(copy_data)}개")

        # ZIP 파일 생성
        timestamp = int(time.time())
        zip_filename = f"detail_page_{timestamp}.zip"
        zip_path = os.path.join(OUTPUT_DIR, zip_filename)

        import zipfile

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 이미지 파일 추가
            for img in images:
                img_url = img.get('url', '')
                section = img.get('section', 'unknown')

                if img_url.startswith('/output/'):
                    local_path = os.path.join(OUTPUT_DIR, img_url.replace('/output/', ''))
                    if os.path.exists(local_path):
                        zf.write(local_path, f'images/{section}.png')

            # 카피 텍스트 파일 추가
            section_names = {
                'hero': '01_히어로배너',
                'problem': '02_문제제기',
                'solution': '03_해결책',
                'features': '04_주요특징',
                'usage': '05_사용방법',
                'review': '06_후기리뷰',
                'spec': '07_제품스펙',
                'cta': '08_CTA'
            }

            copy_text = ""
            for key, content in copy_data.items():
                if content:
                    title = section_names.get(key, key)
                    copy_text += f"=== {title} ===\n{content}\n\n"

            zf.writestr('copy.txt', copy_text.encode('utf-8'))

        # ZIP 파일 반환
        return send_file(
            zip_path,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename
        )

    except Exception as e:
        print(f"[DETAIL-ZIP] 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


# ===== 썸네일 자동 생성 API =====

@app.route('/thumbnail')
def thumbnail_page():
    """썸네일 자동 생성 페이지"""
    return render_template('thumbnail.html')


@app.route('/thumbnail-ai')
def thumbnail_ai_page():
    """AI 썸네일 생성 페이지 (GPT-5.1 + Gemini 3 Pro)"""
    return render_template('thumbnail-ai.html')


@app.route('/api/thumbnail/generate', methods=['POST'])
def generate_thumbnail_with_text():
    """썸네일 생성 API"""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        import requests
        from io import BytesIO
        import base64

        data = request.json
        image_src = data.get('image', '')
        main_text = data.get('mainText', '')
        price = data.get('price', '')
        original_price = data.get('originalPrice')
        tags = data.get('tags', [])
        template = data.get('template', 'sale')
        font_style = data.get('font', 'noto-black')
        bg_style = data.get('bgStyle', 'blur')
        bg_color = data.get('bgColor', '#1a1a2e')

        print(f"[THUMBNAIL] 템플릿: {template}, 배경: {bg_style}")
        print(f"[THUMBNAIL] 텍스트: {main_text}, 가격: {price}")

        # 이미지 로드
        if image_src.startswith('data:'):
            # Base64 이미지
            base64_data = image_src.split(',')[1]
            img_data = base64.b64decode(base64_data)
            product_img = Image.open(BytesIO(img_data))
        elif image_src.startswith('http'):
            # URL 이미지
            response = requests.get(image_src, timeout=10)
            product_img = Image.open(BytesIO(response.content))
        else:
            return jsonify({'ok': False, 'error': '유효하지 않은 이미지'}), 400

        # RGBA로 변환
        product_img = product_img.convert('RGBA')

        # 썸네일 크기 (9:16)
        WIDTH, HEIGHT = 1080, 1920

        # 템플릿별 색상 설정
        template_colors = {
            'sale': {'primary': '#ff416c', 'secondary': '#ff4b2b', 'accent': '#ffffff'},
            'value': {'primary': '#11998e', 'secondary': '#38ef7d', 'accent': '#ffffff'},
            'must': {'primary': '#667eea', 'secondary': '#764ba2', 'accent': '#ffffff'},
            'gift': {'primary': '#f093fb', 'secondary': '#f5576c', 'accent': '#ffffff'},
            'hot': {'primary': '#eb3349', 'secondary': '#f45c43', 'accent': '#ffff00'},
            'minimal': {'primary': '#2c3e50', 'secondary': '#4ca1af', 'accent': '#ffffff'}
        }
        colors = template_colors.get(template, template_colors['sale'])

        # 배경 생성
        if bg_style == 'blur':
            # 상품 이미지를 확대하고 블러 처리
            bg_img = product_img.copy()
            bg_img = bg_img.resize((WIDTH + 100, HEIGHT + 100), Image.Resampling.LANCZOS)
            bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=30))
            # 중앙 크롭
            left = (bg_img.width - WIDTH) // 2
            top = (bg_img.height - HEIGHT) // 2
            bg_img = bg_img.crop((left, top, left + WIDTH, top + HEIGHT))
            # 어둡게 처리
            dark_overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 150))
            bg_img = Image.alpha_composite(bg_img.convert('RGBA'), dark_overlay)
        elif bg_style == 'gradient':
            # 그라데이션 배경
            bg_img = Image.new('RGBA', (WIDTH, HEIGHT))
            draw = ImageDraw.Draw(bg_img)
            c1 = tuple(int(colors['primary'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            c2 = tuple(int(colors['secondary'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            for y in range(HEIGHT):
                r = int(c1[0] + (c2[0] - c1[0]) * y / HEIGHT)
                g = int(c1[1] + (c2[1] - c1[1]) * y / HEIGHT)
                b = int(c1[2] + (c2[2] - c1[2]) * y / HEIGHT)
                draw.line([(0, y), (WIDTH, y)], fill=(r, g, b, 255))
        else:
            # 단색 배경
            c = tuple(int(bg_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            bg_img = Image.new('RGBA', (WIDTH, HEIGHT), c + (255,))

        # 상품 이미지 배치 (중앙)
        product_size = int(WIDTH * 0.85)
        product_img_resized = product_img.copy()
        product_img_resized.thumbnail((product_size, product_size), Image.Resampling.LANCZOS)

        # 상품 이미지 위치 (상단 여백 25%, 하단 여백 20% 고려)
        img_x = (WIDTH - product_img_resized.width) // 2
        img_y = int(HEIGHT * 0.28)

        # 상품 이미지 합성
        bg_img.paste(product_img_resized, (img_x, img_y), product_img_resized)

        # 폰트 로드 (프로젝트 로컬 Pretendard 우선)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        font_candidates = [
            os.path.join(base_dir, "fonts/Pretendard-Bold.ttf"),
            os.path.join(base_dir, "fonts/Pretendard-SemiBold.ttf"),
            os.path.join(base_dir, "fonts/NanumGothicBold.ttf"),
            '/usr/share/fonts/truetype/noto/NotoSansCJK-Black.ttc',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        ]

        font_path = None
        for fp in font_candidates:
            if os.path.exists(fp):
                font_path = fp
                break

        # 폰트 로드
        try:
            font_large = ImageFont.truetype(font_path, 72)
            font_medium = ImageFont.truetype(font_path, 56)
            font_small = ImageFont.truetype(font_path, 40)
            font_tag = ImageFont.truetype(font_path, 36)
        except:
            font_large = ImageFont.load_default()
            font_medium = font_large
            font_small = font_large
            font_tag = font_large

        draw = ImageDraw.Draw(bg_img)

        # 상단 태그 영역 (상단 5~15%)
        tag_y = int(HEIGHT * 0.06)
        if tags:
            tag_x_start = WIDTH // 2
            tag_spacing = 20
            total_width = 0

            # 태그 총 너비 계산
            tag_widths = []
            for tag in tags[:3]:
                if tag:
                    bbox = draw.textbbox((0, 0), tag, font=font_tag)
                    w = bbox[2] - bbox[0] + 40  # 패딩 포함
                    tag_widths.append(w)
                    total_width += w + tag_spacing

            # 중앙 정렬을 위한 시작 위치
            tag_x = (WIDTH - total_width) // 2

            for i, tag in enumerate(tags[:3]):
                if tag:
                    bbox = draw.textbbox((0, 0), tag, font=font_tag)
                    w = bbox[2] - bbox[0] + 40
                    h = bbox[3] - bbox[1] + 20

                    # 태그 배경 (둥근 사각형 효과)
                    c = tuple(int(colors['primary'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
                    draw.rounded_rectangle(
                        [tag_x, tag_y, tag_x + w, tag_y + h],
                        radius=h // 2,
                        fill=c + (230,)
                    )
                    # 태그 텍스트
                    text_x = tag_x + 20
                    text_y = tag_y + 10
                    draw.text((text_x, text_y), tag, font=font_tag, fill='white')

                    tag_x += w + tag_spacing

        # 하단 텍스트 영역 (하단 20%)
        bottom_y = int(HEIGHT * 0.78)

        # 메인 텍스트 (상품명)
        if main_text:
            # 텍스트 그림자
            shadow_offset = 3
            bbox = draw.textbbox((0, 0), main_text, font=font_large)
            text_w = bbox[2] - bbox[0]
            text_x = (WIDTH - text_w) // 2

            draw.text((text_x + shadow_offset, bottom_y + shadow_offset), main_text, font=font_large, fill=(0, 0, 0, 150))
            draw.text((text_x, bottom_y), main_text, font=font_large, fill='white')

        # 가격
        price_y = bottom_y + 90
        if price:
            # 원가 (취소선 효과)
            if original_price:
                bbox = draw.textbbox((0, 0), original_price, font=font_small)
                orig_w = bbox[2] - bbox[0]
                orig_x = (WIDTH - orig_w) // 2
                draw.text((orig_x, price_y), original_price, font=font_small, fill=(200, 200, 200, 200))
                # 취소선
                line_y = price_y + (bbox[3] - bbox[1]) // 2
                draw.line([(orig_x - 5, line_y), (orig_x + orig_w + 5, line_y)], fill=(200, 200, 200, 200), width=3)
                price_y += 50

            # 현재 가격
            bbox = draw.textbbox((0, 0), price, font=font_medium)
            price_w = bbox[2] - bbox[0]
            price_x = (WIDTH - price_w) // 2

            # 가격 강조 배경
            padding = 20
            c = tuple(int(colors['primary'].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            draw.rounded_rectangle(
                [price_x - padding, price_y - 10, price_x + price_w + padding, price_y + (bbox[3] - bbox[1]) + 10],
                radius=10,
                fill=c + (255,)
            )
            draw.text((price_x, price_y), price, font=font_medium, fill='white')

        # 이미지 저장
        timestamp = int(time.time() * 1000)
        filename = f"thumbnail_{template}_{timestamp}.png"
        filepath = os.path.join(OUTPUT_DIR, filename)

        # RGB로 변환하여 저장
        final_img = bg_img.convert('RGB')
        final_img.save(filepath, 'PNG', quality=95)

        thumbnail_url = f'/output/{filename}'
        print(f"[THUMBNAIL] 생성 완료: {thumbnail_url}")

        return jsonify({'ok': True, 'thumbnailUrl': thumbnail_url})

    except Exception as e:
        print(f"[THUMBNAIL] 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


# ===== 시니어 썸네일 문장 자동 생성 API =====
SENIOR_THUMBNAIL_SYSTEM_PROMPT = """You are an assistant that generates short, highly clickable Korean YouTube thumbnail texts
for a senior (50–70+) audience watching emotional drama and 회상/간증 스타일 videos.

[RULES]

1. Output only Korean text for thumbnail titles.
2. Each line must be:
   - 5~12 Korean characters
   - Easy to read
   - Emotionally evocative (memory, regret, gratitude, realization, first time, etc.)
3. Target viewers:
   - Korean seniors (50–70+)
   - They respond to: 기억, 후회, 깨달음, 첫 경험, 가족, 부모, 첫사랑, 병원, 삶의 전환점
4. Avoid:
   - Internet slang, 영어, 광고 느낌 단어 (구독, 클릭, 유튜브 등)
   - Abstract or vague words only (must hint at a concrete situation or feeling)
5. Style examples:
   - 그날을 잊지 않는다
   - 처음엔 몰랐다
   - 늦게 알았다
   - 엄마의 마지막 부탁
   - 왜 그랬을까
   - 다시 만난 그 자리
   - 하는 게 아니었다
   - 다 겪어봤다
   - 누구나 그런 날 있다

[INPUT]
You will receive a JSON with:
- scene_summary: short description of the drama scene
- tone: target emotional tone (e.g. "회상", "후회", "감사")
- max_length: maximum character length for one line
- num_candidates: how many lines to generate
- keywords: optional list of words to reflect
- ban_words: optional list of words to never use

[OUTPUT]
Return ONLY a JSON object:

{
  "candidates": [
    {"text": "...", "emotion": "...", "intensity": 0.0},
    ...
  ]
}

Where:
- text: the thumbnail phrase (Korean only, within max_length)
- emotion: guessed emotional tag like "회상", "후회", "감사", "그리움", "깨달음", "긴장", "기적", "이별", "재회"
- intensity: 0.0–1.0 indicating how strong the emotion feels.
"""

@app.route('/api/thumbnail/senior-titles', methods=['POST'])
def api_thumbnail_senior_titles():
    """시니어용 썸네일 문장 자동 생성 API"""
    try:
        from openai import OpenAI
        client = OpenAI()

        data = request.get_json() or {}

        scene_summary = data.get("scene_summary", "")
        tone = data.get("tone", "회상")
        max_length = data.get("max_length", 12)
        num_candidates = data.get("num_candidates", 10)
        keywords = data.get("keywords", [])
        ban_words = data.get("ban_words", [])
        language = data.get("language", "ko")

        # 최소 입력 체크
        if not scene_summary:
            return jsonify({"ok": False, "error": "scene_summary is required"}), 400

        user_payload = {
            "scene_summary": scene_summary,
            "tone": tone,
            "max_length": max_length,
            "num_candidates": num_candidates,
            "keywords": keywords,
            "ban_words": ban_words,
            "language": language,
        }

        print(f"[THUMBNAIL] 시니어 썸네일 문장 생성 요청 - tone: {tone}, candidates: {num_candidates}")

        # GPT 호출
        completion = client.chat.completions.create(
            model="gpt-4o-mini",  # 빠르고 저렴한 모델 사용
            messages=[
                {"role": "system", "content": SENIOR_THUMBNAIL_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
            ],
            temperature=0.8,  # 다양성을 위해 약간 높게
            response_format={"type": "json_object"}
        )

        result = completion.choices[0].message.content
        result_json = json.loads(result)

        # 글자 수 계산 추가
        candidates = result_json.get("candidates", [])
        for c in candidates:
            c["length"] = len(c.get("text", ""))

        print(f"[THUMBNAIL] 생성 완료 - {len(candidates)}개 후보")

        return jsonify({
            "ok": True,
            "scene_summary": scene_summary,
            "tone": tone,
            "candidates": candidates
        })

    except Exception as e:
        print(f"[THUMBNAIL][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== 통합 썸네일 디자인 자동 생성 API (스타일 포함) =====
THUMBNAIL_STYLE_PRESETS = {
    "nostalgia": {
        "name": "시니어 감성",
        "description": "세피아, 추억, 따뜻한 회상 느낌",
        "audience": "senior",
        "colors": {
            "background": "#F7EFE5",
            "text": "#373431",
            "accent": "#D19C66",
            "outline": "#2B2B2B"
        },
        "font": {
            "family": "NanumSquareB",
            "weight": "700",
            "size": "72px",
            "letter_spacing": "2px"
        },
        "layout": {
            "position": "left-top",
            "padding": "32px",
            "text_box": True,
            "text_box_opacity": 0.7
        },
        "image_style": "warm sepia tone, soft focus, nostalgic film grain, 1970s Korean aesthetic"
    },
    "clinic_warm": {
        "name": "따뜻한 병원",
        "description": "청결하면서도 따뜻한 의료 컨셉",
        "audience": "senior",
        "colors": {
            "background": "#E8F4F8",
            "text": "#1A365D",
            "accent": "#4299E1",
            "outline": "#FFFFFF"
        },
        "font": {
            "family": "NanumBarunGothicBold",
            "weight": "700",
            "size": "68px",
            "letter_spacing": "1px"
        },
        "layout": {
            "position": "top-center",
            "padding": "28px",
            "text_box": True,
            "text_box_opacity": 0.85
        },
        "image_style": "clean Korean clinic interior, soft natural light, warm atmosphere, modern medical setting"
    },
    "dramatic_conflict": {
        "name": "강렬한 갈등",
        "description": "어두운 배경 + 강렬한 노란 강조",
        "audience": "senior",
        "colors": {
            "background": "#1A1A1A",
            "text": "#FFD700",
            "accent": "#FF4444",
            "outline": "#000000"
        },
        "font": {
            "family": "NanumSquareB",
            "weight": "900",
            "size": "80px",
            "letter_spacing": "0px"
        },
        "layout": {
            "position": "center",
            "padding": "24px",
            "text_box": False,
            "text_box_opacity": 0
        },
        "image_style": "dark moody atmosphere, dramatic lighting, high contrast shadows, intense emotional moment"
    },
    "family_tearjerker": {
        "name": "가족 감동",
        "description": "파스텔톤, 가족/부모 테마",
        "audience": "senior",
        "colors": {
            "background": "#FFF5F5",
            "text": "#4A3728",
            "accent": "#E57373",
            "outline": "#FFFFFF"
        },
        "font": {
            "family": "NanumMyeongjoBold",
            "weight": "700",
            "size": "64px",
            "letter_spacing": "3px"
        },
        "layout": {
            "position": "center",
            "padding": "36px",
            "text_box": True,
            "text_box_opacity": 0.6
        },
        "image_style": "soft pastel colors, gentle lighting, family moments, warm emotional scene, Korean home setting"
    },
    "calm_documentary": {
        "name": "차분한 다큐",
        "description": "실제 사진 그대로, 담백한 톤",
        "audience": "senior",
        "colors": {
            "background": "#F5F5F5",
            "text": "#2D3748",
            "accent": "#3182CE",
            "outline": "#FFFFFF"
        },
        "font": {
            "family": "NanumBarunGothic",
            "weight": "600",
            "size": "60px",
            "letter_spacing": "1px"
        },
        "layout": {
            "position": "bottom-left",
            "padding": "24px",
            "text_box": True,
            "text_box_opacity": 0.9
        },
        "image_style": "realistic photography, natural colors, documentary style, authentic Korean setting"
    },
    "newspaper_retro": {
        "name": "신문 레트로",
        "description": "흑백 헤드라인 스타일",
        "audience": "senior",
        "colors": {
            "background": "#FFFEF0",
            "text": "#1A1A1A",
            "accent": "#8B0000",
            "outline": "#000000"
        },
        "font": {
            "family": "NanumMyeongjoBold",
            "weight": "900",
            "size": "76px",
            "letter_spacing": "4px"
        },
        "layout": {
            "position": "top-center",
            "padding": "20px",
            "text_box": False,
            "text_box_opacity": 0
        },
        "image_style": "black and white photo, newspaper grain texture, vintage print style, bold headline aesthetic"
    },
    # ===== 일반용 스타일 (General Audience) =====
    "breaking_news": {
        "name": "속보/긴급",
        "description": "붉은 배경, 속보/드디어/방금",
        "audience": "general",
        "colors": {
            "background": "#8B0000",
            "text": "#FFFFFF",
            "accent": "#FFD700",
            "outline": "#000000"
        },
        "font": {
            "family": "NanumSquareB",
            "weight": "900",
            "size": "84px",
            "letter_spacing": "0px"
        },
        "layout": {
            "position": "center",
            "padding": "20px",
            "text_box": False,
            "text_box_opacity": 0
        },
        "image_style": "high contrast dramatic lighting, dark silhouette, red warning atmosphere, news broadcast style, empty space for text, YouTube thumbnail composition, no text, 16:9"
    },
    "crime": {
        "name": "사건/범죄",
        "description": "어두운 인물 실루엣, 강한 대비",
        "audience": "general",
        "colors": {
            "background": "#131313",
            "text": "#FFFFFF",
            "accent": "#E60000",
            "outline": "#000000"
        },
        "font": {
            "family": "NanumSquareB",
            "weight": "900",
            "size": "80px",
            "letter_spacing": "0px"
        },
        "layout": {
            "position": "center",
            "padding": "24px",
            "text_box": True,
            "text_box_opacity": 0.5
        },
        "image_style": "high contrast dark background, silhouette of unknown person, red warning light, dramatic shadow, cinematic noir style, empty space for bold text, YouTube thumbnail composition, no text, 16:9"
    },
    "tech": {
        "name": "테크/설명",
        "description": "파란색 계열, 방법/해결/최적",
        "audience": "general",
        "colors": {
            "background": "#0A1628",
            "text": "#FFFFFF",
            "accent": "#00D4FF",
            "outline": "#000000"
        },
        "font": {
            "family": "NanumBarunGothicBold",
            "weight": "700",
            "size": "72px",
            "letter_spacing": "1px"
        },
        "layout": {
            "position": "left-center",
            "padding": "28px",
            "text_box": False,
            "text_box_opacity": 0
        },
        "image_style": "clean tech aesthetic, blue gradient background, modern digital style, futuristic lighting, sharp details, empty space for text, YouTube thumbnail composition, no text, 16:9"
    },
    "money": {
        "name": "경제/재테크",
        "description": "숫자 강조, 기회/수익",
        "audience": "general",
        "colors": {
            "background": "#1A1A2E",
            "text": "#00FF88",
            "accent": "#FFD700",
            "outline": "#000000"
        },
        "font": {
            "family": "NanumSquareB",
            "weight": "900",
            "size": "80px",
            "letter_spacing": "0px"
        },
        "layout": {
            "position": "center",
            "padding": "24px",
            "text_box": False,
            "text_box_opacity": 0
        },
        "image_style": "financial chart background, money growth concept, green and gold colors, stock market aesthetic, clean composition, empty space for text, YouTube thumbnail style, no text, 16:9"
    },
    "vlog": {
        "name": "브이로그/일상",
        "description": "밝은 실제 사진, 진짜/처음/해봤다",
        "audience": "general",
        "colors": {
            "background": "#FFFFFF",
            "text": "#1A1A1A",
            "accent": "#FF6B6B",
            "outline": "#FFFFFF"
        },
        "font": {
            "family": "NanumSquareRoundB",
            "weight": "700",
            "size": "68px",
            "letter_spacing": "1px"
        },
        "layout": {
            "position": "bottom-center",
            "padding": "24px",
            "text_box": True,
            "text_box_opacity": 0.8
        },
        "image_style": "bright natural lighting, lifestyle photography, warm friendly atmosphere, authentic moment, clean background, empty space for text, YouTube thumbnail style, no text, 16:9"
    },
    "dramatic": {
        "name": "드라마/감정폭발",
        "description": "얼굴 클로즈업, 왜/몰랐다/그날",
        "audience": "general",
        "colors": {
            "background": "#0D0D0D",
            "text": "#FFFFFF",
            "accent": "#FF4444",
            "outline": "#000000"
        },
        "font": {
            "family": "NanumSquareB",
            "weight": "900",
            "size": "88px",
            "letter_spacing": "-2px"
        },
        "layout": {
            "position": "center",
            "padding": "20px",
            "text_box": False,
            "text_box_opacity": 0
        },
        "image_style": "extreme close-up face, intense emotion, dramatic side lighting, high contrast shadows, cinematic portrait, dark background, empty space for text, YouTube thumbnail style, no text, 16:9"
    }
}

THUMBNAIL_DESIGN_SYSTEM_PROMPT = """You are an AI system that generates fully structured YouTube thumbnail design data
based on a single scene description.
You must follow the "Thumbnail JSON Schema v1".

Your output must ALWAYS be a valid JSON that matches the "result" structure.
Do not include explanations, plain text, or markdown — ONLY output JSON.

====================
PRIMARY OBJECTIVE
====================

Given a scene summary and metadata (audience type, channel type, style preference),
generate:

1) Thumbnail short text candidates (for Korean thumbnails)
2) Emotion and intensity classification
3) Style selection (auto if needed)
4) Typography recommendation (font, weight, size hint)
5) Layout suggestion (alignment, position, padding)
6) Color palette suggestion (HEX codes)
7) Image-generation prompt (for AI tools like ImageFX, DALL-E, Midjourney)
8) Optional "notes" to guide background-only image creation

====================
AUDIENCE RULES
====================

If "audience": "senior":

- Text length: 8–12 Korean characters
- Use emotions: 회상, 후회, 그리움, 감사, 깨달음, 기다림
- Avoid clickbait, avoid slang, avoid excessive punctuation
- Preferred tones: nostalgia, calm, warm, old photo, clinic, family
- Friendly and reflective titles
- Recommended style keys:
  - "nostalgia"
  - "clinic_warm"
  - "family_tearjerker"
  - "calm_documentary"
  - "dramatic_conflict"
  - "newspaper_retro"
- Colors: low contrast, pastel, film, vintage tones

If "audience": "general":

- Text length: 4–7 Korean characters
- Use emotions: 긴장, 궁금, 분노, 위기, 충격
- Clickbait allowed (but stay concise, clear, not abusive)
- Preferred tones: dramatic, breaking_news, crime, tech, money
- Recommended style keys:
  - "breaking_news"
  - "crime"
  - "tech"
  - "money"
  - "vlog"
  - "dramatic"
- Colors: high contrast, red/yellow/black/white dominant

====================
TEXT GENERATION RULES
====================

- ONLY Korean text for "text" field
- Character count must not exceed "max_length"
- Avoid banned words included in "ban_words"
- At least one candidate must focus on a clear emotional center
- Do not generate English mixed headlines
- NEVER include "유튜브", "클릭", "구독" words

====================
IMAGE PROMPT RULES
====================

Image-generation prompts must:

- NOT contain text
- NOT contain watermark
- MUST describe background only (no title text rendered inside image)
- MUST include clear space ("negative space") for text placement
- ALWAYS include cinematic composition instruction
- Format: 16:9, no characters unless silhouette is needed

Senior image prompt guidance:
- "soft light", "vintage photo", "nostalgic Korean street",
- "film texture", "pastel tones", "calm spring morning",
- "empty clinic entrance", "falling cherry blossoms"

General image prompt guidance:
- "high contrast dramatic lighting", "dark background",
- "silhouette", "red warning light", "empty urban alley",
- "strong color accent", "center composition", "sharp clarity"

====================
STYLE AUTO-SELECTION RULES
====================

If "style": "auto",
choose style from the "recommended style keys" based on:

- scene_summary keywords
- audience type
- channel_type

Examples:
- scene contains "first day, 진료소, 병원" → "clinic_warm"
- scene contains "사건, 피해, 증거, 진실" → "crime"
- scene contains "기억, 편지, 마지막" → "nostalgia"
- scene contains "돈, 투자, 수익" → "money"
- scene contains "기술, 방법, 해결" → "tech"
- scene contains "가족, 부모, 엄마, 아빠" → "family_tearjerker"

====================
REQUIRED OUTPUT FORMAT (JSON only)
====================

The final output MUST be a JSON object shaped as:

{
  "scene_summary": "...",
  "audience": "...",
  "channel_type": "...",
  "style_auto_selected": "...",
  "candidates": [
    {
      "id": "thumb_001",
      "text": "...",
      "length": 7,
      "audience": "...",
      "emotion": "...",
      "intensity": 0.7,
      "style_profile": {
        "style_key": "...",
        "tone": "...",
        "category": "..."
      },
      "design": {
        "layout": {
          "position": "bottom-left",
          "text_box": true,
          "padding": 32,
          "max_lines": 2,
          "alignment": "left"
        },
        "colors": {
          "background": "#F2E7D5",
          "text": "#2B2B2B",
          "accent": "#A67C52",
          "suggested_palette": [
            "#F2E7D5",
            "#2B2B2B",
            "#A67C52",
            "#FFFFFF"
          ]
        },
        "font": {
          "family": "Noto Sans KR",
          "weight": "900",
          "size_hint": "72px",
          "line_spacing": 1.1
        }
      },
      "image_prompt": {
        "prompt": "...(AI image-generation prompt)...",
        "notes": "Background only for thumbnail. No text."
      }
    }
  ]
}

====================
VALIDATION RULES
====================

- ALWAYS return at least 3 candidates
- NEVER leave any field empty
- HEX codes must be valid (#RRGGBB)
- "size_hint" must contain "px"
- intensity value must be between 0.0 and 1.0

====================
OUTPUT LANGUAGE
====================

- Korean for "text"
- English for "image_prompt"

====================
FAIL CASE INSTRUCTIONS
====================

If the request lacks "scene_summary", reply with:

{
  "error": "scene_summary is required"
}

NO free text, NO apology.

====================
END OF SYSTEM PROMPT
====================
"""

@app.route('/api/thumbnail/generate', methods=['POST'])
def api_thumbnail_generate():
    """통합 썸네일 디자인 자동 생성 API v1 (스타일 + 디자인 + 이미지 프롬프트 포함)"""
    try:
        from openai import OpenAI
        client = OpenAI()

        data = request.get_json() or {}

        # v1 스키마 파라미터
        scene_summary = data.get("scene_summary", "")
        audience = data.get("audience", "senior")  # senior / general
        channel_type = data.get("channel_type", "drama")  # drama / issue / vlog / sermon / news
        style = data.get("style", "auto")  # auto = AI가 자동 선택
        num_candidates = data.get("num_candidates", 10)
        max_length = data.get("max_length", 12 if audience == "senior" else 7)
        language = data.get("language", "ko")
        keywords = data.get("keywords", [])
        ban_words = data.get("ban_words", ["구독", "유튜브", "클릭"])
        options = data.get("options", {
            "generate_layout": True,
            "generate_palette": True,
            "generate_image_prompt": True
        })

        if not scene_summary:
            return jsonify({"ok": False, "error": "scene_summary is required"}), 400

        # audience에 맞는 스타일만 필터링
        available_styles = [
            key for key, preset in THUMBNAIL_STYLE_PRESETS.items()
            if preset.get("audience") == audience
        ]

        # 기본 스타일 (audience에 맞게)
        default_style = "nostalgia" if audience == "senior" else "breaking_news"

        user_payload = {
            "scene_summary": scene_summary,
            "audience": audience,
            "channel_type": channel_type,
            "style": style,
            "available_styles": available_styles,
            "num_candidates": num_candidates,
            "max_length": max_length,
            "language": language,
            "keywords": keywords,
            "ban_words": ban_words,
            "options": options
        }

        print(f"[THUMBNAIL-DESIGN-V1] 통합 썸네일 생성 요청")
        print(f"  - audience: {audience}, channel_type: {channel_type}, style: {style}")
        print(f"  - available_styles: {available_styles}")

        # GPT 호출
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": THUMBNAIL_DESIGN_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
            ],
            temperature=0.8,
            response_format={"type": "json_object"}
        )

        result = completion.choices[0].message.content
        result_json = json.loads(result)

        # 에러 체크
        if "error" in result_json:
            return jsonify({"ok": False, "error": result_json["error"]}), 400

        # 추천된 스타일 가져오기
        style_auto_selected = result_json.get("style_auto_selected", default_style)
        if style != "auto" and style in THUMBNAIL_STYLE_PRESETS:
            style_auto_selected = style  # 사용자가 직접 지정한 경우

        # 스타일이 audience에 맞는지 확인
        if style_auto_selected not in available_styles:
            style_auto_selected = default_style

        style_preset = THUMBNAIL_STYLE_PRESETS.get(style_auto_selected, THUMBNAIL_STYLE_PRESETS[default_style])

        # 각 후보에 디자인 정보 보강 (GPT 출력에 없는 경우 프리셋으로 대체)
        candidates = result_json.get("candidates", [])
        for i, c in enumerate(candidates):
            c["id"] = c.get("id", f"thumb_{str(i+1).zfill(3)}")
            c["length"] = len(c.get("text", ""))
            c["audience"] = audience

            # design 보강
            if "design" not in c or not c["design"]:
                c["design"] = {
                    "layout": style_preset["layout"],
                    "colors": style_preset["colors"],
                    "font": style_preset["font"]
                }
            else:
                # 부분적으로 누락된 경우 보강
                if "layout" not in c["design"]:
                    c["design"]["layout"] = style_preset["layout"]
                if "colors" not in c["design"]:
                    c["design"]["colors"] = style_preset["colors"]
                if "font" not in c["design"]:
                    c["design"]["font"] = style_preset["font"]

            # image_prompt 보강
            if "image_prompt" not in c or not c["image_prompt"]:
                c["image_prompt"] = {
                    "prompt": style_preset["image_style"] + ", YouTube thumbnail composition, no text, 16:9",
                    "notes": "Background only for thumbnail. No text."
                }

        print(f"[THUMBNAIL-DESIGN-V1] 생성 완료 - style: {style_auto_selected}, {len(candidates)}개 후보")

        # v1 스키마 응답
        return jsonify({
            "ok": True,
            "version": "1.0",
            "scene_summary": scene_summary,
            "audience": audience,
            "channel_type": channel_type,
            "style_auto_selected": style_auto_selected,
            "style_preset": {
                "key": style_auto_selected,
                "name": style_preset["name"],
                "description": style_preset["description"],
                "colors": style_preset["colors"],
                "font": style_preset["font"],
                "layout": style_preset["layout"],
                "image_style": style_preset["image_style"]
            },
            "candidates": candidates
        })

    except Exception as e:
        print(f"[THUMBNAIL-DESIGN-V1][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/thumbnail/styles', methods=['GET'])
def api_thumbnail_styles():
    """사용 가능한 썸네일 스타일 목록 조회 (audience 필터 지원)"""
    audience_filter = request.args.get("audience")  # senior / general / None(전체)

    styles = []
    for key, preset in THUMBNAIL_STYLE_PRESETS.items():
        preset_audience = preset.get("audience", "senior")

        # audience 필터 적용
        if audience_filter and preset_audience != audience_filter:
            continue

        styles.append({
            "key": key,
            "name": preset["name"],
            "description": preset["description"],
            "audience": preset_audience,
            "colors": preset["colors"],
            "font": preset["font"],
            "layout": preset["layout"]
        })

    return jsonify({
        "ok": True,
        "audience_filter": audience_filter,
        "total": len(styles),
        "styles": styles
    })


# ===== 썸네일 AI 시스템 (GPT-5.1 + Gemini 3 Pro Image) =====
THUMBNAIL_AI_HISTORY_FILE = 'data/thumbnail_ai_history.json'


def load_thumbnail_history():
    """썸네일 학습 데이터 로드"""
    try:
        if os.path.exists(THUMBNAIL_AI_HISTORY_FILE):
            with open(THUMBNAIL_AI_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[THUMBNAIL-AI] 히스토리 로드 오류: {e}")
    return {"selections": []}


def save_thumbnail_history(data):
    """썸네일 학습 데이터 저장"""
    try:
        os.makedirs(os.path.dirname(THUMBNAIL_AI_HISTORY_FILE), exist_ok=True)
        with open(THUMBNAIL_AI_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[THUMBNAIL-AI] 히스토리 저장 오류: {e}")
        return False


def get_learning_examples(limit=5):
    """학습용 예시 데이터 가져오기 (최근 선택 데이터 기반)"""
    history = load_thumbnail_history()
    selections = history.get("selections", [])

    # 최근 선택 데이터 중 limit개 가져오기
    recent = selections[-limit:] if len(selections) > limit else selections

    examples = []
    for sel in recent:
        selected_key = sel.get("selected")  # "A" or "B"
        if selected_key and sel.get("prompts", {}).get(selected_key):
            examples.append({
                "genre": sel.get("genre", "일반"),
                "script_summary": sel.get("script_summary", "")[:100],
                "selected_prompt": sel["prompts"][selected_key],
                "reason": sel.get("selection_reason", "")
            })

    return examples


@app.route('/api/thumbnail-ai/analyze', methods=['POST'])
def api_thumbnail_ai_analyze():
    """
    GPT-5.1이 대본을 분석하여 썸네일 프롬프트 2개 생성
    학습 데이터를 Few-shot으로 활용
    """
    try:
        from openai import OpenAI
        client = OpenAI()

        data = request.get_json() or {}
        script = data.get('script', '')
        title = data.get('title', '')
        genre = data.get('genre', '일반')

        if not script:
            return jsonify({"ok": False, "error": "대본이 필요합니다"}), 400

        print(f"[THUMBNAIL-AI] 분석 요청 - 제목: {title}, 장르: {genre}")
        print(f"[THUMBNAIL-AI] 대본 길이: {len(script)}자")

        # 학습 데이터 가져오기
        learning_examples = get_learning_examples(5)

        # Few-shot 예시 텍스트 생성
        examples_text = ""
        if learning_examples:
            examples_text = "\n\n[과거 사용자가 선호한 썸네일 스타일 예시]\n"
            for i, ex in enumerate(learning_examples, 1):
                examples_text += f"""
예시 {i}:
- 장르: {ex['genre']}
- 대본 요약: {ex['script_summary']}
- 선택된 프롬프트: {ex['selected_prompt']}
- 선택 이유: {ex['reason'] or '없음'}
"""

        system_prompt = f"""당신은 유튜브 썸네일 전문 디자이너입니다.
사용자의 대본을 분석하여 클릭률이 높은 썸네일 이미지 프롬프트 3개를 생성합니다.
(YouTube Test & Compare 기능용 - 3개 썸네일 A/B/C 테스트)

[핵심 원칙]
1. 유튜브 썸네일은 "호기심"과 "감정"을 자극해야 합니다
2. 텍스트는 한글로, 크고 굵게, 읽기 쉽게
3. 대비가 강한 색상 사용 (빨강/노랑/흰색 등)
4. 얼굴 표정이나 감정적인 요소 포함
5. "Before vs After" 또는 "Split Screen" 구도가 효과적

[이미지 프롬프트 작성 규칙]
- 영문으로 작성 (Gemini 3 Pro Image가 이해할 수 있도록)
- 16:9 가로 비율 (YouTube 썸네일 표준)
- 한글 텍스트 오버레이 지시 포함
- 구체적인 색상, 스타일, 구도 명시
- 만화/일러스트 스타일 권장 (저작권 안전)
{examples_text}

[3개 썸네일 차별화 전략]
- A: 감정/표정 중심 (놀람, 충격, 기쁨 등)
- B: 스토리/상황 중심 (Before vs After, 대비 구도)
- C: 텍스트/타이포 중심 (강렬한 문구, 숫자 강조)

[응답 형식]
반드시 다음 JSON 형식으로만 응답하세요:
{{
  "script_summary": "대본 핵심 요약 (1-2문장)",
  "thumbnail_concept": "썸네일 컨셉 설명",
  "prompts": {{
    "A": {{
      "description": "프롬프트 A 설명 (한글)",
      "prompt": "영문 이미지 생성 프롬프트",
      "text_overlay": {{
        "main": "메인 텍스트 (한글)",
        "sub": "서브 텍스트 (한글, 선택)"
      }},
      "style": "스타일 키워드"
    }},
    "B": {{
      "description": "프롬프트 B 설명 (한글)",
      "prompt": "영문 이미지 생성 프롬프트",
      "text_overlay": {{
        "main": "메인 텍스트 (한글)",
        "sub": "서브 텍스트 (한글, 선택)"
      }},
      "style": "스타일 키워드"
    }},
    "C": {{
      "description": "프롬프트 C 설명 (한글)",
      "prompt": "영문 이미지 생성 프롬프트",
      "text_overlay": {{
        "main": "메인 텍스트 (한글)",
        "sub": "서브 텍스트 (한글, 선택)"
      }},
      "style": "스타일 키워드"
    }}
  }}
}}"""

        user_prompt = f"""[제목] {title}
[장르] {genre}

[대본]
{script[:3000]}

위 대본을 분석하여 클릭률 높은 유튜브 썸네일 프롬프트 3개(A/B/C)를 생성해주세요.
YouTube Test & Compare용이므로 세 프롬프트는 서로 확실히 다른 스타일/구도여야 합니다."""

        # GPT-5.1 Responses API 호출
        response = client.responses.create(
            model="gpt-5.1",
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}]
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}]
                }
            ],
            temperature=0.8
        )

        # 결과 추출
        result_text = ""
        if getattr(response, "output_text", None):
            result_text = response.output_text.strip()
        else:
            text_chunks = []
            for item in getattr(response, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    if getattr(content, "type", "") == "text":
                        text_chunks.append(getattr(content, "text", ""))
            result_text = "\n".join(text_chunks).strip()

        # JSON 파싱 (마크다운 코드블록 제거)
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()

        try:
            result = json.loads(result_text)
        except json.JSONDecodeError as je:
            print(f"[THUMBNAIL-AI] JSON 파싱 오류: {je}")
            print(f"[THUMBNAIL-AI] 원본 텍스트: {result_text[:500]}")
            return jsonify({"ok": False, "error": f"AI 응답 파싱 오류: {str(je)}"}), 200

        # 세션 ID 생성
        session_id = f"thumb_{uuid.uuid4().hex[:12]}"

        print(f"[THUMBNAIL-AI] 분석 완료 - 세션: {session_id}")

        return jsonify({
            "ok": True,
            "session_id": session_id,
            "script_summary": result.get("script_summary", ""),
            "thumbnail_concept": result.get("thumbnail_concept", ""),
            "prompts": result.get("prompts", {}),
            "genre": genre,
            "title": title,
            "learning_examples_used": len(learning_examples)
        })

    except Exception as e:
        print(f"[THUMBNAIL-AI][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/thumbnail-ai/generate', methods=['POST'])
def api_thumbnail_ai_generate():
    """
    Gemini 3 Pro Image로 썸네일 이미지 생성
    한글 텍스트 렌더링 지원
    """
    try:
        import requests as req
        import time
        import base64

        data = request.get_json() or {}
        prompt = data.get('prompt', '')
        text_overlay = data.get('text_overlay', {})
        style = data.get('style', 'comic')
        session_id = data.get('session_id', '')
        variant = data.get('variant', 'A')  # A or B

        if not prompt:
            return jsonify({"ok": False, "error": "프롬프트가 필요합니다"}), 400

        print(f"[THUMBNAIL-AI] 이미지 생성 - 세션: {session_id}, 변형: {variant}")

        # OpenRouter API 키
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not openrouter_api_key:
            return jsonify({"ok": False, "error": "OpenRouter API 키가 설정되지 않았습니다"}), 200

        # 텍스트 오버레이 지시 추가
        main_text = text_overlay.get('main', '')
        sub_text = text_overlay.get('sub', '')

        text_instruction = ""
        if main_text:
            text_instruction = f"""
IMPORTANT TEXT OVERLAY INSTRUCTIONS:
- Add large, bold Korean text "{main_text}" prominently in the image
- Text should be highly visible with strong contrast (white text with black outline or vice versa)
- Text position: center or top area of the image
"""
            if sub_text:
                text_instruction += f'- Add smaller subtitle "{sub_text}" below the main text\n'

        # 최종 프롬프트 구성
        enhanced_prompt = f"""Create a YouTube thumbnail image in 16:9 landscape aspect ratio.

{prompt}

{text_instruction}

Style requirements:
- High contrast, eye-catching colors
- Professional YouTube thumbnail quality
- Comic/illustration style (not photorealistic)
- Clean composition suitable for small preview
- {style} aesthetic"""

        # OpenRouter API 호출 (Gemini 3 Pro Image Preview)
        headers = {
            "Authorization": f"Bearer {openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://drama-generator.app",
            "X-Title": "Thumbnail AI Generator"
        }

        payload = {
            "model": "google/gemini-3-pro-image-preview",
            "modalities": ["text", "image"],
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": enhanced_prompt}]
                }
            ]
        }

        # 재시도 로직
        max_retries = 3
        retry_delay = 5
        response = None
        last_error = None

        for attempt in range(max_retries):
            try:
                response = req.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120
                )

                if response.status_code == 200:
                    break
                elif response.status_code in [429, 502, 503, 504]:
                    last_error = response.text
                    print(f"[THUMBNAIL-AI][RETRY] 서버 오류 ({response.status_code}), {retry_delay}초 후 재시도...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    break

            except req.exceptions.Timeout:
                last_error = "요청 시간 초과"
                print(f"[THUMBNAIL-AI][RETRY] 타임아웃 (시도 {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                continue
            except Exception as e:
                last_error = str(e)
                time.sleep(retry_delay)
                continue

        if response is None or response.status_code != 200:
            error_text = last_error or (response.text if response else "알 수 없는 오류")
            print(f"[THUMBNAIL-AI][ERROR] API 최종 실패: {error_text}")
            return jsonify({"ok": False, "error": f"이미지 생성 실패: {error_text[:200]}"}), 200

        result = response.json()

        # 디버그: 전체 응답 구조 출력
        print(f"[THUMBNAIL-AI][DEBUG] OpenRouter 응답 키: {list(result.keys())}")
        if result.get("choices"):
            msg = result["choices"][0].get("message", {})
            print(f"[THUMBNAIL-AI][DEBUG] message 키: {list(msg.keys())}")
            content = msg.get("content")
            if isinstance(content, list):
                for i, item in enumerate(content):
                    if isinstance(item, dict):
                        print(f"[THUMBNAIL-AI][DEBUG] content[{i}] 타입: {item.get('type')}, 키: {list(item.keys())}")
                    else:
                        print(f"[THUMBNAIL-AI][DEBUG] content[{i}]: {type(item).__name__}")
            elif content:
                print(f"[THUMBNAIL-AI][DEBUG] content 타입: {type(content).__name__}, 길이: {len(str(content)[:100])}")

        # 이미지 추출
        image_url = None
        base64_image_data = None

        choices = result.get("choices", [])
        if choices:
            message = choices[0].get("message", {})

            # images 배열 확인
            images = message.get("images", [])
            if images:
                for img in images:
                    if isinstance(img, str):
                        if img.startswith("data:"):
                            base64_image_data = img.split(",", 1)[1] if "," in img else img
                        else:
                            base64_image_data = img
                        break

            # content 배열 확인 (다양한 형식 지원)
            if not base64_image_data:
                content = message.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            item_type = item.get("type", "")

                            # 형식 1: image_url
                            if item_type == "image_url":
                                img_data = item.get("image_url", {})
                                url = img_data.get("url", "")
                                if url.startswith("data:"):
                                    base64_image_data = url.split(",", 1)[1]
                                    print(f"[THUMBNAIL-AI][DEBUG] image_url 형식에서 이미지 추출")
                                    break

                            # 형식 2: inline_data (Gemini 네이티브)
                            if item_type == "image" or "inline_data" in item:
                                inline = item.get("inline_data") or item.get("image", {})
                                if isinstance(inline, dict):
                                    data = inline.get("data") or inline.get("b64_json") or inline.get("base64")
                                    if data:
                                        base64_image_data = data
                                        print(f"[THUMBNAIL-AI][DEBUG] inline_data 형식에서 이미지 추출")
                                        break

                            # 형식 3: b64_json 직접
                            if "b64_json" in item:
                                base64_image_data = item["b64_json"]
                                print(f"[THUMBNAIL-AI][DEBUG] b64_json 형식에서 이미지 추출")
                                break

                            # 형식 4: data 직접
                            if "data" in item and item.get("type") != "text":
                                base64_image_data = item["data"]
                                print(f"[THUMBNAIL-AI][DEBUG] data 필드에서 이미지 추출")
                                break

                elif isinstance(content, str) and len(content) > 1000:
                    # 긴 문자열이면 base64일 가능성
                    try:
                        if content.startswith("data:image"):
                            base64_image_data = content.split(",", 1)[1]
                            print(f"[THUMBNAIL-AI][DEBUG] content 문자열에서 data URI 추출")
                    except:
                        pass

        if base64_image_data:
            # 파일로 저장
            timestamp = int(time.time() * 1000)
            filename = f"thumbnail_ai_{session_id}_{variant}_{timestamp}.png"

            output_dir = os.path.join(os.path.dirname(__file__), 'outputs')
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, filename)

            with open(filepath, 'wb') as f:
                f.write(base64.b64decode(base64_image_data))

            image_url = f'/output/{filename}'
            print(f"[THUMBNAIL-AI] 이미지 저장 완료: {image_url}")

        if not image_url:
            # 디버그: 응답 전체 구조 출력
            import json
            print(f"[THUMBNAIL-AI][DEBUG] 이미지 추출 실패 - 전체 응답:")
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str)[:2000])
            return jsonify({"ok": False, "error": "이미지 생성 결과를 찾을 수 없습니다. 서버 로그를 확인하세요."}), 200

        return jsonify({
            "ok": True,
            "image_url": image_url,
            "session_id": session_id,
            "variant": variant,
            "prompt_used": enhanced_prompt[:500]
        })

    except Exception as e:
        print(f"[THUMBNAIL-AI][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/thumbnail-ai/select', methods=['POST'])
def api_thumbnail_ai_select():
    """
    사용자의 썸네일 선택 저장 (학습 데이터)
    """
    try:
        data = request.get_json() or {}

        session_id = data.get('session_id', '')
        selected = data.get('selected', '')  # "A" or "B"
        prompts = data.get('prompts', {})
        script_summary = data.get('script_summary', '')
        genre = data.get('genre', '일반')
        title = data.get('title', '')
        selection_reason = data.get('selection_reason', '')
        image_urls = data.get('image_urls', {})

        if not session_id or not selected:
            return jsonify({"ok": False, "error": "세션 ID와 선택 정보가 필요합니다"}), 400

        print(f"[THUMBNAIL-AI] 선택 저장 - 세션: {session_id}, 선택: {selected}")

        # 학습 데이터 저장
        history = load_thumbnail_history()

        selection_data = {
            "id": session_id,
            "timestamp": dt.now().isoformat(),
            "title": title,
            "genre": genre,
            "script_summary": script_summary,
            "prompts": {
                "A": prompts.get("A", {}).get("prompt", ""),
                "B": prompts.get("B", {}).get("prompt", "")
            },
            "text_overlays": {
                "A": prompts.get("A", {}).get("text_overlay", {}),
                "B": prompts.get("B", {}).get("text_overlay", {})
            },
            "image_urls": image_urls,
            "selected": selected,
            "selection_reason": selection_reason
        }

        history["selections"].append(selection_data)

        # 최대 100개까지만 유지
        if len(history["selections"]) > 100:
            history["selections"] = history["selections"][-100:]

        save_thumbnail_history(history)

        print(f"[THUMBNAIL-AI] 학습 데이터 저장 완료 - 총 {len(history['selections'])}개")

        return jsonify({
            "ok": True,
            "message": "선택이 저장되었습니다",
            "session_id": session_id,
            "selected": selected,
            "total_selections": len(history["selections"])
        })

    except Exception as e:
        print(f"[THUMBNAIL-AI][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/thumbnail-ai/history', methods=['GET'])
def api_thumbnail_ai_history():
    """
    썸네일 학습 데이터 히스토리 조회
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        genre_filter = request.args.get('genre', None)

        history = load_thumbnail_history()
        selections = history.get("selections", [])

        # 장르 필터
        if genre_filter:
            selections = [s for s in selections if s.get("genre") == genre_filter]

        # 최신순 정렬
        selections = sorted(selections, key=lambda x: x.get("timestamp", ""), reverse=True)

        # limit 적용
        selections = selections[:limit]

        # 통계 계산
        all_selections = history.get("selections", [])
        stats = {
            "total": len(all_selections),
            "a_selected": sum(1 for s in all_selections if s.get("selected") == "A"),
            "b_selected": sum(1 for s in all_selections if s.get("selected") == "B"),
            "c_selected": sum(1 for s in all_selections if s.get("selected") == "C"),
            "genres": {}
        }

        for s in all_selections:
            g = s.get("genre", "일반")
            stats["genres"][g] = stats["genres"].get(g, 0) + 1

        return jsonify({
            "ok": True,
            "selections": selections,
            "stats": stats,
            "limit": limit,
            "genre_filter": genre_filter
        })

    except Exception as e:
        print(f"[THUMBNAIL-AI][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/thumbnail-ai/generate-single', methods=['POST'])
def api_thumbnail_ai_generate_single():
    """
    단일 썸네일 생성 (자동화 파이프라인용 - A 하나만 생성)
    """
    try:
        import requests as req

        data = request.get_json() or {}
        prompt_data = data.get('prompt', {})
        session_id = data.get('session_id', '')

        if not prompt_data.get('prompt'):
            return jsonify({"ok": False, "error": "prompt 필드가 필요합니다"}), 400

        print(f"[THUMBNAIL-AI] 단일 썸네일 생성 - 세션: {session_id}")

        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not openrouter_api_key:
            return jsonify({"ok": False, "error": "OpenRouter API 키가 설정되지 않았습니다"}), 200

        prompt = prompt_data.get('prompt', '')
        text_overlay = prompt_data.get('text_overlay', {})
        style = prompt_data.get('style', 'comic')

        main_text = text_overlay.get('main', '')
        sub_text = text_overlay.get('sub', '')

        text_instruction = ""
        if main_text:
            text_instruction = f"""
IMPORTANT TEXT OVERLAY:
- Add large, bold Korean text "{main_text}" prominently
- High contrast (white text with black outline)
"""
            if sub_text:
                text_instruction += f'- Subtitle: "{sub_text}"\n'

        enhanced_prompt = f"""Create a YouTube thumbnail (16:9 landscape).

{prompt}

{text_instruction}

Style: {style}, comic/illustration, eye-catching, high contrast"""

        headers = {
            "Authorization": f"Bearer {openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://drama-generator.app",
            "X-Title": "Thumbnail AI"
        }

        payload = {
            "model": "google/gemini-3-pro-image-preview",
            "modalities": ["text", "image"],
            "messages": [{"role": "user", "content": [{"type": "text", "text": enhanced_prompt}]}]
        }

        response = req.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=120
        )

        if response.status_code != 200:
            print(f"[THUMBNAIL-AI] API 오류: {response.status_code}")
            return jsonify({"ok": False, "error": response.text[:200]})

        result = response.json()

        # 디버그: 응답 구조 출력
        print(f"[THUMBNAIL-AI] 응답 키: {list(result.keys())}")
        choices = result.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            print(f"[THUMBNAIL-AI] message 키: {list(message.keys())}")

        # 이미지 추출 (다양한 형식 지원)
        base64_image_data = None
        if choices:
            message = choices[0].get("message", {})

            # 방법 1: images 필드 확인 (다양한 형식 지원)
            images = message.get("images")
            if images:
                print(f"[THUMBNAIL-AI] images 발견: 타입={type(images)}, 길이={len(images) if isinstance(images, list) else 'N/A'}")
                if isinstance(images, list) and len(images) > 0:
                    img = images[0]
                    print(f"[THUMBNAIL-AI] images[0] 타입={type(img)}, 내용={str(img)[:200] if img else 'None'}")
                    if isinstance(img, str):
                        base64_image_data = img.split(",", 1)[1] if img.startswith("data:") else img
                    elif isinstance(img, dict):
                        # 다양한 키 시도
                        base64_image_data = (
                            img.get("b64_json") or
                            img.get("base64") or
                            img.get("data") or
                            img.get("image_data") or
                            img.get("bytes")
                        )
                        # url 형식 (data:image/... 포함)
                        if not base64_image_data:
                            url = img.get("url") or img.get("source") or img.get("src")
                            # 중첩 형식: {"type": "image_url", "image_url": {"url": "..."}}
                            if not url:
                                image_url_obj = img.get("image_url")
                                if isinstance(image_url_obj, dict):
                                    url = image_url_obj.get("url")
                                    print(f"[THUMBNAIL-AI] images[0].image_url.url 형식 발견")
                            if url and isinstance(url, str) and url.startswith("data:image"):
                                base64_image_data = url.split(",", 1)[1]
                                print(f"[THUMBNAIL-AI] images[0].url에서 추출 성공")
                elif isinstance(images, str):
                    base64_image_data = images.split(",", 1)[1] if images.startswith("data:") else images

            # 방법 2: content 배열에서 image_url 추출
            if not base64_image_data:
                content = message.get("content")
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            item_type = item.get("type", "")
                            if item_type == "image_url":
                                url_data = item.get("image_url", {})
                                if isinstance(url_data, dict):
                                    url = url_data.get("url", "")
                                    if url.startswith("data:image"):
                                        base64_image_data = url.split(",", 1)[1]
                                        print(f"[THUMBNAIL-AI] content.image_url에서 추출 성공")
                                        break
                            elif item_type == "image":
                                # Gemini 3 Pro 형식
                                img_data = item.get("image", {})
                                if isinstance(img_data, dict):
                                    base64_image_data = img_data.get("data") or img_data.get("b64_json")
                                    if base64_image_data:
                                        print(f"[THUMBNAIL-AI] content.image에서 추출 성공")
                                        break
                            # 방법 2-1: inline_data 형식 (Gemini 일반 형식)
                            inline_data = item.get("inline_data")
                            if inline_data and isinstance(inline_data, dict):
                                base64_image_data = inline_data.get("data")
                                if base64_image_data:
                                    print(f"[THUMBNAIL-AI] inline_data에서 추출 성공")
                                    break

            # 방법 2-2: parts 배열 (네이티브 Gemini 형식)
            if not base64_image_data:
                parts = message.get("parts")
                if isinstance(parts, list):
                    for part in parts:
                        if isinstance(part, dict):
                            inline_data = part.get("inline_data") or part.get("inlineData")
                            if inline_data and isinstance(inline_data, dict):
                                base64_image_data = inline_data.get("data")
                                if base64_image_data:
                                    print(f"[THUMBNAIL-AI] parts.inline_data에서 추출 성공")
                                    break

            # 방법 3: content가 문자열인 경우 (data:image 포함 여부 확인)
            if not base64_image_data:
                content = message.get("content", "")
                if isinstance(content, str) and "data:image" in content:
                    import re
                    match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', content)
                    if match:
                        base64_image_data = match.group(1)
                        print(f"[THUMBNAIL-AI] content 문자열에서 추출 성공")

        if not base64_image_data:
            print(f"[THUMBNAIL-AI] 이미지 추출 실패 - 전체 응답: {str(result)[:1000]}")
            return jsonify({"ok": False, "error": "이미지 데이터 추출 실패"})

        # 파일 저장
        import base64
        upload_dir = "uploads/thumbnails"
        os.makedirs(upload_dir, exist_ok=True)
        filename = f"thumb_{session_id}.png"
        filepath = os.path.join(upload_dir, filename)

        with open(filepath, "wb") as f:
            f.write(base64.b64decode(base64_image_data))

        image_url = f"/uploads/thumbnails/{filename}"
        print(f"[THUMBNAIL-AI] 썸네일 저장: {image_url}")

        return jsonify({
            "ok": True,
            "image_url": image_url
        })

    except Exception as e:
        print(f"[THUMBNAIL-AI][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/thumbnail-ai/generate-both', methods=['POST'])
@app.route('/api/thumbnail-ai/generate-all', methods=['POST'])
def api_thumbnail_ai_generate_both():
    """
    A/B/C 3개의 썸네일을 한 번에 생성 (YouTube Test & Compare용)
    """
    try:
        import requests as req
        import time
        import base64
        from concurrent.futures import ThreadPoolExecutor

        data = request.get_json() or {}
        prompts = data.get('prompts', {})
        session_id = data.get('session_id', '')

        # A/B는 필수, C는 선택 (하위 호환성)
        if not prompts.get('A') or not prompts.get('B'):
            return jsonify({"ok": False, "error": "A/B 프롬프트가 모두 필요합니다"}), 400

        has_c = prompts.get('C') is not None
        print(f"[THUMBNAIL-AI] A/B/C 동시 생성 - 세션: {session_id}, C포함: {has_c}")

        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not openrouter_api_key:
            return jsonify({"ok": False, "error": "OpenRouter API 키가 설정되지 않았습니다"}), 200

        def generate_single(variant, prompt_data):
            """단일 썸네일 생성"""
            prompt = prompt_data.get('prompt', '')
            text_overlay = prompt_data.get('text_overlay', {})
            style = prompt_data.get('style', 'comic')

            main_text = text_overlay.get('main', '')
            sub_text = text_overlay.get('sub', '')

            text_instruction = ""
            if main_text:
                text_instruction = f"""
IMPORTANT TEXT OVERLAY:
- Add large, bold Korean text "{main_text}" prominently
- High contrast (white text with black outline)
"""
                if sub_text:
                    text_instruction += f'- Subtitle: "{sub_text}"\n'

            enhanced_prompt = f"""Create a YouTube thumbnail (16:9 landscape).

{prompt}

{text_instruction}

Style: {style}, comic/illustration, eye-catching, high contrast"""

            headers = {
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://drama-generator.app",
                "X-Title": "Thumbnail AI"
            }

            payload = {
                "model": "google/gemini-3-pro-image-preview",
                "modalities": ["text", "image"],
                "messages": [{"role": "user", "content": [{"type": "text", "text": enhanced_prompt}]}]
            }

            try:
                response = req.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120
                )

                if response.status_code != 200:
                    print(f"[THUMBNAIL-AI][{variant}] API 오류: {response.status_code} - {response.text[:500]}")
                    return {"variant": variant, "ok": False, "error": response.text[:200]}

                result = response.json()

                # 디버그: 전체 응답 구조 출력
                print(f"[THUMBNAIL-AI][{variant}] 응답 키: {list(result.keys())}")
                choices = result.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    print(f"[THUMBNAIL-AI][{variant}] message 키: {list(message.keys())}")
                    print(f"[THUMBNAIL-AI][{variant}] content 타입: {type(message.get('content'))}")

                    # images 배열 직접 확인
                    images_raw = message.get("images")
                    print(f"[THUMBNAIL-AI][{variant}] images 값: 타입={type(images_raw)}, 내용={str(images_raw)[:500] if images_raw else 'None/Empty'}")

                    content_preview = str(message.get('content', ''))[:300]
                    print(f"[THUMBNAIL-AI][{variant}] content 미리보기: {content_preview}")

                # 이미지 추출
                base64_image_data = None
                choices = result.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})

                    # 방법 1: images 필드 확인 (다양한 형식 지원)
                    images = message.get("images")
                    if images:
                        # 배열인 경우
                        if isinstance(images, list) and len(images) > 0:
                            img = images[0]
                            if isinstance(img, str):
                                base64_image_data = img.split(",", 1)[1] if img.startswith("data:") else img
                                print(f"[THUMBNAIL-AI][{variant}] images 배열(str)에서 추출 성공")
                            elif isinstance(img, dict):
                                # 형식 1: {'type': 'image_url', 'image_url': {'url': 'data:...'}} (OpenRouter/GPT-5.1 형식)
                                if img.get("type") == "image_url" and "image_url" in img:
                                    url = img.get("image_url", {}).get("url", "")
                                    if url:
                                        base64_image_data = url.split(",", 1)[1] if url.startswith("data:") else url
                                        print(f"[THUMBNAIL-AI][{variant}] images 배열(image_url dict)에서 추출 성공")
                                else:
                                    # 형식 2: {data: ..., url: ..., b64_json: ...}
                                    data = img.get("data") or img.get("b64_json") or img.get("url", "")
                                    if data:
                                        base64_image_data = data.split(",", 1)[1] if data.startswith("data:") else data
                                        print(f"[THUMBNAIL-AI][{variant}] images 배열(dict)에서 추출 성공")
                        # 문자열인 경우
                        elif isinstance(images, str):
                            base64_image_data = images.split(",", 1)[1] if images.startswith("data:") else images
                            print(f"[THUMBNAIL-AI][{variant}] images 문자열에서 추출 성공")
                        # dict인 경우
                        elif isinstance(images, dict):
                            data = images.get("data") or images.get("b64_json") or images.get("url", "")
                            if data:
                                base64_image_data = data.split(",", 1)[1] if data.startswith("data:") else data
                                print(f"[THUMBNAIL-AI][{variant}] images dict에서 추출 성공")

                    # 방법 2: content 배열에서 image_url 타입 확인
                    if not base64_image_data:
                        content = message.get("content", [])
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict):
                                    item_type = item.get("type", "")

                                    # OpenAI 형식: image_url
                                    if item_type == "image_url":
                                        url = item.get("image_url", {}).get("url", "")
                                        if url.startswith("data:"):
                                            base64_image_data = url.split(",", 1)[1]
                                            print(f"[THUMBNAIL-AI][{variant}] content.image_url에서 추출 성공")
                                            break

                                    # Gemini 형식: inline_data
                                    elif "inline_data" in item:
                                        inline = item.get("inline_data", {})
                                        data = inline.get("data")
                                        if data:
                                            base64_image_data = data
                                            print(f"[THUMBNAIL-AI][{variant}] inline_data에서 추출 성공")
                                            break

                                    # 대안: type이 "image"일 경우
                                    elif item_type == "image":
                                        # inline_data 내부 확인
                                        if "inline_data" in item:
                                            inline = item.get("inline_data", {})
                                            data = inline.get("data")
                                            if data:
                                                base64_image_data = data
                                                print(f"[THUMBNAIL-AI][{variant}] image.inline_data에서 추출 성공")
                                                break
                                        # 직접 data 필드
                                        img_data = item.get("data") or item.get("image") or item.get("url", "")
                                        if img_data:
                                            if img_data.startswith("data:"):
                                                base64_image_data = img_data.split(",", 1)[1]
                                            else:
                                                base64_image_data = img_data
                                            print(f"[THUMBNAIL-AI][{variant}] content.image에서 추출 성공")
                                            break

                                    # 기타: data 필드 직접 확인
                                    elif "data" in item and item_type != "text":
                                        base64_image_data = item["data"]
                                        print(f"[THUMBNAIL-AI][{variant}] data 필드에서 추출 성공")
                                        break

                        elif isinstance(content, str):
                            # content가 문자열인 경우 (텍스트 응답만)
                            print(f"[THUMBNAIL-AI][{variant}] content가 문자열임 (이미지 없음): {content[:200]}")

                if base64_image_data:
                    timestamp = int(time.time() * 1000)
                    filename = f"thumbnail_ai_{session_id}_{variant}_{timestamp}.png"
                    output_dir = os.path.join(os.path.dirname(__file__), 'outputs')
                    os.makedirs(output_dir, exist_ok=True)
                    filepath = os.path.join(output_dir, filename)

                    with open(filepath, 'wb') as f:
                        f.write(base64.b64decode(base64_image_data))

                    return {"variant": variant, "ok": True, "image_url": f'/output/{filename}'}

                # 디버그: 전체 응답 구조 출력
                import json
                print(f"[THUMBNAIL-AI][{variant}] 이미지 추출 실패 - 전체 응답:")
                print(json.dumps(result, indent=2, ensure_ascii=False, default=str)[:3000])
                return {"variant": variant, "ok": False, "error": "이미지 추출 실패 - API 응답에 이미지가 없습니다"}

            except Exception as e:
                return {"variant": variant, "ok": False, "error": str(e)}

        # 병렬 생성 (A/B/C)
        results = {"A": None, "B": None, "C": None}
        max_workers = 3 if has_c else 2

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(generate_single, "A", prompts["A"]): "A",
                executor.submit(generate_single, "B", prompts["B"]): "B"
            }
            if has_c:
                futures[executor.submit(generate_single, "C", prompts["C"])] = "C"

            for future in as_completed(futures):
                result = future.result()
                results[result["variant"]] = result

        # C가 없으면 결과에서 제거
        if not has_c:
            del results["C"]

        status_msg = f"A: {results['A'].get('ok')}, B: {results['B'].get('ok')}"
        if has_c:
            status_msg += f", C: {results['C'].get('ok')}"
        print(f"[THUMBNAIL-AI] A/B/C 생성 완료 - {status_msg}")

        return jsonify({
            "ok": True,
            "session_id": session_id,
            "results": results
        })

    except Exception as e:
        print(f"[THUMBNAIL-AI][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/thumbnail-ai/download-zip', methods=['POST'])
def api_thumbnail_ai_download_zip():
    """
    생성된 썸네일들을 ZIP 파일로 다운로드
    YouTube Test & Compare용 3개 썸네일
    """
    try:
        import zipfile
        from io import BytesIO

        data = request.get_json() or {}
        image_urls = data.get('image_urls', {})
        session_id = data.get('session_id', 'thumbnails')

        if not image_urls:
            return jsonify({"ok": False, "error": "이미지 URL이 필요합니다"}), 400

        # ZIP 파일 생성
        zip_buffer = BytesIO()
        output_dir = os.path.join(os.path.dirname(__file__), 'outputs')

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for variant, url in image_urls.items():
                if not url:
                    continue

                # /output/xxx.png → outputs/xxx.png
                if url.startswith('/output/'):
                    filename = url.replace('/output/', '')
                    filepath = os.path.join(output_dir, filename)

                    if os.path.exists(filepath):
                        # 파일명을 간단하게 변경 (thumbnail_A.png, thumbnail_B.png, thumbnail_C.png)
                        zip_filename = f"thumbnail_{variant}.png"
                        zip_file.write(filepath, zip_filename)
                        print(f"[THUMBNAIL-ZIP] Added: {zip_filename}")

        zip_buffer.seek(0)

        # ZIP 파일 저장
        zip_filename = f"thumbnails_{session_id}_{int(time.time())}.zip"
        zip_filepath = os.path.join(output_dir, zip_filename)

        with open(zip_filepath, 'wb') as f:
            f.write(zip_buffer.getvalue())

        print(f"[THUMBNAIL-ZIP] ZIP 생성 완료: {zip_filename}")

        return jsonify({
            "ok": True,
            "zip_url": f"/output/{zip_filename}",
            "filename": zip_filename
        })

    except Exception as e:
        print(f"[THUMBNAIL-ZIP][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== Google Sheets 자동화 시스템 (서비스 계정 인증) =====
from google.oauth2 import service_account
from googleapiclient.discovery import build

def get_sheets_service_account():
    """서비스 계정을 사용하여 Google Sheets API 서비스 객체 반환"""
    try:
        # 환경변수에서 서비스 계정 JSON 로드
        service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
        if not service_account_json:
            print("[SHEETS] GOOGLE_SERVICE_ACCOUNT_JSON 환경변수가 설정되지 않음")
            return None

        # JSON 문자열을 dict로 파싱
        service_account_info = json.loads(service_account_json)

        # 서비스 계정 인증 정보 생성
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=[
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/spreadsheets.readonly'
            ]
        )

        # Sheets API 서비스 빌드
        service = build('sheets', 'v4', credentials=credentials)
        return service
    except json.JSONDecodeError as e:
        print(f"[SHEETS] 서비스 계정 JSON 파싱 실패: {e}")
        return None
    except Exception as e:
        print(f"[SHEETS] 서비스 계정 인증 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


def sheets_read_rows(service, sheet_id, range_name='Sheet1!A:H'):
    """
    Google Sheets에서 행 읽기
    반환: [[row1_values], [row2_values], ...]
    """
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        return result.get('values', [])
    except Exception as e:
        print(f"[SHEETS] 읽기 실패: {e}")
        return []


def sheets_update_cell(service, sheet_id, cell_range, value):
    """
    Google Sheets 특정 셀 업데이트
    cell_range 예시: 'Sheet1!A2' 또는 'Sheet1!G2:H2'
    """
    try:
        body = {
            'values': [[value]] if not isinstance(value, list) else [value]
        }
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=cell_range,
            valueInputOption='RAW',
            body=body
        ).execute()
        return True
    except Exception as e:
        print(f"[SHEETS] 셀 업데이트 실패: {e}")
        return False


def run_automation_pipeline(row_data, row_index):
    """
    자동화 파이프라인 실행 - 기존 /image 페이지 API 재사용

    row_data: [상태, 예약시간, 채널ID, 대본, 제목, 공개설정, 영상URL, 에러메시지]
    row_index: 시트에서의 행 번호 (1-based, 헤더 제외하면 데이터는 2부터)

    ★★★ 중요: 기존 /image 페이지와 동일한 API를 사용합니다 ★★★
    - /api/image/analyze-script (대본 분석)
    - /api/drama/generate-image (이미지 생성)
    - /api/image/generate-assets-zip (TTS + 자막)
    - /api/thumbnail-ai/generate-all (썸네일 생성)
    - /api/image/generate-video (영상 생성)
    - /api/youtube/upload (YouTube 업로드)
    """
    import requests as req
    import time as time_module

    try:
        # 시트 컬럼 구조:
        # ===== Google Sheets 컬럼 구조 (CLAUDE.md 기준) =====
        # A(0): 상태, B(1): 작업시간, C(2): 채널ID, D(3): 채널명(참고용)
        # E(4): 예약시간, F(5): 대본, G(6): 제목
        # H(7): 제목2(출력), I(8): 제목3(출력), J(9): 비용(출력)
        # K(10): 공개설정, L(11): 영상URL(출력), M(12): 에러메시지(출력)
        # N(13): 음성, O(14): 타겟, P(15): 카테고리(출력), Q(16): 쇼츠URL(출력)
        status = row_data[0] if len(row_data) > 0 else ''
        work_time = row_data[1] if len(row_data) > 1 else ''  # B: 작업시간 (파이프라인 실행용)
        channel_id = (row_data[2] if len(row_data) > 2 else '').strip()  # 공백 제거
        channel_name = row_data[3] if len(row_data) > 3 else ''  # D: 채널명 (참고용, 코드에서 미사용)
        publish_time = row_data[4] if len(row_data) > 4 else ''  # E: 예약시간 (YouTube 공개용)
        script = row_data[5] if len(row_data) > 5 else ''
        title = row_data[6] if len(row_data) > 6 else ''
        # H(7), I(8), J(9)는 출력 컬럼 (제목2, 제목3, 비용)
        visibility = (row_data[10] if len(row_data) > 10 else '').strip() or 'private'  # K열: 공개설정
        # L(11), M(12)는 출력 컬럼 (영상URL, 에러메시지)
        voice = (row_data[13] if len(row_data) > 13 else '').strip() or 'ko-KR-Neural2-C'  # N열: 음성
        audience = (row_data[14] if len(row_data) > 14 else '').strip() or 'senior'  # O열: 타겟 시청자
        category = (row_data[15] if len(row_data) > 15 else '').strip()  # P열: 카테고리 (뉴스 등)

        # 비용 추적 변수 초기화
        total_cost = 0.0

        print(f"[AUTOMATION] ========== 파이프라인 시작 (API 재사용) ==========")
        print(f"[AUTOMATION] 행 {row_index}")
        print(f"  - 작업시간: {work_time}")
        print(f"  - 채널: {channel_name or channel_id}")
        print(f"  - 예약시간: {publish_time or '(없음 - 즉시 공개)'}")
        print(f"  - 대본 길이: {len(script)} 글자")
        print(f"  - 제목: {title or '(AI 생성 예정)'}")
        print(f"  - 공개설정: {visibility}")
        print(f"  - 음성: {voice}")
        print(f"  - 타겟: {audience}")
        print(f"  - 카테고리: {category or '(일반)'}")

        if not script or len(script.strip()) < 10:
            return {"ok": False, "error": "대본이 너무 짧습니다 (최소 10자)", "video_url": None}

        session_id = f"auto_{row_index}_{int(time_module.time())}"
        base_url = "http://127.0.0.1:" + str(os.environ.get("PORT", 5059))

        # ========== 1. 대본 분석 (/api/image/analyze-script) ==========
        print(f"[AUTOMATION] 1. 대본 분석 시작...")
        try:
            # 이미지 개수 8개 고정 (추후 지시 있을때까지)
            fixed_image_count = 8
            print(f"[AUTOMATION] 이미지 {fixed_image_count}개 고정 생성")

            analyze_resp = req.post(f"{base_url}/api/image/analyze-script", json={
                "script": script,
                "content_type": "drama",
                "image_style": "animation",  # 스틱맨 스타일
                "image_count": fixed_image_count,
                "audience": audience,
                "category": category,  # 뉴스 등 카테고리
                "output_language": "auto"
            }, timeout=180)  # GPT-5.1 응답 대기 시간 증가 (120→180초)

            analyze_data = analyze_resp.json()
            if not analyze_data.get('ok'):
                return {"ok": False, "error": f"대본 분석 실패: {analyze_data.get('error')}", "video_url": None}

            scenes = analyze_data.get('scenes', [])
            youtube_meta = analyze_data.get('youtube', {})
            thumbnail_data = analyze_data.get('thumbnail', {})
            ai_prompts = thumbnail_data.get('ai_prompts', {})
            video_effects = analyze_data.get('video_effects', {})  # 새 기능: BGM, 효과음, 자막 강조 등

            # 썸네일 전략 데이터 추출 (새 구조)
            thumbnail_text_candidates = thumbnail_data.get('thumbnail_text_candidates', [])
            best_combo = thumbnail_data.get('best_combo', {})
            layout_suggestion = thumbnail_data.get('layout_suggestion', {})
            consistency_check = thumbnail_data.get('consistency_check', {})
            design_notes = thumbnail_data.get('design_notes', '')

            # GPT-5.1이 대본 분석으로 자동 감지한 카테고리 (news 또는 story)
            detected_category = analyze_data.get('detected_category', 'story')
            print(f"[AUTOMATION] GPT 감지 카테고리: {detected_category}")

            # 썸네일 전략 로깅
            if best_combo:
                print(f"[AUTOMATION] 썸네일 전략:")
                print(f"  - 선택된 제목: {best_combo.get('chosen_title', '')[:50]}")
                print(f"  - 선택된 문구: {best_combo.get('chosen_thumbnail_text', '')}")
                print(f"  - 선택 이유: {best_combo.get('reason', '')[:80]}")
            if layout_suggestion:
                print(f"  - 레이아웃: {layout_suggestion.get('layout_type', '')}")
            if consistency_check:
                print(f"  - CTR 점수: {consistency_check.get('ctr_score', 0)}/10, Watch Time 점수: {consistency_check.get('watchtime_score', 0)}/10")

            generated_title = youtube_meta.get('title', '')
            title_options = youtube_meta.get('title_options', [])

            # description 처리: 새 구조(객체) 또는 기존 구조(문자열) 지원
            desc_raw = youtube_meta.get('description', '')
            if isinstance(desc_raw, dict):
                description = desc_raw.get('full_text', '')
                description_chapters = desc_raw.get('chapters', [])
                description_preview = desc_raw.get('preview_2_lines', '')
            else:
                description = desc_raw
                description_chapters = []
                description_preview = ''

            # 해시태그, 태그, 고정댓글 추출
            hashtags = youtube_meta.get('hashtags', [])
            tags = youtube_meta.get('tags', [])
            pin_comment = youtube_meta.get('pin_comment', '')

            # 로깅
            print(f"[AUTOMATION] 설명란: {len(description)}자, 챕터: {len(description_chapters)}개")
            print(f"[AUTOMATION] 해시태그: {hashtags}")
            print(f"[AUTOMATION] 태그: {len(tags)}개")

            # title_options 로깅 (3가지 스타일 제목)
            if title_options:
                print(f"[AUTOMATION] 제목 옵션 (3가지 스타일):")
                for opt in title_options:
                    print(f"  - [{opt.get('style', '?')}] {opt.get('title', '')}")

            if not title:
                title = generated_title or f"자동 생성 영상 #{row_index}"

            # 비용: GPT-5.1 대본 분석 (~$0.03)
            total_cost += 0.03
            print(f"[AUTOMATION] 1. 완료: {len(scenes)}개 씬, 제목: {title[:40]}... (비용: $0.03)")
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"ok": False, "error": f"대본 분석 오류: {str(e)}", "video_url": None, "cost": total_cost}

        # ========== 2. 병렬 처리: 이미지 + TTS + 썸네일 ==========
        print(f"[AUTOMATION] 2. 병렬 처리 시작 (이미지 {len(scenes)}개 + TTS + 썸네일)...")
        from concurrent.futures import ThreadPoolExecutor, as_completed

        thumbnail_url = None
        parallel_errors = []

        def generate_images():
            """이미지 생성 (병렬 작업 1) - 4개씩 병렬 처리"""
            nonlocal total_cost
            from concurrent.futures import ThreadPoolExecutor as ImgExecutor, as_completed as img_completed

            print(f"[AUTOMATION][IMAGE] 이미지 생성 시작 ({len(scenes)}개, 4개씩 병렬)...")

            def generate_single_image(idx, scene):
                """단일 이미지 생성 (실패 시 3회 재시도)"""
                prompt = scene.get('image_prompt', '')
                if not prompt:
                    return idx, None

                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        img_resp = req.post(f"{base_url}/api/drama/generate-image", json={
                            "prompt": prompt,
                            "size": "1280x720",
                            "imageProvider": "gemini"
                        }, timeout=120)

                        img_data = img_resp.json()
                        if img_data.get('ok') and img_data.get('imageUrl'):
                            print(f"[AUTOMATION][IMAGE] {idx+1}/{len(scenes)} 완료")
                            return idx, img_data['imageUrl']
                        else:
                            print(f"[AUTOMATION][IMAGE] {idx+1} 실패 (시도 {attempt+1}/{max_retries})")
                    except Exception as e:
                        print(f"[AUTOMATION][IMAGE] {idx+1} 오류 (시도 {attempt+1}/{max_retries}): {e}")

                    if attempt < max_retries - 1:
                        time_module.sleep(2)  # 재시도 전 대기

                print(f"[AUTOMATION][IMAGE] {idx+1} 최종 실패 (3회 시도)")
                return idx, None

            # 4개씩 병렬 처리
            with ImgExecutor(max_workers=4) as img_executor:
                futures = {
                    img_executor.submit(generate_single_image, i, scene): i
                    for i, scene in enumerate(scenes)
                }

                for future in img_completed(futures):
                    idx, image_url = future.result()
                    if image_url:
                        scenes[idx]['image_url'] = image_url

            success_count = len([s for s in scenes if s.get('image_url')])
            image_cost = success_count * 0.02
            total_cost += image_cost
            print(f"[AUTOMATION][IMAGE] 완료: {success_count}/{len(scenes)}개 (비용: ${image_cost:.2f})")
            return success_count

        def generate_tts():
            """TTS 생성 (병렬 작업 2)"""
            nonlocal total_cost
            print(f"[AUTOMATION][TTS] TTS 생성 시작...")
            try:
                scenes_for_tts = []
                for i, scene in enumerate(scenes):
                    scenes_for_tts.append({
                        "scene_number": i + 1,
                        "text": scene.get('narration', ''),
                        "image_url": scene.get('image_url', '')
                    })

                assets_resp = req.post(f"{base_url}/api/image/generate-assets-zip", json={
                    "session_id": session_id,
                    "scenes": scenes_for_tts,
                    "voice": voice,
                    "include_images": False
                }, timeout=300)

                assets_data = assets_resp.json()
                if not assets_data.get('ok'):
                    raise Exception(f"TTS 실패: {assets_data.get('error')}")

                scene_metadata = assets_data.get('scene_metadata', [])
                for sm in scene_metadata:
                    idx = sm.get('scene_idx', -1)
                    if 0 <= idx < len(scenes):
                        scenes[idx]['audio_url'] = sm.get('audio_url')
                        scenes[idx]['duration'] = sm.get('duration', 5)
                        scenes[idx]['subtitles'] = sm.get('subtitles', [])

                tts_cost = len(script) * 0.000004
                total_cost += tts_cost
                print(f"[AUTOMATION][TTS] 완료: {len(scene_metadata)}개 씬 (비용: ${tts_cost:.3f})")
                return True
            except Exception as e:
                print(f"[AUTOMATION][TTS] 오류: {e}")
                parallel_errors.append(f"TTS: {str(e)}")
                return False

        def generate_thumbnail():
            """썸네일 생성 (병렬 작업 3)"""
            nonlocal thumbnail_url, total_cost
            print(f"[AUTOMATION][THUMB] 썸네일 생성 시작...")
            try:
                # GPT-5.1이 대본 분석으로 자동 감지한 카테고리 사용 (Google Sheets 의존 제거)
                is_news = detected_category == 'news'
                print(f"[AUTOMATION][THUMB] GPT 감지 카테고리: {detected_category} → {'뉴스' if is_news else '스토리'} 스타일")

                # GPT가 생성한 ai_prompts.A 사용 (카테고리에 맞는 스타일로 이미 생성됨)
                if ai_prompts and ai_prompts.get('A'):
                    thumb_prompt = ai_prompts.get('A').copy() if isinstance(ai_prompts.get('A'), dict) else ai_prompts.get('A')
                    # best_combo에서 선택된 텍스트가 있으면 text_overlay에 적용
                    if best_combo and best_combo.get('chosen_thumbnail_text'):
                        chosen_text = best_combo.get('chosen_thumbnail_text', '')
                        if isinstance(thumb_prompt, dict):
                            # 줄바꿈이 있으면 첫 줄은 main, 나머지는 sub로 분리
                            if '\\n' in chosen_text:
                                parts = chosen_text.split('\\n', 1)
                                thumb_prompt['text_overlay'] = {'main': parts[0], 'sub': parts[1] if len(parts) > 1 else ''}
                            else:
                                thumb_prompt['text_overlay'] = {'main': chosen_text, 'sub': ''}
                            print(f"[AUTOMATION][THUMB] best_combo 텍스트 적용: {chosen_text}")
                    print(f"[AUTOMATION][THUMB] GPT 생성 프롬프트 사용")
                elif is_news:
                    # 폴백: 하드코딩된 뉴스 스타일 프롬프트
                    print(f"[AUTOMATION][THUMB] 하드코딩된 뉴스 스타일 프롬프트 사용 (폴백)")
                    # best_combo 텍스트가 있으면 사용
                    fallback_text = "뉴스 헤드라인"
                    if best_combo and best_combo.get('chosen_thumbnail_text'):
                        fallback_text = best_combo.get('chosen_thumbnail_text', fallback_text)
                    thumb_prompt = {
                        "prompt": "Korean TV news broadcast YouTube thumbnail exactly like KBS MBC SBS news. 16:9 aspect ratio. Real photo of news anchor or reporter in professional attire on one side. Large bold Korean headline text in WHITE or YELLOW with quotation marks. Dark blue or navy gradient background. RED accent bar with '단독' or '속보' badge at top. Multiple text layers - main headline + sub headline. News ticker style bar at bottom. Professional broadcast journalism aesthetic. Photorealistic news studio look. High contrast text readable at small size.",
                        "text_overlay": {"main": fallback_text, "sub": ""}
                    }
                else:
                    # 폴백: 기본 스토리 스타일 프롬프트
                    print(f"[AUTOMATION][THUMB] 하드코딩된 스토리 스타일 프롬프트 사용 (폴백)")
                    # best_combo 텍스트가 있으면 사용
                    fallback_text = "메인 텍스트"
                    if best_combo and best_combo.get('chosen_thumbnail_text'):
                        fallback_text = best_combo.get('chosen_thumbnail_text', fallback_text)
                    thumb_prompt = {
                        "prompt": "Cartoon illustration style YouTube thumbnail, 16:9 aspect ratio. Character with exaggerated emotional expression. Vibrant colors, high contrast. NO realistic humans, comic/cartoon style only.",
                        "text_overlay": {"main": fallback_text, "sub": ""}
                    }

                thumb_resp = req.post(f"{base_url}/api/thumbnail-ai/generate-single", json={
                    "session_id": f"thumb_{session_id}",
                    "prompt": thumb_prompt
                }, timeout=180)

                thumb_data = thumb_resp.json()
                if thumb_data.get('ok') and thumb_data.get('image_url'):
                    thumbnail_url = thumb_data['image_url']
                    total_cost += 0.03
                    print(f"[AUTOMATION][THUMB] 완료 (비용: $0.03)")
                    return thumbnail_url
                else:
                    print(f"[AUTOMATION][THUMB] 실패: {thumb_data.get('error', '알 수 없음')}")
                    return None
            except Exception as e:
                print(f"[AUTOMATION][THUMB] 오류: {e}")
                return None

        # 병렬 실행
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(generate_images): "images",
                executor.submit(generate_tts): "tts",
                executor.submit(generate_thumbnail): "thumbnail"
            }

            for future in as_completed(futures):
                task_name = futures[future]
                try:
                    result = future.result()
                    print(f"[AUTOMATION] 병렬 작업 완료: {task_name}")
                except Exception as e:
                    print(f"[AUTOMATION] 병렬 작업 실패: {task_name} - {e}")
                    parallel_errors.append(f"{task_name}: {str(e)}")

        # TTS 실패 시 중단
        if not any(s.get('audio_url') for s in scenes):
            return {"ok": False, "error": f"TTS 생성 실패: {'; '.join(parallel_errors)}", "video_url": None, "cost": total_cost}

        # 이미지 실패 시 중단 (최소 1개 이상 필요)
        image_success_count = len([s for s in scenes if s.get('image_url')])
        if image_success_count == 0:
            return {"ok": False, "error": f"이미지 생성 실패: 모든 이미지 생성에 실패했습니다", "video_url": None, "cost": total_cost}
        elif image_success_count < len(scenes):
            print(f"[AUTOMATION] 경고: 이미지 {image_success_count}/{len(scenes)}개만 생성됨")

        print(f"[AUTOMATION] 2. 병렬 처리 완료")

        # ========== 3. 영상 생성 (/api/image/generate-video) ==========
        print(f"[AUTOMATION] 3. 영상 생성 시작...")

        video_url_local = None
        video_generation_error = None
        max_video_retries = 2  # 최대 2번 시도 (실패 시 1회 재시도)

        for video_attempt in range(max_video_retries):
            try:
                if video_attempt > 0:
                    print(f"[AUTOMATION] 3. 영상 생성 재시도 ({video_attempt + 1}/{max_video_retries}) - 3분 후 시작...")
                    time_module.sleep(180)  # 재시도 전 3분 대기

                video_resp = req.post(f"{base_url}/api/image/generate-video", json={
                    "session_id": session_id,
                    "scenes": scenes,
                    "language": "ko",  # 한글 자막용 NanumGothic 폰트 적용
                    "video_effects": video_effects  # 새 기능: BGM, 효과음, 자막 강조, Ken Burns 등
                }, timeout=600)

                video_data = video_resp.json()
                if not video_data.get('ok') and not video_data.get('job_id'):
                    video_generation_error = f"영상 생성 시작 실패: {video_data.get('error')}"
                    print(f"[AUTOMATION] 3. 시도 {video_attempt + 1} 실패: {video_generation_error}")
                    continue  # 재시도

                job_id = video_data.get('job_id')

                # 영상 생성 완료 대기 (폴링) - 40분 대기
                # 10분 영상에 ~20분 소요되므로 여유있게 40분
                for _ in range(1200):  # 1200 * 2초 = 40분
                    time_module.sleep(2)
                    status_resp = req.get(f"{base_url}/api/image/video-status/{job_id}", timeout=30)
                    status_data = status_resp.json()

                    if status_data.get('status') == 'completed':
                        video_url_local = status_data.get('video_url')
                        break
                    elif status_data.get('status') == 'failed':
                        video_generation_error = f"영상 생성 실패: {status_data.get('error')}"
                        print(f"[AUTOMATION] 3. 시도 {video_attempt + 1} 실패: {video_generation_error}")
                        break  # 내부 루프 탈출, 재시도

                if video_url_local:
                    print(f"[AUTOMATION] 3. 완료: {video_url_local} (영상 생성은 무료)")
                    break  # 성공, 루프 탈출
                elif not video_generation_error:
                    video_generation_error = "영상 생성 타임아웃 (40분 초과)"
                    print(f"[AUTOMATION] 3. 시도 {video_attempt + 1} 실패: {video_generation_error}")

            except Exception as e:
                import traceback
                traceback.print_exc()
                video_generation_error = f"영상 생성 오류: {str(e)}"
                print(f"[AUTOMATION] 3. 시도 {video_attempt + 1} 예외: {video_generation_error}")

        # 모든 시도 후에도 실패하면 에러 반환
        if not video_url_local:
            return {"ok": False, "error": video_generation_error or "영상 생성 실패", "video_url": None, "cost": total_cost}

        # ========== 4. YouTube 업로드 ==========
        print(f"[AUTOMATION] 4. YouTube 업로드 시작...")

        # GPT가 생성한 예상 챕터 제거 (실제 duration 기반 챕터로 대체)
        # 예상 챕터는 "00:00 제목" 또는 "0:00 제목" 형식의 연속된 줄로 시작함
        try:
            import re
            # 타임스탬프로 시작하는 연속된 줄들을 찾아서 제거 (예상 챕터 섹션)
            # 패턴: 숫자:숫자 또는 숫자:숫자:숫자로 시작하는 줄
            lines = description.split('\n')
            cleaned_lines = []
            in_chapter_section = False
            consecutive_timestamps = 0

            for i, line in enumerate(lines):
                stripped = line.strip()
                # 타임스탬프로 시작하는지 확인 (0:00, 00:00, 1:30 등)
                is_timestamp_line = bool(re.match(r'^\d{1,2}:\d{2}(?::\d{2})?\s', stripped))

                if is_timestamp_line:
                    consecutive_timestamps += 1
                    # 연속으로 3개 이상 타임스탬프 줄이면 챕터 섹션으로 간주
                    if consecutive_timestamps >= 3:
                        in_chapter_section = True
                        # 이전에 추가한 타임스탬프 줄들도 제거
                        while cleaned_lines and re.match(r'^\d{1,2}:\d{2}(?::\d{2})?\s', cleaned_lines[-1].strip()):
                            cleaned_lines.pop()
                    if not in_chapter_section:
                        cleaned_lines.append(line)
                else:
                    consecutive_timestamps = 0
                    if in_chapter_section:
                        # 빈 줄이면 챕터 섹션 종료
                        if not stripped:
                            in_chapter_section = False
                        # 타임스탬프가 아닌 줄이 오면 챕터 섹션 종료
                        else:
                            in_chapter_section = False
                            cleaned_lines.append(line)
                    else:
                        cleaned_lines.append(line)

            description = '\n'.join(cleaned_lines)
            print(f"[AUTOMATION] GPT 예상 챕터 제거 완료 (실제 duration 기반 챕터로 대체)")
        except Exception as clean_err:
            print(f"[AUTOMATION] 챕터 정리 오류 (무시됨): {clean_err}")

        # 자동 챕터 생성 (씬별 chapter_title과 duration 기반)
        try:
            chapters_text = "\n\n📑 챕터\n"
            current_time = 0
            has_chapters = False
            for idx, scene in enumerate(scenes):
                chapter_title = scene.get('chapter_title', '')
                scene_duration = scene.get('duration', 0)
                if chapter_title:
                    has_chapters = True
                    # 타임스탬프 형식: M:SS 또는 H:MM:SS
                    minutes = int(current_time // 60)
                    seconds = int(current_time % 60)
                    if minutes >= 60:
                        hours = minutes // 60
                        minutes = minutes % 60
                        timestamp = f"{hours}:{minutes:02d}:{seconds:02d}"
                    else:
                        timestamp = f"{minutes}:{seconds:02d}"
                    chapters_text += f"{timestamp} {chapter_title}\n"
                current_time += scene_duration

            if has_chapters:
                description = description + chapters_text
                print(f"[AUTOMATION] 자동 챕터 생성 완료 ({len([s for s in scenes if s.get('chapter_title')])}개)")
        except Exception as chapter_err:
            print(f"[AUTOMATION] 챕터 생성 오류 (무시됨): {chapter_err}")

        # 해시태그를 설명란 끝에 추가
        if hashtags and len(hashtags) > 0:
            hashtags_text = "\n\n" + " ".join(hashtags)
            description = description + hashtags_text
            print(f"[AUTOMATION] 해시태그 추가: {' '.join(hashtags)}")

        try:
            upload_payload = {
                "videoPath": video_url_local,
                "title": title,
                "description": description,
                "privacyStatus": visibility,
                "channelId": channel_id
            }

            # 썸네일이 있으면 추가
            if thumbnail_url:
                upload_payload["thumbnailPath"] = thumbnail_url

            # GPT-5.1 생성 태그 추가
            if tags and len(tags) > 0:
                upload_payload["tags"] = tags
                print(f"[AUTOMATION] YouTube 태그 {len(tags)}개 추가")

            # 예약시간(K열)이 있으면 ISO 8601 형식으로 변환하여 추가
            if publish_time:
                try:
                    from datetime import datetime
                    import re

                    # 다양한 형식 지원: "2024-12-06 15:00", "2024/12/06 15:00", "12/06 15:00" 등
                    publish_time_str = str(publish_time).strip()

                    # 이미 ISO 8601 형식이면 그대로 사용
                    if 'T' in publish_time_str and publish_time_str.endswith('Z'):
                        publish_at_iso = publish_time_str
                    else:
                        # 일반적인 날짜 형식 파싱 시도
                        parsed_dt = None
                        formats_to_try = [
                            "%Y-%m-%d %H:%M:%S",
                            "%Y-%m-%d %H:%M",
                            "%Y/%m/%d %H:%M:%S",
                            "%Y/%m/%d %H:%M",
                            "%m/%d %H:%M",  # 월/일만 있으면 현재 연도 사용
                            "%m-%d %H:%M",
                        ]

                        for fmt in formats_to_try:
                            try:
                                parsed_dt = datetime.strptime(publish_time_str, fmt)
                                # 연도가 없는 형식이면 현재 연도 추가
                                if parsed_dt.year == 1900:
                                    parsed_dt = parsed_dt.replace(year=datetime.now().year)
                                break
                            except ValueError:
                                continue

                        if parsed_dt:
                            # UTC로 변환 (한국 시간은 UTC+9)
                            # 시트에 입력된 시간이 한국 시간이라고 가정
                            from datetime import timedelta
                            utc_dt = parsed_dt - timedelta(hours=9)
                            publish_at_iso = utc_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                        else:
                            print(f"[AUTOMATION] 예약시간 파싱 실패, 원본: {publish_time_str}")
                            publish_at_iso = None

                    if publish_at_iso:
                        upload_payload["publish_at"] = publish_at_iso
                        # 예약 업로드 시 privacyStatus는 API에서 자동으로 private로 설정됨
                        print(f"[AUTOMATION] 예약 업로드 설정: {publish_time_str} -> {publish_at_iso}")
                except Exception as parse_err:
                    print(f"[AUTOMATION] 예약시간 처리 오류: {parse_err}")

            upload_resp = req.post(f"{base_url}/api/youtube/upload", json=upload_payload, timeout=600)

            print(f"[AUTOMATION] YouTube 업로드 응답 상태: {upload_resp.status_code}")
            upload_data = upload_resp.json()
            print(f"[AUTOMATION] YouTube 업로드 응답: ok={upload_data.get('ok')}, videoUrl={upload_data.get('videoUrl', 'N/A')[:50] if upload_data.get('videoUrl') else 'N/A'}")

            if upload_data.get('ok'):
                youtube_url = upload_data.get('videoUrl', '')  # camelCase로 반환됨
                video_id = upload_data.get('videoId', '')
                print(f"[AUTOMATION] 4. 완료: {youtube_url} (총 비용: ${total_cost:.2f})")

                # ========== 5. 쇼츠 백그라운드 생성 (롱폼 먼저 반환) ==========
                # 롱폼이 더 중요하므로 먼저 결과를 반환하고, 쇼츠는 백그라운드에서 처리
                shorts_info = video_effects.get('shorts', {})
                highlight_scenes_nums = shorts_info.get('highlight_scenes', [])

                # highlight_scenes가 비어있으면 기본값으로 처음 2-3개 씬 선택
                if not highlight_scenes_nums or len(highlight_scenes_nums) == 0:
                    total_scenes_count = len(scenes) if scenes else 0
                    if total_scenes_count >= 3:
                        mid = total_scenes_count // 2
                        highlight_scenes_nums = [1, mid, total_scenes_count]
                    elif total_scenes_count >= 2:
                        highlight_scenes_nums = [1, total_scenes_count]
                    elif total_scenes_count == 1:
                        highlight_scenes_nums = [1]

                if highlight_scenes_nums and len(highlight_scenes_nums) > 0:
                    # 백그라운드 스레드에서 쇼츠 생성
                    def generate_shorts_background():
                        # FFmpeg 세마포어 획득 (다른 FFmpeg 작업과 동시 실행 방지)
                        print(f"[SHORTS-BG] FFmpeg 세마포어 대기 중...")
                        ffmpeg_semaphore.acquire()
                        print(f"[SHORTS-BG] FFmpeg 세마포어 획득, 쇼츠 생성 시작...")
                        try:
                            import requests as bg_req

                            # 하이라이트 나레이션 추출
                            highlight_narrations = []
                            for scene_num in highlight_scenes_nums:
                                if 1 <= scene_num <= len(scenes):
                                    narration = scenes[scene_num - 1].get('narration', '')
                                    if narration:
                                        clean_narration = re.sub(r'<[^>]+>', '', narration)
                                        highlight_narrations.append(clean_narration)

                            if not highlight_narrations:
                                print(f"[SHORTS-BG] 하이라이트 나레이션 없음, 스킵")
                                return

                            print(f"[SHORTS-BG] 하이라이트 나레이션 {len(highlight_narrations)}개 추출")

                            # GPT-5.1로 쇼츠 콘텐츠 분석
                            shorts_analysis = _analyze_shorts_content_gpt(
                                highlight_narrations=highlight_narrations,
                                title=title,
                                detected_category=detected_category,
                                audience=audience,
                                duration_target=45
                            )

                            if not shorts_analysis:
                                print(f"[SHORTS-BG] 쇼츠 분석 실패")
                                return

                            beats = shorts_analysis.get("structure", {}).get("beats", [])
                            print(f"[SHORTS-BG] 쇼츠 분석 완료: {len(beats)}개 beats")

                            # 쇼츠 제목 및 해시태그 추출
                            platform_info = shorts_analysis.get("platform_specific", {}).get("youtube_shorts", {})
                            shorts_title = platform_info.get("title_suggestion", "") or shorts_info.get('title', f"{title} #Shorts")
                            shorts_hashtags = platform_info.get("hashtags_hint", ["#Shorts", "#유튜브쇼츠"])

                            # 쇼츠 영상 생성
                            shorts_output_path = os.path.join("uploads", f"shorts_{session_id}.mp4")
                            shorts_result = _generate_shorts_video_v2(
                                shorts_analysis=shorts_analysis,
                                voice_name=voice,
                                output_path=shorts_output_path,
                                base_url=base_url
                            )

                            if not shorts_result.get("ok"):
                                print(f"[SHORTS-BG] 쇼츠 영상 생성 실패: {shorts_result.get('error')}")
                                return

                            shorts_duration = shorts_result.get("duration", 0)
                            print(f"[SHORTS-BG] 쇼츠 영상 생성 완료: {shorts_duration:.1f}초")

                            # 쇼츠 업로드
                            shorts_description = f"""🎬 전체 영상 보기: {youtube_url}

{description[:200]}...

{' '.join(shorts_hashtags)}"""

                            shorts_upload_payload = {
                                "videoPath": shorts_output_path,
                                "title": shorts_title,
                                "description": shorts_description,
                                "privacyStatus": visibility,
                                "channelId": channel_id
                            }

                            shorts_resp = bg_req.post(f"{base_url}/api/youtube/upload", json=shorts_upload_payload, timeout=300)
                            shorts_data = shorts_resp.json()

                            if shorts_data.get('ok'):
                                shorts_url = shorts_data.get('videoUrl', '')
                                print(f"[SHORTS-BG] 쇼츠 업로드 완료: {shorts_url}")

                                # Google Sheets Q열에 쇼츠 URL 업데이트
                                try:
                                    service = get_sheets_service_account()
                                    sheet_id = os.environ.get('AUTOMATION_SHEET_ID')
                                    if service and sheet_id:
                                        sheets_update_cell(service, sheet_id, f'Sheet1!Q{row_index}', shorts_url)
                                        print(f"[SHORTS-BG] Google Sheets Q{row_index}에 쇼츠 URL 기록 완료")
                                except Exception as sheets_err:
                                    print(f"[SHORTS-BG] Sheets 업데이트 실패: {sheets_err}")
                            else:
                                print(f"[SHORTS-BG] 쇼츠 업로드 실패: {shorts_data.get('error')}")

                        except Exception as bg_err:
                            print(f"[SHORTS-BG] 백그라운드 쇼츠 오류: {bg_err}")
                            import traceback
                            traceback.print_exc()
                        finally:
                            # 세마포어 해제 (다음 FFmpeg 작업 허용)
                            ffmpeg_semaphore.release()
                            print(f"[SHORTS-BG] FFmpeg 세마포어 해제됨")

                    # 백그라운드 스레드 시작
                    shorts_thread = threading.Thread(target=generate_shorts_background, daemon=True)
                    shorts_thread.start()
                    print(f"[AUTOMATION] 5. 쇼츠 생성 백그라운드 시작 (롱폼 먼저 반환)")

                # 롱폼 결과 즉시 반환 (쇼츠는 백그라운드에서 진행)
                return {
                    "ok": True,
                    "video_url": youtube_url,
                    "shorts_url": None,  # 백그라운드에서 처리 중
                    "error": None,
                    "cost": total_cost,
                    # 새로 추가: 제목 옵션 및 사용된 설정 정보
                    "title": title,
                    "title_options": title_options,
                    "voice": voice,
                    "audience": audience,
                    "detected_category": detected_category,
                    # 유튜브 메타데이터 추가
                    "hashtags": hashtags,
                    "tags": tags,
                    "pin_comment": pin_comment  # YouTube Studio에서 수동으로 고정 필요
                }
            else:
                return {"ok": False, "error": f"YouTube 업로드 실패: {upload_data.get('error')}", "video_url": None, "shorts_url": None, "cost": total_cost}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"ok": False, "error": f"YouTube 업로드 오류: {str(e)}", "video_url": None, "shorts_url": None, "cost": total_cost}

    except Exception as e:
        print(f"[AUTOMATION] 파이프라인 오류: {e}")
        import traceback
        traceback.print_exc()
        return {
            "ok": False,
            "error": str(e),
            "video_url": None,
            "cost": 0.0
        }


# ===== 레거시 자동화 함수들 (더 이상 사용하지 않음 - 참조용으로 유지) =====
# 아래 함수들은 run_automation_pipeline()에서 더 이상 호출하지 않습니다.
# 기존 /image 페이지 API를 재사용하도록 변경되었습니다.


def _automation_analyze_script_gpt5(script, episode_id):
    """대본 분석 - GPT-5.1 Responses API 사용"""
    try:
        from openai import OpenAI
        client = OpenAI()

        # 이미지 수 계산 (150자 = 1분 = 1장, 상한 없음)
        image_count = max(3, len(script) // 150)

        system_prompt = """You are an AI that analyzes scripts and generates image prompts for video production.

## CORE CONCEPT
The visual style is:
1. Background = DETAILED ANIME STYLE (slice-of-life anime, Ghibli-inspired, warm colors, soft lighting)
2. Character = SIMPLE WHITE STICKMAN (round head, TWO DOT EYES, small mouth, thin eyebrows, black outline body)

## Output Format (MUST be valid JSON)
{
    "youtube": {
        "title": "SEO-optimized YouTube title in Korean (click-inducing, 30-50 chars)",
        "description": "Description in Korean (summary + hashtags, 500+ chars)"
    },
    "thumbnail": {
        "text": "썸네일에 들어갈 강렬한 한국어 문구 (8-12자, 클릭 유도)",
        "text_color": "#FFD700",
        "outline_color": "#000000",
        "prompt": "Korean webtoon manhwa style YouTube thumbnail, 16:9 aspect ratio. Cartoon character with EXAGGERATED facial expression (shock, surprise, anger, crying). Clean vector illustration style, bold outlines, vibrant saturated colors, dramatic lighting. NO stickman, NO realistic photo. Style reference: Korean YouTube thumbnail illustration, webtoon art style."
    },
    "scenes": [
        {
            "scene_number": 1,
            "narration": "원본 대본의 정확한 문장 (요약 금지)",
            "image_prompt": "English prompt: detailed anime background, Ghibli-inspired, warm colors. Simple white stickman with round head, two black dot eyes, small mouth, thin eyebrows. [scene description]. NO realistic humans."
        }
    ]
}

## THUMBNAIL RULES (CRITICAL!)
Generate ONE powerful thumbnail that maximizes YouTube CTR (Click-Through Rate):
- Style: Korean webtoon/manhwa cartoon illustration (NOT stickman, NOT realistic photo)
- Character: Cartoon person with exaggerated facial expression (shock, surprise, anger, crying, frustration)
- Text should be 8-12 Korean characters, bold and impactful
- Examples: "결국 터졌다", "이게 실화?", "소름 돋았다", "절대 하지 마세요"
- Colors: Vibrant, saturated, high contrast (red, yellow, orange backgrounds work well)
- Composition: Character on one side, bold text on the other

## CRITICAL RULES
1. narration = 원본 대본의 정확한 문장을 그대로 복사. 요약하거나 줄이지 마세요!
2. image_prompt = 영어로 작성. 반드시 "detailed anime background" + "simple white stickman" 포함
3. NO realistic human faces - ONLY stickman character!"""

        user_prompt = f"""다음 대본을 분석하여 {image_count}개의 씬으로 나누세요.

대본:
{script}

IMPORTANT:
- 나레이션은 원본 대본을 그대로 사용 (요약 금지)
- image_prompt는 영어로, "detailed anime background" + "simple white stickman" 포함
- 반드시 JSON 형식으로만 응답"""

        print(f"[AUTOMATION] GPT-5.1 Responses API 호출 중...")

        # GPT-5.1은 Responses API 사용
        response = client.responses.create(
            model="gpt-5.1",
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": system_prompt
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_prompt
                        }
                    ]
                }
            ],
            temperature=0.7
        )

        print(f"[AUTOMATION] GPT-5.1 응답 완료")

        # Responses API 결과 추출
        if getattr(response, "output_text", None):
            result_text = response.output_text.strip()
        else:
            text_chunks = []
            for item in getattr(response, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    if getattr(content, "type", "") == "text":
                        text_chunks.append(getattr(content, "text", ""))
            result_text = "\n".join(text_chunks).strip()

        # JSON 파싱 (마크다운 코드블록 제거)
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()

        # Trailing comma 제거 (LLM이 자주 실수하는 패턴)
        import re
        result_text = re.sub(r',\s*\]', ']', result_text)
        result_text = re.sub(r',\s*\}', '}', result_text)

        result = json.loads(result_text)
        return {
            "ok": True,
            "youtube": result.get("youtube", {}),
            "thumbnail": result.get("thumbnail", {}),
            "scenes": result.get("scenes", [])
        }

    except Exception as e:
        print(f"[AUTOMATION] 대본 분석 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


def _automation_generate_all_images(scenes, episode_id, output_dir):
    """모든 씬 이미지 병렬 생성 - Gemini 2.5 Flash via OpenRouter"""
    import time as time_module

    try:
        image_paths = []

        for i, scene in enumerate(scenes):
            prompt = scene.get('image_prompt', '')
            if not prompt:
                image_paths.append(None)
                continue

            print(f"[AUTOMATION] 이미지 생성 {i+1}/{len(scenes)}")
            image_result = _automation_generate_image(prompt, episode_id, i)

            if image_result.get('ok'):
                image_paths.append(image_result.get('image_path'))
            else:
                print(f"[AUTOMATION] 이미지 생성 실패 {i+1}: {image_result.get('error')}")
                image_paths.append(None)

            time_module.sleep(1)  # API 부하 방지

        return {"ok": True, "image_paths": image_paths}

    except Exception as e:
        print(f"[AUTOMATION] 이미지 생성 전체 오류: {e}")
        return {"ok": False, "error": str(e), "image_paths": []}


def _automation_generate_tts_neural2(scenes, episode_id, uploads_dir):
    """TTS 생성 - Google Cloud TTS Neural2 직접 호출"""
    import requests
    import base64
    import subprocess
    import tempfile

    try:
        api_key = os.getenv("GOOGLE_CLOUD_API_KEY", "")
        if not api_key:
            return {"ok": False, "error": "GOOGLE_CLOUD_API_KEY가 설정되지 않았습니다"}

        voice_name = "ko-KR-Neural2-C"  # 남성 Neural2 음성 (고품질)
        language_code = "ko-KR"

        audio_data = []

        for i, scene in enumerate(scenes):
            narration = scene.get('narration', '')
            if not narration:
                audio_data.append(None)
                continue

            print(f"[AUTOMATION] TTS 생성 {i+1}/{len(scenes)}: {narration[:30]}...")

            # Google TTS API 호출
            tts_url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
            payload = {
                "input": {"text": narration},
                "voice": {"languageCode": language_code, "name": voice_name},
                "audioConfig": {"audioEncoding": "MP3", "speakingRate": 0.95, "pitch": 0}
            }

            response = requests.post(tts_url, json=payload, timeout=60)

            if response.status_code != 200:
                print(f"[AUTOMATION] TTS API 오류 {i+1}: {response.status_code}")
                audio_data.append(None)
                continue

            result = response.json()
            audio_content = result.get("audioContent", "")

            if not audio_content:
                audio_data.append(None)
                continue

            # MP3 파일 저장
            audio_bytes = base64.b64decode(audio_content)
            audio_filename = f"{episode_id}_scene_{i+1}.mp3"
            audio_path = os.path.join(uploads_dir, audio_filename)

            with open(audio_path, 'wb') as f:
                f.write(audio_bytes)

            # 오디오 길이 측정
            duration = 5.0  # 기본값
            try:
                probe_cmd = [
                    'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1', audio_path
                ]
                result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
                if result.stdout.strip():
                    duration = float(result.stdout.strip())
            except Exception as e:
                print(f"[AUTOMATION] 오디오 길이 측정 실패 {i+1}: {e}")

            audio_data.append({
                "path": audio_path,
                "url": f"/uploads/{audio_filename}",
                "duration": duration
            })

            print(f"[AUTOMATION] TTS 완료 {i+1}: {duration:.1f}초")

        return {"ok": True, "audio_data": audio_data}

    except Exception as e:
        print(f"[AUTOMATION] TTS 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


def _automation_generate_thumbnail(thumbnail_data, episode_id, output_dir):
    """썸네일 이미지 생성 - OpenRouter Gemini 사용"""
    try:
        import requests as req
        import base64

        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not openrouter_api_key:
            return {"ok": False, "error": "OPENROUTER_API_KEY 없음"}

        prompt = thumbnail_data.get('prompt', '')
        if not prompt:
            return {"ok": False, "error": "썸네일 프롬프트 없음"}

        print(f"[AUTOMATION] 썸네일 생성 시작...")

        headers = {
            "Authorization": f"Bearer {openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://drama-generator.app",
            "X-Title": "Drama Automation Thumbnail"
        }

        payload = {
            "model": "google/gemini-2.5-flash-image-preview",
            "modalities": ["text", "image"],
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        }

        response = req.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=120
        )

        if response.status_code != 200:
            return {"ok": False, "error": f"API 오류: {response.status_code}"}

        result = response.json()
        choices = result.get("choices", [])
        if not choices:
            return {"ok": False, "error": "응답에 choices 없음"}

        message = choices[0].get("message", {})

        # 이미지 추출
        images = message.get("images", [])
        base64_data = None

        if images:
            for img in images:
                if isinstance(img, str):
                    if img.startswith("data:"):
                        base64_data = img.split(",", 1)[1] if "," in img else img
                    else:
                        base64_data = img
                elif isinstance(img, dict):
                    if img.get("type") == "image_url":
                        url = img.get("image_url", {}).get("url", "")
                        if url.startswith("data:"):
                            base64_data = url.split(",", 1)[1] if "," in url else url
                if base64_data:
                    break

        if not base64_data:
            # content에서 찾기
            content = message.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "image":
                        base64_data = item.get("data", "")
                        if base64_data:
                            break

        if not base64_data:
            return {"ok": False, "error": "이미지 데이터 없음"}

        # 파일 저장
        image_bytes = base64.b64decode(base64_data)
        filename = f"thumbnail_{episode_id}.png"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'wb') as f:
            f.write(image_bytes)

        print(f"[AUTOMATION] 썸네일 생성 완료: {filepath}")
        return {"ok": True, "path": filepath}

    except Exception as e:
        print(f"[AUTOMATION] 썸네일 생성 오류: {e}")
        return {"ok": False, "error": str(e)}


def _automation_generate_image(prompt, episode_id, scene_index):
    """이미지 생성 - OpenRouter Gemini 사용"""
    try:
        import requests as req

        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not openrouter_api_key:
            return {"ok": False, "error": "OPENROUTER_API_KEY 없음"}

        # 프롬프트 강화
        enhanced_prompt = f"""CRITICAL: Generate image in 16:9 WIDESCREEN LANDSCAPE aspect ratio (1280x720).

{prompt}

Style: Korean webtoon/manhwa illustration style. Clean vector-like artwork with bold outlines.
Character: Cartoon/webtoon style character with EXAGGERATED facial expressions. Simple but expressive features.
Colors: Vibrant, saturated colors with dramatic lighting.
NO realistic humans, NO photorealistic style. Webtoon art style only."""

        headers = {
            "Authorization": f"Bearer {openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://drama-generator.app",
            "X-Title": "Drama Automation"
        }

        payload = {
            "model": "google/gemini-2.5-flash-image-preview",
            "modalities": ["text", "image"],
            "messages": [{"role": "user", "content": [{"type": "text", "text": enhanced_prompt}]}]
        }

        print(f"[AUTOMATION] OpenRouter API 호출 중... (scene {scene_index + 1})")

        # 재시도 로직 (최대 3회)
        import time as time_module
        max_retries = 3
        retry_delay = 3
        response = None
        last_error = None

        for attempt in range(max_retries):
            try:
                response = req.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120
                )

                if response.status_code == 200:
                    break
                elif response.status_code in [429, 502, 503, 504]:
                    last_error = f"HTTP {response.status_code}"
                    print(f"[AUTOMATION] 재시도 {attempt + 1}/{max_retries}: {last_error}")
                    time_module.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    break

            except req.exceptions.Timeout:
                last_error = "타임아웃"
                print(f"[AUTOMATION] 재시도 {attempt + 1}/{max_retries}: {last_error}")
                time_module.sleep(retry_delay)
                continue
            except Exception as e:
                last_error = str(e)
                print(f"[AUTOMATION] 재시도 {attempt + 1}/{max_retries}: {last_error}")
                time_module.sleep(retry_delay)
                continue

        if response is None:
            return {"ok": False, "error": f"API 호출 실패: {last_error}"}

        print(f"[AUTOMATION] OpenRouter 응답: {response.status_code}")

        if response.status_code != 200:
            error_text = response.text[:500] if response.text else "No response body"
            print(f"[AUTOMATION] OpenRouter 에러: {error_text}")
            return {"ok": False, "error": f"API 오류: {response.status_code} - {error_text[:100]}"}

        result = response.json()
        print(f"[AUTOMATION] OpenRouter 결과 키: {list(result.keys())}")
        print(f"[AUTOMATION] 전체 응답 (500자): {json.dumps(result, ensure_ascii=False)[:500]}")

        # 에러 체크
        if result.get("error"):
            error_msg = result.get("error", {})
            print(f"[AUTOMATION] OpenRouter API 에러: {error_msg}")
            return {"ok": False, "error": f"API 에러: {error_msg}"}

        # 이미지 추출
        choices = result.get("choices", [])
        if not choices:
            print(f"[AUTOMATION] choices가 비어있음. 전체 응답: {str(result)[:500]}")
            return {"ok": False, "error": "응답에 choices 없음"}

        message = choices[0].get("message", {})

        # 1. images 배열 먼저 확인 (OpenRouter 표준 형식)
        images = message.get("images", [])
        if images:
            print(f"[AUTOMATION] images 배열 발견: {len(images)}개")
            for img in images:
                base64_data = None

                if isinstance(img, str):
                    # 문자열 형식
                    if img.startswith("data:"):
                        base64_data = img.split(",", 1)[1] if "," in img else img
                    else:
                        base64_data = img

                elif isinstance(img, dict):
                    # 딕셔너리 형식: {"type": "image_url", "image_url": {"url": "data:..."}}
                    if img.get("type") == "image_url":
                        url = img.get("image_url", {}).get("url", "")
                        if url.startswith("data:"):
                            base64_data = url.split(",", 1)[1] if "," in url else url
                        print(f"[AUTOMATION] image_url 형식에서 base64 추출 성공")
                    elif "url" in img:
                        url = img.get("url", "")
                        if url.startswith("data:"):
                            base64_data = url.split(",", 1)[1] if "," in url else url
                    elif "data" in img:
                        base64_data = img.get("data")
                    elif "b64_json" in img:
                        base64_data = img.get("b64_json")

                if base64_data:
                    # 이미지 저장
                    output_dir = os.path.join(os.path.dirname(__file__), 'outputs')
                    os.makedirs(output_dir, exist_ok=True)
                    filename = f"{episode_id}_scene_{scene_index}.png"
                    filepath = os.path.join(output_dir, filename)

                    import base64
                    with open(filepath, 'wb') as f:
                        f.write(base64.b64decode(base64_data))

                    print(f"[AUTOMATION] 이미지 저장 완료: {filepath}")
                    return {
                        "ok": True,
                        "image_url": f"/output/{filename}",
                        "image_path": filepath
                    }

        # 2. content 확인
        content = message.get("content", [])
        print(f"[AUTOMATION] content 타입: {type(content)}, 길이: {len(content) if isinstance(content, list) else 'N/A'}")

        # content가 문자열인 경우 (텍스트만 반환된 경우)
        if isinstance(content, str):
            print(f"[AUTOMATION] content가 문자열임 (이미지 없음): {content[:200]}")
            return {"ok": False, "error": "이미지 대신 텍스트 응답"}

        for item in content:
            if isinstance(item, dict):
                item_type = item.get("type", "unknown")
                print(f"[AUTOMATION] content item type: {item_type}")
                if item_type == "image_url":
                    image_data = item.get("image_url", {})
                    url = image_data.get("url", "")
                    if url.startswith("data:image"):
                        # Base64 이미지 저장
                        output_dir = os.path.join(os.path.dirname(__file__), 'outputs')
                        os.makedirs(output_dir, exist_ok=True)

                        filename = f"{episode_id}_scene_{scene_index}.png"
                        filepath = os.path.join(output_dir, filename)

                        header, encoded = url.split(',', 1)
                        import base64
                        with open(filepath, 'wb') as f:
                            f.write(base64.b64decode(encoded))

                        print(f"[AUTOMATION] 이미지 저장 완료: {filepath}")
                        return {
                            "ok": True,
                            "image_url": f"/output/{filename}",
                            "image_path": filepath
                        }

        print(f"[AUTOMATION] 이미지를 찾지 못함. content: {str(content)[:300]}")
        return {"ok": False, "error": "응답에서 이미지를 찾지 못함"}

    except Exception as e:
        print(f"[AUTOMATION] 이미지 생성 오류: {e}")
        return {"ok": False, "error": str(e)}


def _automation_generate_video(scenes, episode_id, output_dir):
    """영상 생성 - FFmpeg로 이미지 + 오디오 + 자막 결합"""
    import subprocess
    import tempfile
    import re
    import gc  # 메모리 정리용

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            clip_paths = []

            # 전체 자막 데이터 수집 (전체 영상용)
            all_subtitles = []
            current_time = 0.0

            for i, scene in enumerate(scenes):
                image_path = scene.get('image_path')
                audio_path = scene.get('audio_path', '')
                narration = scene.get('narration', '')

                if not image_path or not os.path.exists(image_path):
                    print(f"[AUTOMATION] 씬 {i+1} 스킵 - 이미지 없음: {image_path}")
                    continue

                if not audio_path or not os.path.exists(audio_path):
                    print(f"[AUTOMATION] 씬 {i+1} 스킵 - 오디오 없음: {audio_path}")
                    continue

                duration = scene.get('duration', 5.0)

                # 자막 타이밍 추가
                if narration:
                    all_subtitles.append({
                        'start': current_time,
                        'end': current_time + duration - 0.2,
                        'text': narration
                    })
                current_time += duration

                # 씬 클립 생성 (자막은 나중에 전체 영상에 합성)
                clip_path = os.path.join(temp_dir, f"clip_{i}.mp4")
                ffmpeg_cmd = [
                    'ffmpeg', '-y',
                    '-loop', '1', '-i', image_path,
                    '-i', audio_path,
                    '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                    '-c:a', 'aac', '-b:a', '128k',
                    '-r', '24', '-t', str(duration), '-shortest',
                    '-pix_fmt', 'yuv420p',
                    clip_path
                ]

                print(f"[AUTOMATION] 클립 생성 중 {i+1}/{len(scenes)}: {duration:.1f}초")
                clip_timeout = max(180, int(duration) + 60)
                # 메모리 최적화: stdout/stderr DEVNULL (OOM 방지)
                clip_result = subprocess.run(
                    ffmpeg_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=clip_timeout
                )
                del clip_result
                gc.collect()

                if os.path.exists(clip_path):
                    clip_paths.append(clip_path)
                    print(f"[AUTOMATION] 클립 생성 완료: {clip_path}")

            if not clip_paths:
                return {"ok": False, "error": "생성된 클립이 없습니다"}

            # 클립 병합 (자막 없이)
            concat_file = os.path.join(temp_dir, "concat.txt")
            with open(concat_file, 'w') as f:
                for clip_path in clip_paths:
                    f.write(f"file '{clip_path}'\n")

            merged_video = os.path.join(temp_dir, "merged.mp4")
            concat_cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                '-i', concat_file,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-c:a', 'aac', '-b:a', '192k',
                merged_video
            ]

            print(f"[AUTOMATION] 클립 병합 중... ({len(clip_paths)}개 클립)")
            # 메모리 최적화: stdout/stderr DEVNULL (OOM 방지)
            concat_result = subprocess.run(
                concat_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=300
            )
            del concat_result
            gc.collect()

            if not os.path.exists(merged_video):
                return {"ok": False, "error": "클립 병합 실패"}

            final_video = os.path.join(output_dir, f"{episode_id}_final.mp4")

            # 자막이 있으면 하드코딩
            if all_subtitles:
                print(f"[AUTOMATION] 자막 하드코딩 중... ({len(all_subtitles)}개 자막)")

                # SRT 형식 생성
                def format_srt_time(seconds):
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = int(seconds % 60)
                    millis = int((seconds - int(seconds)) * 1000)
                    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

                srt_path = os.path.join(temp_dir, "subtitles.srt")
                with open(srt_path, 'w', encoding='utf-8') as f:
                    for i, sub in enumerate(all_subtitles, 1):
                        f.write(f"{i}\n")
                        f.write(f"{format_srt_time(sub['start'])} --> {format_srt_time(sub['end'])}\n")
                        f.write(f"{sub['text']}\n\n")

                # 자막 스타일 (한글 최적화)
                subtitle_style = "FontName=NanumGothic,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=1,MarginV=30"

                # FFmpeg 자막 필터
                escaped_srt = srt_path.replace('\\', '\\\\').replace(':', '\\:')
                vf_filter = f"subtitles={escaped_srt}:force_style='{subtitle_style}'"

                subtitle_cmd = [
                    'ffmpeg', '-y',
                    '-i', merged_video,
                    '-vf', vf_filter,
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                    '-c:a', 'copy',
                    final_video
                ]

                # 메모리 최적화: stdout DEVNULL, stderr만 PIPE (OOM 방지)
                result = subprocess.run(
                    subtitle_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=600
                )
                if result.returncode != 0:
                    stderr_msg = result.stderr[:500].decode('utf-8', errors='ignore') if result.stderr else '(stderr 없음)'
                    print(f"[AUTOMATION] 자막 하드코딩 실패: {stderr_msg}")
                    del result
                    gc.collect()
                    # 자막 실패시 병합 영상 사용
                    import shutil
                    shutil.copy(merged_video, final_video)
                else:
                    del result
                    gc.collect()
            else:
                # 자막 없으면 병합 영상 그대로 사용
                import shutil
                shutil.copy(merged_video, final_video)

            if os.path.exists(final_video):
                print(f"[AUTOMATION] 최종 영상 생성 완료: {final_video}")
                return {"ok": True, "video_path": final_video}
            else:
                return {"ok": False, "error": "최종 영상 생성 실패"}

    except Exception as e:
        print(f"[AUTOMATION] 영상 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


def _automation_youtube_upload(video_path, title, description, visibility, channel_id, thumbnail_path=None, tags=None):
    """YouTube 업로드 (썸네일 포함, GPT-5.1 생성 태그 지원)"""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        if not os.path.exists(video_path):
            return {"ok": False, "error": f"영상 파일 없음: {video_path}"}

        # DB에서 토큰 로드
        token_data = load_youtube_token_from_db(channel_id) if channel_id else load_youtube_token_from_db()

        if not token_data or not token_data.get('refresh_token'):
            return {"ok": False, "error": "YouTube 인증이 필요합니다"}

        # Credentials 생성
        creds = Credentials(
            token=token_data.get('token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=token_data.get('client_id') or os.getenv('YOUTUBE_CLIENT_ID'),
            client_secret=token_data.get('client_secret') or os.getenv('YOUTUBE_CLIENT_SECRET'),
            scopes=token_data.get('scopes', ['https://www.googleapis.com/auth/youtube.upload'])
        )

        # 토큰 갱신
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            updated_token = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': list(creds.scopes) if creds.scopes else []
            }
            save_youtube_token_to_db(updated_token, channel_id=channel_id)

        youtube = build('youtube', 'v3', credentials=creds)

        # 태그: GPT-5.1 생성 태그 사용, 없으면 기본 태그
        youtube_tags = tags if tags and len(tags) > 0 else ['자동생성', '드라마', 'AI']
        # YouTube 태그 제한: 최대 500자, 각 태그 30자 이하
        youtube_tags = [tag[:30] for tag in youtube_tags[:20]]

        body = {
            'snippet': {
                'title': title[:100],
                'description': description[:5000] if description else '',
                'tags': youtube_tags,
                'categoryId': '22'
            },
            'status': {
                'privacyStatus': visibility or 'private',
                'selfDeclaredMadeForKids': False
            }
        }

        media = MediaFileUpload(video_path, chunksize=1024*1024, resumable=True, mimetype='video/mp4')

        request = youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[AUTOMATION] 업로드 진행: {int(status.progress() * 100)}%")

        video_id = response.get('id')
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        print(f"[AUTOMATION] YouTube 업로드 완료: {video_url}")

        # 썸네일 업로드
        thumbnail_uploaded = False
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                print(f"[AUTOMATION] 썸네일 업로드 시작: {thumbnail_path}")
                thumb_request = youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype='image/png')
                )
                thumb_request.execute()
                thumbnail_uploaded = True
                print(f"[AUTOMATION] 썸네일 업로드 완료!")
            except Exception as thumb_error:
                print(f"[AUTOMATION] 썸네일 업로드 실패: {thumb_error}")
                # 썸네일 실패해도 영상 업로드는 성공한 것으로 처리

        return {
            "ok": True,
            "video_url": video_url,
            "video_id": video_id,
            "thumbnail_uploaded": thumbnail_uploaded
        }

    except Exception as e:
        print(f"[AUTOMATION] YouTube 업로드 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


@app.route('/api/sheets/auth-status', methods=['GET'])
def api_sheets_auth_status():
    """Google Sheets 서비스 계정 인증 상태 확인"""
    try:
        service = get_sheets_service_account()
        if service:
            # AUTOMATION_SHEET_ID 확인
            sheet_id = os.environ.get('AUTOMATION_SHEET_ID')
            return jsonify({
                "ok": True,
                "authenticated": True,
                "sheet_id_configured": bool(sheet_id),
                "message": "서비스 계정 인증 완료"
            })
        else:
            return jsonify({
                "ok": True,
                "authenticated": False,
                "sheet_id_configured": False,
                "message": "GOOGLE_SERVICE_ACCOUNT_JSON 환경변수를 설정해주세요"
            })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/sheets/check-and-process', methods=['POST'])
def api_sheets_check_and_process():
    """
    Google Sheets에서 '대기' 상태인 행을 찾아 처리
    Render Cron Job에서 5분마다 호출

    시트 구조:
    A: 상태 (대기/처리중/완료/실패)
    B: 예약시간 (2025-12-07 09:00)
    C: 채널ID
    D: 대본
    E: 제목 (선택)
    F: 공개설정 (private/unlisted/public)
    G: 영상URL (자동 입력 - 출력)
    H: 에러메시지 (자동 입력 - 출력)
    I: 음성 (선택, 기본: ko-KR-Neural2-C 남성)
       - 여성: ko-KR-Neural2-A
       - 남성: ko-KR-Neural2-C
    J: 타겟 (선택, 기본: senior)
       - senior: 시니어 (50-70대)
       - general: 일반 (20-40대)
    """
    try:
        # 서비스 계정 인증
        service = get_sheets_service_account()
        if not service:
            return jsonify({
                "ok": False,
                "error": "Google Sheets 서비스 계정이 설정되지 않았습니다"
            }), 400

        # 시트 ID
        sheet_id = os.environ.get('AUTOMATION_SHEET_ID')
        if not sheet_id:
            return jsonify({
                "ok": False,
                "error": "AUTOMATION_SHEET_ID 환경변수가 설정되지 않았습니다"
            }), 400

        # 시트 데이터 읽기 (A:M까지 - 비용, 채널명, 타겟 컬럼 포함)
        rows = sheets_read_rows(service, sheet_id, 'Sheet1!A:M')
        if not rows:
            return jsonify({
                "ok": True,
                "message": "시트가 비어있거나 읽기 실패",
                "processed": 0
            })

        # 현재 시간 (한국 시간 KST = UTC+9)
        from datetime import datetime, timedelta, timezone
        kst = timezone(timedelta(hours=9))
        now = datetime.now(kst).replace(tzinfo=None)  # naive datetime으로 변환 (시트의 작업시간과 비교용)
        processed_count = 0
        results = []

        # ========== 처리중인 작업이 있는지 확인 (40분 타임아웃) ==========
        # "처리중"인 행이 있으면 새 작업을 시작하지 않음 (한 번에 하나씩만 처리)
        # 단, 40분 이상 처리중이거나 시작시간이 없으면 실패로 변경
        # (10분 영상에 ~20분 소요되므로 여유있게 40분)
        for i, row in enumerate(rows[1:], start=2):
            if len(row) > 0 and row[0] == '처리중':
                work_time = row[1] if len(row) > 1 else ''

                # 처리 시작 시간 확인 (B열)
                if work_time:
                    try:
                        work_dt = datetime.strptime(work_time, '%Y-%m-%d %H:%M:%S')
                        elapsed_minutes = (now - work_dt).total_seconds() / 60

                        if elapsed_minutes > 40:
                            # 40분 초과 → 실패로 변경
                            print(f"[SHEETS] 행 {i}: 처리중 상태 {elapsed_minutes:.1f}분 경과 - 타임아웃으로 실패 처리")
                            sheets_update_cell(service, sheet_id, f'Sheet1!A{i}', '실패')
                            sheets_update_cell(service, sheet_id, f'Sheet1!M{i}', f'타임아웃: {elapsed_minutes:.0f}분 경과')
                            continue  # 다음 행 확인
                        else:
                            print(f"[SHEETS] 처리중인 작업 발견 (행 {i}, {elapsed_minutes:.1f}분 경과) - 새 작업 시작 안함")
                    except ValueError:
                        # 시간 형식 파싱 실패 → 실패로 처리
                        print(f"[SHEETS] 행 {i}: 시작시간 형식 오류 - 실패 처리")
                        sheets_update_cell(service, sheet_id, f'Sheet1!A{i}', '실패')
                        sheets_update_cell(service, sheet_id, f'Sheet1!M{i}', '시작시간 형식 오류로 실패')
                        continue  # 다음 행 확인
                else:
                    # 시작시간 없음 → 실패로 처리 (배포 전 작업 등)
                    print(f"[SHEETS] 행 {i}: 시작시간 없음 - 실패 처리")
                    sheets_update_cell(service, sheet_id, f'Sheet1!A{i}', '실패')
                    sheets_update_cell(service, sheet_id, f'Sheet1!M{i}', '시작시간 없음 (서버 재시작)')
                    continue  # 다음 행 확인

                return jsonify({
                    "ok": True,
                    "message": f"행 {i}에서 처리중인 작업이 있어 대기합니다",
                    "processing_row": i,
                    "processed": 0
                })

        # ========== 대기 중인 첫 번째 행만 처리 ==========
        # 행 순회 (첫 번째 행은 헤더로 가정)
        for i, row in enumerate(rows[1:], start=2):  # 2부터 시작 (1-based, 헤더 제외)
            if len(row) < 1:
                continue

            status = row[0] if len(row) > 0 else ''
            work_time = row[1] if len(row) > 1 else ''  # B열: 작업시간 (파이프라인 실행 시점)

            # '대기' 상태이고 작업시간이 지났으면 처리
            if status == '대기':
                # 작업시간 파싱
                should_process = False
                if work_time:
                    try:
                        work_dt = datetime.strptime(work_time, '%Y-%m-%d %H:%M')
                        if now >= work_dt:
                            should_process = True
                    except ValueError:
                        # 작업시간 형식이 잘못되면 즉시 처리
                        should_process = True
                else:
                    # 작업시간이 없으면 즉시 처리
                    should_process = True

                if should_process:
                    print(f"[SHEETS] 처리 시작 - 행 {i}")

                    # 상태를 '처리중'으로 변경 + 시작 시간 기록 (B열)
                    sheets_update_cell(service, sheet_id, f'Sheet1!A{i}', '처리중')
                    sheets_update_cell(service, sheet_id, f'Sheet1!B{i}', now.strftime('%Y-%m-%d %H:%M:%S'))

                    # 파이프라인 실행
                    result = run_automation_pipeline(row, i)

                    # ========== 새로운 컬럼 구조 (H,I 제목 추가로 2칸 밀림) ==========
                    # G: 제목(메인), H: 제목2(대안1), I: 제목3(대안2)
                    # J: 비용, K: 공개설정, L: 영상URL, M: 에러메시지
                    # N: 음성, O: 타겟, P: 카테고리, Q: 쇼츠URL

                    # 비용 기록 (J열) - 성공/실패 모두
                    cost = result.get('cost', 0.0)
                    sheets_update_cell(service, sheet_id, f'Sheet1!J{i}', f'${cost:.2f}')

                    # 제목 기록 (G, H, I열) - GPT가 생성한 3가지 스타일 제목
                    if result.get('title'):
                        sheets_update_cell(service, sheet_id, f'Sheet1!G{i}', result['title'])
                    title_options = result.get('title_options', [])
                    if len(title_options) >= 1:
                        sheets_update_cell(service, sheet_id, f'Sheet1!H{i}', title_options[0].get('title', ''))
                    if len(title_options) >= 2:
                        sheets_update_cell(service, sheet_id, f'Sheet1!I{i}', title_options[1].get('title', ''))

                    # 사용된 설정 정보 기록 (N, O, P열)
                    if result.get('voice'):
                        sheets_update_cell(service, sheet_id, f'Sheet1!N{i}', result['voice'])
                    if result.get('audience'):
                        sheets_update_cell(service, sheet_id, f'Sheet1!O{i}', result['audience'])
                    if result.get('detected_category'):
                        sheets_update_cell(service, sheet_id, f'Sheet1!P{i}', result['detected_category'])

                    if result.get('ok'):
                        # 성공 - 상태: 완료, 영상URL 기록 (L열), 쇼츠URL 기록 (Q열)
                        sheets_update_cell(service, sheet_id, f'Sheet1!A{i}', '완료')
                        if result.get('video_url'):
                            sheets_update_cell(service, sheet_id, f'Sheet1!L{i}', result['video_url'])
                        if result.get('shorts_url'):
                            sheets_update_cell(service, sheet_id, f'Sheet1!Q{i}', result['shorts_url'])
                    else:
                        # 실패 - 상태: 실패, 에러메시지 기록 (M열)
                        sheets_update_cell(service, sheet_id, f'Sheet1!A{i}', '실패')
                        error_msg = result.get('error', '알 수 없는 오류')[:500]  # 최대 500자
                        sheets_update_cell(service, sheet_id, f'Sheet1!M{i}', error_msg)

                    processed_count += 1
                    results.append({
                        "row": i,
                        "ok": result.get('ok'),
                        "error": result.get('error')
                    })

                    # ★ 한 번에 하나만 처리하고 종료
                    break

        return jsonify({
            "ok": True,
            "message": f"{processed_count}개 행 처리 완료",
            "processed": processed_count,
            "results": results
        })

    except Exception as e:
        print(f"[SHEETS] check-and-process 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/sheets/read', methods=['GET'])
def api_sheets_read():
    """Google Sheets 데이터 읽기 (디버깅용)"""
    try:
        service = get_sheets_service_account()
        if not service:
            return jsonify({"ok": False, "error": "서비스 계정 미설정"}), 400

        sheet_id = os.environ.get('AUTOMATION_SHEET_ID')
        if not sheet_id:
            return jsonify({"ok": False, "error": "AUTOMATION_SHEET_ID 미설정"}), 400

        range_name = request.args.get('range', 'Sheet1!A:H')
        rows = sheets_read_rows(service, sheet_id, range_name)

        return jsonify({
            "ok": True,
            "rows": rows,
            "count": len(rows)
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/sheets/update', methods=['POST'])
def api_sheets_update():
    """Google Sheets 셀 업데이트 (디버깅용)"""
    try:
        service = get_sheets_service_account()
        if not service:
            return jsonify({"ok": False, "error": "서비스 계정 미설정"}), 400

        sheet_id = os.environ.get('AUTOMATION_SHEET_ID')
        if not sheet_id:
            return jsonify({"ok": False, "error": "AUTOMATION_SHEET_ID 미설정"}), 400

        data = request.get_json() or {}
        cell_range = data.get('range')  # 예: 'Sheet1!A2'
        value = data.get('value')

        if not cell_range or value is None:
            return jsonify({"ok": False, "error": "range와 value 필수"}), 400

        success = sheets_update_cell(service, sheet_id, cell_range, value)

        return jsonify({
            "ok": success,
            "message": "업데이트 완료" if success else "업데이트 실패"
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== Render 배포를 위한 설정 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5059))
    app.run(host="0.0.0.0", port=port, debug=False)
