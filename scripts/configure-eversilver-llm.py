"""
Wire Eversilver's chat panel into OpenFang (RightNow-AI/openfang) on
the Athena VPS.

OpenFang exposes a fully OpenAI-compatible `/v1/chat/completions` at
http://62.171.154.39:4200/v1, with the `model` field naming a
registered OpenFang agent (Athena, planner, coder, researcher,
browser-hand, orchestrator, …). Auth is a single Bearer token
(`OPENFANG_API_KEY`).

What this script does to the active user's config.toml:

  * inference_url  = http://62.171.154.39:4200/v1
  * default_model  = Athena    (or whatever --model was passed)
  * api_key         = <OPENFANG_API_KEY>  (Bearer token, kept local)
  * cloud_providers contains an `openfang` entry with auth_style=bearer
  * model_routes route reasoning/agentic/coding to the same agent
  * local_ai.stt_provider = whisper      (voice stays local — no key needed)
  * local_ai.whisper_in_process = true
  * voice_server.skip_cleanup = true     (skip the extra LLM cleanup pass)
  * socket.auto_connect = false          (silence the dead api.eversilver.local)

Idempotent. Always writes a timestamped `.bak` of the prior config.
The token is read from `--auth-token` or `$OPENFANG_API_KEY`; it is
NEVER echoed in full to the console or written anywhere other than
the local config.toml (which is per-user, under ~/.eversilver/users/).

Usage:
    # First time — pass the key once, it sticks in config.toml.
    OPENFANG_API_KEY=... python scripts/configure-eversilver-llm.py

    # Same effect with explicit flag:
    python scripts/configure-eversilver-llm.py --auth-token <key>

    # Use a different agent than Athena:
    python scripts/configure-eversilver-llm.py --model researcher

    # Target a specific user dir (rather than active_user.toml):
    python scripts/configure-eversilver-llm.py --user-id local-abc123
"""
from __future__ import annotations
import argparse
import shutil
import sys
import tomllib
from datetime import datetime
from pathlib import Path

try:
    import tomli_w  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    print("tomli-w is required. Install with: pip install tomli-w", file=sys.stderr)
    sys.exit(2)


ROOT = Path.home() / ".eversilver"
# OpenFang on the Athena VPS — open-source agent OS, OpenAI-compatible.
# (RightNow-AI/openfang on GitHub; dashboard at :4200.) Each registered
# agent (Athena, planner, coder, researcher, …) is addressable by its
# name in the `model` field of /v1/chat/completions. Authentication is
# a single Bearer token (OPENFANG_API_KEY) configured on the server.
BACKEND_SLUG = "openfang"
BACKEND_LABEL = "OpenFang (Athena VPS)"
BACKEND_ENDPOINT = "http://62.171.154.39:4200/v1"
BACKEND_ID = "p_openfang"
CHAT_HINTS = ("reasoning", "agentic", "coding")
# Token is read from $OPENFANG_API_KEY (env) or --auth-token CLI flag.
# Never hard-coded; never committed.


def find_active_user_dir(explicit: str | None) -> Path:
    if explicit:
        return ROOT / "users" / explicit
    active = ROOT / "active_user.toml"
    if not active.exists():
        sys.exit(
            f"No active_user.toml at {active}. Launch Eversilver once and click "
            "'Continue without an account' first."
        )
    parsed = tomllib.loads(active.read_text(encoding="utf-8"))
    uid = parsed.get("user_id")
    if not uid:
        sys.exit(f"active_user.toml at {active} has no user_id field.")
    return ROOT / "users" / uid


def load_or_init_config(user_dir: Path) -> tuple[Path, dict]:
    path = user_dir / "config.toml"
    if not path.exists():
        user_dir.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    return path, tomllib.loads(path.read_text(encoding="utf-8"))


def set_field(config: dict, key: str, value: object) -> bool:
    if config.get(key) == value:
        return False
    config[key] = value
    return True


def upsert_backend_provider(config: dict) -> bool:
    """Insert/refresh the llm-backend entry in `cloud_providers`."""
    providers = config.setdefault("cloud_providers", [])
    for entry in providers:
        if entry.get("slug") == BACKEND_SLUG or entry.get("id") == BACKEND_ID:
            changed = False
            for field, want in (
                ("endpoint", BACKEND_ENDPOINT),
                ("label", BACKEND_LABEL),
                # OpenFang requires Bearer auth for non-loopback callers.
                # The chat-factory (factory.rs) reads the token from
                # config.api_key (set in main()) — Eversilver's
                # OpenAiCompatibleProvider then sends it as
                # `Authorization: Bearer <token>` to OpenFang.
                ("auth_style", "bearer"),
            ):
                if entry.get(field) != want:
                    entry[field] = want
                    changed = True
            return changed
    providers.append(
        {
            "id": BACKEND_ID,
            "slug": BACKEND_SLUG,
            "label": BACKEND_LABEL,
            "endpoint": BACKEND_ENDPOINT,
            "auth_style": "bearer",
        }
    )
    return True


def drop_legacy_switchai(config: dict) -> bool:
    """Remove stale cloud_providers entries from earlier installs.

    Spans every backend the configure script has ever pointed Eversilver
    at — switchai (Python LiteLLM shim, removed), eversilver-llm (the
    local LLM-backend service, removed), athena-swarm (direct SAGE
    swarm router on :8100, superseded by OpenFang on :4200).
    """
    LEGACY_SLUGS = {"switchai", "eversilver-llm", "athena-swarm"}
    LEGACY_IDS = {"p_switchai_local", "p_eversilver_llm_local", "p_athena_swarm"}
    providers = config.get("cloud_providers")
    if not isinstance(providers, list):
        return False
    kept = [
        p
        for p in providers
        if not (
            isinstance(p, dict)
            and (p.get("slug") in LEGACY_SLUGS or p.get("id") in LEGACY_IDS)
        )
    ]
    if kept == providers:
        return False
    config["cloud_providers"] = kept
    # Reset primary_cloud if it pointed at any of the legacy providers.
    if config.get("primary_cloud") in LEGACY_IDS:
        config["primary_cloud"] = BACKEND_ID
    return True


def set_model_routes(config: dict, model_id: str) -> bool:
    routes = config.setdefault("model_routes", [])
    filtered = [r for r in routes if isinstance(r, dict) and r.get("hint") not in CHAT_HINTS]
    rebuilt = filtered + [{"hint": h, "model": model_id} for h in CHAT_HINTS]
    if rebuilt == routes:
        return False
    config["model_routes"] = rebuilt
    return True


def disable_remote_socket(config: dict) -> bool:
    socket = config.setdefault("socket", {})
    if socket.get("auto_connect") is False:
        return False
    socket["auto_connect"] = False
    return True


def backup(path: Path) -> Path | None:
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return None
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    bp = path.with_suffix(f".toml.bak.{stamp}")
    shutil.copy2(path, bp)
    return bp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", help="defaults to active_user.toml lookup")
    ap.add_argument(
        "--model",
        default="Athena",
        help=(
            "OpenFang agent name to use as the default for chat — must be a "
            "RUNNING agent in the dashboard at :4200. Common: Athena (personal "
            "assistant), planner, coder, researcher, browser-hand, orchestrator. "
            "Default: Athena"
        ),
    )
    ap.add_argument(
        "--auth-token",
        default=None,
        help=(
            "OpenFang Bearer token. Falls back to $OPENFANG_API_KEY env var. "
            "Required — OpenFang rejects non-loopback requests without it. "
            "Stored in the user's local config.toml only, never logged or "
            "committed."
        ),
    )
    ap.add_argument(
        "--no-socket-disable",
        action="store_true",
        help="Leave socket.auto_connect alone (default: disable WS to dead backend).",
    )
    ap.add_argument(
        "--no-register",
        action="store_true",
        help="Skip registering this install as a node on the Athena swarm.",
    )
    ap.add_argument(
        "--node-id",
        default=None,
        help="Override the swarm node id. Defaults to 'eversilver-<hostname>'.",
    )
    args = ap.parse_args()

    import os

    user_dir = find_active_user_dir(args.user_id)
    config_path, config = load_or_init_config(user_dir)
    model_id = args.model
    api_key = (
        args.auth_token
        or os.environ.get("OPENFANG_API_KEY")
        or config.get("api_key")  # preserve existing if neither supplied
    )
    if not api_key:
        sys.exit(
            "OpenFang API key not provided. Pass --auth-token, set "
            "$OPENFANG_API_KEY in the environment, or pre-populate "
            "config.toml#api_key. The key is required for non-loopback "
            "requests to OpenFang."
        )

    # Masked for the console — never print the full token.
    masked = (api_key[:4] + "…" + api_key[-4:]) if len(api_key) > 12 else "…"

    print(f"  user dir       : {user_dir}")
    print(f"  config         : {config_path}")
    print(f"  inference_url  : {BACKEND_ENDPOINT}")
    print(f"  default_model  : {model_id}")
    print(f"  auth token     : {masked}  (stored in config.toml only)")

    changed = False

    # ── Remote arm (the chat dispatcher's primary path) ────────────────────
    changed |= set_field(config, "inference_url", BACKEND_ENDPOINT)
    changed |= set_field(config, "default_model", model_id)
    changed |= set_field(config, "api_key", api_key)
    changed |= set_model_routes(config, model_id)
    changed |= upsert_backend_provider(config)
    changed |= set_field(config, "primary_cloud", BACKEND_ID)
    changed |= drop_legacy_switchai(config)

    # ── Repoint the auxiliary API surface ─────────────────────────────────
    # Account/billing/integrations/release-channel calls go to whatever
    # `api_url` resolves to (defaulting to https://api.eversilver.local —
    # dead in a local-only install). The llm-backend exposes stub routes
    # for every path the desktop polls, so pointing here drops all the
    # "stale status" banners and 5-min reconnect storms.
    backend_root = BACKEND_ENDPOINT.rsplit("/v1", 1)[0]
    changed |= set_field(config, "api_url", backend_root)

    # ── Per-workload selectors (Settings > AI side panel) ─────────────────
    workload_target = f"{BACKEND_SLUG}:{model_id}"
    for hint in CHAT_HINTS:
        key = f"{hint}_provider"
        if config.get(key) != workload_target:
            config[key] = workload_target
            changed = True

    # ── Local AI runtime: enabled, but only for voice (STT/TTS) ───────────
    # Chat still routes through the llm-backend via inference_url +
    # model_routes above. Voice (whisper STT + piper TTS) is local-only
    # so it doesn't depend on the dead api.eversilver.local backend.
    #
    # local_ai.usage gates individual features:
    #   - chat=false → use the remote arm (llm-backend)
    #   - speech_to_text=true → use whisper-rs in-process
    #   - text_to_speech=true → use piper (if installed)
    local_ai = config.setdefault("local_ai", {})
    if local_ai.get("runtime_enabled") is not True:
        local_ai["runtime_enabled"] = True
        changed = True
    if local_ai.get("stt_provider") != "whisper":
        local_ai["stt_provider"] = "whisper"
        changed = True
    if local_ai.get("whisper_in_process") is not True:
        local_ai["whisper_in_process"] = True
        changed = True
    # Smallest, fastest model — 75MB, ~real-time on CPU.
    if local_ai.get("stt_model_id") != "tiny":
        local_ai["stt_model_id"] = "tiny"
        changed = True
    # Skip the LLM post-processing cleanup pass — it adds a whole second
    # LLM round-trip after every transcription just to fix grammar/
    # punctuation, which for short push-to-talk utterances roughly
    # doubles the perceived latency. Upstream openhuman defaults this
    # to `true`; we flip it for the local-only profile.
    if local_ai.get("voice_llm_cleanup_enabled") is not False:
        local_ai["voice_llm_cleanup_enabled"] = False
        changed = True

    # Same flag from the voice_server side (renderer reads this too).
    vs = config.setdefault("voice_server", {})
    if vs.get("skip_cleanup") is not True:
        vs["skip_cleanup"] = True
        changed = True
    # Per-feature gates:
    #   chat          → cloud (OpenFang Athena)
    #   speech_to_text → local whisper
    #   embeddings    → local Ollama (bge-m3, 1024 dims — matches the
    #                   on-disk format the memory tree expects)
    #   text_to_speech → local piper if installed; otherwise disabled
    usage = local_ai.setdefault("usage", {})
    if usage.get("chat") is not False:
        usage["chat"] = False
        changed = True
    if usage.get("speech_to_text") is not True:
        usage["speech_to_text"] = True
        changed = True
    if usage.get("embeddings") is not True:
        usage["embeddings"] = True
        changed = True
    # Pin the embedding model so the memory tree's dim validator
    # accepts the output (it requires EMBEDDING_DIM=1024).
    if local_ai.get("embedding_model_id") != "bge-m3":
        local_ai["embedding_model_id"] = "bge-m3"
        changed = True
    # Local Ollama base — explicit so the embedder doesn't try the
    # remote arm when the runtime is enabled.
    if not local_ai.get("base_url"):
        local_ai["base_url"] = "http://localhost:11434"
        changed = True

    # ── Re-route the canonical 'summarization-v1' tier to OpenFang ───────
    # Eversilver's memory tree autosummariser dispatches with model
    # 'summarization-v1' against the cloud arm. Without a mapping, the
    # OpenAiCompatibleProvider sends that literal string to OpenFang
    # which has no such agent and 404s. Map it through model_routes to
    # OpenFang's `researcher` agent (smart provider, good at digesting).
    routes = config.get("model_routes", [])
    if isinstance(routes, list):
        wanted_hint = "summarization"
        wanted_model = "researcher"
        existing = next(
            (r for r in routes if isinstance(r, dict) and r.get("hint") == wanted_hint),
            None,
        )
        if existing is None:
            routes.append({"hint": wanted_hint, "model": wanted_model})
            config["model_routes"] = routes
            changed = True
        elif existing.get("model") != wanted_model:
            existing["model"] = wanted_model
            changed = True

    if not args.no_socket_disable:
        changed |= disable_remote_socket(config)

    if not changed:
        print("  status         : already configured (no changes)")
        return 0

    bp = backup(config_path)
    if bp:
        print(f"  backup         : {bp}")

    config_path.write_bytes(tomli_w.dumps(config).encode("utf-8"))
    print("  status         : wired")
    print()

    # Eversilver no longer registers as a SAGE-swarm node — OpenFang has
    # its own agent registry (the dashboard at :4200) and Eversilver is a
    # client of that registry, not a peer in it. The --no-register flag
    # is kept for backward compatibility but is a no-op now.
    _ = args.no_register
    _ = args.node_id

    print()
    print("Next:")
    print(f"  1. Restart Eversilver — chat panel now talks to OpenFang.")
    print(f"  2. Verify the agent is RUNNING in the dashboard:")
    print(f"       http://62.171.154.39:4200/#agents")
    print(f"  3. Smoke-test directly:")
    print(
        f"       curl -X POST {BACKEND_ENDPOINT}/chat/completions \\\n"
        f"            -H 'Authorization: Bearer $OPENFANG_API_KEY' \\\n"
        f"            -H 'Content-Type: application/json' \\\n"
        f"            -d '{{\"model\":\"{model_id}\",\"messages\":[{{\"role\":\"user\",\"content\":\"hi\"}}]}}'"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
