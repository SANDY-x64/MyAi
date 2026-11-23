@echo off
title MyAI - Stop Server
color 0C
cd /d "%~dp0"

echo ========================================================
echo              Stopping MyAI & Cloudflare Tunnel
echo ========================================================
echo.

echo [1] Terminating MyAI server process on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [2] Terminating any running Cloudflare Tunnel daemons...
taskkill /F /IM cloudflared.exe >nul 2>&1

echo.
echo ========================================================
echo        MyAI and all active tunnels are now OFF.
echo ========================================================
echo.
timeout /t 3
exit
