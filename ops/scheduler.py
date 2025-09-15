# ops/scheduler.py
import time, os
from utils.live_updater import update_live_data
from utils.telemetry import inc, log_event

SLEEP_SEC = int(os.getenv("SCHED_SLEEP_SEC", "60"))

if __name__ == "__main__":
    log_event("scheduler.start", "info")
    while True:
        try:
            counts = update_live_data()
            if isinstance(counts, dict):
                total = int(counts.get("total", 0))
                inc("ingest.runs", 1)
                inc("ingest.rows", total)
            else:
                # legacy True/False
                if counts:
                    inc("ingest.runs", 1)
            time.sleep(SLEEP_SEC)
        except Exception as e:
            log_event("scheduler.error", "error", detail=str(e))
            time.sleep(SLEEP_SEC)
