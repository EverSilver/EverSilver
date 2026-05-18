"""Non-streaming chat completion behavior."""

from __future__ import annotations

from tests.conftest import FakeChatResponse


def test_chat_basic(client, fake_switchai):
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": "hi"}],
            "temperature": 0.5,
            "max_tokens": 64,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "openai/gpt-4o-mini"
    assert body["choices"][0]["message"]["content"] == "hello world"
    assert body["choices"][0]["finish_reason"] == "stop"  # completed -> stop
    assert body["usage"]["prompt_tokens"] == 3
    assert body["usage"]["completion_tokens"] == 5
    assert body["usage"]["total_tokens"] == 8

    # Verify SwitchAI was called with mapped args.
    inst = fake_switchai[0]
    args, kwargs = inst.chat.call_args
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]
    assert kwargs["temperature"] == 0.5
    assert kwargs["max_tokens"] == 64
    assert kwargs["stream"] is False


def test_chat_unqualified_model_falls_back_to_default_provider(client, fake_switchai):
    r = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200
    assert r.json()["model"] == "openai/gpt-4o-mini"


def test_chat_finish_reason_max_tokens(client, fake_switchai):
    # Pre-configure the response the next SwitchAI instance will return.
    # We hook by replacing the factory output once instantiated.
    r = client.post(
        "/v1/chat/completions",
        json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "x"}]},
    )
    assert r.status_code == 200
    # Now mutate the cached client and call again with a different model so
    # we exercise a separate instance whose return_value we customize:
    fake_switchai[0].chat.return_value = FakeChatResponse(finish_reason="max_tokens")
    r2 = client.post(
        "/v1/chat/completions",
        json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "x"}]},
    )
    assert r2.json()["choices"][0]["finish_reason"] == "length"


def test_chat_upstream_error_maps_to_502(client, fake_switchai, monkeypatch):
    # Force the first constructed instance to raise.
    import app.switch as switch_mod

    def _boom_factory(provider, model_name, api_key=None):
        from unittest.mock import MagicMock
        inst = MagicMock()
        inst.chat.side_effect = RuntimeError("provider down")
        return inst

    monkeypatch.setattr(switch_mod, "SwitchAI", _boom_factory)
    switch_mod.clear_cache()

    r = client.post(
        "/v1/chat/completions",
        json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 502
    body = r.json()
    assert body["error"]["type"] == "upstream_error"
    assert "provider down" in body["error"]["message"]


def test_chat_invalid_model_provider_returns_400(client, monkeypatch):
    import app.switch as switch_mod

    def _bad_factory(provider, model_name, api_key=None):
        raise ValueError(f"Provider '{provider}' is not supported.")

    monkeypatch.setattr(switch_mod, "SwitchAI", _bad_factory)
    switch_mod.clear_cache()

    r = client.post(
        "/v1/chat/completions",
        json={"model": "openai/some-bogus", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request_error"
