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

        # Create videos table for sermon videos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                title VARCHAR(500) NOT NULL,
                description TEXT,
                scripture_reference VARCHAR(200),
                content TEXT,
                video_path VARCHAR(500),
                thumbnail_path VARCHAR(500),
                duration INTEGER,
                resolution VARCHAR(20) DEFAULT '1080x1920',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create video_uploads table for tracking platform uploads
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS video_uploads (
                id SERIAL PRIMARY KEY,
                video_id INTEGER REFERENCES videos(id),
                platform VARCHAR(50) NOT NULL,
                platform_video_id VARCHAR(500),
                upload_status VARCHAR(50) DEFAULT 'pending',
                upload_url TEXT,
                uploaded_at TIMESTAMP,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create platform_credentials table for API keys
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS platform_credentials (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                platform VARCHAR(50) NOT NULL,
                credentials JSONB NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, platform)
            )
        ''')

        # Create bible_dramas table for Bible drama generation
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

        # Create indexes for bible_dramas
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

        print("✅ PostgreSQL 데이터베이스가 성공적으로 초기화되었습니다.")

    except Exception as e:
        print(f"❌ 데이터베이스 초기화 실패: {str(e)}")

if __name__ == "__main__":
    init_postgres_database()
