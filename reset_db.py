<<<<<<< HEAD
import sqlite3
from datetime import datetime

DB_PATH = "data/users.db"

def reset_all_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Reset everyone to free plan
    c.execute("UPDATE users SET plan=?, expiry=?", ("free", None))
    conn.commit()
    conn.close()
    print("✅ All users reset to FREE plan.")

def list_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT email, name, plan, expiry FROM users")
    rows = c.fetchall()
    conn.close()
    print("\n📋 Current Users:")
    for r in rows:
        print(r)

if __name__ == "__main__":
    print("⚠️ This will reset ALL users to Free plan.")
    confirm = input("Type 'YES' to continue: ")
    if confirm.strip().upper() == "YES":
        reset_all_users()
        list_users()
    else:
        print("❌ Cancelled.")
=======
# reset_db.py
import sqlite3, os

DB_FILE = os.path.join("data", "anomalies.db")

schema = """
CREATE TABLE anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    instrument TEXT,
    type TEXT,
    strike INTEGER,
    expiry TEXT,
    openInterest INTEGER,
    changeInOI INTEGER,
    volume INTEGER,
    iv REAL,
    ltp REAL,
    oi_surge INTEGER,
    volume_surge INTEGER,
    iv_spike INTEGER,
    vwap_status TEXT,
    spot REAL,
    vwap REAL
);
CREATE INDEX IF NOT EXISTS idx_anom_ts ON anomalies(timestamp);
"""

if os.path.exists(DB_FILE):
    print(f"Dropping old anomalies table in {DB_FILE}...")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS anomalies")
    conn.commit()
    conn.executescript(schema)
    conn.commit()
    conn.close()
    print("✅ Recreated anomalies table with correct schema.")
else:
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.executescript(schema)
    conn.commit()
    conn.close()
    print("✅ Created anomalies table fresh.")
>>>>>>> 5acb3a7 (Update project files)
