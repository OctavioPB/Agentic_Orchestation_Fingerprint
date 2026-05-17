"""Postgres-backed fingerprint store: save and retrieve assembled fingerprints."""
from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def save_fingerprint(
    db: AsyncSession,
    session_id: str,
    tenant_id: str,
    fingerprint_dict: dict,  # type: ignore[type-arg]
) -> None:
    """Upsert a fingerprint JSON blob for the given session."""
    now = datetime.now(UTC)
    payload = json.dumps(fingerprint_dict)
    await db.execute(
        text(
            "INSERT INTO fingerprints (session_id, tenant_id, fingerprint, assembled_at)"
            " VALUES (:sid, :tid, :fp, :now)"
            " ON CONFLICT (session_id) DO UPDATE"
            "   SET fingerprint = EXCLUDED.fingerprint,"
            "       assembled_at = EXCLUDED.assembled_at"
        ),
        {"sid": session_id, "tid": tenant_id, "fp": payload, "now": now},
    )
    await db.commit()
    logger.info("fingerprint_saved", session_id=session_id, tenant_id=tenant_id)


async def get_fingerprint(
    db: AsyncSession,
    session_id: str,
    tenant_id: str,
) -> dict | None:  # type: ignore[type-arg]
    """Return the fingerprint dict for the session, or None if not yet assembled.

    Enforces tenant isolation: a tenant can only read its own fingerprints.
    """
    row = await db.execute(
        text(
            "SELECT fingerprint, assembled_at FROM fingerprints"
            " WHERE session_id = :sid AND tenant_id = :tid"
        ),
        {"sid": session_id, "tid": tenant_id},
    )
    record = row.fetchone()
    if not record:
        return None
    fp_json, assembled_at = record
    data: dict = json.loads(fp_json)  # type: ignore[type-arg]
    data["assembled_at"] = assembled_at.isoformat() if assembled_at else None
    return data
