# utils/db_users.py
# --------------------------------------------------------------------
# User/plan store with strict expiry handling and safe helpers.
# Exposes:
#   - init_user_db()
#   - add_user(email, name="Guest")
#   - get_user(email) -> (email, name, plan, expiry)
#   - update_plan(email, plan, days=30) -> (ok: bool, expiry_str)
#   - get_effective_plan(email) -> "free"|"tier1"|"tier2"
#   - downgrade_if_expired(email) -> bool
#   - list_features(plan) -> set[str]
# Storage: data/users.db (override with USERS_DB env).
# --------------------------------------------------------------------
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, date
from typing import Optional, Tuple, Set

USERS_DB = os.getenv("USERS_DB", "data/users.db")
ALLOWED_PLANS = {"free", "tier1", "tier2"}

def _connect():
    os.makedirs(os.path.dirname(USERS_DB), exist_ok=True)
    return sqlite3.connect(USERS_DB, timeout=10, isolation_level=None)

def init_user_db() -> None:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                name TEXT,
                plan TEXT NOT NULL DEFAULT 'free',
                expiry TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                email TEXT,
                action TEXT,
                detail TEXT
            );
        """)
        conn.commit()

def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

def _log(action: str, email: str, detail: str = "") -> None:
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO audits (ts, email, action, detail) VALUES (?, ?, ?, ?)",
                (_now_iso(), email, action, detail),
            )
            conn.commit()
    except Exception:
        pass

def add_user(email: str, name: str = "Guest") -> None:
    if not email:
        return
    init_user_db()
    now = _now_iso()
    with _connect() as conn:
        conn.execute("""
            INSERT INTO users (email, name, plan, expiry, created_at, updated_at)
            VALUES (?, ?, 'free', NULL, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                name=excluded.name,
                updated_at=excluded.updated_at
        """, (email.strip().lower(), name or "Guest", now, now))
        conn.commit()
    _log("user_upsert", email, f"name={name}")

def get_user(email: str) -> Optional[Tuple[str, str, str, Optional[str]]]:
    if not email:
        return None
    init_user_db()
    with _connect() as conn:
        cur = conn.execute("SELECT email, name, plan, expiry FROM users WHERE email = ?", (email.strip().lower(),))
        row = cur.fetchone()
        return tuple(row) if row else None

def _set_plan(email: str, plan: str, expiry_str: Optional[str]) -> None:
    now = _now_iso()
    with _connect() as conn:
        conn.execute("""
            UPDATE users
            SET plan = ?, expiry = ?, updated_at = ?
            WHERE email = ?
        """, (plan, expiry_str, now, email.strip().lower()))
        conn.commit()

def update_plan(email: str, plan: str, days: int = 30) -> Tuple[bool, Optional[str]]:
    """
    Assign plan and push expiry by N days from today (UTC). Returns (ok, expiry_iso_date).
    """
    if not email or (plan or "").lower() not in ALLOWED_PLANS:
        return False, None
    init_user_db()
    # Normalize
    plan = plan.strip().lower()
    exp_date = (date.today() + timedelta(days=max(1, int(days or 0)))).strftime("%Y-%m-%d")
    _set_plan(email, plan, exp_date)
    _log("plan_update", email, f"plan={plan} exp={exp_date}")
    return True, exp_date

def downgrade_if_expired(email: str) -> bool:
    """
    If expired, downgrade to free and clear expiry. Returns True if downgraded.
    """
    u = get_user(email)
    if not u:
        return False
    _, _, plan, expiry = u
    if not expiry or plan == "free":
        return False
    try:
        if datetime.strptime(expiry, "%Y-%m-%d").date() < date.today():
            _set_plan(email, "free", None)
            _log("plan_downgrade", email, f"expired={expiry}")
            return True
    except Exception:
        # If expiry is malformed, err on safe side: downgrade
        _set_plan(email, "free", None)
        _log("plan_downgrade", email, "expiry_malformed")
        return True
    return False

def get_effective_plan(email: Optional[str]) -> str:
    """
    Returns plan considering expiry. Missing user -> free.
    """
    if not email:
        return "free"
    try:
        downgrade_if_expired(email)
    except Exception:
        pass
    u = get_user(email)
    return (u[2] if u else "free") or "free"

def list_features(plan: str) -> Set[str]:
    """
    Declarative entitlement map for gating across the app.
    """
    p = (plan or "free").lower()
    if p == "tier2":
        return {
            "heatmap_live_all",
            "replay_full",
            "anomaly_full",
            "nifty_access",
            "telegram_priority",
            "csv_full",
        }
    if p == "tier1":
        return {
            "heatmap_live_bn",
            "replay_limited",
            "anomaly_20",
            "telegram_basic",
            "csv_last20",
        }
    # free
    return {"heatmap_delayed_bn", "anomaly_delayed", "education"}
