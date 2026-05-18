"""POST /v1/chat/completions — OpenAI-compatible, backed by litellm.

Non-streaming: returns a single `chat.completion` JSON.
Streaming (`stream: true`): server-sent events of `chat.completion.chunk`
objects, terminated by `data: [DONE]\\n\\n`.
"""
from __future__ import annotations
import json
import time
from typing import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .. import litellm_client
from ..schemas import ChatChoice, ChatMessage, ChatRequest, ChatResponse, ChatUsage

router = APIRouter()


def _request_to_dict_messages(req: ChatRequest) -> list[dict]:
    """Pydantic ChatMessages → dicts that LiteLLM accepts."""
    out = []
    for m in req.messages:
        msg: dict = {"role": m.role}
        if m.content is not None:
            msg["content"] = m.content
        if m.name:
            msg["name"] = m.name
        if m.tool_call_id:
            msg["tool_call_id"] = m.tool_call_id
        if m.tool_calls:
            msg["tool_calls"] = m.tool_calls
        out.append(msg)
    return out


def _extract_kwargs(req: ChatRequest) -> dict:
    """Pull through the request fields LiteLLM understands, dropping None."""
    raw = req.model_dump(exclude_none=True)
    for drop in ("model", "messages", "stream"):
        raw.pop(drop, None)
    return raw


@router.post("/v1/chat/completions")
def chat_completion(req: ChatRequest):
    messages = _request_to_dict_messages(req)
    extra = _extract_kwargs(req)
    if req.stream:
        return StreamingResponse(
            _stream(req.model, messages, extra),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        resp = litellm_client.chat_completion(
            model=req.model, messages=messages, stream=False, **extra
        )
    except Exception as e:  # pragma: no cover - covered by error tests
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

    # litellm returns a `ModelResponse` that behaves like the OpenAI SDK
    # object — `.choices[i].message.content`, `.usage.prompt_tokens`, etc.
    return _model_response_to_dict(resp, req.model)


def _model_response_to_dict(resp, requested_model: str) -> dict:
    """Normalize LiteLLM's `ModelResponse` to a plain dict matching OpenAI."""
    # `ModelResponse` may already serialize cleanly via .model_dump() / .dict()
    if hasattr(resp, "model_dump"):
        d = resp.model_dump()
    elif hasattr(resp, "dict"):
        d = resp.dict()
    else:
        d = dict(resp)
    # Ensure the OpenAI envelope is intact even if LiteLLM omits some fields.
    d.setdefault("object", "chat.completion")
    d.setdefault("id", f"chatcmpl-{int(time.time() * 1000)}")
    d.setdefault("created", int(time.time()))
    d["model"] = d.get("model") or requested_model
    d.setdefault("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    if not d.get("choices"):
        d["choices"] = [
            {
                "index": 0,
                "message": {"role": "assistant", "content": ""},
                "finish_reason": "stop",
            }
        ]
    return d


def _stream(model: str, messages: list[dict], extra: dict) -> Iterator[bytes]:
    """Generator that yields SSE-formatted OpenAI chunk frames + [DONE]."""
    try:
        gen = litellm_client.chat_completion(
            model=model, messages=messages, stream=True, **extra
        )
    except Exception as e:
        err = {
            "error": {
                "message": str(e),
                "type": "upstream_error",
                "code": 502,
            }
        }
        yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
        yield b"data: [DONE]\n\n"
        return

    try:
        for chunk in gen:
            if hasattr(chunk, "model_dump"):
                payload = chunk.model_dump()
            elif hasattr(chunk, "dict"):
                payload = chunk.dict()
            else:
                payload = dict(chunk)
            payload.setdefault("object", "chat.completion.chunk")
            payload["model"] = payload.get("model") or model
            yield f"data: {json.dumps(payload)}\n\n".encode("utf-8")
        yield b"data: [DONE]\n\n"
    except Exception as e:  # pragma: no cover
        err = {"error": {"message": str(e), "type": "upstream_error", "code": 502}}
        yield f"data: {json.dumps(err)}\n\n".encode("utf-8")
        yield b"data: [DONE]\n\n"
