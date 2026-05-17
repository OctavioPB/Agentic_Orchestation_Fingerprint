"""Locust load test: 50 concurrent session creation requests, p99 < 2s.

Run:
    locust -f tests/load/locustfile.py --headless -u 50 -r 10 --run-time 30s \
           --host http://localhost:8000

The test passes if no assertion errors appear in the console output.
Latency assertions are checked in test_session_creation.py using asyncio.
"""
from __future__ import annotations

from locust import HttpUser, between, task


class SessionCreationUser(HttpUser):
    """Simulates a hiring platform creating assessment sessions."""

    wait_time = between(0.1, 0.5)

    @task
    def create_session(self) -> None:
        self.client.post(
            "/sessions",
            json={
                "candidate_id": "load-test-candidate",
                "scenario_id": "corrupted_warehouse_v1",
                "tenant_id": "load-test-tenant",
            },
            name="/sessions [POST]",
        )
