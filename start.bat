@echo off
title MyCon Learn
cd /d "%~dp0"

:: Start browser after a short delay (in background)
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8000"

:: Run the server (closing this window stops the app)
poetry run uvicorn app.main:app --host 127.0.0.1 --port 8000
