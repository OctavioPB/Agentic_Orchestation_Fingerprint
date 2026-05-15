"""Airflow DAG: orchid_scenario_provision

Thin wrapper — all orchestration logic lives in services/orchestrator/scenario_engine.py.

Trigger parameters (pass via the Airflow UI or API):
    scenario_id  (str)  — e.g. "scenario_corrupted_warehouse_v1"
    candidate_id (str)  — unique candidate identifier
    tenant_id    (str)  — defaults to "default"

Example CLI trigger:
    airflow dags trigger orchid_scenario_provision \\
        --conf '{"scenario_id":"scenario_corrupted_warehouse_v1","candidate_id":"cand_001"}'
"""

import asyncio
import os

from airflow.decorators import dag, task
from airflow.utils.dates import days_ago

_API_BASE_URL = os.getenv("ORCHID_API_BASE_URL", "http://api:8000")


@dag(
    dag_id="orchid_scenario_provision",
    schedule=None,
    start_date=days_ago(1),
    catchup=False,
    tags=["orchid", "scenario", "provision"],
    params={
        "scenario_id": "scenario_corrupted_warehouse_v1",
        "candidate_id": "cand_unknown",
        "tenant_id": "default",
    },
)
def orchid_scenario_provision() -> None:
    """Provisions a new orchid assessment session."""

    @task()
    def provision_session(**context: object) -> dict:
        from services.orchestrator.scenario_engine import ScenarioEngine  # noqa: PLC0415

        params = context["params"]
        scenario_id: str = params["scenario_id"]
        candidate_id: str = params["candidate_id"]
        tenant_id: str = params.get("tenant_id", "default")

        engine = ScenarioEngine(api_base_url=_API_BASE_URL)
        result = asyncio.run(engine.provision(scenario_id, candidate_id, tenant_id))

        return {
            "session_id": result.session_id,
            "scenario_id": result.scenario_id,
            "state": result.state,
            "started_at": result.started_at.isoformat(),
        }

    provision_session()


orchid_scenario_provision()
