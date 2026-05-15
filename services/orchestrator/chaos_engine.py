"""ChaosEngine — executes fault injection during live assessment sessions.

Per CLAUDE.md Rule 3: chaos injection is Airflow's job. The ChaosEngine
is called exclusively from Airflow DAGs — never from application code.

Invariant: the CHAOS_INJECTED Kafka event is always emitted BEFORE the fault
executes. The ``ChaosResult.kafka_emitted_at`` timestamp is always earlier than
``ChaosResult.executed_at``, giving downstream scorers a reliable signal boundary.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any, Literal

import structlog
from pydantic import BaseModel

from services.orchestrator.scenario_engine import ChaosConfig
from services.telemetry.models import ChaosInjectedPayload, TelemetryEvent

logger = structlog.get_logger(__name__)

_DEFAULT_KAFKA_BROKERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
_FLOOD_MESSAGE_COUNT = 500
_FLOOD_TOPIC_DEFAULT = "orchid.sandbox.prompt_sent"

# Injected docker-exec callable signature: (container_id, cmd_list) → (returncode, output)
DockerExecFn = Callable[[str, list[str]], Coroutine[Any, Any, tuple[int, str]]]


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class ChaosResult(BaseModel):
    session_id: str
    chaos_type: str
    kafka_emitted_at: datetime
    executed_at: datetime
    outcome: Literal["success", "error"]
    detail: str = ""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class ChaosEngine:
    """Executes chaos faults for a live assessment session.

    Accepts injectable ``docker_exec`` and ``telemetry_producer`` so that unit
    tests can run without Docker or Kafka.
    """

    def __init__(
        self,
        kafka_bootstrap_servers: str | None = None,
        telemetry_producer: Any | None = None,
        docker_exec: DockerExecFn | None = None,
    ) -> None:
        self._kafka_brokers = kafka_bootstrap_servers or _DEFAULT_KAFKA_BROKERS
        self._producer = telemetry_producer
        self._docker_exec_fn: DockerExecFn = docker_exec or _default_docker_exec

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def execute(
        self,
        session_id: str,
        chaos_config: ChaosConfig,
        started_at: datetime,
        container_id: str,
    ) -> ChaosResult:
        """Wait until the configured trigger time, then inject the fault.

        The CHAOS_INJECTED Kafka event is always emitted before the fault lands.
        """
        log = logger.bind(
            session_id=session_id,
            chaos_type=chaos_config.type,
            container_id=container_id,
        )

        wait_sec = self._compute_wait_sec(chaos_config.trigger_at_sec, started_at)
        if wait_sec > 0:
            log.info("chaos_waiting", wait_sec=round(wait_sec, 1))
            await asyncio.sleep(wait_sec)

        # Emit to Kafka FIRST — this is the invariant (Rule 3)
        kafka_emitted_at = await self._emit_chaos_event(session_id, chaos_config)
        log.info("chaos_emitted", emitted_at=kafka_emitted_at.isoformat())

        executed_at = datetime.now(UTC)
        outcome: Literal["success", "error"]
        try:
            detail = await self._dispatch(session_id, chaos_config, container_id)
            outcome = "success"
        except Exception as exc:  # noqa: BLE001
            log.error("chaos_execution_failed", error=str(exc))
            detail = str(exc)
            outcome = "error"

        log.info("chaos_complete", outcome=outcome)
        return ChaosResult(
            session_id=session_id,
            chaos_type=chaos_config.type,
            kafka_emitted_at=kafka_emitted_at,
            executed_at=executed_at,
            outcome=outcome,
            detail=detail,
        )

    # ------------------------------------------------------------------
    # Pure helpers (sync, easily unit-tested)
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_wait_sec(trigger_at_sec: int, started_at: datetime) -> float:
        """Seconds to sleep before injecting. Returns 0.0 if trigger already passed."""
        elapsed = (datetime.now(UTC) - started_at).total_seconds()
        return max(0.0, float(trigger_at_sec) - elapsed)

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    async def _dispatch(
        self, session_id: str, chaos_config: ChaosConfig, container_id: str
    ) -> str:
        t = chaos_config.type
        if t == "KILL_CONSUMER":
            return await self._kill_consumer(container_id, chaos_config.params)
        if t == "CORRUPT_SCHEMA":
            return await self._corrupt_schema(
                container_id, chaos_config.target, chaos_config.params
            )
        if t == "FLOOD_TOPIC":
            return await self._flood_topic(session_id, chaos_config.params)
        raise ValueError(f"Unknown chaos type: {t!r}")

    # ------------------------------------------------------------------
    # Kafka emit (best-effort — failure logged, not raised)
    # ------------------------------------------------------------------

    async def _emit_chaos_event(
        self, session_id: str, chaos_config: ChaosConfig
    ) -> datetime:
        emitted_at = datetime.now(UTC)
        event = TelemetryEvent.chaos_injected(
            session_id=session_id,
            payload=ChaosInjectedPayload(
                chaos_type=chaos_config.type,
                target=chaos_config.target,
                trigger_at_sec=chaos_config.trigger_at_sec,
                injected_at=emitted_at.isoformat(),
                params=chaos_config.params,
            ),
        )
        if self._producer is not None:
            try:
                await self._producer.emit(event)
            except Exception as exc:  # noqa: BLE001
                logger.warning("chaos_kafka_emit_failed", error=str(exc))
        return emitted_at

    # ------------------------------------------------------------------
    # Chaos executors
    # ------------------------------------------------------------------

    async def _kill_consumer(self, container_id: str, params: dict[str, Any]) -> str:
        """Send SIGKILL to the pipeline.py process inside the container."""
        signal = params.get("signal", "SIGKILL")
        # pkill returns 1 if no matching process — treat as non-fatal
        rc, output = await self._docker_exec_fn(
            container_id, ["pkill", f"-{signal}", "-f", "pipeline.py"]
        )
        if rc not in (0, 1):
            raise RuntimeError(f"pkill exited {rc}: {output.strip()}")
        return f"{signal} delivered to pipeline.py (pkill exit={rc})"

    async def _corrupt_schema(
        self, container_id: str, target: str, params: dict[str, Any]
    ) -> str:
        """Corrupt schema based on chaos_config.target.

        - target=qdrant-collection → patch qdrant_ingest.py to drop a payload field
        - anything else → drop a column from the SQLite DB via ALTER TABLE
        """
        if target == "qdrant-collection":
            return await self._corrupt_qdrant_schema(container_id, params)
        return await self._corrupt_sqlite_schema(container_id, params)

    async def _corrupt_qdrant_schema(
        self, container_id: str, params: dict[str, Any]
    ) -> str:
        drop_field = params.get("drop_field", "session_id")
        # Use a regex substitution to remove the field from the payload dict literal
        python_code = (
            "import re, pathlib; "
            "p = pathlib.Path('/home/coder/project/qdrant_ingest.py'); "
            "code = p.read_text(); "
            f'code = re.sub(r\'"session_id": session_id,?\\\\s*\', "", code); '
            "p.write_text(code); "
            f"print('dropped {drop_field} from qdrant_ingest.py')"
        )
        rc, output = await self._docker_exec_fn(
            container_id, ["python3", "-c", python_code]
        )
        if rc != 0:
            raise RuntimeError(f"qdrant schema corrupt exited {rc}: {output.strip()}")
        return output.strip()

    async def _corrupt_sqlite_schema(
        self, container_id: str, params: dict[str, Any]
    ) -> str:
        table = params.get("table", "orders")
        column = params.get("column", "status")
        db_path = params.get("db_path", "/home/coder/project/dirty_warehouse.db")
        python_code = (
            f"import sqlite3; "
            f"conn = sqlite3.connect('{db_path}'); "
            f"conn.execute('ALTER TABLE {table} DROP COLUMN {column}'); "
            f"conn.commit(); conn.close(); "
            f"print('dropped column {column} from {table}')"
        )
        rc, output = await self._docker_exec_fn(
            container_id, ["python3", "-c", python_code]
        )
        if rc != 0:
            raise RuntimeError(f"sqlite schema corrupt exited {rc}: {output.strip()}")
        return output.strip()

    async def _flood_topic(self, session_id: str, params: dict[str, Any]) -> str:
        """Publish malformed messages to a Kafka topic via kafka-python.

        Uses a thread executor because kafka-python is synchronous.
        """
        count = int(params.get("message_count", _FLOOD_MESSAGE_COUNT))
        topic = params.get("topic", _FLOOD_TOPIC_DEFAULT)
        brokers = params.get("brokers", self._kafka_brokers)

        def _produce() -> int:
            from kafka import KafkaProducer  # noqa: PLC0415 — lazy: kafka-python optional

            prod = KafkaProducer(bootstrap_servers=brokers)
            for i in range(count):
                prod.send(topic, f"{{not_valid_json_{session_id}_{i}}}".encode())
            prod.flush()
            prod.close()
            return count

        loop = asyncio.get_event_loop()
        sent = await loop.run_in_executor(None, _produce)
        return f"flooded {sent} malformed messages to {topic}"


# ---------------------------------------------------------------------------
# Default docker exec (uses subprocess — mockable in tests)
# ---------------------------------------------------------------------------


async def _default_docker_exec(container_id: str, cmd: list[str]) -> tuple[int, str]:
    """Execute a command inside a running container via the docker CLI."""
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "exec",
        container_id,
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout_bytes, _ = await proc.communicate()
    return proc.returncode or 0, stdout_bytes.decode(errors="replace")
