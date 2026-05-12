param(
    [string]$PythonVersion = "3.12",
    [string]$VenvPath = ".venv"
)

$ErrorActionPreference = "Stop"

Write-Host "Creating virtual environment with Python $PythonVersion ..."
py -$PythonVersion -m venv $VenvPath

$pythonExe = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Cannot find venv python executable at $pythonExe"
}

Write-Host "Upgrading pip ..."
& $pythonExe -m pip install --upgrade pip

Write-Host "Installing dependencies ..."
& $pythonExe -m pip install -r requirements.txt

Write-Host "Done."
Write-Host "Run the app with:"
Write-Host "  $VenvPath\Scripts\python.exe main.py"
