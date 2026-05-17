"""Unit tests for services/api/candidates.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient


def _make_app():
    """Build a minimal FastAPI app with the candidates router and overridden deps."""
    from fastapi import FastAPI

    from services.api.auth import get_current_tenant
    from services.api.candidates import router
    from services.api.dependencies import get_db

    app = FastAPI()
    app.include_router(router)

    # Dependency overrides — no real DB, no real JWT
    def _fake_tenant():
        return "test-tenant"

    async def _fake_db():
        db = AsyncMock()
        # execute() returns an object with fetchone()
        db.execute = AsyncMock(return_value=MagicMock(fetchone=MagicMock(return_value=None)))
        db.commit = AsyncMock()
        yield db

    app.dependency_overrides[get_current_tenant] = _fake_tenant
    app.dependency_overrides[get_db] = _fake_db
    return app


class TestRegisterCandidate:
    def setup_method(self):
        self.app = _make_app()
        self.client = TestClient(self.app)

    def test_status_201(self):
        resp = self.client.post("/candidates", json={})
        assert resp.status_code == 201

    def test_response_contains_candidate_id(self):
        resp = self.client.post("/candidates", json={})
        data = resp.json()
        assert "candidate_id" in data
        assert len(data["candidate_id"]) == 36  # UUID4

    def test_tenant_id_set_from_dependency(self):
        resp = self.client.post("/candidates", json={})
        assert resp.json()["tenant_id"] == "test-tenant"

    def test_email_and_name_forwarded(self):
        resp = self.client.post(
            "/candidates", json={"email": "a@b.com", "name": "Alice"}
        )
        data = resp.json()
        assert data["email"] == "a@b.com"
        assert data["name"] == "Alice"

    def test_empty_body_accepted(self):
        resp = self.client.post("/candidates", json={})
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] is None
        assert data["name"] is None

    def test_unique_ids_per_call(self):
        r1 = self.client.post("/candidates", json={})
        r2 = self.client.post("/candidates", json={})
        assert r1.json()["candidate_id"] != r2.json()["candidate_id"]


class TestGetCandidate:
    def test_not_found_returns_404(self):
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/candidates/nonexistent-id")
        assert resp.status_code == 404
