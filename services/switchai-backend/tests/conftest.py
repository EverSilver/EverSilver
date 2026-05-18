"""Shared pytest fixtures.

We mock ``app.switch.SwitchAI`` so no real provider call is ever made.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.switch as switch_mod
from app.config import reset_settings_for_tests
from app.main import create_app


class FakeChatMessage:
    def __init__(self, role="assistant", content=""):
        self.role = role
        self.content = content


class FakeChatUsage:
    def __init__(self, input_tokens=3, output_tokens=5, total_tokens=8):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = total_tokens


class FakeChatResponse:
    def __init__(self, content="hello world", finish_reason="completed", id_="chatcmpl-fake"):
        self.id = id_
        self.message = FakeChatMessage(content=content)
        self.tool_calls = None
        self.usage = FakeChatUsage()
        self.finish_reason = finish_reason


class FakeEmbedding:
    def __init__(self, index, data):
        self.index = index
        self.data = data


class FakeEmbeddingUsage:
    def __init__(self, input_tokens=4, total_tokens=4):
        self.input_tokens = input_tokens
        self.total_tokens = total_tokens


class FakeEmbeddingResponse:
    def __init__(self, vectors):
        self.embeddings = [FakeEmbedding(i, v) for i, v in enumerate(vectors)]
        self.usage = FakeEmbeddingUsage()


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    """Provide a baseline of env vars + reset settings + clear client cache."""
    monkeypatch.setenv("SWITCHAI_DEFAULT_PROVIDER", "openai")
    monkeypatch.setenv("SWITCHAI_DEFAULT_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral")
    monkeypatch.delenv("SWITCHAI_AUTH_TOKEN", raising=False)
    reset_settings_for_tests()
    switch_mod.clear_cache()
    yield
    switch_mod.clear_cache()
    reset_settings_for_tests()


@pytest.fixture
def fake_switchai(monkeypatch):
    """Replace ``app.switch.SwitchAI`` with a MagicMock factory.

    Each call to ``SwitchAI(provider, model_name, api_key)`` returns a fresh
    MagicMock instance; tests configure ``.chat.return_value`` etc.
    """
    instances: list[MagicMock] = []

    def _factory(provider, model_name, api_key=None):
        inst = MagicMock(name=f"SwitchAI({provider}/{model_name})")
        inst.provider = provider
        inst.model_name = model_name
        # Sensible defaults — tests override as needed.
        inst.chat.return_value = FakeChatResponse()
        inst.embed.return_value = FakeEmbeddingResponse([[0.1, 0.2, 0.3]])
        instances.append(inst)
        return inst

    monkeypatch.setattr(switch_mod, "SwitchAI", _factory)
    return instances


@pytest.fixture
def client(fake_switchai):
    app = create_app()
    return TestClient(app)
