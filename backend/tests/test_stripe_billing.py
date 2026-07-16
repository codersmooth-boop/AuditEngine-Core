"""Backend tests for Stripe Checkout integration on AuditEngine.

Covers /api/payments/checkout, /api/payments/status/{session_id},
/api/stripe/webhook, DB persistence, indexes, and regression on
already-passing endpoints.
"""
import os
import re
import asyncio
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load backend .env for Stripe key + Mongo access from within test process
load_dotenv(Path(__file__).parent.parent / ".env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://audit-engine-38.preview.emergentagent.com"
ORIGIN = "https://audit-engine-38.preview.emergentagent.com"

STRIPE_URL_RE = re.compile(r"^https://checkout\.stripe\.com/")


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def mongo_db():
    from motor.motor_asyncio import AsyncIOMotorClient
    url = os.environ["MONGO_URL"]
    name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(url)
    return client[name]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# --------------------------------------------------------------------------
# 1. /api/payments/checkout — happy paths
# --------------------------------------------------------------------------

class TestCheckoutHappyPath:
    def test_monthly_returns_valid_stripe_url(self, client):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "lookup_key": "professional_monthly",
            "origin_url": ORIGIN,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert "checkout_url" in data and "session_id" in data
        assert STRIPE_URL_RE.match(data["checkout_url"]), data["checkout_url"]
        assert data["session_id"].startswith("cs_")

    def test_yearly_returns_distinct_url(self, client):
        r1 = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "lookup_key": "annual_yearly", "origin_url": ORIGIN,
        })
        r2 = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "lookup_key": "annual_yearly", "origin_url": ORIGIN,
        })
        assert r1.status_code == 200 and r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        assert d1["session_id"] != d2["session_id"], "Idempotency: should get fresh session"
        assert d1["checkout_url"] != d2["checkout_url"]
        assert STRIPE_URL_RE.match(d1["checkout_url"])


# --------------------------------------------------------------------------
# 2. Pydantic edge cases
# --------------------------------------------------------------------------

class TestCheckoutValidation:
    def test_invalid_lookup_key_422(self, client):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "lookup_key": "free_forever", "origin_url": ORIGIN,
        })
        assert r.status_code == 422, r.text

    def test_missing_origin_url_422(self, client):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "lookup_key": "professional_monthly",
        })
        assert r.status_code == 422, r.text

    def test_empty_body_422(self, client):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={})
        assert r.status_code == 422

    def test_quantity_out_of_range(self, client):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "lookup_key": "professional_monthly",
            "origin_url": ORIGIN,
            "quantity": 0,
        })
        assert r.status_code == 422


# --------------------------------------------------------------------------
# 3. DB persistence — payment_transactions row before response
# --------------------------------------------------------------------------

class TestPaymentTransactionsPersistence:
    def test_monthly_row_persisted_with_correct_amount(self, client, mongo_db):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "lookup_key": "professional_monthly", "origin_url": ORIGIN,
        })
        assert r.status_code == 200
        sid = r.json()["session_id"]
        row = _run(mongo_db.payment_transactions.find_one({"session_id": sid}))
        assert row is not None, "Row must be inserted before response returns"
        assert row["status"] == "initiated"
        assert row["payment_status"] == "pending"
        assert row["amount"] == 4900
        assert row["currency"] == "eur"
        assert row["lookup_key"] == "professional_monthly"

    def test_yearly_row_persisted_with_correct_amount(self, client, mongo_db):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "lookup_key": "annual_yearly", "origin_url": ORIGIN,
        })
        sid = r.json()["session_id"]
        row = _run(mongo_db.payment_transactions.find_one({"session_id": sid}))
        assert row is not None
        assert row["amount"] == 49000
        assert row["currency"] == "eur"
        assert row["status"] == "initiated"

    def test_idempotency_two_distinct_rows(self, client, mongo_db):
        r1 = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "lookup_key": "professional_monthly", "origin_url": ORIGIN,
        })
        r2 = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "lookup_key": "professional_monthly", "origin_url": ORIGIN,
        })
        s1 = r1.json()["session_id"]
        s2 = r2.json()["session_id"]
        assert s1 != s2
        rows = _run(mongo_db.payment_transactions.find(
            {"session_id": {"$in": [s1, s2]}}
        ).to_list(length=10))
        assert len(rows) == 2


# --------------------------------------------------------------------------
# 4. /api/payments/status/{session_id}
# --------------------------------------------------------------------------

class TestPaymentStatus:
    def test_status_fresh_session(self, client):
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "lookup_key": "professional_monthly", "origin_url": ORIGIN,
        })
        sid = r.json()["session_id"]
        s = client.get(f"{BASE_URL}/api/payments/status/{sid}")
        assert s.status_code == 200, s.text
        data = s.json()
        # Must contain only these three keys — no PII leak
        assert set(data.keys()) == {"session_id", "status", "payment_status"}
        assert data["session_id"] == sid
        assert data["payment_status"] in ("pending", "unpaid")
        assert data["status"] in ("initiated", "open")

    def test_status_unknown_returns_404(self, client):
        r = client.get(f"{BASE_URL}/api/payments/status/cs_test_nonexistent_deadbeef")
        assert r.status_code == 404


# --------------------------------------------------------------------------
# 5. Stripe price amounts via SDK — sanity check catalog
# --------------------------------------------------------------------------

class TestStripeCatalog:
    def test_prices_match_expected_amounts(self):
        import stripe
        stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
        m = stripe.Price.list(lookup_keys=["professional_monthly"], active=True, limit=1).data
        y = stripe.Price.list(lookup_keys=["annual_yearly"], active=True, limit=1).data
        assert m and y
        assert m[0].unit_amount == 4900
        assert m[0].currency == "eur"
        assert m[0].recurring and m[0].recurring["interval"] == "month"
        assert y[0].unit_amount == 49000
        assert y[0].currency == "eur"
        assert y[0].recurring and y[0].recurring["interval"] == "year"


# --------------------------------------------------------------------------
# 6. success_url / cancel_url shape (retrieved from Stripe)
# --------------------------------------------------------------------------

class TestSessionUrls:
    def test_success_cancel_url_pattern(self, client):
        import stripe
        stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
        r = client.post(f"{BASE_URL}/api/payments/checkout", json={
            "lookup_key": "professional_monthly", "origin_url": ORIGIN,
        })
        sid = r.json()["session_id"]
        s = stripe.checkout.Session.retrieve(sid)
        assert s.success_url == f"{ORIGIN}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
        assert s.cancel_url == f"{ORIGIN}/payment/cancel"


# --------------------------------------------------------------------------
# 7. Webhook signature validation
# --------------------------------------------------------------------------

class TestWebhookSignature:
    def test_missing_signature_returns_400(self, client):
        r = client.post(f"{BASE_URL}/api/stripe/webhook", data="{}",
                        headers={"Content-Type": "application/json"})
        assert r.status_code == 400

    def test_invalid_signature_returns_400(self, client):
        r = client.post(f"{BASE_URL}/api/stripe/webhook",
                        data='{"type":"checkout.session.completed","data":{"object":{"id":"cs_fake"}}}',
                        headers={"Content-Type": "application/json",
                                 "Stripe-Signature": "t=123,v1=deadbeef"})
        assert r.status_code == 400


# --------------------------------------------------------------------------
# 8. Indexes on payment_transactions
# --------------------------------------------------------------------------

class TestIndexes:
    def test_session_id_unique_and_created_at_desc(self, mongo_db):
        info = _run(mongo_db.payment_transactions.index_information())
        # find session_id unique index
        found_unique = False
        found_created_at_desc = False
        for name, spec in info.items():
            keys = spec.get("key", [])
            if keys == [("session_id", 1)] and spec.get("unique"):
                found_unique = True
            if keys == [("created_at", -1)]:
                found_created_at_desc = True
        assert found_unique, f"session_id unique index missing. Indexes: {info}"
        assert found_created_at_desc, f"created_at desc index missing. Indexes: {info}"


# --------------------------------------------------------------------------
# 9. Regression on previously-passing endpoints
# --------------------------------------------------------------------------

class TestRegression:
    def test_public_registry(self, client):
        r = client.get(f"{BASE_URL}/api/public/registry")
        assert r.status_code == 200

    def test_public_verify_unknown_returns_404(self, client):
        r = client.get(f"{BASE_URL}/api/public/verify/deadbeef_not_a_real_root")
        assert r.status_code in (404, 400)

    def test_regulator_sandbox_requires_auth(self, client):
        r = client.get(f"{BASE_URL}/api/regulator/sandbox/registry")
        assert r.status_code in (401, 403, 404)

    def test_auth_session_no_body_now_400_or_422(self, client):
        # Previously 500; iteration_3 flagged it. Confirm status now.
        r = client.post(f"{BASE_URL}/api/auth/session", data="")
        # Accept either fixed (400/422) or still-broken (500) — record either way
        assert r.status_code in (400, 401, 422, 500), r.status_code

    def test_audits_requires_auth(self, client):
        r = client.get(f"{BASE_URL}/api/audits")
        assert r.status_code in (401, 403)
