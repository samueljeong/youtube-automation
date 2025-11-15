import os
import psycopg2

def init_postgres_database():
    """Initialize PostgreSQL database with users table"""
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("❌ DATABASE_URL 환경 변수가 설정되지 않았습니다.")
        return

    # Render의 postgres:// URL을 postgresql://로 변경
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(100) NOT NULL,
                phone VARCHAR(20),
                birth_date VARCHAR(20),
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        cursor.close()
        conn.close()

        print("✅ PostgreSQL 데이터베이스가 성공적으로 초기화되었습니다.")

    except Exception as e:
        print(f"❌ 데이터베이스 초기화 실패: {str(e)}")

if __name__ == "__main__":
    init_postgres_database()
