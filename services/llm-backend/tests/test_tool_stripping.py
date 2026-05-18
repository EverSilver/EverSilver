"""Models that don't support function calling must have `tools` stripped
before the request reaches the provider — otherwise Ollama returns a
hard 400 ("<model> does not support tools") and we lose the whole turn.
"""
from __future__ import annotations


def _fake_completion_recorder(monkeypatch):
    import litellm

    calls: list[dict] = []

    class _Resp:
        def model_dump(self):
            return {
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 1,
                "model": "x",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }

    def fake(**kw):
        calls.append(kw)
        return _Resp()

    monkeypatch.setattr(litellm, "completion", fake)
    return calls


_TOOL_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "search the web",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
        },
    }
]


def test_tools_stripped_for_gemma(client, monkeypatch):
    calls = _fake_completion_recorder(monkeypatch)
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "gemma3:1b-it-qat",
            "messages": [{"role": "user", "content": "hi"}],
            "tools": _TOOL_SPEC,
            "tool_choice": "auto",
        },
    )
    assert r.status_code == 200
    call = calls[0]
    assert "tools" not in call
    assert "tool_choice" not in call
    assert call["model"] == "ollama_chat/gemma3:1b-it-qat"


def test_tools_passed_through_for_openai(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    calls = _fake_completion_recorder(monkeypatch)
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "tools": _TOOL_SPEC,
            "tool_choice": "auto",
        },
    )
    assert r.status_code == 200
    call = calls[0]
    # OpenAI gpt-4o supports tools — must be forwarded unchanged.
    assert call.get("tools") == _TOOL_SPEC
    assert call.get("tool_choice") == "auto"
