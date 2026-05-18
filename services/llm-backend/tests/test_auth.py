"""Tests for the optional bearer-token middleware."""
from __future__ import annotations
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import reset_settings_for_tests
from app.main import create_app


@pytest.fixture()
def auth_client(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
models:
  - name: gemma3:1b-it-qat
    model: ollama_chat/gemma3:1b-it-qat
    api_base: http://localhost:11434
    requires_env: []
embedding_models: []
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_BACKEND_CONFIG_PATH", str(cfg))
    monkeypatch.setenv("LLM_BACKEND_AUTH_TOKEN", "secret-token-xyz")
    reset_settings_for_tests()
    return TestClient(create_app())


def test_public_endpoints_dont_require_auth(auth_client):
    assert auth_client.get("/").status_code == 200
    assert auth_client.get("/health").status_code == 200


def test_v1_requires_bearer(auth_client):
    r = auth_client.get("/v1/models")
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == 401


def test_v1_rejects_wrong_token(auth_client):
    r = auth_client.get("/v1/models", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_v1_accepts_correct_token(auth_client):
    r = auth_client.get(
        "/v1/models", headers={"Authorization": "Bearer secret-token-xyz"}
    )
    assert r.status_code == 200


def test_open_mode_no_token_required(client):
    # The default `client` fixture deletes LLM_BACKEND_AUTH_TOKEN.
    r = client.get("/v1/models")
    assert r.status_code == 200
