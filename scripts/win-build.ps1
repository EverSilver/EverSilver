<#
.SYNOPSIS
  Eversilver Windows build wrapper.

.DESCRIPTION
  Loads the MSVC toolchain (vcvars64), adds Cargo / LLVM / CMake / Ninja
  to PATH, and runs `cargo tauri build` with the requested bundle types.

  Designed to be invoked from package.json scripts so contributors don't
  have to manually source vcvars64 before every build.

.PARAMETER Bundles
  Tauri bundle types to produce. Default: msi nsis.
  Valid values: msi, nsis, app, dmg, deb, appimage.

.PARAMETER Profile
  release (default) or debug.

.EXAMPLE
  pwsh -File scripts/win-build.ps1
  pwsh -File scripts/win-build.ps1 -Bundles msi
  pwsh -File scripts/win-build.ps1 -Profile debug
#>
[CmdletBinding()]
param(
  [string[]]$Bundles = @('msi', 'nsis'),
  [ValidateSet('release', 'debug')]
  [string]$Profile = 'release'
)

$ErrorActionPreference = 'Stop'

function Find-VsBuildTools {
  $candidates = @(
    'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat',
    'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat',
    'C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat',
    'C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat'
  )
  foreach ($p in $candidates) { if (Test-Path $p) { return $p } }
  return $null
}

function Import-VsEnv([string]$vcvars) {
  Write-Host "  -> sourcing $vcvars" -ForegroundColor DarkGray
  & cmd /c "`"$vcvars`" && set" | ForEach-Object {
    if ($_ -match '^(.*?)=(.*)$') { Set-Item "Env:$($matches[1])" $matches[2] }
  }
}

function Add-PathIfMissing([string]$dir) {
  if (-not (Test-Path $dir)) { return }
  if (($env:Path -split ';') -notcontains $dir) {
    $env:Path = "$dir;$env:Path"
  }
}

function Find-Ninja {
  $hits = @(
    "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Ninja-build.Ninja_Microsoft.Winget.Source_8wekyb3d8bbwe",
    'C:\ProgramData\chocolatey\bin'
  )
  foreach ($d in $hits) { if (Test-Path (Join-Path $d 'ninja.exe')) { return $d } }
  return $null
}

# --- Toolchain bootstrap ---
Write-Host "Eversilver Windows build" -ForegroundColor Cyan
Write-Host "  Profile : $Profile"
Write-Host "  Bundles : $($Bundles -join ', ')"

$vcvars = Find-VsBuildTools
if (-not $vcvars) {
  Write-Error "MSVC vcvars64.bat not found. Install Visual Studio Build Tools with the C++ workload."
  exit 1
}
Import-VsEnv $vcvars

Add-PathIfMissing "$env:USERPROFILE\.cargo\bin"
Add-PathIfMissing 'C:\Program Files\LLVM\bin'
Add-PathIfMissing 'C:\Program Files\CMake\bin'
$ninja = Find-Ninja
if ($ninja) { Add-PathIfMissing $ninja }

if (-not $env:LIBCLANG_PATH) { $env:LIBCLANG_PATH = 'C:\Program Files\LLVM\bin' }

# --- Sanity checks ---
$missing = @()
foreach ($tool in 'cl', 'link', 'cargo', 'cmake', 'ninja', 'clang') {
  if (-not (Get-Command "$tool.exe" -ErrorAction SilentlyContinue)) { $missing += $tool }
}
if ($missing) {
  Write-Error "Missing tools on PATH: $($missing -join ', '). Run scripts\bootstrap.ps1 first."
  exit 2
}

# --- Build ---
Push-Location (Join-Path $PSScriptRoot '..\app')
try {
  $bundleArg = $Bundles -join ' '
  $profileFlag = if ($Profile -eq 'debug') { '--debug' } else { '' }
  $cmd = "cargo tauri build $profileFlag --bundles $bundleArg -- --bin Eversilver"
  Write-Host "  -> $cmd" -ForegroundColor DarkGray
  & cargo tauri build $(if ($profileFlag) { $profileFlag }) --bundles @Bundles -- --bin Eversilver
  if ($LASTEXITCODE -ne 0) { throw "cargo tauri build exited with code $LASTEXITCODE" }
} finally {
  Pop-Location
}

# --- Report artifacts ---
$profileDir = if ($Profile -eq 'debug') { 'debug' } else { 'release' }
$bundleDir = Join-Path $PSScriptRoot "..\app\src-tauri\target\$profileDir\bundle"
if (Test-Path $bundleDir) {
  Write-Host "`nArtifacts:" -ForegroundColor Green
  Get-ChildItem -Path $bundleDir -Recurse -Include '*.msi', '*.exe' |
    Sort-Object Length |
    ForEach-Object {
      $size = [math]::Round($_.Length / 1MB, 1)
      Write-Host ("  {0,8} MB  {1}" -f $size, $_.FullName)
    }
} else {
  Write-Warning "Bundle directory not found: $bundleDir"
}
