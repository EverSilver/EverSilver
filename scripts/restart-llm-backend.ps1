<#
.SYNOPSIS
  Restart the local LLM backend (picks up .env / config.yaml changes).
#>
[CmdletBinding()] param()
$ErrorActionPreference = 'Continue'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$backendDir = Join-Path $repoRoot 'services\llm-backend'

# Kill anyone owning :8088 (covers switchai-backend leftovers too).
$conn = Get-NetTCPConnection -LocalPort 8088 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
  foreach ($c in $conn) {
    Write-Host "stopping PID $($c.OwningProcess) on :8088"
    Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Seconds 1
}

Start-Process python `
  -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8088' `
  -WorkingDirectory $backendDir `
  -WindowStyle Hidden
Write-Host "restarting llm-backend..."

for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Milliseconds 500
  try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8088/' -UseBasicParsing -TimeoutSec 1
    if ($r.name -eq 'eversilver-llm-backend') {
      Write-Host "OK -- providers: $($r.providers -join ', ')"
      exit 0
    }
  } catch {}
}
Write-Host "FAIL -- backend did not come up within 15s"
exit 1
