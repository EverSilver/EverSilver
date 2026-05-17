<#
.SYNOPSIS
  Launch the locally-built Eversilver binary (debug or release).

.DESCRIPTION
  Used during development to skip the installer round-trip: builds in dev
  mode if requested, then launches `app/src-tauri/target/<profile>/Eversilver.exe`.

.PARAMETER Profile
  release (default) or debug.

.PARAMETER Build
  Build before launching.

.EXAMPLE
  pwsh -File scripts/win-run.ps1                     # launch release build
  pwsh -File scripts/win-run.ps1 -Profile debug      # launch debug build
  pwsh -File scripts/win-run.ps1 -Build              # rebuild release first
#>
[CmdletBinding()]
param(
  [ValidateSet('release', 'debug')]
  [string]$Profile = 'release',
  [switch]$Build
)

$ErrorActionPreference = 'Stop'

if ($Build) {
  & (Join-Path $PSScriptRoot 'win-build.ps1') -Profile $Profile -Bundles msi
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$exe = Join-Path $PSScriptRoot "..\app\src-tauri\target\$Profile\Eversilver.exe"
if (-not (Test-Path $exe)) {
  Write-Error "Binary not found: $exe`nRun with -Build to build it first."
  exit 1
}

Write-Host "Launching $exe" -ForegroundColor Cyan
& $exe
