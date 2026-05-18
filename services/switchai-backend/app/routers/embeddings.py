"""POST /v1/embeddings — OpenAI-compatible embeddings.

Mapping
-------
Request:
    input: str | list[str]    -> SwitchAI.embed(inputs)
    model: "<provider>/<m>"   -> get_client(provider, model)

SwitchAI EmbeddingResponse:
    .embeddings[*].index, .data   -> data[*].index, .embedding
    .usage.input_tokens           -> usage.prompt_tokens
    .usage.total_tokens           -> usage.total_tokens
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import EmbeddingData, EmbeddingRequest, EmbeddingResponse, EmbeddingUsage
from ..switch import get_client, resolve_model


router = APIRouter(prefix="/v1", tags=["embeddings"])


@router.post("/embeddings", response_model=EmbeddingResponse)
async def embeddings(req: EmbeddingRequest) -> EmbeddingResponse:
    provider, model_name = resolve_model(req.model)
    try:
        client = get_client(provider, model_name)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": {"message": str(e), "type": "invalid_request_error", "code": 400}},
        )

    try:
        er = client.embed(req.input)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error": {
                    "message": f"Upstream provider error: {e}",
                    "type": "upstream_error",
                    "code": 502,
                }
            },
        )

    data = [
        EmbeddingData(index=getattr(e, "index", i), embedding=list(getattr(e, "data", []) or []))
        for i, e in enumerate(getattr(er, "embeddings", []) or [])
    ]
    usage = getattr(er, "usage", None)
    return EmbeddingResponse(
        data=data,
        model=f"{provider}/{model_name}",
        usage=EmbeddingUsage(
            prompt_tokens=getattr(usage, "input_tokens", 0) or 0 if usage else 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0 if usage else 0,
        ),
    )
