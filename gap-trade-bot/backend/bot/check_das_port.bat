@echo off
echo ========================================
echo    Checking DAS Trader Port Status
echo ========================================
echo.

echo Checking for DAS Trader processes...
echo.

echo Method 1: Check all listening ports
echo ----------------------------------------
netstat -an | findstr LISTENING | findstr ":8080"
if %errorlevel% equ 0 (
    echo ✅ Port 8080 is in use (likely DAS Trader)
) else (
    echo ❌ Port 8080 is not in use
)

echo.
echo Method 2: Check all ports for DAS processes
echo ----------------------------------------
netstat -ano | findstr "DAS"
if %errorlevel% equ 0 (
    echo ✅ Found DAS-related connections
) else (
    echo ❌ No DAS connections found
)

echo.
echo Method 3: Check specific common DAS ports
echo ----------------------------------------
echo Checking common DAS Trader ports:
for %%p in (8080 8081 8082 5001 5002) do (
    netstat -an | findstr ":%%p" | findstr LISTENING >nul
    if !errorlevel! equ 0 (
        echo ✅ Port %%p is in use
    ) else (
        echo ❌ Port %%p is not in use
    )
)

echo.
echo Method 4: Find DAS Trader process
echo ----------------------------------------
tasklist | findstr /i "das"
if %errorlevel% equ 0 (
    echo ✅ DAS Trader process found
) else (
    echo ❌ DAS Trader process not found
)

echo.
echo Method 5: Check all listening ports
echo ----------------------------------------
echo All listening ports:
netstat -an | findstr LISTENING | findstr ":808"

echo.
echo ========================================
echo    Port Check Complete
echo ========================================
echo.
echo If DAS Trader is running, you should see:
echo - Port 8080 (or similar) in use
echo - DAS Trader process in tasklist
echo.
echo If not found:
echo 1. Make sure DAS Trader is running
echo 2. Check DAS Trader API settings
echo 3. Restart DAS Trader
echo.
pause
