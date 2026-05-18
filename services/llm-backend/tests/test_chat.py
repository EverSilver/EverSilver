"""Tests for POST /v1/chat/completions (non-streaming).

`litellm.completion` is monkey-patched so the tests don't touch the
network. We assert the request → litellm kwarg mapping (model name
resolved against registry, api_base injected, drop_params handled by
litellm itself) and the response normalization.
"""
from __future__ import annotations
from typing import Any

import pytest

from app import litellm_client


class _FakeMessage:
    def __init__(self, content: str):
        self.role = "assistant"
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.index = 0
        self.message = _FakeMessage(content)
        self.finish_reason = "stop"


class _FakeUsage:
    def __init__(self):
        self.prompt_tokens = 7
        self.completion_tokens = 3
        self.total_tokens = 10


class _FakeResponse:
    """Mimics litellm.ModelResponse — has model_dump()."""

    def __init__(self, content: str, model: str):
        self._content = content
        self._model = model

    def model_dump(self) -> dict:
        return {
            "id": "chatcmpl-fake-001",
            "object": "chat.completion",
            "created": 1700000000,
            "model": self._model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": self._content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
        }


@pytest.fixture()
def captured_calls(monkeypatch):
    """Replace litellm.completion with a recorder; return the call list."""
    calls: list[dict[str, Any]] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _FakeResponse("Hello from fake LLM.", kwargs.get("model", "?"))

    import litellm

    monkeypatch.setattr(litellm, "completion", fake_completion)
    return calls


def test_chat_completion_resolves_registry_model(client, captured_calls):
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "gemma3:1b-it-qat",
            "messages": [{"role": "user", "content": "Ping"}],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "Hello from fake LLM."
    assert body["model"] == "ollama_chat/gemma3:1b-it-qat"
    assert body["usage"]["total_tokens"] == 10

    # One upstream call, with resolved model and api_base injected.
    assert len(captured_calls) == 1
    call = captured_calls[0]
    assert call["model"] == "ollama_chat/gemma3:1b-it-qat"
    assert call["api_base"] == "http://localhost:11434"
    assert call["stream"] is False
    assert call["messages"] == [{"role": "user", "content": "Ping"}]


def test_chat_completion_passes_through_unknown_model(client, captured_calls):
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "openai/gpt-4o",  # not in registry — raw passthrough
            "messages": [{"role": "user", "content": "Hi"}],
            "temperature": 0.3,
            "max_tokens": 64,
        },
    )
    assert r.status_code == 200, r.text
    call = captured_calls[0]
    assert call["model"] == "openai/gpt-4o"
    assert "api_base" not in call  # nothing injected for unknown
    assert call["temperature"] == 0.3
    assert call["max_tokens"] == 64


def test_chat_completion_upstream_error_is_502(client, monkeypatch):
    import litellm

    def boom(**_):
        raise RuntimeError("ollama unreachable")

    monkeypatch.setattr(litellm, "completion", boom)
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "gemma3:1b-it-qat",
            "messages": [{"role": "user", "content": "Ping"}],
        },
    )
    assert r.status_code == 502
    err = r.json()["detail"]["error"]
    assert err["type"] == "upstream_error"
    assert "ollama unreachable" in err["message"]


def test_chat_completion_normalizes_missing_fields(client, monkeypatch):
    """A LiteLLM response missing id/created/usage should still come back
    as a well-formed OpenAI chat.completion object."""

    class _Bare:
        def model_dump(self):
            return {
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ]
            }

    import litellm

    monkeypatch.setattr(litellm, "completion", lambda **kw: _Bare())
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "gemma3:1b-it-qat",
            "messages": [{"role": "user", "content": "Ping"}],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "chat.completion"
    assert body["id"].startswith("chatcmpl-")
    assert body["created"] > 0
    # When upstream omits `model`, we fall back to the requested name.
    assert body["model"] == "gemma3:1b-it-qat"
    assert body["usage"]["total_tokens"] == 0
