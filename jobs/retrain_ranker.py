# jobs/retrain_ranker.py
# -------------------------------------------------------------------
# Nightly retrain with safe promotion based on Brier score.
# -------------------------------------------------------------------
from __future__ import annotations
import os, json, shutil

from ai.train_ranker import train_and_save

DB_PATH = os.getenv("TR_DB_PATH", "data/anomalies.db")
MODEL_PATH = os.getenv("TR_MODEL_PATH", "models/ai_ranker.pkl")

def _load_manifest(path: str) -> dict:
    man_path = os.path.splitext(path)[0] + ".manifest.json"
    if os.path.exists(man_path):
        with open(man_path, "r") as f:
            return json.load(f)
    return {}

def main():
    tmp_model = MODEL_PATH + ".new"
    tmp = train_and_save(db_path=DB_PATH, model_out=tmp_model, days=int(os.getenv("TR_TRAIN_DAYS", "60")))
    old = _load_manifest(MODEL_PATH)

    old_brier = float(old.get("metrics_valid", {}).get("brier", 9e9)) if old else 9e9
    new_brier = float(tmp.get("metrics_valid", {}).get("brier", 9e8))

    # Promote if better by at least 5% (or if no old model)
    improve = (old_brier - new_brier) / max(1e-9, old_brier) if old_brier < 9e9 else 1.0
    if not old or improve >= 0.05:
        # atomically replace
        if os.path.exists(MODEL_PATH):
            shutil.move(MODEL_PATH, MODEL_PATH + ".bak")
        shutil.move(tmp_model, MODEL_PATH)
        with open(os.path.splitext(MODEL_PATH)[0] + ".manifest.json", "w") as f:
            json.dump(tmp, f, indent=2)
        print(f"Promoted new model. ΔBrier={improve:.2%}")
    else:
        # discard
        try: os.remove(tmp_model)
        except: pass
        print(f"Kept old model. New not better. ΔBrier={improve:.2%}")

if __name__ == "__main__":
    main()
