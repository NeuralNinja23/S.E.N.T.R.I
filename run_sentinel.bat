@echo off
setlocal enabledelayedexpansion

:: Get root directory path of the batch file
set "ROOT_DIR=%~dp0"

echo ===================================================
echo   S.E.N.T.I.N.E.L. Startup Manager
echo ===================================================
echo.

:: Verify port 8008 and 3030 are not already in use
netstat -aon | findstr :8008 >nul
if !errorlevel! equ 0 (
    echo [Warning] Port 8008 is already in use. Cleaning up old session...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8008') do (
        taskkill /F /PID %%a >nul 2>&1
    )
)

netstat -aon | findstr :3030 >nul
if !errorlevel! equ 0 (
    echo [Warning] Port 3030 is already in use. Cleaning up old session...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3030') do (
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo [System] Starting Backend Server (FastAPI on Port 8008)...
cd /d "%ROOT_DIR%backend"
start "Sentinel_Backend" /min cmd /c "venv\Scripts\uvicorn app.main:app --port 8008"

echo [System] Starting Frontend Server (Next.js on Port 3030)...
cd /d "%ROOT_DIR%frontend"
start "Sentinel_Frontend" /min cmd /c "npm run dev -- -p 3030"

echo [System] Waking up engines and loading CUDA caches...
timeout /t 5 /nobreak >nul

echo [System] Launching J.A.R.V.I.S. Interface in Chrome (Port 3030)...
echo [System] Close the opened Chrome window to automatically stop the servers.
echo.

:: Launch Chrome in dedicated app mode with an isolated profile so we can track its process termination reliably
start /wait "" chrome --app=http://localhost:3030 --user-data-dir="%TEMP%\sentinel_chrome_profile"

echo ===================================================
echo   Chrome window closed. Shutting down S.E.N.T.I.N.E.L.
echo ===================================================
echo.

echo [System] Stopping Backend Server (Port 8008)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8008') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [System] Stopping Frontend Server (Port 3030)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3030') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [System] Cleanup complete. Goodbye!
timeout /t 2 /nobreak >nul
exit
