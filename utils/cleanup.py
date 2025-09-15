import os
from datetime import datetime, timedelta
from utils.db_core import using_postgres, pg_conn, sqlite_conn
from sqlalchemy import text

keep_days = int(os.getenv("KEEP_DAYS", "14"))

if using_postgres():
    cutoff = (datetime.utcnow() - timedelta(days=keep_days))
    with pg_conn() as c:
        c.execute(text("DELETE FROM anomalies WHERE timestamp < :cut"), {"cut": cutoff})
else:
    from dateutil import parser
    # crude cleanup for SQLite
    import sqlite3
    db = os.getenv("ANOM_SQLITE_PATH", "data/anomalies.db")
    with sqlite3.connect(db) as cn:
        cur = cn.cursor()
        # SQLite has TEXT timestamps; we can’t easily compare; skip or convert if you stored ISO strings
        # Example (if ISO): keep rows with timestamp >= cutoff iso
        cutoff_iso = (datetime.utcnow() - timedelta(days=keep_days)).isoformat()
        cur.execute("DELETE FROM anomalies WHERE timestamp < ?", (cutoff_iso,))
        cn.commit()
