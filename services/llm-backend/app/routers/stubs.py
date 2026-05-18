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


# ── Catch-all 200 for any other GET so the desktop doesn't error ───────
# Specific paths above take precedence (registered earlier on the
# router). Anything we haven't modelled gets an empty 200 — safer than
# letting the transport layer error and triggering the stale-connection
# banner.


@router.get("/{full_path:path}")
def stub_get_any(full_path: str) -> dict[str, Any]:
    return {"ok": True, "stub": True, "path": f"/{full_path}"}
