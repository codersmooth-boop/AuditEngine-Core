"""Stripe Checkout — BYOK (user-owned Stripe account).

The `emergentintegrations` library only supports `mode='payment'` (one-time), so
we drive the raw `stripe` SDK directly for subscription checkout, using the
user-provided API key from STRIPE_API_KEY.

Routes:
- POST /api/payments/checkout        → create Session (subscription), persist row, return checkout_url
- GET  /api/payments/status/{sid}    → poll session status (used by /payment/success)
- POST /api/webhook/stripe           → Stripe webhook (raw signature verification)

Plan IDs → Stripe Price IDs are mapped server-side. Frontend never sends prices
or amounts. Frontend sends only {plan_id, origin_url}.
"""
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import stripe
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).parent / ".env", override=True)

# Fixed, server-side catalog. Frontend sends only plan_id.
PLANS = {
    "professional_monthly": "price_1TtrVK2EF5EE1c01gRIxaKIX",  # €49/mo
    "annual_yearly":        "price_1Ttrdg2EF5EE1c01qEOTjEM4",  # €490/yr
}

STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


def _load_stripe_key() -> str:
    key = os.environ.get("STRIPE_API_KEY", "").strip()
    if not key:
        raise HTTPException(500, "Stripe not configured (STRIPE_API_KEY missing)")
    stripe.api_key = key
    return key


class CheckoutRequest(BaseModel):
    plan_id: str = Field(..., pattern=r"^(professional_monthly|annual_yearly)$")
    quantity: int = Field(1, ge=1, le=100)
    origin_url: str
    user_id: Optional[str] = None


def make_router(db):
    router = APIRouter(prefix="/api/payments", tags=["payments"])

    @router.post("/checkout")
    async def create_checkout(req: CheckoutRequest):
        _load_stripe_key()
        price_id = PLANS[req.plan_id]
        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                line_items=[{"price": price_id, "quantity": req.quantity}],
                success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{req.origin_url}/payment/cancel",
                metadata={"user_id": req.user_id or "", "plan_id": req.plan_id},
                billing_address_collection="auto",
            )
        except stripe.error.StripeError as e:
            raise HTTPException(502, f"Stripe error: {e.user_message or str(e)}")

        await db.payment_transactions.insert_one({
            "session_id": session.id,
            "user_id": req.user_id,
            "plan_id": req.plan_id,
            "stripe_price_id": price_id,
            "status": "initiated",
            "payment_status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })

        return {"checkout_url": session.url, "session_id": session.id}

    @router.get("/status/{session_id}")
    async def get_status(session_id: str):
        _load_stripe_key()
        record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if not record:
            raise HTTPException(404, "Transaction not found")

        # Webhook fallback: consult Stripe directly if still pending.
        if record.get("payment_status") != "paid":
            try:
                s = stripe.checkout.Session.retrieve(session_id)
                if s.payment_status == "paid" or s.status == "complete":
                    await db.payment_transactions.update_one(
                        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                        {"$set": {
                            "status": "completed",
                            "payment_status": "paid",
                            "stripe_subscription_id": s.subscription,
                            "amount_total": s.amount_total,
                            "currency": s.currency,
                            "updated_at": datetime.now(timezone.utc),
                        }},
                    )
                    record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
            except stripe.error.StripeError:
                pass  # transient; return DB state

        return {
            "session_id": record["session_id"],
            "status": record["status"],
            "payment_status": record["payment_status"],
        }

    return router


async def handle_stripe_webhook(request: Request, db) -> dict:
    """Registered by server.py at POST /api/webhook/stripe."""
    _load_stripe_key()
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    if not STRIPE_WEBHOOK_SECRET:
        # Without a shared secret we cannot trust the payload. Reject.
        raise HTTPException(400, "Webhook secret not configured")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
    except Exception as e:
        raise HTTPException(400, f"Malformed webhook: {e}")

    obj = event["data"]["object"]
    t = event["type"]
    now = datetime.now(timezone.utc)
    if t == "checkout.session.completed":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
            {"$set": {
                "status": "completed",
                "payment_status": obj.get("payment_status", "paid"),
                "stripe_subscription_id": obj.get("subscription"),
                "updated_at": now,
            }},
        )
    elif t == "checkout.session.async_payment_succeeded":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"]},
            {"$set": {"payment_status": "paid", "updated_at": now}},
        )
    elif t == "checkout.session.async_payment_failed":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"]},
            {"$set": {"status": "failed", "payment_status": "failed", "updated_at": now}},
        )
    elif t == "checkout.session.expired":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"]},
            {"$set": {"status": "expired", "payment_status": "expired", "updated_at": now}},
        )
    elif t == "charge.refunded":
        await db.payment_transactions.update_one(
            {"stripe_payment_intent_id": obj.get("payment_intent")},
            {"$set": {"status": "refunded", "payment_status": "refunded", "updated_at": now}},
        )
    return {"status": "ok"}
