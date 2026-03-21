param(
    [string]$PythonExe = ".venv/Scripts/python.exe",
    [switch]$Clean,
    [string]$BuildPath = "out/build",
    [string]$DistPath = "out/dist"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Remove-PathWithRetry {
    param([string]$TargetPath)
    if (-not (Test-Path $TargetPath)) { return $true }
    for ($i = 0; $i -lt 5; $i++) {
        try {
            Remove-Item $TargetPath -Recurse -Force -ErrorAction Stop
            return $true
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    Write-Warning "Unable to remove path due to lock: $TargetPath"
    return $false
}

$absBuildPath = Join-Path $root $BuildPath
$absDistPath = Join-Path $root $DistPath

if ($Clean) {
    Remove-PathWithRetry $absBuildPath
    Remove-PathWithRetry $absDistPath
}

if (-not (Test-Path $absBuildPath)) { New-Item -ItemType Directory -Path $absBuildPath | Out-Null }
if (-not (Test-Path $absDistPath)) { New-Item -ItemType Directory -Path $absDistPath | Out-Null }

& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r requirements.txt pyinstaller

& $PythonExe -m PyInstaller --noconfirm --workpath $absBuildPath --distpath $absDistPath pdf_gui.spec

$distExe = Join-Path $absDistPath "pdf_tools_gui.exe"
if (-not (Test-Path $distExe)) {
    throw "Expected dist output not found: $distExe"
}

Write-Host "Build complete: $distExe"
