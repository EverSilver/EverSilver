"""Optional bearer-token middleware.

Active iff ``SWITCHAI_AUTH_TOKEN`` is set in the environment.

Rules:
    * ``/`` and ``/health`` are always public (liveness / probe).
    * Everything under ``/v1/`` requires ``Authorization: Bearer <token>``.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings


PUBLIC_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = get_settings().switchai_auth_token
        if not token:
            return await call_next(request)

        path = request.url.path
        if path in PUBLIC_PATHS or not path.startswith("/v1"):
            return await call_next(request)

        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "Missing bearer token.",
                        "type": "invalid_request_error",
                        "code": 401,
                    }
                },
            )
        presented = header.split(" ", 1)[1].strip()
        if presented != token:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "Invalid bearer token.",
                        "type": "invalid_request_error",
                        "code": 401,
                    }
                },
            )
        return await call_next(request)
