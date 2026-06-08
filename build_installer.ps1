param(
    [switch]$SkipPyInstallerBuild,
    [switch]$SkipPyInstallerInstall
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EnvPath = Join-Path $ProjectRoot ".env"
$DistAppDir = Join-Path $ProjectRoot "dist\RetailPOS"
$DistExe = Join-Path $DistAppDir "RetailPOS.exe"
$StagingDir = Join-Path $ProjectRoot "build\installer\RetailPOS"
$InnoScript = Join-Path $ProjectRoot "installer\RetailPOS.iss"

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

function Reset-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-ChildPath -Path $Path -Parent (Join-Path $ProjectRoot "build")
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Read-EnvFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    $values = @{}
    foreach ($rawLine in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }

        $key, $value = $line.Split("=", 2)
        $key = $key.Trim()
        $value = $value.Trim().Trim('"').Trim("'")
        if ($key) {
            $values[$key] = $value
        }
    }
    return $values
}

function Assert-SupabaseEnv {
    if (-not (Test-Path $EnvPath)) {
        throw "Cannot find .env. Create .env with SUPABASE_URL and SUPABASE_ANON_KEY before building the installer."
    }

    $envValues = Read-EnvFile -Path $EnvPath
    foreach ($key in @("SUPABASE_URL", "SUPABASE_ANON_KEY")) {
        if (-not $envValues.ContainsKey($key) -or [string]::IsNullOrWhiteSpace([string]$envValues[$key])) {
            throw ".env is missing $key. The installer needs this value so the installed app works immediately."
        }
    }

    if (-not ([string]$envValues["SUPABASE_URL"]).StartsWith("http")) {
        throw ".env SUPABASE_URL must look like a valid URL."
    }
}

function Find-InnoCompiler {
    $command = Get-Command "iscc" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    foreach ($candidate in @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
    )) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    return $null
}

if (-not (Test-Path $PythonExe)) {
    throw "Cannot find .venv\Scripts\python.exe. Run setup.ps1 or create the virtual environment first."
}

Assert-SupabaseEnv

if (-not $SkipPyInstallerBuild) {
    $buildExeArgs = @()
    if ($SkipPyInstallerInstall) {
        $buildExeArgs += "-SkipInstall"
    }
    & (Join-Path $ProjectRoot "build_exe.ps1") @buildExeArgs
}

if (-not (Test-Path $DistExe)) {
    throw "Cannot find $DistExe. Run .\build_exe.ps1 first or rerun this script without -SkipPyInstallerBuild."
}

$InnoCompiler = Find-InnoCompiler
if (-not $InnoCompiler) {
    throw "Inno Setup compiler was not found. Install it with: winget install JRSoftware.InnoSetup"
}

Reset-Directory -Path $StagingDir
Copy-Item -Path (Join-Path $DistAppDir "*") -Destination $StagingDir -Recurse -Force
Copy-Item -LiteralPath $EnvPath -Destination (Join-Path $StagingDir ".env") -Force

if (Test-Path (Join-Path $StagingDir "pos.db")) {
    Remove-Item -LiteralPath (Join-Path $StagingDir "pos.db") -Force
}

Write-Host ""
Write-Host "Building installer with Inno Setup..." -ForegroundColor Cyan
& $InnoCompiler `
    "/DSourceDir=$StagingDir" `
    "/DProjectRoot=$ProjectRoot" `
    $InnoScript

$InstallerExe = Join-Path $ProjectRoot "installer\Output\RetailPOSSetup.exe"
if (-not (Test-Path $InstallerExe)) {
    throw "Installer build finished but $InstallerExe was not found."
}

Write-Host ""
Write-Host "Installer build complete:" -ForegroundColor Green
Write-Host "  $InstallerExe"
Write-Host ""
Write-Host "This installer includes .env from this build machine. Use only SUPABASE_ANON_KEY, never a service-role key."
