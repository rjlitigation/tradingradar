# utils/payments.py
# --------------------------------------------------------------------
# Simple simulated billing to keep your flow airtight in dev/demo:
#  - Records a transaction (idempotency key optional)
#  - Updates the user's plan/expiry atomically
#  - No external gateways hardcoded (plug real provider later)
# Tables live in USERS_DB for simplicity.
# Exposes:
#   simulate_payment(email, plan, amount=None, idempotency_key=None) -> (ok, receipt_dict)
# --------------------------------------------------------------------
from __future__ import annotations

import os
import uuid
import sqlite3
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

from utils.db_users import init_user_db, update_plan, get_user, USERS_DB

PRICE_INR = {"tier1": 499, "tier2": 999}

def _connect():
    os.makedirs(os.path.dirname(USERS_DB), exist_ok=True)
    return sqlite3.connect(USERS_DB, timeout=10, isolation_level=None)

def _ensure_payments_schema():
    init_user_db()
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                email TEXT NOT NULL,
                plan TEXT NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                provider TEXT NOT NULL,
                idempotency_key TEXT
            )
        """)
        conn.commit()

def simulate_payment(email: str, plan: str, amount: Optional[int] = None,
                     idempotency_key: Optional[str] = None,
                     provider: str = "SIMULATED",
                     currency: str = "INR") -> Tuple[bool, Dict[str, Any]]:
    """
    Records a simulated successful payment and upgrades the user.
    Returns (ok, receipt).
    """
    if not email or (plan or "").lower() not in PRICE_INR:
        return False, {"error": "invalid_email_or_plan"}
    _ensure_payments_schema()

    # Idempotency: if the key already exists, return previous receipt
    if idempotency_key:
        with _connect() as conn:
            cur = conn.execute("SELECT id, ts, email, plan, amount, currency, provider, idempotency_key FROM payments WHERE idempotency_key = ?", (idempotency_key,))
            row = cur.fetchone()
            if row:
                rid, ts, em, pl, am, curcy, prov, ik = row
                return True, {"id": rid, "ts": ts, "email": em, "plan": pl, "amount": am, "currency": curcy, "provider": prov, "idempotency_key": ik}

    amt = int(amount if amount is not None else PRICE_INR[plan.lower()])
    pay_id = str(uuid.uuid4())
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

    # Persist + upgrade
    with _connect() as conn:
        conn.execute(
            "INSERT INTO payments (id, ts, email, plan, amount, currency, provider, idempotency_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pay_id, ts, email.strip().lower(), plan.lower(), amt, currency, provider, idempotency_key),
        )
        conn.commit()

    ok, expiry = update_plan(email, plan.lower(), days=30)
    receipt = {"id": pay_id, "ts": ts, "email": email, "plan": plan.lower(), "amount": amt, "currency": currency, "provider": provider, "expiry": expiry}
    return ok, receipt
