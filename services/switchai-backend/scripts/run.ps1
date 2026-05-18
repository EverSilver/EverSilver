# Windows launcher: loads .env (if present) then runs uvicorn.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*#') { return }
        if ($_ -match '^\s*$') { return }
        $kv = $_ -split '=', 2
        if ($kv.Count -eq 2) {
            $name = $kv[0].Trim()
            $value = $kv[1].Trim().Trim('"').Trim("'")
            [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

$bindHost = $env:SWITCHAI_HOST; if (-not $bindHost) { $bindHost = "127.0.0.1" }
$port = $env:SWITCHAI_PORT; if (-not $port) { $port = "8088" }

python -m uvicorn app.main:app --host $bindHost --port $port
