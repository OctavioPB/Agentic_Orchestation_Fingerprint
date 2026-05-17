"""Unit tests for services/api/auth.py."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from services.api.auth import (
    create_access_token,
    generate_api_key,
    get_current_tenant,
    hash_api_key,
    verify_access_token,
)

# ---------------------------------------------------------------------------
# Token round-trip
# ---------------------------------------------------------------------------


class TestCreateVerifyToken:
    def test_round_trip(self):
        token = create_access_token("acme")
        assert verify_access_token(token) == "acme"

    def test_different_tenants_produce_different_tokens(self):
        t1 = create_access_token("tenant-a")
        t2 = create_access_token("tenant-b")
        assert t1 != t2

    def test_invalid_token_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            verify_access_token("this.is.not.valid")
        assert exc_info.value.status_code == 401

    def test_tampered_token_raises_401(self):
        token = create_access_token("acme")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(HTTPException) as exc_info:
            verify_access_token(tampered)
        assert exc_info.value.status_code == 401

    def test_empty_token_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            verify_access_token("")
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# API key hashing
# ---------------------------------------------------------------------------


class TestHashApiKey:
    def test_deterministic(self):
        assert hash_api_key("my-key") == hash_api_key("my-key")

    def test_different_keys_different_hashes(self):
        assert hash_api_key("key-a") != hash_api_key("key-b")

    def test_returns_hex_string(self):
        h = hash_api_key("test-key")
        assert len(h) == 64
        int(h, 16)  # raises ValueError if not valid hex


class TestGenerateApiKey:
    def test_returns_two_strings(self):
        raw, hashed = generate_api_key()
        assert isinstance(raw, str)
        assert isinstance(hashed, str)

    def test_raw_starts_with_orchid_prefix(self):
        raw, _ = generate_api_key()
        assert raw.startswith("orchid_")

    def test_hash_matches_raw(self):
        raw, hashed = generate_api_key()
        assert hash_api_key(raw) == hashed

    def test_unique_per_call(self):
        raw1, _ = generate_api_key()
        raw2, _ = generate_api_key()
        assert raw1 != raw2


# ---------------------------------------------------------------------------
# get_current_tenant dependency
# ---------------------------------------------------------------------------


class TestGetCurrentTenant:
    @pytest.mark.asyncio
    async def test_valid_token_and_matching_header(self):
        token = create_access_token("tenant-x")
        tenant = await get_current_tenant(
            x_tenant_id="tenant-x",
            authorization=f"Bearer {token}",
        )
        assert tenant == "tenant-x"

    @pytest.mark.asyncio
    async def test_missing_bearer_prefix_raises_401(self):
        token = create_access_token("tenant-x")
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(
                x_tenant_id="tenant-x",
                authorization=token,  # missing "Bearer " prefix
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_mismatched_tenant_raises_403(self):
        token = create_access_token("tenant-a")
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(
                x_tenant_id="tenant-b",
                authorization=f"Bearer {token}",
            )
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(
                x_tenant_id="tenant-x",
                authorization="Bearer not.a.jwt",
            )
        assert exc_info.value.status_code == 401
