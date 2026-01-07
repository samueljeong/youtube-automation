import sqlite3

conn = sqlite3.connect('users.db')
cursor = conn.cursor()

cursor.execute('SELECT id, email, name, phone, birth_date, created_at FROM users')
users = cursor.fetchall()

print("Users in database:")
print("-" * 80)
for user in users:
    print(f"ID: {user[0]}")
    print(f"Email: {user[1]}")
    print(f"Name: {user[2]}")
    print(f"Phone: {user[3]}")
    print(f"Birth Date: {user[4]}")
    print(f"Created At: {user[5]}")
    print("-" * 80)

print(f"\nTotal users: {len(users)}")

conn.close()
