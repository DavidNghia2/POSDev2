param(
    [string]$PythonVersion = "3.12",
    [string]$VenvPath = ".venv"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvFullPath = Join-Path $projectRoot $VenvPath
$requirementsPath = Join-Path $projectRoot "requirements.txt"
$logoPath = Join-Path $projectRoot "assets\app_logo.png"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Please install Python 3.11+ or 3.12 from python.org."
}

if (-not (Test-Path $requirementsPath)) {
    throw "Cannot find requirements.txt at $requirementsPath"
}

if (-not (Test-Path $logoPath)) {
    throw "Cannot find app logo at $logoPath"
}

Write-Host "Creating virtual environment with Python $PythonVersion ..."
py -$PythonVersion -m venv $venvFullPath

$pythonExe = Join-Path $venvFullPath "Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Cannot find venv python executable at $pythonExe"
}

Write-Host "Upgrading pip ..."
& $pythonExe -m pip install --upgrade pip

Write-Host "Installing dependencies ..."
& $pythonExe -m pip install -r $requirementsPath

Write-Host "Verifying app modules ..."
& $pythonExe -m compileall -q `
    (Join-Path $projectRoot "main.py") `
    (Join-Path $projectRoot "login") `
    (Join-Path $projectRoot "pos_terminal") `
    (Join-Path $projectRoot "product_management") `
    (Join-Path $projectRoot "admin") `
    (Join-Path $projectRoot "database") `
    (Join-Path $projectRoot "ui")

Write-Host "Done."
Write-Host "Run the app with:"
Write-Host "  $VenvPath\Scripts\python.exe main.py"
