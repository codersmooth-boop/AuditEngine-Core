"""Hostile forensic audit backend tests for AuditEngine."""
import os, hashlib, time, io, requests, pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://audit-engine-38.preview.emergentagent.com").rstrip("/")
LOCAL_URL = "http://localhost:8001"

TOKEN_A = os.environ.get("TOKEN_A")
TOKEN_B = os.environ.get("TOKEN_B")

HEADERS_A = {"Authorization": f"Bearer {TOKEN_A}"}
HEADERS_B = {"Authorization": f"Bearer {TOKEN_B}"}

EVIDENCE = b"deterministic evidence for reproduction test"
YEAR = 2025


def _create_and_complete_audit(headers, evidence: bytes, year: int, client="Test Corp"):
    r = requests.post(f"{BASE_URL}/api/audits", headers=headers, json={
        "client_name": client, "nace_code": "23.5", "nace_name": "Cement", "reporting_year": year,
    })
    assert r.status_code == 200, r.text
    audit_id = r.json()["audit_id"]
    files = {"files": ("evidence.txt", evidence, "text/plain")}
    r = requests.post(f"{BASE_URL}/api/audits/{audit_id}/upload", headers=headers, files=files)
    assert r.status_code == 200, r.text
    # Wait for background processing to complete
    for _ in range(30):
        r = requests.get(f"{BASE_URL}/api/audits/{audit_id}", headers=headers)
        if r.json().get("status") == "COMPLETE":
            return audit_id
        time.sleep(1)
    raise AssertionError(f"Audit {audit_id} did not COMPLETE")


def test_00_auth_sanity():
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=HEADERS_A)
    assert r.status_code == 200
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=HEADERS_B)
    assert r.status_code == 200


def test_02_empty_ledger_rejection():
    """HOSTILE #2: year with no audits returns 400."""
    r = requests.get(f"{BASE_URL}/api/ledger/snapshot-meta?year=2099", headers=HEADERS_A)
    assert r.status_code == 400
    assert "empty ledger" in r.json().get("detail", "").lower()


def test_01_root_spoof_defense_and_deterministic_and_uniqueness():
    """HOSTILE #1 + #3 + #7: user A gets root, user B (same bytes) gets 409;
    verify determinism and upsert (no double-insert)."""
    # Create audit for user A
    _create_and_complete_audit(HEADERS_A, EVIDENCE, YEAR, client="ClientA")
    # User A generates snapshot
    rA = requests.get(f"{BASE_URL}/api/ledger/snapshot-meta?year={YEAR}", headers=HEADERS_A)
    assert rA.status_code == 200, rA.text
    root_a = rA.json()["merkle_root"]

    # Registry total before duplicate
    reg1 = requests.get(f"{BASE_URL}/api/public/registry").json()
    total1 = reg1["total"]

    # HOSTILE #3: same user calls again — should upsert, not insert
    rA2 = requests.get(f"{BASE_URL}/api/ledger/snapshot-meta?year={YEAR}", headers=HEADERS_A)
    assert rA2.status_code == 200
    assert rA2.json()["merkle_root"] == root_a
    reg2 = requests.get(f"{BASE_URL}/api/public/registry").json()
    assert reg2["total"] == total1, f"Registry total changed: {total1} -> {reg2['total']} (should upsert)"

    # HOSTILE #7: Deterministic reproduction with Python only
    file_hash = hashlib.sha256(EVIDENCE).hexdigest()
    composite = hashlib.sha256(file_hash.encode()).hexdigest()
    merkle = hashlib.sha256(composite.encode()).hexdigest()
    assert merkle == root_a, f"Determinism FAIL: python={merkle} vs backend={root_a}"

    # HOSTILE #1: User B uploads IDENTICAL bytes, gets a different composite? No — same bytes = same composite.
    _create_and_complete_audit(HEADERS_B, EVIDENCE, YEAR, client="ClientB")
    rB = requests.get(f"{BASE_URL}/api/ledger/snapshot-meta?year={YEAR}", headers=HEADERS_B)
    assert rB.status_code == 409, f"Expected 409 spoof rejection, got {rB.status_code}: {rB.text}"
    detail = rB.json().get("detail", "").lower()
    assert "already registered" in detail or "different workspace" in detail


def test_05_pii_leakage_registry():
    """HOSTILE #5a: /api/public/registry entries expose ONLY allowed keys."""
    r = requests.get(f"{BASE_URL}/api/public/registry")
    assert r.status_code == 200
    allowed = {"merkle_root", "reporting_year", "audit_count", "generated_at"}
    for e in r.json().get("entries", []):
        extra = set(e.keys()) - allowed
        assert not extra, f"Extra keys in registry entry: {extra}"


def test_05_pii_leakage_verify():
    """HOSTILE #5c: /api/public/verify returns only allowed keys."""
    reg = requests.get(f"{BASE_URL}/api/public/registry").json()
    if not reg["entries"]:
        pytest.skip("no snapshots to verify")
    root = reg["entries"][0]["merkle_root"]
    r = requests.get(f"{BASE_URL}/api/public/verify/{root}")
    assert r.status_code == 200, r.text
    allowed = {"status", "workspace_id_hashed", "audit_count", "reporting_year", "timestamp"}
    extra = set(r.json().keys()) - allowed
    assert not extra, f"Extra keys in verify response: {extra}"


def test_05_pii_leakage_leaderboard():
    """HOSTILE #5b: /api/public/leaderboard entries expose only allowed keys."""
    r = requests.get(f"{BASE_URL}/api/public/leaderboard")
    assert r.status_code == 200
    allowed = {"rank", "workspace_id_hashed", "total_audits", "snapshot_count",
               "last_attestation_date", "first_attestation_date",
               "current_streak", "last_streak_year"}
    for e in r.json().get("entries", []):
        extra = set(e.keys()) - allowed
        assert not extra, f"Extra keys in leaderboard entry: {extra}"


def test_04_rate_limiting():
    """HOSTILE #4: 75 rapid hits should trigger 429 after ~60."""
    # Get a real merkle root
    reg = requests.get(f"{LOCAL_URL}/api/public/registry").json()
    root = reg["entries"][0]["merkle_root"] if reg["entries"] else "a" * 64
    headers = {"X-Forwarded-For": "9.9.9.9"}
    codes = []
    for i in range(75):
        r = requests.get(f"{LOCAL_URL}/api/public/verify/{root}", headers=headers)
        codes.append(r.status_code)
    count_429 = sum(1 for c in codes if c == 429)
    count_ok = sum(1 for c in codes if c in (200, 404))
    print(f"200/404 count={count_ok}, 429 count={count_429}")
    assert count_429 > 0, f"No 429s observed in 75 requests. codes={codes}"
    assert count_ok >= 40, f"Expected ~60 OK before rate limit, got {count_ok}"


def test_06_prompt_injection_hardening():
    """HOSTILE #6: SYSTEM_PROMPT + analyze_documents hardening."""
    src = open("/app/backend/llm_service.py").read()
    assert "CRITICAL SECURITY DIRECTIVE" in src
    assert "<UNTRUSTED_DATA>" in src
    assert "</UNTRUSTED_DATA>" in src
    assert "refuse" in src.lower() or "MUST NOT follow" in src
    assert "executive_summary" in src and "Flag" in src
    # Sanitization
    assert '.replace("</UNTRUSTED_DATA>"' in src
