# signal_engine.py
# -------------------------------------------------------------------
# Backend signal emitter with AI Autopilot guardrails.
# -------------------------------------------------------------------
from __future__ import annotations

import os, pandas as pd
from ops.autopilot import should_emit_alert, record_alert, run_health_checks
from bots.telegram_alert import send_alert

TENANT_ID = os.getenv("TR_TENANT_ID", "default_tenant")
ALERT_CHANNEL = "telegram"
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def _format_alert(row: pd.Series) -> str:
    return (
        f"📌 *Signal* — {row['instrument']} {row['type']} {int(row['strike'])}\n"
        f"• OIΔ: {row.get('changeInOI')} | Vol: {row.get('volume')} | IV: {row.get('iv'):.2f} | LTP: {row.get('ltp'):.2f}\n"
        f"• VWAP: {row.get('vwap'):.2f} ({row.get('vwap_status')}) | Score: {int(row.get('anomaly_score',0))}"
        f"{(' | AI: ' + str(row.get('ai_band'))) if str(row.get('ai_band') or '') else ''}\n"
        f"_Educational context. Not trading advice._"
    )

def emit_signals(anomalies_df: pd.DataFrame, top_k: int = 5) -> int:
    if anomalies_df is None or anomalies_df.empty:
        return 0

    _ = run_health_checks()
    band_rank = {"very_high": 3, "high": 2, "elevated": 1, "typical": 0}

    df = anomalies_df.copy()
    df["__band_rank"] = df["ai_band"].astype(str).map(lambda x: band_rank.get(x.lower(), 0))
    df = df.sort_values(["__band_rank","anomaly_score"], ascending=[False,False]).head(top_k)

    sent = 0
    for _, r in df.iterrows():
        if not should_emit_alert(tenant_id=TENANT_ID, channel=ALERT_CHANNEL):
            continue
        if send_alert(chat_id=TELEGRAM_CHAT_ID, text=_format_alert(r)):
            record_alert(tenant_id=TENANT_ID, channel=ALERT_CHANNEL)
            sent += 1
    return sent
