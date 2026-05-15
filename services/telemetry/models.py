"""Pydantic v2 models for all orchid telemetry events."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ─── Enums ─────────────────────────────────────────────────────────────────────


class EventType(StrEnum):
    PROMPT_SENT = "PROMPT_SENT"
    AGENT_RESPONSE = "AGENT_RESPONSE"
    CORRECTION_ISSUED = "CORRECTION_ISSUED"
    CODE_EXECUTED = "CODE_EXECUTED"
    FOCUS_SHIFT = "FOCUS_SHIFT"
    CHAOS_INJECTED = "CHAOS_INJECTED"
    SCENARIO_STARTED = "SCENARIO_STARTED"
    SCENARIO_ENDED = "SCENARIO_ENDED"


class AgentName(StrEnum):
    DELTA = "DELTA"
    NOVA = "NOVA"
    ECHO = "ECHO"


# ─── Default factories ─────────────────────────────────────────────────────────


def _new_event_id() -> str:
    return str(uuid.uuid4())


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


# ─── Payload models ────────────────────────────────────────────────────────────


class PromptSentPayload(BaseModel):
    agent: AgentName
    text: str
    # Any: context keys/values vary by scenario and sprint — intentionally open
    context: dict[str, Any] = Field(default_factory=dict)


class AgentResponsePayload(BaseModel):
    agent: AgentName
    text: str
    model: str
    latency_ms: int
    token_count: int


class CorrectionIssuedPayload(BaseModel):
    agent: AgentName
    correction_text: str
    original_event_id: str
    error_type: str | None = None


class CodeExecutedPayload(BaseModel):
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""


class FocusShiftPayload(BaseModel):
    from_component: str | None = None
    to_component: str
    dwell_ms: int


class ChaosConfig(BaseModel):
    type: str
    trigger_at_sec: int
    target: str
    # Any: params structure differs per chaos type (KILL_CONSUMER vs CORRUPT_SCHEMA etc.)
    params: dict[str, Any] = Field(default_factory=dict)


class ChaosInjectedPayload(BaseModel):
    chaos_type: str
    target: str
    trigger_at_sec: int
    injected_at: str
    # Any: same reasoning as ChaosConfig.params
    params: dict[str, Any] = Field(default_factory=dict)


class ScenarioStartedPayload(BaseModel):
    scenario_id: str
    scenario_version: str
    chaos_config: ChaosConfig | None = None


class ScenarioEndedPayload(BaseModel):
    reason: Literal["completed", "timeout"]
    duration_sec: int


# ─── Envelope ──────────────────────────────────────────────────────────────────


class TelemetryEvent(BaseModel):
    """Transport envelope for all orchid telemetry events.

    The `payload` field is a raw dict so that the envelope can be serialized to
    Kafka without knowing the specific payload type. Callers construct typed
    payload models first, then call `.model_dump()` to fill this field.
    """

    event_id: str = Field(default_factory=_new_event_id)
    session_id: str
    timestamp: str = Field(default_factory=_utc_now)
    event_type: EventType
    # Any: payload schema varies per event_type; validated at construction via typed helpers
    payload: dict[str, Any]

    # ── Typed factory helpers ───────────────────────────────────────────────────

    @classmethod
    def make(
        cls,
        session_id: str,
        event_type: EventType,
        payload: BaseModel,
        **overrides: Any,
    ) -> TelemetryEvent:
        """Generic factory — prefer the typed class methods below."""
        return cls(
            session_id=session_id,
            event_type=event_type,
            payload=payload.model_dump(),
            **overrides,
        )

    @classmethod
    def prompt_sent(cls, session_id: str, payload: PromptSentPayload) -> TelemetryEvent:
        return cls.make(session_id, EventType.PROMPT_SENT, payload)

    @classmethod
    def agent_response(cls, session_id: str, payload: AgentResponsePayload) -> TelemetryEvent:
        return cls.make(session_id, EventType.AGENT_RESPONSE, payload)

    @classmethod
    def correction_issued(
        cls, session_id: str, payload: CorrectionIssuedPayload
    ) -> TelemetryEvent:
        return cls.make(session_id, EventType.CORRECTION_ISSUED, payload)

    @classmethod
    def code_executed(cls, session_id: str, payload: CodeExecutedPayload) -> TelemetryEvent:
        return cls.make(session_id, EventType.CODE_EXECUTED, payload)

    @classmethod
    def focus_shift(cls, session_id: str, payload: FocusShiftPayload) -> TelemetryEvent:
        return cls.make(session_id, EventType.FOCUS_SHIFT, payload)

    @classmethod
    def chaos_injected(cls, session_id: str, payload: ChaosInjectedPayload) -> TelemetryEvent:
        return cls.make(session_id, EventType.CHAOS_INJECTED, payload)

    @classmethod
    def scenario_started(
        cls, session_id: str, payload: ScenarioStartedPayload
    ) -> TelemetryEvent:
        return cls.make(session_id, EventType.SCENARIO_STARTED, payload)

    @classmethod
    def scenario_ended(cls, session_id: str, payload: ScenarioEndedPayload) -> TelemetryEvent:
        return cls.make(session_id, EventType.SCENARIO_ENDED, payload)
