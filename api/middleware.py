"""API middleware — request_id + structured JSON access log."""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_logger = logging.getLogger("finops.api.access")
if not _logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(h)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request_id, time the request, and emit a single-line JSON log.

    - Response carries `x-request-id` so clients can correlate logs.
    - Each access is a single JSON line on stdout (log aggregators pick it up).
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = rid
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            _logger.error(
                json.dumps(
                    {
                        "request_id": rid,
                        "method": request.method,
                        "path": request.url.path,
                        "status": 500,
                        "duration_ms": round(duration_ms, 2),
                        "error": repr(e),
                    },
                    default=str,
                )
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["x-request-id"] = rid
        _logger.info(
            json.dumps(
                {
                    "request_id": rid,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                }
            )
        )
        return response
