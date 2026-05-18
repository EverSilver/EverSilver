"""Tests for SSE streaming on POST /v1/chat/completions."""
from __future__ import annotations
import json


class _Chunk:
    def __init__(self, delta_content: str, finish_reason: str | None = None):
        self._delta = delta_content
        self._finish = finish_reason

    def model_dump(self) -> dict:
        return {
            "id": "chatcmpl-stream-001",
            "object": "chat.completion.chunk",
            "created": 1700000000,
            "model": "ollama_chat/gemma3:1b-it-qat",
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": self._delta},
                    "finish_reason": self._finish,
                }
            ],
        }


def _fake_stream():
    yield _Chunk("Hel")
    yield _Chunk("lo!")
    yield _Chunk("", finish_reason="stop")


def _parse_sse(text: str) -> list[dict | str]:
    """Split SSE body into a list of parsed JSON payloads + the terminator."""
    out: list[dict | str] = []
    for frame in text.split("\n\n"):
        frame = frame.strip()
        if not frame.startswith("data: "):
            continue
        payload = frame[len("data: ") :]
        if payload == "[DONE]":
            out.append("[DONE]")
        else:
            out.append(json.loads(payload))
    return out


def test_chat_streaming_emits_sse_chunks_and_done(client, monkeypatch):
    import litellm

    captured: dict = {}

    def fake_completion(**kw):
        captured.update(kw)
        assert kw["stream"] is True
        return _fake_stream()

    monkeypatch.setattr(litellm, "completion", fake_completion)
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "gemma3:1b-it-qat",
            "messages": [{"role": "user", "content": "say hi"}],
            "stream": True,
        },
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    frames = _parse_sse(r.text)
    # 3 chunk frames + terminator
    assert frames[-1] == "[DONE]"
    chunk_frames = [f for f in frames if f != "[DONE]"]
    assert len(chunk_frames) == 3
    deltas = [c["choices"][0]["delta"]["content"] for c in chunk_frames]
    assert "".join(deltas) == "Hello!"
    assert chunk_frames[0]["object"] == "chat.completion.chunk"
    assert chunk_frames[0]["model"] == "ollama_chat/gemma3:1b-it-qat"
    assert chunk_frames[-1]["choices"][0]["finish_reason"] == "stop"


def test_chat_streaming_error_path_emits_error_frame_then_done(client, monkeypatch):
    import litellm

    def boom(**_):
        raise RuntimeError("upstream blew up")

    monkeypatch.setattr(litellm, "completion", boom)
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "gemma3:1b-it-qat",
            "messages": [{"role": "user", "content": "x"}],
            "stream": True,
        },
    )
    assert r.status_code == 200  # SSE error envelopes ride a 200
    frames = _parse_sse(r.text)
    assert frames[-1] == "[DONE]"
    assert any(isinstance(f, dict) and "error" in f for f in frames)
    err = next(f for f in frames if isinstance(f, dict) and "error" in f)
    assert err["error"]["type"] == "upstream_error"
    assert "upstream blew up" in err["error"]["message"]
