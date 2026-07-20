"""Iteration 10 · Direct Anthropic API integration (BYOK)

Covers:
- /api/system/heartbeat aggregate liveness envelope
- api_connection.route == 'anthropic-direct' with real token counts + 'OK' body
- extraction_logic, legal_mapping, merkle_root, pdf_export sub-envelopes
- End-to-end LLM audit: seed session → create audit → upload → wait COMPLETE
    → assert stream_logs contain 'claude direct' (NOT emergent fallback)
- .env has ANTHROPIC_API_KEY and llm_service.py has load_dotenv(override=True) at module top
- Unit-level fallback logic: heartbeat() with patched env falls back to emergent/offline

NOTE: heartbeat costs ~11in/~4out tokens against the user's Anthropic account per call.
This suite calls it once. The E2E audit will consume ~a few thousand tokens (one call).
"""
import io
import os
import sys
import time
import asyncio
import importlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

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


# ---------------- Session seeding ----------------
@pytest.fixture(scope="module")
def auth():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    ts = int(time.time() * 1000)
    user_id = f"test-user-i10-{ts}"
    token = f"test_session_i10_{ts}"
    db.users.insert_one({
        "user_id": user_id,
        "email": f"i10-{ts}@auditengine.test",
        "name": "I10 Test",
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {
        "user_id": user_id,
        "token": token,
        "db": db,
        "headers": {"Authorization": f"Bearer {token}"},
    }
    db.audits.delete_many({"user_id": user_id})
    db.users.delete_many({"user_id": user_id})
    db.user_sessions.delete_many({"user_id": user_id})


# =====================================================================
# 1. Heartbeat envelope · single real anthropic-direct call
# =====================================================================
class TestSystemHeartbeat:
    @pytest.fixture(scope="class")
    def hb(self):
        r = requests.get(f"{BASE_URL}/api/system/heartbeat", timeout=60)
        assert r.status_code == 200, r.text
        return r.json()

    def test_envelope_shape(self, hb):
        for k in ("api_connection", "extraction_logic", "legal_mapping",
                  "merkle_root", "pdf_export", "registry", "generated_at"):
            assert k in hb, f"missing key {k}"

    def test_api_connection_anthropic_direct(self, hb):
        ac = hb["api_connection"]
        assert ac["status"] == "ACTIVE"
        assert ac["route"] == "anthropic-direct"
        assert ac["ok"] is True
        assert ac["model"] == "claude-sonnet-4-5-20250929"
        assert isinstance(ac["input_tokens"], int) and ac["input_tokens"] > 0
        assert isinstance(ac["output_tokens"], int) and ac["output_tokens"] > 0
        assert "OK" in ac["body"].upper()

    def test_extraction_logic(self, hb):
        el = hb["extraction_logic"]
        assert el["status"] == "SYNCED"
        assert el["model"] == "claude-sonnet-4-5-20250929"
        assert "UNTRUSTED_DATA" in el["system_prompt"]

    def test_legal_mapping(self, hb):
        lm = hb["legal_mapping"]
        assert lm["status"] == "SYNCED"
        for taxo in ("CSRD", "ESRS", "CSDDD", "EU Taxonomy",
                     "GHG Protocol", "GRI", "SFDR"):
            assert taxo in lm["taxonomies"], f"missing taxonomy {taxo}"

    def test_merkle_root(self, hb):
        mr = hb["merkle_root"]
        assert mr["status"] == "OPERATIONAL"
        digest = mr["digest_probe"]
        assert isinstance(digest, str) and len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_pdf_export(self, hb):
        pe = hb["pdf_export"]
        assert pe["status"] == "READY"
        assert "RobotoMono" in pe["detail"]
        assert "Inter" in pe["detail"]


# =====================================================================
# 2. Env + module-load contract
# =====================================================================
class TestEnvAndModuleContract:
    def test_env_has_anthropic_api_key(self):
        with open("/app/backend/.env") as f:
            src = f.read()
        assert "ANTHROPIC_API_KEY=" in src
        # Ensure it is non-empty (do not print value)
        for line in src.splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                assert len(val) > 20, "ANTHROPIC_API_KEY appears empty/short"
                assert val.startswith("sk-ant-"), "Not an anthropic-formatted key"

    def test_llm_service_loads_env_override_true(self):
        with open("/app/backend/llm_service.py") as f:
            src = f.read()
        assert "load_dotenv(" in src
        assert "override=True" in src
        # Verify load_dotenv occurs at module top (before any function def)
        pre_def = src.split("\ndef ", 1)[0].split("\nasync def ", 1)[0]
        assert "load_dotenv(" in pre_def, "load_dotenv must run at module import"


# =====================================================================
# 3. End-to-end LLM audit · claude direct log line proof
# =====================================================================
class TestEndToEndAuditDirectRoute:
    def test_audit_completes_via_claude_direct(self, auth):
        # CREATE
        payload = {
            "client_name": "TEST_I10_DIRECT",
            "nace_code": "C.10",
            "nace_name": "Manufacture of food products",
            "reporting_year": 2024,
        }
        r = requests.post(f"{BASE_URL}/api/audits", json=payload,
                          headers=auth["headers"], timeout=15)
        assert r.status_code in (200, 201), r.text
        audit_id = r.json()["audit_id"]

        # UPLOAD small text file
        sample = (
            "AuditEngine test evidence bundle.\n"
            "Client discloses Scope 1 and Scope 2 emissions for FY2024. "
            "No Scope 3 category-level breakdown is provided. "
            "Board ESG oversight is documented quarterly. "
            "Supplier due diligence covers Tier-1 only. "
            "EU Taxonomy KPI reporting is absent."
        ).encode("utf-8")
        files = {"files": ("evidence.txt", io.BytesIO(sample), "text/plain")}
        up = requests.post(f"{BASE_URL}/api/audits/{audit_id}/upload",
                           files=files, headers=auth["headers"], timeout=30)
        assert up.status_code == 200, up.text

        # POLL for COMPLETE (timeout 180s)
        deadline = time.time() + 180
        final = None
        while time.time() < deadline:
            g = requests.get(f"{BASE_URL}/api/audits/{audit_id}",
                             headers=auth["headers"], timeout=15)
            assert g.status_code == 200, g.text
            doc = g.json()
            if doc.get("status") in ("COMPLETE", "FAILED"):
                final = doc
                break
            time.sleep(3)
        assert final is not None, "audit did not terminate within 180s"
        assert final["status"] == "COMPLETE", f"status={final['status']} logs={final.get('stream_logs')}"

        # PROOF · stream_logs must include `claude direct` line
        logs = final.get("stream_logs", []) or []
        combined = " || ".join((l.get("text") or "") for l in logs).lower()
        assert "claude direct" in combined, \
            f"expected 'claude direct · in=… out=…' log line proving anthropic-direct path was used. Got: {combined[:800]}"
        # And must NOT indicate the emergent fallback was used silently
        # (production log line is only emitted on the direct path)
        assert "emergent fallback" not in combined


# =====================================================================
# 4. Fallback logic unit test · patched env → emergent/offline route
# =====================================================================
class TestHeartbeatFallbackLogic:
    """We cannot mutate the running server's module-level env at request time.
    Instead re-import llm_service in isolation with a patched os.environ so
    the module-level `ANTHROPIC_API_KEY` binds to the fallback value.
    """
    def _reimport_with_env(self, env_overrides):
        sys.path.insert(0, "/app/backend")
        # Remove any cached module
        for k in ("llm_service",):
            if k in sys.modules:
                del sys.modules[k]
        with patch.dict(os.environ, env_overrides, clear=False):
            import llm_service  # noqa
            return llm_service

    def test_no_anthropic_key_falls_back_to_emergent(self):
        # Unset ANTHROPIC_API_KEY, keep EMERGENT_LLM_KEY (real value from .env if any)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            # Also need to prevent load_dotenv from re-reading the file value.
            # llm_service does load_dotenv(override=True) at import — but env we
            # set here is overridden by the file. So we monkey-patch load_dotenv.
            import dotenv as _dotenv
            orig = _dotenv.load_dotenv
            _dotenv.load_dotenv = lambda *a, **kw: True
            try:
                for k in ("llm_service",):
                    if k in sys.modules:
                        del sys.modules[k]
                import llm_service  # noqa
                assert llm_service.ANTHROPIC_API_KEY in (None, "")
                hb = asyncio.get_event_loop().run_until_complete(llm_service.heartbeat()) \
                    if not asyncio.get_event_loop().is_running() \
                    else asyncio.run(llm_service.heartbeat())
                assert hb["route"] in ("emergent-universal", "offline")
            finally:
                _dotenv.load_dotenv = orig
                # Restore real module state for other tests
                for k in ("llm_service",):
                    if k in sys.modules:
                        del sys.modules[k]

    def test_no_keys_at_all_returns_offline(self):
        import dotenv as _dotenv
        orig = _dotenv.load_dotenv
        _dotenv.load_dotenv = lambda *a, **kw: True
        try:
            with patch.dict(os.environ,
                            {"ANTHROPIC_API_KEY": "", "EMERGENT_LLM_KEY": ""},
                            clear=False):
                for k in ("llm_service",):
                    if k in sys.modules:
                        del sys.modules[k]
                import llm_service  # noqa
                hb = asyncio.run(llm_service.heartbeat())
                assert hb["route"] == "offline"
                assert hb["ok"] is False
        finally:
            _dotenv.load_dotenv = orig
            for k in ("llm_service",):
                if k in sys.modules:
                    del sys.modules[k]


# =====================================================================
# 5. Regression · unchanged public/auth surface
# =====================================================================
class TestPublicSurfaceRegression:
    def test_auth_me_anon_envelope(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json() == {"authenticated": False}

    def test_public_verify_short_root_404(self):
        r = requests.get(f"{BASE_URL}/api/public/verify/deadbeef", timeout=10)
        # Endpoint validates 64-hex; short input yields 4xx (not 500)
        assert r.status_code in (400, 404, 422)

    def test_public_registry(self):
        r = requests.get(f"{BASE_URL}/api/public/registry", timeout=10)
        assert r.status_code == 200

    def test_stripe_webhook_present(self):
        r = requests.post(f"{BASE_URL}/api/webhook/stripe", data=b"{}", timeout=10)
        assert r.status_code in (400, 401, 403)

    def test_payments_tier_authed(self, auth):
        r = requests.get(f"{BASE_URL}/api/payments/tier",
                         headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        assert "tier" in r.json()
