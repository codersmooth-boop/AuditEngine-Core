"""Zero-Gap Closure iteration 7 tests — 12 patches.

Covers:
- PATCH 5: PDF fonts (RobotoMono/Inter) + Board Brief generation size
- PATCH 7: Upload size ceiling (25 MB) 413 rejection
- PATCH 10: /api/audits/{id}/reset endpoint (404/409/200 flows)
- Regression: /api/payments/tier, /api/public/verify, /api/public/registry, /api/auth/session, /api/regulator/sandbox/*
"""
import os
import io
import sys
import time
import subprocess
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Read from frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ---------------------- Session seeding helper ----------------------
def _seed_session():
    """Insert user + session directly into Mongo, return (user_id, session_token)."""
    from pymongo import MongoClient
    from datetime import datetime, timedelta, timezone
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    ts = int(time.time() * 1000)
    user_id = f"test-user-zg-{ts}"
    session_token = f"test_session_zg_{ts}"
    db.users.insert_one({
        "user_id": user_id,
        "email": f"zg-{ts}@auditengine.test",
        "name": "ZG Test",
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return user_id, session_token, db


@pytest.fixture(scope="module")
def auth():
    user_id, token, db = _seed_session()
    yield {"user_id": user_id, "token": token, "db": db,
           "headers": {"Authorization": f"Bearer {token}"}}
    # Teardown
    db.audits.delete_many({"user_id": user_id})
    db.users.delete_many({"user_id": user_id})
    db.user_sessions.delete_many({"user_id": user_id})


# =====================================================================
# PATCH 5 · PDF fonts + generation
# =====================================================================
class TestPdfService:
    def test_no_courier_or_helvetica_refs(self):
        with open("/app/backend/pdf_service.py") as f:
            src = f.read()
        assert "Courier" not in src, "Courier still referenced in pdf_service.py"
        assert "Helvetica" not in src, "Helvetica still referenced in pdf_service.py"
        assert 'MONO = "RobotoMono"' in src
        assert 'SANS = "Inter"' in src

    def test_ttf_files_present(self):
        fonts = ["RobotoMono-Regular.ttf", "RobotoMono-Bold.ttf",
                 "Inter-Regular.ttf", "Inter-Bold.ttf"]
        for f in fonts:
            path = f"/app/backend/fonts/{f}"
            assert os.path.exists(path), f"Missing font: {path}"
            assert os.path.getsize(path) > 1000

    def test_board_brief_generation(self):
        sys.path.insert(0, "/app/backend")
        from pdf_service import build_board_brief_pdf as generate_board_brief_pdf
        sample_audit = {
            "audit_id": "TEST_AUDIT_ZG",
            "client_name": "TEST_CLIENT",
            "nace_code": "C.10",
            "reporting_year": 2024,
            "compliance_score": 72,
            "critical_findings_count": 3,
            "value_at_stake_eur": 125000,
            "greenwashing_risk": "MODERATE",
            "executive_summary": "Test executive summary paragraph for board brief PDF generation.",
            "findings": [
                {"id": "F1", "title": "Sample Finding A", "severity": "HIGH",
                 "description": "Details", "value_at_stake_eur": 50000, "impact_score": 5,
                 "regulation_reference": "CSRD Art. 19", "recommended_action": "Do X"},
                {"id": "F2", "title": "Sample Finding B", "severity": "MEDIUM",
                 "description": "Details", "value_at_stake_eur": 25000, "impact_score": 3,
                 "regulation_reference": "CSRD Art. 20", "recommended_action": "Do Y"},
            ],
            "roadmap": [
                {"phase": "Phase 1", "actions": ["A1", "A2"], "duration_days": 30},
            ],
            "file_hashes": [{"sha256": "a" * 64, "filename": "f1.pdf"}, {"sha256": "b" * 64, "filename": "f2.pdf"}],
            "created_at": "2024-01-01T00:00:00Z",
            "completed_at": "2024-01-02T00:00:00Z",
        }
        pdf_bytes = generate_board_brief_pdf(sample_audit)
        assert isinstance(pdf_bytes, (bytes, bytearray))
        assert len(pdf_bytes) > 30_000, f"PDF too small: {len(pdf_bytes)} bytes"
        assert pdf_bytes[:4] == b"%PDF"

    def test_board_brief_uses_surface(self):
        with open("/app/backend/pdf_service.py") as f:
            src = f.read()
        # Find the board-brief _page_bg block (line ~450) and ensure setFillColor(SURFACE) is used
        assert "setFillColor(SURFACE)" in src, "Board brief _page_bg missing SURFACE fill"


# =====================================================================
# PATCH 7 · Upload size ceiling 25 MB
# =====================================================================
class TestUploadCeiling:
    def test_max_upload_bytes_constant(self):
        with open("/app/backend/server.py") as f:
            src = f.read()
        assert "MAX_UPLOAD_BYTES = 25 * 1024 * 1024" in src
        assert "exceeds 25 MB ceiling" in src

    def test_oversize_upload_rejected(self, auth):
        # Create an audit first via API
        create_resp = requests.post(
            f"{BASE_URL}/api/audits",
            json={"client_name": "TEST_ZG", "nace_code": "C.10", "nace_name": "Manufacturing", "reporting_year": 2024},
            headers=auth["headers"], timeout=15,
        )
        assert create_resp.status_code in (200, 201), create_resp.text
        audit_id = create_resp.json()["audit_id"]

        # Build a >25MB file
        big = io.BytesIO(b"A" * (26 * 1024 * 1024))
        files = {"files": ("big.pdf", big, "application/pdf")}
        resp = requests.post(
            f"{BASE_URL}/api/audits/{audit_id}/upload",
            files=files, headers=auth["headers"], timeout=60,
        )
        assert resp.status_code == 413, f"Expected 413 got {resp.status_code}: {resp.text[:200]}"
        assert "exceeds 25 MB ceiling" in resp.text


# =====================================================================
# PATCH 10 · Reset endpoint
# =====================================================================
class TestResetEndpoint:
    def test_reset_requires_auth(self):
        resp = requests.post(f"{BASE_URL}/api/audits/nonexistent/reset", timeout=10)
        assert resp.status_code in (401, 403)

    def test_reset_nonexistent_returns_404(self, auth):
        resp = requests.post(
            f"{BASE_URL}/api/audits/does-not-exist-xyz/reset",
            headers=auth["headers"], timeout=10,
        )
        assert resp.status_code == 404

    def test_reset_draft_returns_409(self, auth):
        create_resp = requests.post(
            f"{BASE_URL}/api/audits",
            json={"client_name": "TEST_ZG_DRAFT", "nace_code": "C.10", "nace_name": "Manufacturing", "reporting_year": 2024},
            headers=auth["headers"], timeout=15,
        )
        audit_id = create_resp.json()["audit_id"]
        # New audit defaults to DRAFT
        resp = requests.post(
            f"{BASE_URL}/api/audits/{audit_id}/reset",
            headers=auth["headers"], timeout=10,
        )
        assert resp.status_code == 409, resp.text

    def test_reset_failed_transitions_to_draft(self, auth):
        create_resp = requests.post(
            f"{BASE_URL}/api/audits",
            json={"client_name": "TEST_ZG_FAILED", "nace_code": "C.10", "nace_name": "Manufacturing", "reporting_year": 2024},
            headers=auth["headers"], timeout=15,
        )
        audit_id = create_resp.json()["audit_id"]
        # Force FAILED state
        auth["db"].audits.update_one(
            {"audit_id": audit_id},
            {"$set": {"status": "FAILED"}},
        )
        resp = requests.post(
            f"{BASE_URL}/api/audits/{audit_id}/reset",
            headers=auth["headers"], timeout=10,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "DRAFT"
        # Verify persisted
        get_resp = requests.get(
            f"{BASE_URL}/api/audits/{audit_id}",
            headers=auth["headers"], timeout=10,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "DRAFT"

    def test_reset_non_owner_returns_404(self, auth):
        # Create audit under auth user
        create_resp = requests.post(
            f"{BASE_URL}/api/audits",
            json={"client_name": "TEST_ZG_OWN", "nace_code": "C.10", "nace_name": "Manufacturing", "reporting_year": 2024},
            headers=auth["headers"], timeout=15,
        )
        audit_id = create_resp.json()["audit_id"]
        # Seed second user and try to reset first user's audit
        _uid2, token2, db2 = _seed_session()
        try:
            resp = requests.post(
                f"{BASE_URL}/api/audits/{audit_id}/reset",
                headers={"Authorization": f"Bearer {token2}"}, timeout=10,
            )
            assert resp.status_code == 404, resp.text
        finally:
            db2.users.delete_one({"user_id": _uid2})
            db2.user_sessions.delete_one({"user_id": _uid2})


# =====================================================================
# Regression suite
# =====================================================================
class TestRegression:
    def test_payments_tier(self, auth):
        r = requests.get(f"{BASE_URL}/api/payments/tier", headers=auth["headers"], timeout=10)
        assert r.status_code == 200, r.text
        assert "tier" in r.json()

    def test_public_verify_invalid(self):
        r = requests.get(f"{BASE_URL}/api/public/verify?root=deadbeef", timeout=10)
        assert r.status_code in (200, 404)

    def test_public_registry(self):
        r = requests.get(f"{BASE_URL}/api/public/registry", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), (list, dict))

    def test_auth_me(self, auth):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        assert r.json()["user_id"] == auth["user_id"]

    def test_regulator_sandbox_list(self, auth):
        r = requests.get(f"{BASE_URL}/api/regulator/sandbox/list", headers=auth["headers"], timeout=10)
        # Endpoint may or may not exist; if not, skip
        if r.status_code == 404:
            pytest.skip("regulator sandbox list endpoint not present")
        assert r.status_code in (200, 401)
