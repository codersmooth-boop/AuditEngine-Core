# AuditEngine — Product Requirements Document

## Original Problem Statement
Build a high-precision, enterprise-grade ESG Compliance Intelligence Platform called 'AuditEngine' with clinical, terminal-like precision UI ('The Mirror of Certainty'). CSRD/ESRS/EU Taxonomy audit workflows, LLM-driven analysis, PDF delivery.

## User Choices
- LLM: Claude Sonnet 4.5 (via Emergent LLM key)
- Auth: Emergent Google Auth
- Persistence: MongoDB
- PDF: Real reportlab-generated
- NACE: Full Rev. 2 dataset (996 codes)

## Architecture
- **Backend (FastAPI)**: `/app/backend/server.py` + `llm_service.py`, `pdf_service.py`, `file_extractor.py`, `nace_rev2.json`
- **Frontend (React)**: pages/{Login,Dashboard,AuditView,AuthCallback}, components/{NewAuditDrawer,IntakeZone,ProcessingPanel,ComplianceRing,KPIStrip,FindingsTable,RoadmapPanel,RescoreSimulator,UtcClock}
- **DB Collections**: users, user_sessions, audits

## Core Requirements
- Google OAuth login → workspace dashboard
- Create audit → drawer (Client, NACE searchable, Year)
- Drag-drop intake (PDF/XLSX/TXT/CSV) → 32px status bar
- 5-step processing panel with UTC timer
- LLM analysis → findings + roadmap + score + greenwashing risk
- KPI strip (Score ring, Value @ Stake, Critical count, Greenwashing)
- Findings table (severity outlined tags, expandable, status, reg ref, bucket)
- Roadmap Top 5 (Action → Impact → € Saving, cost, payback)
- Re-score simulator (tick resolves → projected score)
- PDF download

## Implemented (Feb 2026)
- All above modules
- 4 intake buckets shown as sidebar summary
- MISSING/UNVERIFIED visual tags in table + bucket panel

## Backlog (P1/P2)
- P1: LLM streaming to UI during Step 3
- P1: Multi-user org accounts / sharing
- P2: Historical trend charts across audits
- P2: Peer benchmarking by NACE sector
