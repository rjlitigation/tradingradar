# ai/labels.py
import pandas as pd
import numpy as np

def make_labels(df: pd.DataFrame, horizon_min=15, move_bps=20, max_adverse_bps=25) -> pd.Series:
    """
    Binary label: did spot move in the proxy direction within T minutes,
    without exceeding adverse excursion > max_adverse_bps?
    CE -> up proxy, PE -> down proxy.
    """
    if df.empty:
        return pd.Series(dtype=int)

    x = df.sort_values('timestamp').copy()
    x['timestamp'] = pd.to_datetime(x['timestamp'], errors='coerce')
    x['spot'] = pd.to_numeric(x.get('spot', 0), errors='coerce').fillna(0)

    # Forward window extrema (simple rolling lookahead approximation)
    fwd_max = x['spot'].rolling(horizon_min, min_periods=1).max().shift(-horizon_min + 1)
    fwd_min = x['spot'].rolling(horizon_min, min_periods=1).min().shift(-horizon_min + 1)

    up_bps = 1e4 * (fwd_max - x['spot']) / x['spot'].replace(0, np.nan)
    dn_bps = 1e4 * (fwd_min - x['spot']) / x['spot'].replace(0, np.nan)

    up_bps = up_bps.replace([np.inf, -np.inf], 0).fillna(0)
    dn_bps = dn_bps.replace([np.inf, -np.inf], 0).fillna(0)

    is_ce = x['type'].astype(str).str.upper().eq('CE').astype(int)
    hit = (is_ce * (up_bps >= move_bps) + (1 - is_ce) * (dn_bps <= -move_bps)).astype(bool)
    mae = np.where(is_ce.astype(bool), dn_bps.abs(), up_bps.abs())  # opposite side excursion
    ok = (mae <= max_adverse_bps)
    return pd.Series((hit & ok).astype(int), index=x.index)
