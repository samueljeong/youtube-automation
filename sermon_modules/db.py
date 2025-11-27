"""
sermon_modules/db.py
데이터베이스 연결 및 초기화

PostgreSQL (프로덕션) 또는 SQLite (개발) 지원
"""

import os
import sqlite3

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None

# 모듈 로드 시점에 데이터베이스 상태 로그 출력
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
    safe_url = DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL[:50]
    print(f"[SERMON-DB]    Host: {safe_url}")

    def get_db_connection():
        """Create a PostgreSQL database connection"""
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
else:
    # SQLite 사용 (로컬 개발용)
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sermon_data.db')

    print("[SERMON-DB] ⚠️  SQLite 사용 중 (로컬 개발 모드)")
    print(f"[SERMON-DB]    DB 파일: {DB_PATH}")
    print("[SERMON-DB]    경고: Render에서는 서버 재시작 시 데이터가 초기화됩니다!")

    def get_db_connection():
        """Create a SQLite database connection"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

print("=" * 50)


def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        # PostgreSQL 테이블 생성
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

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sermon_settings (
                id SERIAL PRIMARY KEY,
                setting_key VARCHAR(100) UNIQUE NOT NULL,
                setting_value VARCHAR(255) NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            INSERT INTO sermon_settings (setting_key, setting_value, description)
            VALUES ('default_step3_credits', '3', '신규 회원 기본 Step3 크레딧')
            ON CONFLICT (setting_key) DO NOTHING
        ''')

        conn.commit()

        # step3_credits 컬럼 추가 (이미 있으면 무시)
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

        # 벤치마크 분석 테이블
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

        # step1_analyses 테이블
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

        # 배너 참조 이미지 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banner_reference_images (
                id SERIAL PRIMARY KEY,
                image_url TEXT NOT NULL,
                template_type VARCHAR(50),
                style_tags TEXT,
                color_palette TEXT,
                description TEXT,
                quality_score INTEGER DEFAULT 5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # API 사용량 로그 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sermon_api_usage_logs (
                id SERIAL PRIMARY KEY,
                step_name VARCHAR(100),
                model_name VARCHAR(100),
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost DECIMAL(10, 6) DEFAULT 0,
                style_name VARCHAR(100),
                category VARCHAR(100),
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    else:
        # SQLite 테이블 생성
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
                subscription_expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sermon_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT NOT NULL,
                description TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            INSERT OR IGNORE INTO sermon_settings (setting_key, setting_value, description)
            VALUES ('default_step3_credits', '3', '신규 회원 기본 Step3 크레딧')
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banner_reference_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_url TEXT NOT NULL,
                template_type TEXT,
                style_tags TEXT,
                color_palette TEXT,
                description TEXT,
                quality_score INTEGER DEFAULT 5,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sermon_api_usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                step_name TEXT,
                model_name TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost REAL DEFAULT 0,
                style_name TEXT,
                category TEXT,
                user_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

    conn.commit()
    cursor.close()
    conn.close()


def get_setting(key, default=None):
    """설정값 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        cursor.execute('SELECT setting_value FROM sermon_settings WHERE setting_key = %s', (key,))
    else:
        cursor.execute('SELECT setting_value FROM sermon_settings WHERE setting_key = ?', (key,))

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result:
        return result['setting_value'] if USE_POSTGRES else result[0]
    return default


def set_setting(key, value, description=None):
    """설정값 저장"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if USE_POSTGRES:
        if description:
            cursor.execute('''
                INSERT INTO sermon_settings (setting_key, setting_value, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value,
                description = EXCLUDED.description, updated_at = CURRENT_TIMESTAMP
            ''', (key, value, description))
        else:
            cursor.execute('''
                INSERT INTO sermon_settings (setting_key, setting_value)
                VALUES (%s, %s)
                ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value,
                updated_at = CURRENT_TIMESTAMP
            ''', (key, value))
    else:
        if description:
            cursor.execute('''
                INSERT OR REPLACE INTO sermon_settings (setting_key, setting_value, description, updated_at)
                VALUES (?, ?, ?, datetime('now'))
            ''', (key, value, description))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO sermon_settings (setting_key, setting_value, updated_at)
                VALUES (?, ?, datetime('now'))
            ''', (key, value))

    conn.commit()
    cursor.close()
    conn.close()
