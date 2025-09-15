# utils/live_updater.py
# --------------------------------------------------------------------
# Single entry point to ingest/refresh anomalies:
#  1) Fetch BANKNIFTY + NIFTY option-chain snapshots
#  2) Enrich with VWAP/Spot context (per symbol)
#  3) Run deterministic analyzer (OI/Vol/IV surges)
#  4) Attach AI-lite band (if model exists)
#  5) Upsert into SQLite + prune old rows
#  6) File-lock to avoid concurrent writers
# Designed to be called from Streamlit (idempotent + fast).
# --------------------------------------------------------------------
from __future__ import annotations

import os
import sqlite3
import logging
from contextlib import contextmanager
from typing import Dict, List

import pandas as pd

from utils.nse_fetcher import load_option_chain
from utils.vwap_tracker import get_vwap_status
from utils.analyzer import analyze_snapshot
from utils.storage import ensure_schema, upsert_anomalies, prune_old_rows
from utils.telemetry import inc

# --- AI imports ---
try:
    from ai.engine import AIRanker, DEFAULT_FEATURES
except Exception:
    AIRanker, DEFAULT_FEATURES = None, []

DEFAULT_SYMBOLS = ["BANKNIFTY", "NIFTY"]
DB_FILE = os.path.join("data", "anomalies.db")


# ---------------- Schema helpers ----------------
def _ensure_ai_schema():
    """Ensure anomalies table has ai_band + anomaly_score columns."""
    if not os.path.exists(DB_FILE):
        return
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(anomalies)")
    cols = {r[1] for r in cur.fetchall()}
    to_add = []
    if "anomaly_score" not in cols:
        to_add.append(("anomaly_score", "INTEGER"))
    if "ai_band" not in cols:
        to_add.append(("ai_band", "TEXT"))
    for name, typ in to_add:
        try:
            cur.execute(f"ALTER TABLE anomalies ADD COLUMN {name} {typ}")
        except Exception:
            pass
    conn.commit()
    conn.close()


# ---------------- Lock helpers ----------------
@contextmanager
def _file_lock(lock_path: str, stale_seconds: int = 180):
    """Simple cross-process lock using an exclusive file create."""
    try:
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            os.write(fd, str(os.getpid()).encode("utf-8"))
        finally:
            os.close(fd)
        yield
    except FileExistsError:
        # stale lock tolerance
        try:
            st = os.stat(lock_path)
            age = int(__import__("time").time()) - int(st.st_mtime)
            if age > stale_seconds:
                os.remove(lock_path)
                with _file_lock(lock_path, stale_seconds):
                    yield
            else:
                yield  # skip silently
        except Exception:
            yield
    finally:
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except Exception:
            pass


# ---------------- VWAP helpers ----------------
def _enrich_with_vwap(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    v = get_vwap_status(symbol)
    spot = float(v.get("spot", 0.0))
    vwap = float(v.get("vwap", 0.0))
    status = str(v.get("status", "VWAP data unavailable") or "")

    out = df.copy()
    out["spot"] = pd.to_numeric(out.get("spot", spot), errors="coerce").fillna(spot)
    out["vwap"] = pd.to_numeric(out.get("vwap", vwap), errors="coerce").fillna(vwap)
    out["vwap_status"] = out.get("vwap_status", status).astype(str).replace({"": status})
    return out


def _safe_concat(frames: List[pd.DataFrame]) -> pd.DataFrame:
    clean = [f for f in frames if f is not None and not f.empty]
    return pd.concat(clean, ignore_index=True) if clean else pd.DataFrame()


# ---------------- Main updater ----------------
def update_live_data(symbols: List[str] | None = None) -> Dict[str, int]:
    """
    Public entry. Returns counts inserted per symbol + total.
    Honors env flags:
      UPDATE_ENABLED (default: true)
      PRUNE_DAYS     (default: 45)
      INGEST_LOCK    (default: data/.update.lock)
    """
    from utils.storage import ensure_schema
    from utils.storage import upsert_anomalies, prune_old_rows

    # env flags
    def _bool_env(name: str, default: bool) -> bool:
        v = os.getenv(name)
        if v is None:
            return default
        return str(v).strip().lower() in {"1", "true", "yes", "on"}

    def _int_env(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, "").strip() or default)
        except Exception:
            return default

    if not _bool_env("UPDATE_ENABLED", True):
        return {s: 0 for s in DEFAULT_SYMBOLS} | {"total": 0, "skipped": 1}

    symbols = [s.strip().upper() for s in (symbols or DEFAULT_SYMBOLS) if s]
    if not symbols:
        symbols = DEFAULT_SYMBOLS

    ensure_schema()
    _ensure_ai_schema()
    lock_path = os.getenv("INGEST_LOCK", "data/.update.lock")

    inserted_counts: Dict[str, int] = {s: 0 for s in symbols}

    with _file_lock(lock_path):
        snapshots: List[pd.DataFrame] = []

        # 1) Load normalized OC snapshots
        for sym in symbols:
            snap = load_option_chain(sym)  # fail-soft
            if snap is None or snap.empty:
                continue
            snap["instrument"] = sym
            # 2) Enrich with VWAP/Spot
            snap = _enrich_with_vwap(snap, sym)
            snapshots.append(snap)

        merged = _safe_concat(snapshots)
        if merged.empty:
            return {**inserted_counts, "total": 0, "skipped": 0}

        # 3) Analyze snapshot (flags + score)
        analyzed = analyze_snapshot(merged)

        # 4) AI-lite band (if model present)
        if AIRanker is not None:
            try:
                model_path = os.path.join("models", "ai_ranker.pkl")
                ranker = AIRanker(model_path, feature_cols=DEFAULT_FEATURES)
                preds = ranker.predict(analyzed)
                if not preds.empty:
                    analyzed["ai_band"] = preds["calibrated_band"].astype(str)
            except Exception as e:
                logging.info(f"AI ranker not applied: {e}")
                analyzed["ai_band"] = ""
        else:
            analyzed["ai_band"] = ""

        # 5) Upsert into anomalies
        total = 0
        for sym in symbols:
            part = analyzed[analyzed["instrument"].astype(str).str.upper().eq(sym)]
            if part.empty:
                continue
            n = upsert_anomalies(part)
            inserted_counts[sym] = int(n or 0)
            total += int(n or 0)

        # 6) Prune old rows
        prune_days = _int_env("PRUNE_DAYS", 45)
        try:
            prune_old_rows(prune_days)
        except Exception:
            pass

        inserted_counts["total"] = total
        inserted_counts["skipped"] = 0
        
        try:
            inc("ingest.rows", int(inserted_counts.get("total", 0)))
        except Exception:
            pass

        return inserted_counts
