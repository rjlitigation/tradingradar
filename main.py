import time
from datetime import datetime
import pytz

from utils.nse_fetcher import fetch_option_chain
from utils.analyzer import analyze_anomalies
from utils.vwap_tracker import get_vwap_for
from bots.telegram_alert import send_alert
from utils.storage import init_db, save_anomaly
from utils.db_users import init_user_db
init_user_db()

from flask import Flask
from app.legal import legal_bp

app = Flask(__name__)
app.register_blueprint(legal_bp)

@app.route("/")
def home():
    return "TradingRadar Platform is Live 🚀"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)


INSTRUMENTS = ["BANKNIFTY", "NIFTY"]

sent_cache = set()      # to suppress duplicates after alert sent
persistence = {}        # to require consecutive confirmations

def top3_volume_surge(analyzed_df):
    """Return top 3 rows (by volume) among volume_surge=True."""
    sub = analyzed_df[analyzed_df["volume_surge"]].copy()
    if sub.empty:
        return []
    sub = sub.sort_values("volume", ascending=False).head(3)
    triples = []
    for _, r in sub.iterrows():
        triples.append((r["type"], int(r["strike"]), r["expiry"], int(r["volume"])))
    return triples

def market_open():
    """IST market hours 09:15–15:30."""
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist).time()
    return (now >= datetime.strptime("09:15", "%H:%M").time() and
            now <= datetime.strptime("15:30", "%H:%M").time())

def vwap_status_line(instrument):
    spot, vwap = get_vwap_for(instrument)
    if spot is not None and vwap is not None:
        if spot > vwap:
            status = "Spot above VWAP"
        elif spot < vwap:
            status = "Spot below VWAP"
        else:
            status = "Spot equal to VWAP"
        print(f"📊 [{instrument}] {status} | Spot={spot:.2f}, VWAP={vwap:.2f}")
        return status, spot, vwap
    else:
        print(f"⚠️ [{instrument}] VWAP data unavailable")
        return "VWAP data unavailable", spot, vwap

def run_once_for(instrument):
    # 1) VWAP context
    vwap_status, spot, vwap = vwap_status_line(instrument)

    # 2) Fetch option chain
    df = fetch_option_chain(symbol=instrument)
    if df.empty:
        print(f"⚠️ [{instrument}] No data fetched this cycle.")
        return

    # 3) Analyze & score
    analyzed = analyze_anomalies(df)
    anomalies = analyzed[analyzed["anomaly"]]

    # Send a concise summary once per cycle (top 3 volume surges)
    top3 = top3_volume_surge(analyzed)
    if top3:
        summary_lines = [f"{t} {s} {e} (Vol {v})" for (t, s, e, v) in top3]
        summary_msg = f"📊 [{instrument}] Top 3 Volume Surges:\n" + "\n".join("• " + line for line in summary_lines)
        send_alert(summary_msg)
    
    # 4) Alert logic: score>=2 and persistence>=2
    for _, row in anomalies.iterrows():
        key = f"{instrument}_{row['type']}_{row['strike']}_{row['expiry']}"
        score = int(row.get("anomaly_score", 0))

        if score >= 2:
            persistence[key] = persistence.get(key, 0) + 1
            if persistence[key] >= 2 and key not in sent_cache:
                msg = (f"⚡ [{instrument}] Strong Anomaly (Score {score}/3)\n"
                       f"Type: {row['type']} | Strike: {row['strike']} | Expiry: {row['expiry']}\n"
                       f"OI: {row['openInterest']} (Δ {row['changeInOI']}) | "
                       f"Vol: {row['volume']} | IV: {row['iv']:.2f} | LTP: {row['ltp']}\n"
                       f"Flags → OI:{row['oi_surge']} Vol:{row['volume_surge']} IV:{row['iv_spike']}\n"
                       f"VWAP Status → {vwap_status}"
                       + (f" (Spot={spot:.2f}, VWAP={vwap:.2f})" if (spot is not None and vwap is not None) else "")
                      )
                send_alert(msg)
                sent_cache.add(key)
                save_anomaly(instrument, row, vwap_status, spot, vwap)
        else:
            persistence[key] = 0

def main_loop():
    print("🔁 Starting TradingRadar loop (BANKNIFTY + NIFTY)...")
    init_db()

    while True:
        if market_open():
            for instrument in INSTRUMENTS:
                run_once_for(instrument)
        else:
            print("⏸️ Market closed. Waiting...")

        time.sleep(120)  # every 2 minutes

if __name__ == "__main__":
    main_loop()
