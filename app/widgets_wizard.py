# app/widgets_wizard.py
import streamlit as st
from utils.prefs import get_prefs, save_prefs

def render_onboarding_wizard(email: str):
    st.markdown('<div class="card"><h3>🧭 Onboarding</h3>', unsafe_allow_html=True)
    if not email:
        st.info("Login to personalize your experience.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    prefs = get_prefs(email)
    instruments = st.multiselect("Instruments", ["BANKNIFTY","NIFTY"], default=prefs.get("instruments", ["BANKNIFTY"]))
    risk = st.selectbox("Noise tolerance", ["Low","Medium","High"], index=["Low","Medium","High"].index(prefs.get("risk","Medium")))
    alerts = st.multiselect("Alert channels", ["telegram","email","in-app"], default=prefs.get("alerts", ["in-app"]))
    topk = st.slider("Max alerts per hour", 1, 12, int(prefs.get("max_alerts_per_hour", 6)))

    if st.button("Save Preferences", use_container_width=True):
        save_prefs(email, {
            "instruments": instruments,
            "risk": risk,
            "alerts": alerts,
            "max_alerts_per_hour": topk
        })
        st.success("Preferences saved.")
    st.markdown('</div>', unsafe_allow_html=True)
