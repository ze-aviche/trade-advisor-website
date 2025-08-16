# Gap-Trade-Bot Backend Startup Script (PowerShell)

# Get the project root directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "Starting Gap-Trade-Bot Backend..." -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot" -ForegroundColor Yellow

# Create logs directory if it doesn't exist
$backendLogsDir = Join-Path $ProjectRoot "backend\logs"
if (-not (Test-Path $backendLogsDir)) { 
    New-Item -ItemType Directory -Path $backendLogsDir -Force | Out-Null 
    Write-Host "Created logs directory" -ForegroundColor Green
}

# Check if port 5000 is available
Write-Host "Checking port 5000..." -ForegroundColor Magenta
$backendPort = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($backendPort) {
    Write-Host "Port 5000 is already in use. Stopping existing process..." -ForegroundColor Yellow
    foreach ($process in $backendPort) {
        Stop-Process -Id $process.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

# Stop any existing Python processes
Write-Host "Cleaning up existing Python processes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Start backend
Write-Host "Starting backend server..." -ForegroundColor Cyan
$backendLogFile = Join-Path $backendLogsDir "gap_trade_backend_all.log"

# Start the backend as a background job
$backendJob = Start-Job -ScriptBlock {
    param($projectRoot, $logFile)
    Set-Location "$projectRoot\backend"
    python app.py | Tee-Object -FilePath $logFile
} -ArgumentList $ProjectRoot, $backendLogFile

# Wait for backend to start
Write-Host "Waiting for backend to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 8

# Check if backend is running by checking the port
$backendPort = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($backendPort) {
    Write-Host "Backend started successfully and is listening on port 5000" -ForegroundColor Green
} else {
    Write-Host "Backend failed to start - port 5000 not listening" -ForegroundColor Red
    Write-Host "Check $backendLogFile for details" -ForegroundColor Yellow
    exit 1
}

# Test backend health
Write-Host "Testing backend health..." -ForegroundColor Magenta
Start-Sleep -Seconds 3
$healthResponse = Invoke-RestMethod -Uri "http://localhost:5000/api/health" -Method Get -TimeoutSec 5 -ErrorAction SilentlyContinue
if ($healthResponse) {
    Write-Host "Backend API is responding" -ForegroundColor Green
} else {
    Write-Host "Backend health check failed, but service may still be starting..." -ForegroundColor Yellow
}

# Final status
Write-Host ""
Write-Host "Backend startup completed!" -ForegroundColor Green
Write-Host "Backend URL: http://localhost:5000" -ForegroundColor Cyan
Write-Host "Log file: $backendLogFile" -ForegroundColor Yellow
Write-Host ""
Write-Host "To stop: Use stop_services.bat or manually kill Python processes" -ForegroundColor Yellow
Write-Host "To check status: check_status.bat" -ForegroundColor Yellow
