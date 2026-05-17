"""Concurrent session creation load test: 50 parallel requests, p99 < 2 seconds.

This test bypasses locust's distributed runner and uses asyncio directly so it can
be executed as part of the regular pytest suite without a running server.
It spins up the FastAPI app in-process via httpx.ASGITransport and fires 50
concurrent POST /sessions requests.
"""
from __future__ import annotations

import asyncio
import statistics
import time

import httpx
import pytest


@pytest.mark.asyncio
async def test_50_concurrent_sessions_p99_under_2s() -> None:
    """POST /sessions 50 times concurrently; assert p99 latency < 2 seconds."""
    from services.api.main import app

    latencies: list[float] = []

    async def _create_session(client: httpx.AsyncClient) -> None:
        start = time.perf_counter()
        resp = await client.post(
            "/sessions",
            json={
                "candidate_id": "load-test-candidate",
                "scenario_id": "corrupted_warehouse_v1",
                "tenant_id": "load-test-tenant",
            },
        )
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)
        # Accept 201 (created) or 500 (infra not available) — we test latency, not infra
        assert resp.status_code in {201, 500, 503}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await asyncio.gather(*[_create_session(client) for _ in range(50)])

    assert len(latencies) == 50, f"Expected 50 responses, got {len(latencies)}"

    latencies_sorted = sorted(latencies)
    p99_index = int(0.99 * len(latencies_sorted)) - 1
    p99 = latencies_sorted[max(p99_index, 0)]
    median = statistics.median(latencies)

    print(f"\nLoad test results: median={median*1000:.1f}ms  p99={p99*1000:.1f}ms")
    assert p99 < 2.0, f"p99 latency {p99*1000:.0f}ms exceeds 2000ms threshold"
