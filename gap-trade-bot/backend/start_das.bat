@echo off
echo Starting DAS Pro and establishing connection...
echo.

REM Change to the backend directory
cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist "..\venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call "..\venv\Scripts\activate.bat"
)

REM Run the DAS startup script
python start_das_pro.py

REM Keep window open to see results
pause
