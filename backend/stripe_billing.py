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
from fastapi import APIRouter, Depends, HTTPException, Request
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


def make_router(db, get_current_user):
    router = APIRouter(prefix="/api/payments", tags=["payments"])

    async def _resolve_active_tier(user_id: str) -> dict:
        """Return {tier, active, plan_id, stripe_customer_id, current_period_end}
        for the given user. `tier` is 'free' or a plan_id."""
        _load_stripe_key()
        row = await db.payment_transactions.find_one(
            {"user_id": user_id, "payment_status": "paid",
             "stripe_subscription_id": {"$ne": None}},
            sort=[("updated_at", -1)],
        )
        if not row or not row.get("stripe_subscription_id"):
            return {"tier": "free", "active": False, "plan_id": None,
                    "stripe_customer_id": None, "current_period_end": None}
        try:
            sub = stripe.Subscription.retrieve(row["stripe_subscription_id"])
        except stripe.error.StripeError:
            return {"tier": "free", "active": False, "plan_id": None,
                    "stripe_customer_id": None, "current_period_end": None}
        active = sub.status in ("active", "trialing", "past_due")
        return {
            "tier": row["plan_id"] if active else "free",
            "active": active,
            "plan_id": row["plan_id"],
            "stripe_customer_id": sub.customer if isinstance(sub.customer, str) else sub.customer.id,
            "current_period_end": sub.get("current_period_end") if hasattr(sub, "get") else None,
            "stripe_status": sub.status,
        }

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

    @router.get("/tier")
    async def get_tier(user: dict = Depends(get_current_user)):
        info = await _resolve_active_tier(user["user_id"])
        return info

    class PortalRequest(BaseModel):
        return_url: str

    @router.post("/portal")
    async def create_portal_session(req: PortalRequest, user: dict = Depends(get_current_user)):
        info = await _resolve_active_tier(user["user_id"])
        customer_id = info.get("stripe_customer_id")
        if not customer_id:
            raise HTTPException(400, "No active subscription — nothing to manage")
        _load_stripe_key()
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=req.return_url,
            )
        except stripe.error.InvalidRequestError as e:
            msg = (e.user_message or str(e)).lower()
            if "no configuration" in msg or "default configuration" in msg:
                # Auto-provision a minimal portal configuration for this account.
                cfg = stripe.billing_portal.Configuration.create(
                    business_profile={"headline": "AuditEngine · Manage subscription"},
                    features={
                        "customer_update": {"enabled": True, "allowed_updates": ["email", "address"]},
                        "invoice_history": {"enabled": True},
                        "payment_method_update": {"enabled": True},
                        "subscription_cancel": {"enabled": True, "mode": "at_period_end"},
                        "subscription_update": {
                            "enabled": True, "default_allowed_updates": ["price"],
                            "products": [{"product": stripe.Price.retrieve(list(PLANS.values())[0]).product,
                                          "prices": list(PLANS.values())}],
                        },
                    },
                )
                session = stripe.billing_portal.Session.create(
                    customer=customer_id, return_url=req.return_url, configuration=cfg.id,
                )
            else:
                raise HTTPException(502, f"Stripe error: {e.user_message or str(e)}")
        return {"portal_url": session.url}

    return router


async def handle_stripe_webhook(request: Request, db) -> dict:
    """Registered by server.py at POST /api/webhook/stripe.

    Compatible with both Stripe payload styles:
    - Snapshot: event.data.object contains the full object.
    - Thin:     event.data.object contains only {id, object} — we re-fetch
                via the Stripe API to enrich before persisting.
    """
    _load_stripe_key()
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(400, "Webhook secret not configured")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
    except Exception as e:
        raise HTTPException(400, f"Malformed webhook: {e}")

    obj = event["data"]["object"]
    obj_type = obj.get("object")
    obj_id = obj.get("id")
    t = event["type"]
    now = datetime.now(timezone.utc)

    def _is_thin(o: dict) -> bool:
        # A thin payload carries id/object and little else. We defensively
        # re-fetch anytime a hint field for the given event type is missing.
        return len(o.keys()) <= 3

    # --- checkout.session.* events ------------------------------------------
    if t.startswith("checkout.session.") and obj_type == "checkout.session":
        if _is_thin(obj) or "payment_status" not in obj:
            try:
                obj = stripe.checkout.Session.retrieve(obj_id).to_dict_recursive()
            except stripe.error.StripeError:
                pass

        payment_status = obj.get("payment_status", "pending")
        subscription_id = obj.get("subscription")

        if t == "checkout.session.completed":
            customer_id = obj.get("customer")
            user_id_meta = (obj.get("metadata") or {}).get("user_id")
            await db.payment_transactions.update_one(
                {"session_id": obj_id, "payment_status": {"$ne": "paid"}},
                {"$set": {
                    "status": "completed",
                    "payment_status": payment_status or "paid",
                    "stripe_subscription_id": subscription_id,
                    "stripe_customer_id": customer_id,
                    "amount_total": obj.get("amount_total"),
                    "currency": obj.get("currency"),
                    "updated_at": now,
                }},
            )
            # Link the Stripe customer back to our user record for portal access.
            if user_id_meta and customer_id:
                await db.users.update_one(
                    {"user_id": user_id_meta},
                    {"$set": {"stripe_customer_id": customer_id}},
                )
        elif t == "checkout.session.async_payment_succeeded":
            await db.payment_transactions.update_one(
                {"session_id": obj_id},
                {"$set": {"payment_status": "paid", "status": "completed", "updated_at": now}},
            )
        elif t == "checkout.session.async_payment_failed":
            await db.payment_transactions.update_one(
                {"session_id": obj_id},
                {"$set": {"status": "failed", "payment_status": "failed", "updated_at": now}},
            )
        elif t == "checkout.session.expired":
            await db.payment_transactions.update_one(
                {"session_id": obj_id},
                {"$set": {"status": "expired", "payment_status": "expired", "updated_at": now}},
            )
        return {"status": "ok", "type": t, "session_id": obj_id}

    # --- charge.refunded ----------------------------------------------------
    if t == "charge.refunded":
        pi = obj.get("payment_intent")
        if not pi and _is_thin(obj):
            try:
                obj = stripe.Charge.retrieve(obj_id).to_dict_recursive()
                pi = obj.get("payment_intent")
            except stripe.error.StripeError:
                pass
        if pi:
            await db.payment_transactions.update_one(
                {"stripe_payment_intent_id": pi},
                {"$set": {"status": "refunded", "payment_status": "refunded", "updated_at": now}},
            )
        return {"status": "ok", "type": t, "payment_intent": pi}

    # --- unhandled event types are still 200-OK'd so Stripe doesn't retry ----
    return {"status": "ok", "type": t, "handled": False}
