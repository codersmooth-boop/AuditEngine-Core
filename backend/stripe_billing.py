"""Stripe Checkout — /api/payments/{checkout,status,webhook} for AuditEngine.

Flow A · SMP (Stripe-managed payments + tax) — country FI, digital SaaS.
Lookup keys: professional_monthly · annual_yearly.
"""
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import stripe
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).parent / ".env")

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


class CheckoutRequest(BaseModel):
    lookup_key: str = Field(..., pattern=r"^(professional_monthly|annual_yearly)$")
    quantity: int = Field(1, ge=1, le=100)
    origin_url: str
    user_id: Optional[str] = None


def make_router(db):
    router = APIRouter(prefix="/api/payments", tags=["payments"])

    @router.post("/checkout")
    async def create_checkout(req: CheckoutRequest):
        prices = stripe.Price.list(lookup_keys=[req.lookup_key], active=True, limit=1).data
        if not prices:
            raise HTTPException(500, f"Price not found: {req.lookup_key}")
        price = prices[0]
        kwargs = dict(
            line_items=[{"price": price.id, "quantity": req.quantity}],
            mode="subscription" if price.recurring else "payment",
            success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{req.origin_url}/payment/cancel",
            metadata={"user_id": req.user_id or "", "lookup_key": req.lookup_key},
        )
        try:
            session = stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
        except stripe.error.InvalidRequestError as e:
            msg = (e.user_message or str(e)).lower()
            if "managed payments" in msg or "ineligible" in msg:
                session = stripe.checkout.Session.create(
                    **kwargs,
                    automatic_tax={"enabled": True},
                    billing_address_collection="required",
                )
            else:
                raise
        await db.payment_transactions.insert_one({
            "session_id": session.id,
            "user_id": req.user_id,
            "lookup_key": req.lookup_key,
            "amount": (price.unit_amount or 0) * req.quantity,
            "currency": price.currency,
            "status": "initiated",
            "payment_status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
        return {"checkout_url": session.url, "session_id": session.id}

    @router.get("/status/{session_id}")
    async def get_status(session_id: str):
        record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if not record:
            raise HTTPException(404, "Transaction not found")
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
                            "stripe_payment_intent_id": s.payment_intent,
                            "updated_at": datetime.now(timezone.utc),
                        }},
                    )
                    record = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
            except stripe.error.StripeError:
                pass
        return {
            "session_id": record["session_id"],
            "status": record["status"],
            "payment_status": record["payment_status"],
        }

    return router


async def handle_stripe_webhook(request: Request, db) -> dict:
    """Registered at /api/stripe/webhook by server.py."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
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
                "stripe_payment_intent_id": obj.get("payment_intent"),
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
