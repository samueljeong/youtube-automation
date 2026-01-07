#!/usr/bin/env python3
"""
benchmark_analyses 테이블에 video_category 컬럼 추가 마이그레이션
영상 카테고리: 간증, 드라마, 명언, 마음, 철학, 인간관계
"""
import os
import sqlite3
import sys


def migrate_sqlite():
    """SQLite에 video_category 컬럼 추가"""
    db_path = os.path.join(os.path.dirname(__file__), 'users.db')

    if not os.path.exists(db_path):
        print(f"❌ SQLite 데이터베이스를 찾을 수 없습니다: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 컬럼 존재 여부 확인
        cursor.execute("PRAGMA table_info(benchmark_analyses)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'video_category' not in columns:
            cursor.execute('''
                ALTER TABLE benchmark_analyses
                ADD COLUMN video_category TEXT DEFAULT '간증'
            ''')
            print("✅ SQLite: video_category 컬럼 추가됨")
        else:
            print("ℹ️ SQLite: video_category 컬럼이 이미 존재합니다")

        # 인덱스 추가
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_video_category
            ON benchmark_analyses(video_category)
        ''')

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ SQLite 마이그레이션 실패: {str(e)}")
        return False


def migrate_postgres():
    """PostgreSQL에 video_category 컬럼 추가"""
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("⚠️ DATABASE_URL 환경 변수가 없습니다. PostgreSQL 건너뜁니다.")
        return True

    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    try:
        import psycopg2

        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        # 컬럼 존재 여부 확인
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'benchmark_analyses' AND column_name = 'video_category'
        """)

        if not cursor.fetchone():
            cursor.execute('''
                ALTER TABLE benchmark_analyses
                ADD COLUMN video_category VARCHAR(50) DEFAULT '간증'
            ''')
            print("✅ PostgreSQL: video_category 컬럼 추가됨")
        else:
            print("ℹ️ PostgreSQL: video_category 컬럼이 이미 존재합니다")

        # 인덱스 추가
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_benchmark_video_category
            ON benchmark_analyses(video_category)
        ''')

        conn.commit()
        cursor.close()
        conn.close()
        return True

    except ImportError:
        print("⚠️ psycopg2가 없습니다. PostgreSQL 건너뜁니다.")
        return True
    except Exception as e:
        print(f"❌ PostgreSQL 마이그레이션 실패: {str(e)}")
        return False


if __name__ == "__main__":
    print("🔧 video_category 컬럼 추가 마이그레이션 시작...\n")

    sqlite_success = migrate_sqlite()
    postgres_success = migrate_postgres()

    print("\n" + "=" * 50)
    if sqlite_success and postgres_success:
        print("✅ 마이그레이션 완료!")
        sys.exit(0)
    else:
        print("⚠️ 일부 실패. 로그 확인 필요.")
        sys.exit(1)
