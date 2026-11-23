@echo off
title MyAI - Cloudflare Public Tunnel
color 0E
cd /d "%~dp0"

echo ========================================================
echo        Starting MyAI with Public Cloudflare Access
echo ========================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" tunnel_launcher.py
) else (
    python tunnel_launcher.py
)

pause
