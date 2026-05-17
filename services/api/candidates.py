"""POST /candidates — register a candidate for assessment."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.auth import get_current_tenant
from services.api.dependencies import get_db
from services.api.models import CandidateRequest, CandidateResponse
from services.api.rate_limiter import check_rate_limit

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("", response_model=CandidateResponse, status_code=201)
async def register_candidate(
    body: CandidateRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    """Register a new candidate under the calling tenant."""
    check_rate_limit(tenant_id)
    candidate_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    await db.execute(
        text(
            "INSERT INTO candidates (candidate_id, tenant_id, email, name, created_at)"
            " VALUES (:cid, :tid, :email, :name, :now)"
        ),
        {
            "cid": candidate_id,
            "tid": tenant_id,
            "email": body.email,
            "name": body.name,
            "now": now,
        },
    )
    await db.commit()
    logger.info("candidate_registered", candidate_id=candidate_id, tenant_id=tenant_id)
    return CandidateResponse(
        candidate_id=candidate_id,
        tenant_id=tenant_id,
        email=body.email,
        name=body.name,
        created_at=now.isoformat(),
    )


@router.delete("/{candidate_id}", status_code=204)
async def delete_candidate(
    candidate_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    """GDPR purge: remove candidate and all associated data (sessions, fingerprints).

    Cascades to all stores. Cache entries are evicted immediately.
    Kafka tombstone events are not emitted here — that requires a separate
    Airflow DAG (orchid_data_retention) for the streaming layer.
    """
    row = await db.execute(
        text(
            "SELECT candidate_id FROM candidates"
            " WHERE candidate_id = :cid AND tenant_id = :tid"
        ),
        {"cid": candidate_id, "tid": tenant_id},
    )
    if not row.fetchone():
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id!r} not found")

    sessions_result = await db.execute(
        text("SELECT session_id FROM sessions WHERE candidate_id = :cid AND tenant_id = :tid"),
        {"cid": candidate_id, "tid": tenant_id},
    )
    session_ids = [r[0] for r in sessions_result.fetchall()]

    from services.api.cache import fingerprint_cache

    for sid in session_ids:
        fingerprint_cache.delete(f"fp:{tenant_id}:{sid}")
        await db.execute(
            text("DELETE FROM fingerprints WHERE session_id = :sid AND tenant_id = :tid"),
            {"sid": sid, "tid": tenant_id},
        )

    await db.execute(
        text("DELETE FROM sessions WHERE candidate_id = :cid AND tenant_id = :tid"),
        {"cid": candidate_id, "tid": tenant_id},
    )
    await db.execute(
        text("DELETE FROM candidates WHERE candidate_id = :cid AND tenant_id = :tid"),
        {"cid": candidate_id, "tid": tenant_id},
    )
    await db.commit()
    logger.info(
        "candidate_purged_gdpr",
        candidate_id=candidate_id,
        tenant_id=tenant_id,
        sessions_purged=len(session_ids),
    )


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    """Fetch a candidate by ID, scoped to the calling tenant."""
    check_rate_limit(tenant_id)
    row = await db.execute(
        text(
            "SELECT candidate_id, tenant_id, email, name, created_at"
            " FROM candidates WHERE candidate_id = :cid AND tenant_id = :tid"
        ),
        {"cid": candidate_id, "tid": tenant_id},
    )
    record = row.fetchone()
    if not record:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id!r} not found")
    cid, tid, email, name, created_at = record
    return CandidateResponse(
        candidate_id=cid,
        tenant_id=tid,
        email=email,
        name=name,
        created_at=created_at.isoformat(),
    )
