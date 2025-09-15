# bots/telegram_alert.py
from __future__ import annotations
import os, json, time, requests
from utils.telemetry import inc

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram_alert(text: str, chat_id: str | None = None, parse_mode: str = "HTML") -> bool:
    """
    Sends a Telegram message. Returns True on success.
    Records metrics: alerts.sent
    Logs an event on failure.
    """
    token = BOT_TOKEN
    chat  = chat_id or CHAT_ID
    if not token or not chat:
        log_event("alert.telegram.misconfig", "error", "Missing BOT_TOKEN or CHAT_ID")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": True}

    try:
        r = requests.post(url, data=payload, timeout=10)
        ok = (r.status_code == 200) and (r.json().get("ok") is True)
        if ok:
            try:
                inc("alerts.sent", 1)
            except Exception:
                pass
            return True
        else:
            log_event("alert.telegram.failure", "error", json.dumps({"status": r.status_code, "body": r.text})[:2000])
            return False
    except Exception as e:
        log_event("alert.telegram.exception", "error", str(e))
        return False
