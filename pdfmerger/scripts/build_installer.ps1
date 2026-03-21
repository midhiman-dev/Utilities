param(
    [string]$IsccExe = "iscc",
    [string]$DistPath = "out/dist",
    [string]$InstallerOutputDir = "out/installer",
    [string]$AppVersion = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $DistPath)) {
    throw "Dist path not found. Build GUI first: $DistPath"
}

if (-not (Test-Path $InstallerOutputDir)) {
    New-Item -ItemType Directory -Path $InstallerOutputDir | Out-Null
}

if ([string]::IsNullOrWhiteSpace($AppVersion)) {
    $AppVersion = & .venv/Scripts/python.exe -c "from src.pdf_gui import __version__; print(__version__)"
}

$issFile = Join-Path $root "installer/pdf_tools_gui.iss"
if (-not (Test-Path $issFile)) {
    throw "Inno Setup script not found: $issFile"
}

function Resolve-IsccPath {
    param([string]$Requested)

    $cmd = Get-Command $Requested -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "ISCC not found. Install Inno Setup 6 and ensure 'iscc' is on PATH or pass -IsccExe with full path."
}

$resolvedIscc = Resolve-IsccPath -Requested $IsccExe

$isccArgs = @(
        "/DMyAppVersion=$AppVersion",
        "/DBuildDistDir=$DistPath",
        "/DInstallerOutputDir=$InstallerOutputDir",
        $issFile
)

& $resolvedIscc @isccArgs

Write-Host "Installer build complete in: $InstallerOutputDir"
