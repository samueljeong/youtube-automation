#!/usr/bin/env python3
"""
YouTube 토큰 저장을 위한 데이터베이스 테이블 추가
SQLite와 PostgreSQL 모두 지원
"""
import os
import sqlite3

def migrate_sqlite():
    """SQLite 데이터베이스에 youtube_tokens 테이블 추가"""
    db_path = 'users.db'

    if not os.path.exists(db_path):
        print(f"❌ SQLite 데이터베이스를 찾을 수 없습니다: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # youtube_tokens 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS youtube_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'default',
                token TEXT NOT NULL,
                refresh_token TEXT,
                token_uri TEXT,
                client_id TEXT,
                client_secret TEXT,
                scopes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )
        ''')

        # 인덱스 생성
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_youtube_tokens_user_id
            ON youtube_tokens(user_id)
        ''')

        conn.commit()
        conn.close()

        print(f"✅ SQLite 마이그레이션 완료: {db_path}")
        return True

    except Exception as e:
        print(f"❌ SQLite 마이그레이션 실패: {str(e)}")
        return False


def migrate_postgres():
    """PostgreSQL 데이터베이스에 youtube_tokens 테이블 추가"""
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("⚠️ DATABASE_URL 환경 변수가 설정되지 않았습니다. PostgreSQL 마이그레이션 건너뜁니다.")
        return False

    # Render의 postgres:// URL을 postgresql://로 변경
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    try:
        import psycopg2

        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        # youtube_tokens 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS youtube_tokens (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'default',
                token TEXT NOT NULL,
                refresh_token TEXT,
                token_uri TEXT,
                client_id TEXT,
                client_secret TEXT,
                scopes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )
        ''')

        # 인덱스 생성
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_youtube_tokens_user_id
            ON youtube_tokens(user_id)
        ''')

        conn.commit()
        conn.close()

        print("✅ PostgreSQL 마이그레이션 완료")
        return True

    except ImportError:
        print("⚠️ psycopg2가 설치되지 않았습니다. PostgreSQL 마이그레이션 건너뜁니다.")
        return False
    except Exception as e:
        print(f"❌ PostgreSQL 마이그레이션 실패: {str(e)}")
        return False


def migrate_existing_token():
    """기존 파일 기반 토큰을 데이터베이스로 마이그레이션"""
    import json

    token_file = 'data/youtube_token.json'

    if not os.path.exists(token_file):
        print("ℹ️ 마이그레이션할 기존 토큰 파일이 없습니다.")
        return

    try:
        with open(token_file, 'r') as f:
            token_data = json.load(f)

        # PostgreSQL 우선 시도
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)

            try:
                import psycopg2
                conn = psycopg2.connect(database_url)
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO youtube_tokens (user_id, token, refresh_token, token_uri, client_id, client_secret, scopes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        token = EXCLUDED.token,
                        refresh_token = EXCLUDED.refresh_token,
                        token_uri = EXCLUDED.token_uri,
                        client_id = EXCLUDED.client_id,
                        client_secret = EXCLUDED.client_secret,
                        scopes = EXCLUDED.scopes,
                        updated_at = CURRENT_TIMESTAMP
                ''', (
                    'default',
                    token_data.get('token'),
                    token_data.get('refresh_token'),
                    token_data.get('token_uri'),
                    token_data.get('client_id'),
                    token_data.get('client_secret'),
                    ','.join(token_data.get('scopes', []))
                ))

                conn.commit()
                conn.close()

                print("✅ 기존 토큰을 PostgreSQL로 마이그레이션했습니다.")

                # 백업 후 원본 파일 삭제
                backup_file = token_file + '.backup'
                os.rename(token_file, backup_file)
                print(f"ℹ️ 원본 파일을 백업했습니다: {backup_file}")

                return
            except Exception as e:
                print(f"⚠️ PostgreSQL 마이그레이션 실패, SQLite로 시도: {e}")

        # SQLite로 폴백
        db_path = 'users.db'
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO youtube_tokens (user_id, token, refresh_token, token_uri, client_id, client_secret, scopes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                'default',
                token_data.get('token'),
                token_data.get('refresh_token'),
                token_data.get('token_uri'),
                token_data.get('client_id'),
                token_data.get('client_secret'),
                ','.join(token_data.get('scopes', []))
            ))

            conn.commit()
            conn.close()

            print("✅ 기존 토큰을 SQLite로 마이그레이션했습니다.")

            # 백업 후 원본 파일 삭제
            backup_file = token_file + '.backup'
            os.rename(token_file, backup_file)
            print(f"ℹ️ 원본 파일을 백업했습니다: {backup_file}")

    except Exception as e:
        print(f"❌ 토큰 마이그레이션 실패: {str(e)}")


if __name__ == '__main__':
    print("=== YouTube 토큰 테이블 마이그레이션 시작 ===\n")

    sqlite_success = migrate_sqlite()
    postgres_success = migrate_postgres()

    if sqlite_success or postgres_success:
        print("\n=== 기존 토큰 파일 마이그레이션 시작 ===\n")
        migrate_existing_token()
        print("\n✅ 마이그레이션 완료!")
    else:
        print("\n❌ 마이그레이션 실패")
