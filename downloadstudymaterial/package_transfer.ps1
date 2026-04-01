[CmdletBinding()]
param(
    [ValidateSet('minimal', 'extended')]
    [string]$Mode = 'extended',

    [string]$OutputDir = 'dist',

    [string]$ZipName
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$minimalFiles = @(
    'requirements.txt',
    'drive_folder_downloader.py',
    'app/__init__.py',
    'app/main.py',
    'app/drive_service.py',
    'app/zip_jobs.py'
)

$extendedOnlyFiles = @(
    'README.md',
    '.gitignore',
    'app/templates/home.html',
    'app/templates/browse.html',
    'app/templates/search.html',
    'app/static/app.js',
    'app/static/main.css',
    'app/static/favicon.svg'
)

$filesToInclude = @($minimalFiles)
if ($Mode -eq 'extended') {
    $filesToInclude += $extendedOnlyFiles
}

# Ensure all expected files exist before creating the archive.
$missing = @()
foreach ($relativePath in $filesToInclude) {
    $fullPath = Join-Path $repoRoot ($relativePath -replace '/', '\\')
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        $missing += $relativePath
    }
}

if ($missing.Count -gt 0) {
    Write-Error ("Cannot create transfer ZIP. Missing required files:`n- " + ($missing -join "`n- "))
}

$outputDirectoryPath = Join-Path $repoRoot ($OutputDir -replace '/', '\\')
if (-not (Test-Path -LiteralPath $outputDirectoryPath -PathType Container)) {
    New-Item -ItemType Directory -Path $outputDirectoryPath | Out-Null
}

if ([string]::IsNullOrWhiteSpace($ZipName)) {
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $ZipName = "downloadmaterial-$Mode-$timestamp.zip"
}

$zipPath = Join-Path $outputDirectoryPath $ZipName
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

$tempRoot = Join-Path $outputDirectoryPath (".transfer_staging_" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot | Out-Null

try {
    foreach ($relativePath in $filesToInclude) {
        $sourcePath = Join-Path $repoRoot ($relativePath -replace '/', '\\')
        $stagingPath = Join-Path $tempRoot ($relativePath -replace '/', '\\')

        $stagingDir = Split-Path -Parent $stagingPath
        if (-not (Test-Path -LiteralPath $stagingDir -PathType Container)) {
            New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null
        }

        Copy-Item -LiteralPath $sourcePath -Destination $stagingPath -Force
    }

    Compress-Archive -Path (Join-Path $tempRoot '*') -DestinationPath $zipPath -CompressionLevel Optimal
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host "Created transfer ZIP: $zipPath"
Write-Host "Included mode: $Mode"
Write-Host "Included files:"
$filesToInclude | ForEach-Object { Write-Host ("- " + $_) }
