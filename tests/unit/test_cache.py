"""Unit tests for services/api/cache.py."""
from __future__ import annotations

import time

from services.api.cache import InMemoryTTLCache


class TestInMemoryTTLCache:
    def test_set_and_get(self):
        cache = InMemoryTTLCache(ttl_seconds=60)
        cache.set("key1", {"data": 42})
        assert cache.get("key1") == {"data": 42}

    def test_missing_key_returns_none(self):
        cache = InMemoryTTLCache(ttl_seconds=60)
        assert cache.get("nonexistent") is None

    def test_expired_entry_returns_none(self):
        cache = InMemoryTTLCache(ttl_seconds=0)
        cache.set("k", "v")
        time.sleep(0.01)
        assert cache.get("k") is None

    def test_delete_removes_entry(self):
        cache = InMemoryTTLCache(ttl_seconds=60)
        cache.set("k", "v")
        cache.delete("k")
        assert cache.get("k") is None

    def test_delete_nonexistent_is_noop(self):
        cache = InMemoryTTLCache(ttl_seconds=60)
        cache.delete("does-not-exist")  # no exception

    def test_clear_tenant_removes_matching_keys(self):
        cache = InMemoryTTLCache(ttl_seconds=60)
        cache.set("fp:tenant-a:sess-1", "data1")
        cache.set("fp:tenant-a:sess-2", "data2")
        cache.set("fp:tenant-b:sess-3", "data3")
        count = cache.clear_tenant("tenant-a")
        assert count == 2
        assert cache.get("fp:tenant-a:sess-1") is None
        assert cache.get("fp:tenant-a:sess-2") is None
        assert cache.get("fp:tenant-b:sess-3") == "data3"

    def test_clear_tenant_returns_zero_when_no_match(self):
        cache = InMemoryTTLCache(ttl_seconds=60)
        assert cache.clear_tenant("nonexistent-tenant") == 0

    def test_len_reflects_entries(self):
        cache = InMemoryTTLCache(ttl_seconds=60)
        assert len(cache) == 0
        cache.set("a", 1)
        cache.set("b", 2)
        assert len(cache) == 2

    def test_overwrite_existing_key(self):
        cache = InMemoryTTLCache(ttl_seconds=60)
        cache.set("k", "old")
        cache.set("k", "new")
        assert cache.get("k") == "new"
