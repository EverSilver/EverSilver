# Eversilver

Personal AI super intelligence — private, simple, powerful.

## What is this?

Eversilver is a desktop AI assistant that runs locally on your machine. It pairs a Rust core (business logic, RPC server, integrations) with a Tauri + React shell that hosts an embedded Chromium webview. Memory, agent state, and credentials stay on disk; nothing is shipped to a third-party service unless you explicitly configure it. Everything is meant to be self-hosted, single-user, and fully under your control.

## Development

Prerequisites:

- Node.js 24+
- pnpm 10.10.0
- Rust 1.93.0 (see `rust-toolchain.toml`)
- CMake
- Ninja
- MSVC build tools (Windows) / Xcode CLT (macOS) / build-essential (Linux)

Install and run:

```bash
pnpm install
pnpm dev
```

## License

GPL v3 — see LICENSE
