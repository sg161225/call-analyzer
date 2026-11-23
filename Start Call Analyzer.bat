@echo off
REM ==================================================================
REM  Call Analyzer - double-click this file to start the app.
REM  First run: installs everything it needs (5-10 minutes).
REM  Later runs: starts in a few seconds and opens your browser.
REM ==================================================================
setlocal
cd /d "%~dp0"
title Call Analyzer

REM ---- 1. Find Python (3.10 or newer) --------------------------------
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo.
    echo Python is not installed. Installing it now...
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo Could not install Python automatically.
        echo Please install it from https://www.python.org/downloads/
        echo IMPORTANT: tick "Add python.exe to PATH" during installation.
        echo Then double-click this file again.
        pause
        exit /b 1
    )
    echo.
    echo Python is installed. Please CLOSE this window and double-click
    echo "Start Call Analyzer" again to continue.
    pause
    exit /b 0
)

REM ---- 2. Create the app's private Python environment (first run) ----
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo First-time setup: creating the app environment...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo Could not create the environment. Please send a screenshot of this window.
        pause
        exit /b 1
    )
)
set "VPY=.venv\Scripts\python.exe"

REM ---- 3. Install / update packages (quick when already installed) ---
"%VPY%" -c "import streamlit, groq, pandas, altair, openpyxl, dotenv, imageio_ffmpeg" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Installing the app's packages. This takes a few minutes the first time...
    "%VPY%" -m pip install --upgrade pip --disable-pip-version-check -q
    set "OK="
    for /l %%i in (1,1,3) do (
        if not defined OK (
            "%VPY%" -m pip install --retries 10 --timeout 120 --disable-pip-version-check -r requirements.txt && set "OK=1"
        )
    )
    "%VPY%" -c "import streamlit, groq, pandas, altair, openpyxl, dotenv, imageio_ffmpeg" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo Package installation did not finish. Check your internet connection
        echo and double-click this file again. If it keeps failing, send a
        echo screenshot of this window.
        pause
        exit /b 1
    )
) else (
    "%VPY%" -m pip install -q --disable-pip-version-check -r requirements.txt >nul 2>&1
)

REM ---- 4. Start the app ------------------------------------------------
echo.
echo ==================================================================
echo   Call Analyzer is starting. Your browser will open at:
echo.
echo       http://localhost:8501
echo.
echo   Keep this window open while you use the app.
echo   To stop the app, close this window.
echo ==================================================================
echo.
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 6; Start-Process 'http://localhost:8501'"
"%VPY%" -m streamlit run app.py --server.port 8501 --server.headless true --browser.gatherUsageStats false
pause
