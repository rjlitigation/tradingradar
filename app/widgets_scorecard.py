# app/widgets_scorecard.py
import pandas as pd
import streamlit as st

def _safe_num(x, d=0):
    try:
        return f"{float(x):.{d}f}"
    except Exception:
        return "–"

def render_session_scorecard(df: pd.DataFrame):
    st.markdown('<div class="card"><h3>📊 Session Scorecard</h3>', unsafe_allow_html=True)
    if df is None or df.empty:
        st.info("No data for the current filters.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    df2 = df.copy()
    for b in ("oi_surge","volume_surge","iv_spike"):
        if b not in df2.columns: df2[b] = False
    df2["anomaly_score"] = df2["oi_surge"].astype(int) + df2["volume_surge"].astype(int) + df2["iv_spike"].astype(int)

    total = len(df2)
    strong = int((df2["anomaly_score"] >= 2).sum())
    avg_iv = df2["iv"].astype(float).mean() if "iv" in df2.columns else None

    # PCR by instrument
    pcrs = []
    if {"instrument","type","openInterest"}.issubset(df2.columns):
        g = df2.groupby(["instrument","type"], as_index=False).agg(oi=("openInterest","sum"))
        for inst in sorted(df2["instrument"].dropna().unique()):
            ce = float(g[(g["instrument"]==inst)&(g["type"]=="CE")]["oi"].sum() or 0.0)
            pe = float(g[(g["instrument"]==inst)&(g["type"]=="PE")]["oi"].sum() or 0.0)
            pcr = (pe/ce) if ce>0 else None
            pcrs.append((inst, pcr))

    c1,c2,c3,c4 = st.columns(4)
    with c1: st.metric("Total anomalies", total)
    with c2: st.metric("Strong (≥2 flags)", strong)
    with c3: st.metric("Avg IV", _safe_num(avg_iv,2))
    with c4:
        if pcrs:
            st.write("PCR")
            for inst, pcr in pcrs:
                st.caption(f"{inst}: {_safe_num(pcr,2) if pcr is not None else 'N/A'}")

    # Band distribution if present
    if "ai_band" in df2.columns:
        band_counts = df2["ai_band"].fillna("").replace("", "no_band").value_counts().to_dict()
        st.write("AI Band mix:")
        st.progress(min(1.0, (band_counts.get("very_high",0)/max(1,total))), text=f"Very High: {band_counts.get('very_high',0)}")
        st.progress(min(1.0, (band_counts.get("high",0)/max(1,total))), text=f"High: {band_counts.get('high',0)}")
        st.progress(min(1.0, (band_counts.get("elevated",0)/max(1,total))), text=f"Elevated: {band_counts.get('elevated',0)}")
        st.progress(min(1.0, (band_counts.get("typical",0)/max(1,total))), text=f"Typical: {band_counts.get('typical',0)}")

    st.markdown('</div>', unsafe_allow_html=True)
