"""Unit tests for GDPR candidate purge — DELETE /candidates/{id}."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _make_app(candidate_row=None, session_rows=None):
    from fastapi import FastAPI

    from services.api.auth import get_current_tenant
    from services.api.candidates import router
    from services.api.dependencies import get_db

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_current_tenant] = lambda: "test-tenant"

    call_order: list[str] = []

    async def _fake_db():
        db = AsyncMock()

        def execute_side_effect(query, params=None):
            sql = str(query)
            result = MagicMock()
            if "SELECT candidate_id FROM candidates" in sql:
                result.fetchone = MagicMock(return_value=candidate_row)
            elif "SELECT session_id FROM sessions" in sql:
                result.fetchall = MagicMock(return_value=session_rows or [])
            else:
                result.fetchone = MagicMock(return_value=None)
                result.fetchall = MagicMock(return_value=[])
            call_order.append(sql[:40])
            return result

        db.execute = AsyncMock(side_effect=execute_side_effect)
        db.commit = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = _fake_db
    return app, call_order


class TestDeleteCandidate:
    def test_delete_not_found_returns_404(self):
        app, _ = _make_app(candidate_row=None)
        client = TestClient(app)
        resp = client.delete("/candidates/nonexistent-id")
        assert resp.status_code == 404

    def test_delete_existing_candidate_returns_204(self):
        app, _ = _make_app(candidate_row=("cand-001",), session_rows=[])
        client = TestClient(app)
        resp = client.delete("/candidates/cand-001")
        assert resp.status_code == 204

    def test_delete_purges_associated_sessions(self):
        sessions = [("sess-aaa",), ("sess-bbb",)]
        app, _ = _make_app(candidate_row=("cand-001",), session_rows=sessions)

        deleted_sessions: list[str] = []

        from services.api.auth import get_current_tenant
        from services.api.dependencies import get_db

        async def _tracking_db():
            db = AsyncMock()

            def execute_side_effect(query, params=None):
                sql = str(query)
                result = MagicMock()
                if "SELECT candidate_id FROM candidates" in sql:
                    result.fetchone = MagicMock(return_value=("cand-001",))
                elif "SELECT session_id FROM sessions" in sql:
                    result.fetchall = MagicMock(return_value=sessions)
                elif "DELETE FROM sessions" in sql:
                    deleted_sessions.append("sessions")
                    result.fetchone = MagicMock(return_value=None)
                else:
                    result.fetchone = MagicMock(return_value=None)
                    result.fetchall = MagicMock(return_value=[])
                return result

            db.execute = AsyncMock(side_effect=execute_side_effect)
            db.commit = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = _tracking_db

        with patch("services.api.cache.fingerprint_cache.delete"):
            client = TestClient(app)
            resp = client.delete("/candidates/cand-001")

        assert resp.status_code == 204
        assert deleted_sessions

    def test_delete_evicts_cache(self):
        sessions = [("sess-cache-001",)]
        app, _ = _make_app(candidate_row=("cand-x",), session_rows=sessions)

        evicted: list[str] = []

        with patch("services.api.cache.fingerprint_cache") as mock_cache:
            mock_cache.delete = MagicMock(side_effect=lambda k: evicted.append(k))
            client = TestClient(app)
            client.delete("/candidates/cand-x")

        assert any("sess-cache-001" in k for k in evicted)
