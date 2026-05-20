"""Demo endpoint — issues a pre-seeded JWT for the 'demo' tenant.

Hit GET /auth/demo-token from the dashboard login page to skip manual
token entry during demos and sales calls. Seeds 4 synthetic sessions the
first time it is called; idempotent on repeat calls.
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from faker import Faker
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.api.auth import create_access_token
from services.api.dependencies import get_db

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_DEMO_TENANT = "demo"
_DEMO_ADMIN_KEY = "demo-admin-key"
_DEMO_SESSIONS = 4
_SCENARIO_IDS = ["corrupted-warehouse-v1", "silent-pipeline-v1"]
_STYLE_CLUSTERS = ["architect", "executor", "debugger", "delegator"]
_AGENTS = ["DELTA", "NOVA", "ECHO"]
_fake = Faker()
Faker.seed(42)  # reproducible demo names/emails


class DemoTokenResponse(BaseModel):
    token: str
    tenant_id: str
    seeded: bool
    admin_key: str


def _make_fingerprint(session_id: str, candidate_id: str, scenario_id: str) -> dict:  # type: ignore[type-arg]
    rng = random.Random(session_id)  # stable per session_id for repeatability
    style = rng.choice(_STYLE_CLUSTERS)
    return {
        "session_id": session_id,
        "candidate_id": candidate_id,
        "scenario_id": scenario_id,
        "scores": {
            "efficiency_ratio": round(rng.uniform(0.55, 0.92), 3),
            "trust_calibration": round(rng.uniform(0.48, 0.91), 3),
            "correction_velocity": round(rng.uniform(0.60, 0.97), 3),
            "decomposition_score": round(rng.uniform(0.50, 0.88), 3),
            "chaos_resilience": round(rng.uniform(0.42, 0.85), 3),
        },
        "style_cluster": style,
        "reasoning_trace": [
            "Candidate decomposed the data quality task into three sub-problems before delegating.",
            "DELTA corrected twice on column naming — candidate caught both hallucinations fast.",
            "Task handoff to ECHO was precise; schema proposal accepted with one modification.",
            "Chaos event (Kafka lag) handled within 90 seconds — above median resilience.",
        ],
        "interaction_graph": {
            "nodes": [
                {"id": "human", "label": "Candidate", "node_type": "human"},
                *[{"id": a, "label": a, "node_type": "agent", "agent_name": a} for a in _AGENTS],
            ],
            "edges": [
                {
                    "source": "human",
                    "target": a,
                    "message_count": rng.randint(3, 12),
                    "correction_count": rng.randint(0, 3),
                    "avg_latency_ms": rng.randint(700, 2200),
                }
                for a in _AGENTS
            ]
            + [
                {
                    "source": a,
                    "target": "human",
                    "message_count": rng.randint(3, 10),
                    "correction_count": 0,
                    "avg_latency_ms": rng.randint(700, 2200),
                }
                for a in _AGENTS
            ],
        },
        "benchmark_delta": round(rng.uniform(0.08, 0.38), 3),
        "report_markdown": (
            f"## Orchestration Assessment — {style.title()} Profile\n\n"
            f"This candidate demonstrated a **{style}** leadership style across the "
            f"`{scenario_id}` scenario. Key signals: rapid hallucination detection, "
            f"structured task decomposition, and above-average chaos resilience.\n\n"
            f"**Efficiency ratio** places this candidate in the top 30% of beta cohort."
        ),
    }


async def _seed_demo(db: AsyncSession) -> bool:
    """Insert demo sessions if the demo tenant has none. Returns True if seeded."""
    existing = await db.execute(
        text("SELECT COUNT(*) FROM sessions WHERE tenant_id = :tid"),
        {"tid": _DEMO_TENANT},
    )
    if (existing.scalar() or 0) >= _DEMO_SESSIONS:
        return False

    names = ["Alex Rivera", "Jordan Kim", "Sam Okafor", "Morgan Ellis"]
    for i in range(_DEMO_SESSIONS):
        candidate_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"demo-candidate-{i}"))
        session_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"demo-session-{i}"))
        scenario_id = _SCENARIO_IDS[i % len(_SCENARIO_IDS)]
        started_at = datetime.now(UTC) - timedelta(days=_DEMO_SESSIONS - i, hours=i * 2)
        ended_at = started_at + timedelta(minutes=45 + i * 8)
        assembled_at = ended_at + timedelta(minutes=4)

        await db.execute(
            text(
                "INSERT INTO candidates (candidate_id, tenant_id, email, name, created_at)"
                " VALUES (:cid, :tid, :email, :name, :now)"
                " ON CONFLICT (candidate_id) DO NOTHING"
            ),
            {
                "cid": candidate_id,
                "tid": _DEMO_TENANT,
                "email": f"{names[i].lower().replace(' ', '.')}@demo.orchid.ai",
                "name": names[i],
                "now": started_at,
            },
        )

        await db.execute(
            text(
                "INSERT INTO sessions"
                " (session_id, candidate_id, scenario_id, tenant_id, state, started_at, ended_at)"
                " VALUES (:sid, :cid, :scen, :tid, 'completed', :start, :end)"
                " ON CONFLICT (session_id) DO NOTHING"
            ),
            {
                "sid": session_id,
                "cid": candidate_id,
                "scen": scenario_id,
                "tid": _DEMO_TENANT,
                "start": started_at,
                "end": ended_at,
            },
        )

        fp = _make_fingerprint(session_id, candidate_id, scenario_id)
        await db.execute(
            text(
                "INSERT INTO fingerprints (session_id, tenant_id, fingerprint, assembled_at)"
                " VALUES (:sid, :tid, :fp, :now)"
                " ON CONFLICT (session_id) DO UPDATE SET fingerprint = EXCLUDED.fingerprint"
            ),
            {
                "sid": session_id,
                "tid": _DEMO_TENANT,
                "fp": json.dumps(fp),
                "now": assembled_at,
            },
        )

    await db.commit()
    logger.info("demo_tenant_seeded", sessions=_DEMO_SESSIONS)
    return True


@router.get("/demo-token", response_model=DemoTokenResponse)
async def get_demo_token(db: AsyncSession = Depends(get_db)) -> DemoTokenResponse:
    """Issue a signed JWT for the 'demo' tenant and seed it with synthetic data.

    No authentication required — safe for public demo environments.
    Idempotent: calling it multiple times will not duplicate data.
    """
    seeded = await _seed_demo(db)
    token = create_access_token(_DEMO_TENANT)
    logger.info("demo_token_issued", tenant_id=_DEMO_TENANT, seeded=seeded)
    return DemoTokenResponse(token=token, tenant_id=_DEMO_TENANT, seeded=seeded, admin_key=_DEMO_ADMIN_KEY)
