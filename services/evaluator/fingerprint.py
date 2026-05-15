"""OrchestraFingerprint — the final output of one assessment session.

This is the canonical domain model per CLAUDE.md §4.2. All five scores are
optional (None) at construction time; scoring logic (Sprint 7) fills them in.

``ChaosResilienceMarkers`` captures the raw timing signals needed by the
``chaos_resilience`` scorer. It lives here because it travels with the
fingerprint through the assembly pipeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Score set
# ---------------------------------------------------------------------------


class ScoreSet(BaseModel):
    """All five orchestration scores.

    Values are in [0, 1] when present. None means the scorer has not run yet.
    """

    efficiency_ratio: float | None = None
    trust_calibration: float | None = None
    correction_velocity: float | None = None
    decomposition_score: float | None = None
    chaos_resilience: float | None = None


# ---------------------------------------------------------------------------
# Chaos timing markers (input to chaos_resilience scorer in Sprint 7)
# ---------------------------------------------------------------------------


class ChaosResilienceMarkers(BaseModel):
    """Raw timing evidence collected around the chaos injection event.

    The scorer (Sprint 7) uses these timestamps to compute the score:
        chaos_resilience = f(first_response_latency, recovery_duration_sec,
                             scenario_median_recovery)
    """

    chaos_type: str
    chaos_injected_at: datetime
    first_response_at: datetime | None = None
    recovery_completed_at: datetime | None = None

    @property
    def first_response_latency_sec(self) -> float | None:
        if self.first_response_at is None:
            return None
        return (self.first_response_at - self.chaos_injected_at).total_seconds()

    @property
    def recovery_duration_sec(self) -> float | None:
        if self.recovery_completed_at is None:
            return None
        return (self.recovery_completed_at - self.chaos_injected_at).total_seconds()


# ---------------------------------------------------------------------------
# Interaction graph node / edge models
# ---------------------------------------------------------------------------


class GraphNode(BaseModel):
    id: str
    label: str
    node_type: Literal["human", "agent"]
    agent_name: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    message_count: int
    correction_count: int
    avg_latency_ms: float | None = None

    @property
    def correction_rate(self) -> float:
        if self.message_count == 0:
            return 0.0
        return self.correction_count / self.message_count


class InteractionGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Fingerprint
# ---------------------------------------------------------------------------


_StyleCluster = Literal["architect", "executor", "debugger", "delegator"]


class OrchestraFingerprint(BaseModel):
    """The complete orchestration fingerprint for one candidate session.

    Assembled by ``assemble_fingerprint()`` in Sprint 7. Fields are None until
    the corresponding pipeline stage runs. Persisted to Postgres and Neo4j.
    """

    session_id: str
    candidate_id: str
    scenario_id: str

    scores: ScoreSet = Field(default_factory=ScoreSet)

    # Raw chaos timing signals — populated at chaos injection time (Sprint 5)
    # Used by chaos_resilience scorer in Sprint 7
    chaos_markers: ChaosResilienceMarkers | None = None

    style_cluster: _StyleCluster | None = None

    # Reconstructed thought-tree from Shadow Agent (Sprint 7)
    reasoning_trace: list[str] = Field(default_factory=list)

    # Nodes + edges for dashboard rendering (Sprint 7 / Sprint 9)
    interaction_graph: InteractionGraph = Field(default_factory=InteractionGraph)

    # Cosine distance from senior engineer benchmark profiles (Sprint 6)
    benchmark_delta: float | None = None

    # Human-readable narrative (Sprint 7 — second LLM call)
    report_markdown: str | None = None

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_complete(self) -> bool:
        """True when all five scores and the style cluster are populated."""
        s = self.scores
        return all(
            v is not None
            for v in (
                s.efficiency_ratio,
                s.trust_calibration,
                s.correction_velocity,
                s.decomposition_score,
                s.chaos_resilience,
            )
        ) and self.style_cluster is not None

    def record_chaos_injection(
        self, chaos_type: str, injected_at: datetime
    ) -> None:
        """Called immediately after CHAOS_INJECTED event is emitted."""
        self.chaos_markers = ChaosResilienceMarkers(
            chaos_type=chaos_type,
            chaos_injected_at=injected_at,
        )

    def record_chaos_first_response(self, at: datetime) -> None:
        """Called when the first PROMPT_SENT arrives after CHAOS_INJECTED."""
        if self.chaos_markers is not None and self.chaos_markers.first_response_at is None:
            self.chaos_markers.first_response_at = at

    def record_chaos_recovery(self, at: datetime) -> None:
        """Called when the candidate signals the pipeline is back to normal."""
        if self.chaos_markers is not None:
            self.chaos_markers.recovery_completed_at = at
