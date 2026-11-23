@echo off
title MyAI - Local Assistant
color 0B
cd /d "%~dp0"

echo ========================================================
echo              Starting MyAI Local Platform
echo ========================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py
) else (
    python run.py
)

pause
