"""REST endpoints for session lifecycle management."""
from __future__ import annotations

import asyncio
import os

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.api import state
from services.api.auth import get_current_tenant
from services.api.dependencies import get_db
from services.api.models import CreateSessionRequest, EventsResponse, SessionResponse
from services.api.session_manager import InvalidTransitionError, SessionState
from services.api.session_repository import upsert_session
from services.telemetry.models import ScenarioEndedPayload, ScenarioStartedPayload, TelemetryEvent

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])

_SANDBOX_MAX_DURATION_SEC = int(os.getenv("SANDBOX_MAX_DURATION_SEC", "3600"))


# ── Timeout task ───────────────────────────────────────────────────────────────


async def _run_timeout(session_id: str) -> None:
    """Auto-complete a session after SANDBOX_MAX_DURATION_SEC seconds."""
    await asyncio.sleep(_SANDBOX_MAX_DURATION_SEC)
    record = state.session_manager.get(session_id)
    if record is None or record.state == SessionState.COMPLETED:
        return
    try:
        state.session_manager.transition(session_id, SessionState.COMPLETED)
    except InvalidTransitionError:
        return
    if state.producer:
        ended = TelemetryEvent.scenario_ended(
            session_id,
            ScenarioEndedPayload(
                reason="timeout",
                duration_sec=_SANDBOX_MAX_DURATION_SEC,
            ),
        )
        await state.producer.emit(ended)
    logger.info("session_auto_completed", session_id=session_id, reason="timeout")


# ── Helpers ────────────────────────────────────────────────────────────────────


def _to_response(record) -> SessionResponse:  # type: ignore[no-untyped-def]
    return SessionResponse(
        session_id=record.session_id,
        candidate_id=record.candidate_id,
        scenario_id=record.scenario_id,
        tenant_id=record.tenant_id,
        state=record.state.value,
        started_at=record.started_at.isoformat(),
        ended_at=record.ended_at.isoformat() if record.ended_at else None,
    )


async def _persist(db: AsyncSession, record) -> None:  # type: ignore[no-untyped-def]
    try:
        await upsert_session(db, record)
    except Exception as exc:
        logger.warning("db_persist_failed", session_id=record.session_id, error=str(exc))


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
) -> list[SessionResponse]:
    """List all sessions for the calling tenant, newest first."""
    result = await db.execute(
        text(
            "SELECT session_id, candidate_id, scenario_id, tenant_id, state, started_at, ended_at"
            " FROM sessions WHERE tenant_id = :tid"
            " ORDER BY started_at DESC LIMIT :limit OFFSET :offset"
        ),
        {"tid": tenant_id, "limit": limit, "offset": offset},
    )
    rows = result.fetchall()
    return [
        SessionResponse(
            session_id=r[0],
            candidate_id=r[1],
            scenario_id=r[2],
            tenant_id=r[3],
            state=r[4],
            started_at=r[5].isoformat() if hasattr(r[5], "isoformat") else r[5],
            ended_at=r[6].isoformat() if r[6] and hasattr(r[6], "isoformat") else r[6],
        )
        for r in rows
    ]


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    record = state.session_manager.create(
        candidate_id=body.candidate_id,
        scenario_id=body.scenario_id,
        tenant_id=body.tenant_id,
    )
    state.session_manager.transition(record.session_id, SessionState.ACTIVE)

    # Emit SCENARIO_STARTED (best-effort)
    if state.producer:
        started = TelemetryEvent.scenario_started(
            record.session_id,
            ScenarioStartedPayload(
                scenario_id=body.scenario_id,
                scenario_version="v1",
            ),
        )
        await state.producer.emit(started)

    await _persist(db, record)

    # Start timeout watchdog
    task: asyncio.Task[None] = asyncio.create_task(
        _run_timeout(record.session_id),
        name=f"timeout:{record.session_id}",
    )
    state.timeout_tasks[record.session_id] = task

    logger.info("session_started", session_id=record.session_id, scenario=body.scenario_id)
    return _to_response(record)


@router.delete("/{session_id}", response_model=SessionResponse)
async def end_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    record = state.session_manager.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")

    try:
        state.session_manager.transition(session_id, SessionState.COMPLETED)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # Cancel timeout watchdog
    task = state.timeout_tasks.pop(session_id, None)
    if task:
        task.cancel()

    if state.producer and record.started_at:
        duration = int(
            (record.ended_at - record.started_at).total_seconds()
            if record.ended_at
            else 0
        )
        ended = TelemetryEvent.scenario_ended(
            session_id,
            ScenarioEndedPayload(reason="completed", duration_sec=duration),
        )
        await state.producer.emit(ended)

    await _persist(db, record)
    logger.info("session_ended", session_id=session_id)
    return _to_response(record)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    record = state.session_manager.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    return _to_response(record)


@router.get("/{session_id}/events", response_model=EventsResponse)
async def get_session_events(
    session_id: str,
    offset: int = 0,
    limit: int = 50,
) -> EventsResponse:
    """Return paginated session events.

    Event storage (Qdrant + Kafka replay) is implemented in Sprint 6.
    Until then, returns an empty list so the endpoint contract is established.
    """
    if state.session_manager.get(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
    return EventsResponse(
        session_id=session_id,
        events=[],
        total=0,
        offset=offset,
        limit=limit,
    )


@router.get("/{session_id}/fingerprint")
async def get_session_fingerprint(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:  # type: ignore[type-arg]
    """Return the assembled OrchestraFingerprint for a session.

    Returns 404 if the fingerprint has not yet been assembled by the Airflow DAG.
    Tenant isolation is enforced via the session record's tenant_id.
    Responses are cached in-process for 1 hour.
    """
    from services.api.cache import fingerprint_cache
    from services.api.fingerprint_repository import get_fingerprint

    record = state.session_manager.get(session_id)
    if record is None:
        row = await db.execute(
            text("SELECT tenant_id FROM sessions WHERE session_id = :sid"),
            {"sid": session_id},
        )
        db_record = row.fetchone()
        if not db_record:
            raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")
        tenant_id: str = db_record[0]
    else:
        tenant_id = record.tenant_id

    cache_key = f"fp:{tenant_id}:{session_id}"
    cached = fingerprint_cache.get(cache_key)
    if cached is not None:
        return cached

    fingerprint = await get_fingerprint(db, session_id, tenant_id)
    if fingerprint is None:
        raise HTTPException(
            status_code=404,
            detail=f"Fingerprint for session {session_id!r} not yet assembled",
        )
    fingerprint_cache.set(cache_key, fingerprint)
    return fingerprint
