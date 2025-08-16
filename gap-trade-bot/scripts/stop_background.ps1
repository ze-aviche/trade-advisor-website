# Gap-Trade-Bot Background Stop Script (PowerShell)

Write-Host "🛑 Stopping Gap-Trade-Bot..." -ForegroundColor Cyan

# Function to kill process by pattern
function Stop-ProcessByPattern {
    param(
        [string]$Pattern,
        [string]$Name
    )
    
    Write-Host "🔍 Looking for $Name processes..." -ForegroundColor Magenta
    
    # Get all Python processes and filter by command line
    $processes = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*$Pattern*"
    }
    
    if ($processes) {
        $pids = $processes.Id -join ", "
        Write-Host "📋 Found $Name PIDs: $pids" -ForegroundColor Yellow
        Write-Host "💀 Killing $Name processes..." -ForegroundColor Red
        
        # Stop processes gracefully first
        $processes | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        
        # Force kill if still running
        $stillRunning = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
            $_.CommandLine -like "*$Pattern*"
        }
        
        if ($stillRunning) {
            Write-Host "⚡ Force killing $Name processes..." -ForegroundColor Red
            $stillRunning | Stop-Process -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        }
        
        # Final check
        $finalCheck = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
            $_.CommandLine -like "*$Pattern*"
        }
        
        if (-not $finalCheck) {
            Write-Host "✅ $Name stopped successfully" -ForegroundColor Green
        } else {
            $finalPids = $finalCheck.Id -join ", "
            Write-Host "❌ $Name still running (PIDs: $finalPids)" -ForegroundColor Red
        }
    } else {
        Write-Host "ℹ️ No $Name processes found" -ForegroundColor Yellow
    }
}

# Kill trading bot
Stop-ProcessByPattern -Pattern "run_bot.py" -Name "Trading Bot"

# Kill backend
Stop-ProcessByPattern -Pattern "app.py" -Name "Backend"

# Kill frontend
Stop-ProcessByPattern -Pattern "http.server" -Name "Frontend"

# Additional cleanup - kill any remaining processes on our ports
Write-Host "🧹 Cleaning up any remaining processes on our ports..." -ForegroundColor Yellow

# Kill anything on port 5000 (backend)
$backendProcesses = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($backendProcesses) {
    foreach ($process in $backendProcesses) {
        Stop-Process -Id $process.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Write-Host "✅ Killed processes on port 5000" -ForegroundColor Green
} else {
    Write-Host "ℹ️ No processes on port 5000" -ForegroundColor Yellow
}

# Kill anything on port 3000 (frontend)
$frontendProcesses = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
if ($frontendProcesses) {
    foreach ($process in $frontendProcesses) {
        Stop-Process -Id $process.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Write-Host "✅ Killed processes on port 3000" -ForegroundColor Green
} else {
    Write-Host "ℹ️ No processes on port 3000" -ForegroundColor Yellow
}

# Clean up any background jobs that might be running
Write-Host "🧹 Cleaning up background jobs..." -ForegroundColor Yellow
Get-Job | Where-Object { 
    $_.Name -like "*bot*" -or 
    $_.Name -like "*backend*" -or 
    $_.Name -like "*frontend*" 
} | Stop-Job -PassThru | Remove-Job

Write-Host ""
Write-Host "🎯 Gap-Trade-Bot stop process completed!" -ForegroundColor Green
