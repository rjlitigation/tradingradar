# app/widgets_ghost.py
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    POK = True
except Exception:
    POK = False

def _narrate(row_before: pd.Series, row_after: pd.Series) -> str:
    msgs = []
    try:
        dvwap = (float(row_after.get("spot",0)) - float(row_before.get("spot",0)))
        if abs(dvwap) > 10:
            msgs.append("Spot moved noticeably during the window.")
        if float(row_after.get("iv",0)) - float(row_before.get("iv",0)) > 1.0:
            msgs.append("IV expanded, suggesting rising uncertainty.")
        if float(row_after.get("changeInOI",0)) - float(row_before.get("changeInOI",0)) > 0:
            msgs.append("Open interest build-up persisted.")
    except Exception:
        pass
    return " • ".join(msgs) or "Stable window; limited change observed."

def render_ghost_replay(df: pd.DataFrame, plan: str):
    with st.expander("👻 Ghost Replay (AI-narrated)", expanded=False):
        if plan == "free":
            st.warning("Upgrade to Tier1/Tier2 to unlock Ghost Replay.")
            return
        if df is None or df.empty:
            st.info("No data to replay.")
            return

        # pick a row
        cols = st.columns([2,2,2,2])
        with cols[0]:
            inst = st.selectbox("Instrument", sorted(df["instrument"].dropna().unique().tolist()))
        subset = df[df["instrument"]==inst]
        with cols[1]:
            typ = st.selectbox("Type", sorted(subset["type"].dropna().unique().tolist()))
        subset = subset[subset["type"]==typ]
        with cols[2]:
            strikes = sorted(subset["strike"].dropna().unique().tolist())
            strike = st.selectbox("Strike", strikes)
        sub2 = subset[subset["strike"]==strike].copy().sort_values("timestamp")
        with cols[3]:
            idx = st.number_input("Row index", min_value=0, max_value=max(0,len(sub2)-1), value=max(0,len(sub2)-1), step=1)

        if sub2.empty:
            st.info("No rows for selection.")
            return

        row = sub2.iloc[int(idx)]
        ts = pd.to_datetime(row["timestamp"])
        w_start = ts - pd.Timedelta(minutes=15)
        w_end   = ts + pd.Timedelta(minutes=15)

        win = df[
            (df["instrument"]==inst) &
            (df["type"]==typ) &
            (df["strike"]==strike) &
            (pd.to_datetime(df["timestamp"])>=w_start) &
            (pd.to_datetime(df["timestamp"])<=w_end)
        ].copy().sort_values("timestamp")

        if win.empty:
            st.info("Window empty.")
            return

        if POK:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=pd.to_datetime(win["timestamp"]), y=win["spot"], name="Spot", mode="lines+markers"
            ))
            if "vwap" in win.columns:
                fig.add_trace(go.Scatter(
                    x=pd.to_datetime(win["timestamp"]), y=win["vwap"], name="VWAP", mode="lines"
                ))
            if "iv" in win.columns:
                fig.add_trace(go.Scatter(
                    x=pd.to_datetime(win["timestamp"]), y=win["iv"], name="IV", mode="lines", yaxis="y2"
                ))
            fig.update_layout(
                title=f"{inst} {typ} {int(strike)} • {ts.strftime('%H:%M')}",
                xaxis_title="Time",
                yaxis_title="Price / VWAP",
                yaxis2=dict(title="IV", overlaying="y", side="right", showgrid=False)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.line_chart(win.set_index(pd.to_datetime(win["timestamp"]))[["spot","vwap"]].dropna(), use_container_width=True)

        # narration
        row_before = win.iloc[0]
        row_after  = win.iloc[-1]
        st.caption("Narration (educational): " + _narrate(row_before, row_after))
