# ops/autopilot.py
from __future__ import annotations
import os, json, time, sqlite3
from typing import Dict
from utils.telemetry import log_event


STATE_DB = os.getenv("TR_METRICS_DB", "data/metrics.db")  # reuse metrics DB for small KV state
SAFE_TTL = 300  # seconds a failure keeps safe-mode on, unless cleared

def _ensure_state():
    os.makedirs(os.path.dirname(STATE_DB), exist_ok=True)
    conn = sqlite3.connect(STATE_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT, ts INTEGER)""")
    conn.commit(); conn.close()

def _set_kv(key: str, val: dict):
    _ensure_state()
    conn = sqlite3.connect(STATE_DB)
    conn.execute("INSERT OR REPLACE INTO kv(k,v,ts) VALUES(?,?,?)",
                 (key, json.dumps(val), int(time.time())))
    conn.commit(); conn.close()

def _get_kv(key: str) -> dict | None:
    _ensure_state()
    conn = sqlite3.connect(STATE_DB)
    cur = conn.execute("SELECT v FROM kv WHERE k=?", (key,))
    row = cur.fetchone()
    conn.close()
    if not row: return None
    try:
        return json.loads(row[0])
    except Exception:
        return None

def _set_safe_mode(on: bool, reason: str = ""):
    prev = _get_kv("autopilot.safe")
    was_on = bool(prev and prev.get("on"))
    now = {"on": bool(on), "reason": str(reason or ""), "ts": int(time.time())}
    _set_kv("autopilot.safe", now)

    # Metrics + event logs
    set_gauge("autopilot.safe_mode", 1.0 if on else 0.0)
    if on and not was_on:
        log_event("autopilot.safe_mode", "warn", reason="model_drift")
    if (not on) and was_on:
        log_event("autopilot.safe_mode", "info", reason="recovered")

def get_status() -> Dict[str, str | bool]:
    st = _get_kv("autopilot.safe") or {}
    return {"safe_mode": bool(st.get("on", False)), "reason": st.get("reason", ""), "ts": st.get("ts", 0)}

def should_emit_alert(tenant_id: str = "default_tenant", channel: str = "push", max_per_hour: int | None = None) -> bool:
    # Optional: honor global safe mode by reducing alert volume (not zero)
    st = get_status()
    cap = int(os.getenv("AUTOPILOT_ALERTS_CAP", "6"))
    if max_per_hour is None:
        max_per_hour = cap if not st["safe_mode"] else max(1, cap // 2)

    key = f"alerts.rate.{tenant_id}.{channel}"
    bucket = _get_kv(key) or {"count": 0, "window": int(time.time()) // 3600}
    now_bucket = int(time.time()) // 3600
    if bucket["window"] != now_bucket:
        bucket = {"count": 0, "window": now_bucket}

    return bucket["count"] < max_per_hour

def record_alert(tenant_id: str = "default_tenant", channel: str = "push"):
    key = f"alerts.rate.{tenant_id}.{channel}"
    bucket = _get_kv(key) or {"count": 0, "window": int(time.time()) // 3600}
    now_bucket = int(time.time()) // 3600
    if bucket["window"] != now_bucket:
        bucket = {"count": 0, "window": now_bucket}
    bucket["count"] += 1
    _set_kv(key, bucket)

def run_health_checks() -> Dict[str, str | bool]:
    """
    Very light checks: DB reachable, model file present size>0.
    If failed -> enter safe mode for SAFE_TTL seconds.
    """
    issues = []

    # DB ping
    try:
        db = os.getenv("TR_DB_PATH", "data/anomalies.db")
        os.makedirs(os.path.dirname(db), exist_ok=True)
        import sqlite3; sqlite3.connect(db).close()
    except Exception as e:
        issues.append(f"DB: {e}")

    # Model presence
    mp = os.getenv("TR_MODEL_PATH", "models/ai_ranker.pkl")
    try:
        ok = os.path.exists(mp) and (os.path.getsize(mp) > 0)
        if not ok:
            issues.append("Model missing or empty")
    except Exception as e:
        issues.append(f"Model: {e}")

    if issues:
        _set_safe_mode(True, "; ".join(issues))
    else:
        # Only clear if previous safe mode is older than SAFE_TTL
        prev = _get_kv("autopilot.safe") or {}
        if prev.get("on") and (int(time.time()) - int(prev.get("ts", 0)) > SAFE_TTL):
            _set_safe_mode(False, "")

    return get_status()
