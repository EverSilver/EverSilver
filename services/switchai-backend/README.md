# switchai-backend

OpenAI-compatible FastAPI gateway that wraps the
[SwitchAI](https://github.com/yelboudouri/SwitchAI) library so any client that
speaks the OpenAI REST API can transparently talk to OpenAI, Anthropic,
DeepSeek, Google, Mistral, Ollama, Replicate, VoyageAI, xAI, or Deepgram.

This is the backing service for Eversilver's "custom inference" path — point
Eversilver's `api_url` at `http://127.0.0.1:8088/v1` and everything just works.

## Endpoints

| Method | Path                          | Notes |
|--------|-------------------------------|-------|
| POST   | `/v1/chat/completions`        | OpenAI chat (sync + `stream: true` SSE) |
| POST   | `/v1/embeddings`              | OpenAI embeddings (single or batch input) |
| POST   | `/v1/audio/transcriptions`    | Multipart `file` + `model` + optional `language` |
| POST   | `/v1/images/generations`      | Returns `b64_json` PNGs |
| GET    | `/v1/models`                  | Lists every model whose provider has an env key |
| GET    | `/health`                     | `{"status":"ok"}` |
| GET    | `/`                           | `{name, version, providers}` — Eversilver probe |

The `model` field uses **`<provider>/<model>`** to disambiguate, e.g.:

```
openai/gpt-4o-mini
deepseek/deepseek-chat
mistral/mistral-small-latest
anthropic/claude-3-5-sonnet-20240620
google/gemini-2.0-flash
xai/grok-2-latest
ollama/llama3.2
```

Unqualified model names fall back to `SWITCHAI_DEFAULT_PROVIDER`.

## Install

Requires Python ≥ 3.11.

```bash
# from this directory
pip install -e .
# or, with uv:
uv pip install -e .

# install dev extras for running tests
pip install -e ".[dev]"
```

All deps are pure-Python wheels — no MSVC toolchain needed on Windows.

## Configure

Copy `.env.example` to `.env` and fill in only the provider keys you actually
need:

```bash
cp .env.example .env
```

Important settings:

| Var | Purpose |
|-----|---------|
| `SWITCHAI_HOST` / `SWITCHAI_PORT` | bind address (defaults: `127.0.0.1:8088`) |
| `SWITCHAI_DEFAULT_PROVIDER` | provider used when `model` has no `<provider>/` prefix |
| `SWITCHAI_DEFAULT_MODEL` | model used if the request omits it entirely |
| `SWITCHAI_AUTH_TOKEN` | **(optional)** require `Authorization: Bearer …` on `/v1/*` |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY`, `REPLICATE_API_KEY`, `VOYAGEAI_API_KEY`, `XAI_API_KEY`, `DEEPGRAM_API_KEY` | per-provider keys |

Ollama is local-only — no key required, but you need an `ollama` daemon
reachable wherever SwitchAI looks.

## Run

```bash
# Windows
./scripts/run.ps1

# macOS / Linux
./scripts/run.sh

# Or directly
python -m uvicorn app.main:app --host 127.0.0.1 --port 8088

# Or via the console script
switchai-backend
```

## Eversilver wiring

In Eversilver's "custom inference" / custom OpenAI-compatible config, set:

```
api_url:  http://127.0.0.1:8088/v1
api_key:  (any value, or the SWITCHAI_AUTH_TOKEN you set above)
model:    openai/gpt-4o-mini   # or any "<provider>/<model>" pair
```

Eversilver's runtime probe hits `GET /` which returns:

```json
{
  "name": "switchai-backend",
  "version": "0.1.0",
  "providers": ["openai", "mistral", "ollama"]
}
```

## Curl examples

### Sync chat
```bash
curl -s http://127.0.0.1:8088/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role":"user","content":"hi"}],
    "max_tokens": 64
  }'
```

### Streaming chat
```bash
curl -N http://127.0.0.1:8088/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role":"user","content":"tell me a joke"}],
    "stream": true
  }'
```

### Embeddings
```bash
curl -s http://127.0.0.1:8088/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/text-embedding-3-small",
    "input": ["hello", "world"]
  }'
```

### Models
```bash
curl -s http://127.0.0.1:8088/v1/models | python -m json.tool
```

### Transcription
```bash
curl -s http://127.0.0.1:8088/v1/audio/transcriptions \
  -F "file=@audio.wav" \
  -F "model=openai/whisper-1" \
  -F "language=en"
```

## Dev loop

```bash
pip install -e ".[dev]"
pytest -q
```

Tests mock `switchai.SwitchAI` end-to-end — they never hit a real provider.

## Architecture

```
HTTP request
  │
  ▼
FastAPI router  ─►  resolve_model("provider/model")
                       │
                       ▼
                 get_client(provider, model)  ◄── (provider, model) cache
                       │
                       ▼
                 switchai.SwitchAI.chat / embed / transcribe / generate_image
                       │
                       ▼
                 ChatResponse / EmbeddingResponse / etc.
                       │
                       ▼
                 mapped to OpenAI envelope
                       │
                       ▼
                 JSON  or  SSE  response
```

Errors from upstream providers are normalized to OpenAI's
`{"error":{"message","type","code"}}` envelope. Unsupported providers/models
return `400`; upstream failures return `502`; missing/invalid auth returns
`401`.

## License

MIT.
