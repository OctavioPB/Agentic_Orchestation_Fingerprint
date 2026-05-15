"""Pydantic request/response schemas for the orchid REST API."""
from __future__ import annotations

from pydantic import BaseModel, Field


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


class EventsResponse(BaseModel):
    session_id: str
    events: list[dict]  # type: ignore[type-arg]  # heterogeneous event payloads
    total: int
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=500)


class ErrorResponse(BaseModel):
    detail: str
