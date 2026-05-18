# Eversilver LLM Backend

An **OpenAI-compatible** HTTP proxy, backed by [LiteLLM]. It exposes a
single endpoint surface — `/v1/chat/completions`, `/v1/embeddings`,
`/v1/models` — and routes each request to the right provider (Ollama
local, Ollama Cloud, OpenAI, Anthropic, Mistral, DeepSeek, Gemini, Groq,
xAI, …) based on a YAML model registry.

It's the replacement for the previous SwitchAI-backed service, which
broke under Python 3.14 due to fragile transitive dependencies
(cairosvg, mistralai 1.x, deepgram 4.x, replicate). LiteLLM is
pure-Python, has 100+ providers in a single import, and has a
`drop_params=True` mode that silently strips parameters individual
providers don't support — so the OpenAI request shape Just Works.

[LiteLLM]: https://github.com/BerriAI/litellm

## Quick start

```powershell
# From repo root
cd services/llm-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .

# Copy and edit env (optional — only needed for cloud providers)
Copy-Item .env.example .env

# Run
eversilver-llm-backend
# or: python -m uvicorn app.main:app --host 127.0.0.1 --port 8088
```

Smoke-check it's up:

```powershell
curl http://127.0.0.1:8088/health
curl http://127.0.0.1:8088/v1/models
```

## What you get

| Endpoint                     | Behavior                                                          |
| ---------------------------- | ----------------------------------------------------------------- |
| `GET /`                      | Service identity + which providers have keys configured           |
| `GET /health`                | `{"status":"ok"}` liveness probe                                  |
| `GET /v1/models`             | OpenAI-shape list, filtered to models whose `requires_env` is met |
| `POST /v1/chat/completions`  | OpenAI chat. `stream: true` yields SSE chunks + `data: [DONE]`    |
| `POST /v1/embeddings`        | OpenAI embeddings, single string or batch                         |

## Model registry (`config.yaml`)

Each entry maps a **friendly name** that callers send in the `model`
field to a LiteLLM provider spec, optional `api_base`, and the env
vars required for that provider to be considered available:

```yaml
models:
  - name: gemma3:1b-it-qat                 # what callers send
    model: ollama_chat/gemma3:1b-it-qat    # what LiteLLM sees
    api_base: http://localhost:11434
    requires_env: []                       # always available

  - name: gpt-oss:120b
    model: ollama_chat/gpt-oss:120b        # Ollama Cloud
    api_base: https://ollama.com
    api_key: os.environ/OLLAMA_API_KEY
    requires_env: [OLLAMA_API_KEY]

  - name: gpt-4o-mini
    model: openai/gpt-4o-mini
    requires_env: [OPENAI_API_KEY]
```

Models whose `requires_env` vars are not set are hidden from
`/v1/models` and rejected on call. Add a new provider by adding a new
entry — no code changes needed.

## Auth

Set `LLM_BACKEND_AUTH_TOKEN=<secret>` to require
`Authorization: Bearer <secret>` on all `/v1/*` endpoints. Leave unset
for an open localhost-bound proxy (the default — appropriate for the
Eversilver desktop app talking to a co-located backend).

## Tests

```powershell
python -m pytest -q
```

18 tests cover the health endpoints, model filtering, registry
resolution, non-streaming chat (with mocked LiteLLM), SSE streaming
format, embeddings batch/single, upstream error envelopes, and the
optional auth middleware.

## Files

```
services/llm-backend/
├── app/
│   ├── auth.py              # Optional bearer middleware
│   ├── config.py            # YAML loader + pydantic-settings
│   ├── litellm_client.py    # Registry resolver → litellm.completion
│   ├── main.py              # FastAPI app + uvicorn entrypoint
│   ├── schemas.py           # OpenAI-shape pydantic models
│   └── routers/
│       ├── chat.py          # /v1/chat/completions + SSE streaming
│       ├── embeddings.py    # /v1/embeddings
│       ├── health.py        # /, /health
│       └── models.py        # /v1/models
├── tests/                   # 18 tests, pytest + TestClient
├── config.yaml              # Pre-seeded model registry
├── .env.example
└── pyproject.toml
```

See [`INTEGRATION.md`](./INTEGRATION.md) for wiring this into the
Eversilver desktop app, Ollama Cloud sign-in, and adding new providers.
