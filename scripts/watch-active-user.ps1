# Monitor active_user.toml; whenever it points at a new user_id, run
# configure-eversilver-llm.py against that user dir so a freshly-created
# local user inherits the OpenFang chat config.
#
# Eversilver writes a new user_id on every "Continue without an account"
# click in the welcome screen. Without this watcher, each new user dir
# starts with no inference_url / api_key and chat fails.
#
# Requires: $env:OPENFANG_API_KEY in the parent shell.

$ErrorActionPreference = 'Stop'
$activePath = Join-Path $env:USERPROFILE '.eversilver\active_user.toml'
$script     = Join-Path $PSScriptRoot 'configure-eversilver-llm.py'
$lastUser   = ''

Write-Host 'watch-active-user.ps1 started (Ctrl+C to stop)'

while ($true) {
  if (Test-Path -LiteralPath $activePath) {
    $line = Get-Content -LiteralPath $activePath -ErrorAction SilentlyContinue | Select-String -Pattern 'user_id' | Select-Object -First 1
    if ($line) {
      $current = $line.Line -replace '.*"([^"]+)".*', '$1'
      if ($current -and $current -ne $lastUser) {
        $ts = Get-Date -Format 'HH:mm:ss'
        Write-Host ('[' + $ts + '] active user -> ' + $current)
        & python $script --user-id $current --model Athena 2>&1 |
          Select-String -Pattern 'status|inference_url|auth token' |
          ForEach-Object { Write-Host ('  ' + $_.Line) }
        $lastUser = $current
      }
    }
  }
  Start-Sleep -Seconds 2
}
