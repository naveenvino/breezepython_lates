@echo off
REM Smoke Test Script for Windows
REM Basic tests to verify deployment is working

setlocal enabledelayedexpansion

set BASE_URL=http://localhost:8000
set FAILED_TESTS=0
set PASSED_TESTS=0

REM Colors
set GREEN=[92m
set RED=[91m
set NC=[0m

echo Running smoke tests...
echo Target: %BASE_URL%
echo ================================

REM Test health endpoint
call :test_endpoint "/monitoring/health" "200" "Health endpoint"

REM Test API documentation
call :test_endpoint "/docs" "200" "API documentation"

REM Test monitoring endpoints
call :test_endpoint "/monitoring/status" "200" "Monitoring status"
call :test_endpoint "/monitoring/alerts" "200" "Alerts endpoint"

REM Test auth endpoints
call :test_endpoint "/auth/real-status" "200" "Auth status"

REM Test trading endpoints
call :test_endpoint "/live/market-data/NIFTY" "200" "Market data"
call :test_endpoint "/live/orders" "200" "Orders endpoint"
call :test_endpoint "/live/positions" "200" "Positions endpoint"

REM Test option chain
call :test_endpoint "/option-chain/config" "200" "Option chain config"

REM Test backtest endpoints
call :test_endpoint "/backtest-runs" "200" "Backtest runs"

echo ================================
echo Tests Passed: %GREEN%%PASSED_TESTS%%NC%
echo Tests Failed: %RED%%FAILED_TESTS%%NC%

if %FAILED_TESTS% gtr 0 (
    echo %RED%Some tests failed!%NC%
    exit /b 1
)

echo %GREEN%All smoke tests passed!%NC%
exit /b 0

:test_endpoint
set endpoint=%~1
set expected_status=%~2
set description=%~3

echo | set /p="Testing %description%... "

for /f %%i in ('curl -s -o nul -w "%%{http_code}" "%BASE_URL%%endpoint%"') do set status=%%i

if "%status%"=="%expected_status%" (
    echo %GREEN%PASS%NC%
    set /a PASSED_TESTS+=1
) else (
    echo %RED%FAIL%NC% ^(Expected: %expected_status%, Got: %status%^)
    set /a FAILED_TESTS+=1
)

goto :eof