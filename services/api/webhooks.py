"""POST /webhooks — register webhook URLs; deliver fingerprints on assembly."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from services.api.auth import get_current_tenant
from services.api.dependencies import get_db
from services.api.models import WebhookRequest, WebhookResponse
from services.api.rate_limiter import check_rate_limit

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ---------------------------------------------------------------------------
# Registration endpoint
# ---------------------------------------------------------------------------


@router.post("", response_model=WebhookResponse, status_code=201)
async def register_webhook(
    body: WebhookRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> WebhookResponse:
    """Register a URL to receive OrchestraFingerprint payloads."""
    check_rate_limit(tenant_id)
    webhook_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    url_str = str(body.url)
    await db.execute(
        text(
            "INSERT INTO webhooks (webhook_id, tenant_id, url, active, created_at)"
            " VALUES (:wid, :tid, :url, TRUE, :now)"
        ),
        {"wid": webhook_id, "tid": tenant_id, "url": url_str, "now": now},
    )
    await db.commit()
    logger.info("webhook_registered", webhook_id=webhook_id, tenant_id=tenant_id, url=url_str)
    return WebhookResponse(
        webhook_id=webhook_id,
        tenant_id=tenant_id,
        url=url_str,
        active=True,
        created_at=now.isoformat(),
    )


# ---------------------------------------------------------------------------
# Delivery service
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
async def _post_with_retry(url: str, payload: dict) -> None:  # type: ignore[type-arg]
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()


async def deliver_fingerprint(
    fingerprint_dict: dict,  # type: ignore[type-arg]
    db: AsyncSession,
) -> None:
    """POST the assembled fingerprint to all active webhooks for the session's tenant.

    Called by the Airflow task (or any post-assembly hook) after a fingerprint is saved.
    Retries 3× with exponential back-off per webhook; failures are logged but do not
    propagate — delivery is best-effort once a fingerprint is assembled.
    """
    session_id = fingerprint_dict.get("session_id", "")

    # Resolve tenant from the sessions table
    row = await db.execute(
        text("SELECT tenant_id FROM sessions WHERE session_id = :sid"),
        {"sid": session_id},
    )
    record = row.fetchone()
    if not record:
        logger.warning("webhook_delivery_no_session", session_id=session_id)
        return
    tenant_id: str = record[0]

    hooks_result = await db.execute(
        text(
            "SELECT webhook_id, url FROM webhooks"
            " WHERE tenant_id = :tid AND active = TRUE"
        ),
        {"tid": tenant_id},
    )
    hooks = hooks_result.fetchall()

    for webhook_id, url in hooks:
        try:
            await _post_with_retry(url, fingerprint_dict)
            logger.info(
                "webhook_delivered",
                webhook_id=webhook_id,
                session_id=session_id,
                url=url,
            )
        except Exception as exc:
            logger.error(
                "webhook_delivery_failed",
                webhook_id=webhook_id,
                session_id=session_id,
                url=url,
                error=str(exc),
            )
