# Architecture

A tour through how Eversilver is wired together, from the moment you click
the icon to the moment it answers your question.

## Process model

```
                       ┌───────────────────────────────────┐
                       │           Eversilver.exe          │
                       │       (Tauri host process)        │
                       │                                   │
                       │   ┌─────────────┐    ┌────────┐   │
                       │   │ Rust core   │    │  CEF   │   │
                       │   │ (in-proc)   │←─→│ webview│   │
                       │   └──────┬──────┘    └────┬───┘   │
                       └──────────┼────────────────┼───────┘
                                  │                │
                                  │                │ JSON-RPC
                ┌─────────────────┴─┐              │ + Tauri commands
                │                   │              │
                ▼                   ▼              ▼
        SQLite memory tree    Markdown vault   React app (main)
        ~/.eversilver/db      ~/.eversilver/    ─────────────────
                                  obsidian/    Floating mascot (NSPanel/Win)
                                               Overlay window (transparent)
```

A single OS process hosts everything:

- **Rust core** (`src/eversilver/`) — agent loop, memory tree, RAG,
  integrations, token compression, model router. Linked in-process as a
  library; no out-of-band sidecar binary.
- **CEF runtime** (`app/src-tauri/vendor/tauri-cef/`) — a vendored fork
  of `tauri-runtime` that swaps wry for full Chromium. This is what lets
  Google Meet, OAuth popups, and getDisplayMedia all work natively.
- **React UI** (`app/src/`) — Vite + React 19 + Redux Toolkit. Mounts
  one of three trees depending on the URL/window label: the main app,
  the floating mascot, or the translucent overlay.

The Rust ↔ React boundary is a mix of Tauri's `invoke` commands and a
JSON-RPC channel namespaced under `eversilver.*` (renamed from the
upstream `openhuman.*`).

## App entry → AuthGate → Routes

```
main.tsx
  │
  ▼
 isMascotWindow?  ──► MascotWindowApp   (no auth — child window)
  │
 isOverlayWindow? ──► OverlayApp        (no auth — child window)
  │
  ▼
 <AuthGate>                              ← features/auth/AuthGate.tsx
   <AuthProvider>                        ← LocalAuthProvider (PBKDF2 + localStorage)
     <PaywallProvider>                   ← features/paywall/PaywallProvider.tsx
       isAuthenticated ? <App /> : <LoginScreen />
```

`AuthGate` is the single place auth + paywall context get mounted.
Satellite windows (mascot, overlay) skip the gate because they're child
views hosted by an already-authenticated parent process; gating them
would deadlock first paint.

## Auth layer

Two providers expose the same `useAuth()` surface:

| Provider | Storage | Use case |
|---|---|---|
| `LocalAuthProvider` | `localStorage` + PBKDF2-SHA256 (600k iters) | Personal/preview/offline |
| `SupabaseAuthProvider` | Supabase auth | Multi-device, cloud-synced |

Swap by changing one re-export in `app/src/features/auth/index.ts`.

### Local credential flow

```
signUp(email, pw, name)
  └──► hashPassword(pw)               PBKDF2-SHA256(600k, 16-byte salt)
  └──► users[email] = {…, passwordHash}    localStorage 'eversilver.auth.users.v1'
  └──► session = { userId }                localStorage 'eversilver.auth.session.v1'

signIn(email, pw)
  └──► users[email]
  └──► verifyPassword(pw, stored.passwordHash)   constant-time compare
  └──► session = { userId }
```

A `storage` event listener keeps state in sync across browser tabs.

## Paywall layer

```
PaywallProvider
  ├── currentTier        derived from user.tier (or PREVIEW_TIER if billing off)
  ├── hasFeature(f)      checks tier features in tiers.ts
  ├── isAtLeast(tier)    tierRank-based comparison
  └── checkout(tier)     ► createSubscription via /api/billing/subscribe
                         ► openRazorpayCheckout (UPI + cards + netbanking)
                         ► server webhook flips user.tier authoritatively
```

`BILLING_ENABLED` is the master kill-switch (`config.ts`). When false
every signed-in user is silently promoted to `PREVIEW_TIER` (= ultra)
and `<PaywallGate>` becomes a pass-through. Flip to true via
`VITE_BILLING_ENABLED=true` in `.env`.

### Server side (Cloudflare Worker)

```
POST /api/billing/subscribe       ─► Razorpay /subscriptions/create
                                     KV: subscriptionId → userId

POST /api/billing/webhook         ─► HMAC verify (X-Razorpay-Signature)
                                     idempotent (event_id stored 30d)
                                     subscription.activated → tier=pro/ultra
                                     subscription.cancelled → tier=free
                                     payment.failed         → log + nothing

GET  /api/billing/status          ─► authed; returns { tier, period_end }
POST /api/billing/cancel          ─► soft cancel (cancel_at_cycle_end)
GET  /health                      ─► public liveness
```

Everything signed with HS256 JWT (shared secret matches client). KV
namespace for state. D1 schema also provided for SQL preference.

## Mascot subsystem

Two interchangeable renderers behind one `MascotFace` state machine:

```
agent.state    ─► MascotFace ('idle' | 'speaking' | 'thinking' | …)
                       │
              ┌────────┴────────┐
              ▼                 ▼
      <YellowMascot/>     <VrmMascot/>   (when VITE_MASCOT_MODEL_URL set)
      (2D SVG Ghosty)     (3D .vrm/.glb)
              │                 │
              └─► palette       └─► ExpressionManager
                  ('moonlight'    └─► viseme blendshapes (aa/ee/ih/oh/ou)
                   matches logo)  └─► auto-blink
```

The three.js + three-vrm bundle is **lazy-loaded** behind a dynamic
import in `vrmLoader.ts` — zero bundle cost until a model URL is set.

## Memory tree

```
text/HTML/audio/screenshot
        │
        ▼
   TokenJuice       Markdown normalize, URL shorten, ASCII clamp
        │
        ▼
   chunker (≤3k tokens)
        │
        ▼
   embedder ─────► VSS index (SQLite vector)
        │
        ▼
   hierarchical summary
        │
        ▼
   ┌──────────────┐
   │   SQLite     │     primary store
   │ ~/.eversilver│
   └──────┬───────┘
          │
          └──► mirror to Markdown
               ~/.eversilver/obsidian/   (Obsidian-compatible)
```

Every twenty minutes the core walks each active integration and pulls
fresh data into this pipeline — the "auto-fetch" feature.

## Build pipeline (Windows)

```
scripts/bootstrap.ps1
   ├─► winget: Git, Node 24, Rust 1.95, MSVC + C++, Win SDK, CMake, Ninja, LLVM
   ├─► corepack enable + pnpm@10.10.0
   ├─► add to user PATH + LIBCLANG_PATH
   ├─► git submodule update --init --recursive
   └─► pnpm install

pnpm --filter eversilver-app win:build:release
   └─► pwsh scripts/win-build.ps1 -Profile release
       ├─► import vcvars64.bat env
       ├─► tsc + vite build  (frontend)
       └─► cargo tauri build --bundles msi nsis -- --bin Eversilver
            ├─► cargo build --release            ~10–25 min first time
            ├─► WiX MSI packaging
            └─► NSIS exe packaging
               ↓
          app/src-tauri/target/release/bundle/
              ├── msi/Eversilver_0.53.49_x64_en-US.msi   (machine-wide)
              └── nsis/Eversilver_0.53.49_x64-setup.exe   (per-user)

pnpm --filter eversilver-app win:install
   └─► scripts/win-install.ps1 -Type nsis   (default: per-user, no UAC)
```

## Windows-specific gotchas

| Symptom | Cause | Fix |
|---|---|---|
| `link.exe not found` | MSVC env not loaded | run `pwsh scripts/win-build.ps1` (sources vcvars64) |
| `Application Control policy has blocked this file` | Smart App Control (SAC) is on | Windows Security → App & browser control → Smart App Control → Off (one-way) |
| `LIBCLANG_PATH not found` | LLVM dir not on PATH | `setx LIBCLANG_PATH "C:\Program Files\LLVM\bin"` |
| MSI install fails 1625 | Software Restriction Policy on temp dir | Use the NSIS installer instead |
| Tauri build fails on `whisper-rs-sys` | cmake/ninja missing | `winget install Kitware.CMake Ninja-build.Ninja` |

## Repo conventions

- **Internal Rust crate name**: `eversilver` (workspace) / `eversilver_core`
  (lib). Renamed from upstream — no upstream identifiers anywhere outside
  the LICENSE file (verified by `git grep -i openhuman tinyhumans`).
- **JSON-RPC namespace**: `eversilver.*`.
- **Bundle identifier**: `local.eversilver.app`.
- **Storage keys**: `eversilver.<feature>.<key>.v<version>` — versioned so
  schema migrations don't trample old data.
- **Env var prefix**: `EVERSILVER_` for Rust core, `VITE_EVERSILVER_*` /
  `VITE_BILLING_*` for the React shell.
