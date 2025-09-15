# app/replay.py
# -------------------------------------------------------------------
# TradingRadar — Premium SaaS Dashboard
# World-class, modern, high-tech Streamlit frontend
# -------------------------------------------------------------------

import os, sys, sqlite3
from datetime import date, datetime
import pandas as pd
import streamlit as st

# ----- Project root on path -----
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ----- Internal imports -----
from utils.db_users import init_user_db, get_user, add_user, update_plan, get_effective_plan, list_features
from utils.payments import simulate_payment
from utils.vwap_tracker import get_vwap_status
from utils.live_updater import update_live_data
from utils.storage import read_anomalies_gated
from ai.engine import AIRanker, DEFAULT_FEATURES
from app.widgets_calibration import render_calibration_card
from app.widgets_scorecard import render_session_scorecard
from app.widgets_wizard import render_onboarding_wizard
from app.widgets_ghost import render_ghost_replay

# NEW autopilot + alerts
from ops.autopilot import run_health_checks, should_emit_alert, record_alert
from bots.telegram_alert import send_alert

# ----- AI ranker init -----
if "ai_ranker" not in st.session_state:
    try:
        st.session_state["ai_ranker"] = AIRanker(
            model_path=os.path.join("models", "ai_ranker.pkl"),
            feature_cols=DEFAULT_FEATURES
        )
    except Exception:
        st.session_state["ai_ranker"] = None

init_user_db()

# ----- Optional Plotly -----
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_OK = True
except Exception:
    PLOTLY_OK = False

VALID_INSTRUMENTS = {"BANKNIFTY", "NIFTY"}

# ======= THEME (Dark/Light), CSS =======

DARK_CSS = """
<style>
body { background-color: #0f1116; }
.block-container { padding-top: 0.5rem; padding-bottom: 3rem; }
.header { background:#111418; padding:12px 24px; border-radius:12px; margin-bottom:20px; display:flex; align-items:center; }
.header img { height:40px; margin-right:16px; }
.header h1 { font-size:24px; margin:0; color:#f5f5f5; }
.header .tagline { font-size:14px; color:#9aa0a6; }
.card { background:#1b1f27; border:1px solid #2d2f36; border-radius:14px; padding:16px; margin-bottom:18px; box-shadow:0 2px 6px rgba(0,0,0,0.4); }
.card h3 { margin:0 0 12px 0; color:#f5f5f5; }
.kpi { padding:14px; border-radius:12px; background:#20242f; text-align:center; }
.kpi .label { font-size:14px; font-weight:600; color:#9aa0a6; }
.kpi .value { font-size:28px; font-weight:800; color:#f5f5f5; margin-top:4px; }
.pill { display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:700; }
.pill.green{background:#e6f4ea;color:#137333;}
.pill.red{background:#fce8e6;color:#a50e0e;}
.pill.gray{background:#e8eaed;color:#3c4043;}
.anom-card { border-radius:12px; border:1px solid #2d2f36; background:#161a22; padding:12px 14px; margin-bottom:12px; box-shadow:0 1px 4px rgba(0,0,0,0.35); }
.anom-card .title { font-weight:800; color:#e8eaed; font-size:14px; }
.anom-card .meta { color:#9aa0a6; font-size:12px; margin-top:2px; }
.anom-card .row { display:flex; gap:12px; flex-wrap:wrap; margin-top:8px; }
.badge { border-radius:8px; padding:2px 8px; font-size:12px; font-weight:700; border:1px solid #2d2f36; background:#0f1218; color:#c7cacf; }
.flag { border-radius:999px; padding:2px 10px; font-size:11px; font-weight:700; }
.flag.oi{background:#24382e; color:#4cc784;} .flag.vol{background:#332b20; color:#f5b74a;} .flag.iv{background:#32232f; color:#f071a3;}
.scorebar { height:8px; background:#2d2f36; border-radius:6px; overflow:hidden; margin-top:8px; }
.scorebar > div { height:100%; background:linear-gradient(90deg, #96fbc4, #f9f586, #f6d365, #fda085); width:0%; }
.footer { margin-top:24px; font-size:12px; color:#888; text-align:center; }
.dataframe td, .dataframe th { font-size:13px; padding:6px; }
</style>
"""

LIGHT_CSS = """
<style>
body { background-color: #fafafa; }
.block-container { padding-top: 0.5rem; padding-bottom: 3rem; }
.header { background:#ffffff; padding:12px 24px; border-radius:12px; margin-bottom:20px; display:flex; align-items:center; border:1px solid #e0e0e0; }
.header img { height:40px; margin-right:16px; }
.header h1 { font-size:24px; margin:0; color:#202124; }
.header .tagline { font-size:14px; color:#5f6368; }
.card { background:#ffffff; border:1px solid #e0e0e0; border-radius:12px; padding:16px; margin-bottom:18px; box-shadow:0 1px 4px rgba(0,0,0,0.08); }
.card h3 { margin:0 0 12px 0; color:#202124; }
.kpi { padding:14px; border-radius:12px; background:#f9f9f9; text-align:center; border:1px solid #e0e0e0; }
.kpi .label { font-size:14px; font-weight:600; color:#5f6368; }
.kpi .value { font-size:28px; font-weight:800; color:#202124; margin-top:4px; }
.pill { display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:700; }
.pill.green{background:#e6f4ea;color:#137333;}
.pill.red{background:#fce8e6;color:#a50e0e;}
.pill.gray{background:#f1f3f4;color:#3c4043;}
.anom-card { border-radius:12px; border:1px solid #e0e0e0; background:#ffffff; padding:12px 14px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
.anom-card .title { font-weight:800; color:#202124; font-size:14px; }
.anom-card .meta { color:#5f6368; font-size:12px; margin-top:2px; }
.anom-card .row { display:flex; gap:12px; flex-wrap:wrap; margin-top:8px; }
.badge { border-radius:8px; padding:2px 8px; font-size:12px; font-weight:700; border:1px solid #e0e0e0; background:#f7f9fc; color:#3c4043; }
.flag { border-radius:999px; padding:2px 10px; font-size:11px; font-weight:700; }
.flag.oi{background:#e6f4ea; color:#137333;} .flag.vol{background:#fff3cd; color:#7a5a00;} .flag.iv{background:#fde2ef; color:#a50e79;}
.scorebar { height:8px; background:#eceff1; border-radius:6px; overflow:hidden; margin-top:8px; }
.scorebar > div { height:100%; background:linear-gradient(90deg, #00c853, #ffd600, #ff9100, #ff6d00); width:0%; }
.footer { margin-top:24px; font-size:12px; color:#666; text-align:center; }
.dataframe td, .dataframe th { font-size:13px; padding:6px; }
</style>
"""

# ======= SMALL HELPERS =======

def get_logo_path():
    for p in ("app/assets/logo.png", "app/assets/logo.jpg", "app/assets/logo.jpeg"):
        if os.path.exists(p):
            return p
    return None

def current_plan() -> str:
    if "email" not in st.session_state:
        return "free"
    return get_effective_plan(st.session_state.get("email"))

def available_dates(df: pd.DataFrame):
    if df.empty or "timestamp" not in df.columns:
        return []
    return sorted(df["timestamp"].dropna().astype("datetime64[ns]").dt.date.unique().tolist())

# ======= BRAND HEADER =======

def brand_header():
    logo = get_logo_path()
    st.markdown('<div class="header">', unsafe_allow_html=True)
    cols = st.columns([1, 6])
    with cols[0]:
        if logo:
            st.image(logo, use_container_width=True)
        else:
            st.markdown("<div style='width:100%;height:40px;background:#e0e0e0;border-radius:8px'></div>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown("<h1>TradingRadar</h1><div class='tagline'>Retail Options Sentiment Suite — Premium Dashboard</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ======= KPI =======

def kpi_cards(df: pd.DataFrame):
    c1, c2, c3 = st.columns(3)
    total = len(df)
    strong = 0
    if not df.empty:
        for b in ("oi_surge", "volume_surge", "iv_spike"):
            if b not in df.columns:
                df[b] = False
        strong = int(((df["oi_surge"] | df["volume_surge"] | df["iv_spike"]).astype(bool)).sum())

    vwaps = {}
    if not df.empty:
        latest = df.sort_values("timestamp").groupby("instrument", as_index=False).tail(1)
        for _, row in latest.iterrows():
            vwaps[str(row.get("instrument",""))] = str(row.get("vwap_status","VWAP data unavailable"))

    with c1:
        st.markdown(f'<div class="kpi"><div class="label">Total anomalies</div><div class="value">{total}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="kpi"><div class="label">Strong signals</div><div class="value">{strong}</div></div>', unsafe_allow_html=True)
    with c3:
        pills = ""
        for inst, status in vwaps.items():
            s = status.lower()
            color = "gray"
            if "above" in s: color = "green"
            elif "below" in s: color = "red"
            pills += f'<span class="pill {color}">{inst}: {status}</span>&nbsp;'
        if not pills:
            pills = '<span class="pill gray">No VWAP</span>'
        st.markdown(f'<div class="kpi"><div class="label">VWAP status</div>{pills}</div>', unsafe_allow_html=True)

# ======= VWAP PANEL =======

def gated_vwap_display(plan: str):
    try:
        # Show BN by default; Tier2 shows both BN + NIFTY inline
        symbols = ["BANKNIFTY"] if plan in ("free", "tier1") else ["BANKNIFTY", "NIFTY"]
        st.markdown('<div class="card"><h3>VWAP Context</h3>', unsafe_allow_html=True)
        for sym in symbols:
            v = get_vwap_status(sym)
            spot = float(v.get("spot", 0.0))
            vwap = float(v.get("vwap", 0.0))
            status = v.get("status", "VWAP data unavailable")
            ts = v.get("ts") or datetime.utcnow()
            if plan == "free":
                st.info(f"{sym}: Free (delayed) • Spot≈{int(spot)//10}x, VWAP≈{int(vwap)//10}x • {status}")
            elif plan == "tier1":
                st.success(f"{sym}: Live • Spot={spot:.2f}, VWAP={vwap:.2f} • {status}")
            else:
                slope = "diverging" if abs(spot - vwap) > 25 else "flat"
                st.success(f"{sym}: Live+ • Spot={spot:.2f}, VWAP={vwap:.2f} • {status} • Trend={slope}")
            st.caption(f"Last update: {ts.strftime('%H:%M')} IST")
        st.markdown('</div>', unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"VWAP unavailable: {e}")

# ======= HEATMAPS =======

def sentiment_heatmap(df: pd.DataFrame, key_suffix=""):
    if df.empty:
        st.info("No data available.")
        return
    heat = df.groupby(["instrument", "type"], as_index=False).agg(openInterest=("openInterest", "sum"))
    if PLOTLY_OK and not heat.empty:
        fig = px.bar(heat, x="instrument", y="openInterest", color="type", barmode="group", labels={"openInterest":"Open Interest"})
        st.plotly_chart(fig, use_container_width=True, key=f"heatmap_{key_suffix}")
    else:
        pivot = heat.pivot(index="instrument", columns="type", values="openInterest").fillna(0)
        st.bar_chart(pivot, use_container_width=True)

    for inst in sorted(heat["instrument"].unique()):
        ce = heat[(heat["instrument"] == inst) & (heat["type"] == "CE")]["openInterest"].sum()
        pe = heat[(heat["instrument"] == inst) & (heat["type"] == "PE")]["openInterest"].sum()
        pcr = round(pe/ce, 2) if ce else None
        st.write(f"- **{inst}** PCR: **{pcr if pcr is not None else 'N/A'}**")

def gated_heatmap(df: pd.DataFrame, plan: str):
    st.markdown('<div class="card"><h3>Sentiment Heatmap (OI Pressure)</h3>', unsafe_allow_html=True)
    data = df.copy()
    if data.empty:
        st.info("No data available.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    if plan == "free":
        # BN only + emulate 10-min delay (already gated at DB; this is a second guard)
        data = data[data["instrument"] == "BANKNIFTY"].copy()
        cutoff = data["timestamp"].max()
        if pd.notna(cutoff):
            cutoff = pd.to_datetime(cutoff)
            data = data[pd.to_datetime(data["timestamp"]) <= (cutoff - pd.Timedelta(minutes=10))]
        st.caption("Free: delayed/sample • BANKNIFTY")
        sentiment_heatmap(data, "free")
    elif plan == "tier1":
        st.caption("Tier1: live • BANKNIFTY")
        sentiment_heatmap(data[data["instrument"] == "BANKNIFTY"], "tier1")
    else:
        st.caption("Tier2: live • BANKNIFTY + NIFTY")
        sentiment_heatmap(data[data["instrument"].isin(["BANKNIFTY", "NIFTY"])], "tier2")
    st.markdown('</div>', unsafe_allow_html=True)

# ======= ANOMALY CARDS =======

def render_anomaly_card(r: pd.Series):
    score = int(r.get("oi_surge", False)) + int(r.get("volume_surge", False)) + int(r.get("iv_spike", False))
    width = min(max(score, 0), 3) / 3 * 100
    flags = []
    if bool(r.get("oi_surge", False)): flags.append('<span class="flag oi">OI</span>')
    if bool(r.get("volume_surge", False)): flags.append('<span class="flag vol">VOL</span>')
    if bool(r.get("iv_spike", False)): flags.append('<span class="flag iv">IV</span>')
    flags_html = " ".join(flags) if flags else '<span class="pill gray">No flags</span>'

    html = f"""
    <div class="anom-card">
      <div class="title">{r.get('instrument','')} {r.get('type','')} {int(r.get('strike',0))} <span class="badge">Exp {r.get('expiry','')}</span></div>
      <div class="meta">OI={int(r.get('openInterest',0))}, ΔOI={int(r.get('changeInOI',0))}, Vol={int(r.get('volume',0))}, IV={float(r.get('iv',0.0)):.2f}, LTP={float(r.get('ltp',0.0)):.2f}</div>
      <div class="row">
        {flags_html}
        <span class="badge">Score {score}/3</span>
        <span class="badge">VWAP: {str(r.get('vwap_status',''))}</span>
      </div>
      <div class="scorebar"><div style="width:{width}%"></div></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

    # NEW: AI band badge (tier-gated)
    plan = (st.session_state.get("user", [None, None, "free"])[2] or "free").lower()
    if plan in ("tier1", "tier2") and st.session_state.get("ai_ranker"):
        ai = st.session_state["ai_ranker"]
        row_df = r.to_frame().T
        pred = ai.predict(row_df)
        if not pred.empty:
            band = str(pred.iloc[0]['calibrated_band'])
            st.markdown(f"<span class='badge'>AI: {band}</span>", unsafe_allow_html=True)
            if plan == "tier2":
                st.caption("Educational AI reason codes enabled.")

    # NEW: Alert button with autopilot gating
    if st.button("🔔 Send Alert", key=f"alert_{r['instrument']}_{r['type']}_{r['strike']}_{r['timestamp']}"):
        _alert_anomaly(r)

def _alert_anomaly(r: pd.Series):
    TENANT_ID = os.getenv("TR_TENANT_ID", "default_tenant")
    ALERT_CHANNEL = "telegram"
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    if not should_emit_alert(tenant_id=TENANT_ID, channel=ALERT_CHANNEL):
        st.info("Alert suppressed by Autopilot (cadence/safe-mode).")
        return

    text = (
        f"📈 *Anomaly* — {r['instrument']} {r['type']} {int(r['strike'])}\n"
        f"• OIΔ: {r['changeInOI']} | Vol: {r['volume']} | IV: {r['iv']:.2f} | LTP: {r['ltp']:.2f}\n"
        f"• VWAP: {r['vwap']:.2f} ({r['vwap_status']}) | Score: {int(r.get('anomaly_score',0))}"
        f"{(' | AI: ' + str(r.get('ai_band'))) if str(r.get('ai_band') or '') else ''}\n"
        f"_Educational context. Not trading advice._"
    )

    ok = send_alert(chat_id=TELEGRAM_CHAT_ID, text=text)
    if ok:
        record_alert(tenant_id=TENANT_ID, channel=ALERT_CHANNEL)
        st.success("Alert sent.")
    else:
        st.error("Alert failed.")

def top3_panel(df: pd.DataFrame):
    st.markdown('<div class="card"><h3>Top 3 Recent Anomalies</h3>', unsafe_allow_html=True)
    if df.empty:
        st.info("No anomalies yet.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    # Sort by strength then liquidity
    df2 = df.copy()
    for b in ("oi_surge", "volume_surge", "iv_spike"):
        if b not in df2.columns: df2[b] = False
    df2["anomaly_score"] = df2["oi_surge"].astype(int) + df2["volume_surge"].astype(int) + df2["iv_spike"].astype(int)
    top = df2.sort_values(["anomaly_score", "volume", "openInterest"], ascending=[False, False, False]).head(3)
    cols = st.columns(3)
    for i, (_, r) in enumerate(top.iterrows()):
        with cols[i % 3]:
            render_anomaly_card(r)
    st.markdown('</div>', unsafe_allow_html=True)

# ======= ANOMALY LOG (UI shows what DB gating returned) =======

def anomaly_log(df: pd.DataFrame, plan: str):
    st.subheader("🔎 Anomaly Log")
    if df.empty:
        st.info("No anomalies yet.")
        return
    if plan == "free":
        st.warning("Free: showing delayed sample (gated). Upgrade for live feed.")
    elif plan == "tier1":
        st.info("Tier1: last 20 rows (gated).")
    else:
        st.success("Tier2: full live log.")
    st.dataframe(df.sort_values("timestamp", ascending=False), use_container_width=True)
    # CSV download based on plan
    if plan == "tier1":
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download (last 20)", data=csv, file_name="anomalies_tier1.csv", mime="text/csv", use_container_width=True)
    elif plan == "tier2":
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download (full)", data=csv, file_name="anomalies_full.csv", mime="text/csv", use_container_width=True)

# ======= REPLAY / BACKTEST =======

def replay_panel(df: pd.DataFrame, plan: str):
    with st.expander("🎞️ Replay / Backtest", expanded=False):
        if df.empty:
            st.info("No data available for replay.")
            return
        all_dates = available_dates(df)
        if not all_dates:
            st.info("No dated sessions found.")
            return

        if plan == "free":
            st.warning("🔒 Replay is locked on Free. Upgrade to Tier1/Tier2.")
            return
        if plan == "tier1":
            allowed_dates = all_dates[-3:]
            st.info(f"⭐ Tier1: Limited to last 3 sessions: {', '.join(map(str, allowed_dates))}")
        else:
            allowed_dates = all_dates
            st.success("🚀 Tier2: Full history available.")

        sel = st.selectbox("Select session date", options=allowed_dates, index=len(allowed_dates)-1)
        day = df[pd.to_datetime(df["timestamp"]).dt.date == sel].copy()
        if day.empty:
            st.info("No data for selected session.")
            return

        st.markdown(f"**Session:** {sel} • Rows: {len(day)}")

        # Mini-top3 for the session
        for b in ("oi_surge","volume_surge","iv_spike"):
            if b not in day.columns: day[b] = False
        day["anomaly_score"] = day["oi_surge"].astype(int) + day["volume_surge"].astype(int) + day["iv_spike"].astype(int)
        cols = st.columns(3)
        for i, (_, r) in enumerate(day.sort_values(["anomaly_score","volume","openInterest"], ascending=[False,False,False]).head(3).iterrows()):
            with cols[i % 3]:
                render_anomaly_card(r)

        # OI by strike CE vs PE (session)
        if {"strike","openInterest","type"}.issubset(set(day.columns)):
            plot_df = day.groupby(["type","strike"], as_index=False).agg(openInterest=("openInterest","sum"))
            if not plot_df.empty:
                if PLOTLY_OK:
                    fig = px.bar(plot_df, x="strike", y="openInterest", color="type", barmode="group", title="Open Interest by Strike (session)")
                    st.plotly_chart(fig, use_container_width=True, key="replay_oi_fig")
                else:
                    st.bar_chart(plot_df.pivot(index="strike", columns="type", values="openInterest").fillna(0), use_container_width=True)

        st.dataframe(day.sort_values("timestamp"), use_container_width=True)

# ======= EDUCATION / FAQ =======

def interpretation_guide():
    st.markdown('<div class="card"><h3>📘 Interpretation Guide</h3>', unsafe_allow_html=True)
    st.markdown("""
**OI** = participation, **Volume** = activity, **IV** = expected risk.  
**VWAP**: spot above = bullish undertone; below = bearish; near = neutral.  
**Score 0–3** counts OI/Vol/IV surges (context only; not advice).
    """)
    st.markdown('</div>', unsafe_allow_html=True)

def faq_panel():
    st.markdown('<div class="card"><h3>❓ FAQs</h3>', unsafe_allow_html=True)
    faqs = [
        ("Is this a tips service?", "No. Educational analytics only; no investment advice."),
        ("Why few anomalies?", "Filters suppress noise; fewer alerts = higher signal quality."),
        ("Why delay on Free?", "Retail sources may be 1–3m delayed; Free is additionally delayed."),
        ("What unlocks with Tier2?", "Full history, full heatmaps, NIFTY+BANKNIFTY, priority alerts, full CSV."),
    ]
    for i, (q, a) in enumerate(faqs):
        with st.expander(q, expanded=(i == 0)):
            st.write(a)
    st.markdown('</div>', unsafe_allow_html=True)

def footer():
    st.markdown("""
<div class="footer">
© 2025 TradingRadar • Educational analytics only • Not SEBI-registered.<br/>
No advice is given. Use at your own discretion. Data may be delayed.
</div>
""", unsafe_allow_html=True)

# ======= AUTH / SIDEBAR =======

def login_form():
    st.sidebar.subheader("🔑 Login")
    if "email" in st.session_state:
        user = get_user(st.session_state["email"])
        if user:
            email, name, plan, expiry = user
            st.sidebar.info(f"✅ {email}\n\nPlan: {plan}\n\nExpiry: {expiry}")
        if st.sidebar.button("Logout"):
            for k in ["email", "user"]:
                st.session_state.pop(k, None)
            st.rerun()
        return

    email = st.sidebar.text_input("Email")
    name = st.sidebar.text_input("Name (optional)")
    if st.sidebar.button("Login / Register"):
        if email:
            add_user(email, name or "Guest")
            st.session_state["email"] = email
            st.session_state["user"] = get_user(email)
            st.rerun()

def upgrade_box():
    st.sidebar.subheader("💳 Upgrade Plan")
    user = st.session_state.get("user")
    plan = "free"; expiry = None
    if user:
        _, _, plan, expiry = user
    st.sidebar.markdown(f"**Current Plan:** {plan} (Expiry: {expiry})")

    tier1_disabled = plan in ["tier1", "tier2"]
    tier2_disabled = plan == "tier2"

    if st.sidebar.button("Upgrade to Tier 1 (₹499/mo)", disabled=tier1_disabled):
        ok, receipt = simulate_payment(st.session_state["email"], "tier1")
        if ok:
            st.sidebar.success(f"✅ Upgraded to Tier1 until {receipt.get('expiry')}")
            st.rerun()
        else:
            st.sidebar.error("Payment failed (simulated).")

    if st.sidebar.button("Upgrade to Tier 2 (₹999/mo)", disabled=tier2_disabled):
        ok, receipt = simulate_payment(st.session_state["email"], "tier2")
        if ok:
            st.sidebar.success(f"✅ Upgraded to Tier2 until {receipt.get('expiry')}")
            st.rerun()
        else:
            st.sidebar.error("Payment failed (simulated).")

    with st.sidebar.expander("💡 What’s included?"):
        st.markdown("""
**Free**
- 1 delayed anomaly/day
- Delayed BN heatmap
- Guides & FAQs

**Tier 1 (₹499/mo)**
- Live anomalies (last 20)
- VWAP live
- Replay: last 3 sessions
- Basic alerts

**Tier 2 (₹999/mo)**
- Full anomalies (no limit)
- Full replay & history
- Heatmap: BN + NIFTY
- Priority alerts
- CSV full
        """)

# ======= MAIN =======

import streamlit as st
from ops.autopilot import run_health_checks

# ======= MAIN =======
def main():
    st.set_page_config(page_title="TradingRadar", layout="wide")

    # NEW Safe Mode banner at top
    st_status = run_health_checks()
    if st_status["safe_mode"]:
        st.warning(f"⚠️ AI Safe Mode ON — {st_status['reason'] or 'fallback mode active'}")
    else:
        st.success("✅ AI systems nominal")

    # Theme
    st.sidebar.header("⚙️ Preferences")
    if "theme_choice" not in st.session_state:
        st.session_state["theme_choice"] = "Dark (Pro)"
    theme = st.sidebar.selectbox("Theme", ["Dark (Pro)", "Light (Fintech)"], index=0 if "Dark" in st.session_state["theme_choice"] else 1)
    st.session_state["theme_choice"] = theme
    st.markdown(DARK_CSS if "Dark" in theme else LIGHT_CSS, unsafe_allow_html=True)

    # Auth
    login_form()
    if "email" not in st.session_state:
        st.stop()
    # Keep user fresh in session
    st.session_state["user"] = get_user(st.session_state["email"])

    # Live ingest (idempotent, fast, fail-soft)
    update_live_data()

    # Resolve plan + features
    plan = current_plan()
    feats = list_features(plan)

    # Read anomalies with DB-level gating
    df_all = read_anomalies_gated(plan)
    # Defensive typing
    if not df_all.empty and "timestamp" in df_all.columns:
        df_all["timestamp"] = pd.to_datetime(df_all["timestamp"], errors="coerce")

    # Sidebar: Filters (within gated result)
    st.sidebar.header("🔎 Filters")
    insts = sorted(set(df_all["instrument"].unique()) & VALID_INSTRUMENTS) if not df_all.empty else ["BANKNIFTY"]
    default_insts = insts
    sel_insts = st.sidebar.multiselect("Instrument", options=insts, default=default_insts)

    types = sorted(set((df_all["type"].dropna() if "type" in df_all else pd.Series(["CE","PE"])).astype(str).str.upper().unique()) | {"CE","PE"})
    sel_types = st.sidebar.multiselect("Option Type", options=types, default=types)

    expiries = sorted(df_all["expiry"].dropna().astype(str).unique().tolist()) if not df_all.empty and "expiry" in df_all else []
    sel_expiries = st.sidebar.multiselect("Expiry", options=expiries, default=expiries)

    st.sidebar.header("📅 Date")
    dates = available_dates(df_all)
    default_date = dates[-1] if dates else None
    sel_date = st.sidebar.date_input("Select date", value=default_date)

    # Apply filters to gated df
    df = df_all.copy()
    if not df.empty:
        if sel_insts:
            df = df[df["instrument"].isin(sel_insts)]
        if sel_types:
            df = df[df["type"].isin(sel_types)]
        if sel_expiries:
            df = df[df["expiry"].isin(sel_expiries)]
        if isinstance(sel_date, date):
            df = df[pd.to_datetime(df["timestamp"]).dt.date == sel_date]

    # Sidebar: Upgrades & referral
    upgrade_box()
    st.sidebar.subheader("📢 Invite & Earn")
    st.sidebar.code(f"https://tradingradar.com/?ref={st.session_state['email']}")

    # Main
    brand_header()
    tab_dash, tab_log, tab_edu, tab_faq, tab_contact = st.tabs(
        ["📊 Dashboard", "📜 Anomaly Log", "📘 Interpretation", "❓ FAQs", "📩 Contact"]
    )

    with tab_dash:
        kpi_cards(df)
        gated_vwap_display(plan)
        # Base heatmap on currently filtered slice for precision
        gated_heatmap(df, plan)
        top3_panel(df)
        replay_panel(df, plan)

    with tab_log:
        anomaly_log(df, plan)

    with tab_edu:
        interpretation_guide()

    with tab_faq:
        faq_panel()

    with tab_contact:
        st.header("📩 Contact Us")
        st.markdown("📧 **rj.litigation@gmail.com**")
        st.text_input("Your Name")
        st.text_input("Your Email")
        st.text_area("Message")
        if st.button("Send Message"):
            st.success("✅ Your message has been sent! We’ll get back to you shortly.")
    
    with tab_dash:
        # existing calls...
        render_calibration_card()            # NEW: trust
        render_session_scorecard(df)         # NEW: clarity
        render_ghost_replay(df, plan)        # NEW: wow

    with tab_edu:
        render_onboarding_wizard(st.session_state.get("email",""))  # NEW: personalization
        interpretation_guide()  # (your existing education panel)

    footer()

if __name__ == "__main__":
    main()
