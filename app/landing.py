# app/landing.py
import os, json, time
import streamlit as st
import requests

BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://www.tradingradar.in")
API_BASE = os.getenv("PUBLIC_API_BASE", f"{BASE_URL}/api")

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
HAS_RAZORPAY = bool(RAZORPAY_KEY_ID)

LIGHT = """
<style>
html,body {background:#0f1116;}
.block-container {padding-top:0.5rem; max-width: 1100px;}
.hero {display:flex; gap:22px; align-items:center; padding:20px; border-radius:16px; background:#151923; border:1px solid #232838;}
.hero h1 {margin:0; font-size:38px; color:#eaeef2;}
.hero p {margin:6px 0 0; color:#a8b0b8;}
.tag {display:inline-block; padding:4px 10px; border-radius:999px; background:#1e2533; color:#8ab4f8; font-weight:700; font-size:12px;}
.card {background:#151923; border:1px solid #232838; border-radius:16px; padding:16px; margin:10px 0;}
.price {font-size:28px; font-weight:800; color:#eaeef2;}
.btn {background:#4c8bf5; color:#fff; border:0; padding:10px 16px; border-radius:10px; font-weight:700;}
.small {color:#95a1ad; font-size:13px;}
.footer {text-align:center; color:#8c99a5; margin-top:24px; font-size:12px;}
</style>
"""
st.set_page_config(page_title="TradingRadar — AI Options Anomaly Radar", page_icon="📈", layout="wide")
st.markdown(LIGHT, unsafe_allow_html=True)

# --- Top Nav ---
cols = st.columns([1,4,2,2])
with cols[0]: st.markdown("<div class='tag'>BETA</div>", unsafe_allow_html=True)
with cols[1]: st.write("")
with cols[2]: 
    st.page_link("app/replay.py", label="Open Dashboard", icon="📊")
with cols[3]:
    st.page_link("app/admin.py", label="Admin Console", icon="🛠️")

st.markdown("""
<link rel="canonical" href="https://www.tradingradar.in/">
<meta name="description" content="AI-powered options anomaly radar for BANKNIFTY and NIFTY. Educational analytics, not advisory.">
<meta property="og:title" content="TradingRadar — AI Options Anomaly Radar">
<meta property="og:description" content="World-class ultramodern SaaS for Indian F&O.">
<meta property="og:url" content="https://www.tradingradar.in/">
""", unsafe_allow_html=True)


# --- Hero ---
st.markdown("<div class='hero'>", unsafe_allow_html=True)
lc, rc = st.columns([3,2])
with lc:
    st.markdown("<h1>AI-powered Options Anomaly Radar</h1>", unsafe_allow_html=True)
    st.markdown("<p>World-class, ultramodern SaaS analytics. Ranked anomalies, VWAP context, daily AI digest — all <b>educational, not advisory</b>. Built for Indian F&O (BANKNIFTY + NIFTY).</p>", unsafe_allow_html=True)
    st.markdown("<p class='small'>Reliable autopilot: safe mode, self-healing feeds, alert cadence guardrails.</p>", unsafe_allow_html=True)
with rc:
    st.image("https://i.imgur.com/b2t0G8I.png")  # placeholder hero image

st.markdown("</div>", unsafe_allow_html=True)

# --- Features ---
st.markdown("### Why TradingRadar")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("<div class='card'><b>AI Ranking</b><br/><span class='small'>“Typical / Elevated / High / Very High” bands + reasons</span></div>", unsafe_allow_html=True)
with c2:
    st.markdown("<div class='card'><b>VWAP Context</b><br/><span class='small'>Live VWAP/spot with status chips per index</span></div>", unsafe_allow_html=True)
with c3:
    st.markdown("<div class='card'><b>Daily AI Digest</b><br/><span class='small'>Compliance-safe session summaries via email/Telegram</span></div>", unsafe_allow_html=True)

# --- Pricing ---
st.markdown("### Pricing")
pc1, pc2, pc3 = st.columns(3)
with pc1:
    st.markdown("<div class='card'><div class='price'>Free</div><div class='small'>Delayed BN heatmap • 1 sample anomaly/day • Guides</div><br/>", unsafe_allow_html=True)
    if st.button("Start Free", key="free_btn"):
        st.switch_page("app/replay.py")
    st.markdown("</div>", unsafe_allow_html=True)

def buy(plan: str, email: str):
    try:
        # call API to create order (Razorpay or simulate)
        r = requests.post(f"{API_BASE}/payments/order", json={"plan": plan, "email": email}, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Payment init failed: {e}")
        return None

def verify(payload: dict):
    try:
        r = requests.post(f"{API_BASE}/payments/verify", json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Verification failed: {e}")
        return None

with pc2:
    st.markdown("<div class='card'><div class='price'>₹499 / mo</div><div class='small'>Tier1: Live BN anomalies (last 20), VWAP live, Replay (3 sessions)</div><br/>", unsafe_allow_html=True)
    email = st.text_input("Email for Tier1", key="email_t1", placeholder="you@email.com")
    if st.button("Buy Tier1", key="t1_btn", disabled=not email):
        order = buy("tier1", email)
        if not order: st.stop()
        if HAS_RAZORPAY and "order_id" in order:
            # embed Razorpay Checkout
            html = f"""
            <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
            <script>
              var options = {{
                "key": "{RAZORPAY_KEY_ID}",
                "amount": "{int(order.get('amount', 49900))}",
                "currency": "INR",
                "name": "TradingRadar",
                "description": "Tier1 subscription",
                "order_id": "{order['order_id']}",
                "handler": function (response){{
                    const payload = {{
                        "plan": "tier1",
                        "email": "{email}",
                        "razorpay_payment_id": response.razorpay_payment_id,
                        "razorpay_order_id": response.razorpay_order_id,
                        "razorpay_signature": response.razorpay_signature
                    }};
                    fetch("{API_BASE}/payments/verify", {{
                        method:"POST", headers:{{"Content-Type":"application/json"}},
                        body: JSON.stringify(payload)
                    }}).then(r=>r.json()).then(d=>{{
                        if(d.ok) {{
                          alert("Payment verified. You are Tier1 now.");
                          window.location = "{BASE_URL}/app/replay.py";
                        }} else {{
                          alert("Verification failed: "+(d.detail||'Unknown'));
                        }}
                    }});
                }},
                "prefill": {{"email": "{email}"}},
                "theme": {{"color": "#4c8bf5"}}
              }};
              var rzp1 = new Razorpay(options);
              rzp1.open();
            </script>
            """
            st.components.v1.html(html, height=20)
        else:
            st.success("Simulated payment success. Open Dashboard and check Tier1.")
            st.switch_page("app/replay.py")
    st.markdown("</div>", unsafe_allow_html=True)

with pc3:
    st.markdown("<div class='card'><div class='price'>₹999 / mo</div><div class='small'>Tier2: NIFTY+BN, full history, AI reasons, CSV full, priority alerts</div><br/>", unsafe_allow_html=True)
    email2 = st.text_input("Email for Tier2", key="email_t2", placeholder="you@email.com")
    if st.button("Buy Tier2", key="t2_btn", disabled=not email2):
        order = buy("tier2", email2)
        if not order: st.stop()
        if HAS_RAZORPAY and "order_id" in order:
            html = f"""
            <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
            <script>
              var options = {{
                "key": "{RAZORPAY_KEY_ID}",
                "amount": "{int(order.get('amount', 99900))}",
                "currency": "INR",
                "name": "TradingRadar",
                "description": "Tier2 subscription",
                "order_id": "{order['order_id']}",
                "handler": function (response){{
                    const payload = {{
                        "plan": "tier2",
                        "email": "{email2}",
                        "razorpay_payment_id": response.razorpay_payment_id,
                        "razorpay_order_id": response.razorpay_order_id,
                        "razorpay_signature": response.razorpay_signature
                    }};
                    fetch("{API_BASE}/payments/verify", {{
                        method:"POST", headers:{{"Content-Type":"application/json"}},
                        body: JSON.stringify(payload)
                    }}).then(r=>r.json()).then(d=>{{
                        if(d.ok) {{
                          alert("Payment verified. You are Tier2 now.");
                          window.location = "{BASE_URL}/app/replay.py";
                        }} else {{
                          alert("Verification failed: "+(d.detail||'Unknown'));
                        }}
                    }});
                }},
                "prefill": {{"email": "{email2}"}},
                "theme": {{"color": "#4c8bf5"}}
              }};
              var rzp2 = new Razorpay(options);
              rzp2.open();
            </script>
            """
            st.components.v1.html(html, height=20)
        else:
            st.success("Simulated payment success. Open Dashboard and check Tier2.")
            st.switch_page("app/replay.py")

st.markdown("<div class='footer'>© 2025 TradingRadar • Educational analytics only • Not SEBI-registered • No advice</div>", unsafe_allow_html=True)
