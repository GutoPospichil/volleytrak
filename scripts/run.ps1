param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Rode .\scripts\setup.ps1 antes de iniciar."
}

$env:PYTHONUTF8 = "1"
& $python -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload --reload-dir app --reload-dir pipeline
