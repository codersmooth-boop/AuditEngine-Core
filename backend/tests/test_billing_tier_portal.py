"""Iteration 6 — Tests for /api/payments/tier, /api/payments/portal and
webhook user-linking side effects (Stripe BYOK).

Runs against LIVE test-mode Stripe using STRIPE_API_KEY in backend/.env.
Any Customer/Subscription created during the run is torn down in fixtures
(finally blocks) so the user's real Stripe account stays clean.

Test user emails use the pattern testing-agent-*@auditengine.example.
"""
import json
import os
import secrets
import time
import hmac
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get(
    "REACT_APP_BACKEND_URL") else "https://audit-engine-38.preview.emergentagent.com"

PRICE_MONTHLY = "price_1TtrVK2EF5EE1c01gRIxaKIX"
PRICE_YEARLY = "price_1Ttrdg2EF5EE1c01qEOTjEM4"
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]


# ---------------- fixtures ----------------
@pytest.fixture(scope="session")
def mongo_db():
    from pymongo import MongoClient
    c = MongoClient(os.environ["MONGO_URL"])
    return c[os.environ["DB_NAME"]]


@pytest.fixture(scope="session")
def stripe_mod():
    import stripe
    stripe.api_key = os.environ["STRIPE_API_KEY"]
    return stripe


def _seed_user_and_session(mongo_db, email_suffix: str = ""):
    user_id = f"testing-agent-{uuid.uuid4().hex[:12]}"
    email = f"testing-agent-{user_id}{email_suffix}@auditengine.example"
    session_token = secrets.token_urlsafe(32)
    mongo_db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "name": "Testing Agent",
        "leaderboard_opt_in": False,
        "created_at": datetime.now(timezone.utc),
    })
    mongo_db.user_sessions.insert_one({
        "session_token": session_token,
        "user_id": user_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=2),
        "created_at": datetime.now(timezone.utc),
    })
    return user_id, email, session_token


def _cleanup_user(mongo_db, user_id):
    mongo_db.users.delete_many({"user_id": user_id})
    mongo_db.user_sessions.delete_many({"user_id": user_id})
    mongo_db.payment_transactions.delete_many({"user_id": user_id})


def _cookie(session_token):
    return {"session_token": session_token}


# ---------------- 1. Auth gating ----------------
class TestAuthGating:
    def test_tier_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/payments/tier")
        assert r.status_code == 401, r.text

    def test_tier_bad_session_401(self):
        r = requests.get(f"{BASE_URL}/api/payments/tier",
                         cookies={"session_token": "does-not-exist"})
        assert r.status_code == 401

    def test_portal_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/payments/portal",
                          json={"return_url": "https://example.com/back"})
        assert r.status_code == 401


# ---------------- 2. Tier — free user ----------------
class TestTierFreeUser:
    def test_no_transactions_returns_free(self, mongo_db):
        user_id, _, tok = _seed_user_and_session(mongo_db, "-free")
        try:
            r = requests.get(f"{BASE_URL}/api/payments/tier", cookies=_cookie(tok))
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["tier"] == "free"
            assert d["active"] is False
            assert d["plan_id"] is None
            assert d["stripe_customer_id"] is None
        finally:
            _cleanup_user(mongo_db, user_id)

    def test_portal_free_user_400(self, mongo_db):
        user_id, _, tok = _seed_user_and_session(mongo_db, "-free-p")
        try:
            r = requests.post(f"{BASE_URL}/api/payments/portal",
                              json={"return_url": "https://example.com/back"},
                              cookies=_cookie(tok))
            assert r.status_code == 400, r.text
            d = r.json()
            assert "No active subscription" in d.get("detail", "")
        finally:
            _cleanup_user(mongo_db, user_id)


# ---------------- 3. Tier — canceled / non-existent sub ----------------
class TestTierCanceledSub:
    def test_nonexistent_sub_returns_free(self, mongo_db):
        user_id, _, tok = _seed_user_and_session(mongo_db, "-cancel")
        try:
            mongo_db.payment_transactions.insert_one({
                "session_id": f"cs_test_fake_{uuid.uuid4().hex[:8]}",
                "user_id": user_id,
                "plan_id": "professional_monthly",
                "stripe_price_id": PRICE_MONTHLY,
                "stripe_subscription_id": "sub_nonexistent_1234567890",
                "status": "completed",
                "payment_status": "paid",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })
            r = requests.get(f"{BASE_URL}/api/payments/tier", cookies=_cookie(tok))
            assert r.status_code == 200
            d = r.json()
            assert d["tier"] == "free"
            assert d["active"] is False
        finally:
            _cleanup_user(mongo_db, user_id)


# ---------------- 4. Tier + Portal — real active subscription ----------------
class TestTierActiveSubscription:
    @pytest.fixture(scope="class")
    def active_sub_ctx(self, stripe_mod):
        """Create a real Stripe customer + active subscription with tok_visa.
        Tears down in finalizer to avoid billing pollution."""
        customer = stripe_mod.Customer.create(
            email=f"testing-agent-{uuid.uuid4().hex[:8]}@auditengine.example",
            description="AuditEngine iteration_6 test",
        )
        pm = stripe_mod.PaymentMethod.create(
            type="card", card={"token": "tok_visa"},
        )
        stripe_mod.PaymentMethod.attach(pm.id, customer=customer.id)
        stripe_mod.Customer.modify(
            customer.id,
            invoice_settings={"default_payment_method": pm.id},
        )
        # With default PM set on the customer, Stripe will auto-charge the
        # first invoice and the subscription should become active immediately.
        sub = stripe_mod.Subscription.create(
            customer=customer.id,
            items=[{"price": PRICE_MONTHLY}],
        )
        for _ in range(15):
            if sub.status in ("active", "trialing"):
                break
            time.sleep(1)
            sub = stripe_mod.Subscription.retrieve(sub.id)
        yield {"customer_id": customer.id, "subscription_id": sub.id, "status": sub.status}
        # Teardown
        try:
            stripe_mod.Subscription.cancel(sub.id)
        except Exception:
            pass
        try:
            stripe_mod.Customer.delete(customer.id)
        except Exception:
            pass

    def test_active_sub_tier(self, mongo_db, active_sub_ctx):
        assert active_sub_ctx["status"] in ("active", "trialing"), (
            f"Sub did not become active in Stripe: {active_sub_ctx['status']}")
        user_id, _, tok = _seed_user_and_session(mongo_db, "-active")
        try:
            mongo_db.payment_transactions.insert_one({
                "session_id": f"cs_test_seed_{uuid.uuid4().hex[:8]}",
                "user_id": user_id,
                "plan_id": "professional_monthly",
                "stripe_price_id": PRICE_MONTHLY,
                "stripe_subscription_id": active_sub_ctx["subscription_id"],
                "stripe_customer_id": active_sub_ctx["customer_id"],
                "status": "completed",
                "payment_status": "paid",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })
            r = requests.get(f"{BASE_URL}/api/payments/tier", cookies=_cookie(tok))
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["tier"] == "professional_monthly"
            assert d["active"] is True
            assert d["plan_id"] == "professional_monthly"
            assert d["stripe_customer_id"] == active_sub_ctx["customer_id"]
            assert d.get("stripe_status") in ("active", "trialing")
        finally:
            _cleanup_user(mongo_db, user_id)

    def test_portal_paid_user_returns_url(self, mongo_db, active_sub_ctx):
        user_id, _, tok = _seed_user_and_session(mongo_db, "-portal")
        try:
            mongo_db.payment_transactions.insert_one({
                "session_id": f"cs_test_seed_{uuid.uuid4().hex[:8]}",
                "user_id": user_id,
                "plan_id": "professional_monthly",
                "stripe_price_id": PRICE_MONTHLY,
                "stripe_subscription_id": active_sub_ctx["subscription_id"],
                "stripe_customer_id": active_sub_ctx["customer_id"],
                "status": "completed",
                "payment_status": "paid",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })
            r = requests.post(
                f"{BASE_URL}/api/payments/portal",
                json={"return_url": "https://audit-engine-38.preview.emergentagent.com/dashboard"},
                cookies=_cookie(tok),
            )
            assert r.status_code == 200, r.text
            d = r.json()
            assert d["portal_url"].startswith("https://billing.stripe.com/"), d
        finally:
            _cleanup_user(mongo_db, user_id)


# ---------------- 5. Webhook — user linking side-effect ----------------
def _sign_webhook(payload_bytes: bytes, secret: str) -> str:
    ts = str(int(time.time()))
    signed_payload = f"{ts}.".encode() + payload_bytes
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


class TestWebhookUserLinking:
    def _post_webhook(self, event_obj):
        body = json.dumps(event_obj).encode()
        header = _sign_webhook(body, STRIPE_WEBHOOK_SECRET)
        return requests.post(
            f"{BASE_URL}/api/webhook/stripe",
            data=body,
            headers={"Content-Type": "application/json", "Stripe-Signature": header},
        )

    def test_snapshot_payload_links_customer(self, mongo_db):
        user_id, _, _ = _seed_user_and_session(mongo_db, "-wh-snap")
        session_id = f"cs_test_wh_snap_{uuid.uuid4().hex[:10]}"
        customer_id = f"cus_wh_snap_{uuid.uuid4().hex[:10]}"
        # Pre-insert a payment_transactions row so the update matches
        mongo_db.payment_transactions.insert_one({
            "session_id": session_id,
            "user_id": user_id,
            "plan_id": "professional_monthly",
            "stripe_price_id": PRICE_MONTHLY,
            "status": "initiated",
            "payment_status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
        try:
            event = {
                "id": f"evt_{uuid.uuid4().hex}",
                "object": "event",
                "type": "checkout.session.completed",
                "data": {"object": {
                    "id": session_id,
                    "object": "checkout.session",
                    "payment_status": "paid",
                    "status": "complete",
                    "customer": customer_id,
                    "subscription": f"sub_wh_{uuid.uuid4().hex[:8]}",
                    "amount_total": 4900,
                    "currency": "eur",
                    "metadata": {"user_id": user_id, "plan_id": "professional_monthly"},
                }},
            }
            r = self._post_webhook(event)
            assert r.status_code == 200, r.text
            user = mongo_db.users.find_one({"user_id": user_id})
            assert user is not None
            assert user.get("stripe_customer_id") == customer_id, user
            # Also verify payment_transactions row was updated
            row = mongo_db.payment_transactions.find_one({"session_id": session_id})
            assert row["payment_status"] == "paid"
            assert row.get("stripe_customer_id") == customer_id
        finally:
            _cleanup_user(mongo_db, user_id)

    def test_thin_payload_links_customer(self, mongo_db, stripe_mod):
        """Thin webhook payload (id/object only) — handler re-fetches from Stripe.
        We create a real Checkout Session with a real customer + user_id metadata
        so retrieve() succeeds and the side-effect can fire."""
        user_id, _, _ = _seed_user_and_session(mongo_db, "-wh-thin")
        customer = stripe_mod.Customer.create(
            email=f"testing-agent-{uuid.uuid4().hex[:8]}@auditengine.example",
            description="iter6 thin webhook test",
        )
        try:
            session = stripe_mod.checkout.Session.create(
                mode="subscription",
                line_items=[{"price": PRICE_MONTHLY, "quantity": 1}],
                customer=customer.id,
                success_url="https://example.com/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url="https://example.com/cancel",
                metadata={"user_id": user_id, "plan_id": "professional_monthly"},
            )
            mongo_db.payment_transactions.insert_one({
                "session_id": session.id,
                "user_id": user_id,
                "plan_id": "professional_monthly",
                "stripe_price_id": PRICE_MONTHLY,
                "status": "initiated",
                "payment_status": "pending",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })
            event = {
                "id": f"evt_{uuid.uuid4().hex}",
                "object": "event",
                "type": "checkout.session.completed",
                "data": {"object": {
                    "id": session.id,
                    "object": "checkout.session",
                }},
            }
            r = self._post_webhook(event)
            assert r.status_code == 200, r.text
            user = mongo_db.users.find_one({"user_id": user_id})
            assert user.get("stripe_customer_id") == customer.id, user
        finally:
            try:
                stripe_mod.Customer.delete(customer.id)
            except Exception:
                pass
            _cleanup_user(mongo_db, user_id)


# ---------------- 6. Checkout with user_id persists ----------------
class TestCheckoutUserIdPersistence:
    def test_user_id_persisted_in_row(self, mongo_db):
        user_id = f"testing-agent-{uuid.uuid4().hex[:12]}"
        r = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            json={"plan_id": "professional_monthly",
                  "origin_url": "https://audit-engine-38.preview.emergentagent.com",
                  "user_id": user_id},
        )
        assert r.status_code == 200, r.text
        sid = r.json()["session_id"]
        row = mongo_db.payment_transactions.find_one({"session_id": sid})
        assert row is not None
        assert row["user_id"] == user_id
        mongo_db.payment_transactions.delete_one({"session_id": sid})
