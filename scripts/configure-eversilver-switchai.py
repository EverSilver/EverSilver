"""
Wire the local SwitchAI backend into Eversilver's user config.

The chat dispatcher in `src/eversilver/agent/triage/routing.rs ::
build_remote_provider` hits whatever `config.inference_url` points at,
using `default_model` as the fallback model and `model_routes` for the
per-hint overrides. This script sets all three so chat actually goes
to SwitchAI (http://127.0.0.1:8088/v1) instead of the dead upstream
`api.eversilver.local`.

Idempotent. Always writes a timestamped `.bak` of the prior config.

Usage:
    python scripts/configure-eversilver-switchai.py
    python scripts/configure-eversilver-switchai.py --provider ollama --model phi3:mini
    python scripts/configure-eversilver-switchai.py --provider openai --model gpt-4o-mini
    python scripts/configure-eversilver-switchai.py --user-id local-abc123
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
SWITCHAI_SLUG = "switchai"
SWITCHAI_LABEL = "SwitchAI (local)"
SWITCHAI_ENDPOINT = "http://127.0.0.1:8088/v1"
SWITCHAI_ID = "p_switchai_local"
CHAT_HINTS = ("reasoning", "agentic", "coding")


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
    """Set a top-level field; return True if it actually changed."""
    if config.get(key) == value:
        return False
    config[key] = value
    return True


def upsert_switchai_provider(config: dict) -> bool:
    """Insert/refresh the SwitchAI entry in `cloud_providers`."""
    providers = config.setdefault("cloud_providers", [])
    for entry in providers:
        if entry.get("slug") == SWITCHAI_SLUG or entry.get("id") == SWITCHAI_ID:
            changed = False
            for field, want in (
                ("endpoint", SWITCHAI_ENDPOINT),
                ("label", SWITCHAI_LABEL),
                ("auth_style", "bearer"),
            ):
                if entry.get(field) != want:
                    entry[field] = want
                    changed = True
            return changed
    providers.append(
        {
            "id": SWITCHAI_ID,
            "slug": SWITCHAI_SLUG,
            "label": SWITCHAI_LABEL,
            "endpoint": SWITCHAI_ENDPOINT,
            "auth_style": "bearer",
        }
    )
    return True


def set_model_routes(config: dict, model_id: str) -> bool:
    """Wire chat hints (reasoning/agentic/coding) to `model_id`.

    The Rust router's `model` field is whatever string the OpenAI-compatible
    backend expects in the JSON body, which for SwitchAI is `<provider>/<model>`
    (e.g. `ollama/phi3:mini`). No `switchai:` prefix — that's a different
    grammar used by the AI-panel-style per-workload selectors.
    """
    routes = config.setdefault("model_routes", [])
    # Replace any routes for the chat hints; leave unrelated hints (e.g.
    # 'embedding', 'memory') untouched so users can pin those separately.
    filtered = [r for r in routes if isinstance(r, dict) and r.get("hint") not in CHAT_HINTS]
    rebuilt = filtered + [{"hint": h, "model": model_id} for h in CHAT_HINTS]
    if rebuilt == routes:
        return False
    config["model_routes"] = rebuilt
    return True


def set_per_workload_provider_strings(config: dict, model_id: str) -> bool:
    """The Rust schema also reads top-level workload fields
    (`reasoning_provider`, `agentic_provider`, `coding_provider`) for the
    AI-panel-side selectors. Mirror the routes there for consistency so
    Settings -> AI shows SwitchAI as the active provider.
    """
    changed = False
    for hint in CHAT_HINTS:
        key = f"{hint}_provider"
        # Format: `switchai:<provider/model>` — matches CloudProvider.slug grammar.
        target = f"{SWITCHAI_SLUG}:{model_id}"
        if config.get(key) != target:
            config[key] = target
            changed = True
    return changed


def disable_remote_socket(config: dict) -> bool:
    """Stop Eversilver from auto-connecting to the dead api.eversilver.local
    socket on startup — the WS reconnect storm is noise + battery drain.
    """
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
        "--provider",
        default="ollama",
        help="Upstream provider (ollama, openai, anthropic, mistral, deepseek, "
        "google, xai, ...). Default: ollama",
    )
    ap.add_argument(
        "--model",
        default="phi3:mini",
        help="Model id within the provider. Default: phi3:mini (Ollama local).",
    )
    ap.add_argument(
        "--no-socket-disable",
        action="store_true",
        help="Leave socket.auto_connect alone (default: disable WS to dead backend).",
    )
    args = ap.parse_args()

    user_dir = find_active_user_dir(args.user_id)
    config_path, config = load_or_init_config(user_dir)
    model_id = f"{args.provider}/{args.model}"

    print(f"  user dir : {user_dir}")
    print(f"  config   : {config_path}")
    print(f"  target   : {model_id} via {SWITCHAI_ENDPOINT}")

    changed = False

    # ── Primary path: native local_ai arm (Ollama, no auth) ───────────────
    # Eversilver's `build_local_provider_with_config` directly constructs
    # an OpenAiCompatibleProvider against `ollama_base_url()/v1` with
    # auth_style=None when api_key is empty. That bypasses every cloud
    # auth check, every `auth-profiles.json` lookup, and every upstream
    # backend (api.eversilver.local) dependency. Per-workload provider
    # strings of the form `"ollama:<model>"` route through this arm.
    local_ai = config.setdefault("local_ai", {})
    if local_ai.get("runtime_enabled") is not True:
        local_ai["runtime_enabled"] = True
        changed = True
    if local_ai.get("provider") != args.provider:
        local_ai["provider"] = args.provider
        changed = True
    if local_ai.get("chat_model_id") != args.model:
        local_ai["chat_model_id"] = args.model
        changed = True
    # Empty api_key on local_ai => OpenAiCompatibleProvider uses AuthStyle::None
    if local_ai.get("api_key", "") != "":
        local_ai["api_key"] = ""
        changed = True

    # Per-workload routing strings use the legacy `<provider>:<model>` grammar
    # (e.g. "ollama:phi3:mini"). The factory routes this through the LOCAL arm
    # because the slug "ollama" matches the local provider kind.
    local_routing_target = f"{args.provider}:{args.model}"
    for hint in CHAT_HINTS:
        key = f"{hint}_provider"
        if config.get(key) != local_routing_target:
            config[key] = local_routing_target
            changed = True

    # default_model and model_routes are used by the REMOTE arm; keep them
    # consistent so any code that falls back to remote routing still has a
    # valid model id.
    changed |= set_field(config, "default_model", model_id)
    changed |= set_model_routes(config, model_id)

    # ── Secondary path: SwitchAI cloud provider entry (for openai/anthropic/etc) ──
    # Keep the registration so the user can pick it from Settings > AI later
    # without rerunning this script.
    changed |= set_field(config, "inference_url", SWITCHAI_ENDPOINT)
    changed |= upsert_switchai_provider(config)
    changed |= set_field(config, "primary_cloud", SWITCHAI_ID)

    if not args.no_socket_disable:
        changed |= disable_remote_socket(config)

    if not changed:
        print("  status   : already configured (no changes)")
        return 0

    bp = backup(config_path)
    if bp:
        print(f"  backup   : {bp}")

    config_path.write_bytes(tomli_w.dumps(config).encode("utf-8"))
    print(f"  inference_url    : {SWITCHAI_ENDPOINT}")
    print(f"  default_model    : {model_id}")
    print(f"  model_routes     : {', '.join(CHAT_HINTS)} -> {model_id}")
    print(f"  primary_cloud    : {SWITCHAI_ID}")
    print(f"  socket auto_connect : disabled (avoid WS storm to dead backend)")
    print("  status   : wired")
    print()
    print("Next:")
    print(f"  1. Make sure the upstream provider key is set (e.g. {args.provider.upper()}_API_KEY)")
    print("     in services/switchai-backend/.env -- not needed for ollama.")
    print("  2. Restart the SwitchAI backend so it picks up the env.")
    print("  3. Restart Eversilver so it re-reads inference_url at startup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
