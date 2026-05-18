"""Liveness + identification.

GET /        -> ``{name, version, providers}``; Eversilver hits this for the
                runtime probe of a custom-inference endpoint.
GET /health  -> ``{status: "ok"}``.
"""

from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..config import get_settings


router = APIRouter()


@router.get("/")
async def root():
    return {
        "name": "switchai-backend",
        "version": __version__,
        "providers": get_settings().available_providers(),
    }


@router.get("/health")
async def health():
    return {"status": "ok"}
