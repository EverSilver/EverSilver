"""POST /v1/images/generations — OpenAI-compatible image generation.

SwitchAI returns ``ImageGenerationResponse.images`` as a list of PIL.Image
objects. We encode each as base64 PNG and emit them as ``b64_json`` (matches
OpenAI's ``response_format="b64_json"`` shape — the field is always populated
regardless of the requested response_format, since the provider may not
upload to a URL store).
"""

from __future__ import annotations

import base64
import io
import time

from fastapi import APIRouter, HTTPException

from ..schemas import ImageData, ImageRequest, ImageResponse
from ..switch import get_client, resolve_model


router = APIRouter(prefix="/v1", tags=["images"])


@router.post("/images/generations", response_model=ImageResponse)
async def images_generations(req: ImageRequest) -> ImageResponse:
    provider, model_name = resolve_model(req.model)
    try:
        client = get_client(provider, model_name)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": {"message": str(e), "type": "invalid_request_error", "code": 400}},
        )

    try:
        ir = client.generate_image(prompt=req.prompt, n=req.n or 1)
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

    out: list[ImageData] = []
    for img in getattr(ir, "images", []) or []:
        try:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            out.append(ImageData(b64_json=b64))
        except Exception:  # pragma: no cover
            # If it's already bytes/str, best-effort:
            if isinstance(img, (bytes, bytearray)):
                out.append(ImageData(b64_json=base64.b64encode(img).decode("ascii")))
            elif isinstance(img, str):
                out.append(ImageData(url=img))
    return ImageResponse(created=int(time.time()), data=out)
