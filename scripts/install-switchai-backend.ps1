<#
.SYNOPSIS
  One-shot install + autostart + Eversilver wiring for the SwitchAI backend.

.DESCRIPTION
  Idempotent. Does, in order:
    1. Verifies Python 3.11+
    2. `pip install -e services/switchai-backend[dev]`
    3. Drops a Windows Startup shortcut so the backend launches at login
    4. Starts the backend in the current session if it is not already up
    5. Probes http://127.0.0.1:8088/ to confirm it is responsive
    6. (if Eversilver has been launched at least once)
       Runs `configure-eversilver-switchai.py` to register the local
       SwitchAI provider in the active user's config.toml.

  Safe to re-run any time.

.PARAMETER NoAutostart
  Skip writing the Startup shortcut.

.PARAMETER NoConfigure
  Skip the Eversilver config.toml wiring (use --user-id directly later).

.PARAMETER Provider
  Upstream provider SwitchAI should route to. Default: openai.

.PARAMETER Model
  Model id within that provider. Default: gpt-4o-mini.

.EXAMPLE
  pwsh -File scripts/install-switchai-backend.ps1
  pwsh -File scripts/install-switchai-backend.ps1 -Provider mistral -Model mistral-small-latest
#>
[CmdletBinding()]
param(
  [switch]$NoAutostart,
  [switch]$NoConfigure,
  [string]$Provider = 'openai',
  [string]$Model = 'gpt-4o-mini'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$backendDir = Join-Path $repoRoot 'services\switchai-backend'

function Write-Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Write-WarnX($m) { Write-Host "  !!  $m" -ForegroundColor Yellow }

# -- 1. Python check --------------------------------------------------------
Write-Step '1. Python 3.11+ check'
$pyVersion = & python --version 2>&1
if ($LASTEXITCODE -ne 0 -or $pyVersion -notmatch '^Python (\d+)\.(\d+)') {
  Write-Error 'python is not on PATH. Install Python 3.11+ first.'
  exit 1
}
$major = [int]$matches[1]; $minor = [int]$matches[2]
if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
  Write-Error "Python 3.11+ required (found $pyVersion)."
  exit 1
}
Write-Ok $pyVersion

# -- 2. Install backend + tomli-w (used by configure script) ---------------
Write-Step '2. pip install switchai-backend + helpers'
& python -m pip install --quiet --user -e "$backendDir[dev]" tomli-w
if ($LASTEXITCODE -ne 0) { Write-Error 'pip install failed'; exit 1 }
Write-Ok 'switchai-backend installed editable; tomli-w available'

# -- 3. Windows Startup shortcut -------------------------------------------
if (-not $NoAutostart) {
  Write-Step '3. Windows Startup autostart'
  $startup = [Environment]::GetFolderPath('Startup')
  $lnkPath = Join-Path $startup 'Eversilver SwitchAI Backend.lnk'
  $launcher = Join-Path $repoRoot 'scripts\start-switchai-backend.cmd'
  if (-not (Test-Path $launcher)) {
    @"
@echo off
cd /d "$backendDir"
start "" /B python -m uvicorn app.main:app --host 127.0.0.1 --port 8088
"@ | Set-Content -Path $launcher -Encoding ASCII
    Write-Ok "wrote $launcher"
  }
  $shell = New-Object -ComObject WScript.Shell
  $shortcut = $shell.CreateShortcut($lnkPath)
  $shortcut.TargetPath = $launcher
  $shortcut.WorkingDirectory = $backendDir
  $shortcut.Description = 'Eversilver SwitchAI Backend (OpenAI-compatible LLM router)'
  $shortcut.WindowStyle = 7  # minimized
  $shortcut.Save()
  Write-Ok "autostart shortcut: $lnkPath"
} else {
  Write-WarnX '3. autostart SKIPPED (-NoAutostart)'
}

# -- 4. Start backend in this session if not already up --------------------
Write-Step '4. Backend liveness'
$alreadyUp = $false
try {
  $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8088/' -UseBasicParsing -TimeoutSec 2
  if ($resp.name -eq 'switchai-backend') {
    $alreadyUp = $true
    Write-Ok "already running on :8088 (providers: $($resp.providers -join ', '))"
  }
} catch {
  # not up -- start it
}
if (-not $alreadyUp) {
  Write-Host '  starting backend...' -ForegroundColor DarkGray
  Start-Process python `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8088' `
    -WorkingDirectory $backendDir `
    -WindowStyle Hidden
  for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    try {
      $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8088/' -UseBasicParsing -TimeoutSec 1
      if ($resp.name -eq 'switchai-backend') {
        Write-Ok "backend up (providers: $($resp.providers -join ', '))"
        $alreadyUp = $true
        break
      }
    } catch { }
  }
  if (-not $alreadyUp) {
    Write-WarnX 'backend did not come up within 10s -- check `python -m uvicorn app.main:app` manually'
  }
}

# -- 5. Configure Eversilver to use it ------------------------------------
if (-not $NoConfigure) {
  Write-Step '5. Wiring Eversilver config'
  $active = Join-Path $env:USERPROFILE '.eversilver\active_user.toml'
  if (-not (Test-Path $active)) {
    Write-WarnX 'No active_user.toml yet. Launch Eversilver, click "Continue without an account", then re-run this script (or run scripts\configure-eversilver-switchai.py directly).'
  } else {
    & python (Join-Path $repoRoot 'scripts\configure-eversilver-switchai.py') --provider $Provider --model $Model
    if ($LASTEXITCODE -ne 0) {
      Write-WarnX "config wiring exited $LASTEXITCODE -- see above"
    } else {
      Write-Ok 'config.toml wired'
    }
  }
} else {
  Write-WarnX '5. config wiring SKIPPED (-NoConfigure)'
}

Write-Host "`nDone." -ForegroundColor Magenta
Write-Host "  backend  : http://127.0.0.1:8088"
Write-Host "  health   : http://127.0.0.1:8088/health"
Write-Host "  models   : http://127.0.0.1:8088/v1/models"
Write-Host "  config   : services\switchai-backend\.env (add provider API keys here)"
Write-Host ""
Write-Host "Next:"
Write-Host "  1. Edit $backendDir\.env -- set OPENAI_API_KEY (or whichever provider) so the backend can call upstream"
Write-Host "  2. Restart the backend OR run: pnpm --filter eversilver-app win:switchai:restart"
Write-Host "  3. Launch Eversilver -- chat workloads now route through SwitchAI"
