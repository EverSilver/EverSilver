"""Tests for POST /v1/embeddings."""
from __future__ import annotations


class _FakeEmbeddingResponse:
    def __init__(self, vectors: list[list[float]], model: str):
        self._vectors = vectors
        self._model = model

    def model_dump(self) -> dict:
        return {
            "object": "list",
            "model": self._model,
            "data": [
                {"object": "embedding", "index": i, "embedding": v}
                for i, v in enumerate(self._vectors)
            ],
            "usage": {"prompt_tokens": 4, "total_tokens": 4},
        }


def test_embeddings_single_input_string(client, monkeypatch):
    import litellm

    captured: dict = {}

    def fake_embed(**kw):
        captured.update(kw)
        return _FakeEmbeddingResponse([[0.1, 0.2, 0.3]], kw["model"])

    monkeypatch.setattr(litellm, "embedding", fake_embed)
    r = client.post(
        "/v1/embeddings",
        json={"model": "nomic-embed-text", "input": "hello world"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["object"] == "list"
    assert body["model"] == "ollama/nomic-embed-text"
    assert len(body["data"]) == 1
    assert body["data"][0]["embedding"] == [0.1, 0.2, 0.3]
    assert body["data"][0]["index"] == 0
    assert body["usage"]["prompt_tokens"] == 4
    # Strings are wrapped into a list before being sent upstream.
    assert captured["input"] == ["hello world"]
    assert captured["model"] == "ollama/nomic-embed-text"
    assert captured["api_base"] == "http://localhost:11434"


def test_embeddings_batch_input(client, monkeypatch):
    import litellm

    monkeypatch.setattr(
        litellm,
        "embedding",
        lambda **kw: _FakeEmbeddingResponse([[1.0, 0.0], [0.0, 1.0]], kw["model"]),
    )
    r = client.post(
        "/v1/embeddings",
        json={"model": "nomic-embed-text", "input": ["a", "b"], "dimensions": 2},
    )
    assert r.status_code == 200
    body = r.json()
    assert [d["embedding"] for d in body["data"]] == [[1.0, 0.0], [0.0, 1.0]]
    assert [d["index"] for d in body["data"]] == [0, 1]


def test_embeddings_upstream_error(client, monkeypatch):
    import litellm

    def boom(**_):
        raise RuntimeError("embed failed")

    monkeypatch.setattr(litellm, "embedding", boom)
    r = client.post(
        "/v1/embeddings",
        json={"model": "nomic-embed-text", "input": "x"},
    )
    assert r.status_code == 502
    err = r.json()["detail"]["error"]
    assert err["type"] == "upstream_error"
    assert "embed failed" in err["message"]
