"""FastAPI app factory + uvicorn entrypoint.

Run:
    uvicorn app.main:app --host 127.0.0.1 --port 8088
or:
    switchai-backend                # uses values from .env / env vars
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .auth import BearerAuthMiddleware
from .config import get_settings
from .routers import audio as audio_router
from .routers import chat as chat_router
from .routers import embeddings as embeddings_router
from .routers import health as health_router
from .routers import images as images_router
from .routers import models as models_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="switchai-backend",
        version=__version__,
        description="OpenAI-compatible HTTP gateway wrapping the SwitchAI library.",
    )

    app.add_middleware(BearerAuthMiddleware)

    app.include_router(health_router.router)
    app.include_router(chat_router.router)
    app.include_router(embeddings_router.router)
    app.include_router(audio_router.router)
    app.include_router(images_router.router)
    app.include_router(models_router.router)

    # --- Error normalization: always emit OpenAI-shaped error envelopes. -----

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(_: Request, exc: StarletteHTTPException):
        # If the detail is already an OpenAI envelope, pass through.
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "message": str(exc.detail),
                    "type": "invalid_request_error",
                    "code": exc.status_code,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "message": "Request validation failed.",
                    "type": "invalid_request_error",
                    "code": 422,
                    "param": str(exc.errors()),
                }
            },
        )

    return app


app = create_app()


def cli() -> None:
    """Console-script entrypoint registered in pyproject.toml."""
    import uvicorn

    s = get_settings()
    host = os.environ.get("SWITCHAI_HOST", s.switchai_host)
    port = int(os.environ.get("SWITCHAI_PORT", s.switchai_port))
    uvicorn.run("app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":  # pragma: no cover
    cli()
