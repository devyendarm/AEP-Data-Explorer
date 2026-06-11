@echo off
echo ========================================================
echo AEP Data Explorer - Source Code Launcher
echo ========================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your system PATH.
    echo Please install Python 3.9+ to run this application from source.
    pause
    exit /b 1
)

:: Check if the virtual environment exists, if not, create it
if not exist .venv (
    echo [INFO] First time setup detected! Creating virtual environment...
    python -m venv .venv
    
    echo [INFO] Installing required libraries...
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip >nul
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install requirements. Please check your internet connection.
        pause
        exit /b 1
    )
    echo [INFO] Setup complete!
) else (
    call .venv\Scripts\activate.bat
)

echo Starting AEP Data Explorer...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo Application crashed or exited with an error.
    pause
)

call .venv\Scripts\deactivate.bat
exit /b 0
