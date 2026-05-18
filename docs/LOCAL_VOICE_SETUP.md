# Local voice (whisper) setup

After studying the openhuman upstream we discovered Eversilver already
ships a fully-working **local Whisper STT** path mirrored from
`openhuman/src/openhuman/voice/factory.rs`. The cloud STT path
(`/openai/v1/audio/transcriptions`) requires a session JWT against the
hosted backend that the local-only install doesn't have, so the right
choice for a self-hosted deployment is the local path.

## Architecture

```
Push-to-talk button (Renderer)
  └─ voice.transcribe RPC (Tauri JSON-RPC)
     └─ Rust core: SttProvider chosen by config.local_ai.stt_provider
        ├─ "whisper" → WhisperSttProvider
        │              └─ whisper-rs (in-process when whisper_in_process=true)
        │                 └─ ggml-<size>.bin model file
        │                    └─ {workspace}/bin/whisper/ggml-<size>.bin
        └─ "cloud"   → CloudSttProvider
                       └─ POST {api_url}/openai/v1/audio/transcriptions
                          (requires backend JWT — not viable for local-only)
```

## What `configure-eversilver-llm.py` sets

| Field | Value | Why |
|---|---|---|
| `local_ai.runtime_enabled` | `true` | Enables the local-AI service that owns whisper-rs |
| `local_ai.stt_provider` | `"whisper"` | Selects the local Whisper branch in `voice/factory.rs` |
| `local_ai.whisper_in_process` | `true` | Use whisper-rs in-process (no external `WHISPER_BIN`) |
| `local_ai.stt_model_id` | `"tiny"` | 75 MB model — near real-time on CPU |
| `local_ai.usage.speech_to_text` | `true` | Per-feature gate |
| `local_ai.usage.chat` | `false` | Chat still routes through llm-backend |

## Required files

The whisper-rs engine looks for the GGML model at:

```
~/.eversilver/bin/whisper/ggml-tiny.bin
```

Download once (75 MB):

```powershell
$dir = "$env:USERPROFILE\.eversilver\bin\whisper"
New-Item -ItemType Directory -Path $dir -Force | Out-Null
Invoke-WebRequest `
  -Uri "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin?download=true" `
  -OutFile "$dir\ggml-tiny.bin"
```

```bash
mkdir -p ~/.eversilver/bin/whisper
curl -fL -o ~/.eversilver/bin/whisper/ggml-tiny.bin \
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin?download=true"
```

For better accuracy at the cost of CPU, swap `tiny` for
`base` (148 MB), `small` (488 MB), `medium` (1.5 GB), or
`large-v3-turbo` (1.5 GB, the recommended ship default upstream).
Update `local_ai.stt_model_id` to match.

## Why not the cloud path

`src/eversilver/voice/cloud_transcribe.rs` requires a non-empty
`get_session_token(config)` JWT. The local install never has one. Even
with a stub backend, OpenAI's Whisper endpoint requires its own API key
and credits; routing through `litellm.transcription` collides with any
`OPENAI_BASE_URL` env override the user has set globally (we saw
404/429 redirect failures when relying on this path).

Local whisper is fully self-contained: one 75 MB model file, no keys,
no rate limits, no network.

## TTS

Cloud TTS uses ElevenLabs via the hosted backend (also JWT-gated).
Local TTS uses `piper` — a separate ~30 MB binary plus a voice `.onnx`
file. Eversilver has the `PiperTtsProvider` branch wired in
`voice/factory.rs`; install Piper from
https://github.com/rhasspy/piper/releases and set `PIPER_BIN` plus
`local_ai.tts_provider = "piper"` in `config.toml`. This isn't
auto-configured today — the configure script keeps `tts_provider =
"cloud"` until the user opts in.
