@echo off
echo ========================================================
echo AEP Data Explorer - Automated Clean, Rebuild, Installer & Git Push
echo ========================================================
echo.

echo [1/6] Cleaning previous build folders...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist dist_clean rmdir /s /q dist_clean
if exist dist\AEP_DataExplorer_Optimized.zip del /q dist\AEP_DataExplorer_Optimized.zip
if exist dist\AEP_DataExplorer_Setup_v1.3.exe del /q dist\AEP_DataExplorer_Setup_v1.3.exe
echo Cleaning complete.
echo.

echo [2/6] Rebuilding PyInstaller executable...
set PYTHONHOME=
pyinstaller --clean --noconfirm AEP_DataExplorer_optimized.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller compilation failed!
    pause
    exit /b 1
)
echo.

echo [3/6] Creating Launcher and Zipping the optimized build...
echo @echo off > dist\AEP_DataExplorer\Run_App.bat
echo start "" "%%~dp0AEP_DataExplorer.exe" >> dist\AEP_DataExplorer\Run_App.bat

powershell -Command "Compress-Archive -Path .\dist\AEP_DataExplorer -DestinationPath .\dist\AEP_DataExplorer_Optimized.zip -Force"
echo Build zipped successfully to dist\AEP_DataExplorer_Optimized.zip.
echo.

echo [4/6] Running Inno Setup to create the installer EXE...
set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 5\ISCC.exe"

if not defined ISCC (
    echo [WARNING] Inno Setup compiler ^(ISCC.exe^) not found in standard locations.
    echo           Skipping installer EXE build.
) else (
    echo Found Inno Setup at: "%ISCC%"
    "%ISCC%" AEP_DataExplorer.iss
    if errorlevel 1 (
        echo [ERROR] Inno Setup compilation failed!
        pause
        exit /b 1
    )
    echo Installer setup EXE created successfully.
)
echo.

echo [5/6] Committing changes to Git and pushing to GitHub...
git add .
git commit -m "Rebuild latest version, compile Inno installer setup, and sync updates"
git push origin main
echo Git push complete.
echo.

echo [6/6] Publishing Release to GitHub...
gh --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] GitHub CLI ^(gh^) is not installed or not in PATH!
    echo Your code has been pushed to GitHub, but the release assets were NOT uploaded.
    echo Please manually create the release and upload the ZIP and installer EXE.
    goto end_release
)

echo GitHub CLI found. Creating release v1.3.0...
if exist .\dist\AEP_DataExplorer_Setup_v1.3.exe (
    gh release create v1.3.0 .\dist\AEP_DataExplorer_Optimized.zip .\dist\AEP_DataExplorer_Setup_v1.3.exe -t "v1.3.0 - Rebuilt & Cleaned Release" -n "Includes automatically rebuilt executable and installer setup with UI and core bug fixes." --clobber
) else (
    gh release create v1.3.0 .\dist\AEP_DataExplorer_Optimized.zip -t "v1.3.0 - Rebuilt & Cleaned Release" -n "Includes automatically rebuilt executable with UI and core bug fixes." --clobber
)
echo Release published successfully!

:end_release
echo.
pause
