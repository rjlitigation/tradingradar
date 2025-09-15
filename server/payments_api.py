# server/payments_api.py
import os, time, hmac, hashlib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from utils.db_users import update_plan, get_user, add_user
from utils.telemetry import log_event, get_counters_snapshot

app = FastAPI(title="TradingRadar Payments API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
HAS_RP = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)

if HAS_RP:
    import razorpay
    rp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

PLAN_PRICES = {"tier1": 49900, "tier2": 99900}  # in paise

class OrderReq(BaseModel):
    plan: str
    email: str

class VerifyReq(BaseModel):
    plan: str
    email: str
    razorpay_payment_id: str | None = None
    razorpay_order_id: str | None = None
    razorpay_signature: str | None = None

@app.get("/health")
def health():
    return {"ok": True, "ts": int(time.time())}

@app.post("/payments/order")
def create_order(req: OrderReq):
    plan = req.plan.lower()
    if plan not in PLAN_PRICES:
        raise HTTPException(400, "Invalid plan")
    amount = PLAN_PRICES[plan]
    if not HAS_RP:
        # simulate order
        oid = f"sim_{int(time.time())}"
        log_event("payment.order.sim", "info", plan=plan, email=req.email)
        return {"ok": True, "order_id": oid, "amount": amount, "simulate": True}
    order = rp_client.order.create(dict(amount=amount, currency="INR", payment_capture=1))
    log_event("payment.order.created", "info", plan=plan, email=req.email, order_id=order.get("id"))
    return {"ok": True, "order_id": order.get("id"), "amount": amount}

@app.post("/payments/verify")
def verify(req: VerifyReq):
    plan = req.plan.lower()
    if plan not in PLAN_PRICES:
        raise HTTPException(400, "Invalid plan")
    email = req.email.strip().lower()
    # Ensure user exists
    if not get_user(email):
        add_user(email, "Subscriber")
    if not HAS_RP:
        # simulate success
        update_plan(email, plan, months=1)
        log_event("payment.verified.sim", "info", plan=plan, email=email)
        return {"ok": True, "simulate": True}
    # real signature verify
    if not (req.razorpay_payment_id and req.razorpay_order_id and req.razorpay_signature):
        raise HTTPException(400, "Missing Razorpay fields")
    body = f"{req.razorpay_order_id}|{req.razorpay_payment_id}"
    expected_sig = hmac.new(RAZORPAY_KEY_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    if expected_sig != req.razorpay_signature:
        log_event("payment.verify.failed", "warn", plan=plan, email=email)
        raise HTTPException(400, "Signature mismatch")
    update_plan(email, plan, months=1)
    log_event("payment.verified", "info", plan=plan, email=email, order_id=req.razorpay_order_id)
    return {"ok": True}
    
@app.get("/status/summary")
def status_summary():
    # limited, safe info for public status
    manifest = {}
    try:
        import json, os
        with open(os.path.join("models","manifest.json"),"r",encoding="utf-8") as f:
            m = json.load(f)
            manifest = {
                "model_id": m.get("model_id"),
                "trained_on": m.get("trained_on"),
                "metrics": m.get("metrics", {}),
            }
    except Exception:
        manifest = {}
    return {
        "ok": True,
        "ts": int(time.time()),
        "autopilot": autopilot_status(),
        "telemetry": get_counters_snapshot(),
        "model": manifest
    }
