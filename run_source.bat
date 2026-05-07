@echo off
echo Starting AEP Data Explorer from source...
call .venv\Scripts\activate.bat
python main.py
if errorlevel 1 goto error
goto end

:error
echo.
echo Application crashed or exited with an error.
pause

:end
