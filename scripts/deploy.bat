@echo off
REM Production Deployment Script for Windows
REM Usage: deploy.bat [environment]

setlocal enabledelayedexpansion

REM Configuration
set ENVIRONMENT=%1
if "%ENVIRONMENT%"=="" set ENVIRONMENT=production
set APP_NAME=trading-system
set BACKUP_DIR=.\backups
set LOG_FILE=.\logs\deployment.log

REM Colors (Windows 10+)
set GREEN=[92m
set RED=[91m
set YELLOW=[93m
set NC=[0m

REM Create necessary directories
if not exist logs mkdir logs
if not exist backups mkdir backups
if not exist data mkdir data

echo %GREEN%[%date% %time%]%NC% Starting deployment for environment: %ENVIRONMENT% >> %LOG_FILE%
echo Starting deployment for environment: %ENVIRONMENT%

REM 1. Check prerequisites
echo Checking prerequisites...
docker --version >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Docker is not installed
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Docker Compose is not installed
    exit /b 1
)

REM 2. Backup current deployment
if exist data (
    echo Creating backup...
    set BACKUP_FILE=%BACKUP_DIR%\backup_%date:~-4%%date:~4,2%%date:~7,2%_%time:~0,2%%time:~3,2%%time:~6,2%.zip
    powershell -command "Compress-Archive -Path data,logs,.env -DestinationPath !BACKUP_FILE! -Force" 2>nul
    echo Backup created: !BACKUP_FILE!
)

REM 3. Load environment configuration
if not exist .env (
    if exist .env.%ENVIRONMENT% (
        echo Copying environment configuration...
        copy .env.%ENVIRONMENT% .env
    ) else (
        echo %RED%[ERROR]%NC% Environment configuration not found: .env.%ENVIRONMENT%
        exit /b 1
    )
)

REM 4. Validate configuration
echo Validating configuration...
findstr /C:"DB_SERVER=" .env >nul || echo %YELLOW%[WARNING]%NC% Missing required variable: DB_SERVER
findstr /C:"DB_NAME=" .env >nul || echo %YELLOW%[WARNING]%NC% Missing required variable: DB_NAME
findstr /C:"BREEZE_API_KEY=" .env >nul || echo %YELLOW%[WARNING]%NC% Missing required variable: BREEZE_API_KEY
findstr /C:"JWT_SECRET_KEY=" .env >nul || echo %YELLOW%[WARNING]%NC% Missing required variable: JWT_SECRET_KEY

REM 5. Build Docker images
echo Building Docker images...
docker-compose build --no-cache
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Docker build failed
    exit /b 1
)

REM 6. Run database migrations
echo Running database migrations...
docker-compose run --rm trading-api python -m src.infrastructure.database.create_tables

REM 7. Stop existing containers
echo Stopping existing containers...
docker-compose down

REM 8. Start new containers
echo Starting new containers...
docker-compose up -d
if errorlevel 1 (
    echo %RED%[ERROR]%NC% Failed to start containers
    exit /b 1
)

REM 9. Wait for services to be healthy
echo Waiting for services to be healthy...
timeout /t 10 /nobreak >nul

REM Check health status
set max_attempts=30
set attempt=0

:health_check
curl -f http://localhost:8000/monitoring/health >nul 2>&1
if not errorlevel 1 (
    echo Services are healthy
    goto :health_check_done
)

set /a attempt+=1
if %attempt% geq %max_attempts% (
    echo %RED%[ERROR]%NC% Services failed to become healthy
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto :health_check

:health_check_done

REM 10. Run smoke tests
echo Running smoke tests...
call scripts\smoke_test.bat

REM 11. Setup monitoring
echo Starting monitoring service...
curl -X POST http://localhost:8000/monitoring/start

REM 12. Cleanup old backups (keep last 30 days)
echo Cleaning up old backups...
forfiles /p "%BACKUP_DIR%" /m "backup_*.zip" /d -30 /c "cmd /c del @path" 2>nul

echo.
echo %GREEN%Deployment completed successfully!%NC%

REM Display service status
echo.
echo %GREEN%Service Status:%NC%
docker-compose ps

echo.
echo %GREEN%Access URLs:%NC%
echo API Documentation: http://localhost:8000/docs
echo Monitoring Dashboard: http://localhost:8000/monitoring_dashboard.html
echo Trading Dashboard: http://localhost:8000/integrated_trading_dashboard.html

echo.
echo %GREEN%Next Steps:%NC%
echo 1. Verify all services are running: docker-compose ps
echo 2. Check logs: docker-compose logs -f
echo 3. Monitor system health: http://localhost:8000/monitoring/status
echo 4. Configure alerts in .env file

echo.
echo Deployment log saved to: %LOG_FILE%

endlocal