@echo off
REM Gap-Trade-Bot Start Services Batch Wrapper

echo Starting Gap-Trade-Bot Services...
powershell -ExecutionPolicy Bypass -File "%~dp0start_background.ps1"
pause
