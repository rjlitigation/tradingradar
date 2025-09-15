# utils/prefs.py
import os, json
from threading import Lock

_PREFS = {}
_LOCK = Lock()
_PATH = os.path.join("data","user_prefs.json")

def _load():
    global _PREFS
    if not os.path.exists(_PATH):
        _PREFS = {}
        return
    try:
        with open(_PATH,"r",encoding="utf-8") as f:
            _PREFS = json.load(f)
    except Exception:
        _PREFS = {}

def _save():
    os.makedirs(os.path.dirname(_PATH), exist_ok=True)
    tmp = _PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_PREFS, f, indent=2, ensure_ascii=False)
    os.replace(tmp, _PATH)

def get_prefs(email: str) -> dict:
    with _LOCK:
        if not _PREFS:
            _load()
        return _PREFS.get(email.lower().strip(), {})

def save_prefs(email: str, prefs: dict):
    with _LOCK:
        if not _PREFS:
            _load()
        _PREFS[email.lower().strip()] = prefs or {}
        _save()
