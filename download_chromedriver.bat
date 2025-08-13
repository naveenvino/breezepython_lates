@echo off
echo ========================================
echo ChromeDriver Download Helper
echo ========================================
echo.
echo Opening ChromeDriver download page...
echo.
echo INSTRUCTIONS:
echo 1. Your browser will open the ChromeDriver download page
echo 2. Download the version that matches your Chrome browser
echo 3. Extract chromedriver.exe to THIS folder: %cd%
echo.
echo To check your Chrome version:
echo - Open Chrome
echo - Go to: chrome://settings/help
echo - Note the version number (e.g., 131.x.x.x)
echo.
start https://googlechromelabs.github.io/chrome-for-testing/
echo.
pause