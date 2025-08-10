@echo off
echo ============================================================
echo  STARTING BACKTEST API SERVER
echo ============================================================
echo.
echo Starting server on http://localhost:8000
echo.
echo Test URLs:
echo   http://localhost:8000/       - API status
echo   http://localhost:8000/docs   - Interactive documentation
echo.
echo Press Ctrl+C to stop the server
echo.
python unified_api_correct.py
pause