import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {"chat_id": CHAT_ID, "text": "✅ Test message from TradingRadarBot"}

r = requests.post(url, data=payload)
print(r.status_code, r.text)
