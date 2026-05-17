"""In-memory TTL cache for fingerprint responses (1-hour TTL).

Production note: swap for Redis via `redis.asyncio` when running
multiple API process replicas. The interface is intentionally kept
compatible: get/set/delete/clear_tenant.
"""
from __future__ import annotations

import time
from typing import Any


class InMemoryTTLCache:
    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (value, time.monotonic() + self._ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear_tenant(self, tenant_id: str) -> int:
        prefix = f"fp:{tenant_id}:"
        stale = [k for k in self._store if k.startswith(prefix)]
        for k in stale:
            del self._store[k]
        return len(stale)

    def __len__(self) -> int:
        return len(self._store)


# Module-level singleton used across the API process
fingerprint_cache = InMemoryTTLCache(ttl_seconds=3600)
