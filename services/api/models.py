"""Pydantic request/response schemas for the orchid REST API."""
from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class CreateSessionRequest(BaseModel):
    candidate_id: str
    scenario_id: str
    tenant_id: str = "default"


class SessionResponse(BaseModel):
    session_id: str
    candidate_id: str
    scenario_id: str
    tenant_id: str
    state: str
    started_at: str
    ended_at: str | None = None
    candidate_name: str | None = None


class EventsResponse(BaseModel):
    session_id: str
    events: list[dict]  # type: ignore[type-arg]  # heterogeneous event payloads
    total: int
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=500)


class ErrorResponse(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------


class CandidateRequest(BaseModel):
    email: str | None = None
    name: str | None = None


class CandidateResponse(BaseModel):
    candidate_id: str
    tenant_id: str
    email: str | None = None
    name: str | None = None
    created_at: str


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


class WebhookRequest(BaseModel):
    url: HttpUrl


class WebhookResponse(BaseModel):
    webhook_id: str
    tenant_id: str
    url: str
    active: bool
    created_at: str


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


class ScoringSignal(BaseModel):
    dimension: str
    signal: str


class ScenarioSummary(BaseModel):
    scenario_id: str
    name: str
    version: str = "v1"
    difficulty: str = "medium"
    description: str = ""
    chaos_component: str | None = None
    chaos_trigger_min: int | None = None
    max_duration_min: int | None = None
    violations_count: int | None = None
    expected_resolution_steps: int | None = None
    ai_solo_steps: int | None = None
    ai_solo_duration_sec: int | None = None
    ai_solo_violations_found: int | None = None
    scoring_signals: list[ScoringSignal] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Fingerprint (passthrough of OrchestraFingerprint fields)
# ---------------------------------------------------------------------------


class FingerprintResponse(BaseModel):
    session_id: str
    candidate_id: str
    scenario_id: str
    scores: dict  # type: ignore[type-arg]  # ScoreSet fields
    style_cluster: str | None = None
    reasoning_trace: list[str] = Field(default_factory=list)
    interaction_graph: dict  # type: ignore[type-arg]  # nodes + edges
    benchmark_delta: float | None = None
    report_markdown: str = ""
    assembled_at: str | None = None


# ---------------------------------------------------------------------------
# Admin / synthetic data
# ---------------------------------------------------------------------------


class TenantSummary(BaseModel):
    tenant_id: str
    session_count: int
    candidate_count: int


class SeedRequest(BaseModel):
    tenant_count: int = Field(default=3, ge=1, le=10)
    sessions_per_tenant: int = Field(default=2, ge=1, le=10)


class SeedResponse(BaseModel):
    tenants_created: int
    sessions_created: int
    fingerprints_created: int
    tenant_ids: list[str]


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------


class ModelCost(BaseModel):
    model: str
    tokens: int
    cost_usd: float


class CostResponse(BaseModel):
    session_id: str
    total_tokens: int
    estimated_cost_usd: float
    breakdown: list[ModelCost]
