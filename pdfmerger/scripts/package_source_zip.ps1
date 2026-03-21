param(
    [string]$OutputDir = "../",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "Packaging clean source archive..."

# Generate filename with current date
$timestamp = Get-Date -Format "yyyyMMdd"
$archiveName = "pdfmerger_source_$timestamp.zip"
$parentDir = Split-Path -Parent $root
$outputPath = Join-Path $parentDir $archiveName

# Check if file exists
if ((Test-Path $outputPath) -and -not $Force) {
    Write-Host "Archive already exists: $outputPath"
    Write-Host "Use -Force to overwrite."
    return
}

Write-Host "Creating archive: $archiveName"
Write-Host "Output: $outputPath"

try {
    # Include the current source/build assets that exist in this checkout.
    $candidateItems = @(
        "src",
        "scripts",
        "installer",
        ".github",
        "archive",
        "pdf_gui.spec",
        "requirements.txt",
        "README.md",
        ".gitignore"
    )

    $itemsToZip = @($candidateItems | Where-Object { Test-Path $_ })
    if (-not $itemsToZip) {
        throw "No source items found to package."
    }

    Compress-Archive -Path $itemsToZip -DestinationPath $outputPath -Force:$Force -ErrorAction Stop
    
    if (Test-Path $outputPath) {
        $fileSize = [math]::Round((Get-Item $outputPath).Length / 1MB, 2)
        Write-Host "SUCCESS: Archive created at $outputPath"
        Write-Host "Size: $fileSize MB"
        Write-Host ""
        Write-Host "Transfer instructions:"
        Write-Host "1. Extract on target: Expand-Archive -Path pdfmerger_source_*.zip -DestinationPath ."
        Write-Host "2. cd pdfmerger_source_* && python -m venv .venv && .\.venv\Scripts\Activate.ps1"
        Write-Host "3. pip install -r requirements.txt"
        Write-Host "4. python src/launch_gui.py  (to test)"
    }
    else {
        Write-Error "Archive not created at expected path: $outputPath"
        exit 1
    }
}
catch {
    Write-Error "Error creating archive: $_"
    exit 1
}
