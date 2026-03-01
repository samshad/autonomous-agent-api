"""
Middleware that assigns a unique ``X-Request-ID`` to every inbound request,
binds it to structlog context vars (so every log line carries it), returns
it in the response header, and asynchronously persists a ``RequestLog`` row
to PostgreSQL for auditing / distributed tracing.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from agent_api.models.domain import RequestLog

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    1. Reads or generates ``X-Request-ID``.
    2. Binds it to structlog context vars for the duration of the request.
    3. Measures wall-clock duration.
    4. Persists a ``RequestLog`` row via the app-level ``DatabaseManager``.
    5. Returns the header to the caller.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # ── 1. Resolve or generate a request ID ─────────────────────────
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        # ── 2. Bind to structlog so every log line in this request scope
        #       automatically carries request_id ─────────────────────────
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Store on request.state so downstream code can access it
        request.state.request_id = request_id

        # ── 3. Execute the request and time it ──────────────────────────
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        # ── 4. Set the response header ──────────────────────────────────
        response.headers[REQUEST_ID_HEADER] = request_id

        # ── 5. Log the completed request ────────────────────────────────
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        # ── 6. Persist to DB (fire-and-forget via a fresh session) ──────
        await self._persist_log(
            request=request,
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        return response

    @staticmethod
    async def _persist_log(
        request: Request,
        request_id: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Write a RequestLog row using the app-level DatabaseManager.

        Uses its own session so it never interferes with the request's
        Unit-of-Work transaction.  Failures are swallowed and logged —
        observability must not break the user response.
        """
        try:
            db_manager = request.app.state.db_manager
            async with db_manager.session() as session:
                log_entry = RequestLog(
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    client_host=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                )
                session.add(log_entry)
                await session.commit()
        except Exception as exc:
            # Never let observability crash the response
            logger.warning("request_log_persist_failed", error=str(exc))
