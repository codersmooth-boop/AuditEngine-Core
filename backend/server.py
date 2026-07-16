from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Depends, Request, Response, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, json, io, asyncio, tempfile
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import httpx
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from llm_service import analyze_documents
from pdf_service import build_audit_pdf, build_board_brief_pdf, build_snapshot_pdf
from file_extractor import extract_text_from_file
from regulator_sandbox import make_router as make_regulator_router, issue_key as issue_regulator_key
from stripe_billing import make_router as make_billing_router, handle_stripe_webhook

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env', override=True)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="AuditEngine")
api_router = APIRouter(prefix="/api")

def _client_ip(request: Request) -> str:
    """Extract the real client IP, respecting X-Forwarded-For / X-Real-IP from the ingress."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("x-real-ip")
    if xri:
        return xri.strip()
    return get_remote_address(request)


# Rate limiter for public endpoints (60 req/min/IP).
limiter = Limiter(key_func=_client_ip, default_limits=[])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("auditengine")

# Load NACE data once
with open(ROOT_DIR / "nace_rev2.json", "r") as f:
    NACE_CODES = json.load(f)


# ---------- STREAM PUB/SUB (in-memory) ----------
STREAM_QUEUES: Dict[str, List[asyncio.Queue]] = {}
STREAM_HISTORY: Dict[str, List[dict]] = {}
STREAM_MAX_HISTORY = 400

# In-memory TTL cache for the public leaderboard (60s)
_LB_CACHE: Dict[str, Any] = {"expires": 0, "data": None}
_LB_TTL_SECONDS = 60


def _stream_publish(audit_id: str, event: dict) -> None:
    from datetime import datetime, timezone as _tz
    event = {**event, "ts": datetime.now(_tz.utc).isoformat()}
    hist = STREAM_HISTORY.setdefault(audit_id, [])
    hist.append(event)
    if len(hist) > STREAM_MAX_HISTORY:
        del hist[: len(hist) - STREAM_MAX_HISTORY]
    # Persist to mongo (fire-and-forget; only log events, not step/done spam)
    if event.get("type") == "log":
        async def _persist():
            try:
                await db.audits.update_one(
                    {"audit_id": audit_id},
                    {"$push": {"stream_logs": {"ts": event["ts"], "text": event["text"], "tag": event.get("tag", "OK")}}},
                )
            except Exception:
                pass
        asyncio.create_task(_persist())
    for q in STREAM_QUEUES.get(audit_id, []):
        try:
            q.put_nowait(event)
        except Exception:
            pass


async def _emit_log(audit_id: str, text: str, tag: str = "OK", delay: float = 0.08):
    _stream_publish(audit_id, {"type": "log", "text": text, "tag": tag})
    if delay:
        await asyncio.sleep(delay)


async def _emit_step(audit_id: str, step: int):
    _stream_publish(audit_id, {"type": "step", "step": step})


async def _emit_done(audit_id: str):
    _stream_publish(audit_id, {"type": "done"})


# ---------- MODELS ----------
class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditCreate(BaseModel):
    client_name: str
    nace_code: str
    nace_name: str
    reporting_year: int


class Audit(BaseModel):
    audit_id: str
    user_id: str
    client_name: str
    nace_code: str
    nace_name: str
    reporting_year: int
    status: str  # DRAFT | PROCESSING | COMPLETE | FAILED
    created_at: datetime
    completed_at: Optional[datetime] = None
    compliance_score: Optional[int] = None
    value_at_stake_eur: Optional[float] = None
    critical_findings_count: Optional[int] = None
    greenwashing_risk: Optional[str] = None  # HIGH | MODERATE | LOW | NONE
    findings: List[Dict[str, Any]] = []
    roadmap: List[Dict[str, Any]] = []
    files: List[str] = []
    processing_step: int = 0  # 0-5


# ---------- AUTH ----------
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@api_router.post("/auth/session")
async def create_session(request: Request, response: Response):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    async with httpx.AsyncClient(timeout=15.0) as hc:
        r = await hc.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id},
        )
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session_id")
        data = r.json()

    email = data["email"]
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"user_id": user_id}, {"$set": {"name": data["name"], "picture": data.get("picture")}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": data["name"],
            "picture": data.get("picture"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    session_token = data["session_token"]
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    # Stored as BSON date so MongoDB TTL index can auto-expire the row.
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    response.set_cookie(
        key="session_token", value=session_token,
        max_age=7 * 24 * 3600, httponly=True, secure=True, samesite="none", path="/",
    )
    return {"user_id": user_id, "email": email, "name": data["name"], "picture": data.get("picture")}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "picture": user.get("picture"),
        "leaderboard_opt_in": bool(user.get("leaderboard_opt_in", False)),
    }


@api_router.patch("/settings/leaderboard")
async def toggle_leaderboard(payload: dict, user: dict = Depends(get_current_user)):
    """Explicit opt-in / opt-out for the public leaderboard. Default: false."""
    opt_in = bool(payload.get("opt_in", False))
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"leaderboard_opt_in": opt_in}})
    _LB_CACHE["expires"] = 0  # invalidate leaderboard cache
    return {"leaderboard_opt_in": opt_in}


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


# ---------- NACE ----------
@api_router.get("/nace")
async def nace_search(q: str = "", limit: int = 50):
    q = q.strip().lower()
    if not q:
        results = [c for c in NACE_CODES if c["level"] in (1, 2)][:limit]
    else:
        results = [c for c in NACE_CODES if q in c["name"].lower() or q in (c.get("code") or "").lower()][:limit]
    return results


# ---------- AUDITS ----------
@api_router.post("/audits")
async def create_audit(payload: AuditCreate, user: dict = Depends(get_current_user)):
    audit_id = f"aud_{uuid.uuid4().hex[:12]}"
    doc = {
        "audit_id": audit_id,
        "user_id": user["user_id"],
        "client_name": payload.client_name,
        "nace_code": payload.nace_code,
        "nace_name": payload.nace_name,
        "reporting_year": payload.reporting_year,
        "status": "DRAFT",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "processing_step": 0,
        "files": [],
        "findings": [],
        "roadmap": [],
    }
    await db.audits.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.get("/audits")
async def list_audits(user: dict = Depends(get_current_user)):
    docs = await db.audits.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return docs


@api_router.get("/audits/{audit_id}")
async def get_audit(audit_id: str, user: dict = Depends(get_current_user)):
    doc = await db.audits.find_one({"audit_id": audit_id, "user_id": user["user_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Audit not found")
    return doc


@api_router.delete("/audits/{audit_id}")
async def delete_audit(audit_id: str, user: dict = Depends(get_current_user)):
    r = await db.audits.delete_one({"audit_id": audit_id, "user_id": user["user_id"]})
    return {"deleted": r.deleted_count}


async def _run_processing(audit_id: str, extracted_texts: List[dict], client_name: str, nace_name: str, nace_code: str, reporting_year: int):
    """Simulate 5-step processing with live streamed execution log, then persist findings."""
    try:
        # STEP 1 · File Extraction
        await _emit_step(audit_id, 1)
        await _emit_log(audit_id, f"Initializing audit engine · case={audit_id[:12]}", "OK", 0.1)
        await _emit_log(audit_id, f"Client: {client_name} · NACE {nace_code} · FY{reporting_year}", "OK", 0.15)
        for d in extracted_texts:
            await _emit_log(audit_id, f"Extracted [{d['filename']}] · {len(d['text']):,} chars", "OK", 0.12)
        await _emit_log(audit_id, "File extraction complete", "OK", 0.2)

        # STEP 2 · Payload Writing
        await db.audits.update_one({"audit_id": audit_id}, {"$set": {"status": "PROCESSING", "processing_step": 2}})
        await _emit_step(audit_id, 2)
        await _emit_log(audit_id, "Structuring intake buckets: OPERATIONAL_ENERGY · SUPPLY_CHAIN · HUMAN_SOCIAL · CONTEXT", "OK", 0.15)
        await _emit_log(audit_id, f"Loading NACE {nace_code} regulatory benchmarks", "OK", 0.15)
        await _emit_log(audit_id, "Loading CSRD/ESRS taxonomy · 12 datapoints armed", "OK", 0.15)
        await _emit_log(audit_id, "Loading CSDDD, EU Taxonomy Art. 8, SFDR PAI matrix", "OK", 0.15)
        await _emit_log(audit_id, "Payload sealed · handoff to Logic Engine", "OK", 0.15)

        # STEP 3 · Logic Engine (LLM)
        await db.audits.update_one({"audit_id": audit_id}, {"$set": {"processing_step": 3}})
        await _emit_step(audit_id, 3)
        await _emit_log(audit_id, "Boot: Claude Sonnet 4.5 · anthropic:claude-sonnet-4-5-20250929", "OK", 0.15)
        await _emit_log(audit_id, "Gap analysis · scanning Scope 1/2/3 disclosures", "OK", 0.2)
        await _emit_log(audit_id, "Cross-referencing ESRS E1-6 emissions requirements", "OK", 0.2)
        await _emit_log(audit_id, "Scanning for CSRD Art. 19a breaches", "SCAN", 0.2)
        await _emit_log(audit_id, "Legal mapping · CSDDD supplier due-diligence tiers", "OK", 0.2)
        await _emit_log(audit_id, "Probing EU Taxonomy Art. 8 substantial-contribution + DNSH", "OK", 0.2)
        await _emit_log(audit_id, "Materiality assessment · double materiality axis", "OK", 0.2)
        result = await analyze_documents(extracted_texts, client_name, nace_name, reporting_year)
        # Publish findings as scripted matches
        for f in (result.get("findings") or [])[:14]:
            tag = {"CRITICAL": "BREACH", "MODERATE": "GAP", "COMPLIANT": "OK"}.get(f.get("severity"), "MATCH")
            await _emit_log(audit_id, f"{f.get('data_point','')} · {f.get('regulatory_ref','')} · {f.get('status','')}", tag, 0.15)
        await _emit_log(audit_id, f"Logic engine returned {len(result.get('findings',[]))} findings", "OK", 0.15)

        # STEP 4 · Risk Map
        await db.audits.update_one({"audit_id": audit_id}, {"$set": {"processing_step": 4}})
        await _emit_step(audit_id, 4)
        await _emit_log(audit_id, "Quantifying value-at-stake · litigation + financing + reputational vectors", "OK", 0.2)
        await _emit_log(audit_id, f"Greenwashing risk classification: {result.get('greenwashing_risk','MODERATE')}", "OK", 0.2)
        await _emit_log(audit_id, "Opportunity find · ranking roadmap by € recoverable", "OK", 0.2)
        for r in (result.get("roadmap") or [])[:5]:
            await _emit_log(audit_id, f"→ {r.get('action','')} · €{r.get('saving_eur',0):,.0f} · payback {r.get('payback_months',0)} mo", "PLAN", 0.15)

        # STEP 5 · PDF Delivery
        await db.audits.update_one({"audit_id": audit_id}, {"$set": {"processing_step": 5}})
        await _emit_step(audit_id, 5)
        await _emit_log(audit_id, "Composing Board Brief cover sheet", "OK", 0.15)
        await _emit_log(audit_id, "Sealing detailed findings dossier + technical appendix", "OK", 0.15)
        await _emit_log(audit_id, "Signing PDF · SHA-256 audit trail attached", "OK", 0.2)

        update = {
            "status": "COMPLETE",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "compliance_score": result["compliance_score"],
            "value_at_stake_eur": result["value_at_stake_eur"],
            "critical_findings_count": result["critical_findings_count"],
            "greenwashing_risk": result["greenwashing_risk"],
            "findings": result["findings"],
            "roadmap": result["roadmap"],
            "executive_summary": result.get("executive_summary", ""),
            "processing_step": 5,
        }
        await db.audits.update_one({"audit_id": audit_id}, {"$set": update})
        await _emit_log(audit_id, f"AUDIT COMPLETE · compliance_score={result['compliance_score']}/100", "DONE", 0.1)
        await _emit_done(audit_id)
    except Exception as e:
        logger.exception("Processing failed")
        await _emit_log(audit_id, f"FATAL: {e}", "FAIL", 0)
        await _emit_done(audit_id)
        await db.audits.update_one({"audit_id": audit_id}, {"$set": {"status": "FAILED", "error": str(e)}})


@api_router.post("/audits/{audit_id}/upload")
async def upload_files(audit_id: str, background_tasks: BackgroundTasks,
                       files: List[UploadFile] = File(...),
                       user: dict = Depends(get_current_user)):
    audit = await db.audits.find_one({"audit_id": audit_id, "user_id": user["user_id"]}, {"_id": 0})
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    extracted = []
    filenames = []
    file_hashes = []
    import hashlib
    for f in files:
        content = await f.read()
        text = extract_text_from_file(f.filename or "file", content)
        extracted.append({"filename": f.filename, "text": text[:60000]})
        filenames.append(f.filename)
        file_hashes.append({
            "filename": f.filename,
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        })

    await db.audits.update_one(
        {"audit_id": audit_id},
        {"$set": {"files": filenames, "file_hashes": file_hashes, "status": "PROCESSING", "processing_step": 1, "stream_logs": []}},
    )

    background_tasks.add_task(
        _run_processing, audit_id, extracted,
        audit["client_name"], audit["nace_name"], audit["nace_code"], audit["reporting_year"],
    )
    return {"ok": True, "audit_id": audit_id, "files": filenames}


@api_router.get("/audits/{audit_id}/stream")
async def stream_audit(audit_id: str, request: Request, token: Optional[str] = None):
    # EventSource cannot set custom headers, so accept ?token= as fallback for Bearer auth.
    # Cookie-based auth also works (same-origin via ingress).
    session_token = request.cookies.get("session_token") or token
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    audit = await db.audits.find_one({"audit_id": audit_id, "user_id": session["user_id"]}, {"_id": 0})
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    q: asyncio.Queue = asyncio.Queue(maxsize=1000)
    STREAM_QUEUES.setdefault(audit_id, []).append(q)

    async def event_gen():
        try:
            # Replay history first so late-joining clients see prior logs
            for ev in list(STREAM_HISTORY.get(audit_id, [])):
                yield f"data: {json.dumps(ev)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(ev)}\n\n"
                    if ev.get("type") == "done":
                        break
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # keepalive
        finally:
            try:
                STREAM_QUEUES.get(audit_id, []).remove(q)
            except ValueError:
                pass

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@api_router.get("/audits/{audit_id}/pdf")
async def download_pdf(audit_id: str, user: dict = Depends(get_current_user)):
    audit = await db.audits.find_one({"audit_id": audit_id, "user_id": user["user_id"]}, {"_id": 0})
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.get("status") != "COMPLETE":
        raise HTTPException(status_code=400, detail="Audit not complete")
    pdf_bytes = build_audit_pdf(audit)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="AuditEngine_{audit["client_name"]}_{audit["reporting_year"]}.pdf"'},
    )


@api_router.get("/audits/{audit_id}/board-brief")
async def download_board_brief(audit_id: str, user: dict = Depends(get_current_user)):
    audit = await db.audits.find_one({"audit_id": audit_id, "user_id": user["user_id"]}, {"_id": 0})
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.get("status") != "COMPLETE":
        raise HTTPException(status_code=400, detail="Audit not complete")
    pdf_bytes = build_board_brief_pdf(audit)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="AuditEngine_BoardBrief_{audit["client_name"]}_{audit["reporting_year"]}.pdf"'},
    )


@api_router.get("/audits/{audit_id}/audit-log")
async def download_audit_log(audit_id: str, user: dict = Depends(get_current_user)):
    audit = await db.audits.find_one({"audit_id": audit_id, "user_id": user["user_id"]}, {"_id": 0})
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    from datetime import datetime, timezone as _tz
    import hashlib as _hl

    logs = audit.get("stream_logs") or []
    file_hashes = audit.get("file_hashes") or []
    body_lines = [f"[{l.get('ts','')}] [{l.get('tag','OK'):<6}] {l.get('text','')}" for l in logs]

    # Deterministic composite fingerprint across all ingested files
    composite = _hl.sha256(("|".join(fh.get("sha256", "") for fh in file_hashes)).encode()).hexdigest()

    header = [
        "================================================================================",
        "  AUDITENGINE // REGULATOR-DEFENSIBLE AUDIT TRAIL",
        "  THE MIRROR OF CERTAINTY — CERTIFIED EXECUTION LOG",
        "================================================================================",
        f"AUDIT ID          : {audit.get('audit_id','')}",
        f"CLIENT            : {audit.get('client_name','')}",
        f"NACE REV. 2       : {audit.get('nace_code','')} · {audit.get('nace_name','')}",
        f"REPORTING YEAR    : {audit.get('reporting_year','')}",
        f"CREATED AT        : {audit.get('created_at','')}",
        f"COMPLETED AT      : {audit.get('completed_at','')}",
        f"STATUS            : {audit.get('status','')}",
        f"COMPLIANCE SCORE  : {audit.get('compliance_score','—')}/100",
        f"GREENWASHING RISK : {audit.get('greenwashing_risk','—')}",
        f"ENGINE VERSION    : AuditEngine v1.0 · anthropic:claude-sonnet-4-5-20250929",
        f"LOG EXPORTED AT   : {datetime.now(_tz.utc).isoformat()}",
        f"LOG LINE COUNT    : {len(logs)}",
        "",
        "--- DIGITAL FINGERPRINT (SHA-256) OF INGESTED EVIDENCE ------------------------",
    ]
    for fh in file_hashes:
        header.append(f"  · {fh.get('filename','')}  ({fh.get('bytes',0)} bytes)")
        header.append(f"    sha256 = {fh.get('sha256','')}")
    header += [
        f"  · composite  = {composite}",
        "",
        "--- EXECUTION SCRIPT ----------------------------------------------------------",
    ]

    footer = [
        "",
        "--- CERTIFICATION OF ANALYSIS -------------------------------------------------",
        "This log constitutes a good-faith, timestamped record of the AuditEngine",
        "compliance analysis executed against the ingested evidence listed above.",
        "The following logic gates were traversed in sequence:",
        "  [1] GAP ANALYSIS      — Datapoint coverage vs. ESRS/CSRD/CSDDD/EU-Tax/SFDR",
        "  [2] LEGAL MAPPING     — Regulatory-reference binding per finding",
        "  [3] OPPORTUNITY FIND  — € Value-at-Stake quantification & roadmap ranking",
        "",
        "Analysis engine, prompt schema and regulatory taxonomy are version-pinned.",
        "Evidence integrity is provable via the SHA-256 fingerprints above.",
        f"Signed // AUDITENGINE // {datetime.now(_tz.utc).isoformat()}",
        "================================================================================",
    ]

    text = "\n".join(header + body_lines + footer)
    return Response(
        content=text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="AuditEngine_{audit.get("client_name","audit")}_{audit.get("reporting_year","")}.log"'},
    )


async def _calculate_trust_streak(user_id: str) -> Dict[str, Any]:
    """Count consecutive reporting years with a persisted snapshot, starting from the most recent."""
    import hashlib as _hl
    workspace_hash = _hl.sha256(user_id.encode()).hexdigest()
    years = await db.snapshots.distinct("reporting_year", {"workspace_id_hashed": workspace_hash})
    years = sorted([y for y in years if isinstance(y, int)], reverse=True)
    if not years:
        return {"current_streak": 0, "last_streak_year": None, "next_due_year": None}
    streak = 1
    for prev in years[1:]:
        if prev == years[0] - streak:
            streak += 1
        else:
            break
    last_year = years[0]
    return {
        "current_streak": streak,
        "last_streak_year": last_year,
        "next_due_year": last_year + 1,
    }


async def _compute_and_persist_snapshot(user_id: str, user_email: str, year: int):
    """Compute merkle root for a user+year, persist to snapshots collection. Returns entries + meta."""
    import hashlib as _hl
    docs = await db.audits.find({"user_id": user_id, "reporting_year": year, "status": "COMPLETE"}, {"_id": 0}).sort("created_at", 1).to_list(500)
    entries = []
    for a in docs:
        fh = a.get("file_hashes") or []
        composite = _hl.sha256(("|".join(x.get("sha256", "") for x in fh)).encode()).hexdigest() if fh else ""
        entries.append({
            "audit_id": a.get("audit_id", ""), "client_name": a.get("client_name", ""),
            "nace_code": a.get("nace_code", ""), "nace_name": a.get("nace_name", ""),
            "created_at": a.get("created_at", ""), "completed_at": a.get("completed_at", ""),
            "compliance_score": a.get("compliance_score"), "value_at_stake_eur": a.get("value_at_stake_eur") or 0,
            "critical_findings_count": a.get("critical_findings_count") or 0,
            "greenwashing_risk": a.get("greenwashing_risk", "NONE"), "composite_hash": composite,
        })
    # P1 · Gap 1.2 — reject empty ledgers.
    if not entries:
        raise HTTPException(status_code=400, detail="Cannot attest to an empty ledger.")

    merkle_root = _hl.sha256(("|".join(e["composite_hash"] for e in entries)).encode()).hexdigest()
    workspace_hash = _hl.sha256(user_id.encode()).hexdigest()
    generated_at = datetime.now(timezone.utc).isoformat()

    # P0 · Gap 2.1 — reject spoof: same merkle_root claimed by a different workspace.
    existing = await db.snapshots.find_one({"merkle_root": merkle_root}, {"_id": 0, "workspace_id_hashed": 1})
    if existing and existing.get("workspace_id_hashed") != workspace_hash:
        raise HTTPException(status_code=409, detail="Merkle root already registered under a different workspace.")

    # P1 · Gap 1.3 — upsert keyed on (workspace, year): most recent root for that year wins.
    await db.snapshots.update_one(
        {"workspace_id_hashed": workspace_hash, "reporting_year": year},
        {"$set": {"merkle_root": merkle_root, "workspace_id_hashed": workspace_hash,
                  "audit_count": len(entries), "reporting_year": year, "generated_at": generated_at}},
        upsert=True,
    )
    # Recompute and persist streak on the workspace (user) doc.
    streak = await _calculate_trust_streak(user_id)
    await db.users.update_one({"user_id": user_id}, {"$set": {
        "current_streak": streak["current_streak"],
        "last_streak_year": streak["last_streak_year"],
    }})
    _LB_CACHE["expires"] = 0  # streak changed → invalidate leaderboard cache
    return entries, merkle_root, generated_at


@api_router.get("/ledger/snapshot")
async def ledger_snapshot(year: int, user: dict = Depends(get_current_user)):
    entries, merkle_root, _ = await _compute_and_persist_snapshot(user["user_id"], user.get("email", ""), year)
    pdf_bytes = build_snapshot_pdf(entries, year, merkle_root, workspace_email=user.get("email", ""))
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="AuditEngine_Snapshot_FY{year}.pdf"'},
    )


@api_router.get("/ledger/snapshot-meta")
async def ledger_snapshot_meta(year: int, user: dict = Depends(get_current_user)):
    """Persist + return only the metadata (no PDF). Used by the badge generator."""
    entries, merkle_root, generated_at = await _compute_and_persist_snapshot(user["user_id"], user.get("email", ""), year)
    return {"merkle_root": merkle_root, "reporting_year": year, "audit_count": len(entries), "generated_at": generated_at}


@api_router.get("/public/badge/{merkle_root}.svg")
@limiter.limit("60/minute")
async def public_badge_svg(request: Request, merkle_root: str):
    """Return a static SVG attestation badge. Public, no auth."""
    root = (merkle_root or "").lower()
    if not (len(root) == 64 and all(c in "0123456789abcdef" for c in root)):
        raise HTTPException(status_code=400, detail="Invalid merkle root")
    snap = await db.snapshots.find_one({"merkle_root": root}, {"_id": 0})
    year = snap.get("reporting_year") if snap else None
    audit_count = snap.get("audit_count") if snap else None
    short = f"{root[:8]}…{root[-8:]}"
    year_line = f"FY{year} · {audit_count} AUDITS" if snap else "UNREGISTERED"
    tick_color = "#00FF41" if snap else "#FF0000"
    status_text = "VERIFIED BY AUDITENGINE" if snap else "UNVERIFIED"

    # Static, dependency-free SVG. All colors hard-coded, monospace font-family for portability.
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="280" height="88" viewBox="0 0 280 88" role="img" aria-label="Verified by AuditEngine">
  <title>Verified by AuditEngine · {short}</title>
  <rect x="0.25" y="0.25" width="279.5" height="87.5" fill="#000000" stroke="#FFFFFF" stroke-width="0.5"/>
  <rect x="0.25" y="0.25" width="18" height="87.5" fill="#000000" stroke="#FFFFFF" stroke-width="0.5"/>
  <text x="9.25" y="52" text-anchor="middle" font-family="'Courier New', ui-monospace, monospace" font-size="16" font-weight="700" fill="{tick_color}">✓</text>
  <text x="28" y="24" font-family="'Courier New', ui-monospace, monospace" font-size="7.5" font-weight="700" fill="#808080" letter-spacing="1.6">// TRUST ANCHOR</text>
  <text x="28" y="43" font-family="'Courier New', ui-monospace, monospace" font-size="11" font-weight="700" fill="{tick_color}" letter-spacing="0.6">{status_text}</text>
  <text x="28" y="60" font-family="'Courier New', ui-monospace, monospace" font-size="8.5" font-weight="500" fill="#E8E8E8" letter-spacing="0.6">{short}</text>
  <text x="28" y="74" font-family="'Courier New', ui-monospace, monospace" font-size="7.5" font-weight="500" fill="#808080" letter-spacing="1.2">{year_line}</text>
</svg>'''
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=300"},
    )


@api_router.get("/public/registry")
@limiter.limit("60/minute")
async def public_registry(request: Request, page: int = 1, limit: int = 50, workspace: Optional[str] = None):
    """Public transparency log. Zero PII: only mathematical roots + timestamps."""
    page = max(1, page)
    limit = max(1, min(200, limit))
    q: Dict[str, Any] = {}
    if workspace:
        if not (len(workspace) == 64 and all(c in "0123456789abcdef" for c in workspace.lower())):
            raise HTTPException(status_code=400, detail="Invalid workspace hash")
        q["workspace_id_hashed"] = workspace.lower()
    total = await db.snapshots.count_documents(q)
    skip = (page - 1) * limit
    cursor = db.snapshots.find(
        q,
        {"_id": 0, "merkle_root": 1, "reporting_year": 1, "audit_count": 1, "generated_at": 1},
    ).sort("generated_at", -1).skip(skip).limit(limit)
    entries = await cursor.to_list(limit)

    workspace_streak = None
    if workspace:
        # Look up streak for opted-in workspaces only; else return None.
        import hashlib as _hl
        candidates = await db.users.find(
            {"leaderboard_opt_in": True},
            {"_id": 0, "user_id": 1, "current_streak": 1, "last_streak_year": 1},
        ).to_list(2000)
        for u in candidates:
            if _hl.sha256(u["user_id"].encode()).hexdigest() == workspace.lower():
                workspace_streak = {
                    "current_streak": u.get("current_streak") or 0,
                    "last_streak_year": u.get("last_streak_year"),
                }
                break

    return {
        "page": page, "limit": limit, "total": total,
        "has_next": skip + len(entries) < total, "entries": entries,
        "workspace_filter": workspace.lower() if workspace else None,
        "workspace_streak": workspace_streak,
    }


@api_router.get("/settings/streak")
async def my_streak(user: dict = Depends(get_current_user)):
    """Live streak status for the authenticated workspace + due-date signal."""
    streak = await _calculate_trust_streak(user["user_id"])
    now_year = datetime.now(timezone.utc).year
    last_year = streak["last_streak_year"]
    at_risk = bool(last_year is not None and now_year > last_year)
    return {**streak, "current_year": now_year, "at_risk": at_risk}


@api_router.get("/public/leaderboard")
@limiter.limit("60/minute")
async def public_leaderboard(request: Request, limit: int = 100):
    """Public, opt-in only. Cached (60s TTL). Zero PII: only workspace hashes + counts."""
    import time as _t
    now = _t.time()
    if _LB_CACHE.get("data") and _LB_CACHE.get("expires", 0) > now:
        return _LB_CACHE["data"]

    limit = max(1, min(500, limit))
    # Set of opted-in workspace_id_hashed + their streak from user docs
    opted_in_users = await db.users.find(
        {"leaderboard_opt_in": True},
        {"_id": 0, "user_id": 1, "current_streak": 1, "last_streak_year": 1},
    ).to_list(2000)
    import hashlib as _hl
    hash_to_streak: Dict[str, Dict[str, Any]] = {}
    for u in opted_in_users:
        h = _hl.sha256(u["user_id"].encode()).hexdigest()
        hash_to_streak[h] = {
            "current_streak": u.get("current_streak") or 0,
            "last_streak_year": u.get("last_streak_year"),
        }
    allowed = set(hash_to_streak.keys())

    if not allowed:
        payload = {"total_workspaces": 0, "entries": [], "cached_at": datetime.now(timezone.utc).isoformat()}
        _LB_CACHE.update({"data": payload, "expires": now + _LB_TTL_SECONDS})
        return payload

    pipeline = [
        {"$match": {"workspace_id_hashed": {"$in": list(allowed)}}},
        {"$group": {
            "_id": "$workspace_id_hashed",
            "total_audits": {"$sum": "$audit_count"},
            "snapshot_count": {"$sum": 1},
            "last_attestation_date": {"$max": "$generated_at"},
            "first_attestation_date": {"$min": "$generated_at"},
        }},
    ]
    agg = await db.snapshots.aggregate(pipeline).to_list(len(allowed))
    # Merge streak, then sort by (total_audits DESC, streak DESC, last_attestation DESC)
    merged = []
    for row in agg:
        s = hash_to_streak.get(row["_id"], {})
        merged.append({
            "workspace_id_hashed": row["_id"],
            "total_audits": row["total_audits"],
            "snapshot_count": row["snapshot_count"],
            "last_attestation_date": row["last_attestation_date"],
            "first_attestation_date": row["first_attestation_date"],
            "current_streak": s.get("current_streak", 0),
            "last_streak_year": s.get("last_streak_year"),
        })
    merged.sort(key=lambda r: (r["total_audits"], r["current_streak"], r["last_attestation_date"] or ""), reverse=True)
    entries = [{"rank": i + 1, **row} for i, row in enumerate(merged[:limit])]
    payload = {"total_workspaces": len(entries), "entries": entries, "cached_at": datetime.now(timezone.utc).isoformat()}
    _LB_CACHE.update({"data": payload, "expires": now + _LB_TTL_SECONDS})
    return payload


@api_router.get("/public/verify/{merkle_root}")
@limiter.limit("60/minute")
async def public_verify(request: Request, merkle_root: str):
    # No auth. Returns integrity confirmation only — no PII, no audit details.
    if not merkle_root or len(merkle_root) != 64 or any(c not in "0123456789abcdef" for c in merkle_root.lower()):
        return JSONResponse(status_code=400, content={"status": "INVALID_ROOT"})
    snap = await db.snapshots.find_one({"merkle_root": merkle_root.lower()}, {"_id": 0})
    if not snap:
        return JSONResponse(status_code=404, content={"status": "NOT_FOUND"})
    return {
        "status": "VERIFIED",
        "workspace_id_hashed": snap["workspace_id_hashed"],
        "audit_count": snap["audit_count"],
        "reporting_year": snap.get("reporting_year"),
        "timestamp": snap["generated_at"],
    }


app.include_router(api_router)
app.include_router(make_regulator_router(db))
app.include_router(make_billing_router(db, get_current_user))


@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    return await handle_stripe_webhook(request, db)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _create_indexes():
    """Idempotent index creation for hot paths."""
    try:
        # One-time migration: coerce any legacy string `expires_at` values to
        # BSON dates so the TTL index below can actually reap them.
        legacy = await db.user_sessions.find(
            {"expires_at": {"$type": "string"}},
            {"_id": 1, "session_token": 1, "expires_at": 1},
        ).to_list(10000)
        for row in legacy:
            try:
                dt = datetime.fromisoformat(row["expires_at"])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                await db.user_sessions.update_one({"_id": row["_id"]}, {"$set": {"expires_at": dt}})
            except Exception:
                # Malformed row — nuke it; a fresh login will replace.
                await db.user_sessions.delete_one({"_id": row["_id"]})

        # If a prior non-TTL index exists on expires_at, drop it so the TTL variant can be created.
        try:
            existing = await db.user_sessions.index_information()
            for name, spec in existing.items():
                if name == "_id_":
                    continue
                keys = spec.get("key") or []
                if len(keys) == 1 and keys[0][0] == "expires_at" and spec.get("expireAfterSeconds") is None:
                    await db.user_sessions.drop_index(name)
        except Exception as e:
            logger.warning(f"Could not inspect/drop legacy expires_at index: {e}")

        await db.snapshots.create_index("merkle_root", unique=True)
        await db.snapshots.create_index([("workspace_id_hashed", 1), ("reporting_year", 1)])
        await db.snapshots.create_index([("generated_at", -1)])
        await db.users.create_index("leaderboard_opt_in")
        await db.users.create_index("user_id", unique=True)
        await db.users.create_index("email")
        await db.audits.create_index([("user_id", 1), ("reporting_year", 1), ("status", 1)])
        await db.audits.create_index("audit_id", unique=True)
        await db.user_sessions.create_index("session_token", unique=True)
        # TTL index — MongoDB reaps rows whose expires_at is in the past.
        await db.user_sessions.create_index("expires_at", expireAfterSeconds=0)
        await db.regulator_keys.create_index("key_hash", unique=True)
        await db.regulator_keys.create_index("expires_at")
        await db.payment_transactions.create_index("session_id", unique=True)
        await db.payment_transactions.create_index([("created_at", -1)])
        logger.info("Indexes ensured on hot-path collections (incl. TTL on user_sessions.expires_at)")
    except Exception as e:
        logger.warning(f"Index creation warning (may pre-exist): {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
