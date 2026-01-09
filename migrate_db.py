import sqlite3
import os

def migrate_database():
    """Migrate existing database to add admin field"""
    db_path = os.path.join(os.path.dirname(__file__), 'users.db')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if is_admin column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]

    if 'is_admin' not in columns:
        print("Adding is_admin column to users table...")
        cursor.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0')
        conn.commit()
        print("✓ is_admin column added successfully")
    else:
        print("✓ is_admin column already exists")

    conn.close()
    print(f"Database migration completed at {db_path}")

if __name__ == "__main__":
    migrate_database()
