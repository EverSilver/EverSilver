"""SwitchAI client factory + per-(provider, model) cache.

A new SwitchAI instance is small but creating one validates the model + key,
so we cache by (provider, model_name) for the process lifetime. This is safe
because each instance is keyed to a single model and holds only the underlying
provider client.

Also exposes ``resolve_model`` for parsing the OpenAI ``model`` field which we
extend with the ``<provider>/<model>`` convention.
"""

from __future__ import annotations

import threading
from typing import Optional

from .config import PROVIDERS, get_settings

# Import lazily-friendly: importing switchai at module load is fine in prod,
# but tests monkeypatch ``app.switch.SwitchAI`` so the symbol must live here.
try:  # pragma: no cover - exercised in real use, mocked in tests
    from switchai import SwitchAI  # type: ignore
except Exception:  # pragma: no cover
    SwitchAI = None  # type: ignore


_lock = threading.Lock()
_cache: dict[tuple[str, str], object] = {}


def resolve_model(model_field: str) -> tuple[str, str]:
    """Parse ``"<provider>/<model>"`` or fall back to default provider.

    Examples:
        ``openai/gpt-4o-mini`` -> ("openai", "gpt-4o-mini")
        ``gpt-4o-mini``        -> (SWITCHAI_DEFAULT_PROVIDER, "gpt-4o-mini")
    """
    if not model_field:
        s = get_settings()
        return s.switchai_default_provider, s.switchai_default_model

    if "/" in model_field:
        provider, _, model = model_field.partition("/")
        provider = provider.lower().strip()
        model = model.strip()
        if provider in PROVIDERS and model:
            return provider, model

    # Unqualified -> default provider.
    return get_settings().switchai_default_provider, model_field


def get_client(provider: str, model: str, api_key: Optional[str] = None):
    """Return a cached SwitchAI client for (provider, model)."""
    if SwitchAI is None:  # pragma: no cover
        raise RuntimeError(
            "switchai is not installed. `pip install switchai` or `pip install -e .`"
        )

    key = (provider, model)
    with _lock:
        client = _cache.get(key)
        if client is None:
            resolved_key = api_key if api_key is not None else get_settings().api_key_for(provider)
            client = SwitchAI(provider=provider, model_name=model, api_key=resolved_key)
            _cache[key] = client
        return client


def clear_cache() -> None:
    """Used in tests to drop cached mocked clients between cases."""
    with _lock:
        _cache.clear()
