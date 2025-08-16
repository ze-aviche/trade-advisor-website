@echo off
REM Gap-Trade-Bot Stop Services Batch Wrapper

echo Stopping Gap-Trade-Bot Services...
powershell -ExecutionPolicy Bypass -File "%~dp0stop_background.ps1"
pause
