"""
Data Collection Router
API endpoints for data collection operations
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import date, datetime
from typing import Optional, List

from ...application.dto.requests import (
    CollectWeeklyDataRequest,
    CollectOptionChainRequest,
    CollectHistoricalDataRequest,
    CollectNiftyDataRequest
)
from ...application.dto.responses import BaseResponse
from ...application.use_cases import CollectWeeklyDataUseCase, FetchOptionChainUseCase
from ...infrastructure.di.container import get_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/collect/weekly", response_model=BaseResponse)
async def collect_weekly_data(
    request: CollectWeeklyDataRequest,
    use_case: CollectWeeklyDataUseCase = Depends(lambda: get_service(CollectWeeklyDataUseCase))
):
    """
    Collect weekly options data
    
    - **from_date**: Start date for collection
    - **to_date**: End date for collection
    - **symbol**: Underlying symbol (default: NIFTY)
    - **strike_range**: Strike range from spot price
    - **use_parallel**: Use parallel processing
    """
    try:
        logger.info(f"Collecting weekly data from {request.from_date} to {request.to_date}")
        result = await use_case.execute(request)
        return result
    except Exception as e:
        logger.error(f"Error collecting weekly data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collect/option-chain", response_model=BaseResponse)
async def collect_option_chain(
    request: CollectOptionChainRequest,
    use_case: FetchOptionChainUseCase = Depends(lambda: get_service(FetchOptionChainUseCase))
):
    """
    Collect current option chain data
    
    - **symbol**: Underlying symbol
    - **expiry_date**: Option expiry date (optional, defaults to current)
    - **save_to_db**: Save to database
    """
    try:
        logger.info(f"Collecting option chain for {request.symbol}")
        result = await use_case.execute(request)
        return result
    except Exception as e:
        logger.error(f"Error collecting option chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_data_collection_status():
    """Get current data collection status"""
    return {
        "status": "ready",
        "last_collection": None,
        "active_jobs": 0
    }


@router.get("/available-symbols")
async def get_available_symbols():
    """Get list of available symbols for data collection"""
    return {
        "symbols": ["NIFTY", "BANKNIFTY", "FINNIFTY"],
        "exchanges": ["NSE", "NFO"]
    }


@router.get("/available-expiries")
async def get_available_expiries(
    symbol: str = Query(default="NIFTY", description="Underlying symbol")
):
    """Get available expiry dates for a symbol"""
    # This would query the actual available expiries
    # For now, return sample data
    from datetime import timedelta
    today = date.today()
    
    # Calculate next few Thursday expiries
    expiries = []
    current = today
    
    for _ in range(5):
        # Find next Thursday
        days_until_thursday = (3 - current.weekday()) % 7
        if days_until_thursday == 0 and current == today:
            # If today is Thursday and market is closed, skip to next week
            days_until_thursday = 7
        
        expiry = current + timedelta(days=days_until_thursday)
        expiries.append(expiry.isoformat())
        current = expiry + timedelta(days=1)
    
    return {
        "symbol": symbol,
        "expiries": expiries
    }


@router.post("/collect/nifty", response_model=BaseResponse)
async def collect_nifty_data(
    request: CollectNiftyDataRequest
):
    """
    Collect historical NIFTY index data
    
    - **from_date**: Start date for collection
    - **to_date**: End date for collection  
    - **symbol**: Index symbol (default: NIFTY)
    - **force_refresh**: Force refresh existing data
    
    This endpoint:
    - Fetches 5-minute data from 9:20 to 15:25
    - Automatically creates hourly candles with correct aggregation
    - 9:15 candle uses 9:20-10:20 data, 10:15 uses 10:20-11:20, etc.
    """
    try:
        from ...infrastructure.services.data_collection_service import DataCollectionService
        from ...infrastructure.services.breeze_service import BreezeService
        from ...infrastructure.database import get_db_manager
        
        logger.info(f"Collecting NIFTY data from {request.from_date} to {request.to_date}")
        
        # Initialize services
        breeze_service = BreezeService()
        data_service = DataCollectionService(breeze_service)
        
        # Convert dates to datetime
        from_datetime = datetime.combine(request.from_date, datetime.min.time())
        to_datetime = datetime.combine(request.to_date, datetime.max.time())
        
        # Collect data
        records_added = await data_service.ensure_nifty_data_available(
            from_date=from_datetime,
            to_date=to_datetime,
            symbol=request.symbol
        )
        
        # Get additional statistics
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            from ...infrastructure.database.models import NiftyIndexData
            from sqlalchemy import and_
            
            five_min_count = session.query(NiftyIndexData).filter(
                and_(
                    NiftyIndexData.symbol == request.symbol,
                    NiftyIndexData.interval == "5minute",
                    NiftyIndexData.timestamp >= from_datetime,
                    NiftyIndexData.timestamp <= to_datetime
                )
            ).count()
            
            hourly_count = session.query(NiftyIndexData).filter(
                and_(
                    NiftyIndexData.symbol == request.symbol,
                    NiftyIndexData.interval == "hourly",
                    NiftyIndexData.timestamp >= from_datetime,
                    NiftyIndexData.timestamp <= to_datetime
                )
            ).count()
        
        return BaseResponse(
            status="SUCCESS",
            message=f"Successfully collected data for {request.symbol}",
            data={
                "symbol": request.symbol,
                "from_date": request.from_date.isoformat(),
                "to_date": request.to_date.isoformat(),
                "records_added": {
                    "total": records_added,
                    "five_minute": five_min_count,
                    "hourly": hourly_count
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error collecting NIFTY historical data: {e}")
        raise HTTPException(status_code=500, detail=str(e))