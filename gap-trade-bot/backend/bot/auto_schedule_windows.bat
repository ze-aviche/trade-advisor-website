@echo off
setlocal enabledelayedexpansion

REM Auto Schedule Trading Bot - Windows
REM Automatically starts bot at 5 AM ET and stops at 8 PM ET

set "BOT_DIR=%~dp0"
set "VENV_PATH=%BOT_DIR%..\..\venv"
set "LOG_FILE=%BOT_DIR%auto_schedule.log"
set "SCRIPT_NAME=%~nx0"

echo 🤖 Gap Trade Bot - Auto Schedule (Windows)
echo ==========================================

REM Function to log messages
:log_message
echo %date% %time% - %~1 >> "%LOG_FILE%"
echo %~1
goto :eof

REM Function to start bot
:start_bot
call :log_message "🚀 Starting bot..."

REM Check if bot is already running
if exist "%BOT_DIR%bot.pid" (
    set /p PID=<"%BOT_DIR%bot.pid"
    tasklist /FI "PID eq !PID!" 2>nul | find /I "python.exe" >nul
    if !errorlevel! equ 0 (
        call :log_message "⚠️ Bot is already running (PID: !PID!)"
        exit /b 1
    ) else (
        call :log_message "🧹 Cleaning up stale PID file"
        del "%BOT_DIR%bot.pid" 2>nul
    )
)

REM Activate virtual environment and start bot
cd /d "%BOT_DIR%"
call "%VENV_PATH%\Scripts\activate.bat"

REM Start bot in background
start /B python run_bot.py > bot_auto.log 2>&1

REM Wait a moment and check if started successfully
timeout /t 3 /nobreak >nul
if exist "%BOT_DIR%bot.pid" (
    set /p BOT_PID=<"%BOT_DIR%bot.pid"
    call :log_message "✅ Bot started successfully (PID: !BOT_PID!)"
    exit /b 0
) else (
    call :log_message "❌ Failed to start bot"
    exit /b 1
)

REM Function to stop bot
:stop_bot
call :log_message "🛑 Stopping bot..."

if exist "%BOT_DIR%bot.pid" (
    set /p PID=<"%BOT_DIR%bot.pid"
    tasklist /FI "PID eq !PID!" 2>nul | find /I "python.exe" >nul
    if !errorlevel! equ 0 (
        REM Try graceful shutdown
        taskkill /PID !PID! /F >nul 2>&1
        
        REM Wait for graceful shutdown
        for /l %%i in (1,1,10) do (
            tasklist /FI "PID eq !PID!" 2>nul | find /I "python.exe" >nul
            if !errorlevel! neq 0 (
                call :log_message "✅ Bot stopped gracefully"
                exit /b 0
            )
            timeout /t 1 /nobreak >nul
        )
        
        call :log_message "✅ Bot force stopped"
        exit /b 0
    ) else (
        call :log_message "⚠️ Bot process not running"
        del "%BOT_DIR%bot.pid" 2>nul
        exit /b 0
    )
) else (
    call :log_message "⚠️ No PID file found - bot may not be running"
    exit /b 0
)

REM Function to check bot status
:check_bot
if exist "%BOT_DIR%bot.pid" (
    set /p PID=<"%BOT_DIR%bot.pid"
    tasklist /FI "PID eq !PID!" 2>nul | find /I "python.exe" >nul
    if !errorlevel! equ 0 (
        call :log_message "✅ Bot is running (PID: !PID!)"
        exit /b 0
    ) else (
        call :log_message "❌ Bot is not running (stale PID file)"
        del "%BOT_DIR%bot.pid" 2>nul
        exit /b 1
    )
) else (
    call :log_message "❌ Bot is not running (no PID file)"
    exit /b 1
)

REM Function to setup scheduled tasks
:setup_tasks
call :log_message "🔧 Setting up scheduled tasks..."

REM Create start task (5 AM ET = 10 AM UTC, Monday-Friday)
schtasks /create /tn "GapTradeBot_Start" /tr "cmd /c \"%BOT_DIR%!SCRIPT_NAME! start\"" /sc daily /st 10:00 /f /ru System /rl highest >nul 2>&1

REM Create stop task (8 PM ET = 1 AM UTC next day, Monday-Friday)
schtasks /create /tn "GapTradeBot_Stop" /tr "cmd /c \"%BOT_DIR%!SCRIPT_NAME! stop\"" /sc daily /st 01:00 /f /ru System /rl highest >nul 2>&1

call :log_message "✅ Scheduled tasks installed:"
call :log_message "   - Start: 5:00 AM ET Monday-Friday"
call :log_message "   - Stop:  8:00 PM ET Monday-Friday"

REM Function to remove scheduled tasks
:remove_tasks
call :log_message "🗑️ Removing scheduled tasks..."

schtasks /delete /tn "GapTradeBot_Start" /f >nul 2>&1
schtasks /delete /tn "GapTradeBot_Stop" /f >nul 2>&1

call :log_message "✅ Scheduled tasks removed"

REM Function to show task status
:show_tasks
echo 📅 Current Scheduled Tasks:
schtasks /query /tn "GapTradeBot_Start" 2>nul | find "TaskName" || echo No start task found
schtasks /query /tn "GapTradeBot_Stop" 2>nul | find "TaskName" || echo No stop task found

REM Main script logic
if "%1"=="start" goto start_bot
if "%1"=="stop" goto stop_bot
if "%1"=="check" goto check_bot
if "%1"=="setup" goto setup_tasks
if "%1"=="remove" goto remove_tasks
if "%1"=="status" (
    call :show_tasks
    echo.
    call :check_bot
    goto :eof
)

REM Show usage if no valid command
echo Usage: %0 {start^|stop^|check^|setup^|remove^|status}
echo.
echo Commands:
echo   start   - Start the trading bot
echo   stop    - Stop the trading bot
echo   check   - Check if bot is running
echo   setup   - Install scheduled tasks for auto scheduling
echo   remove  - Remove scheduled tasks
echo   status  - Show task status and bot status
echo.
echo Auto Schedule:
echo   - Start: 5:00 AM ET Monday-Friday
echo   - Stop:  8:00 PM ET Monday-Friday
echo.
echo Log file: %LOG_FILE%
goto :eof 