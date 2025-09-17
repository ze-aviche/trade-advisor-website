# DAS Pro Startup PowerShell Script
# This script starts DAS Pro and establishes connection

Write-Host "🚀 Starting DAS Pro and establishing connection..." -ForegroundColor Green
Write-Host ""

# Change to the script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Check if virtual environment exists and activate it
$VenvPath = Join-Path $ScriptDir "..\venv\Scripts\Activate.ps1"
if (Test-Path $VenvPath) {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & $VenvPath
}

# Run the DAS startup script
Write-Host "Running DAS Pro startup script..." -ForegroundColor Cyan
python start_das_pro.py

# Keep window open to see results
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
