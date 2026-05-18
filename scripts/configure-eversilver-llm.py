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
BACKEND_SLUG = "eversilver-llm"
BACKEND_LABEL = "Eversilver LLM Backend (local)"
BACKEND_ENDPOINT = "http://127.0.0.1:8088/v1"
BACKEND_ID = "p_eversilver_llm_local"
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", help="defaults to active_user.toml lookup")
    ap.add_argument(
        "--model",
        default="gemma3:1b-it-qat",
        help=(
            "Friendly model name as defined in services/llm-backend/config.yaml "
            "(e.g. gemma3:1b-it-qat, gpt-oss:120b, gpt-4o-mini, "
            "claude-3-5-sonnet-20241022). Default: gemma3:1b-it-qat"
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

    # ── Per-workload selectors (Settings > AI side panel) ─────────────────
    workload_target = f"{BACKEND_SLUG}:{model_id}"
    for hint in CHAT_HINTS:
        key = f"{hint}_provider"
        if config.get(key) != workload_target:
            config[key] = workload_target
            changed = True

    # ── Disable runtime_enabled on local_ai so the chat path doesn't try ─
    # to spin up the embedded Ollama runtime — we delegate to the backend.
    local_ai = config.setdefault("local_ai", {})
    if local_ai.get("runtime_enabled") is not False:
        local_ai["runtime_enabled"] = False
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
    print("Next:")
    print("  1. Start (or restart) the LLM backend so it picks up any new env vars:")
    print("       cd services/llm-backend && eversilver-llm-backend")
    print("  2. Restart Eversilver so it re-reads inference_url at startup.")
    print(f"  3. Verify the model is exposed:")
    print(f"       curl {BACKEND_ENDPOINT}/models  | findstr {model_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
