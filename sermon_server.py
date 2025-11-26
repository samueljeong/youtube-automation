import os
import re
import json
import sqlite3
import hashlib
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from openai import OpenAI

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))

# 기본 관리자 이메일 설정
DEFAULT_ADMIN_EMAIL = 'zkvp17@naver.com'

# ===== 인증 시스템 활성화/비활성화 =====
# False로 설정하면 로그인 없이 서비스 이용 가능 (체험 기간용)
# True로 설정하면 회원가입/로그인 필수 (유료화 시)
AUTH_ENABLED = False

def get_client():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY가 비어 있습니다.")
    # GPT-5 긴 처리 시간을 위한 타임아웃 설정 (10분)
    return OpenAI(api_key=key, timeout=600.0)

client = get_client()

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None

# 모듈 로드 시점에 데이터베이스 상태 로그 출력 (gunicorn 환경에서도 동작)
print("=" * 50)
print("[SERMON-DB] Database Configuration")
print("=" * 50)

if USE_POSTGRES:
    # PostgreSQL 사용
    import psycopg2
    from psycopg2.extras import RealDictCursor

    # Render의 postgres:// URL을 postgresql://로 변경
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    print("[SERMON-DB] ✅ PostgreSQL 사용 중")
    # URL에서 비밀번호를 숨기고 출력
    safe_url = DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL[:50]
    print(f"[SERMON-DB]    Host: {safe_url}")

    def get_db_connection():
        """Create a PostgreSQL database connection"""
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
else:
    # SQLite 사용 (로컬 개발용)
    DB_PATH = os.path.join(os.path.dirname(__file__), 'sermon_data.db')

    print("[SERMON-DB] ⚠️  SQLite 사용 중 (로컬 개발 모드)")
    print(f"[SERMON-DB]    DB 파일: {DB_PATH}")
    print("[SERMON-DB]    경고: Render에서는 서버 재시작 시 데이터가 초기화됩니다!")
    print("[SERMON-DB]    → DATABASE_URL 환경변수를 설정해주세요.")

    def get_db_connection():
        """Create a SQLite database connection"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

print("=" * 50)

# DB 초기화
def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        # Users 테이블 생성 (Sermon 전용)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sermon_users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(100) NOT NULL,
                phone VARCHAR(20),
                birth_date VARCHAR(20),
                is_admin INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                step3_credits INTEGER DEFAULT 3,
                subscription_status VARCHAR(50) DEFAULT 'free',
                subscription_expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_users_email
            ON sermon_users(email)
        ''')

        # 전역 설정 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sermon_settings (
                id SERIAL PRIMARY KEY,
                setting_key VARCHAR(100) UNIQUE NOT NULL,
                setting_value VARCHAR(255) NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 기본 설정값 삽입 (존재하지 않을 때만)
        cursor.execute('''
            INSERT INTO sermon_settings (setting_key, setting_value, description)
            VALUES ('default_step3_credits', '3', '신규 회원 기본 Step3 크레딧')
            ON CONFLICT (setting_key) DO NOTHING
        ''')

        # 여기서 먼저 커밋 (테이블 생성 확정)
        conn.commit()

        # 기존 사용자에게 step3_credits 컬럼 추가 (이미 있으면 무시)
        # 컬럼 존재 여부 먼저 확인
        cursor.execute('''
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'sermon_users' AND column_name = 'step3_credits'
        ''')
        if not cursor.fetchone():
            try:
                cursor.execute('ALTER TABLE sermon_users ADD COLUMN step3_credits INTEGER DEFAULT 3')
                conn.commit()
            except Exception:
                conn.rollback()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sermon_benchmark_analyses (
                id SERIAL PRIMARY KEY,
                sermon_text TEXT NOT NULL,
                sermon_hash VARCHAR(100) UNIQUE,
                reference VARCHAR(200),
                sermon_title TEXT,
                category VARCHAR(100),
                style_name VARCHAR(100),
                analysis_result TEXT NOT NULL,
                sermon_structure TEXT,
                theological_depth TEXT,
                application_elements TEXT,
                illustration_style TEXT,
                language_style TEXT,
                success_factors TEXT,
                ai_model VARCHAR(50) DEFAULT 'gpt-5',
                analysis_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_benchmark_category
            ON sermon_benchmark_analyses(category)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_benchmark_style
            ON sermon_benchmark_analyses(style_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_benchmark_created_at
            ON sermon_benchmark_analyses(created_at DESC)
        ''')

        # step1_analyses 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS step1_analyses (
                id SERIAL PRIMARY KEY,
                reference VARCHAR(200) NOT NULL,
                sermon_text TEXT,
                analysis_text TEXT NOT NULL,
                analysis_hash VARCHAR(100) UNIQUE,
                category VARCHAR(100),
                style_name VARCHAR(100),
                step_name VARCHAR(100),
                quality_score INTEGER,
                theological_depth_score INTEGER,
                practical_application_score INTEGER,
                ai_model VARCHAR(50) DEFAULT 'gpt-5',
                analysis_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_reference
            ON step1_analyses(reference)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_category
            ON step1_analyses(category)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_quality
            ON step1_analyses(quality_score DESC)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_created_at
            ON step1_analyses(created_at DESC)
        ''')

        # API 사용량 로그 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_usage_logs (
                id SERIAL PRIMARY KEY,
                step_name VARCHAR(50) NOT NULL,
                model_name VARCHAR(50) NOT NULL,
                style_name VARCHAR(100),
                category VARCHAR(100),
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                estimated_cost_usd DECIMAL(10, 6) DEFAULT 0,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_usage_step_name
            ON api_usage_logs(step_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_usage_model_name
            ON api_usage_logs(model_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_usage_created_at
            ON api_usage_logs(created_at DESC)
        ''')

        # 현수막 참조 이미지 테이블 생성 (PostgreSQL)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banner_references (
                id SERIAL PRIMARY KEY,
                image_url TEXT NOT NULL,
                image_data TEXT,
                template_type VARCHAR(50) NOT NULL,
                title VARCHAR(200),
                description TEXT,
                color_palette TEXT,
                style_tags TEXT,
                quality_score INTEGER DEFAULT 5,
                use_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_banner_ref_template
            ON banner_references(template_type)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_banner_ref_quality
            ON banner_references(quality_score DESC)
        ''')
    else:
        # SQLite: Users 테이블 생성 (Sermon 전용)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sermon_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                phone TEXT,
                birth_date TEXT,
                is_admin INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                step3_credits INTEGER DEFAULT 3,
                subscription_status TEXT DEFAULT 'free',
                subscription_expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 전역 설정 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sermon_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 기본 설정값 삽입
        cursor.execute('''
            INSERT OR IGNORE INTO sermon_settings (setting_key, setting_value, description)
            VALUES ('default_step3_credits', '3', '신규 회원 기본 Step3 크레딧')
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_users_email
            ON sermon_users(email)
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sermon_benchmark_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sermon_text TEXT NOT NULL,
                sermon_hash TEXT UNIQUE,
                reference TEXT,
                sermon_title TEXT,
                category TEXT,
                style_name TEXT,
                analysis_result TEXT NOT NULL,
                sermon_structure TEXT,
                theological_depth TEXT,
                application_elements TEXT,
                illustration_style TEXT,
                language_style TEXT,
                success_factors TEXT,
                ai_model TEXT DEFAULT 'gpt-5',
                analysis_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_benchmark_category
            ON sermon_benchmark_analyses(category)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_benchmark_style
            ON sermon_benchmark_analyses(style_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sermon_benchmark_created_at
            ON sermon_benchmark_analyses(created_at DESC)
        ''')

        # step1_analyses 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS step1_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT NOT NULL,
                sermon_text TEXT,
                analysis_text TEXT NOT NULL,
                analysis_hash TEXT UNIQUE,
                category TEXT,
                style_name TEXT,
                step_name TEXT,
                quality_score INTEGER,
                theological_depth_score INTEGER,
                practical_application_score INTEGER,
                ai_model TEXT DEFAULT 'gpt-5',
                analysis_tokens INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_reference
            ON step1_analyses(reference)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_category
            ON step1_analyses(category)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_quality
            ON step1_analyses(quality_score DESC)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_step1_created_at
            ON step1_analyses(created_at DESC)
        ''')

        # API 사용량 로그 테이블 생성 (SQLite)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                step_name TEXT NOT NULL,
                model_name TEXT NOT NULL,
                style_name TEXT,
                category TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_usage_step_name
            ON api_usage_logs(step_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_usage_model_name
            ON api_usage_logs(model_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_usage_created_at
            ON api_usage_logs(created_at DESC)
        ''')

        # 현수막 참조 이미지 테이블 생성 (SQLite)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banner_references (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_url TEXT NOT NULL,
                image_data TEXT,
                template_type TEXT NOT NULL,
                title TEXT,
                description TEXT,
                color_palette TEXT,
                style_tags TEXT,
                quality_score INTEGER DEFAULT 5,
                use_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_banner_ref_template
            ON banner_references(template_type)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_banner_ref_quality
            ON banner_references(quality_score DESC)
        ''')

    conn.commit()
    conn.close()

# 앱 시작 시 DB 초기화
init_db()


# ===== 설정 관련 헬퍼 함수 =====
def get_setting(key, default=None):
    """설정값 가져오기"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('SELECT setting_value FROM sermon_settings WHERE setting_key = %s', (key,))
        else:
            cursor.execute('SELECT setting_value FROM sermon_settings WHERE setting_key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        return result['setting_value'] if result else default
    except:
        return default


def set_setting(key, value, description=None):
    """설정값 저장하기"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('''
                INSERT INTO sermon_settings (setting_key, setting_value, description, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (setting_key) DO UPDATE SET setting_value = %s, updated_at = CURRENT_TIMESTAMP
            ''', (key, value, description, value))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO sermon_settings (setting_key, setting_value, description, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (key, value, description))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[SETTING] 저장 실패: {e}")
        return False


# ===== API 사용량 기록 함수 =====
MODEL_PRICING = {
    # 모델별 가격 (USD per 1M tokens) - input/output
    'gpt-4o': {'input': 2.5, 'output': 10.0},
    'gpt-4o-mini': {'input': 0.15, 'output': 0.6},
    'gpt-5': {'input': 5.0, 'output': 20.0},
    'gpt-5.1': {'input': 7.5, 'output': 30.0},
}

def calculate_cost(model_name, input_tokens, output_tokens):
    """모델과 토큰 수로 비용 계산 (USD)"""
    pricing = MODEL_PRICING.get(model_name, MODEL_PRICING['gpt-4o'])
    input_cost = (input_tokens / 1_000_000) * pricing['input']
    output_cost = (output_tokens / 1_000_000) * pricing['output']
    return input_cost + output_cost

def log_api_usage(step_name, model_name, input_tokens=0, output_tokens=0, style_name=None, category=None, user_id=None):
    """API 사용량을 DB에 기록"""
    try:
        total_tokens = input_tokens + output_tokens
        estimated_cost = calculate_cost(model_name, input_tokens, output_tokens)

        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('''
                INSERT INTO api_usage_logs (step_name, model_name, style_name, category, input_tokens, output_tokens, total_tokens, estimated_cost_usd, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (step_name, model_name, style_name, category, input_tokens, output_tokens, total_tokens, estimated_cost, user_id))
        else:
            cursor.execute('''
                INSERT INTO api_usage_logs (step_name, model_name, style_name, category, input_tokens, output_tokens, total_tokens, estimated_cost_usd, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (step_name, model_name, style_name, category, input_tokens, output_tokens, total_tokens, estimated_cost, user_id))
        conn.commit()
        conn.close()
        print(f"[USAGE-LOG] {step_name} - {model_name}: {total_tokens} tokens, ${estimated_cost:.6f}")
        return True
    except Exception as e:
        print(f"[USAGE-LOG] 기록 실패: {e}")
        return False


def get_user_credits(user_id):
    """사용자 크레딧 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('SELECT step3_credits FROM sermon_users WHERE id = %s', (user_id,))
        else:
            cursor.execute('SELECT step3_credits FROM sermon_users WHERE id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result['step3_credits'] if result else 0
    except:
        return 0


def use_credit(user_id):
    """크레딧 1회 차감 (성공 시 True, 실패 시 False)"""
    try:
        credits = get_user_credits(user_id)
        if credits <= 0:
            return False

        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('UPDATE sermon_users SET step3_credits = step3_credits - 1 WHERE id = %s AND step3_credits > 0', (user_id,))
        else:
            cursor.execute('UPDATE sermon_users SET step3_credits = step3_credits - 1 WHERE id = ? AND step3_credits > 0', (user_id,))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0
    except:
        return False


def add_credits(user_id, amount):
    """크레딧 추가"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('UPDATE sermon_users SET step3_credits = step3_credits + %s WHERE id = %s', (amount, user_id))
        else:
            cursor.execute('UPDATE sermon_users SET step3_credits = step3_credits + ? WHERE id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False


def set_credits(user_id, amount):
    """크레딧 설정 (직접 지정)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('UPDATE sermon_users SET step3_credits = %s WHERE id = %s', (amount, user_id))
        else:
            cursor.execute('UPDATE sermon_users SET step3_credits = ? WHERE id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False


# ===== 인증 관련 함수 및 데코레이터 =====
def login_required(f):
    """로그인 필수 데코레이터 (AUTH_ENABLED가 False면 통과)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """관리자 권한 필수 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        # 관리자 권한 확인
        conn = get_db_connection()
        cursor = conn.cursor()
        if USE_POSTGRES:
            cursor.execute('SELECT is_admin FROM sermon_users WHERE id = %s', (session['user_id'],))
        else:
            cursor.execute('SELECT is_admin FROM sermon_users WHERE id = ?', (session['user_id'],))
        user = cursor.fetchone()
        conn.close()

        if not user or not user['is_admin']:
            flash('관리자 권한이 필요합니다.', 'error')
            return redirect(url_for('home'))

        return f(*args, **kwargs)
    return decorated_function


def api_login_required(f):
    """API용 로그인 필수 데코레이터 (AUTH_ENABLED가 False면 통과)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)
        if 'user_id' not in session:
            return jsonify({"ok": False, "error": "로그인이 필요합니다.", "redirect": "/login"}), 401
        return f(*args, **kwargs)
    return decorated_function


# ===== 인증 라우트 =====
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """회원가입"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        phone = request.form.get('phone')
        birth_date = request.form.get('birth_date')

        # 유효성 검사 - 이름과 전화번호 필수
        if not email or not password or not name or not phone:
            flash('이메일, 비밀번호, 실명, 전화번호는 필수 항목입니다.', 'error')
            return render_template('sermon_signup.html')

        if len(password) < 6:
            flash('비밀번호는 최소 6자 이상이어야 합니다.', 'error')
            return render_template('sermon_signup.html')

        # 전화번호 형식 정규화 (숫자만 추출)
        phone_normalized = ''.join(filter(str.isdigit, phone))
        if len(phone_normalized) < 10:
            flash('올바른 전화번호를 입력해주세요.', 'error')
            return render_template('sermon_signup.html')

        conn = get_db_connection()
        cursor = conn.cursor()

        # 이메일 중복 확인
        if USE_POSTGRES:
            cursor.execute('SELECT * FROM sermon_users WHERE email = %s', (email,))
        else:
            cursor.execute('SELECT * FROM sermon_users WHERE email = ?', (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('이미 존재하는 이메일입니다.', 'error')
            conn.close()
            return render_template('sermon_signup.html')

        # 실명+전화번호 중복 확인 (같은 명의로 중복 가입 방지)
        if USE_POSTGRES:
            cursor.execute('SELECT * FROM sermon_users WHERE name = %s AND phone = %s', (name, phone_normalized))
        else:
            cursor.execute('SELECT * FROM sermon_users WHERE name = ? AND phone = ?', (name, phone_normalized))
        duplicate_identity = cursor.fetchone()

        if duplicate_identity:
            flash('이미 같은 이름과 전화번호로 가입된 계정이 있습니다.', 'error')
            conn.close()
            return render_template('sermon_signup.html')

        # 비밀번호 해시 및 사용자 생성
        password_hash = generate_password_hash(password)

        # 기본 관리자 이메일인 경우 자동으로 관리자 권한 부여
        is_admin = 1 if email == DEFAULT_ADMIN_EMAIL else 0

        # 기본 크레딧 설정에서 가져오기
        default_credits = int(get_setting('default_step3_credits', '3'))

        try:
            if USE_POSTGRES:
                cursor.execute(
                    'INSERT INTO sermon_users (email, password_hash, name, phone, birth_date, is_admin, step3_credits) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                    (email, password_hash, name, phone_normalized, birth_date if birth_date else None, is_admin, default_credits)
                )
                conn.commit()
                cursor.execute('SELECT * FROM sermon_users WHERE email = %s', (email,))
            else:
                cursor.execute(
                    'INSERT INTO sermon_users (email, password_hash, name, phone, birth_date, is_admin, step3_credits) VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (email, password_hash, name, phone_normalized, birth_date if birth_date else None, is_admin, default_credits)
                )
                conn.commit()
                cursor.execute('SELECT * FROM sermon_users WHERE email = ?', (email,))

            user = cursor.fetchone()
            conn.close()

            # 자동 로그인
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_name'] = user['name']
            session['is_admin'] = user['is_admin']

            flash('회원가입이 완료되었습니다!', 'success')
            return redirect(url_for('home'))

        except Exception as e:
            conn.close()
            flash(f'회원가입 중 오류가 발생했습니다: {str(e)}', 'error')
            return render_template('sermon_signup.html')

    return render_template('sermon_signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """로그인"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('이메일과 비밀번호를 입력해주세요.', 'error')
            return render_template('sermon_login.html')

        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('SELECT * FROM sermon_users WHERE email = %s', (email,))
        else:
            cursor.execute('SELECT * FROM sermon_users WHERE email = ?', (email,))

        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            # 로그인 성공
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['user_name'] = user['name']
            session['is_admin'] = user['is_admin']

            flash(f'{user["name"]}님, 환영합니다!', 'success')
            return redirect(url_for('home'))
        else:
            flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'error')
            return render_template('sermon_login.html')

    return render_template('sermon_login.html')


@app.route('/logout')
def logout():
    """로그아웃"""
    session.clear()
    flash('로그아웃되었습니다.', 'success')
    return redirect(url_for('login'))


# ===== 관리자 라우트 =====
@app.route('/admin')
@admin_required
def admin_dashboard():
    """관리자 대시보드"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('SELECT id, email, name, phone, birth_date, is_admin, is_active, step3_credits, subscription_status, created_at FROM sermon_users ORDER BY created_at DESC')
        else:
            cursor.execute('SELECT id, email, name, phone, birth_date, is_admin, is_active, step3_credits, subscription_status, created_at FROM sermon_users ORDER BY created_at DESC')

        users = cursor.fetchall()
        conn.close()

        # PostgreSQL RealDictCursor는 이미 dict를 반환하지만, 확인을 위해 로그
        print(f"[ADMIN] users count: {len(users)}")
        if users:
            print(f"[ADMIN] first user type: {type(users[0])}")

        return render_template('sermon_admin.html', users=users)
    except Exception as e:
        import traceback
        print(f"[ADMIN ERROR] {str(e)}")
        print(traceback.format_exc())
        return f"Admin Error: {str(e)}", 500


@app.route('/admin/toggle-admin/<int:user_id>', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    """관리자 권한 토글"""
    if user_id == session['user_id']:
        flash('자신의 관리자 권한은 변경할 수 없습니다.', 'error')
        return redirect(url_for('admin_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute('SELECT is_admin FROM sermon_users WHERE id = %s', (user_id,))
        user = cursor.fetchone()
        if user:
            new_status = 0 if user['is_admin'] else 1
            cursor.execute('UPDATE sermon_users SET is_admin = %s WHERE id = %s', (new_status, user_id))
            conn.commit()
            action = '부여' if new_status else '제거'
            flash(f'관리자 권한이 {action}되었습니다.', 'success')
    else:
        cursor.execute('SELECT is_admin FROM sermon_users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        if user:
            new_status = 0 if user['is_admin'] else 1
            cursor.execute('UPDATE sermon_users SET is_admin = ? WHERE id = ?', (new_status, user_id))
            conn.commit()
            action = '부여' if new_status else '제거'
            flash(f'관리자 권한이 {action}되었습니다.', 'success')

    if not user:
        flash('사용자를 찾을 수 없습니다.', 'error')

    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """사용자 삭제"""
    if user_id == session['user_id']:
        flash('자신의 계정은 삭제할 수 없습니다.', 'error')
        return redirect(url_for('admin_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute('DELETE FROM sermon_users WHERE id = %s', (user_id,))
    else:
        cursor.execute('DELETE FROM sermon_users WHERE id = ?', (user_id,))

    conn.commit()
    conn.close()

    flash('사용자가 삭제되었습니다.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/api/auth/status')
def auth_status():
    """현재 로그인 상태 반환 (프론트엔드용)"""
    if 'user_id' in session:
        credits = get_user_credits(session['user_id'])
        is_admin = session.get('is_admin', 0)
        return jsonify({
            "ok": True,
            "loggedIn": True,
            "user": {
                "id": session['user_id'],
                "email": session['user_email'],
                "name": session['user_name'],
                "isAdmin": is_admin,
                "credits": credits if not is_admin else -1  # -1은 무제한
            }
        })
    return jsonify({"ok": True, "loggedIn": False})


@app.route('/api/db-status')
def db_status():
    """데이터베이스 연결 상태 확인 (디버깅용)"""
    db_type = "PostgreSQL" if USE_POSTGRES else "SQLite"
    status = {
        "ok": True,
        "database_type": db_type,
        "use_postgres": USE_POSTGRES,
        "warning": None
    }

    if not USE_POSTGRES:
        status["warning"] = "SQLite 사용 중! Render에서는 서버 재시작 시 데이터가 초기화됩니다. DATABASE_URL 환경변수를 설정해주세요."
        status["db_path"] = DB_PATH
    else:
        # PostgreSQL 연결 테스트
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM sermon_users")
            result = cursor.fetchone()
            user_count = result['count'] if isinstance(result, dict) else result[0]
            status["user_count"] = user_count
            status["connection_test"] = "success"
            conn.close()
        except Exception as e:
            status["connection_test"] = "failed"
            status["error"] = str(e)
            status["ok"] = False

    return jsonify(status)


# ===== 크레딧 관리 API =====
@app.route('/api/credits')
@api_login_required
def get_my_credits():
    """내 크레딧 조회"""
    # 인증이 비활성화된 경우에도 코드 입력 기능을 위해 크레딧 0으로 반환
    if not AUTH_ENABLED:
        return jsonify({
            "ok": True,
            "credits": 0,
            "unlimited": False,
            "authDisabled": True  # 클라이언트에서 체험 모드임을 알 수 있도록
        })

    user_id = session.get('user_id')
    is_admin = session.get('is_admin', 0)
    credits = get_user_credits(user_id)
    return jsonify({
        "ok": True,
        "credits": credits if not is_admin else -1,
        "unlimited": bool(is_admin)
    })


@app.route('/admin/set-credits/<int:user_id>', methods=['POST'])
@admin_required
def admin_set_credits(user_id):
    """관리자: 사용자 크레딧 설정"""
    try:
        amount = int(request.form.get('credits', 0))
        if amount < 0:
            amount = 0
        set_credits(user_id, amount)
        flash(f'크레딧이 {amount}으로 설정되었습니다.', 'success')
    except ValueError:
        flash('올바른 숫자를 입력해주세요.', 'error')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/add-credits/<int:user_id>', methods=['POST'])
@admin_required
def admin_add_credits(user_id):
    """관리자: 사용자 크레딧 추가"""
    try:
        amount = int(request.form.get('credits', 0))
        if amount > 0:
            add_credits(user_id, amount)
            flash(f'{amount} 크레딧이 추가되었습니다.', 'success')
        else:
            flash('양수를 입력해주세요.', 'error')
    except ValueError:
        flash('올바른 숫자를 입력해주세요.', 'error')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    """관리자: 전역 설정 관리"""
    if request.method == 'POST':
        default_credits = request.form.get('default_step3_credits', '3')
        set_setting('default_step3_credits', default_credits, '신규 회원 기본 Step3 크레딧')
        flash('설정이 저장되었습니다.', 'success')
        return redirect(url_for('admin_settings'))

    # 현재 설정값 가져오기
    default_credits = get_setting('default_step3_credits', '3')
    return render_template('sermon_settings.html', default_credits=default_credits)


@app.route('/admin/benchmark-data')
@admin_required
def admin_benchmark_data():
    """관리자: Benchmark 데이터 조회 페이지 (새 창에서 열림)"""
    data_type = request.args.get('type', 'sermon')  # 'sermon' 또는 'step1'
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if data_type == 'step1':
            # Step1 분석 데이터
            if USE_POSTGRES:
                cursor.execute("SELECT COUNT(*) as cnt FROM step1_analyses")
                total = cursor.fetchone()['cnt']
                cursor.execute("""
                    SELECT id, reference, category, style_name, step_name,
                           analysis_text, created_at
                    FROM step1_analyses
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, (per_page, offset))
            else:
                cursor.execute("SELECT COUNT(*) as cnt FROM step1_analyses")
                total = cursor.fetchone()['cnt']
                cursor.execute("""
                    SELECT id, reference, category, style_name, step_name,
                           analysis_text, created_at
                    FROM step1_analyses
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (per_page, offset))

            items = cursor.fetchall()
            title = "Step1 분석 데이터"
        else:
            # Step3 설교문 분석 데이터
            if USE_POSTGRES:
                cursor.execute("SELECT COUNT(*) as cnt FROM sermon_benchmark_analyses")
                total = cursor.fetchone()['cnt']
                cursor.execute("""
                    SELECT id, reference, sermon_title, category, style_name,
                           sermon_structure, theological_depth, application_elements,
                           illustration_style, language_style, success_factors,
                           analysis_tokens, created_at
                    FROM sermon_benchmark_analyses
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, (per_page, offset))
            else:
                cursor.execute("SELECT COUNT(*) as cnt FROM sermon_benchmark_analyses")
                total = cursor.fetchone()['cnt']
                cursor.execute("""
                    SELECT id, reference, sermon_title, category, style_name,
                           sermon_structure, theological_depth, application_elements,
                           illustration_style, language_style, success_factors,
                           analysis_tokens, created_at
                    FROM sermon_benchmark_analyses
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                """, (per_page, offset))

            items = cursor.fetchall()
            title = "Step3 설교문 분석 데이터"

        conn.close()

        total_pages = (total + per_page - 1) // per_page

        return render_template('sermon_benchmark_view.html',
                             items=items,
                             data_type=data_type,
                             title=title,
                             total=total,
                             page=page,
                             total_pages=total_pages,
                             per_page=per_page)
    except Exception as e:
        print(f"[BENCHMARK-VIEW] 오류: {str(e)}")
        return f"데이터 조회 오류: {str(e)}", 500


@app.route('/api/admin/usage-stats')
@admin_required
def api_usage_stats():
    """관리자: 사용량 통계 API"""
    days = int(request.args.get('days', 7))  # 1, 7, 30

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 날짜 필터 (PostgreSQL과 SQLite 차이)
        if USE_POSTGRES:
            date_filter = f"created_at >= NOW() - INTERVAL '{days} days'"

            # 모델별 사용량
            cursor.execute(f"""
                SELECT model_name,
                       COUNT(*) as count,
                       SUM(input_tokens) as total_input,
                       SUM(output_tokens) as total_output,
                       SUM(total_tokens) as total_tokens,
                       SUM(estimated_cost_usd) as total_cost
                FROM api_usage_logs
                WHERE {date_filter}
                GROUP BY model_name
                ORDER BY total_tokens DESC
            """)
            model_stats = cursor.fetchall()

            # 스타일별 사용량
            cursor.execute(f"""
                SELECT style_name,
                       COUNT(*) as count,
                       SUM(total_tokens) as total_tokens,
                       SUM(estimated_cost_usd) as total_cost
                FROM api_usage_logs
                WHERE {date_filter} AND style_name IS NOT NULL AND style_name != ''
                GROUP BY style_name
                ORDER BY count DESC
            """)
            style_stats = cursor.fetchall()

            # 일별 사용량 (최근 N일)
            cursor.execute(f"""
                SELECT DATE(created_at) as date,
                       COUNT(*) as count,
                       SUM(total_tokens) as total_tokens,
                       SUM(estimated_cost_usd) as total_cost
                FROM api_usage_logs
                WHERE {date_filter}
                GROUP BY DATE(created_at)
                ORDER BY date ASC
            """)
            daily_stats = cursor.fetchall()

            # 전체 합계
            cursor.execute(f"""
                SELECT COUNT(*) as total_calls,
                       SUM(input_tokens) as total_input,
                       SUM(output_tokens) as total_output,
                       SUM(total_tokens) as total_tokens,
                       SUM(estimated_cost_usd) as total_cost
                FROM api_usage_logs
                WHERE {date_filter}
            """)
            totals = cursor.fetchone()

        else:
            # SQLite
            date_filter = f"created_at >= datetime('now', '-{days} days')"

            cursor.execute(f"""
                SELECT model_name,
                       COUNT(*) as count,
                       SUM(input_tokens) as total_input,
                       SUM(output_tokens) as total_output,
                       SUM(total_tokens) as total_tokens,
                       SUM(estimated_cost_usd) as total_cost
                FROM api_usage_logs
                WHERE {date_filter}
                GROUP BY model_name
                ORDER BY total_tokens DESC
            """)
            model_stats = cursor.fetchall()

            cursor.execute(f"""
                SELECT style_name,
                       COUNT(*) as count,
                       SUM(total_tokens) as total_tokens,
                       SUM(estimated_cost_usd) as total_cost
                FROM api_usage_logs
                WHERE {date_filter} AND style_name IS NOT NULL AND style_name != ''
                GROUP BY style_name
                ORDER BY count DESC
            """)
            style_stats = cursor.fetchall()

            cursor.execute(f"""
                SELECT DATE(created_at) as date,
                       COUNT(*) as count,
                       SUM(total_tokens) as total_tokens,
                       SUM(estimated_cost_usd) as total_cost
                FROM api_usage_logs
                WHERE {date_filter}
                GROUP BY DATE(created_at)
                ORDER BY date ASC
            """)
            daily_stats = cursor.fetchall()

            cursor.execute(f"""
                SELECT COUNT(*) as total_calls,
                       SUM(input_tokens) as total_input,
                       SUM(output_tokens) as total_output,
                       SUM(total_tokens) as total_tokens,
                       SUM(estimated_cost_usd) as total_cost
                FROM api_usage_logs
                WHERE {date_filter}
            """)
            totals = cursor.fetchone()

        conn.close()

        # 결과 포맷팅
        return jsonify({
            "ok": True,
            "days": days,
            "modelStats": [dict(row) for row in model_stats],
            "styleStats": [dict(row) for row in style_stats],
            "dailyStats": [dict(row) for row in daily_stats],
            "totals": dict(totals) if totals else {}
        })

    except Exception as e:
        print(f"[USAGE-STATS] 오류: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


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
    단계별 기본 system prompt 반환
    사용자의 guide를 최우선으로 따르도록 설계
    """
    step_lower = step_name.lower()

    # 제목 추천 단계
    if '제목' in step_name:
        return """당신은 설교 '제목 후보'만 제안하는 역할입니다.

CRITICAL RULES:
1. 반드시 한국어로만 응답하세요
2. 정확히 3개의 제목만 제시하세요
3. 각 제목은 한 줄로 작성하세요
4. 번호, 기호, 마크다운 사용 금지
5. 제목만 작성하고 설명 추가 금지

출력 형식 예시:
하나님의 약속을 믿는 믿음
약속의 땅을 향한 여정
아브라함의 신앙 결단"""

    # 모든 다른 단계 - 기본 역할만 명시
    else:
        return f"""당신은 설교 '초안 자료'만 준비하는 역할입니다.

현재 단계: {step_name}

기본 역할:
- 반드시 한국어로만 응답하세요
- 완성된 설교 문단이 아닌, 자료와 구조만 제공
- 사용자가 제공하는 세부 지침을 최우선으로 따름
- 지침이 없는 경우에만 일반적인 설교 자료 형식 사용

⚠️ 중요: 사용자의 세부 지침이 제공되면 그것을 절대적으로 우선하여 따라야 합니다."""


# ===== JSON 지침 처리 함수들 =====
def is_json_guide(guide_text):
    """guide가 JSON 형식인지 확인"""
    if not guide_text or not isinstance(guide_text, str):
        return False
    stripped = guide_text.strip()
    return stripped.startswith('{') and stripped.endswith('}')


def parse_json_guide(guide_text):
    """JSON guide를 파싱하여 딕셔너리로 반환"""
    try:
        return json.loads(guide_text)
    except json.JSONDecodeError as e:
        print(f"[JSON Parse Error] {e}")
        return None


def build_prompt_from_json(json_guide, step_type="step1"):
    """
    JSON 지침을 기반으로 시스템 프롬프트 생성

    JSON 구조 예시:
    {
        "step": "step1",
        "style": "강해설교",
        "role": "성경 본문 분석가",
        "principle": "강해설교는 '본문이 말하는 그대로'를 해석해야 한다",
        "output_format": {
            "historical_background": { "label": "역사·정황 배경", "description": "..." },
            ...
        }
    }
    """
    role = json_guide.get("role", "설교 자료 작성자")
    principle = json_guide.get("principle", "")
    output_format = json_guide.get("output_format", {})

    # 시스템 프롬프트 구성
    prompt = f"""당신은 '{role}'입니다.

【 핵심 원칙 】
{principle}

【 출력 형식 】
반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 순수 JSON만 출력하세요.

```json
{{
"""

    # output_format에서 필드들 추출
    fields = []
    for key, value in output_format.items():
        label = value.get("label", key) if isinstance(value, dict) else key
        description = value.get("description", "") if isinstance(value, dict) else ""
        fields.append(f'  "{key}": "/* {label}: {description} */"')

    prompt += ",\n".join(fields)
    prompt += "\n}\n```\n"

    # 각 필드 상세 설명 추가
    prompt += "\n【 각 필드 상세 지침 】\n"
    for key, value in output_format.items():
        if isinstance(value, dict):
            label = value.get("label", key)
            description = value.get("description", "")
            purpose = value.get("purpose", "")
            items = value.get("items", [])

            prompt += f"\n▶ {key} ({label})\n"
            if description:
                prompt += f"  - 설명: {description}\n"
            if purpose:
                prompt += f"  - 목적: {purpose}\n"
            if items:
                prompt += f"  - 포함 항목: {', '.join(items)}\n"

            # 중첩 구조 처리 (per_verse, sub_items 등)
            for sub_key in ["per_verse", "per_term", "sub_items", "format"]:
                if sub_key in value:
                    sub_value = value[sub_key]
                    if isinstance(sub_value, dict):
                        prompt += f"  - {sub_key}:\n"
                        for sk, sv in sub_value.items():
                            if isinstance(sv, dict):
                                prompt += f"    • {sk}: {sv.get('description', sv)}\n"
                            else:
                                prompt += f"    • {sk}: {sv}\n"
                    elif isinstance(sub_value, list):
                        prompt += f"  - {sub_key}: {', '.join(str(x) for x in sub_value)}\n"

    prompt += "\n⚠️ 중요: 반드시 위 JSON 형식으로만 응답하세요. 마크다운이나 추가 설명 없이 순수 JSON만 출력하세요."

    return prompt


def build_step3_prompt_from_json(json_guide, meta_data, step1_result, step2_result):
    """
    Step3용 프롬프트 생성 - Step1, Step2 JSON 결과와 meta 데이터 통합

    json_guide: Step3 지침 (writing_spec 포함)
    meta_data: 사용자 입력 정보 (scripture, title, target, worship_type, duration 등)
    step1_result: Step1 JSON 결과
    step2_result: Step2 JSON 결과 (writing_spec 포함)
    """
    # 분량과 예배유형 추출
    duration = meta_data.get("duration", "")
    worship_type = meta_data.get("worship_type", "")

    prompt = ""

    # ★★★ 맨 앞에 분량/예배유형 최우선 강조 ★★★
    prompt += "=" * 50 + "\n"
    prompt += "【 ★★★ 최우선 지침 ★★★ 】\n"
    prompt += "=" * 50 + "\n"
    if duration:
        prompt += f"\n🚨 분량: {duration}\n"
        prompt += f"   → 이 설교는 반드시 {duration} 분량으로 작성하세요.\n"
        prompt += f"   → Step1/Step2 자료가 길더라도 {duration}에 맞춰 압축하세요.\n"
        prompt += "   → 분량 제한은 다른 모든 지침보다 우선합니다.\n"
    if worship_type:
        prompt += f"\n🚨 예배/집회 유형: {worship_type}\n"
        prompt += f"   → '{worship_type}'에 적합한 톤과 내용으로 작성하세요.\n"
    prompt += "\n" + "=" * 50 + "\n\n"

    prompt += "【 설교문 작성 지침 】\n\n"

    # Meta 정보 (한글 키 매핑)
    key_labels = {
        "scripture": "성경 본문",
        "title": "설교 제목",
        "target": "대상",
        "worship_type": "예배·집회 유형",
        "duration": "분량",
        "sermon_style": "설교 스타일",
        "category": "카테고리"
    }

    prompt += "▶ 기본 정보\n"
    for key, value in meta_data.items():
        if value:
            label = key_labels.get(key, key)
            prompt += f"  - {label}: {value}\n"
    prompt += "\n"

    # Step2의 writing_spec 적용 (단, 홈화면 duration이 우선)
    if step2_result and isinstance(step2_result, dict):
        writing_spec = step2_result.get("writing_spec", {})
        if writing_spec:
            prompt += "▶ 작성 규격 (참고용 - 홈화면 분량 설정이 우선)\n"
            for key, value in writing_spec.items():
                # length는 홈화면 duration이 우선하므로 표시만
                if key == "length" and duration:
                    prompt += f"  - {key}: {value} (※ 홈화면 설정 '{duration}'이 우선)\n"
                elif isinstance(value, list):
                    prompt += f"  - {key}: {', '.join(value)}\n"
                else:
                    prompt += f"  - {key}: {value}\n"
            prompt += "\n"

    # Step1 분석 자료
    if step1_result:
        prompt += "▶ Step1 분석 자료 (참고용)\n"
        if isinstance(step1_result, dict):
            prompt += json.dumps(step1_result, ensure_ascii=False, indent=2)
        else:
            prompt += str(step1_result)
        prompt += "\n\n"

    # Step2 구조
    if step2_result:
        prompt += "▶ Step2 설교 구조 (참고용 - 분량에 맞게 조절)\n"
        if isinstance(step2_result, dict):
            # writing_spec은 이미 위에서 처리했으므로 제외
            step2_without_spec = {k: v for k, v in step2_result.items() if k != "writing_spec"}
            prompt += json.dumps(step2_without_spec, ensure_ascii=False, indent=2)
        else:
            prompt += str(step2_result)
        prompt += "\n\n"

    # 마지막 지침
    prompt += "=" * 50 + "\n"
    prompt += "【 최종 작성 지침 】\n"
    prompt += "위 Step1/Step2 자료를 참고하여 설교문을 작성하세요.\n"
    if duration:
        prompt += f"⚠️ 단, 반드시 {duration} 분량을 지켜주세요. 이것이 가장 중요합니다.\n"
    prompt += "=" * 50

    return prompt


@app.route("/")
@login_required
def home():
    if AUTH_ENABLED:
        return render_template("sermon.html", user_name=session.get('user_name'), is_admin=session.get('is_admin'))
    else:
        return render_template("sermon.html", user_name="체험 사용자", is_admin=0)

@app.route("/sermon")
@login_required
def sermon():
    if AUTH_ENABLED:
        return render_template("sermon.html", user_name=session.get('user_name'), is_admin=session.get('is_admin'))
    else:
        return render_template("sermon.html", user_name="체험 사용자", is_admin=0)

@app.route("/health")
def health():
    return jsonify({"ok": True})

# ===== 처리 단계 실행 API (gpt-4o-mini) =====
@app.route("/api/sermon/process", methods=["POST"])
@api_login_required
def api_process_step():
    """단일 처리 단계 실행 (gpt-4o-mini 사용)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400
        
        category = data.get("category", "")
        step_id = data.get("stepId", "")
        step_name = data.get("stepName", "")
        step_type = data.get("stepType", "step1")
        reference = data.get("reference", "")
        title = data.get("title", "")
        text = data.get("text", "")
        guide = data.get("guide", "")
        master_guide = data.get("masterGuide", "")
        previous_results = data.get("previousResults", {})

        # 프론트엔드에서 전달받은 모델 사용 (없으면 기본값)
        model_name = data.get("model")
        if not model_name:
            # 기본값: stepType 기반 모델 선택
            if step_type == "step1":
                model_name = "gpt-5"
            else:  # step2
                model_name = "gpt-4o-mini"

        # temperature 설정 (gpt-4o-mini만 사용)
        use_temperature = (model_name == "gpt-4o-mini")

        print(f"[PROCESS] {category} - {step_name} (Step: {step_type}, 모델: {model_name})")

        # JSON 지침 여부 확인
        is_json = is_json_guide(guide)
        json_guide = None

        if is_json:
            json_guide = parse_json_guide(guide)
            if json_guide:
                print(f"[PROCESS] JSON 지침 감지됨 - style: {json_guide.get('style', 'unknown')}")
                # JSON 지침 기반 시스템 프롬프트 생성
                system_content = build_prompt_from_json(json_guide, step_type)
            else:
                # JSON 파싱 실패시 기존 방식 사용
                print(f"[PROCESS] JSON 파싱 실패 - 기존 텍스트 방식 사용")
                is_json = False

        if not is_json:
            # 기존 텍스트 방식
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
        user_content = f"[성경구절]\n{reference}\n\n"

        # 제목이 있으면 추가 (제목 추천 단계가 아닐 때만)
        if title and '제목' not in step_name:
            user_content += f"[설교 제목]\n{title}\n\n"
            user_content += "위 제목을 염두에 두고 모든 내용을 작성해주세요.\n\n"

        if text:
            user_content += f"[성경 본문]\n{text}\n\n"

        # 이전 단계 결과 추가
        if previous_results:
            user_content += "[이전 단계 결과 (참고용)]\n"
            for prev_id, prev_data in previous_results.items():
                user_content += f"\n### {prev_data['name']}\n{prev_data['result']}\n"
            user_content += "\n"

        # 제목 추천 단계 특별 처리
        if '제목' in step_name:
            user_content += f"위 성경 본문({reference})에 적합한 설교 제목을 정확히 3개만 제안해주세요.\n"
            user_content += "각 제목은 한 줄로, 번호나 기호 없이 작성하세요."
        else:
            user_content += f"위 내용을 바탕으로 '{step_name}' 단계를 작성해주세요.\n"

        if title and '제목' not in step_name:
            user_content += f"\n제목 '{title}'을 고려하여 작성하세요."

        # GPT 호출 (모델 동적 선택)
        # JSON 형식 강제하지 않음 - guide에 따라 자유롭게 출력
        if use_temperature:
            completion = client.chat.completions.create(
                model=model_name,
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
        else:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": system_content
                    },
                    {
                        "role": "user",
                        "content": user_content
                    }
                ]
            )

        result = completion.choices[0].message.content.strip()

        # 토큰 사용량 추출
        usage_data = None
        if hasattr(completion, 'usage') and completion.usage:
            usage_data = {
                "input_tokens": completion.usage.prompt_tokens,
                "output_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens
            }
            # 사용량 기록
            log_api_usage(
                step_name=step_id or step_type or 'step',
                model_name=model_name,
                input_tokens=usage_data['input_tokens'],
                output_tokens=usage_data['output_tokens'],
                style_name=data.get('styleName'),
                category=category
            )

        # 제목 추천 단계는 JSON 파싱하지 않고 그대로 반환
        if '제목' in step_name:
            result = remove_markdown(result)
            return jsonify({"ok": True, "result": result, "usage": usage_data})

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

            print(f"[PROCESS][SUCCESS] JSON 형식으로 응답받아 포맷팅 완료")

            # Step1인 경우 백그라운드로 DB 저장
            if step_type == "step1" or step_id == "step1":
                try:
                    import threading
                    save_thread = threading.Thread(
                        target=save_step1_analysis,
                        args=(reference, text, formatted_result, category, data.get("styleName", ""), step_id)
                    )
                    save_thread.daemon = True
                    save_thread.start()
                    print(f"[PROCESS] Step1 분석 저장 백그라운드 시작")
                except Exception as e:
                    print(f"[PROCESS] Step1 저장 시작 실패 (무시): {str(e)}")

            return jsonify({"ok": True, "result": formatted_result, "usage": usage_data})

        except json.JSONDecodeError as je:
            # JSON 파싱 실패 시 원본 텍스트를 반환 (정상 처리)
            # guide에서 텍스트 형식을 요구했을 수 있으므로 오류가 아님
            print(f"[PROCESS][INFO] 텍스트 형식으로 응답받음 (JSON 아님)")
            result = remove_markdown(result)

            # Step1인 경우 백그라운드로 DB 저장
            if step_type == "step1" or step_id == "step1":
                try:
                    import threading
                    save_thread = threading.Thread(
                        target=save_step1_analysis,
                        args=(reference, text, result, category, data.get("styleName", ""), step_id)
                    )
                    save_thread.daemon = True
                    save_thread.start()
                    print(f"[PROCESS] Step1 분석 저장 백그라운드 시작")
                except Exception as e:
                    print(f"[PROCESS] Step1 저장 시작 실패 (무시): {str(e)}")

            return jsonify({"ok": True, "result": result, "usage": usage_data})

    except Exception as e:
        print(f"[PROCESS][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 묵상메시지 생성 API =====
@app.route("/api/sermon/meditation", methods=["POST"])
@api_login_required
def api_meditation():
    """묵상메시지 생성 (GPT-4o-mini 사용)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        reference = data.get("reference", "")
        verse = data.get("verse", "")
        template = data.get("template", "")

        if not reference:
            return jsonify({"ok": False, "error": "성경구절을 입력해주세요."}), 400
        if not verse:
            return jsonify({"ok": False, "error": "본문말씀을 입력해주세요."}), 400

        print(f"[Meditation] 묵상메시지 생성 시작 - 구절: {reference}, 템플릿 사용: {'예' if template else '아니오'}")

        # 템플릿이 있으면 해당 양식 분석 후 사용
        if template:
            system_content = """당신은 따뜻하고 은혜로운 묵상메시지를 작성하는 전문가입니다.
사용자가 제공한 샘플 템플릿의 양식과 어조, 구조를 분석하여 동일한 스타일로 새로운 묵상메시지를 작성합니다.

작성 지침:
1. 샘플 템플릿의 문단 구조, 문체, 어조를 정확히 따라할 것
2. 템플릿의 글 길이와 비슷하게 작성
3. 성경 본문의 역사적/신학적 의미를 먼저 설명
4. 일상생활에 적용할 수 있는 실천적 교훈 포함
5. 따뜻하고 위로가 되는 어조 유지
6. 마크다운 기호 사용하지 않고 순수 텍스트로 작성
7. 날짜, 성경구절, 본문말씀은 제외하고 묵상 내용만 작성 (클라이언트에서 조합함)"""

            user_content = f"""[샘플 템플릿]
{template}

[작성할 묵상메시지 정보]
성경구절: {reference}
본문말씀: {verse}

위 샘플 템플릿과 동일한 양식과 스타일로 새로운 묵상메시지를 작성해주세요.
날짜, 성경구절, 본문말씀 부분은 제외하고 묵상 본문만 작성해주세요."""
        else:
            # 기본 양식 사용
            system_content = """당신은 따뜻하고 은혜로운 묵상메시지를 작성하는 전문가입니다.
주어진 성경구절과 본문말씀을 바탕으로 깊이 있는 묵상메시지를 작성합니다.

작성 지침:
1. 첫 번째 문단: 성경 본문의 역사적/신학적 배경 설명 (3-4문장)
2. 두 번째 문단: 우리 일상에서의 적용과 성찰 (3-4문장)
3. 세 번째 문단: 따뜻한 권면과 축복의 말씀 (2-3문장)
4. 마지막: 짧은 기도문 (선택)
5. 따뜻하고 위로가 되는 어조 사용
6. 마크다운 기호 사용하지 않고 순수 텍스트로 작성
7. 날짜, 성경구절, 본문말씀은 제외하고 묵상 내용만 작성"""

            user_content = f"""성경구절: {reference}
본문말씀: {verse}

위 말씀을 바탕으로 오늘의 묵상메시지를 작성해주세요.
날짜, 성경구절, 본문말씀 부분은 제외하고 묵상 본문만 작성해주세요."""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7,
            max_tokens=1500
        )

        result = completion.choices[0].message.content.strip()
        print(f"[Meditation] 생성 완료 - 길이: {len(result)}자")

        return jsonify({
            "ok": True,
            "result": result,
            "usage": {
                "input_tokens": completion.usage.prompt_tokens if hasattr(completion, 'usage') else 0,
                "output_tokens": completion.usage.completion_tokens if hasattr(completion, 'usage') else 0
            }
        })

    except Exception as e:
        print(f"[Meditation] 오류: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== GPT PRO (Step3) 처리 API =====
@app.route("/api/sermon/gpt-pro", methods=["POST"])
@api_login_required
def api_gpt_pro():
    """GPT PRO 완성본 작성"""
    try:
        # 인증이 비활성화된 경우 크레딧 체크 건너뛰기
        if AUTH_ENABLED:
            # 크레딧 확인
            user_id = session.get('user_id')
            current_credits = get_user_credits(user_id)

            # 관리자는 무제한
            is_admin = session.get('is_admin', 0)
            if not is_admin and current_credits <= 0:
                return jsonify({
                    "ok": False,
                    "error": "Step3 사용 크레딧이 부족합니다. 관리자에게 문의하세요.",
                    "credits": 0,
                    "needCredits": True
                }), 200
        else:
            # 체험 모드: 크레딧 무제한
            user_id = None
            current_credits = -1
            is_admin = 0

        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        reference = data.get("reference", "")
        title = data.get("title", "")
        series_name = data.get("seriesName", "")
        style_name = data.get("styleName", "")
        category = data.get("category", "")
        draft_content = data.get("draftContent", "")
        style_description = data.get("styleDescription", "")
        completed_step_names = data.get("completedStepNames", [])

        # 프론트엔드에서 전달받은 모델 사용 (없으면 기본값 gpt-5)
        gpt_pro_model = data.get("model", "gpt-5")
        # 사용자 지정 최대 토큰량 (없으면 기본값 16000)
        max_tokens = data.get("maxTokens", 16000)
        # 사용자 지정 지침 (통합된 시스템 지침 + 요청 사항)
        custom_prompt = data.get("customPrompt", "")

        # JSON 모드 데이터 (새로 추가)
        step1_result = data.get("step1Result")  # Step1 JSON 결과
        step2_result = data.get("step2Result")  # Step2 JSON 결과 (writing_spec 포함)
        target_audience = data.get("target", "")  # 대상
        worship_type = data.get("worshipType", "")  # 예배 유형
        duration = data.get("duration", "20분")  # 분량 (기본 20분)
        special_notes = data.get("specialNotes", "")  # 특별 참고 사항

        # JSON 모드 여부 확인 (실제 객체가 있을 때만)
        is_json_mode = (isinstance(step1_result, dict) and len(step1_result) > 0) or \
                       (isinstance(step2_result, dict) and len(step2_result) > 0)

        print(f"[GPT-PRO/Step3] JSON 모드: {is_json_mode}, step1_result 타입: {type(step1_result)}, step2_result 타입: {type(step2_result)}")

        print(f"[GPT-PRO/Step3] 처리 시작 - 스타일: {style_name}, 모델: {gpt_pro_model}, 토큰: {max_tokens}")
        print(f"[GPT-PRO/Step3] draft_content 길이: {len(draft_content)}, 완료된 단계: {completed_step_names}")
        if len(draft_content) < 100:
            print(f"[GPT-PRO/Step3] ⚠️ draft_content가 너무 짧음! 내용: {draft_content[:500]}")

        # 제목 생성 여부 확인
        has_title = bool(title and title.strip())

        # 시스템 프롬프트 (간단한 역할 정의만)
        system_content = "당신은 한국어 설교 전문가입니다. 마크다운 기호 대신 순수 텍스트만 사용합니다."

        # ★★★ 최우선 지침: 홈화면 설정 (분량, 예배유형) - 다른 모든 지침보다 우선 ★★★
        system_content += "\n\n" + "=" * 50
        system_content += "\n【 ★ 최우선 지침 - 반드시 준수 ★ 】"
        system_content += "\n" + "=" * 50
        if duration:
            system_content += f"\n\n🚨 분량 제한: 이 설교는 반드시 {duration} 분량으로 작성하세요."
            system_content += f"\n   - {duration} 분량을 절대 초과하지 마세요."
            system_content += "\n   - Step1, Step2의 구조가 길더라도 {duration} 안에 맞춰 압축하세요."
            system_content += "\n   - 이 분량 제한은 다른 모든 지침보다 우선합니다."
        if worship_type:
            system_content += f"\n\n🚨 예배/집회 유형: '{worship_type}'"
            system_content += f"\n   - 이 설교는 '{worship_type}'에 맞는 톤과 내용으로 작성하세요."
        if special_notes:
            system_content += f"\n\n🚨 특별 참고 사항:"
            system_content += f"\n   {special_notes}"
            system_content += f"\n   - 위 내용을 설교문 작성 시 반드시 고려하세요."
        system_content += "\n" + "=" * 50

        # 제목이 없으면 GPT가 생성하도록 지시
        if not has_title:
            system_content += (
                "\n\n⚠️ 제목 생성: 설교문 맨 앞에 '설교 제목: (제목 내용)' 형식으로 적절한 제목을 먼저 생성하세요."
                "\n그 다음 빈 줄을 넣고 바로 설교 내용을 시작하세요. 본문 성경구절은 출력하지 마세요."
            )
        else:
            system_content += "\n\n⚠️ 중요: 설교 제목과 본문 성경구절은 다시 출력하지 마세요. 바로 설교 내용부터 시작하세요."

        # 사용자 메시지 구성
        meta_lines = []
        if category:
            meta_lines.append(f"- 카테고리: {category}")
        if style_name:
            meta_lines.append(f"- 설교 스타일: {style_name}")
        if style_description:
            meta_lines.append(f"- 스타일 설명: {style_description}")
        if reference:
            meta_lines.append(f"- 본문 성경구절: {reference}")
        if title:
            meta_lines.append(f"- 설교 제목: {title}")
        if series_name:
            meta_lines.append(f"- 시리즈명: {series_name}")

        meta_section = "\n".join(meta_lines)

        # 글자수 제한 변수 초기화 (JSON 모드에서 writing_spec.length로 설정됨)
        length_constraint = None

        # JSON 모드 vs 기존 텍스트 모드
        if is_json_mode:
            try:
                print(f"[GPT-PRO/Step3] JSON 모드 활성화")
                # meta 데이터 구성
                meta_data = {
                    "scripture": reference,
                    "title": title,
                    "target": target_audience,
                    "worship_type": worship_type,
                    "duration": duration,
                    "sermon_style": style_name,
                    "category": category,
                    "special_notes": special_notes
                }

                # Step2에서 writing_spec 추출하여 시스템 프롬프트에 반영
                writing_spec = {}
                length_constraint = None  # 글자수 제한 (예: "1800-2800자")
                if step2_result and isinstance(step2_result, dict):
                    writing_spec = step2_result.get("writing_spec", {})
                    length_constraint = writing_spec.get("length")  # 글자수 제한 추출
                    if length_constraint:
                        print(f"[GPT-PRO/Step3] writing_spec length 감지: {length_constraint}")

                # 시스템 프롬프트에 writing_spec 반영
                if writing_spec:
                    system_content += "\n\n【 작성 규격 】\n"
                    for key, value in writing_spec.items():
                        if isinstance(value, list):
                            system_content += f"- {key}: {', '.join(value)}\n"
                        else:
                            system_content += f"- {key}: {value}\n"

                # JSON 기반 user_content 생성
                user_content = build_step3_prompt_from_json(
                    json_guide=None,
                    meta_data=meta_data,
                    step1_result=step1_result,
                    step2_result=step2_result
                )

                # 추가 지침이 있으면 포함
                if custom_prompt and custom_prompt.strip():
                    user_content += f"\n\n【추가 지침】\n{custom_prompt.strip()}"

            except Exception as json_err:
                print(f"[GPT-PRO/Step3] JSON 모드 오류, 텍스트 모드로 전환: {str(json_err)}")
                is_json_mode = False  # 텍스트 모드로 전환

        if not is_json_mode:
            # 기존 텍스트 모드
            user_content = (
                "아래는 gpt-4o-mini가 정리한 연구·개요 자료입니다."
                " 참고만 하고, 문장은 처음부터 새로 작성해주세요."
            )
            if meta_section:
                user_content += f"\n\n[기본 정보]\n{meta_section}"
            user_content += "\n\n[설교 초안 자료]\n"
            user_content += draft_content

            # 사용자 지정 지침 추가 (통합된 지침)
            if custom_prompt and custom_prompt.strip():
                user_content += f"\n\n【지침】\n{custom_prompt.strip()}"
            else:
                # 기본 지침 (하드코딩 - 사용자가 지침을 설정하지 않은 경우)
                user_content += "\n\n【지침】\n"
                user_content += (
                    "당신은 한국어 설교 전문가입니다.\n"
                    "step1,2 자료는 참고용으로만 활용하고 문장은 처음부터 새로 구성하며,\n"
                    "묵직하고 명료한 어조로 신학적 통찰과 실제적 적용을 균형 있게 제시하세요.\n\n"
                    "1. Step2의 설교 구조(서론, 본론, 결론)를 반드시 따라 작성하세요.\n"
                    "2. Step2의 대지(포인트) 구성을 유지하고 각 섹션의 핵심 메시지를 확장하세요.\n"
                    "3. 역사적 배경, 신학적 통찰, 실제 적용을 균형 있게 제시하세요.\n"
                    "4. 관련 성경구절을 적절히 인용하세요.\n"
                    "5. 가독성을 위해 각 섹션 사이에 빈 줄을 넣으세요.\n"
                    "6. 마크다운, 불릿 기호 대신 순수 텍스트 단락을 사용하세요.\n"
                    "7. 충분히 길고 상세하며 풍성한 내용으로 작성해주세요."
                )

        # 공통 지침 추가 - length_constraint가 있으면 글자수 제한 강조
        if length_constraint:
            user_content += f"\n\n⚠️ 매우 중요 - 글자수 제한: 설교문 전체 분량을 반드시 '{length_constraint}' 범위 내로 작성하세요!"
            user_content += f"\n이 글자수 제한은 설교 유형에 맞춘 필수 규격입니다. 초과하거나 부족하지 않도록 주의하세요."
        else:
            user_content += f"\n\n⚠️ 중요: 충분히 길고 상세하며 풍성한 내용으로 작성해주세요 (최대 {max_tokens} 토큰)."

        # 토큰 사용량 저장용 변수
        usage_data = None

        # 모델에 따라 적절한 API 호출
        # gpt-5 계열은 max_completion_tokens 사용, temperature 미지원
        # gpt-4o 계열은 max_tokens 사용, temperature 지원
        if gpt_pro_model in ["gpt-5", "gpt-5.1"]:
            # gpt-5, gpt-5.1은 temperature 지원 안함 (기본값 1만 허용)
            completion = client.chat.completions.create(
                model=gpt_pro_model,
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
                max_completion_tokens=max_tokens
            )
            result = completion.choices[0].message.content.strip()

            # Chat Completions API 토큰 사용량 추출
            if hasattr(completion, 'usage') and completion.usage:
                usage_data = {
                    "input_tokens": getattr(completion.usage, 'prompt_tokens', 0),
                    "output_tokens": getattr(completion.usage, 'completion_tokens', 0),
                    "total_tokens": getattr(completion.usage, 'total_tokens', 0)
                }
        elif gpt_pro_model.startswith("gpt-5"):
            # 다른 gpt-5.x 모델
            completion = client.chat.completions.create(
                model=gpt_pro_model,
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
                max_completion_tokens=max_tokens
            )
            result = completion.choices[0].message.content.strip()

            if hasattr(completion, 'usage') and completion.usage:
                usage_data = {
                    "input_tokens": getattr(completion.usage, 'prompt_tokens', 0),
                    "output_tokens": getattr(completion.usage, 'completion_tokens', 0),
                    "total_tokens": getattr(completion.usage, 'total_tokens', 0)
                }
        else:
            # gpt-4o 등 다른 모델
            completion = client.chat.completions.create(
                model=gpt_pro_model,
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
                max_tokens=max_tokens
            )
            result = completion.choices[0].message.content.strip()

            # Chat Completions API 토큰 사용량 추출
            if hasattr(completion, 'usage') and completion.usage:
                usage_data = {
                    "input_tokens": completion.usage.prompt_tokens,
                    "output_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens
                }

        if not result:
            raise RuntimeError(f"{gpt_pro_model} API로부터 결과를 받지 못했습니다.")

        # 사용량 기록
        if usage_data:
            log_api_usage(
                step_name='step3',
                model_name=gpt_pro_model,
                input_tokens=usage_data.get('input_tokens', 0),
                output_tokens=usage_data.get('output_tokens', 0),
                style_name=style_name,
                category=category
            )

        # 마크다운 제거
        result = remove_markdown(result)

        # 결과 앞에 제목과 본문 추가
        final_result = ""

        # 제목 처리
        if has_title:
            # 사용자가 입력한 제목 사용
            final_result += f"설교 제목: {title}\n\n"
            # 본문 추가
            if reference:
                final_result += f"본문: {reference}\n\n"
            # GPT 결과 (제목 없이)
            final_result += result
        else:
            # GPT가 생성한 제목 포함된 결과 그대로 사용
            # 본문만 추가
            if reference:
                # GPT 결과 앞에 본문 삽입
                final_result += f"본문: {reference}\n\n"
            final_result += result

        print(f"[GPT-PRO] 완료")

        # 설교문 자동 분석 및 DB 저장 (백그라운드 처리 - 실패해도 사용자에게 영향 없음)
        try:
            # 제목 추출 (GPT가 생성한 경우)
            extracted_title = title if has_title else ""
            if not has_title and "설교 제목:" in final_result:
                # GPT가 생성한 제목 추출
                lines = final_result.split('\n')
                for line in lines:
                    if line.startswith("설교 제목:"):
                        extracted_title = line.replace("설교 제목:", "").strip()
                        break

            # 비동기적으로 분석 수행 (실패해도 무시)
            import threading
            analysis_thread = threading.Thread(
                target=analyze_sermon_for_benchmark,
                args=(final_result, reference, extracted_title, category, style_name)
            )
            analysis_thread.daemon = True  # 메인 프로세스 종료 시 함께 종료
            analysis_thread.start()
            print(f"[GPT-PRO] 벤치마크 분석 백그라운드 시작")
        except Exception as e:
            print(f"[GPT-PRO] 벤치마크 분석 시작 실패 (무시): {str(e)}")

        # 크레딧 차감 (관리자 제외, 인증 활성화 시에만)
        remaining_credits = current_credits
        if AUTH_ENABLED and not is_admin and user_id:
            use_credit(user_id)
            remaining_credits = get_user_credits(user_id)
            print(f"[GPT-PRO/Step3] 크레딧 차감 - 사용자: {user_id}, 남은 크레딧: {remaining_credits}")

        print(f"[GPT-PRO/Step3] 완료 - 토큰: {usage_data}")
        return jsonify({
            "ok": True,
            "result": final_result,
            "usage": usage_data,
            "credits": remaining_credits if not is_admin else -1  # -1은 무제한 표시
        })

    except Exception as e:
        print(f"[GPT-PRO/Step3][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


@app.route("/api/sermon/qa", methods=["POST"])
@api_login_required
def api_sermon_qa():
    """설교 준비 Q&A - 처리 단계 결과와 본문을 기반으로 질문에 답변"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        question = data.get("question", "")
        reference = data.get("reference", "")
        step_results = data.get("stepResults", {})

        if not question:
            return jsonify({"ok": False, "error": "질문이 비어있습니다"}), 400

        print(f"[Q&A] 질문: {question}")

        # 시스템 메시지: Q&A 역할 정의
        system_content = """당신은 설교 준비를 돕는 성경 연구 도우미입니다.

당신의 역할:
- 사용자가 현재 준비 중인 성경 본문과 관련된 질문에 답변합니다
- 제공된 처리 단계 결과(배경 지식, 본문 분석, 개요 등)를 참고하여 답변합니다
- 질문이 모호한 경우, 현재 맥락(성경 본문, 처리 단계)을 기준으로 이해하고 답변합니다
- 간단하고 명확하게 답변하되, 필요시 성경적 배경이나 신학적 설명을 추가합니다

답변 원칙:
- 친절하고 이해하기 쉬운 톤으로 작성
- 불확실한 경우 "정확하지 않을 수 있습니다"라고 명시
- 필요시 관련 성경 구절이나 역사적 배경 언급"""

        # 사용자 메시지: 컨텍스트 + 질문
        user_content = ""

        # 성경 본문 정보
        if reference:
            user_content += f"【 현재 준비 중인 성경 본문 】\n{reference}\n\n"

        # 처리 단계 결과들
        if step_results:
            user_content += "【 처리 단계 결과 】\n"
            for step_id, step_data in step_results.items():
                step_name = step_data.get("name", "")
                step_result = step_data.get("result", "")
                if step_result:
                    user_content += f"\n### {step_name}\n{step_result}\n"
            user_content += "\n"

        # 사용자 질문
        user_content += f"【 사용자 질문 】\n{question}\n\n"
        user_content += "위 맥락을 참고하여 질문에 답변해주세요."

        # GPT 호출 (gpt-4o-mini)
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
            temperature=0.7
        )

        answer = completion.choices[0].message.content

        print(f"[Q&A] 답변 완료")

        return jsonify({"ok": True, "answer": answer})

    except Exception as e:
        print(f"[Q&A][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


@app.route("/api/sermon/recommend-scripture", methods=["POST"])
@api_login_required
def api_recommend_scripture():
    """상황에 맞는 성경 본문 추천 (단락 단위, 본문 포함)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        query = data.get("query", "")
        if not query:
            return jsonify({"ok": False, "error": "상황을 입력해주세요"}), 400

        print(f"[본문추천] 검색어: {query}")

        system_content = """당신은 설교 본문 선정 전문가입니다. 사용자가 제시하는 상황, 행사, 주제에 가장 적합한 성경 본문을 추천해주세요.

【 핵심 원칙 】
1. 단락(Pericope) 단위로 추천: 1-2절이 아닌, 하나의 완결된 이야기나 논증 단위로 추천하세요.
   - 좋은 예: 창세기 18:17-33 (아브라함의 중보기도), 요한복음 15:1-17 (포도나무 비유)
   - 나쁜 예: 창세기 18:17 (너무 짧음), 시편 23:1 (단절됨)
2. 새벽설교, 주일설교 등에 적합한 5-20절 분량의 본문을 추천하세요.
3. 실제 성경 본문 내용을 포함하세요 (개역개정 기준).

【 응답 형식 】
반드시 아래 JSON 형식으로만 응답하세요:
[
  {
    "scripture": "창세기 18:17-33",
    "title": "아브라함의 중보기도",
    "text": "여호와께서 이르시되 내가 하려는 것을 아브라함에게 숨기겠느냐... (핵심 구절 3-5개 발췌)",
    "reason": "이 본문이 해당 상황에 적합한 이유를 2-3문장으로 구체적으로 설명. 본문의 핵심 메시지와 상황의 연결점을 분석적으로 제시하세요."
  },
  ...
]

【 주의사항 】
- 정확히 5개의 추천을 제공하세요
- scripture: 한글 성경 표기법 + 단락 범위 (예: 창세기 18:17-33)
- title: 본문의 핵심 주제를 5-10자로
- text: 해당 본문의 핵심 구절 3-5개를 발췌 (... 으로 연결)
- reason: 50-100자로 상황과 본문의 연결점을 분석적으로 설명
- JSON 형식만 응답하세요"""

        user_content = f"""다음 상황/행사/주제에 적합한 설교 본문 5개를 추천해주세요.

상황: {query}

각 추천에 대해:
1. 단락 단위의 본문 범위 (5-20절)
2. 본문 제목
3. 핵심 성경 구절 발췌
4. 이 본문을 추천하는 구체적인 이유 (상황과의 연결점)

를 제공해주세요."""

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7
        )

        response_text = completion.choices[0].message.content.strip()

        # JSON 파싱
        try:
            # 코드블록 제거
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            recommendations = json.loads(response_text)
        except json.JSONDecodeError:
            print(f"[본문추천] JSON 파싱 실패: {response_text[:200]}")
            return jsonify({"ok": False, "error": "추천 결과 파싱 실패"}), 200

        print(f"[본문추천] 완료: {len(recommendations)}개 추천")

        return jsonify({"ok": True, "recommendations": recommendations})

    except Exception as e:
        print(f"[본문추천][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 200


# ===== 설교문 벤치마크 분석 함수 =====
def analyze_sermon_for_benchmark(sermon_text, reference="", sermon_title="", category="", style_name=""):
    """
    생성된 설교문을 자동으로 분석하여 DB에 저장

    Args:
        sermon_text: 생성된 설교문 텍스트
        reference: 본문 성경구절
        sermon_title: 설교 제목
        category: 카테고리 (설교 유형)
        style_name: 설교 스타일

    Returns:
        dict: {"ok": True/False, "message": "..."}
    """
    try:
        # 설교문 해시 생성 (중복 체크용)
        sermon_hash = hashlib.md5(sermon_text.encode('utf-8')).hexdigest()

        # DB 기반 중복 체크
        is_duplicate = False
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            if USE_POSTGRES:
                cursor.execute("SELECT id FROM sermon_benchmark_analyses WHERE sermon_hash = %s", (sermon_hash,))
            else:
                cursor.execute("SELECT id FROM sermon_benchmark_analyses WHERE sermon_hash = ?", (sermon_hash,))
            existing = cursor.fetchone()
            conn.close()

            if existing:
                is_duplicate = True
                print(f"[SERMON-BENCHMARK] 중복 설교문 감지 (해시: {sermon_hash[:8]}...) - 분석 건너뜀")
                return {"ok": True, "message": "중복 설교문 - 분석 건너뜀", "isDuplicate": True}
        except Exception as e:
            print(f"[SERMON-BENCHMARK] 중복 체크 실패: {str(e)}")

        print(f"[SERMON-BENCHMARK] 설교문 분석 시작 - 스타일: {style_name}, 카테고리: {category}")

        # GPT로 설교문 분석
        system_content = """당신은 설교문 분석 전문가입니다.

제공된 설교문을 분석하여 다음 요소들을 추출하고 정리하세요:

1. **설교 구조 분석**
   - 서론, 본론, 결론의 구성 방식
   - 각 파트의 비중과 전환 흐름
   - 대지 구조 (있는 경우)

2. **신학적 깊이**
   - 성경 해석의 정확성과 깊이
   - 신학적 통찰의 수준
   - 복음 중심성

3. **적용 요소**
   - 실천 가능한 적용의 구체성
   - 청중 맥락에 대한 이해
   - 실생활 연결성

4. **예화 및 스토리텔링**
   - 예화 사용 방식과 효과
   - 스토리텔링 기법
   - 감정적 공감 유도 방법

5. **언어 스타일**
   - 문체와 어조
   - 문장 구조와 리듬
   - 명확성과 설득력

6. **성공 요인 분석**
   - 전반적인 설교의 강점
   - 청중 몰입 요소
   - 차별화 포인트

분석 결과는 구조화되고 명확하게 작성하세요."""

        user_content = f"""[설교문 정보]
- 본문 성경구절: {reference}
- 설교 제목: {sermon_title}
- 카테고리: {category}
- 스타일: {style_name}

[설교문 내용]
{sermon_text}

위 설교문을 분석하여 핵심 패턴과 성공 요인을 추출해주세요."""

        completion = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ]
        )

        analysis = completion.choices[0].message.content.strip()
        total_tokens = completion.usage.total_tokens if hasattr(completion, 'usage') else 0

        # 분석 결과를 섹션별로 파싱
        sermon_structure = ""
        theological_depth = ""
        application_elements = ""
        illustration_style = ""
        language_style = ""
        success_factors = ""

        # 섹션별 추출 (간단한 패턴 매칭)
        sections = analysis.split('\n\n')
        for section in sections:
            if '설교 구조' in section or '구조 분석' in section:
                sermon_structure = section
            elif '신학적 깊이' in section or '신학' in section:
                theological_depth = section
            elif '적용' in section:
                application_elements = section
            elif '예화' in section or '스토리텔링' in section:
                illustration_style = section
            elif '언어' in section or '스타일' in section:
                language_style = section
            elif '성공 요인' in section:
                success_factors = section

        # DB에 저장
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            if USE_POSTGRES:
                cursor.execute('''
                    INSERT INTO sermon_benchmark_analyses
                    (sermon_text, sermon_hash, reference, sermon_title, category, style_name,
                     analysis_result, sermon_structure, theological_depth, application_elements,
                     illustration_style, language_style, success_factors, ai_model, analysis_tokens)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (sermon_text, sermon_hash, reference, sermon_title, category, style_name,
                      analysis, sermon_structure, theological_depth, application_elements,
                      illustration_style, language_style, success_factors, 'gpt-5', total_tokens))
            else:
                cursor.execute('''
                    INSERT INTO sermon_benchmark_analyses
                    (sermon_text, sermon_hash, reference, sermon_title, category, style_name,
                     analysis_result, sermon_structure, theological_depth, application_elements,
                     illustration_style, language_style, success_factors, ai_model, analysis_tokens)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (sermon_text, sermon_hash, reference, sermon_title, category, style_name,
                      analysis, sermon_structure, theological_depth, application_elements,
                      illustration_style, language_style, success_factors, 'gpt-5', total_tokens))

            conn.commit()
            conn.close()
            print(f"[SERMON-BENCHMARK] DB 저장 완료 (해시: {sermon_hash[:8]}..., 토큰: {total_tokens})")
        except Exception as e:
            print(f"[SERMON-BENCHMARK] DB 저장 실패: {str(e)}")

        print(f"[SERMON-BENCHMARK] 분석 완료 - 모델: gpt-5")

        return {"ok": True, "message": "분석 완료 및 DB 저장됨", "isDuplicate": False}

    except Exception as e:
        print(f"[SERMON-BENCHMARK][ERROR] {str(e)}")
        return {"ok": False, "message": f"분석 실패: {str(e)}"}


# ===== Step1 분석 자동 저장 함수 =====
def save_step1_analysis(reference, sermon_text, analysis_text, category="", style_name="", step_name="step1"):
    """
    Step1 본문 분석 결과를 자동으로 DB에 저장

    Args:
        reference: 성경 본문 구절
        sermon_text: 성경 본문 텍스트
        analysis_text: 분석 결과 텍스트
        category: 카테고리
        style_name: 설교 스타일
        step_name: 단계 이름 (기본값: step1)

    Returns:
        dict: {"ok": True/False, "message": "..."}
    """
    try:
        # 분석 해시 생성 (중복 체크용 - reference + analysis_text 조합)
        hash_content = f"{reference}|{analysis_text}"
        analysis_hash = hashlib.md5(hash_content.encode('utf-8')).hexdigest()

        # DB 기반 중복 체크
        is_duplicate = False
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            if USE_POSTGRES:
                cursor.execute("SELECT id FROM step1_analyses WHERE analysis_hash = %s", (analysis_hash,))
            else:
                cursor.execute("SELECT id FROM step1_analyses WHERE analysis_hash = ?", (analysis_hash,))
            existing = cursor.fetchone()
            conn.close()

            if existing:
                is_duplicate = True
                print(f"[STEP1-SAVE] 중복 분석 감지 (해시: {analysis_hash[:8]}...) - 저장 건너뜀")
                return {"ok": True, "message": "중복 분석 - 저장 건너뜀", "isDuplicate": True}
        except Exception as e:
            print(f"[STEP1-SAVE] 중복 체크 실패: {str(e)}")

        print(f"[STEP1-SAVE] Step1 분석 저장 시작 - 본문: {reference[:30]}...")

        # GPT-5로 분석 품질 평가
        evaluation_system = """당신은 성경 본문 분석 평가 전문가입니다.

제공된 성경 본문 분석을 평가하여 다음 3가지 점수를 10점 만점으로 매기세요:

1. **전체 품질 (quality_score)**: 분석의 전반적인 완성도와 유용성
2. **신학적 깊이 (theological_depth_score)**: 신학적 통찰과 해석의 깊이
3. **실천 적용성 (practical_application_score)**: 실제 설교에 적용 가능한 정도

각 점수는 1-10 사이의 정수로 제시하세요.
JSON 형식으로 응답하세요: {"quality": 8, "theological_depth": 9, "practical_application": 7}"""

        evaluation_user = f"""[성경 구절]
{reference}

[분석 내용]
{analysis_text[:2000]}

위 분석의 품질을 평가해주세요."""

        try:
            eval_completion = client.chat.completions.create(
                model="gpt-4o-mini",  # 빠른 평가를 위해 mini 사용
                messages=[
                    {"role": "system", "content": evaluation_system},
                    {"role": "user", "content": evaluation_user}
                ],
                temperature=0.3
            )

            eval_result = eval_completion.choices[0].message.content.strip()
            # JSON 파싱
            import json
            # ```json 태그 제거
            if '```json' in eval_result:
                eval_result = eval_result.split('```json')[1].split('```')[0].strip()
            elif '```' in eval_result:
                eval_result = eval_result.split('```')[1].split('```')[0].strip()

            scores = json.loads(eval_result)
            quality_score = scores.get("quality", 5)
            theological_depth_score = scores.get("theological_depth", 5)
            practical_application_score = scores.get("practical_application", 5)

            print(f"[STEP1-SAVE] 평가 완료 - 품질:{quality_score}, 신학:{theological_depth_score}, 적용:{practical_application_score}")
        except Exception as e:
            print(f"[STEP1-SAVE] 품질 평가 실패 (기본값 사용): {str(e)}")
            quality_score = 5
            theological_depth_score = 5
            practical_application_score = 5

        # DB에 저장
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 토큰 수는 대략적으로 계산 (영어는 4자당 1토큰, 한글은 2자당 1토큰 정도)
            estimated_tokens = len(analysis_text) // 3

            if USE_POSTGRES:
                cursor.execute('''
                    INSERT INTO step1_analyses
                    (reference, sermon_text, analysis_text, analysis_hash, category, style_name, step_name,
                     quality_score, theological_depth_score, practical_application_score, ai_model, analysis_tokens)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (reference, sermon_text, analysis_text, analysis_hash, category, style_name, step_name,
                      quality_score, theological_depth_score, practical_application_score, 'gpt-5', estimated_tokens))
            else:
                cursor.execute('''
                    INSERT INTO step1_analyses
                    (reference, sermon_text, analysis_text, analysis_hash, category, style_name, step_name,
                     quality_score, theological_depth_score, practical_application_score, ai_model, analysis_tokens)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (reference, sermon_text, analysis_text, analysis_hash, category, style_name, step_name,
                      quality_score, theological_depth_score, practical_application_score, 'gpt-5', estimated_tokens))

            conn.commit()
            conn.close()
            print(f"[STEP1-SAVE] DB 저장 완료 (해시: {analysis_hash[:8]}...)")
        except Exception as e:
            print(f"[STEP1-SAVE] DB 저장 실패: {str(e)}")

        return {"ok": True, "message": "Step1 분석 저장 완료", "isDuplicate": False}

    except Exception as e:
        print(f"[STEP1-SAVE][ERROR] {str(e)}")
        return {"ok": False, "message": f"저장 실패: {str(e)}"}


# ===== AI 챗봇 API =====
@app.route('/api/sermon/chat', methods=['POST'])
def api_sermon_chat():
    """설교 페이지 AI 챗봇 - 현재 작업 상황 및 오류에 대해 질문/답변"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "No data received"}), 400

        question = data.get("question", "")
        context = data.get("context", {})  # 현재 작업 상태
        selected_model = data.get("model", "gpt-4o-mini")  # 선택된 모델

        # 허용된 모델 목록
        allowed_models = ["gpt-4o-mini", "gpt-4o", "gpt-5"]
        if selected_model not in allowed_models:
            selected_model = "gpt-4o-mini"

        if not question:
            return jsonify({"ok": False, "error": "질문을 입력해주세요."}), 400

        print(f"[SERMON-CHAT] 모델: {selected_model}, 질문: {question[:100]}...")

        # 컨텍스트 구성
        context_text = ""

        # 현재 스텝 결과들
        if context.get("step1Result"):
            context_text += f"【Step1 결과 (본문 연구)】\n{context.get('step1Result', '')[:2000]}\n\n"

        if context.get("step2Result"):
            context_text += f"【Step2 결과 (설교 구조)】\n{context.get('step2Result', '')[:2000]}\n\n"

        if context.get("step3Result"):
            context_text += f"【Step3 결과 (설교문)】\n{context.get('step3Result', '')[:3000]}\n\n"

        # 입력 데이터
        if context.get("bibleVerse"):
            context_text += f"【성경 본문】\n{context.get('bibleVerse', '')}\n\n"

        if context.get("sermonStyle"):
            context_text += f"【설교 스타일】\n{context.get('sermonStyle', '')}\n\n"

        # 오류 정보
        if context.get("lastError"):
            context_text += f"【최근 오류】\n{context.get('lastError', '')}\n\n"

        # API 응답 정보
        if context.get("apiResponse"):
            context_text += f"【API 응답 정보】\n{context.get('apiResponse', '')}\n\n"

        # 시스템 프롬프트
        system_prompt = """당신은 설교문 작성 도구의 AI 어시스턴트입니다.
사용자가 설교문 작성 과정에서 겪는 문제나 질문에 답변합니다.

역할:
1. 현재 설교문 작성 상황 분석 및 설명
2. Step1(본문 연구), Step2(설교 구조), Step3(설교문 작성) 단계별 도움
3. 오류 발생 시 원인 분석 및 해결 방법 안내
4. API 오류, 크레딧 문제, 네트워크 오류 등 기술적 문제 해결 도움
5. 설교 내용에 대한 피드백 및 개선 제안

일반적인 오류 유형:
- Step3 크레딧 부족: 관리자에게 크레딧 충전 요청 필요
- API 타임아웃: 입력 내용이 너무 길거나 서버 부하
- 네트워크 오류: 인터넷 연결 확인 필요
- 모델 오류: 다른 AI 모델로 시도 권장

답변 시 유의사항:
- 기술적 문제는 구체적인 해결 방법을 안내하세요
- 설교 내용 관련 질문은 신학적으로 적절한 답변을 제공하세요
- 한국어로 친절하고 이해하기 쉽게 답변하세요"""

        # 사용자 메시지 구성
        user_content = ""
        if context_text:
            user_content += f"{context_text}\n"
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

        print(f"[SERMON-CHAT][SUCCESS] {selected_model}로 답변 생성 완료")
        return jsonify({"ok": True, "answer": answer, "usage": usage})

    except Exception as e:
        print(f"[SERMON-CHAT][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== 디자인 도우미 (현수막/배너 생성) =====

# 배너 템플릿 로드
def load_banner_templates():
    """배너 템플릿 JSON 파일 로드"""
    template_path = os.path.join(os.path.dirname(__file__), 'banner_templates.json')
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[BANNER] 템플릿 로드 실패: {e}")
        return None

@app.route('/api/banner/templates')
def get_banner_templates():
    """배너 템플릿 목록 반환"""
    templates = load_banner_templates()
    if templates:
        return jsonify({"ok": True, "data": templates})
    return jsonify({"ok": False, "error": "템플릿 로드 실패"}), 500

@app.route('/api/banner/generate', methods=['POST'])
def generate_banner():
    """현수막/배너 이미지 생성"""
    try:
        data = request.json
        model = data.get('model', 'dalle3')  # dalle3 또는 flux_pro
        template_type = data.get('template', 'general')
        layout = data.get('layout', 'horizontal')

        # 사용자 입력
        event_name = data.get('event_name', '')  # 행사명
        church_name = data.get('church_name', '')  # 교회명
        schedule = data.get('schedule', '')  # 일정
        speaker = data.get('speaker', '')  # 강사
        theme = data.get('theme', '')  # 주제/말씀
        custom_prompt = data.get('custom_prompt', '')  # 사용자 정의 프롬프트

        # 템플릿 로드
        templates = load_banner_templates()
        if not templates:
            return jsonify({"ok": False, "error": "템플릿 로드 실패"}), 500

        # 템플릿 정보 가져오기
        template_info = templates['templates'].get(template_type, templates['templates']['general'])
        layout_info = templates['layouts'].get(layout, templates['layouts']['horizontal'])
        model_info = templates['models'].get(model, templates['models']['dalle3'])

        # 이미지 생성 프롬프트 구성
        if custom_prompt:
            base_prompt = custom_prompt
        else:
            base_prompt = f"Create a beautiful church banner background for {template_info['name_en']}."
            if event_name:
                base_prompt += f" Event: {event_name}."
            if theme:
                base_prompt += f" Theme: {theme}."

        full_prompt = f"{base_prompt} Style: {template_info['prompt_style']}. "
        full_prompt += "The image should be atmospheric and suitable for text overlay. "
        full_prompt += "No text, letters, or words in the image. High quality, professional design, "
        full_prompt += "beautiful lighting, church-appropriate aesthetic."

        print(f"[BANNER] 생성 요청 - 모델: {model}, 템플릿: {template_type}, 레이아웃: {layout}")
        print(f"[BANNER] 프롬프트: {full_prompt[:100]}...")

        image_url = None

        if model == 'dalle3':
            # DALL-E 3 사용
            image_url = generate_with_dalle3(full_prompt, layout_info['dalle_size'])
        elif model == 'flux_pro':
            # Flux Pro 사용
            image_url = generate_with_flux_pro(full_prompt, layout_info['flux_aspect'])
        else:
            return jsonify({"ok": False, "error": f"지원하지 않는 모델: {model}"}), 400

        if image_url:
            print(f"[BANNER] 이미지 생성 성공")
            return jsonify({
                "ok": True,
                "image_url": image_url,
                "model": model_info['name'],
                "template": template_info['name'],
                "layout": layout_info['name'],
                "prompt_used": full_prompt
            })
        else:
            return jsonify({"ok": False, "error": "이미지 생성 실패"}), 500

    except Exception as e:
        print(f"[BANNER][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


def generate_with_dalle3(prompt, size="1792x1024"):
    """DALL-E 3로 이미지 생성"""
    try:
        print(f"[DALLE3] 이미지 생성 시작 - 크기: {size}")

        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality="standard",
            n=1
        )

        image_url = response.data[0].url
        print(f"[DALLE3] 이미지 생성 완료")
        return image_url

    except Exception as e:
        print(f"[DALLE3][ERROR] {str(e)}")
        raise e


def generate_with_flux_pro(prompt, aspect_ratio="16:9"):
    """Flux Pro (fal.ai)로 이미지 생성"""
    try:
        import fal_client

        # fal.ai API 키 확인
        fal_key = os.getenv("FAL_KEY")
        if not fal_key:
            raise RuntimeError("FAL_KEY가 설정되지 않았습니다. fal.ai에서 API 키를 발급받아 환경변수에 설정해주세요.")

        print(f"[FLUX_PRO] fal.ai 이미지 생성 시작 - 비율: {aspect_ratio}")

        # aspect_ratio를 fal.ai 형식으로 변환
        size_map = {
            "16:9": "landscape_16_9",
            "9:16": "portrait_16_9",
            "1:1": "square",
            "4:3": "landscape_4_3",
            "3:4": "portrait_4_3"
        }
        image_size = size_map.get(aspect_ratio, "landscape_16_9")

        # fal.ai Flux Dev 모델 호출
        result = fal_client.subscribe(
            "fal-ai/flux/dev",
            arguments={
                "prompt": prompt,
                "image_size": image_size,
                "num_inference_steps": 28,
                "guidance_scale": 3.5,
                "num_images": 1,
                "enable_safety_checker": True
            }
        )

        # 결과에서 이미지 URL 추출
        if result and 'images' in result and len(result['images']) > 0:
            image_url = result['images'][0]['url']
            print(f"[FLUX_PRO] fal.ai 이미지 생성 완료")
            return image_url
        else:
            raise RuntimeError("이미지 생성 결과가 없습니다.")

    except Exception as e:
        print(f"[FLUX_PRO][ERROR] {str(e)}")
        raise e


# ===== 한글 텍스트 오버레이 기능 =====

# 사용 가능한 폰트 목록
AVAILABLE_FONTS = {
    "nanum_gothic": {"name": "나눔고딕", "file": "NanumGothic.ttf", "bold": "NanumGothicBold.ttf"},
    "nanum_barun": {"name": "나눔바른고딕", "file": "NanumBarunGothic.ttf", "bold": "NanumBarunGothicBold.ttf"},
    "nanum_myeongjo": {"name": "나눔명조", "file": "NanumMyeongjo.ttf", "bold": "NanumMyeongjoBold.ttf"},
    "nanum_square": {"name": "나눔스퀘어", "file": "NanumSquareR.ttf", "bold": "NanumSquareB.ttf"},
    "nanum_square_round": {"name": "나눔스퀘어라운드", "file": "NanumSquareRoundR.ttf", "bold": "NanumSquareRoundB.ttf"}
}

def get_font_path(font_id, bold=False):
    """폰트 파일 경로 반환"""
    font_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    font_info = AVAILABLE_FONTS.get(font_id, AVAILABLE_FONTS['nanum_gothic'])
    font_file = font_info['bold'] if bold else font_info['file']
    return os.path.join(font_dir, font_file)

def add_text_overlay(image_url, texts, font_id="nanum_gothic"):
    """이미지에 한글 텍스트 오버레이 추가"""
    from PIL import Image, ImageDraw, ImageFont
    import requests
    from io import BytesIO
    import base64

    try:
        print(f"[TEXT_OVERLAY] 텍스트 오버레이 시작 - 폰트: {font_id}")

        # 이미지 다운로드
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert('RGBA')

        # 오버레이용 투명 레이어 생성
        overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        img_width, img_height = img.size

        # 텍스트 렌더링
        for text_item in texts:
            if not text_item.get('text'):
                continue

            text = text_item['text']
            position = text_item.get('position', 'center')  # top, center, bottom
            font_size = text_item.get('font_size', 60)
            color = text_item.get('color', '#FFFFFF')
            shadow = text_item.get('shadow', True)
            bold = text_item.get('bold', False)
            y_offset = text_item.get('y_offset', 0)  # 추가 Y 오프셋

            # 폰트 로드
            font_path = get_font_path(font_id, bold)
            try:
                font = ImageFont.truetype(font_path, font_size)
            except Exception as e:
                print(f"[TEXT_OVERLAY] 폰트 로드 실패, 기본 폰트 사용: {e}")
                font = ImageFont.load_default()

            # 텍스트 크기 계산
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # X 위치 (가운데 정렬)
            x = (img_width - text_width) // 2

            # Y 위치 계산
            if position == 'top':
                y = int(img_height * 0.1) + y_offset
            elif position == 'bottom':
                y = int(img_height * 0.75) + y_offset
            else:  # center
                y = (img_height - text_height) // 2 + y_offset

            # 색상 파싱
            if color.startswith('#'):
                r = int(color[1:3], 16)
                g = int(color[3:5], 16)
                b = int(color[5:7], 16)
                text_color = (r, g, b, 255)
            else:
                text_color = (255, 255, 255, 255)

            # 그림자 효과
            if shadow:
                shadow_offset = max(2, font_size // 20)
                shadow_color = (0, 0, 0, 180)
                draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color)

            # 텍스트 그리기
            draw.text((x, y), text, font=font, fill=text_color)

        # 이미지 합성
        result = Image.alpha_composite(img, overlay)
        result = result.convert('RGB')

        # Base64로 인코딩
        buffer = BytesIO()
        result.save(buffer, format='PNG', quality=95)
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        data_url = f"data:image/png;base64,{img_base64}"

        print(f"[TEXT_OVERLAY] 텍스트 오버레이 완료")
        return data_url

    except Exception as e:
        print(f"[TEXT_OVERLAY][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        # 오버레이 실패 시 원본 이미지 URL 반환
        return image_url


@app.route('/api/banner/fonts')
def get_available_fonts():
    """사용 가능한 폰트 목록 반환"""
    fonts = [{"id": k, "name": v["name"]} for k, v in AVAILABLE_FONTS.items()]
    return jsonify({"ok": True, "fonts": fonts})


@app.route('/api/banner/generate-with-text', methods=['POST'])
def generate_banner_with_text():
    """현수막/배너 이미지 생성 + 한글 텍스트 오버레이"""
    try:
        data = request.json
        model = data.get('model', 'dalle3')
        template_type = data.get('template', 'general')
        layout = data.get('layout', 'horizontal')
        custom_prompt = data.get('custom_prompt', '')

        # 텍스트 오버레이 설정
        add_text = data.get('add_text', False)
        font_id = data.get('font_id', 'nanum_gothic')
        event_name = data.get('event_name', '')
        church_name = data.get('church_name', '')
        schedule = data.get('schedule', '')
        speaker = data.get('speaker', '')
        theme = data.get('theme', '')

        # 템플릿 로드
        templates = load_banner_templates()
        if not templates:
            return jsonify({"ok": False, "error": "템플릿 로드 실패"}), 500

        template_info = templates['templates'].get(template_type, templates['templates']['general'])
        layout_info = templates['layouts'].get(layout, templates['layouts']['horizontal'])
        model_info = templates['models'].get(model, templates['models']['dalle3'])

        # 참조 이미지 스타일 정보 가져오기
        ref_style = get_reference_style_description(template_type)
        style_enhancement = ""
        if ref_style:
            if ref_style.get('tags'):
                style_enhancement += f" Design style: {', '.join(ref_style['tags'][:5])}."
            if ref_style.get('colors'):
                style_enhancement += f" Color palette inspiration: {', '.join(ref_style['colors'][:3])}."
            if ref_style.get('descriptions'):
                style_enhancement += f" Reference: {ref_style['descriptions'][0][:100]}."
            print(f"[BANNER] 참조 스타일 적용: {len(ref_style.get('tags', []))}개 태그, {len(ref_style.get('colors', []))}개 색상")

        # 이미지 생성 프롬프트 구성
        if custom_prompt:
            base_prompt = custom_prompt
        else:
            base_prompt = f"Create a beautiful Korean church banner background for {template_info['name_en']}."
            if event_name:
                base_prompt += f" Event theme: {event_name}."
            if theme:
                base_prompt += f" Message: {theme}."

        full_prompt = f"{base_prompt} Style: {template_info['prompt_style']}. "
        full_prompt += style_enhancement  # 참조 스타일 추가
        full_prompt += "Modern, clean, professional Korean church banner design. "
        full_prompt += "Soft gradient background with elegant composition. "
        full_prompt += "The image should be atmospheric and suitable for text overlay. "
        full_prompt += "No text, letters, or words in the image. High quality, professional design, "
        full_prompt += "beautiful lighting, church-appropriate aesthetic. Leave clear space in center for text overlay."

        print(f"[BANNER] 생성 요청 - 모델: {model}, 텍스트 오버레이: {add_text}")

        # 이미지 생성
        image_url = None
        if model == 'dalle3':
            image_url = generate_with_dalle3(full_prompt, layout_info['dalle_size'])
        elif model == 'flux_pro':
            image_url = generate_with_flux_pro(full_prompt, layout_info['flux_aspect'])
        else:
            return jsonify({"ok": False, "error": f"지원하지 않는 모델: {model}"}), 400

        if not image_url:
            return jsonify({"ok": False, "error": "이미지 생성 실패"}), 500

        # 텍스트 오버레이 적용
        final_image_url = image_url
        if add_text:
            texts = []

            # 행사명 (상단)
            if event_name:
                texts.append({
                    "text": event_name,
                    "position": "top",
                    "font_size": 80,
                    "color": "#FFFFFF",
                    "bold": True,
                    "shadow": True,
                    "y_offset": 20
                })

            # 주제/말씀 (중앙)
            if theme:
                texts.append({
                    "text": theme,
                    "position": "center",
                    "font_size": 60,
                    "color": "#FFD700",
                    "bold": True,
                    "shadow": True,
                    "y_offset": 0
                })

            # 일정 (중앙 아래)
            if schedule:
                texts.append({
                    "text": schedule,
                    "position": "center",
                    "font_size": 45,
                    "color": "#FFFFFF",
                    "bold": False,
                    "shadow": True,
                    "y_offset": 80
                })

            # 강사 (하단)
            if speaker:
                texts.append({
                    "text": speaker,
                    "position": "bottom",
                    "font_size": 50,
                    "color": "#FFFFFF",
                    "bold": False,
                    "shadow": True,
                    "y_offset": -60
                })

            # 교회명 (하단)
            if church_name:
                texts.append({
                    "text": church_name,
                    "position": "bottom",
                    "font_size": 55,
                    "color": "#FFFFFF",
                    "bold": True,
                    "shadow": True,
                    "y_offset": 20
                })

            if texts:
                final_image_url = add_text_overlay(image_url, texts, font_id)

        print(f"[BANNER] 이미지 생성 완료")
        return jsonify({
            "ok": True,
            "image_url": final_image_url,
            "original_url": image_url,
            "model": model_info['name'],
            "template": template_info['name'],
            "layout": layout_info['name'],
            "text_added": add_text,
            "font": AVAILABLE_FONTS.get(font_id, {}).get('name', '나눔고딕')
        })

    except Exception as e:
        print(f"[BANNER][ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/banner/generate-prompt', methods=['POST'])
def generate_banner_prompt():
    """GPT를 사용하여 현수막용 이미지 프롬프트 생성"""
    try:
        data = request.json
        template_type = data.get('template', 'general')
        event_name = data.get('event_name', '')
        theme = data.get('theme', '')
        mood = data.get('mood', '')  # 분위기 (따뜻한, 경건한, 활기찬 등)

        # 템플릿 정보 로드
        templates = load_banner_templates()
        template_info = templates['templates'].get(template_type, templates['templates']['general'])

        system_prompt = """당신은 교회 현수막/배너 디자인을 위한 이미지 프롬프트 전문가입니다.
사용자가 제공한 정보를 바탕으로 AI 이미지 생성에 최적화된 영어 프롬프트를 작성해주세요.

규칙:
1. 프롬프트는 반드시 영어로 작성
2. 이미지에 텍스트/글자가 포함되지 않도록 명시
3. 교회에 적합한 경건하고 아름다운 분위기
4. 배경 이미지로 적합하게 (텍스트 오버레이 공간 확보)
5. 고품질, 전문적인 디자인 스타일"""

        user_prompt = f"""다음 정보로 현수막 배경 이미지 프롬프트를 생성해주세요:

행사 유형: {template_info['name']} ({template_info['name_en']})
행사명: {event_name if event_name else '미지정'}
주제/말씀: {theme if theme else '미지정'}
분위기: {mood if mood else template_info['prompt_style']}

기본 스타일 참고: {template_info['prompt_style']}

프롬프트만 출력해주세요 (설명 없이)."""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )

        generated_prompt = completion.choices[0].message.content.strip()

        return jsonify({
            "ok": True,
            "prompt": generated_prompt,
            "template": template_info['name']
        })

    except Exception as e:
        print(f"[BANNER-PROMPT][ERROR] {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== 현수막 참조 이미지 관리 API =====

@app.route('/api/banner/references', methods=['GET'])
def get_banner_references():
    """참조 이미지 목록 조회"""
    try:
        template_type = request.args.get('template', None)

        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            if template_type:
                cursor.execute('''
                    SELECT id, image_url, template_type, title, description,
                           color_palette, style_tags, quality_score, use_count, created_at
                    FROM banner_references
                    WHERE is_active = 1 AND template_type = %s
                    ORDER BY quality_score DESC, use_count DESC
                ''', (template_type,))
            else:
                cursor.execute('''
                    SELECT id, image_url, template_type, title, description,
                           color_palette, style_tags, quality_score, use_count, created_at
                    FROM banner_references
                    WHERE is_active = 1
                    ORDER BY quality_score DESC, use_count DESC
                ''')
        else:
            if template_type:
                cursor.execute('''
                    SELECT id, image_url, template_type, title, description,
                           color_palette, style_tags, quality_score, use_count, created_at
                    FROM banner_references
                    WHERE is_active = 1 AND template_type = ?
                    ORDER BY quality_score DESC, use_count DESC
                ''', (template_type,))
            else:
                cursor.execute('''
                    SELECT id, image_url, template_type, title, description,
                           color_palette, style_tags, quality_score, use_count, created_at
                    FROM banner_references
                    WHERE is_active = 1
                    ORDER BY quality_score DESC, use_count DESC
                ''')

        rows = cursor.fetchall()
        conn.close()

        references = []
        for row in rows:
            references.append({
                'id': row['id'],
                'image_url': row['image_url'],
                'template_type': row['template_type'],
                'title': row['title'],
                'description': row['description'],
                'color_palette': row['color_palette'],
                'style_tags': row['style_tags'],
                'quality_score': row['quality_score'],
                'use_count': row['use_count'],
                'created_at': str(row['created_at']) if row['created_at'] else None
            })

        return jsonify({"ok": True, "references": references, "count": len(references)})

    except Exception as e:
        print(f"[BANNER-REF][ERROR] 조회 실패: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/banner/references', methods=['POST'])
def add_banner_reference():
    """참조 이미지 추가"""
    try:
        data = request.json
        image_url = data.get('image_url')
        template_type = data.get('template_type', 'general')
        title = data.get('title', '')
        description = data.get('description', '')
        style_tags = data.get('style_tags', '')

        if not image_url:
            return jsonify({"ok": False, "error": "이미지 URL이 필요합니다."}), 400

        # 이미지 URL 유효성 검사 및 색상 추출 시도
        color_palette = ''
        try:
            # 이미지를 다운로드하여 주요 색상 추출
            response = requests.get(image_url, timeout=10)
            if response.status_code == 200:
                img = Image.open(io.BytesIO(response.content))
                img_small = img.resize((100, 100))
                colors = img_small.convert('RGB').getcolors(10000)
                if colors:
                    # 가장 많이 사용된 상위 5개 색상 추출
                    sorted_colors = sorted(colors, key=lambda x: x[0], reverse=True)[:5]
                    hex_colors = ['#{:02x}{:02x}{:02x}'.format(c[1][0], c[1][1], c[1][2]) for c in sorted_colors]
                    color_palette = ','.join(hex_colors)
        except Exception as color_error:
            print(f"[BANNER-REF] 색상 추출 실패 (무시): {str(color_error)}")

        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                INSERT INTO banner_references (image_url, template_type, title, description, color_palette, style_tags)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (image_url, template_type, title, description, color_palette, style_tags))
            new_id = cursor.fetchone()['id']
        else:
            cursor.execute('''
                INSERT INTO banner_references (image_url, template_type, title, description, color_palette, style_tags)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (image_url, template_type, title, description, color_palette, style_tags))
            new_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return jsonify({
            "ok": True,
            "message": "참조 이미지가 추가되었습니다.",
            "id": new_id,
            "color_palette": color_palette
        })

    except Exception as e:
        print(f"[BANNER-REF][ERROR] 추가 실패: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/banner/references/<int:ref_id>', methods=['DELETE'])
def delete_banner_reference(ref_id):
    """참조 이미지 삭제 (비활성화)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('UPDATE banner_references SET is_active = 0 WHERE id = %s', (ref_id,))
        else:
            cursor.execute('UPDATE banner_references SET is_active = 0 WHERE id = ?', (ref_id,))

        conn.commit()
        conn.close()

        return jsonify({"ok": True, "message": "참조 이미지가 삭제되었습니다."})

    except Exception as e:
        print(f"[BANNER-REF][ERROR] 삭제 실패: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/banner/references/<int:ref_id>/rate', methods=['POST'])
def rate_banner_reference(ref_id):
    """참조 이미지 품질 점수 업데이트"""
    try:
        data = request.json
        score = data.get('score', 5)

        if not 1 <= score <= 10:
            return jsonify({"ok": False, "error": "점수는 1-10 사이여야 합니다."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('UPDATE banner_references SET quality_score = %s WHERE id = %s', (score, ref_id))
        else:
            cursor.execute('UPDATE banner_references SET quality_score = ? WHERE id = ?', (score, ref_id))

        conn.commit()
        conn.close()

        return jsonify({"ok": True, "message": "점수가 업데이트되었습니다."})

    except Exception as e:
        print(f"[BANNER-REF][ERROR] 점수 업데이트 실패: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


def get_reference_style_description(template_type):
    """참조 이미지들의 스타일 설명 생성 (AI 프롬프트용)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if USE_POSTGRES:
            cursor.execute('''
                SELECT style_tags, color_palette, description
                FROM banner_references
                WHERE is_active = 1 AND template_type = %s
                ORDER BY quality_score DESC, use_count DESC
                LIMIT 5
            ''', (template_type,))
        else:
            cursor.execute('''
                SELECT style_tags, color_palette, description
                FROM banner_references
                WHERE is_active = 1 AND template_type = ?
                ORDER BY quality_score DESC, use_count DESC
                LIMIT 5
            ''', (template_type,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return None

        # 스타일 태그와 색상 팔레트 수집
        all_tags = []
        all_colors = []
        descriptions = []

        for row in rows:
            if row['style_tags']:
                all_tags.extend(row['style_tags'].split(','))
            if row['color_palette']:
                all_colors.extend(row['color_palette'].split(','))
            if row['description']:
                descriptions.append(row['description'])

        # 중복 제거 및 빈도순 정렬
        from collections import Counter
        tag_counts = Counter(all_tags)
        top_tags = [tag for tag, _ in tag_counts.most_common(10)]

        color_counts = Counter(all_colors)
        top_colors = [color for color, _ in color_counts.most_common(5)]

        style_desc = {
            'tags': top_tags,
            'colors': top_colors,
            'descriptions': descriptions[:3]
        }

        return style_desc

    except Exception as e:
        print(f"[BANNER-REF][ERROR] 스타일 설명 생성 실패: {str(e)}")
        return None


# ===== 이미지 크롤링 API =====

@app.route('/api/banner/crawl', methods=['POST'])
def crawl_banner_images():
    """웹사이트에서 이미지 URL 크롤링"""
    try:
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin, urlparse

        data = request.json
        target_url = data.get('url', '').strip()
        min_width = data.get('min_width', 200)  # 최소 이미지 너비
        min_height = data.get('min_height', 100)  # 최소 이미지 높이

        if not target_url:
            return jsonify({"ok": False, "error": "URL을 입력해주세요."}), 400

        if not target_url.startswith(('http://', 'https://')):
            target_url = 'https://' + target_url

        print(f"[CRAWL] 크롤링 시작: {target_url}")

        # 웹페이지 가져오기
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        }

        response = requests.get(target_url, headers=headers, timeout=30)
        response.raise_for_status()

        # HTML 파싱
        soup = BeautifulSoup(response.text, 'html.parser')
        base_url = f"{urlparse(target_url).scheme}://{urlparse(target_url).netloc}"

        # 이미지 URL 추출
        images = []
        seen_urls = set()

        # 1. <img> 태그에서 이미지 추출
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src:
                full_url = urljoin(target_url, src)
                if full_url not in seen_urls and is_valid_image_url(full_url):
                    seen_urls.add(full_url)
                    images.append({
                        'url': full_url,
                        'alt': img.get('alt', ''),
                        'source': 'img'
                    })

        # 2. background-image 스타일에서 이미지 추출
        for elem in soup.find_all(style=True):
            style = elem.get('style', '')
            urls = re.findall(r'url\(["\']?([^"\')\s]+)["\']?\)', style)
            for url in urls:
                full_url = urljoin(target_url, url)
                if full_url not in seen_urls and is_valid_image_url(full_url):
                    seen_urls.add(full_url)
                    images.append({
                        'url': full_url,
                        'alt': '',
                        'source': 'background'
                    })

        # 3. <a> 태그 내 이미지 링크 (고해상도 이미지)
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            if is_valid_image_url(href):
                full_url = urljoin(target_url, href)
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    images.append({
                        'url': full_url,
                        'alt': a.get('title', ''),
                        'source': 'link'
                    })

        # 이미지 유효성 검사 및 크기 필터링 (병렬 처리)
        valid_images = []
        for img_data in images[:50]:  # 최대 50개까지만 처리
            try:
                # HEAD 요청으로 빠르게 확인
                head_resp = requests.head(img_data['url'], headers=headers, timeout=5, allow_redirects=True)
                content_type = head_resp.headers.get('content-type', '')
                if 'image' in content_type:
                    valid_images.append(img_data)
            except:
                # HEAD 실패 시 그냥 추가 (나중에 로드 시 확인)
                if img_data['url'].lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    valid_images.append(img_data)

        print(f"[CRAWL] 완료: {len(valid_images)}개 이미지 발견")

        return jsonify({
            "ok": True,
            "url": target_url,
            "images": valid_images,
            "count": len(valid_images)
        })

    except requests.exceptions.RequestException as e:
        print(f"[CRAWL][ERROR] 요청 실패: {str(e)}")
        return jsonify({"ok": False, "error": f"웹페이지 접근 실패: {str(e)}"}), 400
    except Exception as e:
        print(f"[CRAWL][ERROR] 크롤링 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


def is_valid_image_url(url):
    """이미지 URL 유효성 검사"""
    if not url:
        return False

    # 데이터 URL 제외
    if url.startswith('data:'):
        return False

    # 너무 작은 이미지 (아이콘 등) 제외
    excluded_patterns = [
        'icon', 'logo', 'favicon', 'sprite', 'button', 'arrow',
        'loading', 'spinner', 'placeholder', 'blank', 'pixel',
        '1x1', 'spacer', 'transparent'
    ]
    url_lower = url.lower()
    for pattern in excluded_patterns:
        if pattern in url_lower:
            return False

    # 일반적인 이미지 확장자 또는 이미지 서비스 URL
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
    image_services = ('images', 'img', 'photo', 'upload', 'cdn', 'media')

    if any(url_lower.endswith(ext) for ext in image_extensions):
        return True
    if any(service in url_lower for service in image_services):
        return True

    return True  # 확실하지 않으면 일단 포함


@app.route('/api/banner/references/bulk', methods=['POST'])
def bulk_add_banner_references():
    """참조 이미지 일괄 추가"""
    try:
        data = request.json
        images = data.get('images', [])
        template_type = data.get('template_type', 'general')
        style_tags = data.get('style_tags', '')

        if not images:
            return jsonify({"ok": False, "error": "추가할 이미지가 없습니다."}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        added_count = 0
        failed_count = 0

        for img in images:
            try:
                image_url = img.get('url', '')
                if not image_url:
                    continue

                # 색상 추출 시도
                color_palette = ''
                try:
                    response = requests.get(image_url, timeout=10)
                    if response.status_code == 200:
                        img_obj = Image.open(io.BytesIO(response.content))
                        img_small = img_obj.resize((100, 100))
                        colors = img_small.convert('RGB').getcolors(10000)
                        if colors:
                            sorted_colors = sorted(colors, key=lambda x: x[0], reverse=True)[:5]
                            hex_colors = ['#{:02x}{:02x}{:02x}'.format(c[1][0], c[1][1], c[1][2]) for c in sorted_colors]
                            color_palette = ','.join(hex_colors)
                except Exception as color_error:
                    pass  # 색상 추출 실패해도 계속 진행

                description = img.get('alt', '')

                if USE_POSTGRES:
                    cursor.execute('''
                        INSERT INTO banner_references (image_url, template_type, title, description, color_palette, style_tags)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (image_url, template_type, '', description, color_palette, style_tags))
                else:
                    cursor.execute('''
                        INSERT INTO banner_references (image_url, template_type, title, description, color_palette, style_tags)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (image_url, template_type, '', description, color_palette, style_tags))

                added_count += 1

            except Exception as e:
                print(f"[BULK-ADD] 이미지 추가 실패: {str(e)}")
                failed_count += 1

        conn.commit()
        conn.close()

        print(f"[BULK-ADD] 완료: {added_count}개 추가, {failed_count}개 실패")

        return jsonify({
            "ok": True,
            "message": f"{added_count}개 이미지가 추가되었습니다.",
            "added": added_count,
            "failed": failed_count
        })

    except Exception as e:
        print(f"[BULK-ADD][ERROR] 일괄 추가 실패: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ===== Render 배포를 위한 설정 =====
if __name__ == "__main__":
    # 데이터베이스 연결 상태 로그 출력
    print("=" * 50)
    print("🚀 Sermon Server Starting...")
    print("=" * 50)

    if USE_POSTGRES:
        print("✅ PostgreSQL 사용 중")
        print(f"   DATABASE_URL 설정됨: {DATABASE_URL[:30]}..." if DATABASE_URL else "")
    else:
        print("⚠️  SQLite 사용 중 (로컬 개발 모드)")
        print(f"   DB 파일: {DB_PATH}")
        print("   경고: Render에서는 서버 재시작 시 데이터가 초기화됩니다!")
        print("   → DATABASE_URL 환경변수를 설정해주세요.")

    print("=" * 50)

    port = int(os.environ.get("PORT", 5058))
    app.run(host="0.0.0.0", port=port, debug=False)
