<#
.SYNOPSIS
  One-shot install + autostart + Eversilver wiring for the LiteLLM-backed
  llm-backend.

.DESCRIPTION
  Idempotent. Does, in order:
    1. Verifies Python 3.11+
    2. `pip install -e services/llm-backend` (+ tomli-w + pytest)
    3. Stops any prior switchai-backend / llm-backend uvicorn on :8088
    4. Drops a Windows Startup shortcut so the backend launches at login
    5. Starts the backend in the current session
    6. Probes http://127.0.0.1:8088/ to confirm it is responsive
    7. (if Eversilver has been launched at least once)
       Runs `configure-eversilver-llm.py` to point the active user's
       config.toml at the new backend.

  Safe to re-run any time.

.PARAMETER NoAutostart
  Skip writing the Startup shortcut.

.PARAMETER NoConfigure
  Skip the Eversilver config.toml wiring.

.PARAMETER Model
  Friendly model name from services/llm-backend/config.yaml.
  Default: gemma3:1b-it-qat (always available; needs local Ollama).

.EXAMPLE
  pwsh -File scripts/install-llm-backend.ps1
  pwsh -File scripts/install-llm-backend.ps1 -Model gpt-oss:120b
#>
[CmdletBinding()]
param(
  [switch]$NoAutostart,
  [switch]$NoConfigure,
  [string]$Model = 'gemma3:1b-it-qat'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$backendDir = Join-Path $repoRoot 'services\llm-backend'

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

# -- 2. Install backend ----------------------------------------------------
Write-Step '2. pip install llm-backend + helpers'
& python -m pip install --quiet --user -e "$backendDir" tomli-w pytest
if ($LASTEXITCODE -ne 0) { Write-Error 'pip install failed'; exit 1 }
Write-Ok 'llm-backend installed editable; tomli-w + pytest available'

# -- 3. Stop any prior backend on :8088 -----------------------------------
Write-Step '3. Stop prior uvicorn on :8088'
$conn = Get-NetTCPConnection -LocalPort 8088 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
  foreach ($c in $conn) {
    try {
      Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop
      Write-Ok "killed PID $($c.OwningProcess) holding :8088"
    } catch {
      Write-WarnX "could not kill PID $($c.OwningProcess): $_"
    }
  }
  Start-Sleep -Milliseconds 500
} else {
  Write-Ok 'nothing holding :8088'
}

# -- 4. Windows Startup shortcut -----------------------------------------
if (-not $NoAutostart) {
  Write-Step '4. Windows Startup autostart'
  $startup = [Environment]::GetFolderPath('Startup')
  # Remove stale switchai shortcut if present.
  $stale = Join-Path $startup 'Eversilver SwitchAI Backend.lnk'
  if (Test-Path $stale) { Remove-Item $stale -Force; Write-Ok 'removed stale SwitchAI autostart' }

  $lnkPath = Join-Path $startup 'Eversilver LLM Backend.lnk'
  $launcher = Join-Path $repoRoot 'scripts\start-llm-backend.cmd'
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
  $shortcut.Description = 'Eversilver LLM Backend (OpenAI-compatible, LiteLLM)'
  $shortcut.WindowStyle = 7  # minimized
  $shortcut.Save()
  Write-Ok "autostart shortcut: $lnkPath"
} else {
  Write-WarnX '4. autostart SKIPPED (-NoAutostart)'
}

# -- 5. Start backend in this session -------------------------------------
Write-Step '5. Start backend'
Start-Process python `
  -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8088' `
  -WorkingDirectory $backendDir `
  -WindowStyle Hidden
$up = $false
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Milliseconds 500
  try {
    $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8088/' -UseBasicParsing -TimeoutSec 1
    if ($resp.name -eq 'eversilver-llm-backend') {
      Write-Ok "backend up (providers: $($resp.providers -join ', '))"
      $up = $true
      break
    }
  } catch { }
}
if (-not $up) {
  Write-WarnX 'backend did not come up within 15s -- check `python -m uvicorn app.main:app` manually'
}

# -- 6. Configure Eversilver ----------------------------------------------
if (-not $NoConfigure) {
  Write-Step '6. Wiring Eversilver config'
  $active = Join-Path $env:USERPROFILE '.eversilver\active_user.toml'
  if (-not (Test-Path $active)) {
    Write-WarnX 'No active_user.toml yet. Launch Eversilver, click "Continue without an account", then re-run this script (or run scripts\configure-eversilver-llm.py directly).'
  } else {
    & python (Join-Path $repoRoot 'scripts\configure-eversilver-llm.py') --model $Model
    if ($LASTEXITCODE -ne 0) {
      Write-WarnX "config wiring exited $LASTEXITCODE -- see above"
    } else {
      Write-Ok 'config.toml wired'
    }
  }
} else {
  Write-WarnX '6. config wiring SKIPPED (-NoConfigure)'
}

Write-Host "`nDone." -ForegroundColor Magenta
Write-Host "  backend  : http://127.0.0.1:8088"
Write-Host "  health   : http://127.0.0.1:8088/health"
Write-Host "  models   : http://127.0.0.1:8088/v1/models"
Write-Host "  config   : services\llm-backend\.env (provider API keys here)"
Write-Host ""
Write-Host "Next:"
Write-Host "  1. (Optional) Edit $backendDir\.env -- set OPENAI_API_KEY / OLLAMA_API_KEY / etc."
Write-Host "  2. Restart the backend OR run: pnpm --filter eversilver-app win:llm:restart"
Write-Host "  3. Launch Eversilver -- chat workloads now route through llm-backend"
