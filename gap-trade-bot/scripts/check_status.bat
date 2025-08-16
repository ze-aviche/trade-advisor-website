@echo off
echo ========================================
echo   Gap-Trade-Bot Status Check
echo ========================================

echo.
echo Checking Python processes...
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE 2>nul
if %errorlevel% neq 0 (
    echo ❌ No Python processes found
) else (
    echo ✅ Python processes found
)

echo.
echo Checking port 5000 (Backend)...
netstat -an | find ":5000" | find "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Port 5000: Backend server is running
    echo    🌐 URL: http://localhost:5000
) else (
    echo ❌ Port 5000: Not in use
)

echo.
echo Checking port 3000 (Frontend)...
netstat -an | find ":3000" | find "LISTENING" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Port 3000: Frontend server is running
    echo    🌐 URL: http://localhost:3000
) else (
    echo ❌ Port 3000: Not in use
)

echo.
echo ========================================
echo Summary:
echo - Use start_services.bat to start all services
echo - Use stop_services.bat to stop all services
echo ========================================
pause
