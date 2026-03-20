#!/usr/bin/env powershell
param()

$ErrorActionPreference = "Stop"

Write-Host "===== Mermaid to PNG Converter =====" -ForegroundColor Cyan
Write-Host ""

$projectDir = "c:\Dhiman\Heroma\Utilities\mermaidtopng"
$exePath = "$projectDir\src\MermaidPng.App\bin\Debug\net8.0-windows\MermaidPng.exe"

# Change to project directory
Set-Location $projectDir

try {
    # Stop any running instances
    Write-Host "Checking for running instances..." -ForegroundColor Yellow
    $processes = Get-Process -Name "MermaidPng" -ErrorAction SilentlyContinue
    if ($processes) {
        Write-Host "Stopping $($processes.Count) running instance(s)..." -ForegroundColor Yellow
        $processes | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
    }
    
    Write-Host "Cleaning build artifacts..." -ForegroundColor Yellow
    try {
        if (Test-Path "src\MermaidPng.App\bin") {
            Remove-Item -Recurse -Force "src\MermaidPng.App\bin" -ErrorAction SilentlyContinue
        }
        if (Test-Path "src\MermaidPng.App\obj") {
            Remove-Item -Recurse -Force "src\MermaidPng.App\obj" -ErrorAction SilentlyContinue
        }
    }
    catch {
        Write-Host "Warning: Could not clean all files (some may be in use)" -ForegroundColor Yellow
    }
    
    Write-Host "Building application..." -ForegroundColor Yellow
    $buildOutput = & dotnet build -c Debug 2>&1
    Write-Host $buildOutput
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed!" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    Write-Host "`nBuild successful!" -ForegroundColor Green
    
    if (-not (Test-Path $exePath)) {
        Write-Host "ERROR: Executable not found at $exePath" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    Write-Host "Launching application..." -ForegroundColor Green
    Write-Host "Executable path: $exePath" -ForegroundColor Gray
    
    # Launch the application
    & $exePath
}
catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
