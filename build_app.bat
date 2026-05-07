@echo off
echo Cleaning generic build folders...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist dist_clean rmdir /s /q dist_clean

echo Building AEP_DataExplorer using optimized spec file...
set PYTHONHOME=
pyinstaller --clean --noconfirm AEP_DataExplorer_optimized.spec
if errorlevel 1 goto error

echo Creating Launcher in dist...
echo @echo off > dist\AEP_DataExplorer\Run_App.bat
echo start "" "%%~dp0AEP_DataExplorer.exe" >> dist\AEP_DataExplorer\Run_App.bat

echo Build Complete and Cleaned.
goto end

:error
echo Build Failed.
exit /b 1

:end
