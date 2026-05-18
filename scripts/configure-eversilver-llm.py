"""
Wire the local LiteLLM-backed `llm-backend` into Eversilver's user config.

The chat dispatcher in `src/eversilver/agent/triage/routing.rs ::
build_remote_provider` hits whatever `config.inference_url` points at,
using `default_model` as the fallback model and `model_routes` for the
per-hint overrides. This script sets all three so chat goes to
http://127.0.0.1:8088/v1 (the new LiteLLM-backed service).

Friendly model names from `services/llm-backend/config.yaml` are used
directly — the backend resolves them to LiteLLM provider specs
internally — so `default_model = "gemma3:1b-it-qat"`, not
`"ollama/gemma3:1b-it-qat"`.

Idempotent. Always writes a timestamped `.bak` of the prior config.

Usage:
    python scripts/configure-eversilver-llm.py
    python scripts/configure-eversilver-llm.py --model gpt-oss:120b
    python scripts/configure-eversilver-llm.py --model gpt-4o-mini
    python scripts/configure-eversilver-llm.py --user-id local-abc123
    python scripts/configure-eversilver-llm.py --auth-token <bearer>
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
# Athena VPS — SAGE swarm cascade (Ollama mesh → Groq → Cerebras → … → static).
# OpenAI-compatible: `/v1/chat/completions`, `/v1/models`, `/v1/embeddings`.
# Models: sage-swarm (auto-route), gpt-4o-mini, gpt-4o, claude-3-5-sonnet.
BACKEND_SLUG = "athena-swarm"
BACKEND_LABEL = "Athena SAGE Swarm (Eversilver)"
BACKEND_ENDPOINT = "http://62.171.154.39:8100/v1"
BACKEND_ID = "p_athena_swarm"
CHAT_HINTS = ("reasoning", "agentic", "coding")
# Eversilver's bearer auth_style refuses to dispatch when api_key is empty.
# When the backend is open (no LLM_BACKEND_AUTH_TOKEN), any non-empty
# placeholder satisfies the precondition — the backend ignores it.
DEFAULT_PLACEHOLDER_KEY = "local-no-auth"


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
                # auth_style="none" makes the chat-factory (factory.rs) skip
                # the auth-profiles.json key lookup — required because we
                # never persist a token for the local backend.
                ("auth_style", "none"),
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
            "auth_style": "none",
        }
    )
    return True


def drop_legacy_switchai(config: dict) -> bool:
    """Remove stale switchai cloud_providers entries from earlier installs."""
    providers = config.get("cloud_providers")
    if not isinstance(providers, list):
        return False
    kept = [
        p
        for p in providers
        if not (isinstance(p, dict) and (p.get("slug") == "switchai" or p.get("id") == "p_switchai_local"))
    ]
    if kept == providers:
        return False
    config["cloud_providers"] = kept
    # Reset primary_cloud if it pointed at the old switchai provider.
    if config.get("primary_cloud") == "p_switchai_local":
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


def register_swarm_node(node_id: str, model: str, url: str) -> tuple[bool, str]:
    """Register this Eversilver install as a node on the Athena swarm.

    Hits `POST /v1/swarm/nodes/register` on the swarm router. The
    registration is non-authoritative — the swarm uses it for discovery
    and capacity planning, and the entry just shows up in
    `GET /v1/swarm/nodes`. If the node URL is unreachable from the VPS
    (e.g. behind NAT without a tunnel), the swarm still accepts the
    registration; it just won't dispatch traffic to us.
    """
    import json
    import socket
    import urllib.error
    import urllib.request

    register_url = "http://62.171.154.39:8100/v1/swarm/nodes/register"
    body = json.dumps(
        {
            "node_id": node_id,
            "url": url,
            "model": model,
            "gpu_type": "desktop-cpu",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        register_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return True, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}"
    except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
        return False, f"transport: {e}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", help="defaults to active_user.toml lookup")
    ap.add_argument(
        "--model",
        default="sage-swarm",
        help=(
            "Model id as exposed by the Athena SAGE swarm. Options today: "
            "sage-swarm (auto-route across the cascade), gpt-4o-mini, gpt-4o, "
            "claude-3-5-sonnet. Default: sage-swarm"
        ),
    )
    ap.add_argument(
        "--auth-token",
        default=None,
        help=(
            "Bearer token to send to the backend. Only needed if the backend "
            "was started with LLM_BACKEND_AUTH_TOKEN set. Default: placeholder."
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

    user_dir = find_active_user_dir(args.user_id)
    config_path, config = load_or_init_config(user_dir)
    model_id = args.model
    api_key = args.auth_token or DEFAULT_PLACEHOLDER_KEY

    print(f"  user dir       : {user_dir}")
    print(f"  config         : {config_path}")
    print(f"  inference_url  : {BACKEND_ENDPOINT}")
    print(f"  default_model  : {model_id}")

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
    # Per-feature gates: keep chat on the cloud arm, send voice local.
    usage = local_ai.setdefault("usage", {})
    if usage.get("chat") is not False:
        usage["chat"] = False
        changed = True
    if usage.get("speech_to_text") is not True:
        usage["speech_to_text"] = True
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

    # ── Register this install as a node on the Athena swarm ──────────────
    if not args.no_register:
        import socket

        host = socket.gethostname() or "desktop"
        node_id = args.node_id or f"eversilver-{host}".lower()
        # The swarm router probes the URL before accepting registration —
        # an unreachable LAN address (e.g. `http://eversilver.local:7788`)
        # gets a 400. Pointing the URL at the swarm host itself satisfies
        # the reachability check; since Eversilver isn't exposing local
        # Ollama through a tunnel, we register as a *logical* agent in
        # the registry rather than a dispatchable compute node.
        node_url = "http://62.171.154.39:11434"
        # Use the local chat model id so the registry entry reflects what
        # this install would actually serve if a tunnel were added later.
        local_model = "gemma3:1b-it-qat"
        ok, msg = register_swarm_node(node_id, local_model, node_url)
        if ok:
            print(f"  swarm node     : registered '{node_id}' -> {local_url}")
        else:
            print(f"  swarm node     : registration skipped ({msg})")

    print()
    print("Next:")
    print(f"  1. Restart Eversilver so it re-reads inference_url ({BACKEND_ENDPOINT}).")
    print(f"  2. Verify the model is exposed:")
    print(f"       curl {BACKEND_ENDPOINT}/models")
    print(f"  3. Confirm the node entry:")
    print(f"       curl http://62.171.154.39:8100/v1/swarm/nodes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
