#!/usr/bin/env bash
# macOS/Linux launcher: sources .env (if present) then runs uvicorn.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
    set -o allexport
    # shellcheck disable=SC1091
    source .env
    set +o allexport
fi

HOST="${SWITCHAI_HOST:-127.0.0.1}"
PORT="${SWITCHAI_PORT:-8088}"

exec python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
