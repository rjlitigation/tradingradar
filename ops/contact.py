# app/contact.py
import streamlit as st
import smtplib, os

st.set_page_config(page_title="Contact Us — TradingRadar", layout="wide")

st.title("📩 Contact TradingRadar")
st.write("Have questions, partnership ideas, or feedback? Reach us here:")

name = st.text_input("Your Name")
email = st.text_input("Your Email")
msg = st.text_area("Message")

if st.button("Send"):
    if not (name and email and msg):
        st.error("All fields required.")
    else:
        # For now, just simulate (later: integrate SMTP or API like SendGrid)
        st.success("✅ Message recorded. We'll get back to you shortly.")
        # optional: save to DB/log
        with open("data/contact_log.txt", "a", encoding="utf-8") as f:
            f.write(f"{name} <{email}>: {msg}\n")
