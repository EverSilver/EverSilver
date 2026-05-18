# OpenFang ↔ Eversilver — feature parity map

Eversilver is a fork of [openhuman](https://github.com/tinyhumansai/openhuman).
Its primary backend is **OpenFang** ([RightNow-AI/openfang](https://github.com/RightNow-AI/openfang))
running on the Athena VPS at `http://62.171.154.39:4200`. OpenFang is an
agent operating system that exposes an OpenAI-compatible HTTP surface
plus its own native APIs for hands, channels, skills, and workflows.

This document maps every openhuman feature to whether/how it works in
this install.

## Wire diagram

```
┌─────────────────────────┐                ┌───────────────────────────────────┐
│  Eversilver desktop     │                │   Athena VPS                      │
│  (Tauri shell + Rust)   │                │                                   │
│                          │                │  ┌──────────────────────────┐   │
│  Chat panel ─────────────┼─────HTTPS─────▶│  │ OpenFang :4200            │   │
│  (OpenAiCompatible       │   Bearer       │  │  /v1/chat/completions    │   │
│   Provider)              │   <token>      │  │  /v1/models              │   │
│                          │                │  │  /api/agents             │   │
│  Local whisper-cli ──────┤                │  │  /api/hands              │   │
│  (ggml-tiny.bin)         │                │  │  /api/channels           │   │
│                          │                │  └──────────────────────────┘   │
│  Local Ollama :11434 ────┤                │                                   │
│  (bge-m3 embeddings)     │                │  /v1/embeddings  — 404 (no)      │
│                          │                │  /v1/audio/speech — 404 (no)      │
└─────────────────────────┘                └───────────────────────────────────┘
```

## Feature matrix

| openhuman feature | Surface in this install | Status |
|---|---|---|
| Agent chat (any of OpenFang's 23 agents) | `POST /v1/chat/completions` → OpenFang | ✅ |
| Athena personal assistant | `model=Athena` | ✅ default |
| Voice STT (push-to-talk) | local `whisper-cli` + `ggml-tiny.bin` | ✅ |
| Memory tree (episodic + hierarchical summaries) | local Ollama embeddings + `summarization` route → `openfang:researcher` | ✅ once `bge-m3` is pulled |
| Skills (Eversilver's tool catalog) | shipped in-binary; local | ✅ |
| Browser navigation, web research, collection | OpenFang `/api/hands` (Browser Hand, Researcher Hand, Collector Hand) — separate API from chat | ⚠ wirable; not yet invoked from Eversilver tool dispatch |
| Voice TTS (mascot lip-sync + audible replies) | OpenFang has no audio endpoint; needs **local Piper** | ❌ requires Piper install |
| Composio integrations (Gmail, Notion, GitHub, Slack, …) | hosted-backend feature; `api.eversilver.local` is dead | ❌ not reachable without a real upstream |
| Meeting agent (joins Google Meet) | hosted-backend feature | ❌ not reachable |
| Channels (Telegram, Discord, WhatsApp) | OpenFang `/api/channels` exists; needs per-channel tokens on the VPS side | ⚠ server-side, not in this client |
| Auto-updates from GitHub releases | `update.scheduler` → release feed (404 by design — no published releases) | ⚠ silent |
| Local skills | inherited from openhuman | ✅ |
| TokenJuice compression | inherited from openhuman | ✅ |

## OpenFang model namespace

Available models (call any by `model: "<name>"` or the prefixed form `openfang:<name>`):

| name | role |
|---|---|
| Athena | personal assistant (DEFAULT) |
| planner, coder, analyst, codex, researcher | task specialists |
| orchestrator, master-orchestrator | multi-agent fan-out |
| browser-hand, researcher-hand, collector-hand | desktop / web automation (also via /api/hands) |
| analytics-orchestrator, analytics-agent, notebook-executor | data work |
| code-reviewer, admin-executor, standard-executor | execution roles |
| Tsi, Trm, Hermes, Rea, leon, assistant | additional specialists |

Switch the default agent any time:

```powershell
$env:OPENFANG_API_KEY = "<your-key>"
python scripts\configure-eversilver-llm.py --model researcher
```

## What needs more work to reach full openhuman parity

1. **TTS (voice replies + mascot lip-sync).** OpenFang doesn't have an
   audio endpoint. Install [Piper](https://github.com/rhasspy/piper),
   then set in `config.toml`:
   ```toml
   [local_ai]
   tts_provider = "piper"
   tts_voice_id = "en_US-lessac-medium"
   ```
   The `PiperTtsProvider` branch in `src/eversilver/voice/factory.rs`
   handles the rest, including viseme generation for mascot lip-sync.

2. **Hands as tool calls.** OpenFang's `/api/hands` is a separate
   protocol from `/v1/chat/completions`. To let Eversilver agents
   invoke `browser-hand` / `researcher-hand` as native tool calls
   (rather than the user manually chatting them), a thin tool adapter
   would need to be added under `src/eversilver/tools/` that POSTs to
   the OpenFang hands endpoint and surfaces the result. Not done in
   this pass — Eversilver's agent currently can still ask the user to
   open OpenFang's dashboard for hand-driven work.

3. **Composio integrations & meeting agent.** Both depend on the
   hosted Eversilver/openhuman backend (`api.eversilver.local`). No
   workaround possible without standing that backend up; the openhuman
   project itself depends on the hosted service for these.

## Auth + secrets

The OpenFang token is **only** stored in the per-user
`~/.eversilver/users/<user-id>/config.toml` (TOML field `api_key`).
It's masked in any console output and never committed to git
(verified via `git grep`). Rotate with:

```powershell
$env:OPENFANG_API_KEY = "<new-token>"
python scripts\configure-eversilver-llm.py
```
