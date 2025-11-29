import os
import re
import json
import sqlite3
import threading
import queue
import uuid
import tempfile
from datetime import datetime as dt
from flask import Flask, render_template, request, jsonify, send_file
from openai import OpenAI

app = Flask(__name__)

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
def save_youtube_token_to_db(token_data, user_id='default'):
    """YouTube 토큰을 데이터베이스에 저장"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                INSERT INTO youtube_tokens (user_id, token, refresh_token, token_uri, client_id, client_secret, scopes, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET
                    token = EXCLUDED.token,
                    refresh_token = EXCLUDED.refresh_token,
                    token_uri = EXCLUDED.token_uri,
                    client_id = EXCLUDED.client_id,
                    client_secret = EXCLUDED.client_secret,
                    scopes = EXCLUDED.scopes,
                    updated_at = CURRENT_TIMESTAMP
            ''', (
                user_id,
                token_data.get('token'),
                token_data.get('refresh_token'),
                token_data.get('token_uri'),
                token_data.get('client_id'),
                token_data.get('client_secret'),
                ','.join(token_data.get('scopes', []))
            ))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO youtube_tokens (user_id, token, refresh_token, token_uri, client_id, client_secret, scopes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (
                user_id,
                token_data.get('token'),
                token_data.get('refresh_token'),
                token_data.get('token_uri'),
                token_data.get('client_id'),
                token_data.get('client_secret'),
                ','.join(token_data.get('scopes', []))
            ))

        conn.commit()
        conn.close()
        print(f"[YOUTUBE-TOKEN] 데이터베이스에 저장 완료 (user_id: {user_id})")
        return True
    except Exception as e:
        print(f"[YOUTUBE-TOKEN] 데이터베이스 저장 실패: {e}")
        return False


def load_youtube_token_from_db(user_id='default'):
    """YouTube 토큰을 데이터베이스에서 로드"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('SELECT * FROM youtube_tokens WHERE user_id = %s', (user_id,))
        else:
            cursor.execute('SELECT * FROM youtube_tokens WHERE user_id = ?', (user_id,))

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
            print(f"[YOUTUBE-TOKEN] 데이터베이스에서 로드 완료 (user_id: {user_id})")
            return token_data
        else:
            print(f"[YOUTUBE-TOKEN] 데이터베이스에 토큰 없음 (user_id: {user_id})")
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
                save_youtube_token_to_db(token_data, user_id)
                return token_data
            except Exception as file_error:
                print(f"[YOUTUBE-TOKEN] 레거시 파일 로드도 실패: {file_error}")
        return None

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

    conn.commit()
    cursor.close()
    conn.close()
    print("[DRAMA-DB] Database initialized (including youtube_tokens)")

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
    return render_template("drama.html")

@app.route("/drama")
def drama():
    return render_template("drama.html")

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
            temperature=0.8
        )

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

        if not script:
            return jsonify({"ok": False, "error": "대본이 없습니다."}), 400

        print(f"[DRAMA-STEP4-ANALYZE] 등장인물 및 씬 분석 시작")

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
- 프롬프트는 DALL-E 3에 최적화되도록 상세하게 작성
- 인물 프롬프트는 portrait 스타일에 적합하게 작성
- 한국 드라마 스타일의 시각적 요소 반영

🚨 매우 중요 - 한국인 외모 필수 요구사항 (반드시 프롬프트 맨 앞에 배치):

- ⚠️ 한국인 할머니 (halmeoni):
  "Authentic Korean grandmother (halmeoni) from South Korea, pure Korean ethnicity, distinct Korean elderly facial features: round face shape, single eyelids (monolid) or narrow double eyelids typical of Korean elderly, flat nose bridge, Korean skin tone (light to medium beige with warm undertones), natural Korean aging patterns with laugh lines, permed short gray/white hair typical of Korean grandmothers"

- ⚠️ 한국인 할아버지 (harabeoji):
  "Authentic Korean grandfather (harabeoji) from South Korea, pure Korean ethnicity, distinct Korean elderly facial features: angular Korean face shape, single eyelids or hooded eyes typical of Korean elderly men, Korean skin tone, weathered face with Korean aging characteristics, balding or short gray hair typical of Korean grandfathers"

- ⚠️ 1970~80년대 시대 감성 스타일:
  "vintage Korean film photography aesthetic, slightly faded warm colors, film grain texture, soft focus edges, nostalgic color grading similar to 1970s-1980s Korean cinema"

- ⚠️ 절대 금지: "Asian" 단독 사용, Western facial features, 현대적 요소
- ⚠️ 프롬프트 맨 앞에 한국인 특징을 배치해야 AI 모델이 정확히 인식합니다"""

        user_content = f"""다음 드라마 대본을 분석해주세요:

{script[:15000]}

⚠️ 중요: 대본에 있는 모든 씬을 빠짐없이 추출해주세요. 씬 번호가 있다면 모든 번호의 씬을 포함해야 합니다.
등장인물과 씬 정보를 JSON 형식으로 추출해주세요."""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
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

🚨 매우 중요 - 인물 외모 일관성 유지:
- 등장인물 정보에 제공된 외모 설명(나이, 머리 스타일, 체형, 얼굴 특징 등)을 정확히 그대로 사용하세요
- 외모 설명을 재해석하거나 변경하지 마세요
- 예: "78 years old elderly man" → 반드시 "78 years old elderly man"으로 유지
- 예: "white hair, wrinkled face" → 반드시 "white hair, wrinkled face"로 유지
- 추가할 수 있는 것: 위치, 표정, 행동, 자세 (외모는 변경 금지!)

🚨 한국인 외모 필수 - 프롬프트 맨 앞에 배치:
- 한국인 할머니: "Authentic Korean grandmother (halmeoni) from South Korea, pure Korean ethnicity, distinct Korean elderly facial features: round face shape, single eyelids typical of Korean elderly, Korean skin tone, permed short gray/white hair"
- 한국인 할아버지: "Authentic Korean grandfather (harabeoji) from South Korea, pure Korean ethnicity, distinct Korean elderly facial features: angular Korean face, single eyelids or hooded eyes, Korean skin tone, balding or short gray hair"
- 절대로 "Asian" 단독 사용 금지 - 반드시 "Korean"과 구체적인 한국인 특징 명시

🚨 1970~80년대 시대 감성 - 프롬프트 끝에 추가:
- "vintage Korean film photography aesthetic, slightly faded warm colors, film grain texture, nostalgic color grading similar to 1970s-1980s Korean cinema, soft warm lighting"

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

            # 사이즈에 따른 비율 결정
            if size == "1792x1024" or "16:9" in size:
                aspect_instruction = "IMPORTANT: Generate image in 16:9 widescreen landscape aspect ratio (width significantly larger than height)."
            elif size == "1024x1792" or "9:16" in size:
                aspect_instruction = "IMPORTANT: Generate image in 9:16 vertical portrait aspect ratio (height significantly larger than width)."
            else:
                aspect_instruction = "IMPORTANT: Generate image in 16:9 widescreen landscape aspect ratio for YouTube video."

            # 프롬프트에 스타일 가이드 추가 및 한국 인종 강조
            # 한국인 캐릭터인 경우 인종적 특징을 프롬프트 맨 앞에 배치하여 강조
            prompt_lower = prompt.lower()

            # 한국인 시니어 관련 키워드 감지
            is_elderly = any(kw in prompt_lower for kw in ['elderly', 'grandmother', 'grandfather', 'halmeoni', 'harabeoji', 'old', '70', '80', 'aged', 'senior'])
            is_korean = "korean" in prompt_lower

            if is_korean:
                if is_elderly and ('grandmother' in prompt_lower or 'woman' in prompt_lower or 'halmeoni' in prompt_lower):
                    # 한국 할머니 - 상세한 한국인 특징
                    korean_features = "CRITICAL REQUIREMENT: Authentic Korean grandmother (halmeoni) from South Korea. MUST have pure Korean ethnicity with distinct Korean elderly facial features: round face shape, single eyelids (monolid) or narrow double eyelids typical of Korean elderly, flat nose bridge, Korean skin tone (light to medium beige with warm undertones), natural Korean aging patterns with laugh lines, permed short gray/white hair typical of Korean grandmothers. NOT Western, NOT mixed ethnicity."
                    style_suffix = "vintage Korean film photography aesthetic, slightly faded warm colors, film grain texture, nostalgic color grading similar to 1970s-1980s Korean cinema, soft warm natural lighting"
                elif is_elderly and ('grandfather' in prompt_lower or 'man' in prompt_lower or 'harabeoji' in prompt_lower):
                    # 한국 할아버지 - 상세한 한국인 특징
                    korean_features = "CRITICAL REQUIREMENT: Authentic Korean grandfather (harabeoji) from South Korea. MUST have pure Korean ethnicity with distinct Korean elderly facial features: angular Korean face shape, single eyelids or hooded eyes typical of Korean elderly men, Korean skin tone, weathered kind face with Korean aging characteristics, balding or short gray hair typical of Korean grandfathers. NOT Western, NOT mixed ethnicity."
                    style_suffix = "vintage Korean film photography aesthetic, slightly faded warm colors, film grain texture, nostalgic color grading similar to 1970s-1980s Korean cinema, soft warm natural lighting"
                else:
                    # 일반 한국인
                    korean_features = "CRITICAL REQUIREMENT: The person MUST have authentic Korean/East Asian ethnicity from South Korea with Korean facial bone structure, Korean skin tone, natural Korean facial features. NOT Western features."
                    style_suffix = "cinematic Korean drama photography, professional lighting, 8k resolution, detailed"

                enhanced_prompt = f"{korean_features} {prompt}. {aspect_instruction} Style: {style_suffix}, wide shot composition"
            else:
                enhanced_prompt = f"Generate a high quality, photorealistic image: {prompt}. {aspect_instruction} Style: cinematic lighting, professional photography, 8k resolution, detailed, wide shot composition"

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

                # base64 데이터가 있으면 파일로 저장
                if base64_image_data and not image_url:
                    import base64 as b64
                    try:
                        # base64 디코딩
                        image_bytes = b64.b64decode(base64_image_data)

                        # 파일 저장
                        static_dir = os.path.join(os.path.dirname(__file__), 'static', 'images')
                        os.makedirs(static_dir, exist_ok=True)

                        timestamp = dt.now().strftime("%Y%m%d_%H%M%S_%f")
                        filename = f"gemini_{timestamp}.png"
                        filepath = os.path.join(static_dir, filename)

                        with open(filepath, 'wb') as f:
                            f.write(image_bytes)

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

            result = subprocess.run(cmd, capture_output=True, timeout=60)

            if result.returncode != 0:
                print(f"[TTS-MERGE][ERROR] FFmpeg 실패: {result.stderr.decode()[:200]}")
                # 폴백: 단순 바이트 결합
                return b''.join(audio_data_list)

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

            # 속도 변환: 네이버(-5~5) -> Google(0.25~4.0), 기본값 1.0
            if isinstance(speed, (int, float)):
                if speed == 0:
                    google_speed = 1.0
                else:
                    google_speed = 1.0 + (speed * 0.1)  # -5->0.5, 0->1.0, 5->1.5
                    google_speed = max(0.25, min(4.0, google_speed))
            else:
                google_speed = 1.0

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


# ===== Step6: 씬별 클립 생성 후 concat 방식 영상 제작 =====
def _generate_video_with_cuts(cuts, subtitle_data, burn_subtitle, resolution, fps, update_progress):
    """
    cuts 배열을 사용하여 각 씬별로 클립을 생성하고 concat하여 최종 영상 생성.
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

    # 해상도 파싱 및 최적화 (512MB 환경)
    width, height = resolution.split('x')
    width, height = int(width), int(height)

    MAX_WIDTH = 1280
    MAX_HEIGHT = 720
    if width > MAX_WIDTH or height > MAX_HEIGHT:
        aspect_ratio = width / height
        if aspect_ratio > 16/9:
            width = MAX_WIDTH
            height = int(MAX_WIDTH / aspect_ratio)
        else:
            height = MAX_HEIGHT
            width = int(MAX_HEIGHT * aspect_ratio)
        resolution = f"{width}x{height}"
        print(f"[DRAMA-CUTS-VIDEO] 해상도 조정: {resolution}")

    with tempfile.TemporaryDirectory() as temp_dir:
        update_progress(10, "씬별 영상 생성 준비 중...")

        segment_files = []
        total_duration = 0.0

        for idx, cut in enumerate(cuts):
            cut_id = cut.get('cutId', idx + 1)
            img_url = cut.get('imageUrl', '')
            audio_url = cut.get('audioUrl', '')
            cut_duration = cut.get('duration', 10)

            progress_pct = 10 + int((idx / len(cuts)) * 60)
            update_progress(progress_pct, f"씬 {cut_id} 처리 중... ({idx + 1}/{len(cuts)})")

            print(f"[DRAMA-CUTS-VIDEO] 씬 {cut_id} 처리 - 이미지: {img_url[:50] if img_url else 'N/A'}..., 오디오: {audio_url[:50] if audio_url else 'N/A'}...")

            # 이미지 다운로드/처리
            img_path = os.path.join(temp_dir, f"image_{idx:03d}.png")
            if img_url:
                try:
                    if img_url.startswith('data:'):
                        header, encoded = img_url.split(',', 1)
                        img_data = base64.b64decode(encoded)
                        with open(img_path, 'wb') as f:
                            f.write(img_data)
                    elif img_url.startswith('/static/'):
                        local_path = os.path.join(os.path.dirname(__file__), img_url.lstrip('/'))
                        if os.path.exists(local_path):
                            shutil.copy2(local_path, img_path)
                        else:
                            print(f"[DRAMA-CUTS-VIDEO] 로컬 이미지 없음: {local_path}")
                            continue
                    else:
                        response = requests.get(img_url, timeout=60)
                        if response.status_code == 200:
                            with open(img_path, 'wb') as f:
                                f.write(response.content)
                        else:
                            print(f"[DRAMA-CUTS-VIDEO] 이미지 다운로드 실패: {img_url}")
                            continue
                except Exception as e:
                    print(f"[DRAMA-CUTS-VIDEO] 이미지 처리 오류: {e}")
                    continue
            else:
                print(f"[DRAMA-CUTS-VIDEO] 씬 {cut_id} 이미지 URL 없음")
                continue

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
                    print(f"[DRAMA-CUTS-VIDEO] 오디오 처리 오류: {e}")

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
                    print(f"[DRAMA-CUTS-VIDEO] 오디오 길이 확인 오류: {e}")

            print(f"[DRAMA-CUTS-VIDEO] 씬 {cut_id}: 오디오={has_audio}, 길이={actual_duration:.1f}초")

            # 씬별 클립 생성
            segment_path = os.path.join(temp_dir, f"segment_{idx:03d}.mp4")

            if has_audio:
                # 이미지 + 오디오로 클립 생성
                ffmpeg_cmd = [
                    'ffmpeg', '-y',
                    '-loop', '1',
                    '-i', img_path,
                    '-i', audio_path,
                    '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                    '-c:a', 'aac', '-b:a', '128k',
                    '-r', str(fps),
                    '-t', str(actual_duration),
                    '-shortest',
                    '-pix_fmt', 'yuv420p',
                    segment_path
                ]
            else:
                # 오디오 없이 이미지만으로 클립 생성 (무음)
                ffmpeg_cmd = [
                    'ffmpeg', '-y',
                    '-loop', '1',
                    '-i', img_path,
                    '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                    '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
                    '-c:a', 'aac',
                    '-r', str(fps),
                    '-t', str(actual_duration),
                    '-shortest',
                    '-pix_fmt', 'yuv420p',
                    segment_path
                ]

            try:
                print(f"[DRAMA-CUTS-VIDEO] 씬 {cut_id} FFmpeg 명령: {' '.join(ffmpeg_cmd[:10])}...")
                process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=300)
                if process.returncode == 0 and os.path.exists(segment_path):
                    segment_files.append(segment_path)
                    total_duration += actual_duration
                    print(f"[DRAMA-CUTS-VIDEO] 씬 {cut_id} 클립 생성 완료: {segment_path}")
                else:
                    stderr_msg = process.stderr[:500] if process.stderr else '(stderr 없음)'
                    print(f"[DRAMA-CUTS-VIDEO] 씬 {cut_id} FFmpeg 오류 (returncode={process.returncode}): {stderr_msg}")
                    # FFmpeg 오류 상세 로그
                    if process.stdout:
                        print(f"[DRAMA-CUTS-VIDEO] 씬 {cut_id} FFmpeg stdout: {process.stdout[:300]}")
            except subprocess.TimeoutExpired:
                print(f"[DRAMA-CUTS-VIDEO] 씬 {cut_id} 타임아웃 (300초 초과)")
            except Exception as e:
                import traceback
                print(f"[DRAMA-CUTS-VIDEO] 씬 {cut_id} 클립 생성 오류: {e}")
                traceback.print_exc()

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
            process = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=600)
            if process.returncode != 0:
                stderr_msg = process.stderr[:500] if process.stderr else '(stderr 없음)'
                print(f"[DRAMA-CUTS-VIDEO] Concat 오류 (returncode={process.returncode}): {stderr_msg}")
                raise Exception(f"영상 병합 실패: {stderr_msg[:200]}")
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

        # Base64 인코딩 (20MB 이하만)
        if file_size_mb <= 20:
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
    from PIL import Image

    # 메모리 최적화: 해상도 자동 제한 (512MB 환경)
    width, height = resolution.split('x')
    width, height = int(width), int(height)

    # 1280x720 초과 시 자동으로 다운스케일
    MAX_WIDTH = 1280
    MAX_HEIGHT = 720
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

    update_progress(5, "FFmpeg 확인 중...")

    # FFmpeg 설치 확인
    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        raise Exception("FFmpeg가 설치되어 있지 않습니다. 서버에 FFmpeg를 설치해주세요.")

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
            project_font = os.path.join(base_dir, 'fonts', 'NanumGothicBold.ttf')

            font_found = False
            font_location = None
            if os.path.exists(project_font):
                font_found = True
                font_location = project_font
            else:
                # 시스템 폰트 폴백
                system_fonts = [
                    '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
                    '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
                ]
                for sf in system_fonts:
                    if os.path.exists(sf):
                        font_found = True
                        font_location = sf
                        break

            # ASS 자막에는 폰트 경로가 아닌 폰트 이름을 사용해야 함
            subtitle_font = 'NanumGothic' if font_found else 'Arial'

            print(f"[VIDEO-SUBTITLE] 자막 폰트: {subtitle_font} (found: {font_found}, location: {font_location if font_found else 'N/A'})")

            # ASS 헤더 생성 (한글 폰트 명시)
            ass_header = f"""[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{subtitle_font},72,&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,3,4,0,2,30,30,200,1

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
        try:
            process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=1800)
        except subprocess.TimeoutExpired:
            print(f"[DRAMA-STEP6-VIDEO][ERROR] FFmpeg 타임아웃 (30분)")
            raise Exception("영상 인코딩 시간 초과 (30분). 이미지 수를 줄이거나 해상도를 낮춰주세요.")

        if process.returncode != 0:
            error_msg = process.stderr.strip()
            print(f"[DRAMA-STEP6-VIDEO][ERROR] FFmpeg 오류: {error_msg}")

            # 일반적인 오류 메시지 개선
            if "No such file or directory" in error_msg:
                raise Exception("파일을 찾을 수 없습니다. 이미지나 오디오 파일이 손상되었을 수 있습니다.")
            elif "Invalid data" in error_msg or "corrupt" in error_msg:
                raise Exception("손상된 파일이 감지되었습니다. 이미지나 오디오를 다시 생성해주세요.")
            elif "Permission denied" in error_msg:
                raise Exception("파일 권한 오류. 서버 관리자에게 문의하세요.")
            else:
                raise Exception(f"영상 인코딩 실패: {error_msg[:300]}")

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

        # 메모리 최적화: Base64 인코딩 제한을 20MB로 낮춤 (512MB 환경)
        video_url = f"/static/videos/{video_filename}"
        if file_size_mb <= 20:
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


# ===== Step6: 영상 제작 API (비동기 큐 방식) =====
@app.route('/api/drama/generate-video', methods=['POST'])
def api_generate_video():
    """이미지와 오디오를 합쳐서 영상 생성 (비동기 - 백그라운드 워커 사용)

    Render 등 타임아웃이 있는 환경에서도 안정적으로 동작.
    요청 즉시 job_id 반환 → 프론트엔드에서 폴링으로 상태 확인
    """
    print(f"[DRAMA-STEP6-VIDEO] === API 호출 시작 (비동기 모드) ===")
    try:
        data = request.get_json()
        if not data:
            print(f"[DRAMA-STEP6-VIDEO] 요청 데이터 없음")
            return jsonify({"ok": False, "error": "No data received"}), 400

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

대본:
{script[:3000]}

제목: {title}

【필수 형식】으로 응답해주세요:

1. 주인공 정보: (대본의 주인공 - 나이, 성별, 직업, 현재 상황/감정)
2. 이미지 프롬프트: (영어로, 아래 조건 포함)
   - 주인공의 나이와 외모 반영 (60~80대 한국인)
   - 현재 감정 상태 (슬픔, 분노, 눈물, 기쁨 등)
   - 클로즈업 또는 미디엄 샷
   - 시네마틱 조명, 드라마틱한 분위기
3. 썸네일 텍스트: (3~4줄로 구성, 각 줄 \\n으로 구분)
   - 1줄: 훅 (충격적인 숫자/상황)
   - 2줄: 핵심 인물/사건
   - 3줄: 감정 강조 (강조색으로 표시될 부분)
   - 4줄: 궁금증 유발
4. 강조 줄 번호: (3줄 중 강조할 줄 번호, 예: 3)

【예시】
1. 주인공 정보: 76세 남성 목사, 교회 문을 닫으려던 절망적 순간
2. 이미지 프롬프트: Dramatic close-up portrait of a 76-year-old Korean elderly man pastor, tears streaming down wrinkled face, wearing simple clothes, emotional expression of despair turning to hope, cinematic golden hour lighting, church interior blurred background, high quality photograph
3. 썸네일 텍스트: 1년간 혼자 예배드리던\\n76세 목사님\\n교회 문 닫으려던 그날\\n한 청년이 나타났습니다
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

            enhanced_prompt = f"Generate a high quality YouTube thumbnail image: {image_prompt}. IMPORTANT: Ensure Korean/East Asian facial features if person is depicted. Style: dramatic, eye-catching, professional YouTube thumbnail quality."

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
                os.path.join(static_dir, 'fonts', 'NanumGothicBold.ttf'),
                "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
                "/System/Library/Fonts/AppleSDGothicNeo.ttc",
                "C:/Windows/Fonts/malgunbd.ttf",
            ]
            for fp in font_paths:
                if os_module.path.exists(fp):
                    try:
                        font = ImageFont.truetype(fp, font_size)
                        break
                    except:
                        continue
            if not font:
                font = ImageFont.load_default()

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

        if error:
            return f"인증 오류: {error}", 400

        if not code:
            return "인증 코드가 없습니다.", 400

        # 저장된 상태 로드
        oauth_state = load_oauth_state()
        if not oauth_state:
            return "인증 세션이 만료되었습니다. 다시 시도해주세요.", 400

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

        # 토큰 저장
        token_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': list(credentials.scopes) if credentials.scopes else []
        }

        save_youtube_token_to_db(token_data)

        print(f"[YOUTUBE-CALLBACK] 인증 완료, /drama 페이지로 리다이렉트")
        # Drama Lab 페이지로 리다이렉트 (Step5로 이동)
        return redirect('/drama?youtube_auth=success&step=5')

    except Exception as e:
        print(f"[YOUTUBE-CALLBACK][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return f"인증 오류: {str(e)}", 500


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
    """YouTube 채널 목록 가져오기"""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        # 데이터베이스에서 토큰 로드
        token_data = load_youtube_token_from_db()
        if not token_data:
            return jsonify({
                "success": False,
                "error": "YouTube 인증이 필요합니다."
            })

        credentials = Credentials.from_authorized_user_info(token_data)

        # 토큰 갱신 필요시
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            # 갱신된 토큰 저장 (데이터베이스에)
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
                "need_reauth": True
            })
        elif "credentials" in str(e).lower():
            return jsonify({
                "success": False,
                "error": "YouTube 인증 정보가 올바르지 않습니다. 다시 인증해주세요.",
                "need_reauth": True
            })
        else:
            return jsonify({
                "success": False,
                "error": f"채널 목록을 가져오는 데 실패했습니다: {str(e)}"
            })


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
        privacy_status = data.get('privacy_status', 'private')
        publish_at = data.get('publish_at')  # ISO 8601 형식의 예약 공개 시간
        channel_id = data.get('channel_id')  # 선택된 채널 ID

        if not video_data:
            return jsonify({"success": False, "error": "비디오 데이터가 없습니다."})

        if channel_id:
            print(f"[YOUTUBE-UPLOAD] 선택된 채널 ID: {channel_id}")

        # 데이터베이스에서 토큰 로드
        token_data = load_youtube_token_from_db()
        if not token_data:
            return jsonify({"success": False, "error": "YouTube 인증이 필요합니다."})

        credentials = Credentials.from_authorized_user_info(token_data)

        # 토큰 갱신
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            # 갱신된 토큰 저장 (데이터베이스에)
            token_data['token'] = credentials.token
            save_youtube_token_to_db(token_data)

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

        print(f"[THUMBNAIL] 썸네일 생성 시작 - 텍스트 {len(text_lines)}줄")

        if not image_url:
            return jsonify({"ok": False, "error": "이미지 URL이 필요합니다."}), 400

        if not text_lines:
            return jsonify({"ok": False, "error": "텍스트가 필요합니다."}), 400

        # 이미지 로드
        if image_url.startswith("data:"):
            # Base64 data URL
            header, encoded = image_url.split(",", 1)
            image_data = base64.b64decode(encoded)
            img = Image.open(BytesIO(image_data))
        else:
            # HTTP URL
            response = req.get(image_url, timeout=30)
            img = Image.open(BytesIO(response.content))

        # RGBA로 변환 (투명도 지원)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # 이미지 크기 (유튜브 썸네일: 1280x720 권장)
        width, height = img.size
        print(f"[THUMBNAIL] 이미지 크기: {width}x{height}")

        # 폰트 로드 (한글 지원 폰트)
        font = None
        font_paths = [
            # Linux (Render)
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            # Mac
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/Library/Fonts/NanumGothicBold.ttf",
            # Windows
            "C:/Windows/Fonts/malgunbd.ttf",
            "C:/Windows/Fonts/malgun.ttf",
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

        for i, line in enumerate(text_lines):
            y = y_start + (i * line_height)

            # 텍스트 크기 측정
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]

            # X 위치 결정
            if position == "center":
                x = (width - text_width) // 2
            elif position == "right":
                x = width - text_width - x_margin
            else:  # left
                x = x_margin

            # 색상 결정 (강조 줄인지 확인)
            if i in highlight_lines:
                fill_color = highlight_color
            else:
                fill_color = text_color

            # 외곽선 그리기 (8방향)
            for dx in range(-outline_width, outline_width + 1):
                for dy in range(-outline_width, outline_width + 1):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), line, font=font, fill=outline_color)

            # 메인 텍스트 그리기
            draw.text((x, y), line, font=font, fill=fill_color)

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
            "thumbnailUrl": result_url,
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
                <a href="/drama" class="back-btn">← Drama Lab으로 돌아가기</a>
            </body>
            </html>
            """

        # 이미 인증된 토큰 확인
        token_data = load_youtube_token_from_db()
        if token_data and token_data.get('refresh_token'):
            try:
                from google.auth.transport.requests import Request
                credentials = Credentials.from_authorized_user_info(token_data)
                if credentials and (credentials.valid or credentials.refresh_token):
                    # 이미 인증됨 - Drama 페이지로 리다이렉트
                    return redirect('/drama?youtube_auth=success')
            except Exception as e:
                print(f"[YOUTUBE-AUTH-GET] 기존 토큰 검증 실패: {e}")

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

        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # 항상 동의 화면 표시 (refresh_token 확보)
        )

        # 상태 저장
        save_oauth_state({
            'state': state,
            'redirect_uri': redirect_uri,
            'client_id': client_id,
            'client_secret': client_secret
        })

        print(f"[YOUTUBE-AUTH-GET] Google OAuth URL로 리다이렉트")
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
            <a href="/drama">← 돌아가기</a>
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
            <a href="/drama">← 돌아가기</a>
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
        privacy_status = data.get('privacyStatus', 'private')
        thumbnail_path = data.get('thumbnailPath')

        print(f"[YOUTUBE-UPLOAD] 업로드 요청 수신")
        print(f"  - 영상: {video_path}")
        print(f"  - 제목: {title}")
        print(f"  - 공개 설정: {privacy_status}")

        # 영상 파일 경로 처리
        if video_path and not video_path.startswith('http'):
            # 상대 경로를 절대 경로로 변환
            if video_path.startswith('/static/'):
                full_path = os.path.join(os.path.dirname(__file__), video_path.lstrip('/'))
            else:
                full_path = os.path.join(os.path.dirname(__file__), video_path)

            if not os.path.exists(full_path):
                print(f"[YOUTUBE-UPLOAD][WARN] 영상 파일 없음: {full_path}")
                return jsonify({
                    "ok": False,
                    "error": f"영상 파일을 찾을 수 없습니다: {video_path}"
                }), 200
        else:
            full_path = video_path

        # 썸네일 경로 처리
        full_thumbnail_path = None
        if thumbnail_path:
            if thumbnail_path.startswith('/static/'):
                full_thumbnail_path = os.path.join(os.path.dirname(__file__), thumbnail_path.lstrip('/'))
            elif not thumbnail_path.startswith('http'):
                full_thumbnail_path = os.path.join(os.path.dirname(__file__), thumbnail_path)
            else:
                full_thumbnail_path = thumbnail_path

        # 실제 업로드 시도
        try:
            import sys
            sys.path.insert(0, os.path.dirname(__file__))

            from step5_youtube_upload.youtube_auth import check_auth_status
            from step5_youtube_upload.upload_video import upload_video_to_youtube

            # 인증 상태 확인
            auth_status = check_auth_status()

            if auth_status.get('connected'):
                # 실제 업로드 실행
                print(f"[YOUTUBE-UPLOAD] 실제 업로드 시작 - 채널: {auth_status.get('channelName')}")

                result = upload_video_to_youtube(
                    video_path=full_path,
                    title=title,
                    description=description,
                    tags=tags,
                    category_id=category_id,
                    privacy_status=privacy_status,
                    thumbnail_path=full_thumbnail_path
                )

                if result.get('ok'):
                    print(f"[YOUTUBE-UPLOAD] 업로드 성공: {result.get('videoUrl')}")
                    return jsonify(result)
                else:
                    print(f"[YOUTUBE-UPLOAD] 업로드 실패: {result.get('error')}")
                    return jsonify(result)

            else:
                # 테스트 모드로 폴백
                print(f"[YOUTUBE-UPLOAD] 테스트 모드 - 이유: {auth_status.get('message')}")

        except ImportError as e:
            print(f"[YOUTUBE-UPLOAD] 모듈 임포트 오류: {e}")

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


# ===== Render 배포를 위한 설정 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5059))
    app.run(host="0.0.0.0", port=port, debug=False)
