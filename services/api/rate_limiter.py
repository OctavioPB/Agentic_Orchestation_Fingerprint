"""In-memory sliding-window rate limiter: 100 requests per minute per tenant."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

_WINDOW_SEC: float = 60.0
_LIMIT: int = 100

# tenant_id → deque of monotonic request timestamps within the current window
_windows: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(tenant_id: str) -> None:
    """Raise HTTP 429 if the tenant has exceeded 100 requests in the last 60 seconds.

    Uses a sliding window to avoid the boundary burst problem of fixed windows.
    Thread-safety: acceptable for single-process deployments; replace with Redis
    for multi-process/multi-instance production.
    """
    now = time.monotonic()
    window = _windows[tenant_id]

    # Evict timestamps that have fallen outside the window
    while window and now - window[0] > _WINDOW_SEC:
        window.popleft()

    if len(window) >= _LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {_LIMIT} requests per {int(_WINDOW_SEC)}s",
            headers={"Retry-After": str(int(_WINDOW_SEC))},
        )

    window.append(now)
