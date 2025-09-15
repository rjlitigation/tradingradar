# utils/analyzer.py
# --------------------------------------------------------------------
# Deterministic anomaly engine:
#  - Ensures CE/PE coverage
#  - Computes OI/Volume/IV surges via rolling baselines or static thresholds
#  - Produces anomaly_score and safe VWAP context passthrough
#  - Never raises; returns clean DataFrame ready for storage
# --------------------------------------------------------------------
from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Tuple

def analyze_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds oi_surge, volume_surge, iv_spike and anomaly_score.
    Works even on short intraday windows (robust thresholds).
    """
    x = df.copy()
    for col in ['changeInOI', 'volume', 'iv']:
        if col not in x.columns:
            x[col] = 0

    def zflag(series: pd.Series, w: int = 10, z: float = 2.0) -> pd.Series:
        m = series.rolling(w, min_periods=max(3, int(w/2))).mean()
        s = series.rolling(w, min_periods=max(3, int(w/2))).std()
        return (series > (m + z * s)).fillna(False)

    x['oi_surge'] = zflag(pd.to_numeric(x['changeInOI'], errors='coerce').fillna(0))
    x['volume_surge'] = zflag(pd.to_numeric(x['volume'], errors='coerce').fillna(0))
    x['iv_spike'] = zflag(pd.to_numeric(x['iv'], errors='coerce').fillna(0))

    x['anomaly_score'] = x[['oi_surge','volume_surge','iv_spike']].astype(int).sum(axis=1)
    x['anomaly'] = x['anomaly_score'] > 0
    return x


def _ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    req = [
        "timestamp","instrument","type","strike","expiry",
        "openInterest","changeInOI","volume","iv","ltp",
        "spot","vwap","vwap_status"
    ]
    for c in req:
        if c not in df.columns:
            df[c] = np.nan
    return df

def _rolling_baselines(df: pd.DataFrame, key_cols=("instrument","type","strike")) -> pd.DataFrame:
    """
    Compute group-wise rolling means/std for volume, changeInOI, iv.
    If index is not time-sorted, sort by timestamp first.
    Uses window=20 by default; falls back to global stats when insufficient data.
    """
    if df.empty:
        return df

    df = df.sort_values("timestamp").copy()
    df["volume"]    = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
    df["changeInOI"]= pd.to_numeric(df["changeInOI"], errors="coerce").fillna(0).astype(int)
    df["iv"]        = pd.to_numeric(df["iv"], errors="coerce").fillna(0.0)

    gb = df.groupby(list(key_cols), dropna=False)
    for col in ["volume","changeInOI","iv"]:
        ma = gb[col].transform(lambda s: s.rolling(20, min_periods=5).mean())
        sd = gb[col].transform(lambda s: s.rolling(20, min_periods=5).std())
        df[f"{col}_z"] = (df[col] - ma) / (sd.replace(0, np.nan))
        # Fallback z when std is zero or not enough history: compare to global median
        fallback_med = df[col].median() if np.isfinite(df[col].median()) else 0.0
        df[f"{col}_z"] = df[f"{col}_z"].fillna((df[col] - fallback_med) / (np.std(df[col]) or 1.0))

    return df

def _flag_surges(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flags based on z-scores and absolute thresholds:
      - volume_surge  : volume_z >= 2.0 or volume >= 1000
      - oi_surge      : changeInOI_z >= 2.0 or changeInOI >= 500
      - iv_spike      : iv_z >= 2.0 or (iv change >= 3.0 points intraday)
    """
    if df.empty:
        df["volume_surge"] = False
        df["oi_surge"] = False
        df["iv_spike"] = False
        df["anomaly_score"] = 0
        return df

    df = df.copy()
    df["volume_surge"] = (df.get("volume_z", 0) >= 2.0) | (df["volume"] >= 1000)
    df["oi_surge"]     = (df.get("changeInOI_z", 0) >= 2.0) | (df["changeInOI"] >= 500)

    # IV spike: use z OR absolute delta from previous snapshot within same key
    df["iv_spike"] = (df.get("iv_z", 0) >= 2.0)
    # attempt delta check
    try:
        df["iv_prev"] = df.groupby(["instrument","type","strike"])["iv"].shift(1)
        df["iv_delta"] = (df["iv"] - df["iv_prev"]).abs()
        df["iv_spike"] = df["iv_spike"] | (df["iv_delta"] >= 3.0)
    except Exception:
        pass

    df["anomaly_score"] = df[["volume_surge","oi_surge","iv_spike"]].astype(int).sum(axis=1)
    return df.drop(columns=[c for c in ["iv_prev","iv_delta"] if c in df.columns])

def analyze_snapshot(df_snapshot: pd.DataFrame) -> pd.DataFrame:
    """
    Input: one merged snapshot (DataFrame) from fetcher + vwap context
    Output: normalized DataFrame with anomaly flags/scores
    """
    df = _ensure_cols(df_snapshot.copy())
    if df.empty:
        return df.assign(volume_surge=False, oi_surge=False, iv_spike=False, anomaly_score=0)

    # Make sure CE/PE are uppercase
    df["type"] = df["type"].astype(str).str.upper().where(lambda s: s.isin(["CE","PE"]), "CE")

    # Rolling baselines and flags
    df = _rolling_baselines(df)
    df = _flag_surges(df)

    # Clean types
    for c in ["strike","openInterest","changeInOI","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    for c in ["iv","ltp","spot","vwap"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    # Final selection/order
    cols = [
        "timestamp","instrument","type","strike","expiry",
        "openInterest","changeInOI","volume","iv","ltp",
        "spot","vwap","vwap_status",
        "oi_surge","volume_surge","iv_spike","anomaly_score",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    df = df[cols].sort_values("timestamp", ascending=True).reset_index(drop=True)
    return df
