# ai/train_dummy.py
# Trains a small RandomForest on your anomalies.db for a quick ai_ranker.pkl
import os, sqlite3, joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import brier_score_loss
from feature_store import build_features
from labels import make_labels

DB_FILE = os.path.join("data", "anomalies.db")
MODEL_DIR = os.path.join("models")
MODEL_PATH = os.path.join(MODEL_DIR, "ai_ranker.pkl")

os.makedirs(MODEL_DIR, exist_ok=True)

def load_df(limit=50000):
    if not os.path.exists(DB_FILE): return pd.DataFrame()
    conn = sqlite3.connect(DB_FILE)
    q = """
      SELECT timestamp,instrument,type,strike,expiry,changeInOI,volume,iv,spot,vwap
      FROM anomalies
      ORDER BY id ASC
      LIMIT ?
    """
    df = pd.read_sql(q, conn, params=(limit,))
    conn.close()
    return df

def main():
    raw = load_df()
    if raw.empty:
        print("No data in anomalies.db. Train aborted.")
        return
    feats = build_features(raw)
    y = make_labels(feats).reindex(feats.index).fillna(0).astype(int)

    # Feature set aligned with engine DEFAULT_FEATURES
    cols = [
        "changeInOI_z_15","volume_z_15","iv_z_15",
        "changeInOI_z_5","volume_z_5","iv_z_5",
        "dist_to_vwap_bps","pct_otm","time_bin","is_weekly"
    ]
    for c in cols:
        if c not in feats.columns:
            feats[c] = 0.0
    X = feats[cols].fillna(0)

    # Simple time-series split
    tscv = TimeSeriesSplit(n_splits=5)
    best_model, best_brier = None, 1e9
    for train_idx, test_idx in tscv.split(X):
        clf = RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_leaf=20, random_state=42, n_jobs=-1
        )
        clf.fit(X.iloc[train_idx], y.iloc[train_idx])
        proba = clf.predict_proba(X.iloc[test_idx])[:,1]
        brier = brier_score_loss(y.iloc[test_idx], proba)
        if brier < best_brier:
            best_brier, best_model = brier, clf

    if best_model is None:
        print("Training failed to produce model.")
        return

    joblib.dump(best_model, MODEL_PATH)
    print(f"Saved model → {MODEL_PATH} (brier={best_brier:.4f})")

if __name__ == "__main__":
    main()
