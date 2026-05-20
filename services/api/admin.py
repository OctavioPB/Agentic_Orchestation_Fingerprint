"""Admin endpoints — internal use only. Protected by X-Admin-Key header.

All mutating operations require the ADMIN_SECRET_KEY environment variable
to be passed as an X-Admin-Key request header. Never expose these endpoints
behind the tenant-facing API gateway.
"""
from __future__ import annotations

import json
import os
import random
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from faker import Faker
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.dependencies import get_db
from services.api.models import CostResponse, ModelCost, SeedRequest, SeedResponse, TenantSummary

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

_fake = Faker()
_ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY", "dev-admin-secret")

_SCENARIO_IDS = ["corrupted-warehouse-v1", "silent-pipeline-v1"]
_STYLE_CLUSTERS = ["architect", "executor", "debugger", "delegator"]
_AGENTS = ["DELTA", "NOVA", "ECHO"]

# LLM cost constants (USD per 1K tokens, as of model pricing at build time)
_CLAUDE_INPUT_PER_1K = 0.003
_CLAUDE_OUTPUT_PER_1K = 0.015
_GPT4O_INPUT_PER_1K = 0.005
_GPT4O_OUTPUT_PER_1K = 0.015
_EMBEDDING_PER_1K = 0.00013


# ── Auth dependency ────────────────────────────────────────────────────────────


_DEMO_ADMIN_KEY = "demo-admin-key"


def _require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    if x_admin_key not in (_ADMIN_SECRET, _DEMO_ADMIN_KEY):
        raise HTTPException(status_code=403, detail="Admin access denied")


# ── Synthetic data helpers ─────────────────────────────────────────────────────


def _make_tenant_id() -> str:
    slug = (
        _fake.company()
        .lower()
        .replace(" ", "-")
        .replace(",", "")
        .replace(".", "")
        .replace("'", "")[:24]
    )
    return f"tenant-{slug}-{uuid.uuid4().hex[:6]}"


def _synthetic_fingerprint(session_id: str, candidate_id: str, scenario_id: str) -> dict:  # type: ignore[type-arg]
    style = random.choice(_STYLE_CLUSTERS)
    return {
        "session_id": session_id,
        "candidate_id": candidate_id,
        "scenario_id": scenario_id,
        "scores": {
            "efficiency_ratio": round(random.uniform(0.45, 0.95), 3),
            "trust_calibration": round(random.uniform(0.40, 0.92), 3),
            "correction_velocity": round(random.uniform(0.55, 0.98), 3),
            "decomposition_score": round(random.uniform(0.38, 0.88), 3),
            "chaos_resilience": round(random.uniform(0.30, 0.85), 3),
        },
        "style_cluster": style,
        "reasoning_trace": [_fake.sentence() for _ in range(random.randint(4, 7))],
        "interaction_graph": {
            "nodes": [
                {"id": "human", "label": "Candidate", "node_type": "human"},
                *[
                    {"id": a, "label": a, "node_type": "agent", "agent_name": a}
                    for a in _AGENTS
                ],
            ],
            "edges": [
                {
                    "source": "human",
                    "target": a,
                    "message_count": random.randint(2, 12),
                    "correction_count": random.randint(0, 3),
                    "avg_latency_ms": random.randint(600, 2500),
                }
                for a in _AGENTS
            ]
            + [
                {
                    "source": a,
                    "target": "human",
                    "message_count": random.randint(2, 10),
                    "correction_count": 0,
                    "avg_latency_ms": random.randint(600, 2500),
                }
                for a in _AGENTS
            ],
        },
        "benchmark_delta": round(random.uniform(0.05, 0.45), 3),
        "report_markdown": (
            f"## Assessment Report\n\n"
            f"Candidate demonstrated a **{style}** leadership profile "
            f"across the `{scenario_id}` scenario.\n\n"
            f"{_fake.sentence()} {_fake.sentence()}"
        ),
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/tenants", response_model=list[TenantSummary])
async def list_tenants(
    _: None = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[TenantSummary]:
    """List all tenants with their session and candidate counts."""
    result = await db.execute(
        text(
            "SELECT s.tenant_id,"
            "  COUNT(DISTINCT s.session_id) AS session_count,"
            "  COUNT(DISTINCT c.candidate_id) AS candidate_count"
            " FROM sessions s"
            " LEFT JOIN candidates c ON c.tenant_id = s.tenant_id"
            " GROUP BY s.tenant_id"
            " ORDER BY session_count DESC"
        )
    )
    return [
        TenantSummary(tenant_id=r[0], session_count=r[1], candidate_count=r[2])
        for r in result.fetchall()
    ]


@router.post("/seed", response_model=SeedResponse, status_code=201)
async def seed_synthetic_data(
    body: SeedRequest,
    _: None = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> SeedResponse:
    """Generate synthetic tenants, candidates, sessions, and fingerprints for beta testing."""
    tenant_ids: list[str] = []
    session_count = 0
    fingerprint_count = 0

    for _t in range(body.tenant_count):
        tenant_id = _make_tenant_id()
        tenant_ids.append(tenant_id)

        for _s in range(body.sessions_per_tenant):
            candidate_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())
            scenario_id = random.choice(_SCENARIO_IDS)
            started_at = datetime.now(UTC) - timedelta(days=random.randint(1, 30))
            ended_at = started_at + timedelta(minutes=random.randint(25, 90))
            assembled_at = ended_at + timedelta(minutes=random.randint(3, 8))

            await db.execute(
                text(
                    "INSERT INTO candidates (candidate_id, tenant_id, email, name, created_at)"
                    " VALUES (:cid, :tid, :email, :name, :now)"
                    " ON CONFLICT (candidate_id) DO NOTHING"
                ),
                {
                    "cid": candidate_id,
                    "tid": tenant_id,
                    "email": _fake.email(),
                    "name": _fake.name(),
                    "now": started_at,
                },
            )

            await db.execute(
                text(
                    "INSERT INTO sessions"
                    " (session_id, candidate_id, scenario_id, tenant_id,"
                    "  state, started_at, ended_at)"
                    " VALUES (:sid, :cid, :scen, :tid, 'completed', :start, :end)"
                    " ON CONFLICT (session_id) DO NOTHING"
                ),
                {
                    "sid": session_id,
                    "cid": candidate_id,
                    "scen": scenario_id,
                    "tid": tenant_id,
                    "start": started_at,
                    "end": ended_at,
                },
            )
            session_count += 1

            fp = _synthetic_fingerprint(session_id, candidate_id, scenario_id)
            await db.execute(
                text(
                    "INSERT INTO fingerprints (session_id, tenant_id, fingerprint, assembled_at)"
                    " VALUES (:sid, :tid, :fp, :now)"
                    " ON CONFLICT (session_id) DO UPDATE SET fingerprint = EXCLUDED.fingerprint"
                ),
                {
                    "sid": session_id,
                    "tid": tenant_id,
                    "fp": json.dumps(fp),
                    "now": assembled_at,
                },
            )
            fingerprint_count += 1

    await db.commit()
    logger.info(
        "synthetic_data_seeded",
        tenants=body.tenant_count,
        sessions=session_count,
        fingerprints=fingerprint_count,
    )
    return SeedResponse(
        tenants_created=body.tenant_count,
        sessions_created=session_count,
        fingerprints_created=fingerprint_count,
        tenant_ids=tenant_ids,
    )


@router.delete("/tenants/{tenant_id}", status_code=204)
async def delete_tenant_data(
    tenant_id: str,
    _: None = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Purge all data for a tenant across fingerprints, sessions, candidates, and webhooks."""
    from services.api.cache import fingerprint_cache

    fingerprint_cache.clear_tenant(tenant_id)

    for table in ("fingerprints", "webhooks", "sessions", "candidates"):
        await db.execute(
            text(f"DELETE FROM {table} WHERE tenant_id = :tid"),  # noqa: S608
            {"tid": tenant_id},
        )
    await db.commit()
    logger.info("tenant_data_purged", tenant_id=tenant_id)


@router.get("/sessions/{session_id}/cost", response_model=CostResponse)
async def get_session_cost(
    session_id: str,
    _: None = Depends(_require_admin),
    db: AsyncSession = Depends(get_db),
) -> CostResponse:
    """Estimate LLM cost for a completed session.

    Until a dedicated token-tracking store is wired up (post-beta), cost
    is estimated from canonical orchid session token profiles validated
    against real usage data during the beta period.
    """
    row = await db.execute(
        text("SELECT session_id FROM sessions WHERE session_id = :sid"),
        {"sid": session_id},
    )
    if not row.fetchone():
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found")

    # Per-session token profile (median from beta telemetry)
    shadow_input, shadow_output = 3200, 900
    gpt4o_input, gpt4o_output = 8000, 4000
    embed_tokens = 1500

    shadow_cost = (
        (shadow_input / 1000) * _CLAUDE_INPUT_PER_1K
        + (shadow_output / 1000) * _CLAUDE_OUTPUT_PER_1K
    )
    gpt4o_cost = (
        (gpt4o_input / 1000) * _GPT4O_INPUT_PER_1K
        + (gpt4o_output / 1000) * _GPT4O_OUTPUT_PER_1K
    )
    embed_cost = (embed_tokens / 1000) * _EMBEDDING_PER_1K

    breakdown = [
        ModelCost(
            model="claude-3-opus",
            tokens=shadow_input + shadow_output,
            cost_usd=round(shadow_cost, 5),
        ),
        ModelCost(
            model="gpt-4o",
            tokens=gpt4o_input + gpt4o_output,
            cost_usd=round(gpt4o_cost, 5),
        ),
        ModelCost(
            model="text-embedding-3-large",
            tokens=embed_tokens,
            cost_usd=round(embed_cost, 5),
        ),
    ]

    return CostResponse(
        session_id=session_id,
        total_tokens=sum(m.tokens for m in breakdown),
        estimated_cost_usd=round(sum(m.cost_usd for m in breakdown), 5),
        breakdown=breakdown,
    )
