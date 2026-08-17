"""Standalone FastAPI receiver for Razorpay webhooks; Streamlit remains separate."""
import hashlib
import json
from fastapi import FastAPI, Header, HTTPException, Request

from core.billing.razorpay_service import RazorpayBillingService
from core.billing.razorpay_webhook import RazorpayWebhookProcessor
from database.database import Database

app = FastAPI(title="AgentStock Razorpay Webhook")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/razorpay/webhook")
async def razorpay_webhook(request: Request, x_razorpay_signature: str | None = Header(default=None), x_razorpay_event_id: str | None = Header(default=None)):
    raw = await request.body()
    if not x_razorpay_signature:
        raise HTTPException(status_code=400, detail="Missing Razorpay signature")
    if not RazorpayBillingService().verify_webhook_signature(raw, x_razorpay_signature):
        raise HTTPException(status_code=401, detail="Invalid Razorpay signature")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Malformed webhook payload") from exc
    event_id = x_razorpay_event_id or hashlib.sha256(raw).hexdigest()
    try:
        return RazorpayWebhookProcessor(Database("agentstock.db")).process(event_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Malformed webhook payload") from exc
