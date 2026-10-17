@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
    echo Python 3.9 or newer is required. Install Python and add it to PATH.
    pause
    exit /b 1
)
python tools\dashboard.py --open
if errorlevel 1 pause
endlocal
