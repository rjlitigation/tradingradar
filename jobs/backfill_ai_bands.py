# jobs/backfill_ai_bands.py
# -------------------------------------------------------------------
# Attach ai_band to existing anomalies rows that are missing it.
# Safe on big tables (chunked).
# -------------------------------------------------------------------
from __future__ import annotations
import os, sqlite3, pandas as pd

from ai.engine import AIRanker, DEFAULT_FEATURES

DB_PATH = os.getenv("TR_DB_PATH", "data/anomalies.db")
MODEL_PATH = os.getenv("TR_MODEL_PATH", "models/ai_ranker.pkl")
CHUNK = int(os.getenv("TR_BACKFILL_CHUNK", "2000"))

def _read_missing(conn, limit):
    q = f"""
      SELECT rowid, * FROM anomalies
      WHERE (ai_band IS NULL OR ai_band = '')
      ORDER BY timestamp DESC
      LIMIT {limit}
    """
    return pd.read_sql_query(q, conn)

def _update_rows(conn, df: pd.DataFrame):
    cur = conn.cursor()
    for _, r in df.iterrows():
        cur.execute(
            "UPDATE anomalies SET ai_band=? WHERE rowid=?",
            (str(r["ai_band"] or ""), int(r["rowid"]))
        )
    conn.commit()

def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ranker = AIRanker(MODEL_PATH, feature_cols=DEFAULT_FEATURES)

    total = 0
    while True:
        batch = _read_missing(conn, CHUNK)
        if batch.empty:
            break
        annotated = ranker.annotate(batch)
        _update_rows(conn, annotated[["rowid", "ai_band"]])
        total += len(batch)
        if len(batch) < CHUNK:
            break

    conn.close()
    print(f"Backfilled ai_band on {total} rows.")

if __name__ == "__main__":
    main()
