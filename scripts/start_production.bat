@echo off
REM Production Startup Script for Windows (without Docker)
REM Starts the trading system in production mode

setlocal

REM Configuration
set WORKERS=4
set PORT=8000
set HOST=0.0.0.0
set LOG_FILE=logs\production.log

REM Colors
set GREEN=[92m
set RED=[91m
set YELLOW=[93m
set NC=[0m

echo %GREEN%Starting Trading System in Production Mode%NC%
echo ==========================================

REM 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Python is not installed or not in PATH
    exit /b 1
)

REM 2. Create directories
if not exist logs mkdir logs
if not exist data mkdir data
if not exist backups mkdir backups

REM 3. Check environment file
if not exist .env (
    if exist .env.production (
        echo Copying production environment...
        copy .env.production .env
    ) else (
        echo %RED%[ERROR]%NC% Environment file not found. Please create .env file
        exit /b 1
    )
)

REM 4. Install dependencies
echo Installing dependencies...
pip install -q -r requirements-prod.txt

REM 5. Run database migrations
echo Running database migrations...
python -c "from src.infrastructure.database.create_tables import create_all_tables; create_all_tables()"

REM 6. Start Redis (if installed)
where redis-server >nul 2>&1
if not errorlevel 1 (
    echo Starting Redis cache...
    start /B redis-server
)

REM 7. Start the API server
echo Starting API server...
echo Server will run on http://%HOST%:%PORT%
echo Logs will be saved to %LOG_FILE%
echo.

REM Start with uvicorn
start /B uvicorn unified_api_correct:app --host %HOST% --port %PORT% --workers %WORKERS% --log-level info >> %LOG_FILE% 2>&1

REM Wait for server to start
timeout /t 5 /nobreak >nul

REM 8. Check if server is running
curl -f http://localhost:%PORT%/monitoring/health >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Server failed to start. Check %LOG_FILE% for details
    exit /b 1
)

REM 9. Start monitoring
echo Starting monitoring service...
curl -X POST http://localhost:%PORT%/monitoring/start >nul 2>&1

echo.
echo %GREEN%Trading System Started Successfully!%NC%
echo.
echo Access URLs:
echo - API Documentation: http://localhost:%PORT%/docs
echo - Monitoring Dashboard: http://localhost:%PORT%/monitoring_dashboard.html
echo - Trading Dashboard: http://localhost:%PORT%/integrated_trading_dashboard.html
echo.
echo Commands:
echo - View logs: type %LOG_FILE%
echo - Stop server: Press Ctrl+C or run stop_production.bat
echo - Check status: curl http://localhost:%PORT%/monitoring/status
echo.

REM Keep the window open
pause

endlocal