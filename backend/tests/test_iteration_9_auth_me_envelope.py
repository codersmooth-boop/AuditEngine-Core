"""Iteration 9 — `/api/auth/me` envelope contract.

The endpoint used to return HTTP 401 for anon callers, which triggered
Chromium's native `Failed to load resource: 401` devtools console noise on
public/login routes. The contract was changed to ALWAYS return 200 with an
`authenticated` boolean envelope.

Covers:
- Anon: 200 + {authenticated:false}
- Invalid / random cookie: 200 + {authenticated:false}
- Valid cookie: 200 + {authenticated:true, user_id, email, name, picture, leaderboard_opt_in}
- Valid Bearer: same as above
- Regression: /api/audits still requires auth (401 for anon)
- Regression: fetchMe client interprets envelope
"""
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def seeded():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    ts = int(time.time() * 1000)
    uid = f"test-user-i9-{ts}"
    tok = f"test_session_i9_{ts}"
    db.users.insert_one({
        "user_id": uid, "email": f"i9-{ts}@auditengine.test",
        "name": "I9 Test", "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    db.user_sessions.insert_one({
        "user_id": uid, "session_token": tok,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"user_id": uid, "token": tok, "db": db}
    db.users.delete_many({"user_id": uid})
    db.user_sessions.delete_many({"user_id": uid})
    db.audits.delete_many({"user_id": uid})


class TestAuthMeEnvelope:
    def test_anon_returns_200_authenticated_false(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body == {"authenticated": False}

    def test_random_cookie_returns_200_authenticated_false(self):
        r = requests.get(
            f"{BASE_URL}/api/auth/me",
            cookies={"session_token": "totally_bogus_xyz_12345"},
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json() == {"authenticated": False}

    def test_valid_cookie_returns_authenticated_true(self, seeded):
        r = requests.get(
            f"{BASE_URL}/api/auth/me",
            cookies={"session_token": seeded["token"]},
            timeout=10,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["authenticated"] is True
        assert body["user_id"] == seeded["user_id"]
        assert body["email"].startswith("i9-")
        assert body["name"] == "I9 Test"
        assert "picture" in body
        assert body["leaderboard_opt_in"] is False

    def test_valid_bearer_returns_authenticated_true(self, seeded):
        r = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json()["authenticated"] is True


class TestProtectedRoutesRegression:
    def test_audits_anon_still_401(self):
        r = requests.get(f"{BASE_URL}/api/audits", timeout=10)
        assert r.status_code == 401

    def test_audits_authed(self, seeded):
        r = requests.get(
            f"{BASE_URL}/api/audits",
            headers={"Authorization": f"Bearer {seeded['token']}"},
            timeout=10,
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_ledger_snapshot_anon_401(self):
        r = requests.get(f"{BASE_URL}/api/ledger/snapshot?year=2024", timeout=10)
        assert r.status_code == 401

    def test_settings_streak_anon_401(self):
        r = requests.get(f"{BASE_URL}/api/settings/streak", timeout=10)
        assert r.status_code == 401


class TestFrontendCallerContract:
    def test_fetch_me_client_interprets_envelope(self):
        with open("/app/frontend/src/lib/api.js") as f:
            src = f.read()
        # New contract: fetchMe throws on authenticated:false
        assert "authenticated === false" in src or "authenticated===false" in src.replace(" ", ""), \
            "api.js fetchMe must inspect r.data.authenticated"
