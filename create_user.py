"""ユーザー作成スクリプト: python create_user.py <username> <password>"""
import sys
import database
import auth

database.init_db()

if len(sys.argv) != 3:
    print("Usage: python create_user.py <username> <password>")
    sys.exit(1)

username, password = sys.argv[1], sys.argv[2]
existing = database.get_user_by_username(username)
if existing:
    print(f"Error: user '{username}' already exists")
    sys.exit(1)

hashed = auth.hash_password(password)
database.create_user(username, hashed)
print(f"User '{username}' created.")
