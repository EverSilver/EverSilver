"""POST /v1/audio/transcriptions — OpenAI-compatible speech-to-text.

SwitchAI's ``transcribe`` takes a filesystem path, so we save the uploaded
multipart blob to a temp file, call SwitchAI, then unlink in a ``finally``.
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..switch import get_client, resolve_model


router = APIRouter(prefix="/v1", tags=["audio"])


@router.post("/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(...),
    language: Optional[str] = Form(None),
    # OpenAI-compat extras accepted-but-ignored:
    prompt: Optional[str] = Form(None),  # noqa: ARG001
    response_format: Optional[str] = Form(None),  # noqa: ARG001
    temperature: Optional[float] = Form(None),  # noqa: ARG001
):
    provider, model_name = resolve_model(model)
    try:
        client = get_client(provider, model_name)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": {"message": str(e), "type": "invalid_request_error", "code": 400}},
        )

    suffix = os.path.splitext(file.filename or "audio")[1] or ".wav"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        try:
            content = await file.read()
            tmp.write(content)
            tmp.flush()
            tmp.close()
        except Exception as e:  # pragma: no cover
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "message": f"Failed to read upload: {e}",
                        "type": "invalid_request_error",
                        "code": 400,
                    }
                },
            )

        try:
            tr = client.transcribe(tmp.name, language=language)
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

        return {"text": getattr(tr, "text", "")}
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
