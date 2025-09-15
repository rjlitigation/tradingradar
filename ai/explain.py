# ai/explain.py
from typing import List, Tuple
import numpy as np

def explain_tree_shap(model, x_row: np.ndarray, feature_names: List[str], top_k: int = 5) -> list[tuple[str, float]]:
    """
    SHAP explanation for tree models. Falls back gracefully if shap is missing.
    """
    try:
        import shap
    except Exception:
        # Fallback: no shap → empty reasons
        return []

    try:
        explainer = shap.TreeExplainer(model)
        vals = explainer.shap_values(x_row.reshape(1, -1))
        # Handle shap output variants
        if isinstance(vals, list) and len(vals) > 1:
            v = vals[1][0]
        else:
            v = np.array(vals)[0]
        pairs = sorted(zip(feature_names, v), key=lambda t: abs(t[1]), reverse=True)[:top_k]
        return [(str(n), float(val)) for n, val in pairs]
    except Exception:
        return []
