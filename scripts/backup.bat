@echo off
REM Backup Script for Trading System (Windows)
REM Creates timestamped backups of data, logs, and configuration

setlocal enabledelayedexpansion

REM Configuration
set BACKUP_DIR=.\backups
set RETENTION_DAYS=30
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,8%_%datetime:~8,6%
set BACKUP_NAME=trading_backup_%TIMESTAMP%

REM Colors
set GREEN=[92m
set RED=[91m
set YELLOW=[93m
set NC=[0m

REM Create backup directory
if not exist %BACKUP_DIR% mkdir %BACKUP_DIR%

echo %GREEN%[%date% %time%]%NC% Starting backup process...

REM 1. Create temporary backup directory
set TEMP_BACKUP_DIR=%TEMP%\%BACKUP_NAME%
mkdir "%TEMP_BACKUP_DIR%"

REM 2. Backup database
echo Backing up database...
sqlcmd -S "(localdb)\mssqllocaldb" -d "KiteConnectApi" -Q "BACKUP DATABASE [KiteConnectApi] TO DISK='%TEMP_BACKUP_DIR%\database.bak'" 2>nul
if errorlevel 1 echo %YELLOW%[WARNING]%NC% Database backup failed

REM 3. Backup application data
echo Backing up application data...
if exist data xcopy /E /I /Q data "%TEMP_BACKUP_DIR%\data" >nul
if exist logs xcopy /E /I /Q logs "%TEMP_BACKUP_DIR%\logs" >nul
if exist static xcopy /E /I /Q static "%TEMP_BACKUP_DIR%\static" >nul

REM 4. Backup configuration files
echo Backing up configuration files...
if exist .env copy .env "%TEMP_BACKUP_DIR%\" >nul
if exist requirements-prod.txt copy requirements-prod.txt "%TEMP_BACKUP_DIR%\" >nul
if exist docker-compose.yml copy docker-compose.yml "%TEMP_BACKUP_DIR%\" >nul
if exist nginx.conf copy nginx.conf "%TEMP_BACKUP_DIR%\" >nul

REM 5. Create system info file
echo Creating system info...
(
echo Backup Information
echo ==================
echo Date: %date% %time%
echo Computer: %COMPUTERNAME%
echo User: %USERNAME%
echo.
echo Backup Contents:
dir "%TEMP_BACKUP_DIR%" /B
) > "%TEMP_BACKUP_DIR%\backup_info.txt"

REM 6. Compress backup
echo Compressing backup...
set BACKUP_FILE=%BACKUP_DIR%\%BACKUP_NAME%.zip
powershell -command "Compress-Archive -Path '%TEMP_BACKUP_DIR%\*' -DestinationPath '%BACKUP_FILE%' -Force"

if not exist "%BACKUP_FILE%" (
    echo %RED%[ERROR]%NC% Failed to create backup archive
    exit /b 1
)

REM 7. Calculate backup size
for %%A in ("%BACKUP_FILE%") do set SIZE=%%~zA
set /a SIZE_MB=%SIZE% / 1048576
echo Backup size: %SIZE_MB% MB

REM 8. Cleanup temporary files
rmdir /S /Q "%TEMP_BACKUP_DIR%"

REM 9. Remove old backups
echo Cleaning up old backups ^(keeping last %RETENTION_DAYS% days^)...
forfiles /p "%BACKUP_DIR%" /m "trading_backup_*.zip" /d -%RETENTION_DAYS% /c "cmd /c del @path" 2>nul

REM 10. List recent backups
echo Recent backups:
dir %BACKUP_DIR%\trading_backup_*.zip /B /O-D 2>nul | head -5

echo.
echo %GREEN%Backup completed: %BACKUP_FILE%%NC%

REM Optional: Upload to cloud storage
if defined AWS_S3_BUCKET (
    echo Uploading to S3...
    aws s3 cp "%BACKUP_FILE%" "s3://%AWS_S3_BUCKET%/backups/"
)

if defined AZURE_STORAGE_CONTAINER (
    echo Uploading to Azure...
    az storage blob upload --container-name "%AZURE_STORAGE_CONTAINER%" --file "%BACKUP_FILE%" --name "backups/%BACKUP_NAME%.zip"
)

echo %GREEN%Backup process completed successfully!%NC%

endlocal