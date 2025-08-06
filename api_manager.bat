@echo off
REM Unified API Manager for BreezeConnect Trading System

if "%1"=="" goto menu

if "%1"=="start" goto start_api
if "%1"=="stop" goto stop_api
if "%1"=="restart" goto restart_api
if "%1"=="test" goto test_api
if "%1"=="status" goto status_api
goto invalid

:menu
echo.
echo ========================================
echo    BreezeConnect API Manager
echo ========================================
echo 1. Start API
echo 2. Stop API
echo 3. Restart API
echo 4. Test API
echo 5. Check Status
echo 6. Exit
echo ========================================
echo.
set /p choice="Enter your choice (1-6): "

if "%choice%"=="1" goto start_api
if "%choice%"=="2" goto stop_api
if "%choice%"=="3" goto restart_api
if "%choice%"=="4" goto test_api
if "%choice%"=="5" goto status_api
if "%choice%"=="6" goto end

echo Invalid choice. Please try again.
goto menu

:start_api
echo Starting Unified API on port 8000...
start "BreezeConnect API" python unified_api_correct.py
echo API started. Check the new window for logs.
if "%1"=="" pause
goto end

:stop_api
echo Stopping API...
taskkill /FI "WINDOWTITLE eq BreezeConnect API*" /T /F >nul 2>&1
taskkill /IM python.exe /FI "MEMUSAGE gt 100000" /F >nul 2>&1
echo API stopped.
if "%1"=="" pause
goto end

:restart_api
echo Restarting API...
call :stop_api
timeout /t 2 /nobreak >nul
call :start_api
goto end

:test_api
echo Testing API endpoints...
echo.
echo Testing health check...
curl -s http://localhost:8000/health || echo API is not running
echo.
echo Testing backtest endpoint...
curl -X POST http://localhost:8000/backtest -H "Content-Type: application/json" -d "{\"from_date\": \"2025-07-14\", \"to_date\": \"2025-07-18\", \"signals_to_test\": [\"S1\"]}"
echo.
if "%1"=="" pause
goto end

:status_api
echo Checking API status...
tasklist /FI "IMAGENAME eq python.exe" | findstr /I "python" >nul 2>&1
if %errorlevel%==0 (
    echo API appears to be running.
    echo.
    echo Active Python processes:
    tasklist /FI "IMAGENAME eq python.exe" /FO TABLE | findstr /I "python"
) else (
    echo API is not running.
)
if "%1"=="" pause
goto end

:invalid
echo Invalid command: %1
echo Usage: api_manager.bat [start|stop|restart|test|status]
goto end

:end
if "%1"=="" exit /b 0