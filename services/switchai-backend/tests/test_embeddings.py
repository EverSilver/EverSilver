"""Embedding endpoint behavior."""

from __future__ import annotations

from tests.conftest import FakeEmbeddingResponse


def test_embed_single(client, fake_switchai):
    r = client.post(
        "/v1/embeddings",
        json={"model": "openai/text-embedding-3-small", "input": "hello"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["object"] == "list"
    assert body["model"] == "openai/text-embedding-3-small"
    assert len(body["data"]) == 1
    assert body["data"][0]["embedding"] == [0.1, 0.2, 0.3]
    assert body["data"][0]["index"] == 0
    assert body["usage"]["prompt_tokens"] == 4

    inst = fake_switchai[0]
    assert inst.embed.call_args.args[0] == "hello"


def test_embed_list(client, fake_switchai):
    # Create cached client by triggering one call:
    client.post(
        "/v1/embeddings",
        json={"model": "openai/text-embedding-3-small", "input": "warmup"},
    )
    fake_switchai[0].embed.return_value = FakeEmbeddingResponse([[1.0], [2.0], [3.0]])
    r = client.post(
        "/v1/embeddings",
        json={"model": "openai/text-embedding-3-small", "input": ["a", "b", "c"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert [d["embedding"] for d in body["data"]] == [[1.0], [2.0], [3.0]]
    assert [d["index"] for d in body["data"]] == [0, 1, 2]


def test_embed_upstream_error(client, fake_switchai, monkeypatch):
    import app.switch as switch_mod
    from unittest.mock import MagicMock

    def _factory(provider, model_name, api_key=None):
        m = MagicMock()
        m.embed.side_effect = RuntimeError("nope")
        return m

    monkeypatch.setattr(switch_mod, "SwitchAI", _factory)
    switch_mod.clear_cache()

    r = client.post(
        "/v1/embeddings",
        json={"model": "openai/text-embedding-3-small", "input": "x"},
    )
    assert r.status_code == 502
    assert r.json()["error"]["type"] == "upstream_error"
