"""Iteration 8 · Hyper-user sensory audit polish patches
- PATCH A: Dashboard 12-col grid math (source-grep)
- PATCH B: fetchMe silenced 401 (source-grep for validateStatus)
- REGRESSION: Board Brief PDF contains 'VERIFIED EVIDENCE CHAIN:' string in bytes
- REGRESSION: /api/audits/{id}/pdf, /board-brief, /audit-log endpoints reachable
- REGRESSION: /api/payments/tier, /api/public/verify, /api/public/registry, /api/auth/me
"""
import io
import os
import re
import sys
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


def _pdf_contains(pdf_bytes: bytes, needle: str) -> bool:
    """Extract text from PDF bytes and check if needle string is present."""
    import io as _io
    import pypdf
    try:
        reader = pypdf.PdfReader(_io.BytesIO(pdf_bytes))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        return needle in text
    except Exception:
        return needle.encode() in pdf_bytes


# ---------------------- Session seeding helper ----------------------
def _seed_session():
    from pymongo import MongoClient
    from datetime import datetime, timedelta, timezone
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    ts = int(time.time() * 1000)
    user_id = f"test-user-i8-{ts}"
    session_token = f"test_session_i8_{ts}"
    db.users.insert_one({
        "user_id": user_id,
        "email": f"i8-{ts}@auditengine.test",
        "name": "I8 Test",
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
    db.audits.delete_many({"user_id": user_id})
    db.users.delete_many({"user_id": user_id})
    db.user_sessions.delete_many({"user_id": user_id})


# =====================================================================
# PATCH A · Dashboard 12-col grid math
# =====================================================================
class TestPatchADashboardGrid:
    def test_dashboard_uses_grid_cols_12(self):
        with open("/app/frontend/src/pages/Dashboard.jsx") as f:
            src = f.read()
        assert "grid-cols-12" in src, "Dashboard.jsx must declare grid-cols-12"

    def test_dashboard_grid_math_header_and_row_sum_to_12(self):
        """Extract col-span-N counts from the two grid-cols-12 blocks and assert sum == 12 each."""
        with open("/app/frontend/src/pages/Dashboard.jsx") as f:
            src = f.read()

        # Find both grid-cols-12 blocks and their subsequent col-span-N children.
        # Header block: lines ~148-157; row block ~168-191. We split by grid-cols-12 occurrences.
        parts = src.split("grid-cols-12")
        # parts[0] = pre-header; parts[1] = between header start and row start; parts[2] = row + after
        assert len(parts) >= 3, "Expected at least 2 grid-cols-12 blocks (header + row)"

        header_block = parts[1]
        row_block = parts[2]

        # Only consider col-span-N in the *first* consecutive block of the div-children
        # A safe heuristic: capture all col-span-N until the block closes (next '</div>' at outer level).
        # Since Dashboard has no other grid-cols-12 in header_block, sum all col-span-N in header_block up to next `{audits.map` marker.
        header_slice = header_block.split("{loading")[0]
        row_slice = row_block.split("</div>\n      ))}")[0]

        h_spans = [int(x) for x in re.findall(r"col-span-(\d+)", header_slice)]
        r_spans = [int(x) for x in re.findall(r"col-span-(\d+)", row_slice)]

        assert sum(h_spans) == 12, f"Header col-span sum={sum(h_spans)} (spans={h_spans})"
        assert sum(r_spans) == 12, f"Row col-span sum={sum(r_spans)} (spans={r_spans})"
        # Explicit expected pattern per PRD
        assert h_spans == [1, 2, 3, 1, 1, 1, 2, 1], f"Header spans mismatch: {h_spans}"
        assert r_spans == [1, 2, 3, 1, 1, 1, 2, 1], f"Row spans mismatch: {r_spans}"


# =====================================================================
# PATCH B · Silenced auth 401 noise
# =====================================================================
class TestPatchBFetchMeSilence:
    def test_fetchme_uses_validate_status(self):
        with open("/app/frontend/src/lib/api.js") as f:
            src = f.read()
        assert "validateStatus" in src, "api.js must use validateStatus in fetchMe"
        # Ensure /auth/me call has validateStatus attached
        assert re.search(r"/auth/me[^)]*validateStatus", src, re.S), \
            "fetchMe must pass validateStatus for /auth/me"
        # Ensure it accepts 200 OR 401
        assert "s === 200 || s === 401" in src or "s===200||s===401" in src.replace(" ", "")


# =====================================================================
# REGRESSION · Board Brief PDF contains 'VERIFIED EVIDENCE CHAIN:' bytes
# =====================================================================
class TestBoardBriefEvidenceChain:
    def test_board_brief_pdf_contains_verified_evidence_chain_string(self):
        sys.path.insert(0, "/app/backend")
        from pdf_service import build_board_brief_pdf
        sample_audit = {
            "audit_id": "TEST_I8",
            "client_name": "TEST_CLIENT_I8",
            "nace_code": "C.10",
            "reporting_year": 2024,
            "compliance_score": 78,
            "critical_findings_count": 2,
            "value_at_stake_eur": 90000,
            "greenwashing_risk": "LOW",
            "executive_summary": "Test summary.",
            "findings": [
                {"id": "F1", "title": "A", "severity": "HIGH",
                 "description": "d", "value_at_stake_eur": 50000, "impact_score": 5,
                 "regulation_reference": "CSRD Art. 19", "recommended_action": "X"},
            ],
            "roadmap": [{"phase": "P1", "actions": ["A1"], "duration_days": 30}],
            "file_hashes": [{"sha256": "a" * 64, "filename": "f1.pdf"},
                            {"sha256": "b" * 64, "filename": "f2.pdf"}],
            "created_at": "2024-01-01T00:00:00Z",
            "completed_at": "2024-01-02T00:00:00Z",
        }
        pdf_bytes = build_board_brief_pdf(sample_audit)
        assert pdf_bytes[:4] == b"%PDF"
        found = _pdf_contains(pdf_bytes, "VERIFIED EVIDENCE CHAIN:")
        assert found, "Board Brief PDF must contain 'VERIFIED EVIDENCE CHAIN:' footer text"


# =====================================================================
# REGRESSION · Audit lifecycle endpoints reachable
# =====================================================================
class TestAuditArtifactsEndpoints:
    def _make_complete_audit(self, auth):
        """Create an audit and directly mark it COMPLETE with minimal fields for artifact rendering."""
        create_resp = requests.post(
            f"{BASE_URL}/api/audits",
            json={"client_name": "TEST_I8_LIFE", "nace_code": "C.10",
                  "nace_name": "Manufacturing", "reporting_year": 2024},
            headers=auth["headers"], timeout=15,
        )
        assert create_resp.status_code in (200, 201), create_resp.text
        audit_id = create_resp.json()["audit_id"]
        # Force COMPLETE with minimal payload sufficient for PDF/board-brief
        auth["db"].audits.update_one(
            {"audit_id": audit_id},
            {"$set": {
                "status": "COMPLETE",
                "compliance_score": 80,
                "critical_findings_count": 1,
                "value_at_stake_eur": 50000,
                "greenwashing_risk": "LOW",
                "executive_summary": "Test summary.",
                "findings": [{"id": "F1", "title": "T", "severity": "HIGH",
                              "description": "d", "value_at_stake_eur": 50000,
                              "impact_score": 5, "regulation_reference": "CSRD",
                              "recommended_action": "Do"}],
                "roadmap": [{"phase": "P1", "actions": ["A1"], "duration_days": 30}],
                "file_hashes": [{"sha256": "a" * 64, "filename": "f1.pdf"}],
                "completed_at": "2024-06-01T00:00:00Z",
            }},
        )
        return audit_id

    def test_pdf_endpoint(self, auth):
        aid = self._make_complete_audit(auth)
        r = requests.get(f"{BASE_URL}/api/audits/{aid}/pdf",
                         headers=auth["headers"], timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 5000

    def test_board_brief_endpoint_bytes_contain_evidence_chain(self, auth):
        aid = self._make_complete_audit(auth)
        r = requests.get(f"{BASE_URL}/api/audits/{aid}/board-brief",
                         headers=auth["headers"], timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert r.content[:4] == b"%PDF"
        # Verify the footer string is in the extracted PDF text
        assert _pdf_contains(r.content, "VERIFIED EVIDENCE CHAIN:"), \
            "Live board-brief PDF missing VERIFIED EVIDENCE CHAIN footer"

    def test_audit_log_endpoint(self, auth):
        aid = self._make_complete_audit(auth)
        r = requests.get(f"{BASE_URL}/api/audits/{aid}/audit-log",
                         headers=auth["headers"], timeout=30)
        assert r.status_code == 200, r.text[:200]
        assert len(r.content) > 0


# =====================================================================
# REGRESSION · Previously-locked routes
# =====================================================================
class TestPreviouslyLockedRegression:
    def test_payments_tier(self, auth):
        r = requests.get(f"{BASE_URL}/api/payments/tier", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        assert "tier" in r.json()

    def test_payments_portal_requires_body(self, auth):
        # Endpoint should exist (400/422 for missing body or 200 if it accepts default)
        r = requests.post(f"{BASE_URL}/api/payments/portal",
                          json={"return_url": "https://example.com"},
                          headers=auth["headers"], timeout=15)
        # 200 (redirect url returned) or 400/402 if no active subscription — but NOT 404/500
        assert r.status_code in (200, 400, 402, 409), f"Unexpected status: {r.status_code} {r.text[:200]}"

    def test_public_verify(self):
        r = requests.get(f"{BASE_URL}/api/public/verify?root=deadbeef", timeout=10)
        assert r.status_code in (200, 404)

    def test_public_registry(self):
        r = requests.get(f"{BASE_URL}/api/public/registry", timeout=10)
        assert r.status_code == 200

    def test_auth_me_with_valid_session(self, auth):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        assert r.json()["user_id"] == auth["user_id"]

    def test_auth_me_without_session_returns_401_silently(self):
        """PATCH B underlying behaviour: /api/auth/me must still return 401 for anon."""
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code == 401

    def test_stripe_webhook_endpoint_exists(self):
        # Sending a bogus payload should return 400 (bad signature) — NOT 404
        r = requests.post(f"{BASE_URL}/api/webhook/stripe", data=b"{}", timeout=10)
        assert r.status_code in (400, 401, 403), f"webhook endpoint status: {r.status_code}"
