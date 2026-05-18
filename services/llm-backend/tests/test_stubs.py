"""Stub endpoints absorb Eversilver's auxiliary backend traffic so the
desktop UI doesn't show stale-connection banners and the log isn't
flooded with `api.eversilver.local` transport errors."""
from __future__ import annotations


def test_auth_me_returns_local_user(client):
    r = client.get("/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["local"] is True
    assert body["display_name"] == "Local User"
    assert "@" in body["email"]


def test_teams_usage_returns_unlimited(client):
    r = client.get("/teams/me/usage")
    assert r.status_code == 200
    body = r.json()
    assert body["tokens_limit"] is None
    assert body["tier"] == "local"


def test_stripe_plan_is_local_active(client):
    r = client.get("/payments/stripe/currentPlan")
    assert r.status_code == 200
    assert r.json()["plan"] == "local"
    assert r.json()["status"] == "active"


def test_composio_returns_empty_collections(client):
    for path, key in (
        ("/agent-integrations/composio/toolkits", "toolkits"),
        ("/agent-integrations/composio/connections", "connections"),
        ("/agent-integrations/composio/categories", "categories"),
    ):
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.json()[key] == [], path


def test_release_latest_returns_local_build(client):
    r = client.get("/api/release/latest")
    assert r.status_code == 200
    assert "local" in r.json()["version"]


def test_openai_passthrough_paths_match_v1(client):
    r1 = client.get("/v1/models")
    r2 = client.get("/openai/v1/models")
    assert r1.status_code == r2.status_code == 200
    assert {m["id"] for m in r1.json()["data"]} == {m["id"] for m in r2.json()["data"]}


def test_catchall_returns_ok_stub_for_unknown(client):
    r = client.get("/something/we/never/implemented")
    assert r.status_code == 200
    body = r.json()
    assert body == {"ok": True, "stub": True, "path": "/something/we/never/implemented"}


def test_concrete_routes_take_precedence_over_catchall(client):
    r = client.get("/health")
    assert r.json() == {"status": "ok"}
    r = client.get("/v1/models")
    assert "data" in r.json()
