"""
Wire the local SwitchAI backend into Eversilver's user config.

Eversilver routes LLM workloads to entries in `config.cloud_providers`. This
script registers an entry for the local SwitchAI backend
(`http://127.0.0.1:8088/v1`) and sets the chat workloads (reasoning,
agentic, coding) to use it. Idempotent -- running twice does nothing
destructive.

Run after the SwitchAI backend is installed and after Eversilver has been
launched at least once (so the per-user dir exists).

Usage:
    python scripts/configure-eversilver-switchai.py
    python scripts/configure-eversilver-switchai.py --provider openai --model gpt-4o-mini
    python scripts/configure-eversilver-switchai.py --user-id local-abc123
"""
from __future__ import annotations
import argparse
import os
import shutil
import sys
import tomllib
from datetime import datetime
from pathlib import Path

try:
    import tomli_w  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    print(
        "tomli-w is required. Install with: pip install tomli-w",
        file=sys.stderr,
    )
    sys.exit(2)


ROOT = Path.home() / ".eversilver"
SWITCHAI_SLUG = "switchai"
SWITCHAI_LABEL = "SwitchAI (local)"
SWITCHAI_ENDPOINT = "http://127.0.0.1:8088/v1"
SWITCHAI_ID = "p_switchai_local"


def find_active_user_dir(explicit: str | None) -> Path:
    """Return the workspace dir for the active local user."""
    if explicit:
        return ROOT / "users" / explicit
    active = ROOT / "active_user.toml"
    if not active.exists():
        sys.exit(
            f"No active_user.toml at {active}. Launch Eversilver once and "
            "use the 'Continue without an account' button so a local user dir "
            "is created, then re-run."
        )
    parsed = tomllib.loads(active.read_text(encoding="utf-8"))
    uid = parsed.get("user_id")
    if not uid:
        sys.exit(f"active_user.toml at {active} has no user_id field.")
    return ROOT / "users" / uid


def load_or_init_config(user_dir: Path) -> tuple[Path, dict]:
    """Load the user's config.toml, creating an empty one if missing."""
    path = user_dir / "config.toml"
    if not path.exists():
        # The Rust core normally creates this on first launch. If we get
        # here, just create the file empty and let the Rust schema layer
        # fill in defaults the next time it loads.
        user_dir.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return path, data


def upsert_switchai_provider(config: dict) -> bool:
    """Insert or refresh the SwitchAI provider entry. Returns True if changed."""
    providers = config.setdefault("cloud_providers", [])
    for entry in providers:
        if entry.get("slug") == SWITCHAI_SLUG or entry.get("id") == SWITCHAI_ID:
            updated = False
            if entry.get("endpoint") != SWITCHAI_ENDPOINT:
                entry["endpoint"] = SWITCHAI_ENDPOINT
                updated = True
            if entry.get("label") != SWITCHAI_LABEL:
                entry["label"] = SWITCHAI_LABEL
                updated = True
            if entry.get("auth_style") != "bearer":
                entry["auth_style"] = "bearer"
                updated = True
            return updated
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


def set_chat_routing(config: dict, provider: str, model: str) -> bool:
    """Register a top-level model_routes entry pointing at switchai.

    Schema: model_routes is `Vec<{ hint, model }>` per
    src/eversilver/config/schema/routes.rs:ModelRouteConfig. The `model`
    field is in `<slug>:<provider/model>` form which the Rust factory
    resolves against `cloud_providers` at runtime.
    """
    target_model = f"{SWITCHAI_SLUG}:{provider}/{model}"
    routes = config.setdefault("model_routes", [])

    # Drop any prior switchai routes (idempotent).
    routes_changed = False
    filtered = [r for r in routes if not (isinstance(r, dict) and r.get("model", "").startswith(f"{SWITCHAI_SLUG}:"))]
    if len(filtered) != len(routes):
        routes_changed = True

    for hint in ("reasoning", "agentic", "coding"):
        filtered.append({"hint": hint, "model": target_model})
        routes_changed = True

    config["model_routes"] = filtered
    return routes_changed


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup_path = path.with_suffix(f".toml.bak.{stamp}")
    shutil.copy2(path, backup_path)
    return backup_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--user-id",
        help="Eversilver user id (defaults to active_user.toml lookup)",
    )
    ap.add_argument(
        "--provider",
        default="openai",
        help="SwitchAI upstream provider (openai, anthropic, mistral, "
        "deepseek, google, ollama, xai, ...). Default: openai",
    )
    ap.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="Model id within the provider. Default: gpt-4o-mini",
    )
    args = ap.parse_args()

    user_dir = find_active_user_dir(args.user_id)
    config_path, config = load_or_init_config(user_dir)
    print(f"  user dir : {user_dir}")
    print(f"  config   : {config_path}")

    changed_provider = upsert_switchai_provider(config)
    changed_routing = set_chat_routing(config, args.provider, args.model)

    if not (changed_provider or changed_routing):
        print("  status   : already configured (no changes)")
        return 0

    backup_path = backup(config_path) if config_path.read_text(encoding="utf-8") else None
    if backup_path:
        print(f"  backup   : {backup_path}")

    config_path.write_bytes(tomli_w.dumps(config).encode("utf-8"))
    print(f"  provider : {SWITCHAI_LABEL}  endpoint={SWITCHAI_ENDPOINT}")
    print(f"  routing  : reasoning, agentic, coding -> {SWITCHAI_SLUG}:{args.provider}/{args.model}")
    print("  status   : wired")
    print()
    print("Next:")
    print("  1. Provide an API key for your chosen upstream provider in the")
    print(f"     SwitchAI backend's .env (e.g. {args.provider.upper()}_API_KEY=...)")
    print("  2. Restart the SwitchAI backend so it picks up the new key.")
    print("  3. Restart Eversilver (it caches the routing config at startup).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
