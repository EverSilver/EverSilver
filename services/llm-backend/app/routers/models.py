"""GET /v1/models — lists model entries from config.yaml whose required env
vars are present right now (so the list reflects what actually works)."""
from __future__ import annotations
import time
from fastapi import APIRouter

from ..config import available_models
from ..schemas import ModelInfo, ModelsListResponse

router = APIRouter()


@router.get("/v1/models", response_model=ModelsListResponse)
def list_models() -> ModelsListResponse:
    chat, embed = available_models()
    now = int(time.time())
    out: list[ModelInfo] = []
    for m in chat + embed:
        owner = m.model.split("/", 1)[0]
        if owner.startswith("ollama"):
            owner = "ollama"
        out.append(ModelInfo(id=m.name, created=now, owned_by=owner))
    return ModelsListResponse(data=out)
