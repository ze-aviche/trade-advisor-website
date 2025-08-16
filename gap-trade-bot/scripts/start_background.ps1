# Gap-Trade-Bot Background Startup Script (PowerShell)

# Get the project root directory (where this script is located)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "🚀 Starting Gap-Trade-Bot in background..." -ForegroundColor Cyan
Write-Host "📁 Project root: $ProjectRoot" -ForegroundColor Yellow

# Function to check if port is available
function Test-Port {
    param(
        [int]$Port,
        [string]$Service
    )
    
    $connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if ($connection) {
        Write-Host "❌ Port $Port is already in use by $Service" -ForegroundColor Red
        return $false
    } else {
        Write-Host "✅ Port $Port is available" -ForegroundColor Green
        return $true
    }
}

# Function to start service with validation
function Start-ServiceWithValidation {
    param(
        [string]$Name,
        [string]$Command,
        [string]$LogFile,
        [int]$Port
    )
    
    Write-Host "🔍 Starting $Name..." -ForegroundColor Magenta
    
    # Check port if specified
    if ($Port) {
        if (-not (Test-Port -Port $Port -Service $Name)) {
            Write-Host "💀 Killing process on port $Port..." -ForegroundColor Yellow
            $processes = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
            foreach ($process in $processes) {
                Stop-Process -Id $process.OwningProcess -Force -ErrorAction SilentlyContinue
            }
            Start-Sleep -Seconds 2
        }
    }
    
    # Start the service
    $job = Start-Job -ScriptBlock {
        param($cmd, $logFile)
        Set-Location $using:ProjectRoot
        Invoke-Expression $cmd | Tee-Object -FilePath $logFile
    } -ArgumentList $Command, $LogFile
    
    # Wait for service to start
    Start-Sleep -Seconds 3
    
    # Check if job is running
    if ($job.State -eq "Running") {
        Write-Host "✅ $Name started successfully (Job ID: $($job.Id))" -ForegroundColor Green
        return $job
    } else {
        Write-Host "❌ $Name failed to start" -ForegroundColor Red
        return $null
    }
}

# Create logs directories if they don't exist
$backendLogsDir = Join-Path $ProjectRoot "backend\logs"
$botLogsDir = Join-Path $ProjectRoot "backend\bot\logs"
$frontendDir = Join-Path $ProjectRoot "frontend"

if (-not (Test-Path $backendLogsDir)) { New-Item -ItemType Directory -Path $backendLogsDir -Force | Out-Null }
if (-not (Test-Path $botLogsDir)) { New-Item -ItemType Directory -Path $botLogsDir -Force | Out-Null }
if (-not (Test-Path $frontendDir)) { New-Item -ItemType Directory -Path $frontendDir -Force | Out-Null }

# Clean up any existing processes
Write-Host "🛑 Cleaning up any existing processes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Check if ports are available
Write-Host "🔍 Checking port availability..." -ForegroundColor Magenta
if (-not (Test-Port -Port 5000 -Service "Backend")) { exit 1 }
if (-not (Test-Port -Port 3000 -Service "Frontend")) { exit 1 }

# Start trading bot first
Write-Host "🤖 Starting trading bot..." -ForegroundColor Cyan
$botLogFile = Join-Path $botLogsDir "gap_trade_bot_all.log"
$botJob = Start-ServiceWithValidation -Name "Trading Bot" -Command "cd '$ProjectRoot\backend\bot'; python run_bot.py" -LogFile $botLogFile

if (-not $botJob) {
    Write-Host "❌ Trading bot failed to start" -ForegroundColor Red
    Write-Host "📋 Check $botLogFile for details" -ForegroundColor Yellow
    exit 1
}

# Wait for bot to initialize
Write-Host "⏳ Waiting for bot to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check if bot is still running
if ($botJob.State -eq "Running") {
    Write-Host "✅ Trading bot started (Job ID: $($botJob.Id))" -ForegroundColor Green
} else {
    Write-Host "❌ Trading bot failed to start" -ForegroundColor Red
    Write-Host "📋 Check $botLogFile for details" -ForegroundColor Yellow
    exit 1
}

# Start backend
Write-Host "🔧 Starting backend server..." -ForegroundColor Cyan
$backendLogFile = Join-Path $backendLogsDir "gap_trade_backend_all.log"
$backendJob = Start-ServiceWithValidation -Name "Backend" -Command "cd '$ProjectRoot\backend'; python app.py" -LogFile $backendLogFile -Port 5000

if (-not $backendJob) {
    Write-Host "❌ Backend failed to start" -ForegroundColor Red
    Write-Host "📋 Check $backendLogFile for details" -ForegroundColor Yellow
    exit 1
}

# Wait for backend to start
Write-Host "⏳ Waiting for backend to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check if backend is still running
if ($backendJob.State -eq "Running") {
    Write-Host "✅ Backend started (Job ID: $($backendJob.Id))" -ForegroundColor Green
} else {
    Write-Host "❌ Backend failed to start" -ForegroundColor Red
    Write-Host "📋 Check $backendLogFile for details" -ForegroundColor Yellow
    exit 1
}

# Test backend health
Write-Host "🔍 Testing backend health..." -ForegroundColor Magenta
Start-Sleep -Seconds 2
try {
    $response = Invoke-RestMethod -Uri "http://localhost:5000/api/health" -Method Get -TimeoutSec 5
    Write-Host "✅ Backend is responding" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Backend health check failed, but continuing..." -ForegroundColor Yellow
}

# Start frontend
Write-Host "🌐 Starting frontend server..." -ForegroundColor Cyan
$frontendLogFile = Join-Path $frontendDir "frontend.log"
$frontendJob = Start-ServiceWithValidation -Name "Frontend" -Command "cd '$ProjectRoot\frontend'; python -m http.server 3000" -LogFile $frontendLogFile -Port 3000

if (-not $frontendJob) {
    Write-Host "❌ Frontend failed to start" -ForegroundColor Red
    Write-Host "📋 Check $frontendLogFile for details" -ForegroundColor Yellow
    exit 1
}

# Wait for frontend to start
Write-Host "⏳ Waiting for frontend to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Check if frontend is still running
if ($frontendJob.State -eq "Running") {
    Write-Host "✅ Frontend started (Job ID: $($frontendJob.Id))" -ForegroundColor Green
} else {
    Write-Host "❌ Frontend failed to start" -ForegroundColor Red
    Write-Host "📋 Check $frontendLogFile for details" -ForegroundColor Yellow
    exit 1
}

# Final status check
Write-Host ""
Write-Host "🎯 Gap-Trade-Bot startup completed!" -ForegroundColor Green
Write-Host "📊 Backend: http://localhost:5000" -ForegroundColor Cyan
Write-Host "🌐 Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "📋 Logs: $botLogFile, $backendLogFile, $frontendLogFile" -ForegroundColor Yellow
Write-Host ""
Write-Host "🛑 To stop: $ProjectRoot\scripts\stop_services.bat" -ForegroundColor Yellow
Write-Host "📊 To check status: $ProjectRoot\scripts\check_status.bat" -ForegroundColor Yellow
Write-Host ""
Write-Host "🔍 Checking final status..." -ForegroundColor Magenta

# Run status check using the working batch file
& "$ProjectRoot\scripts\check_status.bat"
