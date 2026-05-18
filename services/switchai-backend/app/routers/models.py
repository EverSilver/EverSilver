"""GET /v1/models — lists every SwitchAI-supported model for providers whose
API key is configured in the environment.

We import each provider module dynamically and read its ``SUPPORTED_MODELS``
dict (this mirrors SwitchAI's own discovery mechanism).
"""

from __future__ import annotations

import ast
import os
from functools import lru_cache

from fastapi import APIRouter

from ..config import PROVIDERS, get_settings
from ..schemas import ModelCard, ModelList


router = APIRouter(prefix="/v1", tags=["models"])


def _providers_dir() -> str | None:
    """Locate switchai/providers/ without importing the heavy parent package."""
    try:
        import switchai  # noqa: F401 -- may pull cairo on some installs
    except Exception:
        # Fall back to spec_from_file via package finder.
        try:
            import importlib.util as iu

            spec = iu.find_spec("switchai")
            if spec and spec.submodule_search_locations:
                return os.path.join(list(spec.submodule_search_locations)[0], "providers")
        except Exception:
            return None
        return None
    try:
        import switchai as _sa

        return os.path.join(os.path.dirname(_sa.__file__), "providers")
    except Exception:
        return None


@lru_cache(maxsize=None)
def _provider_models(provider: str) -> tuple[str, ...]:
    """Read SUPPORTED_MODELS keys from a provider module via AST parse.

    We deliberately avoid importing the module to side-step optional native
    dependencies pulled in by ``switchai/__init__.py``.
    """
    pdir = _providers_dir()
    if not pdir:
        return ()
    path = os.path.join(pdir, f"_{provider}.py")
    if not os.path.isfile(path):
        return ()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except Exception:
        return ()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "SUPPORTED_MODELS":
                    if isinstance(node.value, ast.Dict):
                        keys: list[str] = []
                        for k in node.value.keys:
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                keys.append(k.value)
                        return tuple(keys)
    return ()


@router.get("/models", response_model=ModelList)
async def list_models() -> ModelList:
    settings = get_settings()
    cards: list[ModelCard] = []
    for provider in PROVIDERS:
        # Only advertise providers we can actually serve.
        if provider != "ollama" and not settings.api_key_for(provider):
            continue
        for model in _provider_models(provider):
            cards.append(ModelCard(id=f"{provider}/{model}", owned_by=provider))
    return ModelList(data=cards)
