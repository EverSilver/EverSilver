"""Model listing reflects env-provided API keys."""

from __future__ import annotations


def test_models_only_lists_keyed_providers(client, monkeypatch):
    # Baseline conftest sets OPENAI_API_KEY + MISTRAL_API_KEY.
    r = client.get("/v1/models")
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "list"
    owners = {m["owned_by"] for m in body["data"]}
    # ollama is always available (no key needed)
    assert "ollama" in owners
    assert "openai" in owners
    assert "mistral" in owners
    # Anthropic key not set in conftest -> shouldn't appear.
    assert "anthropic" not in owners
    # Every id has provider/model form.
    for m in body["data"]:
        assert "/" in m["id"]
        assert m["id"].startswith(f"{m['owned_by']}/")


def test_root_endpoint_reports_providers(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "switchai-backend"
    assert "providers" in body
    assert "openai" in body["providers"]
    assert "ollama" in body["providers"]


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
