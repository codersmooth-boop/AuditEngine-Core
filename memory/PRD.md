# AuditEngine — PRD (Product Requirements Document)

## Original Problem Statement
Build a high-precision, enterprise-grade ESG Compliance Intelligence Platform ("AuditEngine") with a clinical, financial-grade design ("The Mirror of Certainty"). Pure #000000 background, 0.5px white borders, Roboto Mono for data, Inter for prose, zero decorations. Core: LLM-powered ESG audit (CSRD/ESRS/CSDDD/EU-Tax/SFDR), deterministic Merkle Root snapshots, public verification/registry/leaderboard/badges, and a Regulator Sandbox with time-boxed API keys.

## Architecture
- **Frontend**: React 18 + TailwindCSS, strict overrides (border-radius=0, box-shadow=none), monochrome + semantic accents (#00FF41, #FFBF00, #FF0000, #FFD700).
- **Backend**: FastAPI + motor (async MongoDB) + slowapi (rate limiting) + emergentintegrations (Claude Sonnet 4.5).
- **Persistence**: MongoDB. Collections: `users`, `user_sessions`, `audits`, `snapshots`, `regulator_keys`.
- **Auth**: Emergent Google OAuth (session cookies, 7-day TTL).
- **LLM**: Claude Sonnet 4.5 via Emergent Universal Key, prompt-injection defended via `<UNTRUSTED_DATA>` sentinels.
- **Streaming**: SSE for live LLM audit terminal ("Glass Box").
- **Verifiability**: SHA-256 composite hashing per audit + Merkle Root per (workspace, year) snapshot. Client-side reproduction via `crypto.subtle`.

## Personas
- **CFO / Sustainability Lead**: uploads evidence, downloads Board Brief + Full Audit + Snapshot PDFs.
- **External Auditor**: reviews audit trail (.log export), verifies Merkle Root via /verify or client-side ReproductionTest.
- **Regulator / Policy Analyst**: uses `/api/regulator/sandbox` for aggregated network statistics with zero PII.
- **Public**: views /registry (transparency log), /leaderboard (opt-in), and SVG attestation badges.

## Core Requirements
- Zero rounded corners, zero shadows, strict monochrome + accents.
- Zero PII on public routes (`/verify`, `/registry`, `/leaderboard`, `/regulator`, `/api/public/badge/*.svg`) — only workspace hashes and Merkle Roots.
- Verifiable audit trail: SHA-256 of every ingested file, composite fingerprint per audit, Merkle Root per snapshot.
- Rate limiting on public endpoints: 60/min/IP; regulator sandbox: 10/min/key.
- Idempotent, index-backed MongoDB.

## Implemented (chronological)
- **2026-07** — MVP: Google OAuth, Dashboard, NACE lookup, 4-bucket intake, 5-step processing, Compliance Ring, Findings Table, Strategic Roadmap, Re-score Simulator.
- **2026-07** — Board Brief + Full Audit + Snapshot PDF pipelines (ReportLab), .log audit trail export.
- **2026-07** — SSE Live LLM Token Streaming ("Glass Box"), Cover Sheet Integration.
- **2026-07** — Merkle Root computation + persistence, /verify Trust Anchor microsite, /registry global transparency log, SVG attestation badges, /leaderboard opt-in mechanic, Trust Streak calc.
- **2026-07** — P0/P1 Hardening: slowapi rate limiting, prompt-injection defense, MongoDB hot-path indexes, client-side hash ReproductionTest.
- **2026-07** — Hostile Audit passed 15/15.
- **2026-07-16 (this fork)** — **Regulator Sandbox** completed & validated:
  - `/api/regulator/sandbox/{whoami, adoption, streaks, scores, volatility}` — all return envelope with `k_anonymity_threshold=5`, `rate_limit_per_min=10`, `cross_verification.registry_master_root` (rolling SHA-256 over every snapshot merkle_root in generated_at order), `generated_at`, `snapshot_count`, `latest_snapshot_at`.
  - Time-boxed API keys via `regulator_keys` collection, 30-day default TTL, minted through `python /app/backend/issue_regulator_key.py` CLI. Header: `X-Regulator-Key`.
  - Per-key in-process token-bucket rate limit (10 req/min).
  - K-anonymity threshold=5 enforced at aggregation layer (not post-filter).
  - Frontend `/regulator` page upgraded from static docs to live terminal: key entry (masked), endpoint selector, EXECUTE button, live status pill (200/401/429), formatted response payload viewer.
  - TTL index on `user_sessions.expires_at` with `expireAfterSeconds=0` + migration coercing legacy ISO-string values to BSON Date.
  - `POST /api/auth/session` hardened: returns 400 on empty/invalid JSON bodies (was 500).
- **Testing (iter 3)**: 17/18 pass. Zero critical, zero sandbox regressions.

- **2026-07-16 (this fork, cont.)** — **Stripe Billing** integrated:
  - Flow A claimable sandbox provisioned (country FI, SMP-eligible). Onboarding URL captured for future account claim.
  - Catalog seeded via `setup_stripe.py` (idempotent): `professional_monthly` €49/mo, `annual_yearly` €490/yr, tax_code `txcd_10103001` (SaaS).
  - `POST /api/payments/checkout` — validates lookup_key against pydantic pattern, creates Stripe Session with `managed_payments={enabled: true}` (falls back to Stripe Tax + billing address if not eligible), persists row in `payment_transactions` before returning.
  - `GET /api/payments/status/{session_id}` — polls Stripe as webhook fallback, updates DB idempotently, returns only `{session_id, status, payment_status}` (no PII).
  - `POST /api/stripe/webhook` — signature-verified; handles `checkout.session.completed`, `async_payment_succeeded/failed`, `expired`, `charge.refunded`.
  - Frontend `/pricing` — three pillars (Professional / Annual / Enterprise), Annual highlighted `#00FF41` "ACTIVE · RECOMMENDED".
  - Enterprise "CONTACT FOR QUOTE" — email `codersmooth@gmail.com` obfuscated as `String.fromCharCode(...)` arrays, assembled only on user click. HTML source contains ZERO email/`gmail`/`codersmooth` literals (verified).
  - `/payment/success` — polls status 8× at 2s, renders receipt card with session ID + status pill; `/payment/cancel` explains no-charge state and returns to /pricing.
  - Mongo `payment_transactions` collection with unique index on `session_id` + descending index on `created_at`.
- **Testing (iter 4)**: 21/21 pass. Zero critical, zero minor. All webhook signature/idempotency/pydantic/DB-row-before-return semantics verified.

## Sandbox key handoff
- Onboarding URL (share with user, one click to convert to real account): captured in fork context.
- Stripe test card: `4242 4242 4242 4242`, any future expiry, any CVC.
- Tax mode selected: **Stripe manages everything including tax and compliance (+3.5% per transaction)** — available in ~80 countries. Alternatives on request: Stripe calculates tax only (+0.5%) or DIY (no tax help).

## Prioritized Backlog
- **P1** — Redis-backed rate limiter for horizontal scale-out (currently in-process memory).
- **P1** — Modularize server.py (876 lines) into routers: auth, ledger, public, regulator, stripe.
- **P1** — TTL / cleanup on `payment_transactions` rows stuck in `initiated`/`pending` state (abandoned carts).
- **P2** — Background task for Snapshot PDF generation (currently synchronous).
- **P2** — TTL index on `regulator_keys.expires_at` (currently expires_at stored as ISO string; migrate to BSON date first).
- **P2** — Periodic sweep of empty `_RATE_BUCKETS` deques (small memory leak on unused keys).
- **P2** — Fail-fast on missing `STRIPE_SECRET_KEY` at import (currently falls back to `sk_test_emergent`).
- **P3** — HMAC/salted KDF for regulator key hashing (currently plain SHA-256 for lookup).

## API Surface (excerpt)
- `POST /api/auth/session`, `GET /api/auth/me`, `POST /api/auth/logout`
- `POST /api/audits`, `GET /api/audits`, `GET /api/audits/{id}`, `POST /api/audits/{id}/upload`, `GET /api/audits/{id}/stream` (SSE), `GET /api/audits/{id}/pdf`, `/board-brief`, `/audit-log`
- `GET /api/ledger/snapshot?year=YYYY`, `GET /api/ledger/snapshot-meta?year=YYYY`
- `GET /api/public/verify/{root}`, `GET /api/public/registry`, `GET /api/public/leaderboard`, `GET /api/public/badge/{root}.svg`
- `GET /api/regulator/sandbox/{whoami|adoption|streaks|scores|volatility}` (header `X-Regulator-Key`)

## Key files
- Backend: `server.py`, `regulator_sandbox.py`, `issue_regulator_key.py`, `llm_service.py`, `pdf_service.py`, `file_extractor.py`.
- Frontend: `src/pages/{Login,Dashboard,AuditView,Ledger,Verify,Registry,Leaderboard,Regulator,AuthCallback}.jsx`, `src/components/{IntakeZone,ProcessingPanel,ComplianceRing,KPIStrip,FindingsTable,RoadmapPanel,RescoreSimulator,BadgeModal,VerifierModal,ReproductionTest}.jsx`.
