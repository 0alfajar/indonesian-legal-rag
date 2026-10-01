@echo off
REM Legal Atlas - Quick Setup Script (Windows)

echo.
echo Legal Atlas Setup
echo ==================
echo.

REM Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Python not found. Please install Python 3.11 or higher.
    exit /b 1
)

REM Get Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Python %PYTHON_VERSION% detected
echo.

REM Create virtual environment
echo Creating virtual environment...
python -m venv .venv

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1

REM Install dependencies
echo Installing dependencies...
pip install -e . >nul 2>&1

echo.
echo Installation complete!
echo.
echo Quick Start:
echo    .venv\Scripts\activate
echo    python -m legal_rag serve
echo.
echo Full documentation: README.md
echo.
pause
