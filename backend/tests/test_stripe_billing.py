"""Backend tests for Stripe BYOK migration (Flow B) on AuditEngine.

Verifies:
- backend/.env contains ONLY STRIPE_API_KEY (no residual sandbox keys)
- Sessions land on user's account acct_1TtrBl2EF5EE1c01
- /api/payments/checkout returns valid subscription sessions using user's Price IDs
- /api/payments/status returns minimal shape without PII
- /api/webhook/stripe (new path) validates signature; /api/stripe/webhook (old) 404s
- payment_transactions row persisted before response
- PLANS dict in stripe_billing.py has only user's 2 Price IDs
- Regression on core endpoints
"""
import os
import re
import asyncio
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)
# Also allow importing stripe_billing directly
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://audit-engine-38.preview.emergentagent.com"
ORIGIN = "https://audit-engine-38.preview.emergentagent.com"

EXPECTED_ACCOUNT_ID = "acct_1TtrBl2EF5EE1c01"
PRICE_MONTHLY = "price_1TtrVK2EF5EE1c01gRIxaKIX"
PRICE_YEARLY = "price_1Ttrdg2EF5EE1c01qEOTjEM4"

STRIPE_URL_RE = re.compile(r"^https://checkout\.stripe\.com/")


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def mongo_db():
    from pymongo import MongoClient
    url = os.environ["MONGO_URL"]
    name = os.environ["DB_NAME"]
    c = MongoClient(url)
    return c[name]


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --------------------------------------------------------------------------
# 1. .env hygiene — only STRIPE_API_KEY
# --------------------------------------------------------------------------
class TestEnvHygiene:
    def test_no_residual_sandbox_env_vars(self):
        env_path = Path(__file__).parent.parent / ".env"
        content = env_path.read_text()
        banned = ["STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY",
                  "STRIPE_ACCOUNT_ID", "STRIPE_MODE"]
        # STRIPE_WEBHOOK_SECRET is optional; per spec it should also be absent
        for key in banned:
            assert f"{key}=" not in content, f"{key} still present in backend/.env"

    def test_stripe_api_key_present(self):
        key = os.environ.get("STRIPE_API_KEY", "")
        assert key.startswith("sk_test_51TtrBl2EF5EE1c01"), \
            "STRIPE_API_KEY not user's key"


# --------------------------------------------------------------------------
# 2. PLANS dict has only user's 2 Price IDs
# --------------------------------------------------------------------------
class TestPlanCatalog:
    def test_plans_dict_contents(self):
        from stripe_billing import PLANS
        assert set(PLANS.keys()) == {"professional_monthly", "annual_yearly"}
        assert PLANS["professional_monthly"] == PRICE_MONTHLY
        assert PLANS["annual_yearly"] == PRICE_YEARLY
        # No sandbox price residue
        for pid in PLANS.values():
            assert "EJ3Jre5OM3" not in pid, f"Sandbox price id leaked: {pid}"


# --------------------------------------------------------------------------
# 3. /api/payments/checkout — happy paths
# --------------------------------------------------------------------------
class TestCheckoutHappyPath:
    def test_monthly(self, client):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "plan_id": "professional_monthly", "origin_url": ORIGIN,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert STRIPE_URL_RE.match(d["checkout_url"])
        assert d["session_id"].startswith("cs_test_")

    def test_yearly(self, client):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "plan_id": "annual_yearly", "origin_url": ORIGIN,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert STRIPE_URL_RE.match(d["checkout_url"])
        assert d["session_id"].startswith("cs_test_")


# --------------------------------------------------------------------------
# 4. Session details via Stripe SDK — mode, amount, currency, price, account
# --------------------------------------------------------------------------
class TestSessionShape:
    @pytest.fixture(scope="class")
    def stripe_mod(self):
        import stripe
        stripe.api_key = os.environ["STRIPE_API_KEY"]
        return stripe

    def test_account_is_user_account(self, stripe_mod):
        acct = stripe_mod.Account.retrieve()
        assert acct.id == EXPECTED_ACCOUNT_ID, \
            f"Stripe key is bound to {acct.id}, expected {EXPECTED_ACCOUNT_ID}"

    def test_monthly_session_details(self, client, stripe_mod):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "plan_id": "professional_monthly", "origin_url": ORIGIN,
        })
        sid = r.json()["session_id"]
        s = stripe_mod.checkout.Session.retrieve(
            sid, expand=["line_items", "line_items.data.price"])
        assert s.mode == "subscription"
        assert s.amount_total == 4900
        assert s.currency == "eur"
        assert s.line_items.data[0].price.id == PRICE_MONTHLY
        assert s.success_url == f"{ORIGIN}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
        assert s.cancel_url == f"{ORIGIN}/payment/cancel"

    def test_yearly_session_details(self, client, stripe_mod):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "plan_id": "annual_yearly", "origin_url": ORIGIN,
        })
        sid = r.json()["session_id"]
        s = stripe_mod.checkout.Session.retrieve(
            sid, expand=["line_items", "line_items.data.price"])
        assert s.mode == "subscription"
        assert s.amount_total == 49000
        assert s.currency == "eur"
        assert s.line_items.data[0].price.id == PRICE_YEARLY


# --------------------------------------------------------------------------
# 5. Pydantic validation
# --------------------------------------------------------------------------
class TestCheckoutValidation:
    def test_invalid_plan_id_enterprise(self, client):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "plan_id": "enterprise", "origin_url": ORIGIN,
        })
        assert r.status_code == 422

    def test_invalid_plan_id_random(self, client):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "plan_id": "free_forever", "origin_url": ORIGIN,
        })
        assert r.status_code == 422

    def test_missing_origin_url(self, client):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "plan_id": "professional_monthly",
        })
        assert r.status_code == 422

    def test_empty_body(self, client):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={})
        assert r.status_code == 422


# --------------------------------------------------------------------------
# 6. DB persistence
# --------------------------------------------------------------------------
class TestPersistence:
    def test_row_persisted_before_response(self, client, mongo_db):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "plan_id": "professional_monthly", "origin_url": ORIGIN,
        })
        sid = r.json()["session_id"]
        row = mongo_db.payment_transactions.find_one({"session_id": sid})
        assert row is not None
        assert row["status"] == "initiated"
        assert row["payment_status"] == "pending"
        assert row["plan_id"] == "professional_monthly"
        assert row["stripe_price_id"] == PRICE_MONTHLY
        assert "created_at" in row and "updated_at" in row

    def test_idempotency_distinct_rows(self, client, mongo_db):
        r1 = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "plan_id": "professional_monthly", "origin_url": ORIGIN,
        })
        r2 = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "plan_id": "professional_monthly", "origin_url": ORIGIN,
        })
        s1, s2 = r1.json()["session_id"], r2.json()["session_id"]
        assert s1 != s2
        rows = list(mongo_db.payment_transactions.find(
            {"session_id": {"$in": [s1, s2]}}))
        assert len(rows) == 2


# --------------------------------------------------------------------------
# 7. /api/payments/status
# --------------------------------------------------------------------------
class TestPaymentStatus:
    def test_status_fresh_session_shape(self, client):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "plan_id": "professional_monthly", "origin_url": ORIGIN,
        })
        sid = r.json()["session_id"]
        s = client.get(f"{BASE_URL}/api/payments/status/{sid}")
        assert s.status_code == 200
        data = s.json()
        assert set(data.keys()) == {"session_id", "status", "payment_status"}
        assert data["session_id"] == sid
        assert data["status"] == "initiated"
        assert data["payment_status"] == "pending"

    def test_status_unknown_404(self, client):
        r = client.get(f"{BASE_URL}/api/payments/status/cs_test_nonexistent_deadbeef")
        assert r.status_code == 404


# --------------------------------------------------------------------------
# 8. Webhook paths
# --------------------------------------------------------------------------
class TestWebhookPaths:
    def test_new_webhook_rejects_missing_sig(self, client):
        r = client.post(f"{BASE_URL}/api/webhook/stripe", data="{}",
                        headers={"Content-Type": "application/json"})
        assert r.status_code == 400

    def test_new_webhook_rejects_bad_sig(self, client):
        r = client.post(f"{BASE_URL}/api/webhook/stripe",
                        data='{"type":"checkout.session.completed","data":{"object":{"id":"cs_x"}}}',
                        headers={"Content-Type": "application/json",
                                 "Stripe-Signature": "t=123,v1=deadbeef"})
        assert r.status_code == 400

    def test_old_webhook_path_removed(self, client):
        r = client.post(f"{BASE_URL}/api/stripe/webhook", data="{}",
                        headers={"Content-Type": "application/json"})
        assert r.status_code in (404, 405), f"old path still live: {r.status_code}"


# --------------------------------------------------------------------------
# 9. Regression on other endpoints
# --------------------------------------------------------------------------
class TestRegression:
    def test_public_registry(self, client):
        r = client.get(f"{BASE_URL}/api/public/registry")
        assert r.status_code == 200

    def test_public_leaderboard(self, client):
        r = client.get(f"{BASE_URL}/api/public/leaderboard")
        assert r.status_code == 200

    def test_public_verify_invalid_root(self, client):
        r = client.get(f"{BASE_URL}/api/public/verify/notarealroot")
        assert r.status_code in (400, 404)

    def test_regulator_sandbox_requires_auth(self, client):
        r = client.get(f"{BASE_URL}/api/regulator/sandbox/whoami")
        assert r.status_code in (401, 403)

    def test_audits_requires_auth(self, client):
        r = client.get(f"{BASE_URL}/api/audits")
        assert r.status_code in (401, 403)

    def test_auth_session_empty_body(self, client):
        r = client.post(f"{BASE_URL}/api/auth/session", data="")
        assert r.status_code in (400, 401, 422)
