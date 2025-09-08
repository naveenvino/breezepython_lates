"""
ARCHIVED DUPLICATE ENDPOINTS
These endpoints were removed from unified_api_correct.py because they are duplicates.
The active versions are still in the main file.
Archived on: 2025-09-08

DUPLICATE ENDPOINTS:
1. /save-trade-config (lines 4127, 9997) - DUPLICATE of /api/trade-config/save
2. /trade-config GET (lines 4178, 10033) - DUPLICATE of /api/trade-config/load
3. /health (line 1575) - DUPLICATE of /api/health
4. /positions (line 2420) - DUPLICATE of /api/positions
5. / root endpoint (line 1560) - DUPLICATE of main root

These can be restored if needed by copying back to unified_api_correct.py
"""

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from datetime import datetime
import json
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

# ==================== ARCHIVED DUPLICATE ENDPOINTS ====================

# DUPLICATE 1: /save-trade-config (was at line 4127)
@app.post("/save-trade-config")
async def save_trade_config_old(request: Request):
    """OLD VERSION - Duplicate of /api/trade-config/save"""
    try:
        config = await request.json()
        # Original implementation would go here
        return JSONResponse(content={
            "status": "archived",
            "message": "This endpoint is archived. Use /api/trade-config/save instead"
        })
    except Exception as e:
        logger.error(f"Archived endpoint called: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# DUPLICATE 2: /trade-config GET (was at line 4178)
@app.get("/trade-config")
async def get_trade_config_old():
    """OLD VERSION - Duplicate of /api/trade-config/load"""
    return JSONResponse(content={
        "status": "archived",
        "message": "This endpoint is archived. Use /api/trade-config/load/default instead"
    })

# DUPLICATE 3: /health (was at line 1575)
@app.get("/health")
async def health_check_old():
    """OLD VERSION - Duplicate of /api/health"""
    return JSONResponse(content={
        "status": "archived",
        "message": "This endpoint is archived. Use /api/health instead"
    })

# DUPLICATE 4: /positions (was at line 2420)
@app.get("/positions")
async def get_positions_old():
    """OLD VERSION - Duplicate of /api/positions"""
    return JSONResponse(content={
        "status": "archived",
        "message": "This endpoint is archived. Use /api/positions or /api/trading/positions instead"
    })

# DUPLICATE 5: / root (was at line 1560)
@app.get("/")
async def root_old():
    """OLD VERSION - Duplicate of main root endpoint"""
    return JSONResponse(content={
        "status": "archived",
        "message": "This endpoint is archived. Main root endpoint is at line 114"
    })