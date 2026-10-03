import logging
import time
from uuid import UUID, uuid4


logger = logging.getLogger("app.http")


class RequestObservabilityMiddleware:
    """Attach a safe request ID and log HTTP completion without request data."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        started_at = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            logger.error(
                "HTTP request failed",
                extra={
                    "request_id": request_id,
                    "method": scope.get("method", ""),
                    "path": scope.get("path", ""),
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "error_type": type(exc).__name__,
                },
            )
            raise

        logger.info(
            "HTTP request completed",
            extra={
                "request_id": request_id,
                "method": scope.get("method", ""),
                "path": scope.get("path", ""),
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            },
        )

    @staticmethod
    def _request_id(scope) -> str:
        headers = dict(scope.get("headers", []))
        candidate = headers.get(b"x-request-id", b"").decode("ascii", errors="ignore")
        try:
            return str(UUID(candidate))
        except (ValueError, AttributeError):
            return str(uuid4())


# FILE PURPOSE:
# Adds validated request correlation IDs and privacy-conscious HTTP
# completion/error logs, including the full duration of streamed responses.
