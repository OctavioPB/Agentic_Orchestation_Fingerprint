"""Integration test: full provision → teardown lifecycle via the orchid API.

Uses ``httpx.ASGITransport`` so no running server is needed. Kafka and Postgres
fail silently via the existing best-effort try/except patterns in the API.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from services.orchestrator.scenario_engine import ScenarioEngine


def _make_client_and_engine() -> tuple[httpx.AsyncClient, ScenarioEngine]:
    from services.api.main import app  # noqa: PLC0415

    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    engine = ScenarioEngine(
        api_base_url="http://testserver",
        http_client=client,
    )
    return client, engine


@pytest.mark.integration
class TestScenarioLifecycle:
    def test_provision_returns_active_session(self) -> None:
        async def _run() -> None:
            client, engine = _make_client_and_engine()
            async with client:
                result = await engine.provision(
                    scenario_id="scenario_corrupted_warehouse_v1",
                    candidate_id="cand_integ_001",
                )
            assert result.session_id.startswith("sess_")
            assert result.state == "ACTIVE"
            assert result.scenario_id == "scenario_corrupted_warehouse_v1"
            assert result.config.violations_count == 8

        asyncio.run(_run())

    def test_teardown_completes_session(self) -> None:
        async def _run() -> None:
            client, engine = _make_client_and_engine()
            async with client:
                provision = await engine.provision(
                    scenario_id="scenario_corrupted_warehouse_v1",
                    candidate_id="cand_integ_002",
                )
                teardown = await engine.teardown(session_id=provision.session_id)

            assert teardown.session_id == provision.session_id
            assert teardown.state == "COMPLETED"
            assert teardown.duration_sec >= 0.0

        asyncio.run(_run())

    def test_full_lifecycle_silent_pipeline(self) -> None:
        async def _run() -> None:
            client, engine = _make_client_and_engine()
            async with client:
                provision = await engine.provision(
                    scenario_id="scenario_silent_pipeline_v1",
                    candidate_id="cand_integ_003",
                )
                assert provision.config.violations_count == 3
                assert provision.config.chaos_config.type == "CORRUPT_SCHEMA"

                teardown = await engine.teardown(session_id=provision.session_id)
                assert teardown.state == "COMPLETED"

        asyncio.run(_run())

    def test_teardown_archives_log(self) -> None:
        import tempfile  # noqa: PLC0415

        async def _run(archive_dir: Path) -> str | None:
            client, engine = _make_client_and_engine()
            async with client:
                provision = await engine.provision(
                    scenario_id="scenario_corrupted_warehouse_v1",
                    candidate_id="cand_integ_004",
                )
                teardown = await engine.teardown(
                    session_id=provision.session_id,
                    archive_dir=archive_dir,
                )
            return teardown.archived_log_path

        with tempfile.TemporaryDirectory() as tmp:
            archived = asyncio.run(_run(Path(tmp)))
            assert archived is not None
            assert Path(archived).exists()

    def test_provision_config_matches_json_file(self) -> None:
        async def _run() -> None:
            client, engine = _make_client_and_engine()
            async with client:
                result = await engine.provision(
                    scenario_id="scenario_corrupted_warehouse_v1",
                    candidate_id="cand_integ_005",
                )
            assert result.config.chaos_config.type == "KILL_CONSUMER"
            assert result.config.chaos_config.trigger_at_sec == 1800
            assert result.config.expected_resolution_steps == 6

        asyncio.run(_run())
