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


def note_failure(scope: str, identity: str, limit: int) -> None:
    """
    Record a failed attempt against one identity, and refuse once too many.

    Separate from `rate_limit` because the thing being counted is different:
    that limiter counts *requests from a client*, this counts *failures against
    an account*. Kio is used from school networks where a whole year group
    shares one public IP, so an IP-keyed limit either locks out a classroom or
    is too loose to stop guessing. Keying on the targeted account instead makes
    the limit independent of how many students sit behind one router.

    Only failures are recorded, so someone signing in correctly is never
    throttled however busy their school is. The window is the same rolling
    minute as `rate_limit`, and the counter is in-process -- see the topology
    note in docs/production-configuration.md.
    """
    key = f"fail:{scope}:{identity}"
    now = time.monotonic()
    window = _hits[key]
    while window and now - window[0] > _WINDOW_SECONDS:
        window.popleft()

    window.append(now)
    if len(window) > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts for this account. Please wait a minute.",
            headers={"Retry-After": "60"},
        )


def clear_failures(scope: str, identity: str) -> None:
    """Forget an identity's failures after a success."""
    _hits.pop(f"fail:{scope}:{identity}", None)


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
