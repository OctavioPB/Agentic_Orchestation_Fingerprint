"""Lightweight telemetry emitter for the candidate sandbox.

Sends orchid telemetry events to Kafka so the evaluator pipeline can observe
candidate actions in real time. Uses kafka-python (already installed in the
sandbox image) without requiring the full services/telemetry module.

Usage (called automatically by the assessment scaffolding):
    from telemetry_client import SandboxTelemetryClient

    client = SandboxTelemetryClient(session_id="sess_abc123")
    client.emit_prompt_sent(agent="DELTA", text="Analyze pipeline.py")
    client.emit_code_executed(command="python3 pipeline.py", exit_code=1, stderr="Error!")
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

_KAFKA_BROKERS = os.environ.get("KAFKA_BROKERS", "kafka:9092")
_TOPIC_PREFIX = "orchid.sandbox"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _envelope(session_id: str, event_type: str, payload: dict) -> dict:
    return {
        "event_id": _new_id(),
        "session_id": session_id,
        "timestamp": _utc_now(),
        "event_type": event_type,
        "payload": payload,
    }


class SandboxTelemetryClient:
    """Emits telemetry events from inside the candidate sandbox to Kafka."""

    def __init__(self, session_id: str, bootstrap_servers: str = _KAFKA_BROKERS) -> None:
        self.session_id = session_id
        self._servers = bootstrap_servers
        self._producer = self._build_producer()

    def _build_producer(self):  # type: ignore[return]  # kafka-python not type-stubbed
        try:
            from kafka import KafkaProducer

            return KafkaProducer(
                bootstrap_servers=self._servers,
                value_serializer=lambda v: json.dumps(v).encode(),
                key_serializer=lambda k: k.encode(),
            )
        except Exception as exc:
            logger.warning("Kafka unavailable — telemetry disabled: %s", exc)
            return None

    def _emit(self, event_type: str, payload: dict) -> None:
        if self._producer is None:
            return
        topic = f"{_TOPIC_PREFIX}.{event_type.lower()}"
        envelope = _envelope(self.session_id, event_type, payload)
        try:
            self._producer.send(topic, key=self.session_id, value=envelope)
            self._producer.flush(timeout=2)
        except Exception as exc:
            logger.warning("Telemetry emit failed: %s", exc)

    # ── Public emit methods ─────────────────────────────────────────────────────

    def emit_scenario_started(self, scenario_id: str, scenario_version: str = "v1") -> None:
        self._emit(
            "SCENARIO_STARTED",
            {"scenario_id": scenario_id, "scenario_version": scenario_version},
        )

    def emit_prompt_sent(self, agent: str, text: str, context: dict | None = None) -> None:
        self._emit(
            "PROMPT_SENT",
            {"agent": agent, "text": text, "context": context or {}},
        )

    def emit_agent_response(
        self, agent: str, text: str, model: str, latency_ms: int, token_count: int
    ) -> None:
        self._emit(
            "AGENT_RESPONSE",
            {
                "agent": agent,
                "text": text,
                "model": model,
                "latency_ms": latency_ms,
                "token_count": token_count,
            },
        )

    def emit_correction_issued(
        self,
        agent: str,
        correction_text: str,
        original_event_id: str,
        error_type: str | None = None,
    ) -> None:
        self._emit(
            "CORRECTION_ISSUED",
            {
                "agent": agent,
                "correction_text": correction_text,
                "original_event_id": original_event_id,
                "error_type": error_type,
            },
        )

    def emit_code_executed(
        self, command: str, exit_code: int, stdout: str = "", stderr: str = ""
    ) -> None:
        self._emit(
            "CODE_EXECUTED",
            {"command": command, "exit_code": exit_code, "stdout": stdout, "stderr": stderr},
        )

    def emit_scenario_ended(self, reason: str = "completed", duration_sec: int = 0) -> None:
        self._emit("SCENARIO_ENDED", {"reason": reason, "duration_sec": duration_sec})

    def close(self) -> None:
        if self._producer:
            self._producer.flush(timeout=5)
            self._producer.close()
