"""Airflow DAG: orchid_scenario_teardown

Thin wrapper — all orchestration logic lives in services/orchestrator/scenario_engine.py.

Trigger parameters:
    session_id   (str)  — session to tear down
    archive_dir  (str)  — optional directory to archive the session JSON log

Example CLI trigger:
    airflow dags trigger orchid_scenario_teardown \\
        --conf '{"session_id":"sess_abc123"}'
"""

import asyncio
import os
from pathlib import Path

from airflow.decorators import dag, task
from airflow.utils.dates import days_ago

_API_BASE_URL = os.getenv("ORCHID_API_BASE_URL", "http://api:8000")


@dag(
    dag_id="orchid_scenario_teardown",
    schedule=None,
    start_date=days_ago(1),
    catchup=False,
    tags=["orchid", "scenario", "teardown"],
    params={
        "session_id": "",
        "archive_dir": "",
    },
)
def orchid_scenario_teardown() -> None:
    """Tears down an orchid assessment session and optionally archives its log."""

    @task()
    def teardown_session(**context: object) -> dict:
        from services.orchestrator.scenario_engine import ScenarioEngine  # noqa: PLC0415

        params = context["params"]
        session_id: str = params["session_id"]
        archive_dir_str: str = params.get("archive_dir", "")

        archive_dir = Path(archive_dir_str) if archive_dir_str else None
        engine = ScenarioEngine(api_base_url=_API_BASE_URL)
        result = asyncio.run(engine.teardown(session_id, archive_dir=archive_dir))

        return {
            "session_id": result.session_id,
            "state": result.state,
            "ended_at": result.ended_at.isoformat(),
            "duration_sec": result.duration_sec,
            "archived_log_path": result.archived_log_path,
        }

    teardown_session()


orchid_scenario_teardown()
