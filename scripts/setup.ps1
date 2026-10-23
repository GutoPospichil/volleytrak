param(
    [switch]$Cv,
    [string]$TorchIndex = "https://download.pytorch.org/whl/cu126"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$cache = Join-Path $root ".cache"
$pipCache = Join-Path $cache "pip"
$temp = Join-Path $cache "tmp"
New-Item -ItemType Directory -Force -Path $pipCache, $temp | Out-Null

$env:PIP_CACHE_DIR = $pipCache
$env:TMP = $temp
$env:TEMP = $temp

$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$pipFlags = @(
    "--trusted-host", "pypi.org",
    "--trusted-host", "files.pythonhosted.org",
    "--trusted-host", "download.pytorch.org"
)

if (-not (Test-Path $python)) {
    Write-Host "Criando venv em $venv"
    py -3.11 -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Falha ao criar a venv" }
}

Write-Host "Atualizando pip"
& $python -m pip install --upgrade pip @pipFlags
if ($LASTEXITCODE -ne 0) { throw "Falha ao atualizar o pip" }

Write-Host "Instalando dependencias base"
& $python -m pip install @pipFlags -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar requirements.txt" }

if ($Cv) {
    Write-Host "Instalando PyTorch CUDA e Ultralytics"
    & $python -m pip install @pipFlags torch torchvision --index-url $TorchIndex
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar PyTorch" }
    & $python -m pip install @pipFlags -r (Join-Path $root "requirements-cv.txt")
    if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar Ultralytics" }
}

Write-Host ""
Write-Host "Pronto. Para iniciar:"
Write-Host "  .\scripts\run.ps1"
