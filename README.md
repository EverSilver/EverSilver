<h1 align="center">Eversilver</h1>

<p align="center"><em>Personal AI super intelligence — private, simple, powerful.</em></p>

<p align="center">
  <img src="./logo.png" alt="Eversilver" width="180" />
</p>

---

Eversilver is a single-binary, local-first AI assistant that lives on your
desktop as a floating mascot, plugs into the tools you already use, and
keeps every byte of your personal context on your machine.

## What's inside

- **Native desktop shell** built on Tauri + a vendored CEF runtime — full
  Chromium parity for Google Meet, OAuth flows, and complex web tools.
- **Local-first memory tree** stored in SQLite, mirrored as Markdown into
  an Obsidian-compatible vault you can read with any editor.
- **Tool routing** that lands each task on the right LLM (reasoning, fast,
  vision) under a single subscription.
- **Voice in / voice out** with mascot lip-sync, including a live Google
  Meet participant agent.
- **Hot-swappable mascot renderer** — ships with a 2D SVG character
  (moonlight palette); drop in any `.vrm`/`.glb` to render a 3D character
  with face + viseme + lip-sync wiring.
- **One-click integrations** with Gmail, Notion, GitHub, Slack, Stripe,
  Calendar, Drive, Linear, Jira and 110+ more — every connection exposed
  as a typed tool.
- **Drop-in auth + UPI/Razorpay billing** scaffolding (Indian payments
  first-class). Off by default; one env flip turns billing on.

## Quick start (Windows)

```powershell
# One-shot install of every dev dependency
pwsh -File scripts/bootstrap.ps1

# Build the Windows installer (.msi + .exe)
pnpm --filter eversilver-app win:build:release

# Install + launch
pnpm --filter eversilver-app win:install
```

The build produces both an **NSIS** per-user installer (no admin needed)
and an **MSI** machine-wide installer in
`app/src-tauri/target/release/bundle/`.

## Quick start (other platforms)

```bash
pnpm install
pnpm --filter eversilver-app macos:build:release   # macOS
pnpm dev                                            # web-only dev mode
```

## Project layout

```
eversilver/
├── app/                          desktop shell (Tauri + React + Vite)
│   ├── src/                      React UI
│   │   ├── features/
│   │   │   ├── auth/             login + session (Local or Supabase)
│   │   │   ├── paywall/          tiers + UPI/Razorpay checkout
│   │   │   ├── human/Mascot/     2D Ghosty SVG + optional VRM 3D
│   │   │   └── …
│   │   ├── mascot/               floating mascot window
│   │   ├── overlay/              translucent overlay window
│   │   └── main.tsx              entry (wraps App in AuthGate)
│   ├── src-tauri/                Rust shell (Tauri commands, OS bridges)
│   │   └── vendor/
│   │       ├── tauri-cef/                CEF-backed Tauri runtime fork
│   │       └── tauri-plugin-notification/ notification plugin fork
│   └── package.json
├── src/eversilver/               Rust core library (agent, memory, RAG)
├── packages/                     npm + homebrew packaging
├── services/
│   └── billing-worker/           Cloudflare Worker for Razorpay (deploy-ready)
├── scripts/
│   ├── bootstrap.ps1             one-shot Windows dev setup
│   ├── win-build.ps1             Windows installer build
│   ├── win-install.ps1           run produced installer
│   ├── win-run.ps1               launch built binary
│   └── generate-icons.py         icon set generator
├── ARCHITECTURE.md               component diagram + data flow
├── CHANGELOG.md                  release history
└── LICENSE                       GPL-3.0
```

## Auth

The app boots with `LocalAuthProvider` — localStorage + PBKDF2 (600k
iterations, SHA-256, per-OWASP-2023) credential storage. Sessions are
reactive across tabs via the `storage` event. Suitable for personal use
and offline-first dev.

To swap in real multi-device auth, change one line in
`app/src/features/auth/index.ts`:

```ts
export { SupabaseAuthProvider as AuthProvider } from './SupabaseAuthProvider';
```

…then set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in `.env`. See
`app/src/features/auth/PROVIDER_SELECTION.md` for the full comparison.

## Billing (UPI-first, India)

Billing is **off** by default — every signed-in user gets full access
under preview mode. To turn it on:

1. Sign up at [Razorpay](https://dashboard.razorpay.com/signup) (15-min KYC)
2. Create Pro (₹499/mo) and Ultra (₹1499/mo) plans
3. Deploy the Cloudflare Worker:
   ```bash
   cd services/billing-worker
   npm install
   npx wrangler kv:namespace create BILLING_KV
   npx wrangler secret put RAZORPAY_KEY_SECRET
   npx wrangler secret put RAZORPAY_KEY_ID
   npx wrangler secret put RAZORPAY_WEBHOOK_SECRET
   npx wrangler secret put JWT_SECRET
   npx wrangler deploy
   ```
4. Set in your app `.env`:
   ```
   VITE_BILLING_ENABLED=true
   VITE_BILLING_API_URL=https://<your-worker>.workers.dev
   ```
5. Paste the Razorpay plan IDs into `app/src/features/paywall/tiers.ts`.

Full walkthrough: `services/billing-worker/README.md` and
`app/src/features/paywall/RAZORPAY_SETUP.md`.

## LLM backend (SwitchAI)

Eversilver routes all chat / reasoning / coding workloads through a local
SwitchAI backend (`services/switchai-backend/`), an OpenAI-compatible
FastAPI service that wraps the [SwitchAI](https://github.com/yelboudouri/SwitchAI)
library. SwitchAI gives a unified interface to OpenAI, Anthropic, Mistral,
DeepSeek, Google, Ollama, xAI, Replicate, Voyage, and Deepgram — you bring
the keys, the backend routes per request.

One-shot setup:

```powershell
pnpm --filter eversilver-app win:switchai
```

This installs the Python deps, registers a Windows Startup shortcut for
auto-launch, starts the backend on `http://127.0.0.1:8088`, and wires the
active local user's `config.toml` with a `[[cloud_providers]]` entry +
`model_routes` for reasoning / agentic / coding workloads.

Provide one upstream API key in `services/switchai-backend/.env`:

```bash
OPENAI_API_KEY=sk-...
# or any of: ANTHROPIC_API_KEY, MISTRAL_API_KEY, DEEPSEEK_API_KEY,
#            GOOGLE_API_KEY, XAI_API_KEY, REPLICATE_API_KEY,
#            VOYAGE_API_KEY, DEEPGRAM_API_KEY
```

Restart the backend and Eversilver:

```powershell
pnpm --filter eversilver-app win:switchai:restart
```

Switch upstream provider/model:

```powershell
pnpm --filter eversilver-app win:switchai -- -Provider mistral -Model mistral-small-latest
```

Full integration walkthrough: `services/switchai-backend/INTEGRATION.md`.
Backend's own docs (endpoints, curl examples, tests):
`services/switchai-backend/README.md`.

## 3D mascot

Eversilver ships with a 2D SVG mascot ("Ghosty") in a moonlight palette
that matches the brand. To use a 3D character instead — e.g. a
VRoid-designed avatar — drop a `.vrm` or `.glb` into `app/public/`, set
`VITE_MASCOT_MODEL_URL=/yours.vrm`, and the renderer hot-swaps with full
face / viseme / lip-sync wiring. The three.js + three-vrm bundle is
lazy-loaded so the cost is zero until you actually use it.

See `app/src/features/human/Mascot/vrm/README.md` for the full
expression map and recommended model sources.

## Development

```bash
pnpm install                                # one time
pnpm dev                                     # web-only Vite (fast iteration)
pnpm --filter eversilver-app dev:app:win    # full desktop dev mode (Windows)
pnpm --filter eversilver-app test            # vitest unit tests
pnpm --filter eversilver-app compile         # TypeScript typecheck
cargo check --workspace                      # Rust typecheck
```

If `cargo` fails on Windows with `link.exe not found`, run
`scripts/bootstrap.ps1` to install the MSVC toolchain. If it fails with
"Application Control policy has blocked this file", turn off Smart App
Control in Windows Security → App & browser control.

For an in-depth tour see `ARCHITECTURE.md`. For release notes see
`CHANGELOG.md`.

## License

GPL-3.0. See `LICENSE`.
