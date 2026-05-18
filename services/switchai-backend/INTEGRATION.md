# Eversilver + SwitchAI Integration

How the local SwitchAI backend slots into Eversilver as the LLM router.

```
   Eversilver (React + Rust)
        |
        | OpenAI-compatible POST /v1/chat/completions
        v
   switchai-backend (FastAPI)
        |
        | switchai.SwitchAI(provider, model, api_key).chat(...)
        v
   Upstream provider (OpenAI / Anthropic / Mistral / DeepSeek / Google /
                       Ollama / xAI / Replicate / Voyage / Deepgram)
```

## One-shot setup

From the repo root:

```powershell
pnpm --filter eversilver-app win:switchai
```

This runs `scripts/install-switchai-backend.ps1` which:

1. Verifies Python 3.11+ is on PATH
2. `pip install -e services/switchai-backend[dev]` + `tomli-w`
3. Drops a Windows Startup shortcut at
   `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Eversilver SwitchAI Backend.lnk`
   so the backend launches on login (skip with `-NoAutostart`)
4. Starts the backend in the current session if it isn't already up
5. Probes `http://127.0.0.1:8088/` to confirm it's responsive
6. Runs `scripts/configure-eversilver-switchai.py` against the active
   local user's `config.toml` to:
   * Register the SwitchAI provider in `[[cloud_providers]]`
   * Add `model_routes` entries for `reasoning`, `agentic`, `coding`
     pointing at `switchai:<provider>/<model>` (default `openai/gpt-4o-mini`)
   * Back the original config up to `config.toml.bak.<timestamp>` before
     writing

Re-running is safe — every step detects "already done" state.

## Pick a different upstream model

```powershell
pnpm --filter eversilver-app win:switchai -- -Provider mistral -Model mistral-small-latest
```

Or directly:

```powershell
python scripts/configure-eversilver-switchai.py --provider deepseek --model deepseek-chat
```

Supported providers (from the SwitchAI library): `openai`, `anthropic`,
`mistral`, `deepseek`, `google`, `ollama`, `xai`, `replicate`, `voyageai`,
`deepgram`. Model names follow each provider's native naming.

## Provide API keys

The Eversilver-side `auth_style = "bearer"` means a token can be set on the
provider entry in the AI panel; the SwitchAI backend's optional
`SWITCHAI_AUTH_TOKEN` accepts that token.

The actual upstream key (OpenAI, Anthropic, etc.) lives in
`services/switchai-backend/.env`:

```bash
# services/switchai-backend/.env
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# MISTRAL_API_KEY=...
# DEEPSEEK_API_KEY=...
# GOOGLE_API_KEY=...
# XAI_API_KEY=...
# Optional: only require local clients (Eversilver) to send a bearer
# SWITCHAI_AUTH_TOKEN=any-string-you-pick
```

After editing `.env`, restart the backend:

```powershell
pnpm --filter eversilver-app win:switchai:restart
```

## Test the backend independently

```powershell
# Probe
curl http://127.0.0.1:8088/
# -> {"name":"switchai-backend","version":"0.1.0","providers":["openai", ...]}

# List models
curl http://127.0.0.1:8088/v1/models

# Chat (with OPENAI_API_KEY set)
curl -s http://127.0.0.1:8088/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"ping"}]}'
```

## How Eversilver finds it

On the next launch, Eversilver's Rust core loads
`~/.eversilver/users/<uid>/config.toml`. The `cloud_providers` entry
registers SwitchAI as a known provider; the `model_routes` entries direct
every chat workload (reasoning, agentic, coding) to it. The factory
parses `switchai:openai/gpt-4o-mini` as
`{ provider_slug: "switchai", model: "openai/gpt-4o-mini" }` and dispatches
to the registered provider's `endpoint`.

## Backup safety

Every config write makes a timestamped backup:
`~/.eversilver/users/<uid>/config.toml.bak.YYYYMMDDTHHMMSS`.
Rollback by copying the latest `.bak.*` over `config.toml`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `python --version` says < 3.11 | Install Python 3.11+ via winget: `winget install Python.Python.3.13` |
| Port 8088 already taken | Set `SWITCHAI_PORT=9088` in `.env`, restart backend, re-run `configure-eversilver-switchai.py` (it'll need a manual endpoint patch in `config.toml`) |
| Eversilver still tries the upstream `api.eversilver.local` | Restart Eversilver. The Rust core caches routes at startup |
| Chat returns 502 | Backend can't reach upstream — check that the provider's API key is set in `services/switchai-backend/.env` and the key has credit |
| `/v1/models` returns empty | No provider keys set in env. Add at least one provider key to `.env` and restart |
