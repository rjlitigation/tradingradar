<<<<<<< HEAD
# app/bootstrap.py
import os, sys, time, threading, subprocess, signal

# Ensure project root on path
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# --- Import your loops (already built earlier) ---
# live updater
from utils.live_updater import update_live_data
# kick a background thread to call update_live_data() every minute
def loop():
    while True:
        try:
            update_live_data()
        except Exception as e:
            print("[bootstrap updater]", e)
        time.sleep(60)
threading.Thread(target=loop, daemon=True).start()

# THEN import streamlit app (so the thread runs alongside)
import app.replay  # noqa: F401

# telegram dispatcher
try:
    from bots.telegram_dispatcher import run_telegram_dispatcher
except Exception as e:
    def run_telegram_dispatcher():
        print(f"[bootstrap] telegram_dispatcher unavailable: {e}")
        while True:
            time.sleep(60)

def _start_daemon(target, name):
    t = threading.Thread(target=target, name=name, daemon=True)
    t.start()
    print(f"[bootstrap] started thread: {name}")
    return t

def main():
    # 1) start background threads
    _start_daemon(run_live_updater, "live_updater")
    _start_daemon(run_telegram_dispatcher, "telegram_dispatcher")

    # 2) launch Streamlit
    cmd = [
        sys.executable, "-m", "streamlit", "run", "app/replay.py",
        "--server.port", os.environ.get("PORT", "10000"),
        "--server.address", "0.0.0.0",
    ]
    print("[bootstrap] launching Streamlit:", " ".join(cmd))

    # Forward SIGTERM to child so Render can stop cleanly
    proc = subprocess.Popen(cmd)

    def handle_sig(sig, frame):
        try:
            proc.terminate()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sig)

    # Wait forever (or until Streamlit exits)
    proc.wait()

if __name__ == "__main__":
    main()
=======
# app/bootstrap.py
"""
Bootstrap runner for TradingRadar
- Ensures database stays live on every Render / UptimeRobot ping
- Runs live updater once so anomalies DB never goes stale
"""

import traceback
from utils.live_updater import update_live_data

def run_bootstrap():
    try:
        wrote = update_live_data()
        print(f"[bootstrap] updater ran, wrote={wrote}")
    except Exception as e:
        print("[bootstrap] updater error:", e)
        traceback.print_exc()

if __name__ == "__main__":
    run_bootstrap()
>>>>>>> 5acb3a7 (Update project files)
