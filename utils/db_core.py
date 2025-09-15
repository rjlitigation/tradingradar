# utils/db_core.py
import os, sqlite3
from contextlib import contextmanager

POSTGRES_URL = os.getenv("POSTGRES_URL", "").strip()

# Lazy import to avoid forcing deps locally if you're staying on SQLite
_engine = None
_use_pg = bool(POSTGRES_URL)

if _use_pg:
    # SQLAlchemy for Postgres
    from sqlalchemy import create_engine, text
    _engine = create_engine(POSTGRES_URL, pool_pre_ping=True)

# ---------- Context managers ----------
@contextmanager
def pg_conn():
    conn = None
    try:
        conn = _engine.connect()
        yield conn
    finally:
        if conn is not None:
            conn.close()

@contextmanager
def sqlite_conn(path):
    conn = None
    try:
        conn = sqlite3.connect(path, check_same_thread=False)
        yield conn
    finally:
        if conn is not None:
            conn.close()

# ---------- Public helpers ----------
def using_postgres() -> bool:
    return _use_pg

def ensure_tables():
    """
    Creates (if not exist) the required tables for users and anomalies.
    Works for both SQLite and Postgres.
    """
    if using_postgres():
        ddl_users = """
        CREATE TABLE IF NOT EXISTS users (
            email   TEXT PRIMARY KEY,
            name    TEXT,
            plan    TEXT NOT NULL DEFAULT 'free',
            expiry  DATE
        );
        """
        ddl_anoms = """
        CREATE TABLE IF NOT EXISTS anomalies (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP,
            instrument TEXT,
            type TEXT,
            strike INTEGER,
            expiry TEXT,
            openInterest INTEGER,
            changeInOI INTEGER,
            volume INTEGER,
            iv DOUBLE PRECISION,
            ltp DOUBLE PRECISION,
            oi_surge BOOLEAN,
            volume_surge BOOLEAN,
            iv_spike BOOLEAN,
            vwap_status TEXT,
            spot DOUBLE PRECISION,
            vwap DOUBLE PRECISION
        );
        """
        with pg_conn() as c:
            c.execute(text(ddl_users))
            c.execute(text(ddl_anoms))
    else:
        db_file_users = os.getenv("USERS_SQLITE_PATH", "data/users.db")
        db_file_anom  = os.getenv("ANOM_SQLITE_PATH", "data/anomalies.db")
        for path in (db_file_users, db_file_anom):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        with sqlite_conn(db_file_users) as cn:
            cn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT,
                plan TEXT NOT NULL DEFAULT 'free',
                expiry TEXT
            );
            """)
            cn.commit()
        with sqlite_conn(db_file_anom) as cn:
            cn.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
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
            """)
            cn.commit()
