"""Runtime settings + model registry loader."""
from __future__ import annotations
import os
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelEntry(BaseModel):
    name: str
    model: str
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    requires_env: List[str] = []


class Settings(BaseSettings):
    """Server config. Override via env or .env in the working dir."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="LLM_BACKEND_", extra="ignore")

    bind_host: str = "127.0.0.1"
    bind_port: int = 8088
    config_path: str = "config.yaml"
    auth_token: Optional[str] = None
    default_chat_model: str = "gemma3:1b-it-qat"
    default_embedding_model: str = "nomic-embed-text"
    log_level: str = "info"


_SETTINGS: Optional[Settings] = None


def get_settings() -> Settings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = Settings()
    return _SETTINGS


def reset_settings_for_tests() -> None:
    """Force re-read of env on next get_settings(). Tests only."""
    global _SETTINGS
    _SETTINGS = None


def load_models(config_path: Optional[str] = None) -> tuple[list[ModelEntry], list[ModelEntry]]:
    """Load (chat_models, embedding_models) from config.yaml."""
    path = Path(config_path or get_settings().config_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    if not path.exists():
        return [], []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    chat = [ModelEntry(**m) for m in (data.get("models") or [])]
    embed = [ModelEntry(**m) for m in (data.get("embedding_models") or [])]
    return chat, embed


def has_required_env(entry: ModelEntry) -> bool:
    """True when every var in `requires_env` is set in the process env."""
    return all(bool(os.environ.get(name)) for name in entry.requires_env)


def available_models() -> tuple[list[ModelEntry], list[ModelEntry]]:
    """Models whose required env vars are present right now."""
    chat, embed = load_models()
    return (
        [m for m in chat if has_required_env(m)],
        [m for m in embed if has_required_env(m)],
    )
