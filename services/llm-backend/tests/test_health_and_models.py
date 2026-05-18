"""Tests for /health, /, and /v1/models."""
from __future__ import annotations


def test_root_identifies_service(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "eversilver-llm-backend"
    assert body["backend"] == "litellm"
    assert "providers" in body
    # ollama appears even with no key because requires_env=[]
    assert "ollama" in body["providers"]


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_models_lists_only_available(client):
    r = client.get("/v1/models")
    assert r.status_code == 200
    ids = {m["id"] for m in r.json()["data"]}
    # Always-available
    assert "gemma3:1b-it-qat" in ids
    assert "nomic-embed-text" in ids
    # Only when keys present
    assert "gpt-4o-mini" not in ids
    assert "text-embedding-3-small" not in ids


def test_models_reveals_openai_when_key_set(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    r = client.get("/v1/models")
    ids = {m["id"] for m in r.json()["data"]}
    assert "gpt-4o-mini" in ids
    assert "text-embedding-3-small" in ids
