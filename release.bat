@echo off
echo ========================================================
echo AEP Data Explorer - Automated Release and Git Push Script
echo ========================================================
echo.

echo [1/3] Zipping the optimized build...
if exist dist\AEP_DataExplorer_Optimized.zip del /q dist\AEP_DataExplorer_Optimized.zip
powershell -Command "Compress-Archive -Path .\dist\AEP_DataExplorer -DestinationPath .\dist\AEP_DataExplorer_Optimized.zip -Force"
echo Build zipped successfully to dist\AEP_DataExplorer_Optimized.zip.
echo.

echo [2/3] Committing changes to Git...
git add .
git commit -m "Optimize PyInstaller build, exclude heavy ML libraries, fix data restoration bugs"
git push origin main
echo Git push complete.
echo.

echo [3/3] Publishing Release to GitHub...
gh --version >nul 2>&1
if %errorlevel% == 0 (
    echo GitHub CLI found. Creating release v1.1.0...
    gh release create v1.1.0 .\dist\AEP_DataExplorer_Optimized.zip -t "v1.1.0 - Optimized Build & Bug Fixes" -n "Includes isolated clean-room build strategy and fixes for local data cache OS purging."
    echo Release published successfully!
) else (
    echo [WARNING] GitHub CLI (gh) is not installed or not in PATH!
    echo Your code has been pushed to GitHub, but the ZIP file was NOT uploaded to the releases page.
    echo Please go to your GitHub repository in your browser and manually create a release, then upload:
    echo "dist\AEP_DataExplorer_Optimized.zip"
)

echo.
pause
