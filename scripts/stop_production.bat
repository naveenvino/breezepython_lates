@echo off
REM Stop Production Services Script for Windows

setlocal

REM Colors
set GREEN=[92m
set RED=[91m
set YELLOW=[93m
set NC=[0m

echo %YELLOW%Stopping Trading System Services...%NC%
echo ====================================

REM 1. Stop monitoring service
echo Stopping monitoring service...
curl -X POST http://localhost:8000/monitoring/stop >nul 2>&1

REM 2. Find and kill Python processes running the API
echo Stopping API server...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    taskkill /PID %%a /F >nul 2>&1
)

REM 3. Stop Redis if running
echo Stopping Redis...
taskkill /IM redis-server.exe /F >nul 2>&1

REM 4. Kill any remaining Python processes for our app
echo Cleaning up Python processes...
wmic process where "commandline like '%%unified_api%%'" delete >nul 2>&1

REM 5. Check if services are stopped
timeout /t 2 /nobreak >nul

netstat -ano | findstr :8000 >nul 2>&1
if not errorlevel 1 (
    echo %YELLOW%[WARNING]%NC% Some services may still be running on port 8000
) else (
    echo %GREEN%All services stopped successfully%NC%
)

echo.
echo Services have been stopped.
echo To restart, run: start_production.bat

endlocal
pause