"""Kafka topic name constants for all orchid telemetry event types."""
from __future__ import annotations

from .models import EventType

_SANDBOX_PREFIX = "orchid.sandbox"

# Map from EventType → Kafka topic name
TOPIC_MAP: dict[EventType, str] = {
    EventType.PROMPT_SENT: f"{_SANDBOX_PREFIX}.prompt_sent",
    EventType.AGENT_RESPONSE: f"{_SANDBOX_PREFIX}.agent_response",
    EventType.CORRECTION_ISSUED: f"{_SANDBOX_PREFIX}.correction_issued",
    EventType.CODE_EXECUTED: f"{_SANDBOX_PREFIX}.code_executed",
    EventType.FOCUS_SHIFT: f"{_SANDBOX_PREFIX}.focus_shift",
    EventType.CHAOS_INJECTED: f"{_SANDBOX_PREFIX}.chaos_injected",
    EventType.SCENARIO_STARTED: f"{_SANDBOX_PREFIX}.scenario_started",
    EventType.SCENARIO_ENDED: f"{_SANDBOX_PREFIX}.scenario_ended",
}

DLQ_TOPIC = "orchid.dlq"

ALL_ORCHID_TOPICS: list[str] = list(TOPIC_MAP.values()) + [DLQ_TOPIC]
