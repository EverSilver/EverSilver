# Run the LLM backend in the foreground (Windows).
# Loads .env if python-dotenv is installed.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (Test-Path .\.venv\Scripts\Activate.ps1) {
    . .\.venv\Scripts\Activate.ps1
}
python -m uvicorn app.main:app --host $(if ($env:LLM_BACKEND_BIND_HOST) { $env:LLM_BACKEND_BIND_HOST } else { "127.0.0.1" }) --port $(if ($env:LLM_BACKEND_BIND_PORT) { $env:LLM_BACKEND_BIND_PORT } else { "8088" })
