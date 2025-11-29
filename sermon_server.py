import os
import re
import json
import sqlite3
import hashlib
import requests as http_requests
import io
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from openai import OpenAI

# ===== 모듈화된 함수 (sermon_modules) =====
# 다음 함수들은 sermon_modules에서 import하여 사용 가능합니다:
# - from sermon_modules.db import get_db_connection, init_db, get_setting, set_setting, USE_POSTGRES
# - from sermon_modules.utils import calculate_cost, format_json_result, remove_markdown
# - from sermon_modules.auth import login_required, admin_required, api_login_required
# - from sermon_modules.auth import get_user_credits, use_credit, add_credits, set_credits
# - from sermon_modules.prompt import get_system_prompt_for_step, build_prompt_from_json

# ===== API Blueprint (sermon_modules.api_sermon) =====
from sermon_modules.api_sermon import api_sermon_bp, init_sermon_api

# ===== Education Blueprint =====
from education_server import education_bp, init_education_api

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

# ===== API Blueprint 초기화 및 등록 =====
init_sermon_api(client)
app.register_blueprint(api_sermon_bp)

# ===== Education Blueprint 초기화 및 등록 =====
init_education_api(client)
app.register_blueprint(education_bp)

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
    Step3용 프롬프트 생성 - Step3 지침, Step1/Step2 JSON 결과와 meta 데이터 통합

    json_guide: Step3 스타일별 지침 (priority_order, use_from_step1, use_from_step2, writing_rules 등)
    meta_data: 사용자 입력 정보 (scripture, title, target, worship_type, duration 등)
    step1_result: Step1 JSON 결과
    step2_result: Step2 JSON 결과 (writing_spec 포함)
    """
    # 분량과 예배유형 추출
    duration = meta_data.get("duration", "")
    worship_type = meta_data.get("worship_type", "")
    special_notes = meta_data.get("special_notes", "")

    prompt = ""

    # ═══════════════════════════════════════════════════════
    # 1. 최우선 지침: 홈화면 설정 (meta_override)
    # ═══════════════════════════════════════════════════════
    prompt += "=" * 60 + "\n"
    prompt += "【 ★★★ 1순위: 홈화면 설정 (최우선) ★★★ 】\n"
    prompt += "=" * 60 + "\n"

    if duration:
        prompt += f"\n🚨 분량: {duration}\n"
        prompt += f"   → 이 설교는 반드시 {duration} 분량으로 작성하세요.\n"
        prompt += f"   → Step1/Step2 자료가 길더라도 {duration}에 맞춰 압축하세요.\n"
        prompt += "   → 분량 제한은 다른 모든 지침보다 우선합니다.\n"

    if worship_type:
        prompt += f"\n🚨 예배/집회 유형: {worship_type}\n"
        prompt += f"   → '{worship_type}'에 적합한 톤과 내용으로 작성하세요.\n"

    if special_notes:
        prompt += f"\n🚨 특별 참고 사항:\n"
        prompt += f"   {special_notes}\n"
        prompt += "   → 위 내용을 설교문에 반드시 반영하세요.\n"

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

    prompt += "\n▶ 기본 정보\n"
    for key, value in meta_data.items():
        if value and key != "special_notes":
            label = key_labels.get(key, key)
            prompt += f"  - {label}: {value}\n"
    prompt += "\n"

    # ═══════════════════════════════════════════════════════
    # 2. Step3 스타일별 지침 적용
    # ═══════════════════════════════════════════════════════
    if json_guide and isinstance(json_guide, dict):
        prompt += "=" * 60 + "\n"
        prompt += "【 ★★ 스타일별 작성 지침 ★★ 】\n"
        prompt += "=" * 60 + "\n\n"

        # 우선순위 표시
        priority_order = json_guide.get("priority_order", {})
        if priority_order:
            prompt += "▶ 우선순위\n"
            for key, value in priority_order.items():
                prompt += f"  {key}: {value}\n"
            prompt += "\n"

        # Step1 활용 지침
        use_from_step1 = json_guide.get("use_from_step1", {})
        if use_from_step1:
            prompt += "▶ Step1 자료 활용법 (반드시 적용)\n"
            for field, config in use_from_step1.items():
                if isinstance(config, dict):
                    instruction = config.get("instruction", "")
                    format_hint = config.get("format", "")
                    prompt += f"  • {field}: {instruction}\n"
                    if format_hint:
                        prompt += f"    (형식: {format_hint})\n"
                else:
                    prompt += f"  • {field}: {config}\n"
            prompt += "\n"

        # Step2 활용 지침
        use_from_step2 = json_guide.get("use_from_step2", {})
        if use_from_step2:
            prompt += "▶ Step2 구조 활용법 (반드시 적용)\n"
            for field, config in use_from_step2.items():
                if isinstance(config, dict):
                    instruction = config.get("instruction", "")
                    priority = config.get("priority", "")
                    prompt += f"  • {field}: {instruction}"
                    if priority:
                        prompt += f" [{priority}]"
                    prompt += "\n"
                else:
                    prompt += f"  • {field}: {config}\n"
            prompt += "\n"

        # 작성 규칙
        writing_rules = json_guide.get("writing_rules", {})
        if writing_rules:
            prompt += "▶ 작성 규칙\n"
            for rule_name, rule_config in writing_rules.items():
                if isinstance(rule_config, dict):
                    label = rule_config.get("label", rule_name)
                    rules = rule_config.get("rules", [])
                    prompt += f"  [{label}]\n"
                    for rule in rules:
                        prompt += f"    - {rule}\n"
                else:
                    prompt += f"  • {rule_name}: {rule_config}\n"
            prompt += "\n"

    # ═══════════════════════════════════════════════════════
    # 3. Step2 필수 반영: 설교 구조
    # ═══════════════════════════════════════════════════════
    prompt += "=" * 60 + "\n"
    prompt += "【 ★★ 2순위: Step2 설교 구조 (필수 반영) ★★ 】\n"
    prompt += "=" * 60 + "\n\n"

    if step2_result and isinstance(step2_result, dict):
        # writing_spec 먼저 표시
        writing_spec = step2_result.get("writing_spec", {})
        if writing_spec:
            prompt += "▶ 작성 규격\n"
            for key, value in writing_spec.items():
                if key == "length" and duration:
                    prompt += f"  - {key}: {value} (※ 홈화면 '{duration}'이 우선)\n"
                elif isinstance(value, list):
                    prompt += f"  - {key}: {', '.join(str(v) for v in value)}\n"
                else:
                    prompt += f"  - {key}: {value}\n"
            prompt += "\n"

        # 핵심 구조 필드 강조
        sermon_outline = step2_result.get("sermon_outline")
        if sermon_outline:
            prompt += "▶ 설교 구조 (이 구조를 반드시 따르세요!)\n"
            if isinstance(sermon_outline, dict):
                prompt += json.dumps(sermon_outline, ensure_ascii=False, indent=2)
            elif isinstance(sermon_outline, list):
                for item in sermon_outline:
                    prompt += f"  {item}\n"
            else:
                prompt += f"  {sermon_outline}\n"
            prompt += "\n\n"

        # detailed_points 강조
        detailed_points = step2_result.get("detailed_points")
        if detailed_points:
            prompt += "▶ 상세 구조 (각 대지/소대지 내용을 확장하세요)\n"
            prompt += json.dumps(detailed_points, ensure_ascii=False, indent=2)
            prompt += "\n\n"

        # 나머지 Step2 필드
        excluded_keys = {"writing_spec", "sermon_outline", "detailed_points"}
        other_step2 = {k: v for k, v in step2_result.items() if k not in excluded_keys}
        if other_step2:
            prompt += "▶ Step2 기타 자료\n"
            prompt += json.dumps(other_step2, ensure_ascii=False, indent=2)
            prompt += "\n\n"
    else:
        prompt += "(Step2 결과 없음)\n\n"

    # ═══════════════════════════════════════════════════════
    # 4. Step1 참고 활용: 분석 자료
    # ═══════════════════════════════════════════════════════
    prompt += "=" * 60 + "\n"
    prompt += "【 3순위: Step1 분석 자료 (참고 활용) 】\n"
    prompt += "=" * 60 + "\n\n"

    if step1_result and isinstance(step1_result, dict):
        # 핵심 필드 강조
        key_terms = step1_result.get("key_terms")
        if key_terms:
            prompt += "▶ 핵심 단어 (원어 의미를 설교에 녹여내세요)\n"
            prompt += json.dumps(key_terms, ensure_ascii=False, indent=2)
            prompt += "\n\n"

        cross_references = step1_result.get("cross_references")
        if cross_references:
            prompt += "▶ 보충 성경구절 (적절히 인용하세요)\n"
            prompt += json.dumps(cross_references, ensure_ascii=False, indent=2)
            prompt += "\n\n"

        logical_flow = step1_result.get("logical_flow")
        if logical_flow:
            prompt += "▶ 논리적 전개 흐름\n"
            prompt += f"  {logical_flow}\n\n"

        # 나머지 Step1 필드
        excluded_keys = {"key_terms", "cross_references", "logical_flow"}
        other_step1 = {k: v for k, v in step1_result.items() if k not in excluded_keys}
        if other_step1:
            prompt += "▶ Step1 기타 분석 자료\n"
            prompt += json.dumps(other_step1, ensure_ascii=False, indent=2)
            prompt += "\n\n"
    else:
        prompt += "(Step1 결과 없음)\n\n"

    # ═══════════════════════════════════════════════════════
    # 5. 최종 작성 지침
    # ═══════════════════════════════════════════════════════
    prompt += "=" * 60 + "\n"
    prompt += "【 최종 작성 지침 】\n"
    prompt += "=" * 60 + "\n"
    prompt += "위 자료를 활용하여 설교문을 작성하세요.\n\n"
    prompt += "✅ 필수 체크리스트:\n"
    if duration:
        prompt += f"  □ 분량: {duration} (절대 초과 금지)\n"
    if step2_result:
        prompt += "  □ Step2의 설교 구조(대지/소대지)를 그대로 따름\n"
        prompt += "  □ Step2의 보충 성경구절(supporting_verses)을 인용\n"
    if step1_result:
        prompt += "  □ Step1의 핵심 단어(key_terms) 원어 의미 활용\n"
        prompt += "  □ Step1의 보충 구절(cross_references) 적절히 인용\n"
    prompt += "  □ 대지 간 연결 문장 포함\n"
    prompt += "  □ 마크다운 기호 없이 순수 텍스트로 작성\n"

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

# ===== 설교 API는 sermon_modules.api_sermon Blueprint로 이동됨 =====
# /api/sermon/process, /api/sermon/meditation, /api/sermon/gpt-pro,
# /api/sermon/qa, /api/sermon/recommend-scripture, /api/sermon/chat
# 위 라우트들은 api_sermon_bp Blueprint에서 처리됩니다.


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
        response = http_requests.get(image_url, timeout=30)
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
            response = http_requests.get(image_url, timeout=10)
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

        response = http_requests.get(target_url, headers=headers, timeout=30)
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
                head_resp = http_requests.head(img_data['url'], headers=headers, timeout=5, allow_redirects=True)
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

    except http_requests.exceptions.RequestException as e:
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
                    response = http_requests.get(image_url, timeout=10)
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
