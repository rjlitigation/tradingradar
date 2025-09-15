# utils/storage.py
# --------------------------------------------------------------------
# Centralized SQLite storage helpers:
#  - ensure_schema(): create tables + add missing columns
#  - upsert_anomalies(df): safe UPSERT using a UNIQUE index
#  - prune_old_rows(days): delete aged rows
# AI-aware: will not fail if new columns (ai_band, anomaly_score) appear.
# --------------------------------------------------------------------
from __future__ import annotations

import os
import sqlite3
import logging
from typing import Iterable
import pandas as pd

DB_FILE = os.path.join("data", "anomalies.db")

# Columns we expect (but we will accept extra columns safely)
BASE_COLS = [
    "timestamp", "instrument", "type", "strike", "expiry",
    "openInterest", "changeInOI", "volume",
    "iv", "ltp",
    "vwap_status", "spot", "vwap",
    "oi_surge", "volume_surge", "iv_spike",
    "anomaly_score", "ai_band"
]

def ensure_schema() -> None:
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    # Base table
    cur.execute("""
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
        vwap_status TEXT, 
        spot REAL, 
        vwap REAL,
        oi_surge INTEGER DEFAULT 0, 
        volume_surge INTEGER DEFAULT 0, 
        iv_spike INTEGER DEFAULT 0,
        anomaly_score INTEGER DEFAULT 0,
        ai_band TEXT DEFAULT ''
    )
    """)
    # Add missing columns as needed (safe migration)
    cur.execute("PRAGMA table_info(anomalies)")
    existing = {r[1] for r in cur.fetchall()}
    for name, typ, dflt in [
        ("oi_surge", "INTEGER", "0"),
        ("volume_surge", "INTEGER", "0"),
        ("iv_spike", "INTEGER", "0"),
        ("anomaly_score", "INTEGER", "0"),
        ("ai_band", "TEXT", "''"),
        ("spot", "REAL", "0"),
        ("vwap", "REAL", "0"),
        ("vwap_status", "TEXT", "''"),
    ]:
        if name not in existing:
            try:
                cur.execute(f"ALTER TABLE anomalies ADD COLUMN {name} {typ} DEFAULT {dflt}")
            except Exception:
                pass

    # Create a UNIQUE index for idempotent upserts
    # Key choice: (timestamp, instrument, type, strike, expiry)
    # This is strong enough for intraday OC rows; adjust if needed.
    cur.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_anom_unique
    ON anomalies (timestamp, instrument, type, strike, expiry)
    """)
    conn.commit()
    conn.close()

def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep known columns if present; allow extras (SQLite will ignore in UPSERT writer if not mapped).
    Coerce types to safe defaults.
    """
    out = df.copy()
    # Ensure mandatory dimensions exist
    for c in ["timestamp","instrument","type","strike","expiry"]:
        if c not in out.columns:
            out[c] = ""
    # Numeric coercions
    for c in ["strike","openInterest","changeInOI","volume","anomaly_score","oi_surge","volume_surge","iv_spike"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).astype(int)
    for c in ["iv","ltp","spot","vwap"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0).astype(float)
    for c in ["timestamp","instrument","type","expiry","vwap_status","ai_band"]:
        if c in out.columns:
            out[c] = out[c].astype(str)

    # Order columns (optional)
    cols = [c for c in BASE_COLS if c in out.columns] + [c for c in out.columns if c not in BASE_COLS]
    out = out[cols]
    return out

def _iter_rows(df: pd.DataFrame) -> Iterable[tuple]:
    for _, r in df.iterrows():
        yield (
            r.get("timestamp",""),
            r.get("instrument",""),
            r.get("type",""),
            int(r.get("strike",0) or 0),
            r.get("expiry",""),
            int(r.get("openInterest",0) or 0),
            int(r.get("changeInOI",0) or 0),
            int(r.get("volume",0) or 0),
            float(r.get("iv",0.0) or 0.0),
            float(r.get("ltp",0.0) or 0.0),
            r.get("vwap_status",""),
            float(r.get("spot",0.0) or 0.0),
            float(r.get("vwap",0.0) or 0.0),
            int(r.get("oi_surge",0) or 0),
            int(r.get("volume_surge",0) or 0),
            int(r.get("iv_spike",0) or 0),
            int(r.get("anomaly_score",0) or 0),
            r.get("ai_band","") or "",
        )

def upsert_anomalies(df: pd.DataFrame) -> int:
    """
    SQLite UPSERT using UNIQUE index on (timestamp, instrument, type, strike, expiry).
    If your SQLite is < 3.24 and lacks ON CONFLICT DO UPDATE, we fall back to INSERT OR IGNORE + explicit UPDATE.
    Returns number of rows inserted/updated.
    """
    ensure_schema()
    if df is None or df.empty:
        return 0

    sdf = _sanitize_df(df)
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Try modern UPSERT
    inserted = 0
    try:
        sql = """
        INSERT INTO anomalies (
            timestamp, instrument, type, strike, expiry,
            openInterest, changeInOI, volume, iv, ltp,
            vwap_status, spot, vwap,
            oi_surge, volume_surge, iv_spike,
            anomaly_score, ai_band
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(timestamp, instrument, type, strike, expiry)
        DO UPDATE SET
            openInterest=excluded.openInterest,
            changeInOI=excluded.changeInOI,
            volume=excluded.volume,
            iv=excluded.iv,
            ltp=excluded.ltp,
            vwap_status=excluded.vwap_status,
            spot=excluded.spot,
            vwap=excluded.vwap,
            oi_surge=excluded.oi_surge,
            volume_surge=excluded.volume_surge,
            iv_spike=excluded.iv_spike,
            anomaly_score=excluded.anomaly_score,
            ai_band=excluded.ai_band
        """
        cur.executemany(sql, list(_iter_rows(sdf)))
        inserted = cur.rowcount if cur.rowcount is not None else len(sdf)
    except Exception as e:
        logging.info(f"UPSERT fell back due to: {e}")
        # Fallback path: INSERT OR IGNORE, then UPDATE
        sql_ins = """
        INSERT OR IGNORE INTO anomalies (
            timestamp, instrument, type, strike, expiry,
            openInterest, changeInOI, volume, iv, ltp,
            vwap_status, spot, vwap,
            oi_surge, volume_surge, iv_spike,
            anomaly_score, ai_band
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        cur.executemany(sql_ins, list(_iter_rows(sdf)))
        # Update changed values (best-effort)
        sql_up = """
        UPDATE anomalies SET
            openInterest=?,
            changeInOI=?,
            volume=?,
            iv=?,
            ltp=?,
            vwap_status=?,
            spot=?,
            vwap=?,
            oi_surge=?,
            volume_surge=?,
            iv_spike=?,
            anomaly_score=?,
            ai_band=?
        WHERE timestamp=? AND instrument=? AND type=? AND strike=? AND expiry=?
        """
        # Build tuples for UPDATE
        ups = []
        for _, r in sdf.iterrows():
            ups.append((
                int(r.get("openInterest",0) or 0),
                int(r.get("changeInOI",0) or 0),
                int(r.get("volume",0) or 0),
                float(r.get("iv",0.0) or 0.0),
                float(r.get("ltp",0.0) or 0.0),
                r.get("vwap_status",""),
                float(r.get("spot",0.0) or 0.0),
                float(r.get("vwap",0.0) or 0.0),
                int(r.get("oi_surge",0) or 0),
                int(r.get("volume_surge",0) or 0),
                int(r.get("iv_spike",0) or 0),
                int(r.get("anomaly_score",0) or 0),
                r.get("ai_band","") or "",
                r.get("timestamp",""),
                r.get("instrument",""),
                r.get("type",""),
                int(r.get("strike",0) or 0),
                r.get("expiry",""),
            ))
        cur.executemany(sql_up, ups)
        inserted = len(sdf)  # best-effort count

    conn.commit()
    conn.close()
    return int(inserted or 0)

def prune_old_rows(days: int = 45) -> int:
    """Delete rows older than N days (based on timestamp, UTC)."""
    ensure_schema()
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    # SQLite-friendly comparison: convert timestamp to julianday difference
    sql = """
    DELETE FROM anomalies
    WHERE julianday('now') - julianday(timestamp) > ?
    """
    cur.execute(sql, (float(days),))
    n = cur.rowcount if cur.rowcount is not None else 0
    conn.commit()
    conn.close()
    return int(n or 0)
