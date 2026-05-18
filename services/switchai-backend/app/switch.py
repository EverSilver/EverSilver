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

# `switchai/__init__.py` eagerly imports the `superclients` package which
# pulls in `cairosvg` -> `libcairo-2.dll`, a native dep absent on a
# standard Windows Python install. We don't use any of the superclients
# (Browser, Classifier, Illustrator, ImageRetriever) for chat/embed
# routing -- those are stand-alone agentic helpers. Stubbing the
# subpackage into sys.modules before the switchai import lets the
# main_client load cleanly without GTK/cairo on the system.
import sys as _sys  # noqa: E402
import types as _types  # noqa: E402


def _stub_switchai_superclients() -> None:
    """Pre-populate sys.modules so `from .superclients import Browser, ...`
    in switchai/__init__.py resolves to our no-op stub instead of importing
    cairosvg / libcairo. Idempotent."""
    if "switchai.superclients" in _sys.modules:
        return

    class _Unavailable:  # pragma: no cover - never instantiated in chat path
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError(
                "switchai superclients (Browser/Classifier/Illustrator/ImageRetriever) "
                "are unavailable in this backend: libcairo is not installed on the host. "
                "These helpers are not used by /v1/chat/completions or /v1/embeddings."
            )

    stub = _types.ModuleType("switchai.superclients")
    stub.Browser = _Unavailable  # type: ignore[attr-defined]
    stub.Classifier = _Unavailable  # type: ignore[attr-defined]
    stub.Illustrator = _Unavailable  # type: ignore[attr-defined]
    stub.ImageRetriever = _Unavailable  # type: ignore[attr-defined]
    _sys.modules["switchai.superclients"] = stub


def _stub_broken_provider_deps() -> None:
    """The switchai providers package (`providers/__init__.py`) eagerly imports
    every provider adapter, even ones the caller never selects. When an
    upstream provider's SDK doesn't yet support the host Python version
    (notably `mistralai` on Python 3.14, which installs as an empty
    module), that eager import crashes and takes down chat for everyone.

    Stub each known-broken upstream SDK with a placeholder that only
    raises when actually instantiated. Selecting a different provider
    (ollama, openai, anthropic, deepseek, google, xai, deepgram,
    voyageai) is unaffected.
    """
    import importlib

    def _stub(module_name: str, *exports: str) -> None:
        existing = _sys.modules.get(module_name)
        if existing is not None and all(hasattr(existing, e) for e in exports):
            return  # real package is healthy, leave it alone
        try:
            mod = importlib.import_module(module_name)
            if all(hasattr(mod, e) for e in exports):
                return
        except Exception:
            mod = None

        class _ProviderUnavailable:  # pragma: no cover
            _provider = module_name

            def __init__(self, *_args, **_kwargs) -> None:
                raise RuntimeError(
                    f"Provider SDK '{self._provider}' is unavailable on this Python "
                    "(likely the package has no wheel for this interpreter version). "
                    "Pick a different SwitchAI provider for now (e.g. ollama, openai, anthropic)."
                )

        stub = _types.ModuleType(module_name)
        for name in exports:
            setattr(stub, name, _ProviderUnavailable)
        _sys.modules[module_name] = stub

    # Known incompatibilities (Python 3.14, May 2026):
    #   mistralai (1.x):  empty package, no `Mistral` export
    #   deepgram-sdk (4.x): `PrerecordedOptions` + `FileSource` were
    #                       removed/renamed; switchai expects the 3.x layout
    #   replicate (≤1.x): pydantic v1 layer raises
    #                     "unable to infer type for attribute 'previous'"
    #                     during `replicate/collection.py` import on 3.14
    _stub("mistralai", "Mistral")
    _stub("deepgram", "DeepgramClient", "PrerecordedOptions", "FileSource")
    _stub("replicate", "Client")
    # _replicate.py does `from replicate.client import Client` — stub the
    # submodule too so the import resolves without touching the broken
    # collection.py chain.
    rep_client = _types.ModuleType("replicate.client")

    class _ReplicateUnavailable:  # pragma: no cover
        def __init__(self, *_a, **_k) -> None:
            raise RuntimeError(
                "Provider SDK 'replicate' is unavailable on this Python "
                "(pydantic v1 incompat on 3.14). Pick a different SwitchAI "
                "provider for now."
            )

    rep_client.Client = _ReplicateUnavailable  # type: ignore[attr-defined]
    _sys.modules.setdefault("replicate.client", rep_client)


_stub_switchai_superclients()
_stub_broken_provider_deps()


def _patch_permissive_model_whitelist() -> None:
    """SwitchAI ships a hardcoded ``SUPPORTED_MODELS`` whitelist per provider
    and rejects any model name not in the dict (`Model 'X' is not supported by
    any provider.`). That's wrong for backend use: a user should be able to
    point at any model their upstream provider serves (Ollama tags they
    pulled, fine-tuned OpenAI models, Anthropic snapshots, etc.).

    Replace each whitelist with a permissive mapping that returns
    ``[Task.TEXT_GENERATION]`` for any model name, falling through to the
    real entry if one exists (so vision/embedding-aware models keep their
    extra capabilities).
    """
    try:
        import importlib

        utils = importlib.import_module("switchai.utils")
        Task = utils.Task  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover
        return

    class _PermissiveModels(dict):
        """dict that says "yes" to every `in` check and falls back to
        TEXT_GENERATION for missing keys."""

        def __contains__(self, _item: object) -> bool:  # type: ignore[override]
            return True

        def __getitem__(self, key: object):  # type: ignore[override]
            try:
                return super().__getitem__(key)
            except KeyError:
                return [Task.TEXT_GENERATION]

    for provider in (
        "_openai",
        "_anthropic",
        "_google",
        "_mistral",
        "_ollama",
        "_deepseek",
        "_xai",
        "_voyageai",
        "_replicate",
        "_deepgram",
    ):
        try:
            mod = importlib.import_module(f"switchai.providers.{provider}")
        except Exception:
            continue
        original = getattr(mod, "SUPPORTED_MODELS", {}) or {}
        permissive = _PermissiveModels(original)
        mod.SUPPORTED_MODELS = permissive


try:  # pragma: no cover - exercised in real use, mocked in tests
    from switchai import SwitchAI  # type: ignore

    _patch_permissive_model_whitelist()
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
