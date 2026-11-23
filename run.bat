@echo off
title MyAI - Personal AI Assistant
cd /d "%~dp0"

echo ========================================================
echo               Starting MyAI Application
echo ========================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py
) else (
    python run.py
)

pause
