"""Standalone synthetic data generator for orchid beta testing.

Generates realistic enterprise tenant + candidate + session + fingerprint
data and writes it to data/synthetic/ as JSON fixtures. Can also POST
directly to a running API via the admin endpoint.

Usage:
    python data/synthetic/seed_generator.py                      # write JSON fixtures
    python data/synthetic/seed_generator.py --api http://localhost:8000  # POST to API
    python data/synthetic/seed_generator.py --tenants 5 --sessions 3
"""
from __future__ import annotations

import argparse
import json
import os
import random
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

try:
    from faker import Faker
except ImportError:
    raise SystemExit("Run: pip install faker")  # noqa: B904

_fake = Faker()
_SCENARIO_IDS = ["corrupted-warehouse-v1", "silent-pipeline-v1"]
_STYLE_CLUSTERS = ["architect", "executor", "debugger", "delegator"]
_AGENTS = ["DELTA", "NOVA", "ECHO"]

# Three pre-defined beta enterprise clients (deterministic IDs for docs/demos)
BETA_CLIENTS = [
    {"tenant_id": "tenant-apex-capital-beta", "company": "Apex Capital Partners"},
    {"tenant_id": "tenant-meridian-ventures", "company": "Meridian Ventures Group"},
    {"tenant_id": "tenant-techscale-ai", "company": "TechScale AI Solutions"},
]


def _make_scores() -> dict[str, float]:
    return {
        "efficiency_ratio": round(random.uniform(0.45, 0.95), 3),
        "trust_calibration": round(random.uniform(0.40, 0.92), 3),
        "correction_velocity": round(random.uniform(0.55, 0.98), 3),
        "decomposition_score": round(random.uniform(0.38, 0.88), 3),
        "chaos_resilience": round(random.uniform(0.30, 0.85), 3),
    }


def _make_interaction_graph() -> dict:  # type: ignore[type-arg]
    return {
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
    }


def generate_session(tenant_id: str, company: str) -> dict:  # type: ignore[type-arg]
    """Return a complete synthetic session fixture."""
    candidate_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    scenario_id = random.choice(_SCENARIO_IDS)
    style = random.choice(_STYLE_CLUSTERS)
    started_at = datetime.now(UTC) - timedelta(days=random.randint(1, 30))
    ended_at = started_at + timedelta(minutes=random.randint(25, 90))
    assembled_at = ended_at + timedelta(minutes=random.randint(3, 8))

    return {
        "tenant_id": tenant_id,
        "company": company,
        "candidate": {
            "candidate_id": candidate_id,
            "email": _fake.email(),
            "name": _fake.name(),
            "created_at": started_at.isoformat(),
        },
        "session": {
            "session_id": session_id,
            "candidate_id": candidate_id,
            "scenario_id": scenario_id,
            "tenant_id": tenant_id,
            "state": "completed",
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
        },
        "fingerprint": {
            "session_id": session_id,
            "candidate_id": candidate_id,
            "scenario_id": scenario_id,
            "scores": _make_scores(),
            "style_cluster": style,
            "reasoning_trace": [_fake.sentence() for _ in range(random.randint(4, 7))],
            "interaction_graph": _make_interaction_graph(),
            "benchmark_delta": round(random.uniform(0.05, 0.45), 3),
            "report_markdown": (
                f"## Assessment Report — {company}\n\n"
                f"Candidate demonstrated a **{style}** leadership profile "
                f"across the `{scenario_id}` scenario.\n\n"
                f"{_fake.sentence()} {_fake.sentence()}"
            ),
            "assembled_at": assembled_at.isoformat(),
        },
    }


def generate_corpus(tenant_count: int = 3, sessions_per_tenant: int = 2) -> list[dict]:  # type: ignore[type-arg]
    """Generate a full synthetic corpus."""
    fixtures = []
    clients = BETA_CLIENTS[:tenant_count] if tenant_count <= len(BETA_CLIENTS) else [
        *BETA_CLIENTS,
        *[
            {
                "tenant_id": f"tenant-{_fake.company().lower().replace(' ', '-')[:20]}-{uuid.uuid4().hex[:6]}",
                "company": _fake.company(),
            }
            for _ in range(tenant_count - len(BETA_CLIENTS))
        ],
    ]
    for client in clients:
        for _ in range(sessions_per_tenant):
            fixtures.append(generate_session(client["tenant_id"], client["company"]))
    return fixtures


def write_fixtures(fixtures: list[dict], out_dir: Path) -> None:  # type: ignore[type-arg]
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, fixture in enumerate(fixtures):
        path = out_dir / f"beta_session_{i + 1:03d}.json"
        path.write_text(json.dumps(fixture, indent=2, default=str))
        print(f"  Written: {path}")


def post_to_api(fixtures: list[dict], api_url: str, admin_key: str) -> None:  # type: ignore[type-arg]
    try:
        import httpx
    except ImportError:
        raise SystemExit("Run: pip install httpx")  # noqa: B904

    headers = {"X-Admin-Key": admin_key, "Content-Type": "application/json"}
    tenant_counts = {f["tenant_id"] for f in fixtures}
    resp = httpx.post(
        f"{api_url}/admin/seed",
        json={"tenant_count": len(tenant_counts), "sessions_per_tenant": 2},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    print(f"  Seeded via API: {result}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate orchid synthetic beta data")
    parser.add_argument("--tenants", type=int, default=3)
    parser.add_argument("--sessions", type=int, default=2)
    parser.add_argument("--api", type=str, default=None, help="POST to a live API base URL")
    parser.add_argument(
        "--admin-key",
        type=str,
        default=os.getenv("ADMIN_SECRET_KEY", "dev-admin-secret"),
    )
    parser.add_argument("--out", type=str, default="data/synthetic/beta")
    args = parser.parse_args()

    print(f"Generating {args.tenants} tenants × {args.sessions} sessions each…")
    corpus = generate_corpus(args.tenants, args.sessions)

    if args.api:
        print(f"Posting to {args.api}…")
        post_to_api(corpus, args.api, args.admin_key)
    else:
        out_path = Path(args.out)
        print(f"Writing fixtures to {out_path}/…")
        write_fixtures(corpus, out_path)

    print(f"Done — {len(corpus)} sessions generated.")
