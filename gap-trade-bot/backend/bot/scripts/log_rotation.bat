@echo off
setlocal enabledelayedexpansion

REM Log Rotation Script for Gap Trade Bot (Windows)
REM Deletes logs every 6 hours to prevent disk space issues

set "BOT_DIR=%~dp0"
set "PROJECT_ROOT=%BOT_DIR%..\.."
set "LOG_FILE=%BOT_DIR%log_rotation.log"

echo 🤖 Gap Trade Bot - Log Rotation Script (Windows)
echo ================================================

REM Function to log messages
:log_message
echo %date% %time% - %~1 >> "%LOG_FILE%"
echo %~1
goto :eof

REM Function to get file size in bytes
:get_file_size
set "file=%~1"
if exist "!file!" (
    for %%A in ("!file!") do set "size=%%~zA"
) else (
    set "size=0"
)
goto :eof

REM Function to rotate logs
:rotate_logs
call :log_message "🔄 Starting log rotation..."

set "deleted_count=0"
set "total_size_before=0"
set "total_size_after=0"

REM Calculate total size before deletion
call :get_file_size "%BOT_DIR%auto_schedule_full.log"
set /a total_size_before+=!size!

call :get_file_size "%BOT_DIR%bot_auto.log"
set /a total_size_before+=!size!

call :get_file_size "%PROJECT_ROOT%\backend.log"
set /a total_size_before+=!size!

call :get_file_size "%PROJECT_ROOT%\frontend.log"
set /a total_size_before+=!size!

call :get_file_size "%BOT_DIR%auto_schedule.log"
set /a total_size_before+=!size!

REM Delete log files
if exist "%BOT_DIR%auto_schedule_full.log" (
    call :log_message "🗑️ Deleting: %BOT_DIR%auto_schedule_full.log"
    del "%BOT_DIR%auto_schedule_full.log"
    set /a deleted_count+=1
)

if exist "%BOT_DIR%bot_auto.log" (
    call :log_message "🗑️ Deleting: %BOT_DIR%bot_auto.log"
    del "%BOT_DIR%bot_auto.log"
    set /a deleted_count+=1
)

if exist "%PROJECT_ROOT%\backend.log" (
    call :log_message "🗑️ Deleting: %PROJECT_ROOT%\backend.log"
    del "%PROJECT_ROOT%\backend.log"
    set /a deleted_count+=1
)

if exist "%PROJECT_ROOT%\frontend.log" (
    call :log_message "🗑️ Deleting: %PROJECT_ROOT%\frontend.log"
    del "%PROJECT_ROOT%\frontend.log"
    set /a deleted_count+=1
)

if exist "%BOT_DIR%auto_schedule.log" (
    call :log_message "🗑️ Deleting: %BOT_DIR%auto_schedule.log"
    del "%BOT_DIR%auto_schedule.log"
    set /a deleted_count+=1
)

REM Calculate total size after deletion
call :get_file_size "%BOT_DIR%auto_schedule_full.log"
set /a total_size_after+=!size!

call :get_file_size "%BOT_DIR%bot_auto.log"
set /a total_size_after+=!size!

call :get_file_size "%PROJECT_ROOT%\backend.log"
set /a total_size_after+=!size!

call :get_file_size "%PROJECT_ROOT%\frontend.log"
set /a total_size_after+=!size!

call :get_file_size "%BOT_DIR%auto_schedule.log"
set /a total_size_after+=!size!

set /a freed_space=total_size_before - total_size_after

call :log_message "✅ Log rotation completed:"
call :log_message "   - Files deleted: !deleted_count!"
call :log_message "   - Space freed: !freed_space! bytes"
call :log_message "   - Total size before: !total_size_before! bytes"
call :log_message "   - Total size after: !total_size_after! bytes"

REM Function to setup scheduled task for log rotation
:setup_log_rotation
call :log_message "🔧 Setting up log rotation scheduled task..."

REM Remove existing task first
schtasks /delete /tn "GapTradeBot_LogRotation" /f >nul 2>&1

REM Create scheduled task to run every 6 hours
schtasks /create /tn "GapTradeBot_LogRotation" /tr "cmd /c \"cd /d \"%BOT_DIR%\" && %BOT_DIR%log_rotation.bat rotate\"" /sc daily /st 00:00 /f /ru System /rl highest /mo 1 /d MON,TUE,WED,THU,FRI,SAT,SUN >nul 2>&1

REM Also create additional triggers for 6, 12, and 18 hours
schtasks /change /tn "GapTradeBot_LogRotation" /tr "cmd /c \"cd /d \"%BOT_DIR%\" && %BOT_DIR%log_rotation.bat rotate\"" /st 06:00 >nul 2>&1
schtasks /change /tn "GapTradeBot_LogRotation" /tr "cmd /c \"cd /d \"%BOT_DIR%\" && %BOT_DIR%log_rotation.bat rotate\"" /st 12:00 >nul 2>&1
schtasks /change /tn "GapTradeBot_LogRotation" /tr "cmd /c \"cd /d \"%BOT_DIR%\" && %BOT_DIR%log_rotation.bat rotate\"" /st 18:00 >nul 2>&1

call :log_message "✅ Log rotation scheduled task installed (every 6 hours)"

REM Function to remove log rotation scheduled task
:remove_log_rotation
call :log_message "🗑️ Removing log rotation scheduled task..."

schtasks /delete /tn "GapTradeBot_LogRotation" /f >nul 2>&1

call :log_message "✅ Log rotation scheduled task removed"

REM Function to show log rotation status
:show_status
call :log_message "📊 Log rotation status:"

REM Check if scheduled task exists
schtasks /query /tn "GapTradeBot_LogRotation" >nul 2>&1
if !errorlevel! equ 0 (
    call :log_message "✅ Log rotation scheduled task is active"
    schtasks /query /tn "GapTradeBot_LogRotation" | find "TaskName"
) else (
    call :log_message "❌ Log rotation scheduled task not found"
)

REM Show log file sizes
call :log_message "📁 Current log file sizes:"

call :get_file_size "%BOT_DIR%auto_schedule_full.log"
set /a size_mb=!size! / 1024 / 1024
call :log_message "   - %BOT_DIR%auto_schedule_full.log: !size_mb! MB"

call :get_file_size "%BOT_DIR%bot_auto.log"
set /a size_mb=!size! / 1024 / 1024
call :log_message "   - %BOT_DIR%bot_auto.log: !size_mb! MB"

call :get_file_size "%PROJECT_ROOT%\backend.log"
set /a size_mb=!size! / 1024 / 1024
call :log_message "   - %PROJECT_ROOT%\backend.log: !size_mb! MB"

call :get_file_size "%PROJECT_ROOT%\frontend.log"
set /a size_mb=!size! / 1024 / 1024
call :log_message "   - %PROJECT_ROOT%\frontend.log: !size_mb! MB"

call :get_file_size "%BOT_DIR%auto_schedule.log"
set /a size_mb=!size! / 1024 / 1024
call :log_message "   - %BOT_DIR%auto_schedule.log: !size_mb! MB"

REM Main script logic
if "%1"=="rotate" goto rotate_logs
if "%1"=="setup" goto setup_log_rotation
if "%1"=="remove" goto remove_log_rotation
if "%1"=="status" goto show_status
if "%1"=="manual" goto rotate_logs

REM Show usage if no valid command
echo Usage: %0 {rotate^|setup^|remove^|status^|manual}
echo.
echo Commands:
echo   rotate  - Rotate logs (delete old log files)
echo   setup   - Install scheduled task for automatic rotation (every 6 hours)
echo   remove  - Remove scheduled task for automatic rotation
echo   status  - Show log rotation status and file sizes
echo   manual  - Manually rotate logs now
echo.
echo Log files rotated:
echo   - %BOT_DIR%auto_schedule_full.log
echo   - %BOT_DIR%bot_auto.log
echo   - %PROJECT_ROOT%\backend.log
echo   - %PROJECT_ROOT%\frontend.log
echo   - %BOT_DIR%auto_schedule.log
echo.
echo Schedule: Every 6 hours (0, 6, 12, 18)
echo Log file: %LOG_FILE%
goto :eof 