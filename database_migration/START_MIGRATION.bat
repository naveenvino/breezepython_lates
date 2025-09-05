@echo off
REM ==============================================
REM Database Migration Script
REM SQL Server to PostgreSQL + TimescaleDB
REM ==============================================

echo ================================================
echo DATABASE MIGRATION TOOL
echo SQL Server to PostgreSQL + TimescaleDB
echo ================================================
echo.

REM Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ first
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "..\venv" (
    echo Creating virtual environment...
    python -m venv ..\venv
)

REM Activate virtual environment
echo Activating virtual environment...
call ..\venv\Scripts\activate.bat

REM Install required packages
echo.
echo Installing required packages...
pip install -r requirements.txt

echo.
echo ================================================
echo PREREQUISITES CHECKLIST
echo ================================================
echo.
echo Please ensure you have:
echo [1] PostgreSQL 16 installed
echo [2] TimescaleDB extension downloaded
echo [3] Backed up your SQL Server database
echo [4] At least 10GB free disk space
echo.
echo Press Ctrl+C to cancel, or
pause

REM Run the migration
echo.
echo Starting migration...
python run_migration.py

REM Check if migration was successful
if errorlevel 1 (
    echo.
    echo ================================================
    echo MIGRATION FAILED
    echo ================================================
    echo Please check the log files for details
) else (
    echo.
    echo ================================================
    echo MIGRATION COMPLETED
    echo ================================================
    echo.
    echo Running verification...
    python verify_migration.py
)

echo.
pause