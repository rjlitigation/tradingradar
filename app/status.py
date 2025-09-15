# app/status.py
import os, json, time
import streamlit as st

st.set_page_config(page_title="TradingRadar Status", layout="centered")

API_BASE = os.getenv("PUBLIC_API_BASE", "http://localhost:8000")

st.title("TradingRadar — Public Health")
st.caption("Live status. Educational analytics only.")

try:
    import requests
    r = requests.get(f"{API_BASE}/status/summary", timeout=6)
    j = r.json()
    st.success("Systems reachable")
except Exception as e:
    st.error(f"Status API not reachable: {e}")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Autopilot")
    st.write(j.get("autopilot") or {})
with col2:
    st.subheader("Ingest / Alerts")
    st.write(j.get("telemetry") or {})

st.subheader("Model")
st.write(j.get("model") or {})
st.caption(f"ts: {j.get('ts')}")
