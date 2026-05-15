"""Unit tests for ScenarioEngine — no running server or Docker required."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from services.orchestrator.scenario_engine import (
    ChaosConfig,
    ProvisionResult,
    ScenarioConfig,
    ScenarioEngine,
    TeardownResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_CONFIG: dict = {
    "scenario_id": "test_scenario_v1",
    "name": "Test Scenario",
    "version": "v1",
    "description": "A minimal test scenario.",
    "chaos_config": {
        "type": "KILL_CONSUMER",
        "trigger_at_sec": 300,
        "target": "kafka-consumer",
        "params": {"signal": "SIGKILL"},
    },
    "sandbox_image": "orchid-sandbox:latest",
    "scenario_env": {"SCENARIO_ID": "test_scenario_v1"},
    "expected_resolution_steps": 4,
    "ai_solo_baseline_path": "data/scenarios/agents/baseline/test_ai_solo.json",
    "max_duration_sec": 3600,
    "workspace_dir": "workspace_test",
    "violations_count": 2,
}


def _write_config(directory: Path, cfg: dict) -> None:
    scenario_id = cfg["scenario_id"]
    (directory / f"{scenario_id}.json").write_text(json.dumps(cfg), encoding="utf-8")


# ---------------------------------------------------------------------------
# ChaosConfig validation
# ---------------------------------------------------------------------------


class TestChaosConfig:
    def test_required_fields(self) -> None:
        cc = ChaosConfig(
            type="KILL_CONSUMER",
            trigger_at_sec=1800,
            target="kafka-consumer-process",
        )
        assert cc.type == "KILL_CONSUMER"
        assert cc.trigger_at_sec == 1800
        assert cc.params == {}

    def test_params_populated(self) -> None:
        cc = ChaosConfig(
            type="CORRUPT_SCHEMA",
            trigger_at_sec=1200,
            target="qdrant-collection",
            params={"drop_field": "session_id"},
        )
        assert cc.params["drop_field"] == "session_id"

    def test_default_params_is_empty_dict(self) -> None:
        cc = ChaosConfig(type="X", trigger_at_sec=0, target="y")
        assert isinstance(cc.params, dict)
        assert len(cc.params) == 0


# ---------------------------------------------------------------------------
# ScenarioConfig validation
# ---------------------------------------------------------------------------


class TestScenarioConfig:
    def test_valid_config_parses(self) -> None:
        cfg = ScenarioConfig.model_validate(_VALID_CONFIG)
        assert cfg.scenario_id == "test_scenario_v1"
        assert cfg.violations_count == 2
        assert isinstance(cfg.chaos_config, ChaosConfig)

    def test_chaos_config_nested(self) -> None:
        cfg = ScenarioConfig.model_validate(_VALID_CONFIG)
        assert cfg.chaos_config.type == "KILL_CONSUMER"
        assert cfg.chaos_config.trigger_at_sec == 300

    def test_default_sandbox_image(self) -> None:
        minimal = dict(_VALID_CONFIG)
        del minimal["sandbox_image"]
        cfg = ScenarioConfig.model_validate(minimal)
        assert cfg.sandbox_image == "orchid-sandbox:latest"

    def test_default_scenario_env(self) -> None:
        minimal = dict(_VALID_CONFIG)
        del minimal["scenario_env"]
        cfg = ScenarioConfig.model_validate(minimal)
        assert cfg.scenario_env == {}

    def test_real_corrupted_warehouse_config(self) -> None:
        config_path = (
            Path(__file__).parent.parent.parent
            / "data"
            / "scenarios"
            / "v1"
            / "configs"
            / "scenario_corrupted_warehouse_v1.json"
        )
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        cfg = ScenarioConfig.model_validate(raw)
        assert cfg.scenario_id == "scenario_corrupted_warehouse_v1"
        assert cfg.violations_count == 8
        assert cfg.chaos_config.type == "KILL_CONSUMER"

    def test_real_silent_pipeline_config(self) -> None:
        config_path = (
            Path(__file__).parent.parent.parent
            / "data"
            / "scenarios"
            / "v1"
            / "configs"
            / "scenario_silent_pipeline_v1.json"
        )
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        cfg = ScenarioConfig.model_validate(raw)
        assert cfg.scenario_id == "scenario_silent_pipeline_v1"
        assert cfg.violations_count == 3
        assert cfg.chaos_config.type == "CORRUPT_SCHEMA"
        assert cfg.chaos_config.trigger_at_sec == 1200


# ---------------------------------------------------------------------------
# ScenarioEngine.load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_load_valid_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            _write_config(d, _VALID_CONFIG)
            engine = ScenarioEngine(scenarios_dir=d)
            cfg = engine.load_config("test_scenario_v1")
            assert cfg.scenario_id == "test_scenario_v1"
            assert cfg.name == "Test Scenario"

    def test_missing_config_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = ScenarioEngine(scenarios_dir=Path(tmp))
            with pytest.raises(FileNotFoundError, match="no_such_scenario"):
                engine.load_config("no_such_scenario")

    def test_load_returns_scenario_config_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            _write_config(d, _VALID_CONFIG)
            engine = ScenarioEngine(scenarios_dir=d)
            cfg = engine.load_config("test_scenario_v1")
            assert isinstance(cfg, ScenarioConfig)

    def test_load_real_scenarios(self) -> None:
        engine = ScenarioEngine()
        cfg_v1 = engine.load_config("scenario_corrupted_warehouse_v1")
        cfg_v2 = engine.load_config("scenario_silent_pipeline_v1")
        assert cfg_v1.violations_count == 8
        assert cfg_v2.violations_count == 3


# ---------------------------------------------------------------------------
# ScenarioEngine._compute_duration
# ---------------------------------------------------------------------------


class TestComputeDuration:
    def test_same_time_is_zero(self) -> None:
        engine = ScenarioEngine()
        t = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert engine._compute_duration(t, t) == 0.0

    def test_one_minute(self) -> None:
        engine = ScenarioEngine()
        t0 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        t1 = datetime(2024, 1, 1, 12, 1, 0, tzinfo=UTC)
        assert engine._compute_duration(t0, t1) == 60.0

    def test_result_is_positive(self) -> None:
        engine = ScenarioEngine()
        t0 = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        t1 = datetime(2024, 1, 1, 10, 30, 45, tzinfo=UTC)
        assert engine._compute_duration(t0, t1) > 0


# ---------------------------------------------------------------------------
# ProvisionResult and TeardownResult construction
# ---------------------------------------------------------------------------


class TestProvisionResult:
    def test_construction(self) -> None:
        cfg = ScenarioConfig.model_validate(_VALID_CONFIG)
        result = ProvisionResult(
            session_id="sess_001",
            scenario_id="test_scenario_v1",
            state="ACTIVE",
            started_at=datetime(2024, 1, 1, tzinfo=UTC),
            config=cfg,
        )
        assert result.session_id == "sess_001"
        assert result.state == "ACTIVE"
        assert result.config.violations_count == 2

    def test_config_is_scenario_config(self) -> None:
        cfg = ScenarioConfig.model_validate(_VALID_CONFIG)
        result = ProvisionResult(
            session_id="sess_002",
            scenario_id="test_scenario_v1",
            state="ACTIVE",
            started_at=datetime.now(UTC),
            config=cfg,
        )
        assert isinstance(result.config, ScenarioConfig)


class TestTeardownResult:
    def test_construction_without_archive(self) -> None:
        result = TeardownResult(
            session_id="sess_001",
            state="COMPLETED",
            ended_at=datetime.now(UTC),
            duration_sec=1234.5,
        )
        assert result.archived_log_path is None

    def test_construction_with_archive(self) -> None:
        result = TeardownResult(
            session_id="sess_001",
            state="COMPLETED",
            ended_at=datetime.now(UTC),
            duration_sec=900.0,
            archived_log_path="/tmp/sess_001.json",
        )
        assert result.archived_log_path == "/tmp/sess_001.json"

    def test_duration_sec_is_float(self) -> None:
        result = TeardownResult(
            session_id="s",
            state="COMPLETED",
            ended_at=datetime.now(UTC),
            duration_sec=42,
        )
        assert isinstance(result.duration_sec, float)


# ---------------------------------------------------------------------------
# Baseline JSON files are valid
# ---------------------------------------------------------------------------


class TestBaselineFiles:
    _BASELINE_DIR = (
        Path(__file__).parent.parent.parent / "data" / "scenarios" / "agents" / "baseline"
    )

    def test_corrupted_warehouse_baseline_exists(self) -> None:
        assert (self._BASELINE_DIR / "corrupted_warehouse_ai_solo.json").exists()

    def test_silent_pipeline_baseline_exists(self) -> None:
        assert (self._BASELINE_DIR / "silent_pipeline_ai_solo.json").exists()

    def test_corrupted_warehouse_baseline_valid_json(self) -> None:
        path = self._BASELINE_DIR / "corrupted_warehouse_ai_solo.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["scenario_id"] == "scenario_corrupted_warehouse_v1"
        assert data["total_steps"] == 20
        assert data["violations_found"] == 5

    def test_silent_pipeline_baseline_valid_json(self) -> None:
        path = self._BASELINE_DIR / "silent_pipeline_ai_solo.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["scenario_id"] == "scenario_silent_pipeline_v1"
        assert data["total_steps"] == 19
        assert data["violations_fixed"] == 2

    def test_both_baselines_reference_correct_scenario(self) -> None:
        for fname, expected_id in [
            ("corrupted_warehouse_ai_solo.json", "scenario_corrupted_warehouse_v1"),
            ("silent_pipeline_ai_solo.json", "scenario_silent_pipeline_v1"),
        ]:
            data = json.loads((self._BASELINE_DIR / fname).read_text(encoding="utf-8"))
            assert data["scenario_id"] == expected_id

    def test_baseline_steps_lists_are_non_empty(self) -> None:
        for fname in ["corrupted_warehouse_ai_solo.json", "silent_pipeline_ai_solo.json"]:
            data = json.loads((self._BASELINE_DIR / fname).read_text(encoding="utf-8"))
            assert len(data["steps"]) > 0


# ---------------------------------------------------------------------------
# Workspace v2 file existence
# ---------------------------------------------------------------------------


class TestWorkspaceV2:
    _WORKSPACE = (
        Path(__file__).parent.parent.parent / "services" / "sandbox" / "workspace_v2"
    )

    def test_producer_exists(self) -> None:
        assert (self._WORKSPACE / "producer.py").exists()

    def test_qdrant_ingest_exists(self) -> None:
        assert (self._WORKSPACE / "qdrant_ingest.py").exists()

    def test_etl_dag_exists(self) -> None:
        assert (self._WORKSPACE / "etl_dag.py").exists()

    def test_pipeline_run_log_exists(self) -> None:
        assert (self._WORKSPACE / "pipeline_run.log").exists()

    def test_producer_contains_wrong_topic(self) -> None:
        content = (self._WORKSPACE / "producer.py").read_text(encoding="utf-8")
        assert "orchid.sandbox.agent.responses" in content

    def test_qdrant_ingest_contains_wrong_dimension(self) -> None:
        content = (self._WORKSPACE / "qdrant_ingest.py").read_text(encoding="utf-8")
        assert "[0.1, 0.2, 0.3]" in content

    def test_etl_dag_contains_cycle(self) -> None:
        content = (self._WORKSPACE / "etl_dag.py").read_text(encoding="utf-8")
        assert "load_task >> extract_task" in content

    def test_run_log_shows_zero_indexed(self) -> None:
        content = (self._WORKSPACE / "pipeline_run.log").read_text(encoding="utf-8")
        assert "events_indexed=0" in content
