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
    prompt = "【 설교문 작성 지침 】\n\n"

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

    # 분량 강조 (duration이 있으면 명확히 지시)
    duration = meta_data.get("duration", "")
    if duration:
        prompt += f"⚠️ 중요: 설교문 분량은 반드시 {duration} 분량으로 작성하세요.\n\n"

    # 예배 유형 강조 (worship_type이 있으면 명확히 지시)
    worship_type = meta_data.get("worship_type", "")
    if worship_type:
        prompt += f"⚠️ 중요: 이 설교는 '{worship_type}' 예배/집회용입니다. 해당 상황과 분위기에 맞게 작성하세요.\n\n"

    # Step2의 writing_spec 적용
    if step2_result and isinstance(step2_result, dict):
        writing_spec = step2_result.get("writing_spec", {})
        if writing_spec:
            prompt += "▶ 작성 규격\n"
            for key, value in writing_spec.items():
                if isinstance(value, list):
                    prompt += f"  - {key}: {', '.join(value)}\n"
                else:
                    prompt += f"  - {key}: {value}\n"
            prompt += "\n"

    # Step1 분석 자료
    if step1_result:
        prompt += "▶ Step1 분석 자료\n"
        if isinstance(step1_result, dict):
            prompt += json.dumps(step1_result, ensure_ascii=False, indent=2)
        else:
            prompt += str(step1_result)
        prompt += "\n\n"

    # Step2 구조
    if step2_result:
        prompt += "▶ Step2 설교 구조\n"
        if isinstance(step2_result, dict):
            # writing_spec은 이미 위에서 처리했으므로 제외
            step2_without_spec = {k: v for k, v in step2_result.items() if k != "writing_spec"}
            prompt += json.dumps(step2_without_spec, ensure_ascii=False, indent=2)
        else:
            prompt += str(step2_result)
        prompt += "\n\n"

    prompt += "위 자료를 바탕으로 설교문을 작성하세요. Step2의 구조와 writing_spec을 반드시 따르세요."

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
                    "category": category
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
