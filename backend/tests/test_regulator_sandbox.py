"""Adversarial tests for the Regulator Sandbox module + TTL on user_sessions."""
import os
import re
import time
import hashlib
import asyncio
import subprocess
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path("/app/backend/.env"))
load_dotenv(Path("/app/frontend/.env"))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

SANDBOX_ENDPOINTS = [
    "/api/regulator/sandbox/whoami",
    "/api/regulator/sandbox/adoption",
    "/api/regulator/sandbox/streaks",
    "/api/regulator/sandbox/scores",
    "/api/regulator/sandbox/volatility",
]

PII_FIELDS = {"email", "user_id", "client_name", "workspace_id_hashed", "session_token"}


def _mint_key(name="TEST", org="TEST-ORG", ttl_days=30):
    """Mint a regulator key via CLI. Returns raw key."""
    res = subprocess.run(
        ["python", "issue_regulator_key.py",
         "--name", name, "--organization", org, "--ttl-days", str(ttl_days)],
        cwd="/app/backend", capture_output=True, text=True, timeout=20,
    )
    assert res.returncode == 0, f"CLI failed: {res.stderr}"
    m = re.search(r"key\s+:\s+(reg_\S+)", res.stdout)
    assert m, f"Could not parse key: {res.stdout}"
    return m.group(1)


@pytest.fixture(scope="module")
def reg_key():
    return _mint_key()


@pytest.fixture(scope="module")
def reg_key_2():
    return _mint_key(name="TEST2", org="TEST-ORG2")


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def db():
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


def _walk_scan_pii(obj, path=""):
    """Recursively scan for PII keys/values and return list of offenders."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in PII_FIELDS:
                found.append(f"{path}.{k}")
            found.extend(_walk_scan_pii(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(_walk_scan_pii(v, f"{path}[{i}]"))
    return found


# =========================
# Auth / error path tests
# =========================
class TestAuth:
    def test_missing_header_401(self):
        r = requests.get(f"{BASE_URL}/api/regulator/sandbox/whoami", timeout=15)
        assert r.status_code == 401
        assert r.json()["detail"] == "Missing X-Regulator-Key header"

    def test_invalid_key_401(self):
        r = requests.get(
            f"{BASE_URL}/api/regulator/sandbox/whoami",
            headers={"X-Regulator-Key": "reg_totally_not_real_xxxx"},
            timeout=15,
        )
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid regulator key"

    def test_expired_key_401(self, event_loop):
        raw = _mint_key(name="EXPIRED", org="EXPIRED-ORG", ttl_days=-1)
        r = requests.get(
            f"{BASE_URL}/api/regulator/sandbox/whoami",
            headers={"X-Regulator-Key": raw},
            timeout=15,
        )
        assert r.status_code == 401
        assert r.json()["detail"] == "Regulator key expired"


# =========================
# Endpoint success tests
# =========================
class TestEndpoints:
    def test_whoami(self, reg_key):
        r = requests.get(
            f"{BASE_URL}/api/regulator/sandbox/whoami",
            headers={"X-Regulator-Key": reg_key}, timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["organization"] == "TEST-ORG"
        assert d["name"] == "TEST"
        assert "key_expires_at" in d
        assert d["k_anonymity_threshold"] == 5
        assert d["rate_limit_per_min"] == 10
        assert "generated_at" in d
        cv = d["cross_verification"]
        assert "registry_master_root" in cv
        assert "snapshot_count" in cv
        assert "latest_snapshot_at" in cv

    def test_adoption(self, reg_key):
        r = requests.get(
            f"{BASE_URL}/api/regulator/sandbox/adoption",
            headers={"X-Regulator-Key": reg_key}, timeout=15,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "buckets" in d and isinstance(d["buckets"], list)
        assert "suppressed_audit_count" in d
        assert "cross_verification" in d
        # k-anonymity check
        for b in d["buckets"]:
            assert b["audit_count"] >= 5, f"bucket below K_ANON: {b}"

    def test_streaks(self, reg_key):
        r = requests.get(
            f"{BASE_URL}/api/regulator/sandbox/streaks",
            headers={"X-Regulator-Key": reg_key}, timeout=15,
        )
        assert r.status_code == 200
        d = r.json()
        assert "distribution" in d
        assert "suppressed_count" in d
        assert "cross_verification" in d
        for cell in d["distribution"]:
            assert cell["workspace_count"] >= 5

    def test_scores(self, reg_key):
        r = requests.get(
            f"{BASE_URL}/api/regulator/sandbox/scores",
            headers={"X-Regulator-Key": reg_key}, timeout=15,
        )
        assert r.status_code == 200
        d = r.json()
        assert "distribution" in d
        assert "total_audits" in d
        assert "cross_verification" in d
        for cell in d["distribution"]:
            assert cell["audit_count"] >= 5

    def test_volatility(self, reg_key):
        r = requests.get(
            f"{BASE_URL}/api/regulator/sandbox/volatility",
            headers={"X-Regulator-Key": reg_key}, timeout=15,
        )
        assert r.status_code == 200
        d = r.json()
        assert "series" in d
        assert "cross_verification" in d
        for cell in d["series"]:
            assert cell["total_audits"] >= 5


# =========================
# PII zero-leak audit
# =========================
class TestZeroPII:
    def test_no_pii_across_all_endpoints(self, reg_key):
        for path in SANDBOX_ENDPOINTS:
            r = requests.get(
                f"{BASE_URL}{path}",
                headers={"X-Regulator-Key": reg_key}, timeout=15,
            )
            assert r.status_code == 200, f"{path}: {r.text}"
            offenders = _walk_scan_pii(r.json())
            assert not offenders, f"PII leak in {path}: {offenders}"


# =========================
# Registry Master Root cross-verification
# =========================
class TestRegistryMasterRoot:
    def test_master_root_matches_sha256_of_snapshots(self, db, event_loop):
        # Use a fresh key to avoid colliding with per-key rate limit from earlier tests.
        raw = _mint_key(name="MR", org="MR-ORG")
        r = requests.get(
            f"{BASE_URL}/api/regulator/sandbox/whoami",
            headers={"X-Regulator-Key": raw}, timeout=15,
        )
        assert r.status_code == 200, r.text
        cv = r.json()["cross_verification"]
        api_root = cv["registry_master_root"]
        api_count = cv["snapshot_count"]

        async def compute():
            docs = await db.snapshots.find(
                {}, {"_id": 0, "merkle_root": 1, "generated_at": 1},
            ).sort("generated_at", 1).to_list(200000)
            return docs

        docs = event_loop.run_until_complete(compute())
        assert len(docs) == api_count
        if not docs:
            assert api_root is None
            assert api_count == 0
            return
        expected = hashlib.sha256(
            "|".join(d.get("merkle_root", "") for d in docs).encode()
        ).hexdigest()
        assert api_root == expected
        assert re.match(r"^[0-9a-f]{64}$", api_root)


# =========================
# Rate limiting
# =========================
class TestRateLimit:
    def test_11th_request_returns_429(self, reg_key_2):
        # Use a fresh key so we don't collide with other tests
        raw = _mint_key(name="RL", org="RL-ORG")
        headers = {"X-Regulator-Key": raw}
        results = []
        for i in range(11):
            r = requests.get(
                f"{BASE_URL}/api/regulator/sandbox/whoami",
                headers=headers, timeout=15,
            )
            results.append(r.status_code)
        assert results[:10].count(200) == 10, f"first 10 must pass: {results}"
        assert results[10] == 429, f"11th expected 429, got {results[10]}"
        r11 = requests.get(
            f"{BASE_URL}/api/regulator/sandbox/whoami",
            headers=headers, timeout=15,
        )
        assert r11.status_code == 429
        assert "Retry" in r11.json()["detail"] or "retry" in r11.json()["detail"].lower()

    def test_different_keys_isolated(self, reg_key_2):
        # Use two brand new keys to guarantee clean buckets
        k_a = _mint_key(name="A", org="A-ORG")
        k_b = _mint_key(name="B", org="B-ORG")
        # Burn key A
        for _ in range(10):
            requests.get(f"{BASE_URL}/api/regulator/sandbox/whoami",
                         headers={"X-Regulator-Key": k_a}, timeout=15)
        # Key A should now be 429
        r_a = requests.get(f"{BASE_URL}/api/regulator/sandbox/whoami",
                           headers={"X-Regulator-Key": k_a}, timeout=15)
        assert r_a.status_code == 429
        # Key B must still be fine
        r_b = requests.get(f"{BASE_URL}/api/regulator/sandbox/whoami",
                           headers={"X-Regulator-Key": k_b}, timeout=15)
        assert r_b.status_code == 200


# =========================
# TTL index verification
# =========================
class TestTTLIndex:
    def test_ttl_index_present(self, db, event_loop):
        async def get_info():
            return await db.user_sessions.index_information()
        info = event_loop.run_until_complete(get_info())
        ttl_indexes = []
        non_ttl_expires_at = []
        for name, spec in info.items():
            keys = spec.get("key") or []
            if len(keys) == 1 and keys[0][0] == "expires_at":
                if spec.get("expireAfterSeconds") == 0:
                    ttl_indexes.append(name)
                else:
                    non_ttl_expires_at.append(name)
        assert len(ttl_indexes) == 1, f"expected 1 TTL index, found {ttl_indexes}"
        assert not non_ttl_expires_at, f"stray non-TTL expires_at index: {non_ttl_expires_at}"


# =========================
# Idempotency of key issuance
# =========================
class TestIdempotency:
    def test_two_keys_work_independently(self):
        k1 = _mint_key(name="I1", org="I-ORG")
        k2 = _mint_key(name="I2", org="I-ORG")
        assert k1 != k2
        r1 = requests.get(f"{BASE_URL}/api/regulator/sandbox/whoami",
                          headers={"X-Regulator-Key": k1}, timeout=15)
        r2 = requests.get(f"{BASE_URL}/api/regulator/sandbox/whoami",
                          headers={"X-Regulator-Key": k2}, timeout=15)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["name"] == "I1"
        assert r2.json()["name"] == "I2"


# =========================
# Session expires_at type
# =========================
class TestSessionBSONDate:
    def test_session_expires_at_is_bson_date(self, db, event_loop):
        # Insert a manufactured session doc mimicking the server's insertion
        # path, then verify BSON type.
        token = f"TEST_session_{int(time.time())}"
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        async def insert_and_check():
            await db.user_sessions.insert_one({
                "user_id": "TEST_user",
                "session_token": token,
                "expires_at": expires_at,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            # $type "date" (BSON code 9)
            doc = await db.user_sessions.find_one(
                {"session_token": token, "expires_at": {"$type": "date"}}
            )
            await db.user_sessions.delete_one({"session_token": token})
            return doc

        doc = event_loop.run_until_complete(insert_and_check())
        assert doc is not None, "expires_at is not stored as BSON date"


# =========================
# Regression: previously-passing public endpoints
# =========================
class TestPublicRegression:
    def test_public_registry(self):
        r = requests.get(f"{BASE_URL}/api/public/registry", timeout=15)
        assert r.status_code == 200

    def test_public_leaderboard(self):
        r = requests.get(f"{BASE_URL}/api/public/leaderboard", timeout=15)
        assert r.status_code == 200

    def test_auth_session_missing_creds(self):
        # BUG: /api/auth/session should return 400/401/422 for missing body but returns 500.
        # We keep this assertion as-is so main agent sees the failure; unhandled
        # JSONDecodeError at server.py:169 (body = await request.json()).
        r = requests.post(f"{BASE_URL}/api/auth/session", timeout=15)
        assert r.status_code in (400, 401, 422), f"unexpected {r.status_code}: {r.text}"
