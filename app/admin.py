# app/admin.py
# --------------------------------------------------------------------
# TradingRadar Admin Console
# - Shows AI calibration card
# - Shows autopilot status (safe mode etc.)
# - Shows telemetry counters/events
# --------------------------------------------------------------------

import os, sys, json
import streamlit as st

# ----- Project root -----
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ----- Internal imports -----
from ops.autopilot import get_status
from utils.telemetry import get_counters_snapshot, get_events_snapshot
from app.widgets_calibration import calibration_card

st.set_page_config(page_title="TradingRadar — Admin Console", layout="wide")

st.title("🛠️ TradingRadar Admin Console")

# ====== Section 1: Calibration ======
calibration_card()

# ====== Section 2: Autopilot status ======
st.markdown("### 🤖 Autopilot Status")
status = get_status()
if status.get("safe_mode"):
    st.error(f"⚠️ SAFE MODE — {status.get('reason','unknown')}")
else:
    st.success("✅ Nominal — autopilot running baseline/AI")

st.json(status)

# ====== Section 3: Telemetry Counters ======
st.markdown("### 📊 Metrics Snapshot")
counters = get_counters_snapshot()
if counters:
    st.json(counters)
else:
    st.caption("No counters recorded yet.")

# ====== Section 4: Recent Events ======
st.markdown("### 🗒️ Recent Events (last 20)")
events = get_events_snapshot(limit=20)
if events:
    for ev in events:
        st.write(f"[{ev.get('ts')}] {ev.get('level','info').upper()} — {ev.get('event')}: {ev.get('detail','')}")
else:
    st.caption("No events logged.")
