# AuditEngine: Verifiable Compliance Auditing

### Overview
AuditEngine is a compliance audit platform that analyzes corporate ESG disclosures against EU regulatory frameworks (CSRD, ESRS, CSDDD) and produces structured, cryptographically verifiable compliance reports.

**Current status:** production-grade compute core (8/10) with an early-stage operational perimeter — overall 4/10 for paying enterprise clients. Every gap is named, scoped, and scheduled below. The core does not ship to a paying client before blockers M1–M9 are closed.

**Build timeline:** First commit 2026-07-02 → last build 2026-09-09 (69 calendar days). Hands-on development concentrated on 17 unique days (git-verified) — a production-grade, test-covered compute core built solo, part-time, in under ten weeks.

### What It Does
- Ingests PDF reports up to 300 pages: text layer, tables (pdfplumber), and OCR fallback (pypdfium2 + Tesseract)
- Runs LLM-driven analysis (Claude Sonnet 4.5) against regulatory frameworks
- Produces a compliance score, findings, and a prioritized remediation roadmap with deterministic financial-impact estimates
- Generates a signed PDF report with a full cryptographic audit trail

### Core Architecture

**1. Extraction Layer**
- pypdf text extraction: 101 pages / 407,808 chars measured, +12 MB RSS
- pdfplumber tables with per-page isolation: memory optimized via psutil profiling from **698 MB → 72 MB** peak RSS
- In-process OCR (pypdfium2 + Tesseract): 40 pages, peak RSS 95.8 MB, 0 MB /tmp
- End-to-end 101p audit: ~150 MB total RSS, 0 MB disk, ~25 min P99 — measured
- Heartbeat watchdog (40 min silence) + orphan sweep: dead audits self-diagnose with typed failure reasons, never hang silently

**2. Sovereign Gate (LLM Determinism Layer)**
- Strict JSON schema validation on all LLM output with a 3-retry corrective protocol: violation → corrective prompt → violation + prior → corrective prompt → attempt 3 → **SovereignRejection, no silent fallback**
- Enforced rails: compliance score [0,100], impact score [1,20], payback consistency ±50%, Σ savings ≤ 0.5 × turnover, severity distribution minimums
- **Turnover circuit breaker:** the number everything depends on is anchored deterministically — evidence must appear verbatim in extracted text AND match a regex candidate within ±5%
- Every numeric LLM output is either forced into rails or rejected. Variance is made safe, not identical.
- Prompt-injection defenses: untrusted content is delimiter-wrapped

**3. Verification Layer (Provenance)**
- SHA-256 fingerprint per uploaded file
- Deterministic sorted-keys CDO hash
- Composite provenance anchored to a Merkle root — third parties can recompute via the public verification endpoint
- Deterministic pure-Python Value-at-Stake calculation (superlinear regulatory-escalation model, reproducible in Excel), never left to the LLM

**4. Regulator Sandbox**
- Expiring hashed keys, rate limiting (10 req/min per key)
- k-anonymity (minimum 5 companies) and aggregate-only responses

### Test Results
- **34-test shock suite** runs before every release, pinning schema rejection, retry protocol, watchdog behavior, and Value-at-Stake math
- 8/8 adversarial tests passed (root spoofing, duplicate prevention, PII leakage, rate limiting, prompt injection)
- 15-case regression suite for the Value-at-Stake formula
- End-to-end test with real Anthropic API: audit completed, provenance verified

### Known Weaknesses — Pre-Answered
- **No staging/CI/CD:** tests run against live production, exercised only by validated workloads. Staging + CI/CD scoped (M17, 1 week), required before any client.
- **No external monitoring:** system self-diagnoses dead audits; the page-to-me (M8, 3 hr) is scheduled.
- **Backups unverified:** Atlas PITR available but not proven — M7 is a restore *drill*, not a checkbox.
- **LLM narrative text is bounded-stochastic:** numbers are anchored or rejected; evidence-string verification (M10, 2 hr) closes the textual gap.
- **No semantic verification of findings against source text yet.**
- **Encrypted PDFs fail late** with a misleading error (M9: 1 hr fix). Non-Latin OCR unsupported until traineddata pinning (M12).
- **No external security audit or penetration testing yet.**

### Path to Production Readiness (M1–M9 + beyond)
- **M1:** ToS, Privacy Policy, GDPR Art. 28 sub-processor disclosure (Anthropic, Atlas, Stripe), EU AI Act transparency documents
- **M2–M5:** CORS defaults, upload file-type validation, rate limiting on all public endpoints, per-user token quotas
- **M6:** GDPR erasure workflow (cascading across audits, snapshots, ledger)
- **M7–M9:** backup restore drill, monitoring/alerting, encrypted-PDF fail-fast
- **M10–M11:** per-finding evidence verification, pinned ESRS taxonomy lookup
- **M17:** staging environment + CI/CD pipeline
- Idempotent retry mechanism, load testing at 300–500 pages, external security audit

### Stack
Python · FastAPI · MongoDB · React · Claude Sonnet 4.5 · SHA-256 · Merkle Root · K8s · Stripe
