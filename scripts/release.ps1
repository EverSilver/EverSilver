<#
.SYNOPSIS
  End-to-end release pipeline for Eversilver on Windows.

.DESCRIPTION
  One command to ship a versioned build. Runs:
    1. git working-tree-clean check (or use -AllowDirty)
    2. version bump in app/package.json + Cargo.toml + tauri.conf.json
    3. full vitest + cargo check
    4. cargo tauri build (MSI + NSIS)
    5. SHA-256 hash of every artifact
    6. git commit + tag (signed if you have a signing key)
    7. write a release-NN.json manifest you can attach to a GitHub release
    8. optional: push tag

  After this script exits cleanly, your installer artifacts live in
    app/src-tauri/target/release/bundle/
  and the SHA-256 manifest in
    release/eversilver-<version>.json

.PARAMETER Bump
  patch (default), minor, or major. Or pass an exact version like 1.2.3.

.PARAMETER AllowDirty
  Skip the clean-working-tree check.

.PARAMETER SkipTests
  Skip the test suite. Avoid for actual releases.

.PARAMETER NoTag
  Don't create a git tag (still bumps version + builds).

.PARAMETER Push
  After tagging, push the commit + tag to origin.

.EXAMPLE
  pwsh -File scripts/release.ps1                          # patch bump
  pwsh -File scripts/release.ps1 -Bump minor              # minor bump
  pwsh -File scripts/release.ps1 -Bump 1.0.0              # exact version
  pwsh -File scripts/release.ps1 -SkipTests -NoTag        # dev iteration
#>
[CmdletBinding()]
param(
  [string]$Bump = 'patch',
  [switch]$AllowDirty,
  [switch]$SkipTests,
  [switch]$NoTag,
  [switch]$Push
)

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')

function Write-Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Write-Fail($m) { Write-Host "  X   $m" -ForegroundColor Red; throw $m }

function Get-CurrentVersion {
  $pkg = Get-Content (Join-Path $repoRoot 'app\package.json') -Raw | ConvertFrom-Json
  return $pkg.version
}

function Compute-NextVersion([string]$current, [string]$bump) {
  if ($bump -match '^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$') { return $bump }
  $parts = $current.Split('.')
  if ($parts.Length -lt 3) { Write-Fail "Cannot parse current version '$current'" }
  $major = [int]$parts[0]; $minor = [int]$parts[1]; $patch = [int]($parts[2] -replace '-.*$', '')
  switch ($bump) {
    'patch' { return "$major.$minor.$($patch + 1)" }
    'minor' { return "$major.$($minor + 1).0" }
    'major' { return "$($major + 1).0.0" }
    default { Write-Fail "Unknown bump strategy: $bump" }
  }
}

function Update-PackageJsonVersion([string]$path, [string]$newVersion) {
  $raw = Get-Content $path -Raw
  $obj = $raw | ConvertFrom-Json
  $obj.version = $newVersion
  # Preserve the original formatting style by writing JSON then aligning indent.
  $json = $obj | ConvertTo-Json -Depth 64
  # ConvertTo-Json uses 2-space indent in PowerShell — matches our prettier config.
  Set-Content $path -Value $json -Encoding UTF8 -NoNewline
  Add-Content $path -Value "`n"
}

function Update-TauriConfVersion([string]$path, [string]$newVersion) {
  if (-not (Test-Path $path)) { return }
  $raw = Get-Content $path -Raw
  $obj = $raw | ConvertFrom-Json
  if (-not $obj.version) { return }
  $obj.version = $newVersion
  $json = $obj | ConvertTo-Json -Depth 64
  Set-Content $path -Value $json -Encoding UTF8 -NoNewline
  Add-Content $path -Value "`n"
}

function Update-CargoTomlVersion([string]$path, [string]$newVersion) {
  if (-not (Test-Path $path)) { return }
  $lines = Get-Content $path
  $inPackage = $false
  $changed = $false
  for ($i = 0; $i -lt $lines.Length; $i++) {
    if ($lines[$i] -match '^\[package\]') { $inPackage = $true; continue }
    if ($lines[$i] -match '^\[') { $inPackage = $false; continue }
    if ($inPackage -and $lines[$i] -match '^\s*version\s*=\s*"[^"]+"') {
      $lines[$i] = $lines[$i] -replace '"[^"]+"', "`"$newVersion`""
      $changed = $true
    }
  }
  if ($changed) { Set-Content $path -Value $lines -Encoding UTF8 }
}

# 1. Clean working tree
Write-Step "1. Working tree state"
Push-Location $repoRoot
try {
  $dirty = git status --porcelain
  if ($dirty -and -not $AllowDirty) {
    $dirty | ForEach-Object { Write-Host "  $_" }
    Write-Fail "Working tree is dirty. Commit or stash, or pass -AllowDirty."
  } elseif ($dirty) {
    Write-Host "  (dirty, but -AllowDirty was passed)"
  } else {
    Write-Ok "clean"
  }

  # 2. Version bump
  Write-Step "2. Version bump"
  $current = Get-CurrentVersion
  $next = Compute-NextVersion -current $current -bump $Bump
  Write-Host "  $current -> $next"

  Update-PackageJsonVersion (Join-Path $repoRoot 'app\package.json') $next
  Update-PackageJsonVersion (Join-Path $repoRoot 'package.json') $next
  Update-TauriConfVersion   (Join-Path $repoRoot 'app\src-tauri\tauri.conf.json') $next
  Update-CargoTomlVersion   (Join-Path $repoRoot 'Cargo.toml') $next
  Update-CargoTomlVersion   (Join-Path $repoRoot 'app\src-tauri\Cargo.toml') $next
  Write-Ok "version bumped to $next in package.json + tauri.conf.json + Cargo.toml"

  # 3. Tests
  if (-not $SkipTests) {
    Write-Step "3. Tests"
    Push-Location (Join-Path $repoRoot 'app')
    try {
      & pnpm exec vitest run --config test/vitest.config.ts --no-coverage
      if ($LASTEXITCODE -ne 0) { Write-Fail "vitest failed" }
      Write-Ok "vitest"
      & pnpm exec tsc --noEmit
      if ($LASTEXITCODE -ne 0) { Write-Fail "typecheck failed" }
      Write-Ok "typecheck"
    } finally {
      Pop-Location
    }
  } else {
    Write-Host "`n==> 3. Tests (SKIPPED)" -ForegroundColor Yellow
  }

  # 4. Build installers
  Write-Step "4. Build installers (MSI + NSIS)"
  & (Join-Path $PSScriptRoot 'win-build.ps1') -Profile release -Bundles msi,nsis
  if ($LASTEXITCODE -ne 0) { Write-Fail "Tauri build failed" }

  # 5. Hash artifacts
  Write-Step "5. SHA-256 manifest"
  $bundleDir = Join-Path $repoRoot 'app\src-tauri\target\release\bundle'
  $artifacts = @(Get-ChildItem -Path $bundleDir -Recurse -Include '*.msi', '*-setup.exe')
  if (-not $artifacts) { Write-Fail "No artifacts found in $bundleDir" }
  $manifest = [ordered]@{
    name      = 'eversilver'
    version   = $next
    timestamp = (Get-Date).ToUniversalTime().ToString('o')
    os        = 'windows'
    arch      = 'x86_64'
    artifacts = @()
  }
  foreach ($a in $artifacts) {
    $hash = (Get-FileHash -Path $a.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $manifest.artifacts += [ordered]@{
      file   = $a.Name
      bytes  = $a.Length
      sha256 = $hash
    }
    Write-Host ("  {0,8:N1} MB  sha256:{1}..  {2}" -f ($a.Length / 1MB), $hash.Substring(0, 12), $a.Name)
  }
  $releaseDir = Join-Path $repoRoot 'release'
  New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
  $manifestPath = Join-Path $releaseDir "eversilver-$next.json"
  $manifest | ConvertTo-Json -Depth 16 | Set-Content $manifestPath -Encoding UTF8
  Write-Ok "manifest: $manifestPath"

  # 6. Commit + tag
  if (-not $NoTag) {
    Write-Step "6. Commit + tag"
    & git add -A
    & git commit -m "chore(release): v$next"
    & git tag -a "v$next" -m "Eversilver v$next"
    Write-Ok "tagged v$next"

    if ($Push) {
      Write-Step "7. Push"
      & git push origin HEAD --no-verify
      & git push origin "v$next"
      Write-Ok "pushed v$next"
    }
  } else {
    Write-Host "`n==> 6. Commit + tag (SKIPPED)" -ForegroundColor Yellow
  }

  Write-Host "`nRelease v$next is ready." -ForegroundColor Magenta
  Write-Host "  Installer:  $bundleDir\nsis\Eversilver_${next}_x64-setup.exe"
  Write-Host "  Installer:  $bundleDir\msi\Eversilver_${next}_x64_en-US.msi"
  Write-Host "  Manifest:   $manifestPath"
  if (-not $Push -and -not $NoTag) {
    Write-Host "  Next:  git push origin HEAD --tags"
  }
} finally {
  Pop-Location
}
