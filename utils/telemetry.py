# utils/telemetry.py
# Lightweight counters + event audit for AI/ops
# - Persists to data/metrics.db (SQLite, WAL)
# - Thread/process safe enough for our usage
# - One-liner API: inc(), log_event(), get_counters_snapshot(), get_recent_events()

from __future__ import annotations
import os, json, sqlite3, threading, time
import datetime as dt

DB_PATH = os.getenv("METRICS_DB", os.path.join("data", "metrics.db"))
_lock = threading.Lock()

def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    # Reasonable durability/perf tradeoffs for metrics
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def _init():
    with _connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS counters (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL DEFAULT 0,
            updated_ts TEXT NOT NULL
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            name TEXT NOT NULL,
            level TEXT NOT NULL,
            props TEXT
        )""")
        conn.commit()
_init()

# ----------------- Public API -----------------

def inc(name: str, value: int = 1) -> None:
    """Increment a numeric counter by value."""
    ts = dt.datetime.utcnow().isoformat()
    with _lock, _connect() as conn:
        conn.execute(
            """INSERT INTO counters(name,value,updated_ts)
               VALUES(?,?,?)
               ON CONFLICT(name) DO UPDATE SET
                   value = counters.value + excluded.value,
                   updated_ts = excluded.updated_ts""",
            (name, int(value), ts)
        )
        conn.commit()

def set_counter(name: str, value: int) -> None:
    """Force set a counter to a specific value."""
    ts = dt.datetime.utcnow().isoformat()
    with _lock, _connect() as conn:
        conn.execute(
            """INSERT INTO counters(name,value,updated_ts)
               VALUES(?,?,?)
               ON CONFLICT(name) DO UPDATE SET
                   value = excluded.value,
                   updated_ts = excluded.updated_ts""",
            (name, int(value), ts)
        )
        conn.commit()

def get_counter(name: str) -> int:
    with _connect() as conn:
        cur = conn.execute("SELECT value FROM counters WHERE name=?", (name,))
        row = cur.fetchone()
    return int(row[0]) if row else 0

def get_counters_snapshot(prefix: str | None = None) -> dict[str, int]:
    q = "SELECT name, value FROM counters"
    params = ()
    if prefix:
        q += " WHERE name LIKE ?"
        params = (f"{prefix}%",)
    with _connect() as conn:
        rows = conn.execute(q, params).fetchall()
    return {name: int(v) for name, v in rows}

def log_event(name: str, level: str = "info", **props) -> None:
    """Append a structured audit event."""
    ts = dt.datetime.utcnow().isoformat()
    blob = json.dumps(props, ensure_ascii=False) if props else None
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO events(ts,name,level,props) VALUES(?,?,?,?)",
            (ts, name, level, blob)
        )
        conn.commit()

def get_recent_events(limit: int = 200, name_like: str | None = None) -> list[dict]:
    q = "SELECT ts,name,level,props FROM events"
    params: list = []
    if name_like:
        q += " WHERE name LIKE ?"
        params.append(name_like)
    q += " ORDER BY rowid DESC LIMIT ?"
    params.append(int(limit))
    with _connect() as conn:
        rows = conn.execute(q, tuple(params)).fetchall()
    out = []
    for ts, name, level, props in rows:
        try:
            p = json.loads(props) if props else {}
        except Exception:
            p = {"raw": props}
        out.append({"ts": ts, "name": name, "level": level, "props": p})
    return out

def prune_old_events(days: int = 90) -> None:
    """Optional: call from a daily cron to keep DB small."""
    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=days)).isoformat()
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
        conn.commit()

def timeit(name: str):
    """Context manager to capture timing as counters: timing.<name>.count / .ms"""
    class _Timer:
        def __enter__(self):
            self.t0 = time.perf_counter()
            return self
        def __exit__(self, exc_type, exc, tb):
            ms = int((time.perf_counter() - self.t0) * 1000)
            inc(f"timing.{name}.count", 1)
            inc(f"timing.{name}.ms", ms)
    return _Timer()
