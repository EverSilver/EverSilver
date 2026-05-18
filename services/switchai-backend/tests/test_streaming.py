"""SSE streaming chat chunk format."""

from __future__ import annotations

import json

from tests.conftest import FakeChatMessage


class _StreamChunk:
    def __init__(self, content=None, finish_reason=None):
        self.id = None
        self.message = FakeChatMessage(content=content) if content is not None else None
        self.tool_calls = None
        self.usage = None
        self.finish_reason = finish_reason


def test_chat_stream_sse_format(client, fake_switchai):
    # Make the chat() call return a generator instead of a single response.
    def _gen(*_a, **_kw):
        yield _StreamChunk(content="Hel")
        yield _StreamChunk(content="lo")
        yield _StreamChunk(content="!", finish_reason="completed")

    # First request to create the cached instance.
    client.post(
        "/v1/chat/completions",
        json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    fake_switchai[0].chat.side_effect = _gen

    with client.stream(
        "POST",
        "/v1/chat/completions",
        json={
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        raw = b"".join(r.iter_bytes()).decode("utf-8")

    # Must terminate with [DONE].
    assert raw.rstrip().endswith("data: [DONE]")

    # Parse the data: lines (excluding [DONE]).
    events = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data: "):
            continue
        payload = line[len("data: "):]
        if payload == "[DONE]":
            continue
        events.append(json.loads(payload))

    # First chunk should set role=assistant.
    assert events[0]["choices"][0]["delta"].get("role") == "assistant"
    # All chunks have chat.completion.chunk object.
    for ev in events:
        assert ev["object"] == "chat.completion.chunk"
        assert ev["model"] == "openai/gpt-4o-mini"
    # Content should be split across deltas.
    contents = [ev["choices"][0]["delta"].get("content", "") for ev in events]
    assert "Hel" in contents and "lo" in contents and "!" in contents
    # The final event before [DONE] should carry a finish_reason.
    assert events[-1]["choices"][0]["finish_reason"] == "stop"
