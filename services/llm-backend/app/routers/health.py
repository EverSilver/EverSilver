"""Liveness + service identification."""
from __future__ import annotations
import os
from fastapi import APIRouter

from .. import __version__
from ..config import load_models

router = APIRouter()


@router.get("/")
def root() -> dict:
    chat, embed = load_models()
    providers = sorted({m.model.split("/", 1)[0] for m in chat + embed})
    # Filter to providers whose keys are actually present.
    present = []
    for p in providers:
        if p in {"ollama_chat", "ollama"}:
            present.append("ollama")
            continue
        env_name = f"{p.upper()}_API_KEY"
        if os.environ.get(env_name):
            present.append(p)
    return {
        "name": "eversilver-llm-backend",
        "backend": "litellm",
        "version": __version__,
        "providers": sorted(set(present)),
    }


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
