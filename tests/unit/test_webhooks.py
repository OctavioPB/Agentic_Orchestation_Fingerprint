"""Unit tests for services/api/webhooks.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_app():
    from fastapi import FastAPI

    from services.api.auth import get_current_tenant
    from services.api.dependencies import get_db
    from services.api.webhooks import router

    app = FastAPI()
    app.include_router(router)

    def _fake_tenant():
        return "test-tenant"

    async def _fake_db():
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(fetchone=MagicMock(return_value=None)))
        db.commit = AsyncMock()
        yield db

    app.dependency_overrides[get_current_tenant] = _fake_tenant
    app.dependency_overrides[get_db] = _fake_db
    return app


class TestRegisterWebhook:
    def setup_method(self):
        self.app = _make_app()
        self.client = TestClient(self.app)

    def test_status_201(self):
        resp = self.client.post("/webhooks", json={"url": "https://example.com/hook"})
        assert resp.status_code == 201

    def test_response_fields(self):
        resp = self.client.post("/webhooks", json={"url": "https://example.com/hook"})
        data = resp.json()
        assert "webhook_id" in data
        assert data["active"] is True
        assert data["tenant_id"] == "test-tenant"
        assert "example.com" in data["url"]

    def test_unique_ids_per_registration(self):
        r1 = self.client.post("/webhooks", json={"url": "https://a.com/hook"})
        r2 = self.client.post("/webhooks", json={"url": "https://b.com/hook"})
        assert r1.json()["webhook_id"] != r2.json()["webhook_id"]

    def test_invalid_url_rejected(self):
        resp = self.client.post("/webhooks", json={"url": "not-a-url"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# deliver_fingerprint
# ---------------------------------------------------------------------------


class TestDeliverFingerprint:
    @pytest.mark.asyncio
    async def test_skips_when_session_not_found(self):
        """deliver_fingerprint should exit gracefully when session has no tenant."""
        from services.api.webhooks import deliver_fingerprint

        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(fetchone=MagicMock(return_value=None))
        )
        # Should not raise
        await deliver_fingerprint({"session_id": "ghost-session"}, db)

    @pytest.mark.asyncio
    async def test_posts_to_active_hooks(self):
        from services.api.webhooks import deliver_fingerprint

        db = AsyncMock()
        # First execute: sessions lookup → tenant
        # Second execute: webhooks lookup → list of hooks
        sessions_row = MagicMock(fetchone=MagicMock(return_value=("t1",)))
        hooks_row = MagicMock(
            fetchall=MagicMock(return_value=[("wh1", "https://target.example.com/hook")])
        )
        db.execute = AsyncMock(side_effect=[sessions_row, hooks_row])

        with patch("services.api.webhooks._post_with_retry", new=AsyncMock()) as mock_post:
            await deliver_fingerprint({"session_id": "s1", "scores": {}}, db)
            mock_post.assert_awaited_once()
            url_arg = mock_post.call_args[0][0]
            assert "target.example.com" in url_arg

    @pytest.mark.asyncio
    async def test_logs_error_and_continues_on_delivery_failure(self):
        from services.api.webhooks import deliver_fingerprint

        db = AsyncMock()
        sessions_row = MagicMock(fetchone=MagicMock(return_value=("t1",)))
        hooks_row = MagicMock(
            fetchall=MagicMock(return_value=[("wh1", "https://dead.example.com/hook")])
        )
        db.execute = AsyncMock(side_effect=[sessions_row, hooks_row])

        with patch(
            "services.api.webhooks._post_with_retry",
            new=AsyncMock(side_effect=Exception("connection refused")),
        ):
            # Should not raise — errors are swallowed
            await deliver_fingerprint({"session_id": "s1"}, db)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_allows_up_to_limit(self):
        from services.api.rate_limiter import _windows, check_rate_limit

        _windows.clear()
        for _ in range(100):
            check_rate_limit("rl-test-tenant")

    def test_raises_on_exceed(self):
        from fastapi import HTTPException

        from services.api.rate_limiter import _windows, check_rate_limit

        _windows.clear()
        for _ in range(100):
            check_rate_limit("rl-exceed-tenant")
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit("rl-exceed-tenant")
        assert exc_info.value.status_code == 429
