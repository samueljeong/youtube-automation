#!/usr/bin/env python3
"""
벤치마크 대본 분석 테이블 추가 마이그레이션 스크립트
SQLite와 PostgreSQL 모두 지원
"""
import os
import sqlite3
import sys

def migrate_sqlite():
    """SQLite 데이터베이스에 benchmark_analyses 테이블 추가"""
    db_path = os.path.join(os.path.dirname(__file__), 'users.db')

    if not os.path.exists(db_path):
        print(f"❌ SQLite 데이터베이스를 찾을 수 없습니다: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # benchmark_analyses 테이블 생성
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

        # 인덱스 생성
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_view_count
            ON benchmark_analyses(view_count DESC)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_upload_date
            ON benchmark_analyses(upload_date)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_category
            ON benchmark_analyses(category)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_created_at
            ON benchmark_analyses(created_at DESC)
        ''')

        conn.commit()
        conn.close()

        print(f"✅ SQLite 마이그레이션 완료: {db_path}")
        return True

    except Exception as e:
        print(f"❌ SQLite 마이그레이션 실패: {str(e)}")
        return False


def migrate_postgres():
    """PostgreSQL 데이터베이스에 benchmark_analyses 테이블 추가"""
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("⚠️ DATABASE_URL 환경 변수가 설정되지 않았습니다. PostgreSQL 마이그레이션 건너뜁니다.")
        return True

    # Render의 postgres:// URL을 postgresql://로 변경
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    try:
        import psycopg2

        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        # benchmark_analyses 테이블 생성
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

        # 인덱스 추가
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_view_count
            ON benchmark_analyses(view_count DESC)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_upload_date
            ON benchmark_analyses(upload_date)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_category
            ON benchmark_analyses(category)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_created_at
            ON benchmark_analyses(created_at DESC)
        ''')

        conn.commit()
        cursor.close()
        conn.close()

        print("✅ PostgreSQL 마이그레이션 완료")
        return True

    except ImportError:
        print("⚠️ psycopg2가 설치되지 않았습니다. PostgreSQL 마이그레이션 건너뜁니다.")
        return True
    except Exception as e:
        print(f"❌ PostgreSQL 마이그레이션 실패: {str(e)}")
        return False


if __name__ == "__main__":
    print("🔧 벤치마크 대본 분석 테이블 마이그레이션 시작...\n")

    sqlite_success = migrate_sqlite()
    postgres_success = migrate_postgres()

    print("\n" + "="*50)
    if sqlite_success and postgres_success:
        print("✅ 모든 마이그레이션이 성공적으로 완료되었습니다!")
        sys.exit(0)
    else:
        print("⚠️ 일부 마이그레이션이 실패했습니다. 로그를 확인하세요.")
        sys.exit(1)
