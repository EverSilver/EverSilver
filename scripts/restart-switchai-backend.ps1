<#
.SYNOPSIS
  Restart the local SwitchAI backend (picks up .env changes).
#>
[CmdletBinding()] param()
$ErrorActionPreference = 'Continue'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$backendDir = Join-Path $repoRoot 'services\switchai-backend'

# Kill any process owning :8088
$conn = Get-NetTCPConnection -LocalPort 8088 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
  $owner = $conn.OwningProcess
  Write-Host "stopping PID $owner on :8088"
  Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
  Start-Sleep -Seconds 1
}

# Restart in background
Start-Process python `
  -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8088' `
  -WorkingDirectory $backendDir `
  -WindowStyle Hidden
Write-Host "restarting..."

for ($i = 0; $i -lt 20; $i++) {
  Start-Sleep -Milliseconds 500
  try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:8088/' -UseBasicParsing -TimeoutSec 1
    if ($r.name -eq 'switchai-backend') {
      Write-Host "OK -- providers: $($r.providers -join ', ')"
      exit 0
    }
  } catch {}
}
Write-Host "FAIL -- backend did not come up within 10s"
exit 1
