"""Unit tests for services/telemetry/models.py — no Kafka, no Docker."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from services.telemetry.models import (
    AgentName,
    AgentResponsePayload,
    ChaosConfig,
    ChaosInjectedPayload,
    CodeExecutedPayload,
    CorrectionIssuedPayload,
    EventType,
    FocusShiftPayload,
    PromptSentPayload,
    ScenarioEndedPayload,
    ScenarioStartedPayload,
    TelemetryEvent,
)

# ─── EventType enum ────────────────────────────────────────────────────────────


def test_event_type_values_are_strings() -> None:
    for et in EventType:
        assert isinstance(et, str)


def test_event_type_has_all_8_types() -> None:
    names = {et.value for et in EventType}
    expected = {
        "PROMPT_SENT",
        "AGENT_RESPONSE",
        "CORRECTION_ISSUED",
        "CODE_EXECUTED",
        "FOCUS_SHIFT",
        "CHAOS_INJECTED",
        "SCENARIO_STARTED",
        "SCENARIO_ENDED",
    }
    assert names == expected


def test_agent_name_has_three_agents() -> None:
    assert set(AgentName) == {"DELTA", "NOVA", "ECHO"}


# ─── TelemetryEvent defaults ───────────────────────────────────────────────────


def test_event_id_is_uuid_v4_by_default() -> None:
    event = TelemetryEvent(
        session_id="sess_001",
        event_type=EventType.SCENARIO_STARTED,
        payload={},
    )
    parsed = uuid.UUID(event.event_id)
    assert parsed.version == 4


def test_timestamp_is_utc_iso_by_default() -> None:
    event = TelemetryEvent(
        session_id="sess_001",
        event_type=EventType.SCENARIO_STARTED,
        payload={},
    )
    # Must parse without error and include timezone info
    dt = datetime.fromisoformat(event.timestamp)
    assert dt.tzinfo is not None


def test_two_events_have_distinct_event_ids() -> None:
    e1 = TelemetryEvent(session_id="s", event_type=EventType.CODE_EXECUTED, payload={})
    e2 = TelemetryEvent(session_id="s", event_type=EventType.CODE_EXECUTED, payload={})
    assert e1.event_id != e2.event_id


# ─── Factory class methods ─────────────────────────────────────────────────────


def test_prompt_sent_factory() -> None:
    payload = PromptSentPayload(agent=AgentName.DELTA, text="Analyze the pipeline.")
    event = TelemetryEvent.prompt_sent("sess_abc", payload)
    assert event.event_type == EventType.PROMPT_SENT
    assert event.payload["agent"] == "DELTA"
    assert event.payload["text"] == "Analyze the pipeline."
    assert event.payload["context"] == {}


def test_agent_response_factory() -> None:
    payload = AgentResponsePayload(
        agent=AgentName.NOVA,
        text="The topic name has a typo.",
        model="gpt-4o",
        latency_ms=945,
        token_count=67,
    )
    event = TelemetryEvent.agent_response("sess_abc", payload)
    assert event.event_type == EventType.AGENT_RESPONSE
    assert event.payload["latency_ms"] == 945
    assert event.payload["token_count"] == 67


def test_correction_issued_factory() -> None:
    payload = CorrectionIssuedPayload(
        agent=AgentName.DELTA,
        correction_text="Column name is wrong.",
        original_event_id="evt_abc",
        error_type="hallucinated_column_name",
    )
    event = TelemetryEvent.correction_issued("sess_abc", payload)
    assert event.event_type == EventType.CORRECTION_ISSUED
    assert event.payload["error_type"] == "hallucinated_column_name"


def test_correction_issued_error_type_optional() -> None:
    payload = CorrectionIssuedPayload(
        agent=AgentName.ECHO,
        correction_text="Keep it scoped.",
        original_event_id="evt_xyz",
    )
    event = TelemetryEvent.correction_issued("sess_abc", payload)
    assert event.payload["error_type"] is None


def test_code_executed_factory() -> None:
    payload = CodeExecutedPayload(command="python3 pipeline.py", exit_code=1, stderr="Error!")
    event = TelemetryEvent.code_executed("sess_abc", payload)
    assert event.event_type == EventType.CODE_EXECUTED
    assert event.payload["exit_code"] == 1
    assert event.payload["stdout"] == ""


def test_focus_shift_factory() -> None:
    payload = FocusShiftPayload(from_component="editor", to_component="terminal", dwell_ms=4200)
    event = TelemetryEvent.focus_shift("sess_abc", payload)
    assert event.event_type == EventType.FOCUS_SHIFT
    assert event.payload["dwell_ms"] == 4200


def test_chaos_injected_factory() -> None:
    payload = ChaosInjectedPayload(
        chaos_type="KILL_CONSUMER",
        target="kafka-consumer-process",
        trigger_at_sec=1800,
        injected_at=datetime.now(UTC).isoformat(),
        params={"signal": "SIGKILL"},
    )
    event = TelemetryEvent.chaos_injected("sess_abc", payload)
    assert event.event_type == EventType.CHAOS_INJECTED
    assert event.payload["chaos_type"] == "KILL_CONSUMER"


def test_scenario_started_factory() -> None:
    chaos = ChaosConfig(type="KILL_CONSUMER", trigger_at_sec=1800, target="kafka")
    payload = ScenarioStartedPayload(
        scenario_id="scenario_corrupted_warehouse_v1",
        scenario_version="v1",
        chaos_config=chaos,
    )
    event = TelemetryEvent.scenario_started("sess_abc", payload)
    assert event.event_type == EventType.SCENARIO_STARTED
    assert event.payload["chaos_config"]["type"] == "KILL_CONSUMER"


def test_scenario_ended_factory() -> None:
    payload = ScenarioEndedPayload(reason="completed", duration_sec=2843)
    event = TelemetryEvent.scenario_ended("sess_abc", payload)
    assert event.event_type == EventType.SCENARIO_ENDED
    assert event.payload["reason"] == "completed"
    assert event.payload["duration_sec"] == 2843


# ─── Serialization roundtrip ───────────────────────────────────────────────────


def test_event_json_roundtrip() -> None:
    payload = PromptSentPayload(agent=AgentName.DELTA, text="Fix the broker address.")
    original = TelemetryEvent.prompt_sent("sess_roundtrip", payload)

    serialized = original.model_dump_json()
    restored = TelemetryEvent.model_validate_json(serialized)

    assert restored.event_id == original.event_id
    assert restored.session_id == original.session_id
    assert restored.event_type == original.event_type
    assert restored.payload == original.payload


def test_event_dict_roundtrip() -> None:
    payload = CodeExecutedPayload(command="ls -la", exit_code=0, stdout="README.md\n")
    original = TelemetryEvent.code_executed("sess_abc", payload)

    as_dict = original.model_dump()
    restored = TelemetryEvent.model_validate(as_dict)
    assert restored == original


# ─── Payload validation ────────────────────────────────────────────────────────


def test_prompt_sent_rejects_unknown_agent() -> None:
    with pytest.raises(ValidationError):
        PromptSentPayload(agent="UNKNOWN_AGENT", text="hello")  # type: ignore[arg-type]


def test_scenario_ended_rejects_unknown_reason() -> None:
    with pytest.raises(ValidationError):
        ScenarioEndedPayload(reason="cancelled", duration_sec=100)  # type: ignore[arg-type]


# ─── Synthetic fixture compatibility ──────────────────────────────────────────


def test_synthetic_fixtures_parse_as_telemetry_events() -> None:
    """All events in the synthetic fixtures must deserialize to TelemetryEvent."""
    from pathlib import Path

    fixture_dir = Path(__file__).resolve().parents[2] / "data" / "synthetic"
    for fixture_path in fixture_dir.glob("session_*.json"):
        session = json.loads(fixture_path.read_text())
        for raw_event in session["events"]:
            event = TelemetryEvent.model_validate(raw_event)
            assert event.session_id == session["session_id"], (
                f"{fixture_path.name}: event session_id mismatch"
            )
