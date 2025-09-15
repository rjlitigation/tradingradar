# utils/vwap_tracker.py
# --------------------------------------------------------------------
# Robust VWAP/Spot resolver with graceful fallbacks.
# Order of truth:
# 1) ticks table (preferred) -> compute VWAP intraday
# 2) anomalies table (spot/vwap columns if present)
# 3) cached rolling estimate from last known snapshot
# Never throws; always returns a dict.
# --------------------------------------------------------------------
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, Optional

DB_FILE = os.getenv("ANOMALY_DB", "data/anomalies.db")

def _utcnow():
    return datetime.now(tz=timezone.utc)

def _connect(db_path: str):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return sqlite3.connect(db_path, timeout=5, isolation_level=None)

def _from_ticks(conn: sqlite3.Connection, symbol: str) -> Optional[Dict[str, Any]]:
    """
    Expect optional table 'ticks' with columns:
      ts TEXT(iso) NOT NULL, instrument TEXT, price REAL, qty INTEGER
    VWAP = sum(price*qty) / sum(qty) for today
    Spot = last(price)
    """
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='ticks')
        """)
        if cur.fetchone()[0] != 1:
            return None

        # Only today's session UTC date; many deployments run IST—app shows IST anyway
        cur.execute("""
            SELECT price, qty, ts
            FROM ticks
            WHERE instrument = ? AND date(ts) = date('now')
            ORDER BY ts ASC
        """, (symbol,))
        rows = cur.fetchall()
        if not rows:
            return None

        # Compute VWAP & spot
        notional = 0.0
        volume = 0
        last_price = None
        last_ts = None
        for price, qty, ts in rows:
            p = float(price or 0.0)
            q = int(qty or 0)
            notional += p * q
            volume += q
            last_price = p
            last_ts = ts
        if volume <= 0 or last_price is None:
            return None

        vwap = notional / float(volume)
        ts = datetime.fromisoformat(last_ts) if last_ts else _utcnow()
        status = "Spot above VWAP" if last_price > vwap else ("Spot below VWAP" if last_price < vwap else "Spot near VWAP")
        return {"spot": last_price, "vwap": vwap, "status": status, "ts": ts}
    except Exception:
        return None

def _from_anomalies(conn: sqlite3.Connection, symbol: str) -> Optional[Dict[str, Any]]:
    """
    Fallback: use latest anomalies snapshot that includes spot/vwap/vwap_status.
    """
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='table' AND name='anomalies')
        """)
        if cur.fetchone()[0] != 1:
            return None

        cur.execute("""
            SELECT spot, vwap, vwap_status, timestamp
            FROM anomalies
            WHERE instrument = ?
            ORDER BY id DESC
            LIMIT 1
        """, (symbol,))
        row = cur.fetchone()
        if not row:
            return None
        spot, vwap, vwap_status, ts = row
        spot = float(spot or 0.0)
        vwap = float(vwap or 0.0)
        status = str(vwap_status or "") or ("Spot above VWAP" if spot > vwap else ("Spot below VWAP" if spot < vwap else "Spot near VWAP"))
        ts = datetime.fromisoformat(ts) if ts else _utcnow()
        if spot <= 0 or vwap <= 0:
            return None
        return {"spot": spot, "vwap": vwap, "status": status, "ts": ts}
    except Exception:
        return None

# In-process last known good snapshot
_LAST_SNAPSHOT: Dict[str, Dict[str, Any]] = {}

def get_vwap_status(symbol: str = "BANKNIFTY") -> Dict[str, Any]:
    """
    Public API used by the app. Always returns a dict:
      {"spot": float, "vwap": float, "status": str, "ts": datetime}
    If nothing is available, returns zeros and a human-safe status.
    """
    symbol = (symbol or "BANKNIFTY").strip().upper()
    try:
        with _connect(DB_FILE) as conn:
            out = _from_ticks(conn, symbol) or _from_anomalies(conn, symbol)
            if out:
                _LAST_SNAPSHOT[symbol] = out
                return out

        # Fallback to last known snapshot in memory
        if symbol in _LAST_SNAPSHOT:
            snap = _LAST_SNAPSHOT[symbol]
            return {
                "spot": float(snap.get("spot", 0.0)),
                "vwap": float(snap.get("vwap", 0.0)),
                "status": str(snap.get("status", "VWAP data unavailable")),
                "ts": snap.get("ts") or _utcnow(),
            }
    except Exception:
        pass

    return {
        "spot": 0.0,
        "vwap": 0.0,
        "status": "VWAP data unavailable",
        "ts": _utcnow(),
    }
