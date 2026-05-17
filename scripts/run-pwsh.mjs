#!/usr/bin/env node
/**
 * Run a PowerShell script with whichever PowerShell is available.
 *
 * Order of preference:
 *   1. `pwsh` (PowerShell 7+, cross-platform; bootstrap.ps1 installs it)
 *   2. `powershell.exe` (Windows PowerShell 5.1; ships with every Windows)
 *
 * Usage:
 *   node scripts/run-pwsh.mjs path/to/script.ps1 [args...]
 *
 * Exits with the same exit code as the underlying PowerShell process.
 * Streams stdout/stderr through directly, no buffering.
 */
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const argv = process.argv.slice(2);
if (argv.length === 0) {
  console.error('run-pwsh: missing script path');
  process.exit(2);
}

const [scriptArg, ...scriptArgs] = argv;
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const scriptPath = path.isAbsolute(scriptArg) ? scriptArg : path.resolve(scriptDir, '..', scriptArg);

if (!existsSync(scriptPath)) {
  console.error(`run-pwsh: script not found: ${scriptPath}`);
  process.exit(2);
}

function tryRun(exe) {
  // -NoProfile so the user's profile doesn't slow startup or mutate behavior.
  // -ExecutionPolicy Bypass so unsigned scripts run without the security gate
  // tripping on per-machine policy.
  const args = ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', scriptPath, ...scriptArgs];
  const result = spawnSync(exe, args, { stdio: 'inherit', windowsHide: false });
  return result;
}

// Try pwsh first; fall back to powershell.exe.
let result = tryRun('pwsh');
if (result.error && result.error.code === 'ENOENT') {
  result = tryRun('powershell.exe');
}
if (result.error && result.error.code === 'ENOENT') {
  console.error('run-pwsh: neither pwsh nor powershell.exe found on PATH.');
  process.exit(127);
}
if (result.error) {
  console.error('run-pwsh:', result.error.message);
  process.exit(1);
}
process.exit(result.status ?? 0);
