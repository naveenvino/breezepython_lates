"""
ARCHIVED UNUSED ENDPOINTS
These endpoints were removed from unified_api_correct.py because they are not used by the UI.
Archived on: 2025-09-08

UNUSED ENDPOINTS:
- Data Collection endpoints (/collect/*)
- Data Deletion endpoints (/delete/*)
- Holiday Management endpoints (/api/v1/holidays/*)
- ML validation endpoints (if any)

These can be restored if needed by copying back to unified_api_correct.py
"""

from fastapi import FastAPI, HTTPException, Request, Query, Path
from fastapi.responses import JSONResponse
from datetime import datetime, date
import json
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

# ==================== ARCHIVED DATA COLLECTION ENDPOINTS ====================

@app.post("/collect/nifty-direct", tags=["ARCHIVED - NIFTY Collection"])
async def collect_nifty_direct_archived(request: Request):
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.post("/collect/nifty-bulk", tags=["ARCHIVED - NIFTY Collection"])
async def collect_nifty_bulk_archived(request: Request):
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.post("/collect/options-direct", tags=["ARCHIVED - Options Collection"])
async def collect_options_direct_archived(request: Request):
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.post("/collect/options-bulk", tags=["ARCHIVED - Options Collection"])
async def collect_options_bulk_archived(request: Request):
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.post("/collect/options-specific", tags=["ARCHIVED - Options Collection"])
async def collect_options_specific_archived(request: Request):
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.post("/collect/missing-from-insights", tags=["ARCHIVED - Options Collection"])
async def collect_missing_from_insights_archived(request: Request):
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.post("/collect/tradingview", tags=["ARCHIVED - TradingView Collection"])
async def collect_tradingview_archived(request: Request):
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.post("/collect/tradingview-bulk", tags=["ARCHIVED - TradingView Collection"])
async def collect_tradingview_bulk_archived(request: Request):
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

# ==================== ARCHIVED DATA DELETION ENDPOINTS ====================

@app.delete("/delete/nifty-direct", tags=["ARCHIVED - Data Deletion"])
async def delete_nifty_direct_archived():
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.delete("/delete/options-direct", tags=["ARCHIVED - Data Deletion"])
async def delete_options_direct_archived():
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.delete("/delete/all", tags=["ARCHIVED - Data Deletion"])
async def delete_all_data_archived():
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

# ==================== ARCHIVED HOLIDAY MANAGEMENT ENDPOINTS ====================

@app.get("/api/v1/holidays/{year}", tags=["ARCHIVED - Holiday Management"])
async def get_holidays_archived(year: int = Path(...)):
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.post("/api/v1/holidays/load-defaults", tags=["ARCHIVED - Holiday Management"])
async def load_default_holidays_archived():
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.get("/api/v1/holidays/check/{date}", tags=["ARCHIVED - Holiday Management"])
async def check_holiday_archived(date: str = Path(...)):
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.get("/api/v1/holidays/trading-days", tags=["ARCHIVED - Holiday Management"])
async def get_trading_days_archived():
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.post("/api/v1/holidays/load-all-defaults", tags=["ARCHIVED - Holiday Management"])
async def load_all_default_holidays_archived():
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})

@app.post("/api/v1/holidays/fetch-from-nse", tags=["ARCHIVED - Holiday Management"])
async def fetch_holidays_from_nse_archived():
    """ARCHIVED - Not used by UI"""
    return JSONResponse(content={"status": "archived", "message": "This endpoint is archived"})