"""Postgres persistence for session metadata via SQLAlchemy async."""
from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.session_manager import SessionRecord

logger = structlog.get_logger(__name__)

_UPSERT_SESSION = text("""
    INSERT INTO sessions
        (session_id, candidate_id, scenario_id, tenant_id, state, started_at, ended_at)
    VALUES
        (:session_id, :candidate_id, :scenario_id, :tenant_id, :state, :started_at, :ended_at)
    ON CONFLICT (session_id) DO UPDATE SET
        state      = EXCLUDED.state,
        ended_at   = EXCLUDED.ended_at
""")


async def upsert_session(db: AsyncSession, record: SessionRecord) -> None:
    """Insert or update a session row. Raises on DB errors (caller handles)."""
    await db.execute(
        _UPSERT_SESSION,
        {
            "session_id": record.session_id,
            "candidate_id": record.candidate_id,
            "scenario_id": record.scenario_id,
            "tenant_id": record.tenant_id,
            "state": record.state.value,
            "started_at": record.started_at,
            "ended_at": record.ended_at,
        },
    )
    await db.commit()
    logger.info("session_persisted", session_id=record.session_id, state=record.state)
