"""Unit tests for services/api/admin.py."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

_ADMIN_KEY = "dev-admin-secret"


def _make_app(db_rows: list | None = None, execute_side_effect=None):
    import os

    os.environ.setdefault("ADMIN_SECRET_KEY", _ADMIN_KEY)

    from fastapi import FastAPI

    from services.api.admin import router
    from services.api.dependencies import get_db

    app = FastAPI()
    app.include_router(router)

    async def _fake_db():
        db = AsyncMock()
        if execute_side_effect:
            db.execute = AsyncMock(side_effect=execute_side_effect)
        else:
            result = MagicMock()
            result.fetchall = MagicMock(return_value=db_rows or [])
            result.fetchone = MagicMock(return_value=(db_rows[0] if db_rows else None))
            db.execute = AsyncMock(return_value=result)
        db.commit = AsyncMock()
        yield db

    app.dependency_overrides[get_db] = _fake_db
    return app


class TestAdminAuth:
    def test_list_tenants_requires_admin_key(self):
        client = TestClient(_make_app())
        resp = client.get("/admin/tenants")
        assert resp.status_code == 403

    def test_list_tenants_wrong_key_denied(self):
        client = TestClient(_make_app())
        resp = client.get("/admin/tenants", headers={"X-Admin-Key": "wrong"})
        assert resp.status_code == 403

    def test_seed_requires_admin_key(self):
        client = TestClient(_make_app())
        resp = client.post("/admin/seed", json={"tenant_count": 1, "sessions_per_tenant": 1})
        assert resp.status_code == 403

    def test_delete_tenant_requires_admin_key(self):
        client = TestClient(_make_app())
        resp = client.delete("/admin/tenants/some-tenant")
        assert resp.status_code == 403


class TestListTenants:
    def _row(self, tenant_id: str, sessions: int, candidates: int):
        r = MagicMock()
        r.__getitem__ = lambda self, i: [tenant_id, sessions, candidates][i]
        return r

    def test_empty_returns_empty_list(self):
        client = TestClient(_make_app(db_rows=[]))
        resp = client.get("/admin/tenants", headers={"X-Admin-Key": _ADMIN_KEY})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_tenant_list(self):
        rows = [self._row("tenant-abc", 5, 5), self._row("tenant-xyz", 2, 2)]
        # Need fetchall to return rows
        app = _make_app()
        from services.api.dependencies import get_db

        async def _db_with_rows():
            db = AsyncMock()
            result = MagicMock()
            result.fetchall = MagicMock(return_value=rows)
            db.execute = AsyncMock(return_value=result)
            db.commit = AsyncMock()
            yield db

        app.dependency_overrides[get_db] = _db_with_rows
        client = TestClient(app)
        resp = client.get("/admin/tenants", headers={"X-Admin-Key": _ADMIN_KEY})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["tenant_id"] == "tenant-abc"
        assert data[0]["session_count"] == 5


class TestSeedData:
    def test_seed_returns_201(self):
        client = TestClient(_make_app())
        resp = client.post(
            "/admin/seed",
            json={"tenant_count": 2, "sessions_per_tenant": 1},
            headers={"X-Admin-Key": _ADMIN_KEY},
        )
        assert resp.status_code == 201

    def test_seed_response_fields(self):
        client = TestClient(_make_app())
        resp = client.post(
            "/admin/seed",
            json={"tenant_count": 2, "sessions_per_tenant": 2},
            headers={"X-Admin-Key": _ADMIN_KEY},
        )
        data = resp.json()
        assert data["tenants_created"] == 2
        assert data["sessions_created"] == 4
        assert data["fingerprints_created"] == 4
        assert len(data["tenant_ids"]) == 2

    def test_seed_tenant_ids_are_strings(self):
        client = TestClient(_make_app())
        resp = client.post(
            "/admin/seed",
            json={"tenant_count": 1, "sessions_per_tenant": 1},
            headers={"X-Admin-Key": _ADMIN_KEY},
        )
        ids = resp.json()["tenant_ids"]
        assert all(isinstance(i, str) for i in ids)
        assert all(i.startswith("tenant-") for i in ids)

    def test_seed_validates_tenant_count_range(self):
        client = TestClient(_make_app())
        resp = client.post(
            "/admin/seed",
            json={"tenant_count": 0, "sessions_per_tenant": 1},
            headers={"X-Admin-Key": _ADMIN_KEY},
        )
        assert resp.status_code == 422


class TestDeleteTenant:
    def test_delete_returns_204(self):
        client = TestClient(_make_app())
        resp = client.delete(
            "/admin/tenants/tenant-abc-123",
            headers={"X-Admin-Key": _ADMIN_KEY},
        )
        assert resp.status_code == 204

    def test_delete_commits_db(self):
        from fastapi import FastAPI

        from services.api.admin import router
        from services.api.dependencies import get_db

        committed = []

        async def _db():
            db = AsyncMock()
            db.execute = AsyncMock(return_value=MagicMock())
            db.commit = AsyncMock(side_effect=lambda: committed.append(1))
            yield db

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = _db

        client = TestClient(app)
        client.delete("/admin/tenants/t-abc", headers={"X-Admin-Key": _ADMIN_KEY})
        assert committed


class TestSessionCost:
    def test_cost_forbidden_without_key(self):
        client = TestClient(_make_app())
        resp = client.get("/admin/sessions/some-id/cost")
        assert resp.status_code == 403

    def test_cost_404_for_unknown_session(self):
        app = _make_app()
        from services.api.dependencies import get_db

        async def _db_empty():
            db = AsyncMock()
            result = MagicMock()
            result.fetchone = MagicMock(return_value=None)
            db.execute = AsyncMock(return_value=result)
            yield db

        app.dependency_overrides[get_db] = _db_empty
        client = TestClient(app)
        resp = client.get("/admin/sessions/bad-id/cost", headers={"X-Admin-Key": _ADMIN_KEY})
        assert resp.status_code == 404

    def test_cost_returns_breakdown(self):
        app = _make_app()
        from services.api.dependencies import get_db

        async def _db_found():
            db = AsyncMock()
            result = MagicMock()
            result.fetchone = MagicMock(return_value=("sess-001",))
            db.execute = AsyncMock(return_value=result)
            yield db

        app.dependency_overrides[get_db] = _db_found
        client = TestClient(app)
        resp = client.get("/admin/sessions/sess-001/cost", headers={"X-Admin-Key": _ADMIN_KEY})
        assert resp.status_code == 200
        data = resp.json()
        assert "total_tokens" in data
        assert "estimated_cost_usd" in data
        assert len(data["breakdown"]) == 3
        assert data["estimated_cost_usd"] < 1.0
