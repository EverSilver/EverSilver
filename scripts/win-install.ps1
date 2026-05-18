<#
.SYNOPSIS
  Install the Eversilver Windows build.

.DESCRIPTION
  Picks up the most recently built NSIS installer (preferred -- no admin
  required) or MSI from `app/src-tauri/target/release/bundle/`, runs it
  silently, and reports where it landed.

.PARAMETER Type
  msi or nsis (default: nsis, since it doesn't need admin / SAC bypass).

.EXAMPLE
  pwsh -File scripts/win-install.ps1
  pwsh -File scripts/win-install.ps1 -Type msi
#>
[CmdletBinding()]
param(
  [ValidateSet('msi', 'nsis')]
  [string]$Type = 'nsis'
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------
# Eversilver's local core binds 127.0.0.1:7788 by default. If a sibling fork
# (OpenHuman, an old build, etc.) is still installed/running and holds that
# port, the new install will surface "Can't Reach the Runtime" on first
# launch. Detect and offer to clean up before we install.
function Stop-ConflictingProcesses {
  $names = @('OpenHuman', 'openhuman', 'openhuman-core', 'eversilver-core')
  foreach ($n in $names) {
    $procs = Get-Process -Name $n -ErrorAction SilentlyContinue
    if ($procs) {
      Write-Host "  -> stopping $($procs.Count) $n process(es)" -ForegroundColor DarkYellow
      $procs | Stop-Process -Force -ErrorAction SilentlyContinue
    }
  }
}
function Remove-OpenHumanInstalls {
  # Per-user NSIS install
  $perUser = "$env:LOCALAPPDATA\OpenHuman"
  if (Test-Path "$perUser\uninstall.exe") {
    Write-Host "  -> uninstalling per-user OpenHuman" -ForegroundColor DarkYellow
    Start-Process -FilePath "$perUser\uninstall.exe" -ArgumentList '/S' -Wait
  }
  if (Test-Path $perUser) { Remove-Item $perUser -Recurse -Force -ErrorAction SilentlyContinue }
  # Machine-wide MSI
  $key = Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall' -ErrorAction SilentlyContinue |
    ForEach-Object { Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue } |
    Where-Object { $_.DisplayName -match 'OpenHuman' } | Select-Object -First 1
  if ($key -and $key.UninstallString) {
    Write-Host "  -> uninstalling machine-wide OpenHuman" -ForegroundColor DarkYellow
    cmd /c $key.UninstallString /S | Out-Null
  }
}

$port = Get-NetTCPConnection -LocalPort 7788 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($port) {
  $pidOnPort = $port.OwningProcess
  $procOnPort = Get-Process -Id $pidOnPort -ErrorAction SilentlyContinue
  if ($procOnPort -and $procOnPort.ProcessName -notmatch 'Eversilver') {
    Write-Warning "Port 7788 is held by '$($procOnPort.ProcessName)' (PID $pidOnPort) -- this will collide with Eversilver's local core."
    Stop-ConflictingProcesses
    Remove-OpenHumanInstalls
    Start-Sleep -Seconds 2
  }
}

$bundleDir = Join-Path $PSScriptRoot '..\app\src-tauri\target\release\bundle'
if (-not (Test-Path $bundleDir)) {
  Write-Error "No release bundle found. Run 'pnpm --filter eversilver-app win:build:release' first."
  exit 1
}

$pattern = if ($Type -eq 'msi') { '*.msi' } else { '*-setup.exe' }
$installer = Get-ChildItem -Path $bundleDir -Filter $pattern -Recurse |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if (-not $installer) {
  Write-Error "No $Type installer found in $bundleDir"
  exit 2
}

Write-Host "Installing: $($installer.FullName)" -ForegroundColor Cyan

if ($Type -eq 'msi') {
  Write-Host "  (machine-wide install -- UAC prompt may appear)"
  $proc = Start-Process msiexec.exe -ArgumentList "/i `"$($installer.FullName)`" /qn /norestart" -Verb RunAs -Wait -PassThru
  if ($proc.ExitCode -ne 0) {
    Write-Error "MSI install failed with exit code $($proc.ExitCode)"
    exit $proc.ExitCode
  }
} else {
  # NSIS silent install (per-user, no admin)
  $proc = Start-Process -FilePath $installer.FullName -ArgumentList '/S' -Wait -PassThru
  if ($proc.ExitCode -ne 0) {
    Write-Error "NSIS install failed with exit code $($proc.ExitCode)"
    exit $proc.ExitCode
  }
}

# Find where it landed and offer to launch.
$candidates = @(
  "$env:LOCALAPPDATA\Programs\Eversilver\Eversilver.exe",
  "$env:LOCALAPPDATA\Eversilver\Eversilver.exe",
  "$env:LOCALAPPDATA\eversilver\Eversilver.exe",
  "$env:ProgramFiles\Eversilver\Eversilver.exe"
)
$launchPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

Write-Host "`nEversilver installed." -ForegroundColor Green
if ($launchPath) {
  Write-Host "  Executable: $launchPath"
  Write-Host "  Launching..." -ForegroundColor DarkGray
  Start-Process $launchPath
} else {
  Write-Warning "Could not locate the installed executable automatically -- try the Start Menu."
}
