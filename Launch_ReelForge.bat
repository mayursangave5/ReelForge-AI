@echo off
setlocal enabledelayedexpansion
title ReelForge AI Studio Launcher

:: 1. Switch to project directory
cd /d "%~dp0"
echo ======================================================================
echo                     ReelForge AI Studio Launcher                      
echo ======================================================================
echo.
echo [*] ReelForge AI is starting...
echo [*] Project directory: %CD%

:: 2. Check Python virtual environment
echo [*] Checking Python environment...
if not exist ".venv\Scripts\activate.bat" (
    echo.
    echo ======================================================================
    echo [ERROR] Virtual environment not found at:
    echo         %CD%\.venv\Scripts\activate.bat
    echo.
    echo Please make sure the .venv directory exists in S:\REEL.
    echo ======================================================================
    pause
    exit /b 1
)

:: 3. Activate virtual environment
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to activate the Python virtual environment.
    pause
    exit /b 1
)
echo [*] Python environment: OK (.venv active)

:: 4. Verify Streamlit is installed
python -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Streamlit is not installed in the virtual environment!
    echo         Run: pip install streamlit
    echo.
    pause
    exit /b 1
)
echo [*] Streamlit module: OK

:: 5. Check if ReelForge AI Studio is already running (prevent duplicates)
python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501', timeout=1)" >nul 2>&1
if not errorlevel 1 (
    echo.
    echo ======================================================================
    echo [INFO] ReelForge AI Studio is ALREADY RUNNING on http://localhost:8501!
    echo [INFO] Opening the active dashboard in your default browser...
    echo ======================================================================
    start http://localhost:8501
    timeout /t 3 >nul
    exit /b 0
)

:: 6. Launch Streamlit Dashboard
echo [*] Starting Streamlit dashboard...
echo [*] Dashboard URL: http://localhost:8501
echo.
echo ======================================================================
echo  Dashboard is starting. Your browser will open automatically.
echo  To STOP the dashboard safely, press Ctrl+C in this terminal window.
echo ======================================================================
echo.

python -m streamlit run reels\dashboard.py --server.headless=false --server.port=8501 --browser.serverAddress=localhost

:: 7. Error handling if Streamlit exits unexpectedly
if errorlevel 1 (
    echo.
    echo ======================================================================
    echo [ERROR] Streamlit encountered an issue or exited unexpectedly.
    echo ======================================================================
    pause
)
