"""Optional bearer-token middleware.

When `LLM_BACKEND_AUTH_TOKEN` is set, every `/v1/*` request must carry
`Authorization: Bearer <that-token>`. When unset, the backend is open —
appropriate for a localhost-bound proxy. `/health` and `/` are always
public.
"""
from __future__ import annotations
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/v1/"):
            return await call_next(request)
        token = get_settings().auth_token
        if not token:
            return await call_next(request)
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or header[7:].strip() != token:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "Missing or invalid Authorization header.",
                        "type": "invalid_request_error",
                        "code": 401,
                    }
                },
            )
        return await call_next(request)
