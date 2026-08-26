# AuditEngine: Verifiable Compliance Auditing

### Overview
AuditEngine is a compliance audit platform that analyzes corporate ESG disclosures against EU regulatory frameworks (CSRD, ESRS, CSDDD) and produces structured, verifiable compliance reports.

### What It Does
- Ingests evidence files (PDF, XLSX, TXT, CSV, Markdown) and extracts structured data
- Runs LLM-driven analysis against regulatory frameworks (Claude Sonnet 4.5)
- Produces a compliance score, findings, and a prioritized remediation roadmap with financial-impact estimates
- Generates a signed PDF report with a full audit trail

### Core Architecture

**1. Intelligence Layer**
- Claude Sonnet 4.5 with three routes: direct, fallback, and offline — the system degrades gracefully if the API fails
- Strict JSON schema validation on all LLM output
- Prompt-injection defenses: untrusted content is wrapped in delimiters so uploaded files cannot manipulate analysis

**2. Verification Layer**
- Every evidence file gets a SHA-256 fingerprint
- Snapshots are anchored to a Merkle root — anyone can verify the report hasn't been tampered with via the public verification endpoint
- Deterministic server-side Value-at-Stake calculation (A+B+C+D formula), not left to the LLM

**3. Regulator Sandbox**
- Expiring hashed keys for regulator access
- Rate limiting (10 requests/minute per key)
- k-anonymity (minimum 5 companies before aggregate data is shown)
- Aggregate-only responses — no single company can be identified

### Test Results
- 8/8 adversarial tests passed (root spoofing, duplicate prevention, PII leakage, rate limiting, prompt injection)
- 17/18 regulator sandbox tests passed (1 known edge case, later fixed)
- 15-case regression suite for Value-at-Stake formula
- End-to-end test with real Anthropic API: audit completed, provenance verified in logs

### Current Limitations
- Recovery is reset-based, not idempotent retry-based
- LLM output is validated for structure and integrity, not semantic correctness
- Not yet load-tested at scale
- No external security audit or penetration testing yet

### Path to Production Readiness
- Semantic verification of LLM findings against source evidence
- Idempotent retry mechanism for all pipeline steps
- Load testing and performance benchmarking
- Multi-tenant isolation hardening
- External security audit and penetration testing
- Operational documentation

### Stack
Python · FastAPI · MongoDB · React · Claude Sonnet 4.5 · SHA-256 · Merkle Root
