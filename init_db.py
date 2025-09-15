# init_db.py
import sqlite3, os

db_path = "data/users.db"
os.makedirs("data", exist_ok=True)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    plan TEXT DEFAULT 'free',
    expiry TEXT
)
""")

conn.commit()
conn.close()

print("✅ users table initialized in data/users.db")
