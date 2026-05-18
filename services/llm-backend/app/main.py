"""FastAPI app + uvicorn entrypoint."""
from __future__ import annotations
import os
from pathlib import Path

from fastapi import FastAPI

# Load .env (if python-dotenv is installed). pydantic-settings also reads
# .env via its `env_file` config, but loading explicitly here ensures
# `os.environ` is populated before LiteLLM's lazy module-level reads.
try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
except ImportError:
    load_dotenv = None  # type: ignore[assignment]

if load_dotenv is not None:
    for _candidate in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if _candidate.exists():
            try:
                load_dotenv(_candidate)
                break
            except Exception:
                pass

from .auth import BearerAuthMiddleware  # noqa: E402
from .routers import chat, embeddings, health, models  # noqa: E402


def create_app() -> FastAPI:
    app = FastAPI(
        title="Eversilver LLM Backend",
        description="OpenAI-compatible LLM proxy, backed by LiteLLM.",
        version="0.1.0",
    )
    app.add_middleware(BearerAuthMiddleware)
    app.include_router(health.router)
    app.include_router(models.router)
    app.include_router(chat.router)
    app.include_router(embeddings.router)
    return app


app = create_app()


def cli() -> None:  # entrypoint for `eversilver-llm-backend`
    import uvicorn

    from .config import get_settings

    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host=s.bind_host,
        port=s.bind_port,
        log_level=s.log_level,
        reload=False,
    )


if __name__ == "__main__":  # pragma: no cover
    cli()
