# Integrating the LLM Backend with Eversilver

This service is OpenAI-compatible, so the Eversilver Rust core talks to
it via its existing `OpenAiCompatibleProvider` HTTP path — the same one
that previously pointed at SwitchAI. We just swap the URL and model
allowlist.

## TL;DR

1. Start the backend on `127.0.0.1:8088` (autostarts via the install
   script below).
2. Point Eversilver at it by running
   `scripts/configure-eversilver-llm.py`, which patches the active
   user's `config.toml`.
3. Restart Eversilver. Chat works.

## How the wiring works

Eversilver's chat dispatcher (`src/eversilver/agent/triage/routing.rs`)
calls `build_remote_provider`, which reads from the user's
`config.toml`:

```toml
inference_url   = "http://127.0.0.1:8088/v1/chat/completions"
default_model   = "gemma3:1b-it-qat"
api_key         = "local-no-auth"   # non-empty required by bearer-style auth
model_routes    = { reasoning = "gemma3:1b-it-qat", ... }
```

The `configure-eversilver-llm.py` script writes those fields plus the
per-workload provider strings and disables the dead websocket. The
Eversilver MVP chat allowlist is bypassed because we run as a remote
provider, not the `local_ai` path.

## Ollama Cloud

Free hosted inference for big models (`gpt-oss:120b`, `qwen3-coder:480b`,
`llama3.3:70b`) — no GPU on your laptop required.

```powershell
# Install the Ollama CLI from https://ollama.com/download
ollama signin            # opens browser → returns a key
# Then either:
$env:OLLAMA_API_KEY = "<key>"     # session
# or persist in services/llm-backend/.env
```

Once `OLLAMA_API_KEY` is set, those models appear in
`GET /v1/models` and can be selected via Eversilver's model picker.

## Adding a provider

Edit `services/llm-backend/config.yaml`:

```yaml
models:
  - name: my-friendly-name
    model: anthropic/claude-3-5-sonnet-20241022
    requires_env: [ANTHROPIC_API_KEY]
```

Restart the backend (the YAML is cached per-process). The model
appears in `/v1/models` the moment `ANTHROPIC_API_KEY` is exported.

## Switching the default chat model

Either:

- Set `LLM_BACKEND_DEFAULT_CHAT_MODEL=<name>` in `.env`, or
- Run `python scripts/configure-eversilver-llm.py --model <name>`,
  which updates Eversilver's `default_model` and all `model_routes`.

## Smoke test

```powershell
curl http://127.0.0.1:8088/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{ "model": "gemma3:1b-it-qat",
        "messages": [{"role":"user","content":"Say Pong."}] }'
```

Should return a `chat.completion` with `choices[0].message.content`
containing "Pong" within a couple of seconds.

## Troubleshooting

| Symptom                                            | Cause                                                    | Fix                                                          |
| -------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------ |
| `GET /v1/models` doesn't show a cloud model        | Required env var not set in the backend's process env    | Set it in `.env` (not just your shell), then restart backend |
| `401` on every `/v1/*` call                        | `LLM_BACKEND_AUTH_TOKEN` set but Eversilver's `api_key` doesn't match | Match them or unset the token                                |
| `502 upstream_error: connection refused`           | Ollama daemon not running                                | `ollama serve` (Win: starts automatically after install)     |
| Eversilver shows "authentication issue"            | `api_key` empty in user's `config.toml`                  | Re-run the configure script — it sets a non-empty placeholder |
| Chat hangs forever after dispatch                  | Eversilver still pointing at old SwitchAI service        | Re-run the configure script and restart Eversilver           |
