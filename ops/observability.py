# ops/observability.py
# -------------------------------------------------------------------
# Minimal metrics logger to SQLite: counters, gauges, events.
# -------------------------------------------------------------------
from __future__ import annotations
import os, sqlite3, time

DB = os.getenv("TR_METRICS_DB", "data/metrics.db")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS counters(
        name TEXT, ts INTEGER, value REAL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gauges(
        name TEXT, ts INTEGER, value REAL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS events(
        name TEXT, ts INTEGER, level TEXT, payload TEXT)""")
    conn.commit(); conn.close()

def inc(name: str, by: float = 1.0):
    _ensure()
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO counters(name, ts, value) VALUES(?,?,?)",
                 (name, int(time.time()), float(by)))
    conn.commit(); conn.close()

def set_gauge(name: str, val: float):
    _ensure()
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO gauges(name, ts, value) VALUES(?,?,?)",
                 (name, int(time.time()), float(val)))
    conn.commit(); conn.close()

def log_event(name: str, level: str = "info", payload: str = ""):
    _ensure()
    conn = sqlite3.connect(DB)
    conn.execute("INSERT INTO events(name, ts, level, payload) VALUES(?,?,?,?)",
                 (name, int(time.time()), level, payload))
    conn.commit(); conn.close()
