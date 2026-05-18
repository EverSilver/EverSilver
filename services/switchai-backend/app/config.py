"""Runtime configuration via env vars / .env (pydantic-settings).

All provider API keys are read here so we can both:
  * pass them explicitly into SwitchAI() (when constructing clients), and
  * advertise which providers are "available" on GET /v1/models and GET /.
"""

from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


# Canonical list of providers SwitchAI ships with. Keep in sync with
# switchai/providers/_*.py. Ollama needs no key.
PROVIDERS: tuple[str, ...] = (
    "openai",
    "anthropic",
    "deepseek",
    "google",
    "mistral",
    "ollama",
    "replicate",
    "voyageai",
    "xai",
    "deepgram",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Server ---
    switchai_host: str = "127.0.0.1"
    switchai_port: int = 8088

    # --- Routing defaults ---
    switchai_default_provider: str = "openai"
    switchai_default_model: str = "gpt-4o-mini"

    # --- Auth (optional) ---
    switchai_auth_token: Optional[str] = None

    # --- Provider keys ---
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    replicate_api_key: Optional[str] = None
    voyageai_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None
    deepgram_api_key: Optional[str] = None

    def api_key_for(self, provider: str) -> Optional[str]:
        """Return the API key configured for a provider, or None."""
        if provider == "ollama":
            # Ollama is keyless / local.
            return None
        return getattr(self, f"{provider}_api_key", None)

    def available_providers(self) -> list[str]:
        """Return the providers we can actually serve given current env."""
        out: list[str] = []
        for p in PROVIDERS:
            if p == "ollama" or self.api_key_for(p):
                out.append(p)
        return out


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Singleton accessor — keeps things cheap and overridable in tests."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_for_tests() -> None:
    """Used by tests so monkeypatched env vars take effect."""
    global _settings
    _settings = None
