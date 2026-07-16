"""Regulator Sandbox — aggregated, read-only analytics for institutional access.

Design principles:
- Time-boxed API keys stored in `regulator_keys` collection.
- k-anonymity: buckets with fewer than K_ANON items are suppressed.
- Absolute zero client identity: only aggregate counts / averages / histograms.
- Per-key rate limit: RATE_LIMIT_PER_MIN requests / 60s (in-memory token bucket).
- Every response includes the current Registry Master Root, a SHA-256 rolling
  digest over every `merkle_root` in the snapshots collection ordered by
  `generated_at`. This provides institutional callers a single value they can
  cross-verify against the public `/registry` transparency log.
"""
import hashlib
import secrets
import time
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Deque, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

K_ANON = 5                    # suppress any bucket with fewer than K items
RATE_LIMIT_PER_MIN = 10       # per regulator key
_RATE_BUCKETS: Dict[str, Deque[float]] = defaultdict(deque)


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def issue_key(db, name: str, organization: str, ttl_days: int = 30) -> str:
    """Admin utility — mint a fresh regulator key. Returns the raw key (shown once)."""
    raw = f"reg_{secrets.token_urlsafe(24)}"
    await db.regulator_keys.insert_one({
        "key_hash": _hash_key(raw),
        "name": name,
        "organization": organization,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat(),
        "disabled": False,
        "last_used": None,
        "request_count": 0,
    })
    return raw


async def _compute_registry_master_root(db) -> Dict[str, object]:
    """Rolling SHA-256 over every merkle_root in generated_at order.

    The result is a single fingerprint of the entire public Registry at read
    time — regulators can compare this value across their own historical
    captures of the /api/public/registry log to detect any tampering or
    retroactive edits.
    """
    docs = await db.snapshots.find(
        {}, {"_id": 0, "merkle_root": 1, "generated_at": 1},
    ).sort("generated_at", 1).to_list(200000)
    if not docs:
        return {"registry_master_root": None, "snapshot_count": 0, "latest_snapshot_at": None}
    concat = "|".join(d.get("merkle_root", "") for d in docs)
    master = hashlib.sha256(concat.encode()).hexdigest()
    return {
        "registry_master_root": master,
        "snapshot_count": len(docs),
        "latest_snapshot_at": docs[-1].get("generated_at"),
    }


def _rate_limit(key_hash: str) -> None:
    now = time.time()
    window_start = now - 60.0
    bucket = _RATE_BUCKETS[key_hash]
    while bucket and bucket[0] < window_start:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_PER_MIN:
        retry_in = int(60 - (now - bucket[0])) + 1
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded — {RATE_LIMIT_PER_MIN}/min per key. Retry in {retry_in}s.",
        )
    bucket.append(now)


def make_router(db):
    router = APIRouter(prefix="/api/regulator/sandbox", tags=["regulator"])

    async def _authorize(request: Request) -> dict:
        raw = (
            request.headers.get("x-regulator-key")
            or request.headers.get("X-Regulator-Key")
            or ""
        ).strip()
        if not raw:
            raise HTTPException(status_code=401, detail="Missing X-Regulator-Key header")
        key_hash = _hash_key(raw)
        row = await db.regulator_keys.find_one(
            {"key_hash": key_hash, "disabled": {"$ne": True}}, {"_id": 0},
        )
        if not row:
            raise HTTPException(status_code=401, detail="Invalid regulator key")
        expires_at = row.get("expires_at", "")
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if exp_dt < datetime.now(timezone.utc):
                    raise HTTPException(status_code=401, detail="Regulator key expired")
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=401, detail="Regulator key expiry unreadable")
        _rate_limit(key_hash)
        await db.regulator_keys.update_one(
            {"key_hash": key_hash},
            {"$set": {"last_used": datetime.now(timezone.utc).isoformat()},
             "$inc": {"request_count": 1}},
        )
        return {
            "key_hash": key_hash,
            "name": row["name"],
            "organization": row["organization"],
            "expires_at": expires_at,
        }

    def _suppress(bucket_size: int) -> bool:
        return bucket_size < K_ANON

    async def _envelope(payload: dict) -> dict:
        anchor = await _compute_registry_master_root(db)
        return {
            **payload,
            "k_anonymity_threshold": K_ANON,
            "rate_limit_per_min": RATE_LIMIT_PER_MIN,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "cross_verification": anchor,
        }

    @router.get("")
    async def index(auth: dict = Depends(_authorize)):
        return await _envelope({
            "sandbox": "AuditEngine // Regulator Sandbox",
            "organization": auth["organization"],
            "key_expires_at": auth["expires_at"],
            "endpoints": [
                "/api/regulator/sandbox/whoami",
                "/api/regulator/sandbox/adoption",
                "/api/regulator/sandbox/streaks",
                "/api/regulator/sandbox/scores",
                "/api/regulator/sandbox/volatility",
            ],
        })

    @router.get("/whoami")
    async def whoami(auth: dict = Depends(_authorize)):
        return await _envelope({
            "organization": auth["organization"],
            "name": auth["name"],
            "key_expires_at": auth["expires_at"],
        })

    @router.get("/adoption")
    async def adoption(auth: dict = Depends(_authorize)):
        """Compliance-score distribution grouped by NACE section (letter). k-anonymized."""
        pipeline = [
            {"$match": {"status": "COMPLETE", "compliance_score": {"$ne": None}}},
            {"$group": {
                "_id": {"$substr": ["$nace_code", 0, 1]},
                "audit_count": {"$sum": 1},
                "avg_score": {"$avg": "$compliance_score"},
                "min_score": {"$min": "$compliance_score"},
                "max_score": {"$max": "$compliance_score"},
                "critical_findings_total": {"$sum": {"$ifNull": ["$critical_findings_count", 0]}},
            }},
            {"$sort": {"_id": 1}},
        ]
        rows = await db.audits.aggregate(pipeline).to_list(64)
        buckets = []
        suppressed = 0
        for r in rows:
            if _suppress(r["audit_count"]):
                suppressed += r["audit_count"]
                continue
            buckets.append({
                "nace_section": r["_id"] or "?",
                "audit_count": r["audit_count"],
                "avg_score": round(r["avg_score"], 1),
                "min_score": r["min_score"],
                "max_score": r["max_score"],
                "critical_findings_total": r["critical_findings_total"],
            })
        return await _envelope({"buckets": buckets, "suppressed_audit_count": suppressed})

    @router.get("/streaks")
    async def streaks(auth: dict = Depends(_authorize)):
        """Streak longevity histogram — how long are workspaces staying compliant?"""
        rows = await db.users.find(
            {"current_streak": {"$gt": 0}},
            {"_id": 0, "current_streak": 1},
        ).to_list(20000)
        histogram = Counter(r["current_streak"] for r in rows)
        cells = []
        other = 0
        for k in sorted(histogram):
            n = histogram[k]
            if _suppress(n):
                other += n
            else:
                cells.append({"streak_years": k, "workspace_count": n})
        total = sum(histogram.values())
        return await _envelope({
            "total_workspaces_with_streak": total,
            "distribution": cells,
            "suppressed_count": other,
        })

    @router.get("/scores")
    async def scores(auth: dict = Depends(_authorize)):
        """Compliance-score bell curve — 10-point bucketed distribution across all completed audits."""
        rows = await db.audits.find(
            {"status": "COMPLETE", "compliance_score": {"$ne": None}},
            {"_id": 0, "compliance_score": 1},
        ).to_list(50000)
        histogram: dict = {i: 0 for i in range(0, 101, 10)}
        for r in rows:
            s = max(0, min(100, int(r["compliance_score"])))
            bucket = (s // 10) * 10
            histogram[bucket] += 1
        cells = []
        suppressed = 0
        for lower in sorted(histogram):
            n = histogram[lower]
            if _suppress(n):
                suppressed += n
                continue
            upper = lower + 9 if lower < 100 else 100
            cells.append({"range": f"{lower}-{upper}", "audit_count": n})
        return await _envelope({
            "total_audits": len(rows),
            "distribution": cells,
            "suppressed_count": suppressed,
        })

    @router.get("/volatility")
    async def volatility(auth: dict = Depends(_authorize)):
        """Audit failure & greenwashing incidence over time (by reporting_year)."""
        pipeline = [
            {"$match": {"status": "COMPLETE"}},
            {"$group": {
                "_id": "$reporting_year",
                "total": {"$sum": 1},
                "high_greenwashing": {"$sum": {"$cond": [{"$eq": ["$greenwashing_risk", "HIGH"]}, 1, 0]}},
                "non_compliant": {"$sum": {"$cond": [{"$lt": ["$compliance_score", 60]}, 1, 0]}},
                "avg_critical_findings": {"$avg": {"$ifNull": ["$critical_findings_count", 0]}},
            }},
            {"$sort": {"_id": 1}},
        ]
        rows = await db.audits.aggregate(pipeline).to_list(100)
        cells = []
        suppressed = 0
        for r in rows:
            if _suppress(r["total"]):
                suppressed += r["total"]
                continue
            cells.append({
                "reporting_year": r["_id"],
                "total_audits": r["total"],
                "high_greenwashing_pct": round(100 * r["high_greenwashing"] / r["total"], 1),
                "non_compliant_pct": round(100 * r["non_compliant"] / r["total"], 1),
                "avg_critical_findings": round(r["avg_critical_findings"], 2),
            })
        return await _envelope({
            "series": cells,
            "suppressed_audit_count": suppressed,
        })

    return router
