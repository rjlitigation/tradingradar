# ai/train_ranker.py
# -------------------------------------------------------------------
# Train a fast tabular model from SQLite anomalies → models/ai_ranker.pkl
# - Temporal split (avoid leakage)
# - Optional calibration
# - Saves manifest with metrics + feature list
# -------------------------------------------------------------------
from __future__ import annotations
import os, json, sqlite3, warnings
import numpy as np
import pandas as pd
from datetime import timedelta

warnings.filterwarnings("ignore", category=FutureWarning)

from .feature_store import build_features
from .labels import make_labels
from .engine import DEFAULT_FEATURES

def _load_anomalies(db_path: str, days: int = 45) -> pd.DataFrame:
    if not os.path.exists(db_path):
        raise FileNotFoundError(db_path)
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM anomalies", conn)
    conn.close()
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if days and "timestamp" in df.columns:
        cutoff = df["timestamp"].max() - pd.Timedelta(days=days)
        df = df[df["timestamp"] >= cutoff]
    return df

def _temporal_split(df: pd.DataFrame, valid_frac: float = 0.2):
    df = df.sort_values("timestamp")
    n = len(df)
    k = max(1, int(n * (1 - valid_frac)))
    return df.iloc[:k].copy(), df.iloc[k:].copy()

def _metrics(y_true, p):
    # Basic metrics for quick gating
    eps = 1e-9
    brier = float(np.mean((p - y_true) ** 2))
    # precision@k (k= top 10%)
    k = max(1, int(0.1 * len(p)))
    idx = np.argsort(-p)[:k]
    prec_k = float(np.mean(y_true[idx])) if len(idx) else 0.0
    return {"brier": brier, "precision_at_10pct": prec_k}

def train_and_save(
    db_path: str = "data/anomalies.db",
    model_out: str = "models/ai_ranker.pkl",
    days: int = 45,
) -> dict:
    os.makedirs(os.path.dirname(model_out), exist_ok=True)

    df = _load_anomalies(db_path, days=days)
    if df.empty:
        raise RuntimeError("No data found for training.")

    # Ensure core columns exist
    for c in ["type", "spot", "vwap", "strike", "iv", "volume", "changeInOI", "expiry"]:
        if c not in df.columns:
            df[c] = 0 if c not in ("type", "expiry") else ""

    # Features + labels
    feats = build_features(df)
    y = make_labels(df)

    # Restrict to DEFAULT_FEATURES to avoid fragile deps
    X_cols = [c for c in DEFAULT_FEATURES if c in feats.columns]
    if not X_cols:
        raise RuntimeError("No matching feature columns to train.")

    X = feats[X_cols].replace([np.inf, -np.inf], 0).fillna(0).values
    y = np.asarray(y).astype(int)

    # Temporal split
    df_idx = feats.reset_index(drop=True)
    df_idx["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    trn_mask = df_idx["timestamp"] <= df_idx["timestamp"].quantile(0.8)
    X_tr, y_tr = X[trn_mask], y[trn_mask]
    X_va, y_va = X[~trn_mask], y[~trn_mask]

    # Model: GradientBoosting (robust on tabular, no extra deps)
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.calibration import CalibratedClassifierCV

    base = GradientBoostingClassifier(
        random_state=42,
        n_estimators=200,
        learning_rate=0.05,
        max_depth=3,
        subsample=0.9
    )
    base.fit(X_tr, y_tr)

    # Light calibration if we have enough validation
    calibrated = base
    if len(np.unique(y_va)) > 1 and len(y_va) > 100:
        try:
            calibrated = CalibratedClassifierCV(base, method="isotonic", cv="prefit")
            calibrated.fit(X_va, y_va)
        except Exception:
            from sklearn.linear_model import LogisticRegression
            lr = LogisticRegression(max_iter=200)
            p = base.predict_proba(X_tr)[:, 1]
            lr.fit(p.reshape(-1, 1), y_tr)
            # Wrap as a tiny predictor
            class _Wrap:
                def __init__(self, base, lr): self.base, self.lr = base, lr
                def predict_proba(self, X):
                    p = self.base.predict_proba(X)[:, 1].reshape(-1, 1)
                    q = self.lr.predict_proba(p)[:, 1]
                    return np.vstack([1-q, q]).T
            calibrated = _Wrap(base, lr)

    # Validate
    p_tr = calibrated.predict_proba(X_tr)[:, 1]
    p_va = calibrated.predict_proba(X_va)[:, 1]
    m_tr = _metrics(y_tr, p_tr)
    m_va = _metrics(y_va, p_va)

    # Save
    import joblib
    joblib.dump(calibrated, model_out)

    manifest = {
        "model_path": model_out,
        "feature_cols": X_cols,
        "train_days": days,
        "metrics_train": m_tr,
        "metrics_valid": m_va,
    }
    with open(os.path.splitext(model_out)[0] + ".manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest

if __name__ == "__main__":
    man = train_and_save()
    print(json.dumps(man, indent=2))
