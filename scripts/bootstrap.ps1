<#
.SYNOPSIS
  One-shot Eversilver dev environment bootstrap for Windows.

.DESCRIPTION
  Idempotent: safe to re-run any time. Installs every dependency required
  to build the Eversilver desktop app from source on Windows 10/11.

  What it does:
    1. Verifies PowerShell version (>= 5.1)
    2. Installs / checks: Git, Node.js 24, pnpm 10, Rust 1.95, MSVC Build
       Tools + C++ workload, Windows SDK, CMake, Ninja, LLVM/Clang
    3. Adds the right directories to user PATH
    4. Persists LIBCLANG_PATH
    5. Initializes git submodules
    6. Runs `pnpm install`
    7. Reports any remaining manual steps (Smart App Control, etc.)

.PARAMETER SkipInstalls
  Skip winget installs; only verify and configure environment.

.EXAMPLE
  pwsh -File scripts/bootstrap.ps1
  pwsh -File scripts/bootstrap.ps1 -SkipInstalls
#>
[CmdletBinding()]
param([switch]$SkipInstalls)

$ErrorActionPreference = 'Stop'
$start = Get-Date

function Write-Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn2([string]$msg) { Write-Host "  !!  $msg" -ForegroundColor Yellow }
function Write-Skip([string]$msg) { Write-Host "  ..  $msg" -ForegroundColor DarkGray }

function Test-WingetPackage([string]$id) {
  try {
    $out = winget list --id $id --exact 2>&1 | Out-String
    return ($out -notmatch 'No installed package')
  } catch { return $false }
}

function Install-Winget([string]$id, [string]$friendly, [string]$override = $null) {
  if (Test-WingetPackage $id) { Write-Skip "$friendly already installed"; return }
  if ($SkipInstalls) { Write-Warn2 "$friendly missing (skipped)"; return }
  Write-Host "  -> installing $friendly via winget ($id)" -ForegroundColor DarkGray
  $args = @('install', '--id', $id, '--silent', '--accept-package-agreements', '--accept-source-agreements')
  if ($override) { $args += @('--override', $override) }
  $proc = Start-Process winget -ArgumentList $args -Wait -PassThru -NoNewWindow
  if ($proc.ExitCode -ne 0) {
    Write-Warn2 "$friendly install exited $($proc.ExitCode) -- may need manual install"
  } else {
    Write-Ok "$friendly installed"
  }
}

function Add-UserPath([string]$dir) {
  if (-not (Test-Path $dir)) { return $false }
  $user = [Environment]::GetEnvironmentVariable('Path', 'User')
  $entries = @() + ($user -split ';' | Where-Object { $_ })
  if ($entries -contains $dir) { return $false }
  $combined = "$user;$dir"
  $combined = $combined.TrimStart(';')
  [Environment]::SetEnvironmentVariable('Path', $combined, 'User')
  $env:Path = "$dir;$env:Path"
  Write-Ok "added $dir to user PATH"
  return $true
}

Write-Host "Eversilver dev bootstrap" -ForegroundColor Magenta
Write-Host "  PowerShell : $($PSVersionTable.PSVersion)"
Write-Host "  Host       : $env:COMPUTERNAME / $env:USERNAME"

# --- PHASE 1: Install dependencies ---
Write-Step "Phase 1: installing toolchain"
Install-Winget 'Git.Git'                           'Git'
Install-Winget 'OpenJS.NodeJS.LTS'                 'Node.js (LTS)'
Install-Winget 'Rustlang.Rustup'                   'Rustup'
Install-Winget 'Kitware.CMake'                     'CMake'
Install-Winget 'Ninja-build.Ninja'                 'Ninja'
Install-Winget 'LLVM.LLVM'                         'LLVM / Clang'
Install-Winget 'Microsoft.WindowsSDK.10.0.22621'   'Windows 10/11 SDK'
Install-Winget 'Microsoft.VisualStudio.2022.BuildTools' 'MSVC Build Tools' `
  '--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.Windows10SDK'

# pnpm via corepack (ships with Node)
if (Get-Command corepack -ErrorAction SilentlyContinue) {
  Write-Step "Enabling pnpm via corepack"
  corepack enable 2>&1 | Out-Null
  corepack prepare pnpm@10.10.0 --activate 2>&1 | Out-Null
  Write-Ok "pnpm enabled"
} else {
  Write-Warn2 "corepack missing -- install Node first then re-run"
}

# --- PHASE 2: PATH wiring ---
Write-Step "Phase 2: configuring user PATH"
$candidates = @(
  "$env:USERPROFILE\.cargo\bin",
  'C:\Program Files\CMake\bin',
  'C:\Program Files\LLVM\bin',
  "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Ninja-build.Ninja_Microsoft.Winget.Source_8wekyb3d8bbwe",
  'C:\Program Files\nodejs',
  "$env:APPDATA\npm"
)
foreach ($d in $candidates) { [void](Add-UserPath $d) }

[Environment]::SetEnvironmentVariable('LIBCLANG_PATH', 'C:\Program Files\LLVM\bin', 'User')
$env:LIBCLANG_PATH = 'C:\Program Files\LLVM\bin'
Write-Ok 'LIBCLANG_PATH = C:\Program Files\LLVM\bin'

# --- PHASE 3: Sanity check ---
Write-Step "Phase 3: tool verification"
$tools = @{
  'node'  = 'Node.js'
  'pnpm'  = 'pnpm'
  'cargo' = 'Cargo (Rust)'
  'cmake' = 'CMake'
  'ninja' = 'Ninja'
  'clang' = 'Clang'
}
$missing = @()
foreach ($t in $tools.Keys) {
  $cmd = Get-Command "$t.exe" -ErrorAction SilentlyContinue
  if ($cmd) { Write-Ok "$($tools[$t]): $($cmd.Source)" }
  else      { $missing += $tools[$t]; Write-Warn2 "$($tools[$t]) not on PATH (may need new shell)" }
}

# --- PHASE 4: Submodules + install ---
Write-Step "Phase 4: git submodules + pnpm install"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
Push-Location $repoRoot
try {
  & git submodule update --init --recursive 2>&1 | Out-Null
  Write-Ok 'submodules initialized'
  if (Get-Command pnpm -ErrorAction SilentlyContinue) {
    & pnpm install 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Ok 'pnpm install complete' }
    else                     { Write-Warn2 "pnpm install exited $LASTEXITCODE" }
  } else {
    Write-Warn2 'pnpm not yet on PATH -- open a new shell and run `pnpm install` manually'
  }
} finally {
  Pop-Location
}

# --- PHASE 5: Smart App Control check ---
Write-Step "Phase 5: Smart App Control + WDAC check"
try {
  $ci = Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard -ErrorAction Stop
  if ($ci.CodeIntegrityPolicyEnforcementStatus -eq 2) {
    Write-Warn2 'WDAC is enforced (status 2). Cargo build scripts will be blocked.'
    Write-Warn2 '  Turn off Memory Integrity: Windows Security -> Device Security -> Core isolation'
  }
} catch { }
try {
  $sac = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy' -ErrorAction Stop
  if ($sac.VerifiedAndReputablePolicyState -eq 1) {
    Write-Warn2 'Smart App Control is ON. Cargo build scripts will be blocked.'
    Write-Warn2 '  Turn off in: Windows Security -> App & browser control -> Smart App Control settings'
    Write-Warn2 '  NOTE: turning off SAC is a one-way action (re-enabling requires reinstall).'
  }
} catch { }

# --- Summary ---
$elapsed = (Get-Date) - $start
Write-Host "`nBootstrap complete in $([int]$elapsed.TotalSeconds)s" -ForegroundColor Magenta
if ($missing) {
  Write-Warn2 "Restart your shell so PATH updates take effect, then re-run this script."
} else {
  Write-Host "  Build with:    pnpm --filter eversilver-app win:build:release"
  Write-Host "  Install with:  pnpm --filter eversilver-app win:install"
  Write-Host "  Dev mode:      pnpm dev"
}
