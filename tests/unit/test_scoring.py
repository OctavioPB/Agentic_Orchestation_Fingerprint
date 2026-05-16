"""Unit tests for all five scoring functions — uses synthetic fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.evaluator.scoring import (
    chaos_resilience,
    correction_velocity,
    decomposition_score,
    efficiency_ratio,
    trust_calibration,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_SYNTHETIC = Path(__file__).parent.parent.parent / "data" / "synthetic"
_BASELINES = (
    Path(__file__).parent.parent.parent
    / "data"
    / "scenarios"
    / "agents"
    / "baseline"
)


def _load(filename: str) -> dict:
    return json.loads((_SYNTHETIC / filename).read_text(encoding="utf-8"))


_S1 = _load("session_001.json")
_S2 = _load("session_002.json")


# ---------------------------------------------------------------------------
# efficiency_ratio
# ---------------------------------------------------------------------------


class TestEfficiencyRatio:
    def test_score_in_range(self) -> None:
        score = efficiency_ratio(_S1["events"], _S1["scenario_id"])
        assert 0.0 <= score <= 1.0

    def test_session_002_in_range(self) -> None:
        score = efficiency_ratio(_S2["events"], _S2["scenario_id"])
        assert 0.0 <= score <= 1.0

    def test_candidate_faster_than_baseline_gives_1(self) -> None:
        events = [
            {"event_type": "SCENARIO_STARTED", "timestamp": "2026-01-01T00:00:00Z", "payload": {}},
            {"event_type": "SCENARIO_ENDED", "timestamp": "2026-01-01T00:01:00Z", "payload": {}},
        ]
        # 60 sec candidate, baseline is 1847 sec → ratio = 1847/60 > 1 → clamped to 1.0
        score = efficiency_ratio(events, "scenario_corrupted_warehouse_v1", _BASELINES)
        assert score == 1.0

    def test_candidate_slower_than_baseline_gives_less_than_1(self) -> None:
        events = [
            {"event_type": "SCENARIO_STARTED", "timestamp": "2026-01-01T00:00:00Z", "payload": {}},
            {"event_type": "SCENARIO_ENDED", "timestamp": "2026-01-01T10:00:00Z", "payload": {}},
        ]
        # 36000 sec candidate, baseline 1847 sec → ratio = 1847/36000 ≈ 0.051
        score = efficiency_ratio(events, "scenario_corrupted_warehouse_v1", _BASELINES)
        assert score < 1.0
        assert score > 0.0

    def test_missing_timestamps_returns_neutral(self) -> None:
        events = [{"event_type": "PROMPT_SENT", "timestamp": "", "payload": {}}]
        score = efficiency_ratio(events, "scenario_corrupted_warehouse_v1", _BASELINES)
        assert score == 0.5

    def test_unknown_scenario_returns_neutral(self) -> None:
        score = efficiency_ratio(_S1["events"], "scenario_nonexistent_v99", _BASELINES)
        assert score == 0.5

    def test_returns_float(self) -> None:
        score = efficiency_ratio(_S1["events"], _S1["scenario_id"])
        assert isinstance(score, float)


# ---------------------------------------------------------------------------
# trust_calibration
# ---------------------------------------------------------------------------


class TestTrustCalibration:
    def test_score_in_range_session_001(self) -> None:
        score = trust_calibration(_S1["events"])
        assert 0.0 <= score <= 1.0

    def test_score_in_range_session_002(self) -> None:
        score = trust_calibration(_S2["events"])
        assert 0.0 <= score <= 1.0

    def test_no_corrections_returns_0(self) -> None:
        events = [
            {"event_type": "AGENT_RESPONSE", "payload": {}},
            {"event_type": "AGENT_RESPONSE", "payload": {}},
        ]
        assert trust_calibration(events) == 0.0

    def test_no_agent_responses_returns_0(self) -> None:
        events = [{"event_type": "PROMPT_SENT", "payload": {}}]
        assert trust_calibration(events) == 0.0

    def test_high_severity_correction_increases_score(self) -> None:
        events = [
            {"event_type": "AGENT_RESPONSE", "payload": {}},
            {
                "event_type": "CORRECTION_ISSUED",
                "payload": {"error_type": "hallucinated_column_name"},
            },
        ]
        score = trust_calibration(events)
        assert score == pytest.approx(1.0)

    def test_low_severity_correction_gives_lower_score(self) -> None:
        events_low = [
            {"event_type": "AGENT_RESPONSE", "payload": {}},
            {
                "event_type": "CORRECTION_ISSUED",
                "payload": {"error_type": "clarification_flood"},
            },
        ]
        events_high = [
            {"event_type": "AGENT_RESPONSE", "payload": {}},
            {
                "event_type": "CORRECTION_ISSUED",
                "payload": {"error_type": "hallucinated_column_name"},
            },
        ]
        assert trust_calibration(events_low) < trust_calibration(events_high)

    def test_returns_float(self) -> None:
        assert isinstance(trust_calibration(_S1["events"]), float)


# ---------------------------------------------------------------------------
# correction_velocity
# ---------------------------------------------------------------------------


class TestCorrectionVelocity:
    def test_score_in_range_session_001(self) -> None:
        score = correction_velocity(_S1["events"])
        assert 0.0 <= score <= 1.0

    def test_score_in_range_session_002(self) -> None:
        score = correction_velocity(_S2["events"])
        assert 0.0 <= score <= 1.0

    def test_no_corrections_returns_neutral(self) -> None:
        events = [{"event_type": "PROMPT_SENT", "payload": {}, "timestamp": "2026-01-01T00:00:00Z"}]
        assert correction_velocity(events) == 0.5

    def test_fast_correction_scores_high(self) -> None:
        events = [
            {
                "event_id": "orig",
                "event_type": "AGENT_RESPONSE",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {},
            },
            {
                "event_id": "corr",
                "event_type": "CORRECTION_ISSUED",
                "timestamp": "2026-01-01T00:00:30Z",  # 30 seconds later
                "payload": {"original_event_id": "orig"},
            },
        ]
        score = correction_velocity(events)
        assert score > 0.9

    def test_slow_correction_scores_low(self) -> None:
        events = [
            {
                "event_id": "orig",
                "event_type": "AGENT_RESPONSE",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {},
            },
            {
                "event_id": "corr",
                "event_type": "CORRECTION_ISSUED",
                "timestamp": "2026-01-01T00:15:00Z",  # 900 seconds = beyond MAX
                "payload": {"original_event_id": "orig"},
            },
        ]
        score = correction_velocity(events)
        assert score == 0.0

    def test_correction_without_original_ref_ignored(self) -> None:
        events = [
            {
                "event_id": "corr",
                "event_type": "CORRECTION_ISSUED",
                "timestamp": "2026-01-01T00:05:00Z",
                "payload": {},  # no original_event_id
            }
        ]
        assert correction_velocity(events) == 0.5

    def test_returns_float(self) -> None:
        assert isinstance(correction_velocity(_S1["events"]), float)


# ---------------------------------------------------------------------------
# decomposition_score
# ---------------------------------------------------------------------------


class TestDecompositionScore:
    def test_empty_prompt_scores_returns_0(self) -> None:
        assert decomposition_score([]) == 0.0

    def test_perfect_scores_return_1(self) -> None:
        scores = [
            {"clarity": 10, "specificity": 10, "context_richness": 10}
            for _ in range(3)
        ]
        assert decomposition_score(scores) == pytest.approx(1.0)

    def test_zero_scores_return_0(self) -> None:
        scores = [{"clarity": 0, "specificity": 0, "context_richness": 0}]
        assert decomposition_score(scores) == 0.0

    def test_mid_range_scores(self) -> None:
        scores = [{"clarity": 5, "specificity": 5, "context_richness": 5}]
        result = decomposition_score(scores)
        assert result == pytest.approx(0.5)

    def test_accepts_prompt_score_objects(self) -> None:
        from services.evaluator.shadow_agent import PromptScore

        ps = PromptScore(event_id="e1", clarity=8, specificity=6, context_richness=7)
        result = decomposition_score([ps])
        expected = (8 + 6 + 7) / 3 / 10
        assert result == pytest.approx(expected, abs=1e-4)

    def test_mean_across_multiple_prompts(self) -> None:
        scores = [
            {"clarity": 10, "specificity": 10, "context_richness": 10},  # mean=10
            {"clarity": 0, "specificity": 0, "context_richness": 0},     # mean=0
        ]
        result = decomposition_score(scores)
        assert result == pytest.approx(0.5)

    def test_returns_float(self) -> None:
        scores = [{"clarity": 5, "specificity": 5, "context_richness": 5}]
        assert isinstance(decomposition_score(scores), float)


# ---------------------------------------------------------------------------
# chaos_resilience
# ---------------------------------------------------------------------------


class TestChaosResilience:
    def test_score_in_range_session_001(self) -> None:
        score = chaos_resilience(_S1["events"])
        assert 0.0 <= score <= 1.0

    def test_score_in_range_session_002(self) -> None:
        score = chaos_resilience(_S2["events"])
        assert 0.0 <= score <= 1.0

    def test_no_chaos_returns_neutral(self) -> None:
        events = [{"event_type": "PROMPT_SENT", "timestamp": "2026-01-01T00:00:00Z", "payload": {}}]
        assert chaos_resilience(events) == 0.5

    def test_immediate_response_scores_high(self) -> None:
        chaos_ts = "2026-01-01T00:00:00Z"
        events = [
            {
                "event_type": "CHAOS_INJECTED",
                "timestamp": chaos_ts,
                "payload": {"injected_at": chaos_ts},
            },
            {
                "event_type": "PROMPT_SENT",
                "timestamp": "2026-01-01T00:00:10Z",  # 10 sec later
                "payload": {"text": "consumer crashed, fix it"},
            },
            {
                "event_type": "PROMPT_SENT",
                "timestamp": "2026-01-01T00:01:00Z",
                "payload": {},
            },
            {
                "event_type": "CODE_EXECUTED",
                "timestamp": "2026-01-01T00:02:00Z",
                "payload": {},
            },
        ]
        score = chaos_resilience(events, median_recovery_sec=600.0)
        assert score > 0.8

    def test_no_post_chaos_events_returns_0(self) -> None:
        events = [
            {
                "event_type": "CHAOS_INJECTED",
                "timestamp": "2026-01-01T00:00:00Z",
                "payload": {"injected_at": "2026-01-01T00:00:00Z"},
            }
        ]
        assert chaos_resilience(events) == 0.0

    def test_both_sessions_have_post_chaos_prompts(self) -> None:
        for session in [_S1, _S2]:
            score = chaos_resilience(session["events"])
            assert score > 0.0

    def test_returns_float(self) -> None:
        assert isinstance(chaos_resilience(_S1["events"]), float)


# ---------------------------------------------------------------------------
# Cross-scorer: all five produce [0,1] on both real sessions
# ---------------------------------------------------------------------------


class TestAllScorersOnRealFixtures:
    @pytest.mark.parametrize("session", [_S1, _S2])
    def test_efficiency_ratio_bounded(self, session: dict) -> None:
        assert 0.0 <= efficiency_ratio(session["events"], session["scenario_id"]) <= 1.0

    @pytest.mark.parametrize("session", [_S1, _S2])
    def test_trust_calibration_bounded(self, session: dict) -> None:
        assert 0.0 <= trust_calibration(session["events"]) <= 1.0

    @pytest.mark.parametrize("session", [_S1, _S2])
    def test_correction_velocity_bounded(self, session: dict) -> None:
        assert 0.0 <= correction_velocity(session["events"]) <= 1.0

    @pytest.mark.parametrize("session", [_S1, _S2])
    def test_chaos_resilience_bounded(self, session: dict) -> None:
        assert 0.0 <= chaos_resilience(session["events"]) <= 1.0
