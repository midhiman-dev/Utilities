[CmdletBinding()]
param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name "ocr-utility" `
    --paths "src" `
    --collect-all "pytesseract" `
    --collect-all "PIL" `
    --distpath "dist" `
    --workpath "build\pyinstaller" `
    --specpath "build\pyinstaller" `
    "scripts\pyinstaller_entry.py"

Write-Host "Built $repoRoot\dist\ocr-utility.exe"
