"""Unit tests for OrchestraFingerprint and ChaosResilienceMarkers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from services.evaluator.fingerprint import (
    ChaosResilienceMarkers,
    GraphEdge,
    GraphNode,
    InteractionGraph,
    OrchestraFingerprint,
    ScoreSet,
)

# ---------------------------------------------------------------------------
# ScoreSet
# ---------------------------------------------------------------------------


class TestScoreSet:
    def test_all_none_by_default(self) -> None:
        s = ScoreSet()
        assert s.efficiency_ratio is None
        assert s.trust_calibration is None
        assert s.correction_velocity is None
        assert s.decomposition_score is None
        assert s.chaos_resilience is None

    def test_individual_assignment(self) -> None:
        s = ScoreSet(efficiency_ratio=0.85, chaos_resilience=0.72)
        assert s.efficiency_ratio == 0.85
        assert s.chaos_resilience == 0.72
        assert s.trust_calibration is None

    def test_all_five_scores_named_correctly(self) -> None:
        fields = set(ScoreSet.model_fields.keys())
        assert fields == {
            "efficiency_ratio",
            "trust_calibration",
            "correction_velocity",
            "decomposition_score",
            "chaos_resilience",
        }


# ---------------------------------------------------------------------------
# ChaosResilienceMarkers
# ---------------------------------------------------------------------------


class TestChaosResilienceMarkers:
    def _base(self) -> ChaosResilienceMarkers:
        return ChaosResilienceMarkers(
            chaos_type="KILL_CONSUMER",
            chaos_injected_at=datetime(2026, 5, 15, 10, 30, 0, tzinfo=UTC),
        )

    def test_first_response_latency_none_when_no_response(self) -> None:
        m = self._base()
        assert m.first_response_latency_sec is None

    def test_recovery_duration_none_when_not_recovered(self) -> None:
        m = self._base()
        assert m.recovery_duration_sec is None

    def test_first_response_latency_computed(self) -> None:
        m = self._base()
        m.first_response_at = m.chaos_injected_at + timedelta(seconds=65)
        assert m.first_response_latency_sec == pytest.approx(65.0)

    def test_recovery_duration_computed(self) -> None:
        m = self._base()
        m.recovery_completed_at = m.chaos_injected_at + timedelta(seconds=900)
        assert m.recovery_duration_sec == pytest.approx(900.0)

    def test_first_response_and_recovery_both_computed(self) -> None:
        m = self._base()
        m.first_response_at = m.chaos_injected_at + timedelta(seconds=60)
        m.recovery_completed_at = m.chaos_injected_at + timedelta(seconds=600)
        assert m.first_response_latency_sec == pytest.approx(60.0)
        assert m.recovery_duration_sec == pytest.approx(600.0)


# ---------------------------------------------------------------------------
# GraphEdge.correction_rate
# ---------------------------------------------------------------------------


class TestGraphEdge:
    def test_correction_rate_zero_messages(self) -> None:
        e = GraphEdge(source="human", target="DELTA", message_count=0, correction_count=0)
        assert e.correction_rate == 0.0

    def test_correction_rate_computed(self) -> None:
        e = GraphEdge(source="human", target="NOVA", message_count=10, correction_count=3)
        assert e.correction_rate == pytest.approx(0.3)

    def test_correction_rate_max(self) -> None:
        e = GraphEdge(source="human", target="ECHO", message_count=5, correction_count=5)
        assert e.correction_rate == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# OrchestraFingerprint
# ---------------------------------------------------------------------------


class TestOrchestraFingerprint:
    def _minimal(self) -> OrchestraFingerprint:
        return OrchestraFingerprint(
            session_id="sess_001",
            candidate_id="cand_001",
            scenario_id="scenario_corrupted_warehouse_v1",
        )

    def test_default_scores_are_all_none(self) -> None:
        fp = self._minimal()
        assert fp.scores.chaos_resilience is None
        assert fp.scores.efficiency_ratio is None

    def test_is_complete_false_when_scores_missing(self) -> None:
        fp = self._minimal()
        assert not fp.is_complete

    def test_is_complete_true_when_all_scores_and_cluster_set(self) -> None:
        fp = self._minimal()
        fp.scores = ScoreSet(
            efficiency_ratio=0.9,
            trust_calibration=0.7,
            correction_velocity=0.6,
            decomposition_score=0.8,
            chaos_resilience=0.75,
        )
        fp.style_cluster = "architect"
        assert fp.is_complete

    def test_is_complete_false_when_cluster_missing(self) -> None:
        fp = self._minimal()
        fp.scores = ScoreSet(
            efficiency_ratio=0.9,
            trust_calibration=0.7,
            correction_velocity=0.6,
            decomposition_score=0.8,
            chaos_resilience=0.75,
        )
        assert not fp.is_complete

    def test_record_chaos_injection(self) -> None:
        fp = self._minimal()
        injected_at = datetime.now(UTC)
        fp.record_chaos_injection("KILL_CONSUMER", injected_at)
        assert fp.chaos_markers is not None
        assert fp.chaos_markers.chaos_type == "KILL_CONSUMER"
        assert fp.chaos_markers.chaos_injected_at == injected_at
        assert fp.chaos_markers.first_response_at is None

    def test_record_chaos_first_response_sets_timestamp(self) -> None:
        fp = self._minimal()
        injected_at = datetime.now(UTC)
        fp.record_chaos_injection("KILL_CONSUMER", injected_at)
        response_at = injected_at + timedelta(seconds=90)
        fp.record_chaos_first_response(response_at)
        assert fp.chaos_markers is not None
        assert fp.chaos_markers.first_response_at == response_at

    def test_record_chaos_first_response_idempotent(self) -> None:
        """Second call does not overwrite the first response timestamp."""
        fp = self._minimal()
        fp.record_chaos_injection("KILL_CONSUMER", datetime.now(UTC))
        t1 = datetime.now(UTC) + timedelta(seconds=60)
        t2 = datetime.now(UTC) + timedelta(seconds=120)
        fp.record_chaos_first_response(t1)
        fp.record_chaos_first_response(t2)
        assert fp.chaos_markers is not None
        assert fp.chaos_markers.first_response_at == t1

    def test_record_chaos_recovery(self) -> None:
        fp = self._minimal()
        injected_at = datetime.now(UTC)
        fp.record_chaos_injection("CORRUPT_SCHEMA", injected_at)
        recovery_at = injected_at + timedelta(minutes=15)
        fp.record_chaos_recovery(recovery_at)
        assert fp.chaos_markers is not None
        assert fp.chaos_markers.recovery_completed_at == recovery_at

    def test_record_chaos_first_response_no_op_without_injection(self) -> None:
        fp = self._minimal()
        fp.record_chaos_first_response(datetime.now(UTC))
        assert fp.chaos_markers is None

    def test_record_chaos_recovery_no_op_without_injection(self) -> None:
        fp = self._minimal()
        fp.record_chaos_recovery(datetime.now(UTC))
        assert fp.chaos_markers is None

    def test_style_cluster_valid_values(self) -> None:
        for cluster in ("architect", "executor", "debugger", "delegator"):
            fp = self._minimal()
            fp.style_cluster = cluster  # type: ignore[assignment]
            assert fp.style_cluster == cluster

    def test_defaults_empty_collections(self) -> None:
        fp = self._minimal()
        assert fp.reasoning_trace == []
        assert fp.interaction_graph.nodes == []
        assert fp.interaction_graph.edges == []
        assert fp.benchmark_delta is None
        assert fp.report_markdown is None

    def test_json_roundtrip(self) -> None:
        fp = self._minimal()
        fp.record_chaos_injection("KILL_CONSUMER", datetime.now(UTC))
        fp.scores = ScoreSet(chaos_resilience=0.82)
        dumped = fp.model_dump_json()
        restored = OrchestraFingerprint.model_validate_json(dumped)
        assert restored.session_id == fp.session_id
        assert restored.scores.chaos_resilience == pytest.approx(0.82)
        assert restored.chaos_markers is not None
        assert restored.chaos_markers.chaos_type == "KILL_CONSUMER"


# ---------------------------------------------------------------------------
# InteractionGraph
# ---------------------------------------------------------------------------


class TestInteractionGraph:
    def test_empty_by_default(self) -> None:
        g = InteractionGraph()
        assert g.nodes == []
        assert g.edges == []

    def test_add_nodes_and_edges(self) -> None:
        g = InteractionGraph(
            nodes=[
                GraphNode(id="human", label="Candidate", node_type="human"),
                GraphNode(id="DELTA", label="DELTA", node_type="agent", agent_name="DELTA"),
            ],
            edges=[
                GraphEdge(
                    source="human",
                    target="DELTA",
                    message_count=8,
                    correction_count=2,
                    avg_latency_ms=1240.0,
                )
            ],
        )
        assert len(g.nodes) == 2
        assert len(g.edges) == 1
        assert g.edges[0].correction_rate == pytest.approx(0.25)
