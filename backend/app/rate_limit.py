"""
Kio Rate Limiting
In-process sliding-window limiter as a FastAPI dependency.

Suitable for single-process deployments (dev/beta). For multi-worker
production, replace the backing store with Redis -- the dependency
interface stays the same.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.config import settings

# key -> deque of request timestamps within the window
_hits: dict[str, deque[float]] = defaultdict(deque)
_WINDOW_SECONDS = 60.0


def rate_limit(scope: str, per_minute: int | None = None):
    """
    Dependency factory: limit requests per minute per client for a given scope.

    Keyed by authenticated user (Authorization header) when present,
    otherwise by client IP -- so unauthenticated login attempts are
    throttled per-IP and chat messages per-user.

    Usage:
        @router.post("/login", dependencies=[Depends(rate_limit("login", 10))])
    """
    limit = per_minute or settings.RATE_LIMIT_PER_MINUTE

    async def limiter(request: Request) -> None:
        auth = request.headers.get("authorization", "")
        client = auth or (request.client.host if request.client else "unknown")
        key = f"{scope}:{client}"

        now = time.monotonic()
        window = _hits[key]
        while window and now - window[0] > _WINDOW_SECONDS:
            window.popleft()

        if len(window) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait a moment and try again.",
                headers={"Retry-After": "60"},
            )

        window.append(now)

    return limiter
