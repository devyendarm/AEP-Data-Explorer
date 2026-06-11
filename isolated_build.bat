@echo off
echo ========================================================
echo AEP Data Explorer v1.3 - Full Build Pipeline
echo ========================================================
echo.

echo [1/6] Removing old builds and environments...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist build_venv rmdir /s /q build_venv
if exist dist_clean rmdir /s /q dist_clean

echo [2/6] Creating sterile Python Virtual Environment...
python -m venv build_venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment. Ensure python is in your PATH.
    pause
    exit /b 1
)

echo [3/6] Activating sterile environment and installing ONLY required packages...
call build_venv\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip >nul

echo Installing exact dependencies from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

echo [4/6] Building the Application with PyInstaller...
pyinstaller --clean --noconfirm AEP_DataExplorer_optimized.spec
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo [5/6] Creating Launcher and Portable ZIP...
echo @echo off > dist\AEP_DataExplorer\Run_App.bat
echo start "" "%%~dp0AEP_DataExplorer.exe" >> dist\AEP_DataExplorer\Run_App.bat

echo Compressing the portable build...
if exist dist\AEP_DataExplorer_Sterile_v1.3.zip del /q dist\AEP_DataExplorer_Sterile_v1.3.zip
powershell -Command "Compress-Archive -Path .\dist\AEP_DataExplorer -DestinationPath .\dist\AEP_DataExplorer_Sterile_v1.3.zip -Force"
if %errorlevel% neq 0 (
    echo [WARNING] Failed to create ZIP archive.
) else (
    echo Portable ZIP created: dist\AEP_DataExplorer_Sterile_v1.3.zip
)

echo [6/6] Running Inno Setup to create the installer EXE...

:: Check common Inno Setup install locations
set ISCC=""
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 5\ISCC.exe"

if %ISCC%=="" (
    echo [WARNING] Inno Setup not found in standard locations.
    echo           Skipping installer build. Install Inno Setup 6 from:
    echo           https://jrsoftware.org/isdl.php
    echo           Then re-run this script OR manually open AEP_DataExplorer.iss.
) else (
    echo Found Inno Setup at: %ISCC%
    %ISCC% AEP_DataExplorer.iss
    if %errorlevel% neq 0 (
        echo [ERROR] Inno Setup build failed. Check AEP_DataExplorer.iss for errors.
        pause
        exit /b 1
    )
    echo Installer created: dist\AEP_DataExplorer_Setup_v1.3.exe
)

echo Tearing down sterile environment...
call build_venv\Scripts\deactivate.bat
rmdir /s /q build_venv

echo.
echo ========================================================
echo Build Complete! v1.3 Artifacts:
echo   Portable:  dist\AEP_DataExplorer_Sterile_v1.3.zip
echo   Installer: dist\AEP_DataExplorer_Setup_v1.3.exe
echo ========================================================
pause
