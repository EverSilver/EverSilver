"""POST /v1/embeddings — OpenAI-compatible, backed by litellm.embedding."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException

from .. import litellm_client
from ..schemas import EmbeddingItem, EmbeddingRequest, EmbeddingResponse, EmbeddingUsage

router = APIRouter()


@router.post("/v1/embeddings", response_model=EmbeddingResponse)
def embeddings(req: EmbeddingRequest) -> EmbeddingResponse:
    inputs = req.input if isinstance(req.input, list) else [req.input]
    extra: dict = {}
    if req.dimensions is not None:
        extra["dimensions"] = req.dimensions
    if req.encoding_format:
        extra["encoding_format"] = req.encoding_format
    try:
        resp = litellm_client.embeddings(model=req.model, input=inputs, **extra)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "message": str(e),
                    "type": "upstream_error",
                    "code": 502,
                }
            },
        ) from e
    if hasattr(resp, "model_dump"):
        d = resp.model_dump()
    elif hasattr(resp, "dict"):
        d = resp.dict()
    else:
        d = dict(resp)
    raw_data = d.get("data") or []
    items: list[EmbeddingItem] = []
    for i, entry in enumerate(raw_data):
        vec = entry.get("embedding") if isinstance(entry, dict) else getattr(entry, "embedding", [])
        items.append(EmbeddingItem(index=i, embedding=list(vec or [])))
    usage_raw = d.get("usage") or {}
    return EmbeddingResponse(
        data=items,
        model=d.get("model") or req.model,
        usage=EmbeddingUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens", 0) or 0),
            total_tokens=int(usage_raw.get("total_tokens", 0) or 0),
        ),
    )
