# Changelog

All notable changes to Eversilver are documented in this file. Format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Auth layer**
  - `LocalAuthProvider` with PBKDF2-SHA256 (600k iterations) password
    hashing, versioned localStorage schema, cross-tab session sync, and
    a constant-time password comparator.
  - `SupabaseAuthProvider` as a drop-in production replacement (same
    `useAuth()` surface, backed by Supabase auth).
  - `AuthGate` component that wraps the app, mounts both auth + paywall
    providers, and shows the login screen until the user signs in.
  - Login screen UI with sign in / sign up toggle, error display, and a
    moonlight-themed bootstrap spinner.
- **Paywall layer**
  - Tier system (`free` / `pro` / `ultra`) with INR pricing and
    feature-gate registry.
  - `BILLING_ENABLED` master switch — when off, every signed-in user is
    silently promoted to `PREVIEW_TIER` so the UI is fully usable
    without a backend.
  - Razorpay UPI checkout client (lazy-loaded SDK, UPI-first by default,
    supports cards / netbanking / wallets).
  - `<PaywallGate feature="…">` component + `useEntitlement(feature)`
    hook for inline gating.
  - Pricing screen with INR formatting (₹ + lakh grouping).
- **Billing backend** (`services/billing-worker/`)
  - Cloudflare Worker (Hono v4) with `/subscribe`, `/webhook`,
    `/status`, `/cancel`, `/health` endpoints.
  - HMAC-SHA256 webhook signature verification via WebCrypto with
    constant-time comparison.
  - HS256 JWT auth middleware.
  - KV-based idempotent webhook store (30-day TTL).
  - Soft-cancel via `cancel_at_cycle_end` — tier flips at period end,
    not immediately.
  - D1 schema as a SQL alternative to KV.
  - Vitest test suite covering happy path, signature mismatch, missing
    auth, invalid tier.
- **3D mascot**
  - `VrmMascot` + `vrmLoader.ts` — drop a `.vrm` or `.glb` model into
    `app/public/`, set `VITE_MASCOT_MODEL_URL`, get a full 3D character
    with face + viseme + auto-blink + lip-sync.
  - State machine maps `MascotFace` → VRM expressions.
  - Three.js + three-vrm bundle is **lazy-loaded** — zero bundle cost
    unless used.
- **Brand**
  - Cosmic black/white fractal logo wired through all 16 platform icon
    variants (Windows ICO multi-res, macOS ICNS, Linux PNGs, Windows
    Store tiles).
  - Mascot palette switched from `yellow` to a new `moonlight` palette
    that matches the brand.
- **Windows tooling**
  - `scripts/bootstrap.ps1` — one-shot idempotent installer for Git,
    Node 24, Rust 1.95, MSVC + C++ workload, Windows SDK, CMake, Ninja,
    LLVM/Clang; configures PATH and LIBCLANG_PATH.
  - `scripts/win-build.ps1` — sources vcvars64.bat and runs
    `cargo tauri build`.
  - `scripts/win-install.ps1` — picks the latest NSIS/MSI artifact and
    installs it (NSIS by default, no UAC).
  - `scripts/win-run.ps1` — launches the built binary directly.
  - `win:build`, `win:build:release`, `win:build:debug`, `win:bundle:msi`,
    `win:bundle:nsis`, `win:install`, `win:run` scripts in
    `app/package.json`.
- **Tests**
  - 62+ vitest cases across `LocalAuthProvider`, `SupabaseAuthProvider`,
    `PaywallProvider`, `tiers`, and `crypto`.
  - Test coverage for: bootstrap state, sign up/in/out, password
    verification, session persistence, tier upgrade, billing-disabled
    auto-grant, razorpay checkout fallbacks, INR formatting.
- **Docs**
  - `README.md` — quick start, project layout, auth/billing/3D mascot
    walkthroughs.
  - `ARCHITECTURE.md` — process model, auth flow, paywall flow, memory
    tree, build pipeline, Windows gotchas.
  - `CHANGELOG.md` — this file.
  - `services/billing-worker/README.md` — deploy guide.
  - `app/src/features/paywall/RAZORPAY_SETUP.md` — Razorpay account +
    plan + webhook setup.
  - `app/src/features/auth/PROVIDER_SELECTION.md` — Local vs Supabase.
  - `app/src/features/human/Mascot/vrm/README.md` — 3D mascot guide.

### Changed

- Rebranded every user-facing string from `OpenHuman` → `Eversilver` and
  every internal identifier where doing so doesn't break the build
  (Rust crates, npm packages, JSON-RPC methods, env vars, file paths,
  Tauri bundle id `local.eversilver.app`).
- `whisper-rs-sys` `[patch.crates-io]` entry removed; now resolves
  directly from crates.io.
- Submodule URLs repointed to `EverSilver/tauri-cef` and
  `EverSilver/tauri-plugin-notification` forks; `tauri-cef` pinned to
  the `feat/openhuman-audio-handler` branch (it has the `audio` module
  the meet capture code uses).

### Removed

- All upstream-specific files: `.claude/`, `.agents/`, `.codex/`,
  `design-previews/`, `gitbooks/`, `CODE_OF_CONDUCT.md`,
  `CONTRIBUTING.md`, `CONTRIBUTING-BEGINNERS.md`, `SECURITY.md`,
  `AGENTS.md`, `CODEX_WORKPAD.md`, `README.zh-CN.md`.
- GitHub Actions workflows moved to `.github/workflows-disabled/` — they
  depended on upstream secrets and external CI. Re-enable selectively
  once secrets are wired.
- Husky pre-push hooks (renamed to `.husky-disabled/`) — they enforced
  upstream quality gates not appropriate for a personal fork.

### Security

- Local credentials no longer stored in plaintext. PBKDF2-SHA256 with
  600k iterations and a per-account 16-byte salt; constant-time hash
  comparison via bitwise OR difference.
- Razorpay webhook handler verifies HMAC signatures with constant-time
  comparison; idempotent event store prevents replay.
- LICENSE preserved verbatim (GPL-3.0) as required by upstream.
