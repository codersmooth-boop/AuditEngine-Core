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

from llm_service import analyze_documents
from pdf_service import build_audit_pdf, build_board_brief_pdf
from file_extractor import extract_text_from_file

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="AuditEngine")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("auditengine")

# Load NACE data once
with open(ROOT_DIR / "nace_rev2.json", "r") as f:
    NACE_CODES = json.load(f)


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
    body = await request.json()
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
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    response.set_cookie(
        key="session_token", value=session_token,
        max_age=7 * 24 * 3600, httponly=True, secure=True, samesite="none", path="/",
    )
    return {"user_id": user_id, "email": email, "name": data["name"], "picture": data.get("picture")}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user_id": user["user_id"], "email": user["email"], "name": user["name"], "picture": user.get("picture")}


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


async def _run_processing(audit_id: str, extracted_texts: List[dict], client_name: str, nace_name: str, reporting_year: int):
    """Simulate 5-step processing, then persist findings."""
    try:
        # Step 1 already done (file extraction). Step 2 payload writing
        await db.audits.update_one({"audit_id": audit_id}, {"$set": {"status": "PROCESSING", "processing_step": 1}})
        await asyncio.sleep(1.2)
        await db.audits.update_one({"audit_id": audit_id}, {"$set": {"processing_step": 2}})
        await asyncio.sleep(1.0)
        # Step 3 Logic engine (LLM)
        await db.audits.update_one({"audit_id": audit_id}, {"$set": {"processing_step": 3}})
        result = await analyze_documents(extracted_texts, client_name, nace_name, reporting_year)
        # Step 4 risk map
        await db.audits.update_one({"audit_id": audit_id}, {"$set": {"processing_step": 4}})
        await asyncio.sleep(0.8)
        # Step 5 pdf delivery
        await db.audits.update_one({"audit_id": audit_id}, {"$set": {"processing_step": 5}})
        await asyncio.sleep(0.6)

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
    except Exception as e:
        logger.exception("Processing failed")
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
    for f in files:
        content = await f.read()
        text = extract_text_from_file(f.filename or "file", content)
        extracted.append({"filename": f.filename, "text": text[:60000]})
        filenames.append(f.filename)

    await db.audits.update_one(
        {"audit_id": audit_id},
        {"$set": {"files": filenames, "status": "PROCESSING", "processing_step": 1}},
    )

    background_tasks.add_task(
        _run_processing, audit_id, extracted,
        audit["client_name"], audit["nace_name"], audit["reporting_year"],
    )
    return {"ok": True, "audit_id": audit_id, "files": filenames}


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


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
