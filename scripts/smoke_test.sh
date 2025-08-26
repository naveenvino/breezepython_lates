#!/bin/bash

# Smoke Test Script
# Basic tests to verify deployment is working

set -e

BASE_URL=${BASE_URL:-http://localhost:8000}
FAILED_TESTS=0
PASSED_TESTS=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Test function
test_endpoint() {
    local endpoint=$1
    local expected_status=$2
    local description=$3
    
    echo -n "Testing $description... "
    
    status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$endpoint")
    
    if [ "$status" = "$expected_status" ]; then
        echo -e "${GREEN}PASS${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}FAIL${NC} (Expected: $expected_status, Got: $status)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "Running smoke tests..."
echo "Target: $BASE_URL"
echo "================================"

# Health checks
test_endpoint "/monitoring/health" "200" "Health endpoint"
test_endpoint "/docs" "200" "API documentation"

# Monitoring endpoints
test_endpoint "/monitoring/status" "200" "Monitoring status"
test_endpoint "/monitoring/alerts" "200" "Alerts endpoint"

# Auth endpoints
test_endpoint "/auth/real-status" "200" "Auth status"

# Trading endpoints
test_endpoint "/live/market-data/NIFTY" "200" "Market data"
test_endpoint "/live/orders" "200" "Orders endpoint"
test_endpoint "/live/positions" "200" "Positions endpoint"

# Option chain
test_endpoint "/option-chain/config" "200" "Option chain config"

# Backtest endpoints
test_endpoint "/backtest-runs" "200" "Backtest runs"

echo "================================"
echo -e "Tests Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Tests Failed: ${RED}$FAILED_TESTS${NC}"

if [ $FAILED_TESTS -gt 0 ]; then
    exit 1
fi

echo -e "${GREEN}All smoke tests passed!${NC}"
exit 0