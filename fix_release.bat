@echo off
echo ========================================================
echo AEP Data Explorer - Automated Git Fix and Release Script
echo ========================================================
echo.

echo [1/4] Undoing the failed commit...
git reset HEAD~1

echo [2/4] Removing the giant ZIP file from the local folder...
if exist AEP_DataExplorer_v1.0.zip del /q AEP_DataExplorer_v1.0.zip
echo Deleted AEP_DataExplorer_v1.0.zip.

echo [3/4] Re-committing (now that .gitignore correctly blocks all ZIPs)...
git add .
git commit -m "Optimize PyInstaller build, exclude heavy ML libraries, fix data restoration bugs"
git push origin main
echo Git push complete.
echo.

echo [4/4] Publishing Release to GitHub...
gh --version >nul 2>&1
if not errorlevel 1 (
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
