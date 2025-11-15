#!/usr/bin/env python3
"""
특정 사용자를 관리자로 설정하는 스크립트
사용법: python3 make_admin.py <이메일>
"""

import sqlite3
import os
import sys

def make_admin(email):
    """Make a user admin by email"""
    db_path = os.path.join(os.path.dirname(__file__), 'users.db')

    if not os.path.exists(db_path):
        print(f"❌ 데이터베이스를 찾을 수 없습니다: {db_path}")
        print("먼저 python3 init_db.py를 실행하세요.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if user exists
    cursor.execute('SELECT id, name, email, is_admin FROM users WHERE email = ?', (email,))
    user = cursor.fetchone()

    if not user:
        print(f"❌ 이메일 '{email}'을 가진 사용자를 찾을 수 없습니다.")

        # Show available users
        cursor.execute('SELECT id, email, name FROM users')
        all_users = cursor.fetchall()

        if all_users:
            print("\n등록된 사용자 목록:")
            for u in all_users:
                print(f"  - ID: {u[0]}, 이메일: {u[1]}, 이름: {u[2]}")
        else:
            print("\n아직 등록된 사용자가 없습니다.")

        conn.close()
        return False

    user_id, name, user_email, is_admin = user

    if is_admin:
        print(f"ℹ️ 사용자 '{name}' ({user_email})는 이미 관리자입니다.")
    else:
        cursor.execute('UPDATE users SET is_admin = 1 WHERE id = ?', (user_id,))
        conn.commit()
        print(f"✅ 사용자 '{name}' ({user_email})가 관리자로 승격되었습니다!")

    # Show all admins
    cursor.execute('SELECT id, email, name FROM users WHERE is_admin = 1')
    admins = cursor.fetchall()

    print("\n현재 관리자 목록:")
    for admin in admins:
        print(f"  - ID: {admin[0]}, 이메일: {admin[1]}, 이름: {admin[2]}")

    conn.close()
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python3 make_admin.py <이메일>")
        print("예시: python3 make_admin.py admin@example.com")

        # Show current users
        db_path = os.path.join(os.path.dirname(__file__), 'users.db')
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, email, name FROM users')
            users = cursor.fetchall()

            if users:
                print("\n등록된 사용자 목록:")
                for user in users:
                    print(f"  - ID: {user[0]}, 이메일: {user[1]}, 이름: {user[2]}")

            conn.close()

        sys.exit(1)

    email = sys.argv[1]
    make_admin(email)
