@echo off
setlocal enabledelayedexpansion

REM Auto Schedule Full System - Windows
REM Manages frontend, backend, and trading bot
REM Automatically starts at 5 AM ET and stops at 8 PM ET

set "BOT_DIR=%~dp0"
set "PROJECT_ROOT=%BOT_DIR%..\.."
set "VENV_PATH=%PROJECT_ROOT%\venv"
set "LOG_FILE=%BOT_DIR%auto_schedule_full.log"
set "SCRIPT_NAME=%~nx0"

echo 🤖 Gap Trade Bot - Full System Auto Schedule (Windows)
echo ====================================================

REM Function to log messages
:log_message
echo %date% %time% - %~1 >> "%LOG_FILE%"
echo %~1
goto :eof

REM Function to check if process is running
:is_process_running
set "pid_file=%~1"
if exist "!pid_file!" (
    set /p pid=<"!pid_file!"
    tasklist /FI "PID eq !pid!" 2>nul | find /I "python.exe" >nul
    if !errorlevel! equ 0 (
        exit /b 0
    )
)
exit /b 1

REM Function to start backend server
:start_backend
call :log_message "🚀 Starting backend server..."

call :is_process_running "%PROJECT_ROOT%\backend.pid"
if !errorlevel! equ 0 (
    call :log_message "⚠️ Backend is already running"
    exit /b 1
)

cd /d "%PROJECT_ROOT%"
call "%VENV_PATH%\Scripts\activate.bat"

REM Start backend in background
start /B python backend\app.py > backend.log 2>&1

REM Wait for backend to start
timeout /t 5 /nobreak >nul

REM Check if backend started successfully
if exist "%PROJECT_ROOT%\backend.pid" (
    set /p BACKEND_PID=<"%PROJECT_ROOT%\backend.pid"
    call :log_message "✅ Backend started successfully (PID: !BACKEND_PID!)"
    exit /b 0
) else (
    REM Try to find the process by checking for Flask app
    for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV ^| find "python.exe"') do (
        REM Check if this process is running our Flask app
        tasklist /FI "PID eq %%i" /FI "WINDOWTITLE eq *Flask*" >nul 2>&1
        if !errorlevel! equ 0 (
            echo %%i > "%PROJECT_ROOT%\backend.pid"
            call :log_message "✅ Backend started successfully (PID: %%i)"
            exit /b 0
        )
    )
    call :log_message "❌ Failed to start backend"
    exit /b 1
)

REM Function to start frontend server
:start_frontend
call :log_message "🌐 Starting frontend server..."

call :is_process_running "%PROJECT_ROOT%\frontend.pid"
if !errorlevel! equ 0 (
    call :log_message "⚠️ Frontend is already running"
    exit /b 1
)

cd /d "%PROJECT_ROOT%\frontend"

REM Start frontend in background
start /B python -m http.server 3000 > frontend.log 2>&1

REM Wait for frontend to start
timeout /t 3 /nobreak >nul

REM Check if frontend started successfully
if exist "%PROJECT_ROOT%\frontend.pid" (
    set /p FRONTEND_PID=<"%PROJECT_ROOT%\frontend.pid"
    call :log_message "✅ Frontend started successfully (PID: !FRONTEND_PID!)"
    exit /b 0
) else (
    REM Try to find the process by checking for HTTP server on port 3000
    for /f "tokens=5" %%i in ('netstat -ano ^| find ":3000" ^| find "LISTENING"') do (
        echo %%i > "%PROJECT_ROOT%\frontend.pid"
        call :log_message "✅ Frontend started successfully (PID: %%i)"
        exit /b 0
    )
    call :log_message "❌ Failed to start frontend"
    exit /b 1
)

REM Function to start trading bot
:start_bot
call :log_message "🤖 Starting trading bot..."

call :is_process_running "%BOT_DIR%bot.pid"
if !errorlevel! equ 0 (
    call :log_message "⚠️ Bot is already running"
    exit /b 1
)

cd /d "%BOT_DIR%"
call "%VENV_PATH%\Scripts\activate.bat"

REM Start bot in background
start /B python run_bot.py > bot_auto.log 2>&1

REM Wait for bot to start
timeout /t 10 /nobreak >nul

REM Check if bot started successfully
if exist "%BOT_DIR%bot.pid" (
    set /p BOT_PID=<"%BOT_DIR%bot.pid"
    call :log_message "✅ Bot started successfully (PID: !BOT_PID!)"
    exit /b 0
) else (
    REM Try to find the process by checking for run_bot.py
    for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV ^| find "python.exe"') do (
        REM Check if this process is running our bot
        wmic process where "ProcessId=%%i" get CommandLine /format:list | find "run_bot.py" >nul 2>&1
        if !errorlevel! equ 0 (
            echo %%i > "%BOT_DIR%bot.pid"
            call :log_message "✅ Bot started successfully (PID: %%i)"
            exit /b 0
        )
    )
    call :log_message "❌ Failed to start bot"
    exit /b 1
)

REM Function to start all components
:start_all
call :log_message "🚀 Starting full system..."

REM Start backend
call :start_backend
if !errorlevel! equ 0 (
    call :log_message "✅ Backend started"
) else (
    call :log_message "⚠️ Backend start failed or already running"
)

REM Wait a moment
timeout /t 2 /nobreak >nul

REM Start frontend
call :start_frontend
if !errorlevel! equ 0 (
    call :log_message "✅ Frontend started"
) else (
    call :log_message "⚠️ Frontend start failed or already running"
)

REM Wait a moment
timeout /t 2 /nobreak >nul

REM Start bot
call :start_bot
if !errorlevel! equ 0 (
    call :log_message "✅ Bot started"
) else (
    call :log_message "⚠️ Bot start failed or already running"
)

call :log_message "🎉 Full system startup completed"

REM Function to stop backend
:stop_backend
call :log_message "🛑 Stopping backend..."

if exist "%PROJECT_ROOT%\backend.pid" (
    set /p pid=<"%PROJECT_ROOT%\backend.pid"
    tasklist /FI "PID eq !pid!" 2>nul | find /I "python.exe" >nul
    if !errorlevel! equ 0 (
        REM Try graceful shutdown
        taskkill /PID !pid! /F >nul 2>&1
        
        REM Wait for graceful shutdown
        for /l %%i in (1,1,10) do (
            tasklist /FI "PID eq !pid!" 2>nul | find /I "python.exe" >nul
            if !errorlevel! neq 0 (
                call :log_message "✅ Backend stopped gracefully"
                del "%PROJECT_ROOT%\backend.pid" 2>nul
                exit /b 0
            )
            timeout /t 1 /nobreak >nul
        )
        
        call :log_message "✅ Backend force stopped"
        del "%PROJECT_ROOT%\backend.pid" 2>nul
    ) else (
        call :log_message "⚠️ Backend process not running"
        del "%PROJECT_ROOT%\backend.pid" 2>nul
    )
) else (
    call :log_message "⚠️ No backend PID file found"
)

REM Function to stop frontend
:stop_frontend
call :log_message "🛑 Stopping frontend..."

if exist "%PROJECT_ROOT%\frontend.pid" (
    set /p pid=<"%PROJECT_ROOT%\frontend.pid"
    tasklist /FI "PID eq !pid!" 2>nul | find /I "python.exe" >nul
    if !errorlevel! equ 0 (
        REM Try graceful shutdown
        taskkill /PID !pid! /F >nul 2>&1
        
        REM Wait for graceful shutdown
        for /l %%i in (1,1,5) do (
            tasklist /FI "PID eq !pid!" 2>nul | find /I "python.exe" >nul
            if !errorlevel! neq 0 (
                call :log_message "✅ Frontend stopped gracefully"
                del "%PROJECT_ROOT%\frontend.pid" 2>nul
                exit /b 0
            )
            timeout /t 1 /nobreak >nul
        )
        
        call :log_message "✅ Frontend force stopped"
        del "%PROJECT_ROOT%\frontend.pid" 2>nul
    ) else (
        call :log_message "⚠️ Frontend process not running"
        del "%PROJECT_ROOT%\frontend.pid" 2>nul
    )
) else (
    call :log_message "⚠️ No frontend PID file found"
)

REM Function to stop bot
:stop_bot
call :log_message "🛑 Stopping bot..."

if exist "%BOT_DIR%bot.pid" (
    set /p pid=<"%BOT_DIR%bot.pid"
    tasklist /FI "PID eq !pid!" 2>nul | find /I "python.exe" >nul
    if !errorlevel! equ 0 (
        REM Try graceful shutdown
        taskkill /PID !pid! /F >nul 2>&1
        
        REM Wait for graceful shutdown
        for /l %%i in (1,1,10) do (
            tasklist /FI "PID eq !pid!" 2>nul | find /I "python.exe" >nul
            if !errorlevel! neq 0 (
                call :log_message "✅ Bot stopped gracefully"
                del "%BOT_DIR%bot.pid" 2>nul
                exit /b 0
            )
            timeout /t 1 /nobreak >nul
        )
        
        call :log_message "✅ Bot force stopped"
        del "%BOT_DIR%bot.pid" 2>nul
    ) else (
        call :log_message "⚠️ Bot process not running"
        del "%BOT_DIR%bot.pid" 2>nul
    )
) else (
    call :log_message "⚠️ No bot PID file found"
)

REM Function to stop all components
:stop_all
call :log_message "🛑 Stopping full system..."

REM Stop bot first (most important)
call :stop_bot

REM Stop frontend
call :stop_frontend

REM Stop backend
call :stop_backend

call :log_message "🎉 Full system shutdown completed"

REM Function to check status of all components
:check_status
call :log_message "📊 Checking system status..."

echo 🤖 Trading Bot:
call :is_process_running "%BOT_DIR%bot.pid"
if !errorlevel! equ 0 (
    set /p pid=<"%BOT_DIR%bot.pid"
    echo   ✅ Running (PID: !pid!)
) else (
    echo   ❌ Not running
)

echo 🌐 Frontend:
call :is_process_running "%PROJECT_ROOT%\frontend.pid"
if !errorlevel! equ 0 (
    set /p pid=<"%PROJECT_ROOT%\frontend.pid"
    echo   ✅ Running (PID: !pid!) - http://localhost:3000
) else (
    echo   ❌ Not running
)

echo 🚀 Backend:
call :is_process_running "%PROJECT_ROOT%\backend.pid"
if !errorlevel! equ 0 (
    set /p pid=<"%PROJECT_ROOT%\backend.pid"
    echo   ✅ Running (PID: !pid!) - http://localhost:5000
) else (
    echo   ❌ Not running
)

REM Function to setup scheduled tasks
:setup_tasks
call :log_message "🔧 Setting up scheduled tasks for full system..."

REM Remove existing tasks first
schtasks /delete /tn "GapTradeBot_Full_Start" /f >nul 2>&1
schtasks /delete /tn "GapTradeBot_Full_Stop" /f >nul 2>&1

REM Create start task (5 AM ET = 10 AM UTC, Monday-Friday)
schtasks /create /tn "GapTradeBot_Full_Start" /tr "cmd /c \"cd /d \"%BOT_DIR%\" && %BOT_DIR%!SCRIPT_NAME! start\"" /sc daily /st 10:00 /f /ru System /rl highest /mo 1 /d MON,TUE,WED,THU,FRI >nul 2>&1

REM Create stop task (8 PM ET = 1 AM UTC next day, Monday-Friday)
schtasks /create /tn "GapTradeBot_Full_Stop" /tr "cmd /c \"cd /d \"%BOT_DIR%\" && %BOT_DIR%!SCRIPT_NAME! stop\"" /sc daily /st 01:00 /f /ru System /rl highest /mo 1 /d TUE,WED,THU,FRI,SAT >nul 2>&1

call :log_message "✅ Scheduled tasks installed:"
call :log_message "   - Start: 5:00 AM ET Monday-Friday"
call :log_message "   - Stop:  8:00 PM ET Monday-Friday"

REM Function to remove scheduled tasks
:remove_tasks
call :log_message "🗑️ Removing scheduled tasks..."

schtasks /delete /tn "GapTradeBot_Full_Start" /f >nul 2>&1
schtasks /delete /tn "GapTradeBot_Full_Stop" /f >nul 2>&1

call :log_message "✅ Scheduled tasks removed"

REM Function to show task status
:show_tasks
echo 📅 Current Scheduled Tasks:
schtasks /query /tn "GapTradeBot_Full_Start" 2>nul | find "TaskName" || echo No start task found
schtasks /query /tn "GapTradeBot_Full_Stop" 2>nul | find "TaskName" || echo No stop task found

REM Main script logic
if "%1"=="start" goto start_all
if "%1"=="stop" goto stop_all
if "%1"=="check" goto check_status
if "%1"=="setup" goto setup_tasks
if "%1"=="remove" goto remove_tasks
if "%1"=="status" (
    call :check_status
    echo.
    call :show_tasks
    goto :eof
)

REM Show usage if no valid command
echo Usage: %0 {start^|stop^|check^|setup^|remove^|status}
echo.
echo Commands:
echo   start   - Start all components (backend, frontend, bot)
echo   stop    - Stop all components
echo   check   - Check status of all components
echo   setup   - Install scheduled tasks for auto scheduling
echo   remove  - Remove scheduled tasks
echo   status  - Show system status and scheduled tasks
echo.
echo Components:
echo   - Backend: Flask server (port 5000)
echo   - Frontend: HTTP server (port 3000)
echo   - Trading Bot: Automated trading
echo.
echo Auto Schedule:
echo   - Start: 5:00 AM ET Monday-Friday
echo   - Stop:  8:00 PM ET Monday-Friday
echo.
echo Log file: %LOG_FILE%
goto :eof 