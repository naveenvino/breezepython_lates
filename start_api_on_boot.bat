@echo off
:: Start API on Windows boot
:: This file should be added to Windows Task Scheduler

cd /d "C:\Users\E1791\Kitepy\breezepython"

:: Activate virtual environment
call .venv\Scripts\activate.bat

:: Start the unified API in background
start /min python unified_api_correct.py

:: Log the startup
echo API started at %date% %time% >> startup_log.txt

exit