<<<<<<< HEAD
# utils/diagnose_nse.py
import os, sys
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.nse_fetcher import _ensure_session, NSE_HOME, NSE_OC_PAGE, NSE_OC_API

def run(symbol="BANKNIFTY"):
    s = _ensure_session(force=True)
    print("Has cookie header:", "cookie" in s.headers)
    print("UA:", s.headers.get("user-agent"))

    try:
        r1 = s.get(NSE_OC_PAGE, timeout=12)
        print("OC page status:", r1.status_code)
    except Exception as e:
        print("OC page error:", e); return

    try:
        r2 = s.get(NSE_HOME, timeout=12)
        print("Home status:", r2.status_code)
    except Exception as e:
        print("Home page error:", e); return

    try:
        r3 = s.get(NSE_OC_API.format(symbol=symbol), timeout=14)
        print("API status:", r3.status_code)
        if r3.status_code == 200:
            try:
                j = r3.json()
                print("API ok, top-level keys:", list(j.keys())[:8])
            except Exception as e:
                print("API 200 but JSON parse failed. First 200 chars:\n", r3.text[:200])
        else:
            print("API non-200. First 200 chars:\n", r3.text[:200])
    except Exception as e:
        print("API request error:", e)

if __name__ == "__main__":
    run("BANKNIFTY")
=======
# utils/diagnose_nse.py
import os, sys
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils.nse_fetcher import _ensure_session, NSE_HOME, NSE_OC_PAGE, NSE_OC_API

def run(symbol="BANKNIFTY"):
    s = _ensure_session(force=True)
    print("Has cookie header:", "cookie" in s.headers)
    print("UA:", s.headers.get("user-agent"))

    try:
        r1 = s.get(NSE_OC_PAGE, timeout=12)
        print("OC page status:", r1.status_code)
    except Exception as e:
        print("OC page error:", e); return

    try:
        r2 = s.get(NSE_HOME, timeout=12)
        print("Home status:", r2.status_code)
    except Exception as e:
        print("Home page error:", e); return

    try:
        r3 = s.get(NSE_OC_API.format(symbol=symbol), timeout=14)
        print("API status:", r3.status_code)
        if r3.status_code == 200:
            try:
                j = r3.json()
                print("API ok, top-level keys:", list(j.keys())[:8])
            except Exception as e:
                print("API 200 but JSON parse failed. First 200 chars:\n", r3.text[:200])
        else:
            print("API non-200. First 200 chars:\n", r3.text[:200])
    except Exception as e:
        print("API request error:", e)

if __name__ == "__main__":
    run("BANKNIFTY")
>>>>>>> 5acb3a7 (Update project files)
