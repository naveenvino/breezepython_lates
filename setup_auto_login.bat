@echo off
echo ========================================
echo Auto-Login System Setup
echo ========================================
echo.

echo Installing required dependencies...
pip install selenium pyotp cryptography schedule pywin32 beautifulsoup4 pillow

echo.
echo Downloading ChromeDriver...
echo Please download ChromeDriver from: https://chromedriver.chromium.org/
echo Place it in the same directory as this script or add to PATH
echo.
pause

echo.
echo Running setup script...
python scripts\setup_auto_login.py

echo.
echo Setup complete!
echo.
echo To test auto-login:
echo 1. Start the API server: python unified_api_correct.py
echo 2. Visit http://localhost:8000/docs
echo 3. Use the Auto Login endpoints
echo.
pause