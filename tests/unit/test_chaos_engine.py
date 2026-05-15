"""Unit tests for ChaosEngine and related models — no Docker or Kafka required."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from services.orchestrator.chaos_engine import ChaosEngine, ChaosResult
from services.orchestrator.scenario_engine import ChaosConfig

# ---------------------------------------------------------------------------
# Mock docker exec
# ---------------------------------------------------------------------------


async def _ok_exec(container_id: str, cmd: list[str]) -> tuple[int, str]:
    return 0, f"ok: {' '.join(cmd)}"


async def _fail_exec(container_id: str, cmd: list[str]) -> tuple[int, str]:
    return 2, "error from mock"


async def _pkill_no_match(container_id: str, cmd: list[str]) -> tuple[int, str]:
    return 1, ""  # pkill exit=1 means no process matched — not an error


# ---------------------------------------------------------------------------
# Mock telemetry producer
# ---------------------------------------------------------------------------


class _RecordingProducer:
    """Records emit() calls and their timestamps for ordering assertions."""

    def __init__(self) -> None:
        self.emitted: list[tuple[datetime, object]] = []

    async def emit(self, event: object) -> None:
        self.emitted.append((datetime.now(UTC), event))


# ---------------------------------------------------------------------------
# ChaosResult
# ---------------------------------------------------------------------------


class TestChaosResult:
    def test_success_construction(self) -> None:
        now = datetime.now(UTC)
        result = ChaosResult(
            session_id="sess_001",
            chaos_type="KILL_CONSUMER",
            kafka_emitted_at=now,
            executed_at=now,
            outcome="success",
        )
        assert result.outcome == "success"
        assert result.detail == ""

    def test_error_construction(self) -> None:
        now = datetime.now(UTC)
        result = ChaosResult(
            session_id="sess_001",
            chaos_type="FLOOD_TOPIC",
            kafka_emitted_at=now,
            executed_at=now,
            outcome="error",
            detail="connection refused",
        )
        assert result.outcome == "error"
        assert "connection refused" in result.detail

    def test_kafka_emitted_before_executed(self) -> None:
        t0 = datetime.now(UTC)
        t1 = t0 + timedelta(milliseconds=50)
        result = ChaosResult(
            session_id="s",
            chaos_type="KILL_CONSUMER",
            kafka_emitted_at=t0,
            executed_at=t1,
            outcome="success",
        )
        assert result.kafka_emitted_at <= result.executed_at


# ---------------------------------------------------------------------------
# ChaosEngine._compute_wait_sec
# ---------------------------------------------------------------------------


class TestComputeWaitSec:
    def test_trigger_in_future(self) -> None:
        engine = ChaosEngine()
        started_at = datetime.now(UTC) - timedelta(seconds=10)
        wait = engine._compute_wait_sec(60, started_at)
        assert 48.0 <= wait <= 52.0  # ~50s remaining

    def test_trigger_already_passed(self) -> None:
        engine = ChaosEngine()
        started_at = datetime.now(UTC) - timedelta(seconds=100)
        wait = engine._compute_wait_sec(60, started_at)
        assert wait == 0.0

    def test_trigger_exactly_now(self) -> None:
        engine = ChaosEngine()
        started_at = datetime.now(UTC) - timedelta(seconds=30)
        wait = engine._compute_wait_sec(30, started_at)
        assert wait == 0.0 or wait < 1.0  # tiny positive due to wall-clock drift

    def test_returns_float(self) -> None:
        engine = ChaosEngine()
        started_at = datetime.now(UTC)
        result = engine._compute_wait_sec(100, started_at)
        assert isinstance(result, float)

    def test_zero_trigger_at_sec(self) -> None:
        engine = ChaosEngine()
        started_at = datetime.now(UTC)
        wait = engine._compute_wait_sec(0, started_at)
        assert wait == 0.0


# ---------------------------------------------------------------------------
# ChaosEngine — Kafka emit ordering
# ---------------------------------------------------------------------------


class TestEmitOrdering:
    def test_kafka_emitted_before_fault_executes(self) -> None:
        """kafka_emitted_at must be <= executed_at in the result."""
        producer = _RecordingProducer()
        engine = ChaosEngine(
            telemetry_producer=producer,
            docker_exec=_ok_exec,
        )
        config = ChaosConfig(
            type="KILL_CONSUMER",
            trigger_at_sec=0,
            target="kafka-consumer-process",
            params={"signal": "SIGKILL"},
        )
        started_at = datetime.now(UTC) - timedelta(seconds=10)
        result = asyncio.run(
            engine.execute("sess_001", config, started_at, "container_abc")
        )
        assert result.kafka_emitted_at <= result.executed_at

    def test_emit_called_once(self) -> None:
        producer = _RecordingProducer()
        engine = ChaosEngine(
            telemetry_producer=producer,
            docker_exec=_ok_exec,
        )
        config = ChaosConfig(
            type="KILL_CONSUMER",
            trigger_at_sec=0,
            target="kafka-consumer-process",
        )
        started_at = datetime.now(UTC)
        asyncio.run(engine.execute("sess_002", config, started_at, "ctr"))
        assert len(producer.emitted) == 1

    def test_no_producer_still_executes(self) -> None:
        engine = ChaosEngine(telemetry_producer=None, docker_exec=_ok_exec)
        config = ChaosConfig(
            type="KILL_CONSUMER",
            trigger_at_sec=0,
            target="kafka-consumer-process",
        )
        started_at = datetime.now(UTC)
        result = asyncio.run(engine.execute("sess_003", config, started_at, "ctr"))
        assert result.outcome == "success"


# ---------------------------------------------------------------------------
# KILL_CONSUMER executor
# ---------------------------------------------------------------------------


class TestKillConsumer:
    def test_success(self) -> None:
        engine = ChaosEngine(docker_exec=_ok_exec)
        config = ChaosConfig(
            type="KILL_CONSUMER",
            trigger_at_sec=0,
            target="kafka-consumer-process",
            params={"signal": "SIGKILL"},
        )
        result = asyncio.run(
            engine.execute("sess_k1", config, datetime.now(UTC), "ctr_k")
        )
        assert result.outcome == "success"
        assert result.chaos_type == "KILL_CONSUMER"

    def test_pkill_no_match_is_not_error(self) -> None:
        """pkill exit=1 (no match) must not count as error."""
        engine = ChaosEngine(docker_exec=_pkill_no_match)
        config = ChaosConfig(
            type="KILL_CONSUMER",
            trigger_at_sec=0,
            target="kafka-consumer-process",
        )
        result = asyncio.run(
            engine.execute("sess_k2", config, datetime.now(UTC), "ctr_k2")
        )
        assert result.outcome == "success"

    def test_docker_error_returns_error_outcome(self) -> None:
        engine = ChaosEngine(docker_exec=_fail_exec)
        config = ChaosConfig(
            type="KILL_CONSUMER",
            trigger_at_sec=0,
            target="kafka-consumer-process",
        )
        result = asyncio.run(
            engine.execute("sess_k3", config, datetime.now(UTC), "ctr_k3")
        )
        assert result.outcome == "error"


# ---------------------------------------------------------------------------
# CORRUPT_SCHEMA executor — SQLite path
# ---------------------------------------------------------------------------


class TestCorruptSchemaSqlite:
    def _config(self, extra_params: dict | None = None) -> ChaosConfig:
        params: dict = {"table": "orders", "column": "status"}
        if extra_params:
            params.update(extra_params)
        return ChaosConfig(
            type="CORRUPT_SCHEMA",
            trigger_at_sec=0,
            target="orders_table",
            params=params,
        )

    def test_success(self) -> None:
        engine = ChaosEngine(docker_exec=_ok_exec)
        result = asyncio.run(
            engine.execute("sess_c1", self._config(), datetime.now(UTC), "ctr_c")
        )
        assert result.outcome == "success"
        assert result.chaos_type == "CORRUPT_SCHEMA"

    def test_docker_failure_returns_error(self) -> None:
        engine = ChaosEngine(docker_exec=_fail_exec)
        result = asyncio.run(
            engine.execute("sess_c2", self._config(), datetime.now(UTC), "ctr_c")
        )
        assert result.outcome == "error"

    def test_calls_python3_in_container(self) -> None:
        captured: list[list[str]] = []

        async def _capturing_exec(cid: str, cmd: list[str]) -> tuple[int, str]:
            captured.append(cmd)
            return 0, "ok"

        engine = ChaosEngine(docker_exec=_capturing_exec)
        asyncio.run(
            engine.execute("sess_c3", self._config(), datetime.now(UTC), "ctr_c")
        )
        assert captured[0][0] == "python3"
        assert captured[0][1] == "-c"

    def test_sqlite_code_contains_table_and_column(self) -> None:
        captured: list[list[str]] = []

        async def _capturing_exec(cid: str, cmd: list[str]) -> tuple[int, str]:
            captured.append(cmd)
            return 0, "dropped column status from orders"

        engine = ChaosEngine(docker_exec=_capturing_exec)
        asyncio.run(
            engine.execute(
                "sess_c4",
                self._config({"table": "customers", "column": "email"}),
                datetime.now(UTC),
                "ctr",
            )
        )
        python_code = captured[0][2]
        assert "customers" in python_code
        assert "email" in python_code


# ---------------------------------------------------------------------------
# CORRUPT_SCHEMA — Qdrant path
# ---------------------------------------------------------------------------


class TestCorruptSchemaQdrant:
    def _config(self) -> ChaosConfig:
        return ChaosConfig(
            type="CORRUPT_SCHEMA",
            trigger_at_sec=0,
            target="qdrant-collection",
            params={"drop_field": "session_id"},
        )

    def test_success(self) -> None:
        engine = ChaosEngine(docker_exec=_ok_exec)
        result = asyncio.run(
            engine.execute("sess_q1", self._config(), datetime.now(UTC), "ctr_q")
        )
        assert result.outcome == "success"

    def test_patches_qdrant_ingest(self) -> None:
        captured: list[list[str]] = []

        async def _capturing_exec(cid: str, cmd: list[str]) -> tuple[int, str]:
            captured.append(cmd)
            return 0, "dropped session_id from qdrant_ingest.py"

        engine = ChaosEngine(docker_exec=_capturing_exec)
        asyncio.run(
            engine.execute("sess_q2", self._config(), datetime.now(UTC), "ctr_q")
        )
        python_code = captured[0][2]
        assert "qdrant_ingest.py" in python_code
        assert "session_id" in python_code


# ---------------------------------------------------------------------------
# Unknown chaos type
# ---------------------------------------------------------------------------


class TestUnknownChaosType:
    def test_unknown_type_returns_error_outcome(self) -> None:
        engine = ChaosEngine(docker_exec=_ok_exec)
        config = ChaosConfig(
            type="MAKE_COFFEE",
            trigger_at_sec=0,
            target="coffee-machine",
        )
        result = asyncio.run(
            engine.execute("sess_u1", config, datetime.now(UTC), "ctr_u")
        )
        assert result.outcome == "error"
        assert "MAKE_COFFEE" in result.detail


# ---------------------------------------------------------------------------
# ChaosEngine — real scenario configs
# ---------------------------------------------------------------------------


class TestRealScenarioConfigs:
    def test_corrupted_warehouse_chaos_config_routes_to_kill_consumer(self) -> None:
        from services.orchestrator.scenario_engine import ScenarioEngine  # noqa: PLC0415

        config = ScenarioEngine().load_config("scenario_corrupted_warehouse_v1")
        assert config.chaos_config.type == "KILL_CONSUMER"
        assert config.chaos_config.trigger_at_sec == 1800

    def test_silent_pipeline_chaos_config_routes_to_corrupt_schema(self) -> None:
        from services.orchestrator.scenario_engine import ScenarioEngine  # noqa: PLC0415

        config = ScenarioEngine().load_config("scenario_silent_pipeline_v1")
        assert config.chaos_config.type == "CORRUPT_SCHEMA"
        assert config.chaos_config.target == "qdrant-collection"
        assert config.chaos_config.trigger_at_sec == 1200

    def test_kill_consumer_executes_with_real_config(self) -> None:
        from services.orchestrator.scenario_engine import ScenarioEngine  # noqa: PLC0415

        cfg = ScenarioEngine().load_config("scenario_corrupted_warehouse_v1")
        engine = ChaosEngine(docker_exec=_ok_exec)
        # started_at far enough in the past so trigger_at_sec (1800) already elapsed
        started_at = datetime.now(UTC) - timedelta(seconds=cfg.chaos_config.trigger_at_sec + 60)
        result = asyncio.run(
            engine.execute("sess_r1", cfg.chaos_config, started_at, "ctr_r")
        )
        assert result.chaos_type == "KILL_CONSUMER"
        assert result.outcome == "success"

    def test_corrupt_schema_executes_with_real_config(self) -> None:
        from services.orchestrator.scenario_engine import ScenarioEngine  # noqa: PLC0415

        cfg = ScenarioEngine().load_config("scenario_silent_pipeline_v1")
        engine = ChaosEngine(docker_exec=_ok_exec)
        # started_at far enough in the past so trigger_at_sec (1200) already elapsed
        started_at = datetime.now(UTC) - timedelta(seconds=cfg.chaos_config.trigger_at_sec + 60)
        result = asyncio.run(
            engine.execute("sess_r2", cfg.chaos_config, started_at, "ctr_r")
        )
        assert result.chaos_type == "CORRUPT_SCHEMA"
        assert result.outcome == "success"


# ---------------------------------------------------------------------------
# Synthetic fixtures — CHAOS_INJECTED event presence
# ---------------------------------------------------------------------------


class TestSyntheticFixturesChaosEvents:
    import json
    from pathlib import Path

    _SYNTHETIC_DIR = (
        Path(__file__).parent.parent.parent / "data" / "synthetic"
    )

    def _load(self, filename: str) -> dict:
        import json  # noqa: PLC0415

        return json.loads(
            (self._SYNTHETIC_DIR / filename).read_text(encoding="utf-8")
        )

    def test_session_001_has_chaos_injected(self) -> None:
        data = self._load("session_001.json")
        types = [e["event_type"] for e in data["events"]]
        assert "CHAOS_INJECTED" in types

    def test_session_002_has_chaos_injected(self) -> None:
        data = self._load("session_002.json")
        types = [e["event_type"] for e in data["events"]]
        assert "CHAOS_INJECTED" in types

    def test_chaos_event_emitted_before_scenario_ended(self) -> None:
        for fname in ["session_001.json", "session_002.json"]:
            data = self._load(fname)
            events = data["events"]
            chaos_idx = next(
                i for i, e in enumerate(events) if e["event_type"] == "CHAOS_INJECTED"
            )
            ended_idx = next(
                i for i, e in enumerate(events) if e["event_type"] == "SCENARIO_ENDED"
            )
            assert chaos_idx < ended_idx, f"{fname}: CHAOS_INJECTED must precede SCENARIO_ENDED"

    def test_chaos_event_has_required_payload_fields(self) -> None:
        for fname in ["session_001.json", "session_002.json"]:
            data = self._load(fname)
            for event in data["events"]:
                if event["event_type"] == "CHAOS_INJECTED":
                    payload = event["payload"]
                    assert "chaos_type" in payload
                    assert "target" in payload
                    assert "trigger_at_sec" in payload
                    assert "injected_at" in payload

    def test_post_chaos_prompt_exists(self) -> None:
        """A PROMPT_SENT event must appear after CHAOS_INJECTED in each fixture."""
        for fname in ["session_001.json", "session_002.json"]:
            data = self._load(fname)
            events = data["events"]
            chaos_idx = next(
                i for i, e in enumerate(events) if e["event_type"] == "CHAOS_INJECTED"
            )
            post_chaos = [e for e in events[chaos_idx + 1 :] if e["event_type"] == "PROMPT_SENT"]
            assert len(post_chaos) >= 1, f"{fname}: expected post-chaos PROMPT_SENT"
