param(
    [switch]$OneFile,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$BundledAssetsDir = Join-Path $ProjectRoot "build\pyinstaller_assets\assets"
if (-not (Test-Path $PythonExe)) {
    throw "Cannot find .venv\Scripts\python.exe. Run setup.ps1 or create the virtual environment first."
}

if (-not $SkipInstall) {
    & $PythonExe -m pip install --upgrade "pyinstaller>=6,<7"
}

& $PythonExe -m compileall -q main.py app_paths.py admin cloud database login pos_terminal product_management ui

$IconPath = Join-Path $ProjectRoot "assets\app_logo.ico"
$IconScript = @'
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

source = Path("assets/app_logo.png")
target = Path("assets/app_logo.ico")
image = QImage(str(source))
if image.isNull():
    raise SystemExit(f"Cannot load {source}")

icon = image.scaled(
    256,
    256,
    Qt.AspectRatioMode.KeepAspectRatio,
    Qt.TransformationMode.SmoothTransformation,
)
if not icon.save(str(target), "ICO"):
    raise SystemExit(f"Cannot save {target}")
'@
$IconScript | & $PythonExe -

function Assert-ChildPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $resolvedParent = [System.IO.Path]::GetFullPath($Parent)
    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $resolvedPath.StartsWith($resolvedParent, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify path outside $resolvedParent`: $resolvedPath"
    }
}

function Reset-BundledAssets {
    Assert-ChildPath -Path $BundledAssetsDir -Parent (Join-Path $ProjectRoot "build")
    if (Test-Path $BundledAssetsDir) {
        Remove-Item -LiteralPath $BundledAssetsDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $BundledAssetsDir -Force | Out-Null
}

function Copy-BundledAsset {
    param([Parameter(Mandatory = $true)][string]$RelativePath)

    $source = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path $source)) {
        throw "Required bundled asset is missing: $RelativePath"
    }

    $relativeInsideAssets = $RelativePath.Substring("assets\".Length)
    $destination = Join-Path $BundledAssetsDir $relativeInsideAssets
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force
}

Reset-BundledAssets
Copy-BundledAsset "assets\app_logo.png"
Copy-BundledAsset "assets\ui_check.svg"
Copy-BundledAsset "assets\ui_chevron_down.svg"
Copy-BundledAsset "assets\ui_radio_dot.svg"
Copy-BundledAsset "assets\ui_radio_dot_muted.svg"

$PyInstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name",
    "RetailPOS",
    "--icon",
    $IconPath,
    "--add-data",
    "$BundledAssetsDir;assets",
    "--collect-all",
    "qtawesome",
    "--collect-all",
    "supabase",
    "--collect-all",
    "gotrue",
    "--collect-all",
    "postgrest",
    "--collect-all",
    "realtime",
    "--collect-all",
    "storage3",
    "--collect-all",
    "supafunc"
)

if ($OneFile) {
    $PyInstallerArgs += "--onefile"
}

$PyInstallerArgs += "main.py"
& $PythonExe -m PyInstaller @PyInstallerArgs

if ($OneFile) {
    $OutputExe = Join-Path $ProjectRoot "dist\RetailPOS.exe"
    $ConfigDir = Join-Path $ProjectRoot "dist"
} else {
    $OutputExe = Join-Path $ProjectRoot "dist\RetailPOS\RetailPOS.exe"
    $ConfigDir = Join-Path $ProjectRoot "dist\RetailPOS"
}

if (Test-Path ".env.example") {
    Copy-Item -LiteralPath ".env.example" -Destination (Join-Path $ConfigDir ".env.example") -Force
}

Write-Host ""
Write-Host "Build complete:" -ForegroundColor Green
Write-Host "  $OutputExe"
Write-Host ""
Write-Host "Supabase config:" -ForegroundColor Yellow
Write-Host "  Copy your .env file to $ConfigDir, or set SUPABASE_URL and SUPABASE_ANON_KEY in Windows environment variables."
Write-Host "  Do not copy pos.db into dist; the app creates its runtime DB under %LOCALAPPDATA%\RetailPOS\pos.db."
Write-Host "  To build an installer that includes .env automatically, run .\build_installer.ps1."
Write-Host "  Bundled assets are minimized: app logo and UI SVG files only; assets\products is not packaged."
