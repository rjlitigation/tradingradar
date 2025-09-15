# app/widgets_calibration.py
# --------------------------------------------------------------------
# Calibration Card widget
# Reads models/manifest.json and renders model info + metrics.
# Robust to both "old" (minimal) and "merged" (rich) manifest shapes.
# --------------------------------------------------------------------

import os, json
import streamlit as st
from datetime import datetime

MANIFEST_PATH = os.path.join("models", "manifest.json")

def load_manifest() -> dict:
    try:
        with open(MANIFEST_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def calibration_card():
    manifest = load_manifest()
    if not manifest:
        st.warning("⚠️ No manifest.json found.")
        return

    st.markdown("### 🧪 Model Calibration")
    with st.container():
        cols = st.columns(2)

        # Left: model metadata
        with cols[0]:
            st.markdown("**Model Info**")
            st.write("ID:", manifest.get("model_id") or manifest.get("model_name", "N/A"))
            st.write("Framework:", manifest.get("framework", "N/A"))
            st.write("Trained On:", manifest.get("trained_on", "N/A"))
            st.write("Training Window:", manifest.get("training_window", "N/A"))
            feats = manifest.get("features")
            if feats:
                st.caption("Features: " + ", ".join(feats))

        # Right: calibration + metrics
        with cols[1]:
            st.markdown("**Calibration / Metrics**")
            calib = manifest.get("calibration", {})
            if calib:
                st.write("Bands:", ", ".join(calib.get("bands", [])))
                st.write("Method:", calib.get("method", "N/A"))
            metrics = manifest.get("metrics", {})
            if metrics:
                for k, v in metrics.items():
                    st.write(f"{k}: {v}")
            else:
                st.caption("No metrics recorded.")

        # Footer: optional hash for drift checks
        if manifest.get("feature_hash"):
            st.caption(f"Feature hash: `{manifest['feature_hash']}`")

        # Safe-mode note
        if not manifest.get("metrics"):
            st.info("ℹ️ Metrics unavailable — model may need recalibration.")
