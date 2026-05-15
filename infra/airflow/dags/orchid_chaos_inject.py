"""Airflow DAG: orchid_chaos_inject

Waits until the configured trigger time, emits CHAOS_INJECTED to Kafka, then
executes the fault inside the sandbox container via Docker exec.

All logic lives in services/orchestrator/chaos_engine.py. This DAG is a thin
wrapper, consistent with the Airflow principle: DAG files contain only DAG
definition (CLAUDE.md §5.3).

Trigger parameters:
    session_id    (str)  — active session identifier
    scenario_id   (str)  — used to load ChaosConfig from scenario config JSON
    container_id  (str)  — Docker container running the sandbox
    started_at    (str)  — ISO 8601 UTC timestamp of when the session started;
                           used to compute how long to wait before injecting

Example trigger:
    airflow dags trigger orchid_chaos_inject \\
        --conf '{
            "session_id": "sess_abc123",
            "scenario_id": "scenario_corrupted_warehouse_v1",
            "container_id": "orchid-sandbox-sess_abc123",
            "started_at": "2026-05-15T10:00:00+00:00"
        }'
"""

import asyncio
import os
from datetime import UTC, datetime

from airflow.decorators import dag, task
from airflow.utils.dates import days_ago

_API_BASE_URL = os.getenv("ORCHID_API_BASE_URL", "http://api:8000")


@dag(
    dag_id="orchid_chaos_inject",
    schedule=None,
    start_date=days_ago(1),
    catchup=False,
    tags=["orchid", "chaos"],
    params={
        "session_id": "",
        "scenario_id": "",
        "container_id": "",
        "started_at": "",
    },
)
def orchid_chaos_inject() -> None:
    """Injects a fault into a live assessment session at the configured time."""

    @task()
    def wait_and_inject(**context: object) -> dict:
        from services.orchestrator.chaos_engine import ChaosEngine  # noqa: PLC0415
        from services.orchestrator.scenario_engine import ScenarioEngine  # noqa: PLC0415

        params = context["params"]
        session_id: str = params["session_id"]
        scenario_id: str = params["scenario_id"]
        container_id: str = params["container_id"]
        started_at_str: str = params["started_at"]

        started_at = datetime.fromisoformat(started_at_str)
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)

        config = ScenarioEngine(api_base_url=_API_BASE_URL).load_config(scenario_id)
        engine = ChaosEngine()

        result = asyncio.run(
            engine.execute(
                session_id=session_id,
                chaos_config=config.chaos_config,
                started_at=started_at,
                container_id=container_id,
            )
        )

        return {
            "session_id": result.session_id,
            "chaos_type": result.chaos_type,
            "kafka_emitted_at": result.kafka_emitted_at.isoformat(),
            "executed_at": result.executed_at.isoformat(),
            "outcome": result.outcome,
            "detail": result.detail,
        }

    wait_and_inject()


orchid_chaos_inject()
