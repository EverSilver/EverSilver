#!/usr/bin/env bash
# Run the LLM backend in the foreground (POSIX).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  . .venv/bin/activate
fi
exec python -m uvicorn app.main:app \
  --host "${LLM_BACKEND_BIND_HOST:-127.0.0.1}" \
  --port "${LLM_BACKEND_BIND_PORT:-8088}"
