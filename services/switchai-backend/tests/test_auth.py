"""Bearer-token middleware on/off."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import reset_settings_for_tests
from app.main import create_app


def test_no_auth_when_token_unset(client):
    r = client.post(
        "/v1/chat/completions",
        json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200


def test_auth_required_when_token_set(monkeypatch, fake_switchai):
    monkeypatch.setenv("SWITCHAI_AUTH_TOKEN", "s3cr3t")
    reset_settings_for_tests()
    c = TestClient(create_app())

    # Public endpoints stay open.
    assert c.get("/").status_code == 200
    assert c.get("/health").status_code == 200

    # /v1/* without header -> 401.
    r = c.post(
        "/v1/chat/completions",
        json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == 401

    # Wrong token -> 401.
    r = c.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer wrong"},
        json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 401

    # Correct token -> 200.
    r = c.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer s3cr3t"},
        json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200
