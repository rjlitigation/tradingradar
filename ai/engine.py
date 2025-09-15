# ai/engine.py
# -------------------------------------------------------------------
# Runtime AI ranker with safe fallbacks.
# - If model is missing/corrupt, falls back to deterministic baseline.
# - Exposes DEFAULT_FEATURES used by UI + jobs.
# - Provides annotate(df) helper to attach ai_band.
# -------------------------------------------------------------------
from __future__ import annotations
import os, json
import numpy as np
import pandas as pd

DEFAULT_FEATURES = [
    "changeInOI_z_15", "volume_z_15", "iv_z_5",
    "dist_to_vwap_bps", "pct_otm", "time_bin", "is_weekly"
]

# --- Baseline fallback (no ML) ---
class BaselineRanker:
    """Tiered bands using simple rules that never crash."""
    def __init__(self):
        pass

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        # Expect columns in DEFAULT_FEATURES order (caller ensures)
        # score = z-oi + z-vol + z-iv + mild vwap distance factor
        z_oi   = X[:, 0]
        z_vol  = X[:, 1]
        z_iv   = X[:, 2]
        vwap_b = np.clip(np.abs(X[:, 3]) / 50.0, 0, 1.5)  # 50 bps ≈ 0.5% as heuristic
        raw = 0.45*z_oi + 0.35*z_vol + 0.2*z_iv + 0.15*vwap_b
        # Map to 0..1 via logistic
        p = 1.0 / (1.0 + np.exp(-raw))
        # Return 2-class proba shape (n,2) to match sklearn
        return np.vstack([1-p, p]).T

# --- Main ranker ---
class AIRanker:
    def __init__(self, model_path: str, feature_cols: list[str] = None):
        self.model_path = model_path
        self.cols = feature_cols or DEFAULT_FEATURES
        self.model = None
        self.fallback = BaselineRanker()
        self.manifest = {}
        try:
            import joblib  # lazy import
            if os.path.exists(model_path):
                self.model = joblib.load(model_path)
                # optional manifest
                man_path = os.path.splitext(model_path)[0] + ".manifest.json"
                if os.path.exists(man_path):
                    with open(man_path, "r") as f:
                        self.manifest = json.load(f)
        except Exception:
            self.model = None

    def _ensure_cols(self, feats: pd.DataFrame) -> pd.DataFrame:
        out = feats.copy()
        for c in self.cols:
            if c not in out.columns:
                out[c] = 0.0
        return out

    def _to_X(self, feats: pd.DataFrame) -> np.ndarray:
        X = feats[self.cols].replace([np.inf, -np.inf], 0).fillna(0).values
        return X.astype(float)

    def predict(self, rows: pd.DataFrame) -> pd.DataFrame:
        """Return DataFrame with columns: score, calibrated_band"""
        from .feature_store import build_features  # local import
        feats = build_features(rows)
        feats = self._ensure_cols(feats)
        X = self._to_X(feats)

        try:
            if self.model is not None:
                p = self.model.predict_proba(X)[:, 1]
            else:
                p = self.fallback.predict_proba(X)[:, 1]
        except Exception:
            p = self.fallback.predict_proba(X)[:, 1]

        # Robust banding even for tiny batches
        if len(p) >= 20:
            try:
                bands = pd.qcut(p, q=[0, .5, .8, .95, 1],
                                labels=['typical', 'elevated', 'high', 'very_high'])
            except Exception:
                bands = pd.Series(np.where(p > 0.75, "very_high",
                                   np.where(p > 0.55, "high",
                                   np.where(p > 0.35, "elevated", "typical"))))
        else:
            bands = pd.Series(np.where(p > 0.75, "very_high",
                               np.where(p > 0.55, "high",
                               np.where(p > 0.35, "elevated", "typical"))))

        return pd.DataFrame({"score": p, "calibrated_band": bands}, index=rows.index)

    def annotate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a copy with ai_band column attached."""
        if df is None or df.empty:
            return df
        try:
            preds = self.predict(df)
            out = df.copy()
            out["ai_band"] = preds["calibrated_band"].astype(str).values
            return out
        except Exception:
            out = df.copy()
            out["ai_band"] = ""
            return out
