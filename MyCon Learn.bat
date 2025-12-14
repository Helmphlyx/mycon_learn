@echo off
title MyCon Learn - Vietnamese Practice
cd /d "%~dp0"

echo ================================================
echo   MyCon Learn - Vietnamese Practice App
echo ================================================
echo.
echo Starting server...
echo Close this window to stop the app.
echo.

:: Start server and open browser
start "" http://127.0.0.1:8000
poetry run uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
