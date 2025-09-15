# ai/digest.py
import pandas as pd
from datetime import date

def build_daily_digest(df: pd.DataFrame) -> str:
    """Plain-English educational summary; no advice."""
    if df.empty:
        return f"[{date.today()}] Market Digest: No notable anomalies recorded."

    # PCR by instrument
    pcr_lines = []
    heat = (df.groupby(['instrument','type'], as_index=False)
              .agg(openInterest=('openInterest','sum')))
    for inst in sorted(heat['instrument'].unique()):
        ce = heat[(heat['instrument']==inst)&(heat['type']=='CE')]['openInterest'].sum()
        pe = heat[(heat['instrument']==inst)&(heat['type']=='PE')]['openInterest'].sum()
        pcr = round(pe/ce, 2) if ce else None
        pcr_lines.append(f"- {inst} PCR: {pcr if pcr is not None else 'N/A'}")

    # AI bands distribution
    if 'ai_band' in df.columns:
        band_counts = df['ai_band'].value_counts()
        bands = ", ".join([f"{k}:{int(v)}" for k,v in band_counts.items()])
    else:
        bands = "N/A"

    msg = [
        f"[{date.today()}] TradingRadar Educational Digest",
        "Session context (descriptive):",
        *pcr_lines,
        f"AI bands distribution: {bands}",
        "Note: This summary is educational context, not investment advice."
    ]
    return "\n".join(msg)
