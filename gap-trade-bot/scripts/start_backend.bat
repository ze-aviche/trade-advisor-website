@echo off
echo ========================================
echo   Starting Gap-Trade-Bot Backend
echo ========================================

REM Get project root directory
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

echo Project root: %PROJECT_ROOT%

REM Create logs directory if it doesn't exist
if not exist "%PROJECT_ROOT%\backend\logs" mkdir "%PROJECT_ROOT%\backend\logs"

REM Check if port 5000 is available
echo Checking port 5000...
netstat -an | find ":5000" | find "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo Port 5000 is already in use. Stopping existing process...
    for /f "tokens=5" %%a in ('netstat -ano ^| find ":5000" ^| find "LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)

REM Stop any existing Python processes
echo Cleaning up existing Python processes...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM Start backend
echo Starting backend server...
cd /d "%PROJECT_ROOT%\backend"
start /B python app.py > logs\gap_trade_backend_all.log 2>&1

REM Wait for backend to start
echo Waiting for backend to start...
timeout /t 8 /nobreak >nul

REM Check if backend is running
echo Checking if backend started successfully...
netstat -an | find ":5000" | find "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo Backend started successfully and is listening on port 5000
) else (
    echo Backend failed to start - port 5000 not listening
    echo Check logs\gap_trade_backend_all.log for details
    pause
    exit /b 1
)

REM Test backend health
echo Testing backend health...
timeout /t 3 /nobreak >nul
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:5000/api/health' -UseBasicParsing -TimeoutSec 5; if ($response.StatusCode -eq 200) { Write-Host 'Backend API is responding' } else { Write-Host 'Backend health check failed' } } catch { Write-Host 'Backend health check failed' }" 2>nul

REM Final status
echo.
echo ========================================
echo Backend startup completed!
echo Backend URL: http://localhost:5000
echo Log file: %PROJECT_ROOT%\backend\logs\gap_trade_backend_all.log
echo ========================================
echo.
echo To stop: Use stop_services.bat or manually kill Python processes
echo To check status: check_status.bat
echo ========================================
pause
