"""Thin wrapper around `litellm.completion` / `litellm.embedding`.

Resolves the OpenAI-style ``model`` field against the YAML registry
(`config.yaml`) so callers can use friendly names like
`gemma3:1b-it-qat`, `gpt-4o-mini`, or `claude-3-5-sonnet` and get the
right LiteLLM provider spec + api_base + api_key wired automatically.

Falls through to passing the raw model string to LiteLLM when no registry
entry matches — so callers can also send raw `<provider>/<model>` specs.
"""
from __future__ import annotations
import os
from typing import Any, Iterator, Optional

import litellm  # type: ignore[import-not-found]

from .config import ModelEntry, load_models


# `drop_params=True` silently strips parameters individual providers don't
# accept (e.g. `seed` on Anthropic, `tools` on Ollama). Keeps the surface
# OpenAI-compatible for callers without us hand-coding provider quirks.
litellm.drop_params = True
# Same idea for unsupported response_format etc.
litellm.set_verbose = False


def _registry() -> dict[str, ModelEntry]:
    chat, embed = load_models()
    out: dict[str, ModelEntry] = {}
    for m in chat + embed:
        out[m.name] = m
    return out


def resolve(name: str) -> tuple[str, dict[str, Any]]:
    """Map a friendly name (or raw spec) to (litellm_model, extra_kwargs).

    >>> resolve("gemma3:1b-it-qat")
    ("ollama_chat/gemma3:1b-it-qat", {"api_base": "http://localhost:11434"})
    >>> resolve("openai/gpt-4o")  # raw passthrough
    ("openai/gpt-4o", {})
    """
    reg = _registry()
    entry = reg.get(name)
    if entry is None:
        return name, {}
    extra: dict[str, Any] = {}
    if entry.api_base:
        extra["api_base"] = entry.api_base
    if entry.api_key:
        # Allow YAML to use the LiteLLM `os.environ/X` syntax.
        if entry.api_key.startswith("os.environ/"):
            env_name = entry.api_key.split("/", 1)[1]
            v = os.environ.get(env_name)
            if v:
                extra["api_key"] = v
        else:
            extra["api_key"] = entry.api_key
    return entry.model, extra


# Models that we know don't accept function-calling. The Ollama runtime
# returns a hard 400 ("<model> does not support tools") instead of just
# ignoring the field, and `litellm.drop_params=True` doesn't strip it for
# the Ollama provider, so we have to filter here.
_NO_TOOL_SUBSTRINGS: tuple[str, ...] = (
    "gemma",
    "gemma2",
    "gemma3",
    "phi3",
    "phi-3",
    "smol",
    "tinyllama",
    "deepseek-r1:1.5b",
    "nomic-embed",
    "bge-",
)


def _model_supports_tools(resolved_model: str) -> bool:
    lower = resolved_model.lower()
    if any(s in lower for s in _NO_TOOL_SUBSTRINGS):
        return False
    # LiteLLM ships a capability table for hosted models; trust it when present.
    try:
        return bool(litellm.supports_function_calling(model=resolved_model))
    except Exception:
        # Unknown model — assume supported and let the provider 4xx instead of
        # silently dropping a feature the caller asked for.
        return True


def _truncate_history_for_small_models(
    resolved_model: str, messages: list[dict]
) -> list[dict]:
    """Cap conversation history for small local models so they don't
    spend 60+ seconds re-encoding a transcript that exceeds their useful
    attention window. The system prompt is preserved verbatim; only the
    middle of the transcript is dropped, keeping the latest turns.

    Applied to models smaller than ~4B params. Cloud/large models skip
    this and receive the full transcript.
    """
    small_signals = ("1b", "1.5b", "1.6b", "2b", "3b", "phi3:mini", "smol", "tinyllama")
    lower = resolved_model.lower()
    if not any(s in lower for s in small_signals):
        return messages
    # Keep all system messages + the last 6 turns (user/assistant/tool).
    sys_msgs = [m for m in messages if m.get("role") == "system"]
    non_sys = [m for m in messages if m.get("role") != "system"]
    if len(non_sys) <= 6:
        return messages
    return sys_msgs + non_sys[-6:]


def chat_completion(*, model: str, messages: list[dict], stream: bool = False, **kwargs: Any) -> Any:
    """Synchronous chat completion. Returns a `litellm.ModelResponse`
    when `stream=False`, or an iterator of streaming chunks when True.

    - Strips `tools`/`tool_choice` when the resolved model can't accept
      them (Ollama returns a hard 400 otherwise).
    - Truncates conversation history for small (<4B) local models so a
      long thread doesn't blow past their attention budget and turn into
      a minute-long stall.
    """
    resolved_model, extra = resolve(model)
    if not _model_supports_tools(resolved_model):
        kwargs.pop("tools", None)
        kwargs.pop("tool_choice", None)
        kwargs.pop("functions", None)
        kwargs.pop("function_call", None)
    messages = _truncate_history_for_small_models(resolved_model, messages)
    return litellm.completion(
        model=resolved_model,
        messages=messages,
        stream=stream,
        **{**extra, **kwargs},
    )


def embeddings(*, model: str, input: list[str] | str, **kwargs: Any) -> Any:
    resolved_model, extra = resolve(model)
    return litellm.embedding(model=resolved_model, input=input, **{**extra, **kwargs})


__all__ = ["chat_completion", "embeddings", "resolve"]
