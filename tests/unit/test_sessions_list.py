"""Unit tests for GET /sessions list endpoint."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient


def _row(session_id: str, state: str = "active") -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda self, i: [
        session_id,
        "cand-001",
        "scenario-pipeline-v1",
        "test-tenant",
        state,
        datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        None,
    ][i]
    return r


def _make_app(rows: list[MagicMock] | None = None):
    from fastapi import FastAPI

    from services.api.auth import get_current_tenant
    from services.api.dependencies import get_db
    from services.api.sessions import router

    app = FastAPI()
    app.include_router(router)

    def _fake_tenant():
        return "test-tenant"

    async def _fake_db():
        db = AsyncMock()
        result = MagicMock()
        result.fetchall = MagicMock(return_value=rows or [])
        db.execute = AsyncMock(return_value=result)
        yield db

    app.dependency_overrides[get_current_tenant] = _fake_tenant
    app.dependency_overrides[get_db] = _fake_db
    return app


class TestListSessions:
    def test_empty_returns_200(self):
        client = TestClient(_make_app(rows=[]))
        resp = client.get("/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_session_list(self):
        rows = [_row("sess-aaa", "completed"), _row("sess-bbb", "active")]
        client = TestClient(_make_app(rows=rows))
        resp = client.get("/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["session_id"] == "sess-aaa"
        assert data[0]["state"] == "completed"
        assert data[1]["session_id"] == "sess-bbb"

    def test_response_fields_present(self):
        rows = [_row("sess-xyz")]
        client = TestClient(_make_app(rows=rows))
        resp = client.get("/sessions")
        s = resp.json()[0]
        assert "session_id" in s
        assert "candidate_id" in s
        assert "scenario_id" in s
        assert "tenant_id" in s
        assert "state" in s
        assert "started_at" in s

    def test_ended_at_none_when_not_set(self):
        rows = [_row("sess-abc", "active")]
        client = TestClient(_make_app(rows=rows))
        resp = client.get("/sessions")
        assert resp.json()[0]["ended_at"] is None
