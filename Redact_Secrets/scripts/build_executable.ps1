[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name redact-secrets `
    --paths src `
    --distpath $OutputDirectory `
    src\redact_secrets\__main__.py

Write-Host "Created $OutputDirectory\redact-secrets.exe"
