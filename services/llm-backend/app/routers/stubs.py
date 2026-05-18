"""Stub endpoints that absorb Eversilver's auxiliary backend traffic.

The Eversilver desktop app polls a number of hosted-service endpoints
(auth/me, payments/stripe/currentPlan, teams/me/usage,
agent-integrations/composio/*, openai/v1/models, /api/release/latest) that
were originally served by `api.eversilver.local`. With that host gone,
each poll produces a transport error every 5–30 seconds — visible in
the UI as the "Connections are showing stale status" banner and as
hundreds of WARN lines per minute in the log.

Pointing `config.api_url` at this backend and registering these stubs
returns a sensible empty/no-op shape for every poll, so the desktop UI
treats the backend as healthy and the noise disappears. None of these
endpoints are load-bearing for chat — they exist purely to keep the
app's optional integrations / billing / telemetry surfaces quiet for
the local-only configuration.

If the user ever wires up a real upstream, just point `api_url` at it
and these stubs become unreachable.
"""
from __future__ import annotations
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


# ── Identity / session ─────────────────────────────────────────────────


@router.get("/auth/me")
def auth_me() -> dict[str, Any]:
    """Returns the local placeholder user. The desktop app treats this
    as the source of truth for display_name + email; the rest of the
    fields are tolerated as-null."""
    return {
        "id": "local-user",
        "email": "local@eversilver.local",
        "display_name": "Local User",
        "avatar_url": None,
        "local": True,
        "workspace_id": None,
        "team_id": None,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


# ── Billing / quotas ───────────────────────────────────────────────────


@router.get("/teams/me/usage")
def teams_me_usage() -> dict[str, Any]:
    return {
        "tokens_used": 0,
        "tokens_limit": None,
        "messages_used": 0,
        "messages_limit": None,
        "period_start": "2024-01-01T00:00:00Z",
        "period_end": "2099-12-31T23:59:59Z",
        "tier": "local",
    }


@router.get("/payments/stripe/currentPlan")
def stripe_current_plan() -> dict[str, Any]:
    return {
        "plan": "local",
        "status": "active",
        "renews_at": None,
        "cancelled_at": None,
        "trial_ends_at": None,
        "price_id": None,
    }


# ── Composio / integrations ────────────────────────────────────────────


@router.get("/agent-integrations/composio/toolkits")
def composio_toolkits() -> dict[str, Any]:
    return {"toolkits": [], "total": 0}


@router.get("/agent-integrations/composio/connections")
def composio_connections() -> dict[str, Any]:
    return {"connections": [], "total": 0}


@router.get("/agent-integrations/composio/categories")
def composio_categories() -> dict[str, Any]:
    return {"categories": []}


# ── Releases / update channel ──────────────────────────────────────────


@router.get("/api/release/latest")
def release_latest() -> dict[str, Any]:
    return {
        "version": "0.0.0-local",
        "url": None,
        "notes": "Local build — no remote release channel.",
        "published_at": "2024-01-01T00:00:00Z",
    }


# ── Cloud-model proxy passthrough ──────────────────────────────────────
# The hosted Eversilver API used `/openai/v1/...` as the path prefix.
# Surfacing the same paths here means the `EversilverBackendProvider`
# (a separate code path from `provider:cloud`) works unchanged when the
# user repoints `api_url` to this backend.


@router.get("/openai/v1/models")
async def openai_v1_models(request: Request) -> Any:
    from .models import list_models  # local import avoids router-cycle

    return list_models()


@router.post("/openai/v1/chat/completions")
async def openai_v1_chat(request: Request) -> Any:
    from .chat import chat_completion
    from ..schemas import ChatRequest

    body = await request.json()
    req = ChatRequest(**body)
    return chat_completion(req)


@router.post("/openai/v1/embeddings")
async def openai_v1_embeddings(request: Request) -> Any:
    from .embeddings import embeddings as embed_fn
    from ..schemas import EmbeddingRequest

    body = await request.json()
    req = EmbeddingRequest(**body)
    return embed_fn(req)


# ── Audio: transcription (STT) and speech (TTS) ────────────────────────
# Eversilver's push-to-talk path POSTs to /openai/v1/audio/transcriptions
# with multipart/form-data (file, model, response_format). We route the
# request through LiteLLM so any provider with a transcription model
# (OpenAI whisper-1, Groq whisper-large-v3, Deepgram, etc.) Just Works
# when its env var is present. With no key configured, return a clear
# 503 instead of a generic 'backend transcription request failed'.


@router.post("/openai/v1/audio/transcriptions")
async def openai_v1_audio_transcriptions(request: Request) -> Any:
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse
    import litellm
    import os
    import tempfile
    from pathlib import Path

    form = await request.form()
    upload = form.get("file")
    if upload is None:
        raise HTTPException(status_code=400, detail="missing 'file' field")
    requested = (form.get("model") or "whisper-1").strip()
    response_format = (form.get("response_format") or "json").strip()
    language = form.get("language")
    prompt = form.get("prompt")
    temperature = form.get("temperature")

    # Pick the first transcription model whose env var is configured.
    candidates: list[tuple[str, str]] = [
        ("OPENAI_API_KEY", "whisper-1"),
        ("GROQ_API_KEY", "groq/whisper-large-v3"),
        ("DEEPGRAM_API_KEY", "deepgram/nova-3"),
    ]
    chosen: str | None = None
    if requested and requested != "whisper-1":
        chosen = requested
    else:
        for env_var, model in candidates:
            if os.environ.get(env_var):
                chosen = model
                break

    if not chosen:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "message": (
                        "No speech-to-text provider configured. Set OPENAI_API_KEY, "
                        "GROQ_API_KEY, or DEEPGRAM_API_KEY in services/llm-backend/.env "
                        "and restart the backend."
                    ),
                    "type": "configuration_error",
                    "code": 503,
                }
            },
        )

    raw = await upload.read()
    suffix = Path(getattr(upload, "filename", "audio.webm")).suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(raw)
        tmp_path = f.name
    try:
        kwargs: dict[str, Any] = {"model": chosen, "response_format": response_format}
        if language:
            kwargs["language"] = language
        if prompt:
            kwargs["prompt"] = prompt
        if temperature:
            try:
                kwargs["temperature"] = float(temperature)
            except (TypeError, ValueError):
                pass
        with open(tmp_path, "rb") as fh:
            resp = litellm.transcription(file=fh, **kwargs)
    except Exception as e:  # pragma: no cover - upstream failure shape varies
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": f"transcription failed: {e}",
                    "type": "upstream_error",
                    "code": 502,
                }
            },
        )
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass

    if hasattr(resp, "model_dump"):
        out = resp.model_dump()
    elif hasattr(resp, "dict"):
        out = resp.dict()
    elif isinstance(resp, dict):
        out = resp
    else:
        out = {"text": str(resp)}
    out.setdefault("text", "")
    return out


@router.post("/openai/v1/audio/speech")
async def openai_v1_audio_speech(request: Request) -> Any:
    """TTS — OpenAI text-to-speech via LiteLLM. Streams audio bytes back.

    Returns 503 with a clear message when no TTS provider key is present
    rather than the generic 'backend request failed' banner.
    """
    from fastapi.responses import JSONResponse, Response
    import litellm
    import os

    body = await request.json()
    text = (body.get("input") or body.get("text") or "").strip()
    voice = body.get("voice") or "alloy"
    model = body.get("model") or "tts-1"
    response_format = body.get("response_format") or "mp3"

    if not text:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "missing 'input'", "type": "invalid_request"}},
        )
    if not os.environ.get("OPENAI_API_KEY"):
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "message": (
                        "No text-to-speech provider configured. Set OPENAI_API_KEY "
                        "in services/llm-backend/.env and restart the backend."
                    ),
                    "type": "configuration_error",
                    "code": 503,
                }
            },
        )
    try:
        resp = litellm.speech(
            model=model, voice=voice, input=text, response_format=response_format
        )
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": f"speech synthesis failed: {e}",
                    "type": "upstream_error",
                    "code": 502,
                }
            },
        )
    audio_bytes = getattr(resp, "content", None) or bytes(resp)
    media = "audio/mpeg" if response_format == "mp3" else f"audio/{response_format}"
    return Response(content=audio_bytes, media_type=media)


# ── Catch-all 200 for any other GET so the desktop doesn't error ───────
# Specific paths above take precedence (registered earlier on the
# router). Anything we haven't modelled gets an empty 200 — safer than
# letting the transport layer error and triggering the stale-connection
# banner.


@router.get("/{full_path:path}")
def stub_get_any(full_path: str) -> dict[str, Any]:
    return {"ok": True, "stub": True, "path": f"/{full_path}"}
