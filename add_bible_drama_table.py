#!/usr/bin/env python3
"""
성경 드라마 테이블 추가 마이그레이션 스크립트
SQLite와 PostgreSQL 모두 지원
"""
import os
import sqlite3
import sys

def migrate_sqlite():
    """SQLite 데이터베이스에 bible_dramas 테이블 추가"""
    db_path = os.path.join(os.path.dirname(__file__), 'users.db')

    if not os.path.exists(db_path):
        print(f"❌ SQLite 데이터베이스를 찾을 수 없습니다: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # bible_dramas 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bible_dramas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                scripture_reference TEXT NOT NULL,
                scripture_text TEXT NOT NULL,
                drama_title TEXT,
                duration_minutes INTEGER DEFAULT 20,
                synopsis TEXT,
                characters TEXT,
                scenes TEXT,
                full_script TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        conn.commit()
        conn.close()

        print(f"✅ SQLite 마이그레이션 완료: {db_path}")
        return True

    except Exception as e:
        print(f"❌ SQLite 마이그레이션 실패: {str(e)}")
        return False


def migrate_postgres():
    """PostgreSQL 데이터베이스에 bible_dramas 테이블 추가"""
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

        # bible_dramas 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bible_dramas (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                scripture_reference VARCHAR(200) NOT NULL,
                scripture_text TEXT NOT NULL,
                drama_title VARCHAR(500),
                duration_minutes INTEGER DEFAULT 20,
                synopsis TEXT,
                characters JSONB,
                scenes TEXT,
                full_script TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 인덱스 추가
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_bible_dramas_user_id
            ON bible_dramas(user_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_bible_dramas_scripture_reference
            ON bible_dramas(scripture_reference)
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
    print("🔧 성경 드라마 테이블 마이그레이션 시작...\n")

    sqlite_success = migrate_sqlite()
    postgres_success = migrate_postgres()

    print("\n" + "="*50)
    if sqlite_success and postgres_success:
        print("✅ 모든 마이그레이션이 성공적으로 완료되었습니다!")
        sys.exit(0)
    else:
        print("⚠️ 일부 마이그레이션이 실패했습니다. 로그를 확인하세요.")
        sys.exit(1)
