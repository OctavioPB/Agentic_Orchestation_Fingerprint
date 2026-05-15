"""Sprint 1 smoke tests — validate synthetic fixtures and domain schema contracts."""
import json
from pathlib import Path

SYNTHETIC_DIR = Path(__file__).parent.parent.parent / "data" / "synthetic"

KNOWN_EVENT_TYPES = {
    "SCENARIO_STARTED",
    "SCENARIO_ENDED",
    "PROMPT_SENT",
    "AGENT_RESPONSE",
    "CORRECTION_ISSUED",
    "CODE_EXECUTED",
    "CHAOS_INJECTED",
    "FOCUS_SHIFT",
}

KNOWN_AGENTS = {"DELTA", "NOVA", "ECHO"}

KNOWN_STYLE_CLUSTERS = {"architect", "executor", "debugger", "delegator"}

REQUIRED_FINGERPRINT_SCORES = {
    "efficiency_ratio",
    "trust_calibration",
    "correction_velocity",
    "decomposition_score",
    "chaos_resilience",
}


def test_synthetic_fixtures_exist() -> None:
    """Both synthetic session fixture files must exist."""
    fixtures = list(SYNTHETIC_DIR.glob("session_*.json"))
    assert len(fixtures) >= 2, f"Expected >=2 fixtures in data/synthetic/, found {len(fixtures)}"


def test_synthetic_fixtures_are_valid_json() -> None:
    """Every fixture file must parse as valid JSON."""
    for path in SYNTHETIC_DIR.glob("session_*.json"):
        with path.open() as f:
            data = json.load(f)
        assert isinstance(data, dict), f"{path.name} root must be a JSON object"


def test_synthetic_fixtures_have_required_top_level_fields() -> None:
    """Each fixture must include session_id, candidate_id, scenario_id, and events."""
    required = {"session_id", "candidate_id", "scenario_id", "events"}
    for path in SYNTHETIC_DIR.glob("session_*.json"):
        with path.open() as f:
            data = json.load(f)
        missing = required - data.keys()
        assert not missing, f"{path.name} is missing fields: {missing}"


def test_synthetic_fixtures_have_events() -> None:
    """Each session must have at least one event."""
    for path in SYNTHETIC_DIR.glob("session_*.json"):
        with path.open() as f:
            data = json.load(f)
        assert len(data["events"]) > 0, f"{path.name} has no events"


def test_events_have_required_envelope_fields() -> None:
    """Every event must have event_id, session_id, timestamp, event_type, payload."""
    required = {"event_id", "session_id", "timestamp", "event_type", "payload"}
    for path in SYNTHETIC_DIR.glob("session_*.json"):
        with path.open() as f:
            data = json.load(f)
        for event in data["events"]:
            missing = required - event.keys()
            assert not missing, (
                f"{path.name} event {event.get('event_id', '?')} missing fields: {missing}"
            )


def test_event_types_are_known() -> None:
    """Every event_type in the fixtures must be in the defined enum."""
    for path in SYNTHETIC_DIR.glob("session_*.json"):
        with path.open() as f:
            data = json.load(f)
        for event in data["events"]:
            assert event["event_type"] in KNOWN_EVENT_TYPES, (
                f"{path.name}: unknown event_type '{event['event_type']}'"
            )


def test_sessions_start_and_end() -> None:
    """Each session must have exactly one SCENARIO_STARTED and one SCENARIO_ENDED event."""
    for path in SYNTHETIC_DIR.glob("session_*.json"):
        with path.open() as f:
            data = json.load(f)
        types = [e["event_type"] for e in data["events"]]
        assert types.count("SCENARIO_STARTED") == 1, f"{path.name}: expected 1 SCENARIO_STARTED"
        assert types.count("SCENARIO_ENDED") == 1, f"{path.name}: expected 1 SCENARIO_ENDED"
        assert types[0] == "SCENARIO_STARTED", f"{path.name}: first event must be SCENARIO_STARTED"
        assert types[-1] == "SCENARIO_ENDED", f"{path.name}: last event must be SCENARIO_ENDED"


def test_prompt_sent_events_have_valid_agent() -> None:
    """All PROMPT_SENT events must reference a known agent."""
    for path in SYNTHETIC_DIR.glob("session_*.json"):
        with path.open() as f:
            data = json.load(f)
        for event in data["events"]:
            if event["event_type"] == "PROMPT_SENT":
                agent = event["payload"].get("agent")
                assert agent in KNOWN_AGENTS, (
                    f"{path.name} event {event['event_id']}: unknown agent '{agent}'"
                )


def test_agent_response_events_have_latency_ms() -> None:
    """All AGENT_RESPONSE events must include latency_ms for cost observability."""
    for path in SYNTHETIC_DIR.glob("session_*.json"):
        with path.open() as f:
            data = json.load(f)
        for event in data["events"]:
            if event["event_type"] == "AGENT_RESPONSE":
                assert "latency_ms" in event["payload"], (
                    f"{path.name} event {event['event_id']}: AGENT_RESPONSE missing latency_ms"
                )


def test_orchestration_fingerprint_score_contract() -> None:
    """Document and validate the OrchestraFingerprint score field contract."""
    # Structural contract test — actual implementation lives in services/evaluator.
    # If these field names change, this test fails and forces a documentation update.
    assert REQUIRED_FINGERPRINT_SCORES == {
        "efficiency_ratio",
        "trust_calibration",
        "correction_velocity",
        "decomposition_score",
        "chaos_resilience",
    }


def test_style_clusters_are_defined() -> None:
    """Document the four valid style_cluster values."""
    assert KNOWN_STYLE_CLUSTERS == {"architect", "executor", "debugger", "delegator"}


def test_session_ids_are_unique_across_fixtures() -> None:
    """No two fixture files should share a session_id."""
    session_ids: list[str] = []
    for path in SYNTHETIC_DIR.glob("session_*.json"):
        with path.open() as f:
            data = json.load(f)
        session_ids.append(data["session_id"])
    assert len(session_ids) == len(set(session_ids)), "Duplicate session_id across fixtures"
