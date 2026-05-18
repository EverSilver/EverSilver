"""Shared fixtures."""
from __future__ import annotations
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import reset_settings_for_tests
from app.main import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Force a clean config dir for every test.
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
models:
  - name: gemma3:1b-it-qat
    model: ollama_chat/gemma3:1b-it-qat
    api_base: http://localhost:11434
    requires_env: []
  - name: gpt-4o-mini
    model: openai/gpt-4o-mini
    requires_env: [OPENAI_API_KEY]
embedding_models:
  - name: nomic-embed-text
    model: ollama/nomic-embed-text
    api_base: http://localhost:11434
    requires_env: []
  - name: text-embedding-3-small
    model: openai/text-embedding-3-small
    requires_env: [OPENAI_API_KEY]
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_BACKEND_CONFIG_PATH", str(cfg))
    monkeypatch.delenv("LLM_BACKEND_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    reset_settings_for_tests()
    app = create_app()
    return TestClient(app)
