# ai/feature_store.py
import pandas as pd
import numpy as np

# Rolling windows (minutes) for z-scores on ΔOI, Volume, IV
ROLLS = [5, 15, 30]

SAFE_EPS = 1e-9

def _roll_stats(s: pd.Series, win: int) -> pd.DataFrame:
    r = s.rolling(win, min_periods=max(2, int(win/3))).agg(['mean', 'std'])
    r.columns = [f'{s.name}_{win}_mean', f'{s.name}_{win}_std']
    return r.fillna(0)

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input: normalized anomalies DataFrame with at least:
      ['timestamp','instrument','type','strike','expiry','changeInOI','volume','iv','spot','vwap']
    Output: same DF + engineered features (z-scores, distances, time bins, flags)
    """
    if df.empty:
        return df.copy()

    out = df.copy()
    # Ensure types
    out['timestamp'] = pd.to_datetime(out['timestamp'], errors='coerce')

    for col in ['changeInOI', 'volume', 'iv']:
        if col not in out.columns:
            out[col] = 0
        for w in ROLLS:
            stats = _roll_stats(out[col], w)
            out = pd.concat([out, stats], axis=1)
            out[f'{col}_z_{w}'] = (out[col] - out[f'{col}_{w}_mean']) / (out[f'{col}_{w}_std'] + SAFE_EPS)

    # Spot/VWAP distance in basis points
    out['dist_to_vwap_bps'] = 1e4 * (out.get('spot', 0) - out.get('vwap', 0)) / out.get('vwap', 1).replace(0, np.nan)
    out['dist_to_vwap_bps'] = out['dist_to_vwap_bps'].replace([np.inf, -np.inf], 0).fillna(0)

    # % OTM relative to spot (sign aware via CE/PE type)
    out['pct_otm_raw'] = 100.0 * ((out.get('strike', 0) - out.get('spot', 0)) / out.get('spot', 1).replace(0, np.nan))
    out['pct_otm_raw'] = out['pct_otm_raw'].replace([np.inf, -np.inf], 0).fillna(0)
    is_ce = out['type'].astype(str).str.upper().eq('CE').astype(int)
    is_pe = 1 - is_ce
    out['pct_otm'] = is_ce * out['pct_otm_raw'] - is_pe * out['pct_otm_raw']  # CE positive if strike>spot; PE positive if strike<spot

    # Time bin (minutes from open); doesn’t depend on timezone for ranking
    out['time_bin'] = out['timestamp'].dt.hour.fillna(0) * 60 + out['timestamp'].dt.minute.fillna(0)

    # Weekly expiry heuristic flag
    out['is_weekly'] = out['expiry'].astype(str).str.len().lt(10).astype(int)

    return out
