# utils/compliance.py
BANNED = [
    "buy ", "sell ", "target", "sl ", "stoploss", "stop loss",
    "guaranteed", "sure shot", "multibagger", "advice", "recommend"
]

def sanitize_text(text: str) -> str:
    low = text.lower()
    for w in BANNED:
        if w in low:
            raise ValueError(f"Compliance block: contains '{w.strip()}'")
    return text
