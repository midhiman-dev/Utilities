param(
    [string]$Python = "python",
    [string]$ExeName = "xl2csv"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir = Join-Path $scriptDir ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$entryScript = Join-Path $scriptDir "xlsx_to_csv.py"

if (-not (Test-Path $entryScript)) {
    throw "Cannot find entry script: $entryScript"
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment in $venvDir"
    & $Python -m venv $venvDir
}

Write-Host "Upgrading pip"
& $venvPython -m pip install --upgrade pip

Write-Host "Installing build dependencies"
& $venvPython -m pip install pyinstaller pandas openpyxl

Write-Host "Building standalone executable"
& $venvPython -m PyInstaller `
    --clean `
    --noconfirm `
    --onefile `
    --console `
    --name $ExeName `
    $entryScript

Write-Host ""
Write-Host "Build complete."
Write-Host "Executable: $(Join-Path $scriptDir "dist\$ExeName.exe")"
