import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse


_windows: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def _count_request(key: str, window_seconds: int = 60) -> int:
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        requests = _windows[key]
        while requests and requests[0] <= cutoff:
            requests.popleft()
        requests.append(now)
        return len(requests)


async def in_memory_rate_limit(request: Request, call_next):
    if request.url.path in {"/health", "/health/db", "/health/ready"}:
        return await call_next(request)

    client_host = request.client.host if request.client else "unknown"
    auth_route = request.url.path if request.url.path in {"/auth/login", "/auth/register"} else None
    is_ai_request = request.url.path.startswith(
        ("/orchestrator", "/rag", "/image", "/speech", "/studio", "/resources")
    )
    if auth_route:
        limit = 10
        category = auth_route.removeprefix("/auth/")
    elif is_ai_request:
        limit = 12
        category = "ai"
    else:
        limit = 120
        category = "api"
    key = f"rate:{client_host}:{category}"

    request_count = _count_request(key)

    if request_count > limit:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again shortly."},
            headers={"Retry-After": "60"},
        )
    return await call_next(request)


# FILE PURPOSE:
# Enforces per-process, per-IP API limits without an external service.
