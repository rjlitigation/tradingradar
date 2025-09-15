# utils/nse_fetcher.py
# --------------------------------------------------------------------
# Normalized option-chain fetcher with safe fallbacks.
# We DO NOT hardcode NSE private endpoints here to avoid fragility.
# Strategy:
#  - If ENV var OPTION_SOURCE_CSV_DIR is present, read latest CSV snapshots
#    produced by your collector (recommended in production).
#  - Else, return an empty DataFrame with correct schema (app fails-soft).
# Output columns (normalized, matching app expectations):
#   timestamp, instrument, type, strike, expiry,
#   openInterest, changeInOI, volume, iv, ltp, spot, vwap, vwap_status
# --------------------------------------------------------------------
from __future__ import annotations

import os
import glob
from datetime import datetime, timezone
from typing import Optional, List

import pandas as pd

VALID_INSTRUMENTS = {"BANKNIFTY", "NIFTY"}

REQUIRED_COLS = [
    "timestamp", "instrument", "type", "strike", "expiry",
    "openInterest", "changeInOI", "volume", "iv", "ltp",
    "spot", "vwap", "vwap_status",
]


def fetch_option_chain(instrument: str) -> pd.DataFrame:
    """
    Return a DataFrame with columns:
      ['timestamp','type','strike','expiry','openInterest','changeInOI','volume','iv','ltp','vwap_status','spot','vwap']
    This is a stub. Integrate your real logic here.
    """
    return pd.DataFrame(columns=[
        'timestamp','type','strike','expiry','openInterest','changeInOI',
        'volume','iv','ltp','vwap_status','spot','vwap'
    ])

def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=REQUIRED_COLS)

def _latest_csv_path(symbol: str, base_dir: str) -> Optional[str]:
    pattern = os.path.join(base_dir, f"{symbol}_option_chain_*.csv")
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None

def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    # Normalize types and fill NA safely
    df["timestamp"]   = pd.to_datetime(df["timestamp"], errors="coerce").fillna(pd.Timestamp.utcnow())
    df["instrument"]  = df["instrument"].astype(str).str.upper()
    df["type"]        = df["type"].astype(str).str.upper().where(lambda s: s.isin(["CE", "PE"]), "CE")
    for c in ["strike", "openInterest", "changeInOI", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    for c in ["iv", "ltp", "spot", "vwap"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).astype(float)
    df["expiry"]      = df["expiry"].astype(str)
    df["vwap_status"] = df["vwap_status"].astype(str).fillna("")
    return df

def load_option_chain(symbol: str) -> pd.DataFrame:
    """
    Load normalized option-chain snapshot for the given symbol.
    Preferred source: CSV snapshots directory (set OPTION_SOURCE_CSV_DIR).
    Returns a DataFrame with REQUIRED_COLS; may be empty but never raises.
    """
    symbol = (symbol or "BANKNIFTY").strip().upper()
    if symbol not in VALID_INSTRUMENTS:
        symbol = "BANKNIFTY"

    base_dir = os.getenv("OPTION_SOURCE_CSV_DIR", "").strip()
    if base_dir and os.path.isdir(base_dir):
        try:
            latest = _latest_csv_path(symbol, base_dir)
            if not latest:
                return _empty_df()

            raw = pd.read_csv(latest)
            # Map/rename columns if your collector uses different names
            # Expected at least: ts, type, strike, expiry, oi, chg_oi, volume, iv, ltp, spot
            rename_map = {
                "ts": "timestamp",
                "oi": "openInterest",
                "chg_oi": "changeInOI",
                "OptionType": "type",
                "Type": "type",
                "StrikePrice": "strike",
                "Volume": "volume",
                "IV": "iv",
                "LTP": "ltp",
                "Spot": "spot",
                "VWAP": "vwap",
                "VWAPStatus": "vwap_status",
            }
            df = raw.rename(columns=rename_map).copy()
            # Ensure mandatory columns
            for col in REQUIRED_COLS:
                if col not in df.columns:
                    df[col] = None

            # Inject instrument
            df["instrument"] = symbol
            df = df[REQUIRED_COLS]
            return _coerce_types(df)
        except Exception:
            return _empty_df()

    # No source available -> fail-soft
    return _empty_df()
