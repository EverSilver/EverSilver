"""POST /v1/chat/completions — OpenAI-compatible chat, sync + streaming.

Mapping summary
---------------
OpenAI request   ->  SwitchAI.chat(...) call
    messages     ->  messages (list of {role, content, ...} dicts; passed as-is)
    temperature  ->  temperature
    max_tokens   ->  max_tokens
    tools        ->  tools
    stream       ->  stream

SwitchAI ChatResponse  ->  OpenAI chat.completion
    .id                  ->  id
    .message.role        ->  choices[0].message.role
    .message.content     ->  choices[0].message.content
    .tool_calls[*]       ->  choices[0].message.tool_calls (re-shaped to OpenAI form)
    .finish_reason       ->  choices[0].finish_reason (normalized: completed->stop)
    .usage.input_tokens  ->  usage.prompt_tokens
    .usage.output_tokens ->  usage.completion_tokens
    .usage.total_tokens  ->  usage.total_tokens
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Iterable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatChoice,
    ChatMessageOut,
    Usage,
)
from ..switch import get_client, resolve_model


router = APIRouter(prefix="/v1", tags=["chat"])


# --- finish_reason normalization (SwitchAI -> OpenAI) ---
_FINISH_MAP = {
    "completed": "stop",
    "stop": "stop",
    "max_tokens": "length",
    "length": "length",
    "tool_calls": "tool_calls",
    "content_filter": "content_filter",
    None: "stop",
    "unknown": "stop",
}


def _map_finish(reason: Any) -> str:
    return _FINISH_MAP.get(reason, "stop")


def _map_tool_calls(tool_calls: Any) -> list[dict[str, Any]] | None:
    """SwitchAI ChatToolCall -> OpenAI tool_calls array."""
    if not tool_calls:
        return None
    out: list[dict[str, Any]] = []
    for tc in tool_calls:
        # tc may be a pydantic model (ChatToolCall) or a dict.
        if hasattr(tc, "model_dump"):
            d = tc.model_dump()
        elif isinstance(tc, dict):
            d = tc
        else:  # pragma: no cover
            continue
        fn = d.get("function", {}) or {}
        args = fn.get("arguments", {})
        if not isinstance(args, str):
            args = json.dumps(args, ensure_ascii=False)
        out.append(
            {
                "id": d.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                "type": d.get("type", "function"),
                "function": {"name": fn.get("name"), "arguments": args},
            }
        )
    return out or None


def _messages_to_dicts(messages) -> list[dict[str, Any]]:
    """Convert pydantic ChatMessageIn list to plain dicts SwitchAI accepts."""
    out: list[dict[str, Any]] = []
    for m in messages:
        d = m.model_dump(exclude_none=True)
        out.append(d)
    return out


@router.post("/chat/completions")
async def chat_completions(req: ChatCompletionRequest, request: Request):
    provider, model_name = resolve_model(req.model)

    try:
        client = get_client(provider, model_name)
    except ValueError as e:
        # Unsupported provider/model -> 400 with OpenAI error envelope.
        raise HTTPException(
            status_code=400,
            detail={"error": {"message": str(e), "type": "invalid_request_error", "code": 400}},
        )
    except Exception as e:  # pragma: no cover - misc init failures
        raise HTTPException(
            status_code=500,
            detail={"error": {"message": str(e), "type": "internal_error", "code": 500}},
        )

    messages = _messages_to_dicts(req.messages)
    resolved_model = f"{provider}/{model_name}"

    # --- Streaming path -----------------------------------------------------
    if req.stream:
        return StreamingResponse(
            _stream(client, messages, req, resolved_model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # --- Sync path ----------------------------------------------------------
    try:
        sr = client.chat(
            messages=messages,
            temperature=req.temperature if req.temperature is not None else 1.0,
            max_tokens=req.max_tokens,
            tools=req.tools,
            response_format=None,  # OpenAI's dict form isn't SwitchAI's Type[BaseModel]
            stream=False,
        )
    except Exception as e:
        # Upstream provider error -> 502 with OpenAI envelope.
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

    return _to_openai_response(sr, resolved_model)


def _to_openai_response(sr: Any, resolved_model: str) -> ChatCompletionResponse:
    msg = getattr(sr, "message", None)
    role = getattr(msg, "role", "assistant") if msg else "assistant"
    content = getattr(msg, "content", None) if msg else None
    usage = getattr(sr, "usage", None)
    return ChatCompletionResponse(
        id=getattr(sr, "id", None) or f"chatcmpl-{uuid.uuid4().hex}",
        created=int(time.time()),
        model=resolved_model,
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessageOut(
                    role=role or "assistant",
                    content=content,
                    tool_calls=_map_tool_calls(getattr(sr, "tool_calls", None)),
                ),
                finish_reason=_map_finish(getattr(sr, "finish_reason", None)),
            )
        ],
        usage=Usage(
            prompt_tokens=getattr(usage, "input_tokens", 0) or 0 if usage else 0,
            completion_tokens=getattr(usage, "output_tokens", 0) or 0 if usage else 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0 if usage else 0,
        ),
    )


def _stream(client, messages, req: ChatCompletionRequest, resolved_model: str) -> Iterable[bytes]:
    """Generator producing SSE bytes for chat.completion.chunk format."""
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())

    def _frame(delta: dict[str, Any], finish_reason: str | None = None) -> bytes:
        payload = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": resolved_model,
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "finish_reason": finish_reason,
                }
            ],
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

    # OpenAI clients expect the very first chunk to set the role.
    yield _frame({"role": "assistant", "content": ""})

    try:
        gen = client.chat(
            messages=messages,
            temperature=req.temperature if req.temperature is not None else 1.0,
            max_tokens=req.max_tokens,
            tools=req.tools,
            response_format=None,
            stream=True,
        )
    except Exception as e:
        err = {
            "error": {
                "message": f"Upstream provider error: {e}",
                "type": "upstream_error",
                "code": 502,
            }
        }
        yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
        yield b"data: [DONE]\n\n"
        return

    last_finish: Any = None
    try:
        for piece in gen:
            msg = getattr(piece, "message", None)
            content = getattr(msg, "content", None) if msg else None
            tcs = _map_tool_calls(getattr(piece, "tool_calls", None))
            delta: dict[str, Any] = {}
            if content:
                delta["content"] = content
            if tcs:
                delta["tool_calls"] = tcs
            if delta:
                yield _frame(delta)
            fr = getattr(piece, "finish_reason", None)
            if fr is not None:
                last_finish = fr
    except Exception as e:
        err = {
            "error": {
                "message": f"Upstream provider error: {e}",
                "type": "upstream_error",
                "code": 502,
            }
        }
        yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
        yield b"data: [DONE]\n\n"
        return

    yield _frame({}, finish_reason=_map_finish(last_finish))
    yield b"data: [DONE]\n\n"
