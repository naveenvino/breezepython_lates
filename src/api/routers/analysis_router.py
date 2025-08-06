"""
Data Analysis Router
API endpoints for data analysis operations
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import date
from typing import Optional

from ...application.dto.requests import (
    AnalyzeDataAvailabilityRequest,
    AnalyzeOptionChainRequest,
    GetDataCalendarRequest
)
from ...application.dto.responses import BaseResponse
from ...application.use_cases import AnalyzeDataAvailabilityUseCase, AnalyzeOptionChainUseCase
from ...infrastructure.di.container import get_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/data-availability", response_model=BaseResponse)
async def analyze_data_availability(
    request: AnalyzeDataAvailabilityRequest,
    use_case: AnalyzeDataAvailabilityUseCase = Depends(lambda: get_service(AnalyzeDataAvailabilityUseCase))
):
    """
    Analyze data availability and identify gaps
    
    - **from_date**: Start date for analysis
    - **to_date**: End date for analysis
    - **symbol**: Specific symbol to analyze
    - **data_type**: Type of data (all/nifty/options)
    - **include_gaps**: Include detailed gap analysis
    """
    try:
        logger.info(f"Analyzing data availability for {request.data_type}")
        result = await use_case.execute(request)
        return result
    except Exception as e:
        logger.error(f"Error analyzing data availability: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/option-chain-analysis", response_model=BaseResponse)
async def analyze_option_chain(
    request: AnalyzeOptionChainRequest,
    use_case: AnalyzeOptionChainUseCase = Depends(lambda: get_service(AnalyzeOptionChainUseCase))
):
    """
    Analyze option chain for support/resistance and Greeks
    
    - **symbol**: Underlying symbol
    - **expiry_date**: Option expiry date
    - **spot_price**: Current spot price (optional)
    - **include_greeks**: Calculate and include Greeks
    - **strike_range**: Analyze strikes within range
    """
    try:
        logger.info(f"Analyzing option chain for {request.symbol}")
        result = await use_case.execute(request)
        return result
    except Exception as e:
        logger.error(f"Error analyzing option chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-summary")
async def get_market_summary(
    symbol: str = Query(default="NIFTY", description="Symbol to analyze"),
    days: int = Query(default=30, description="Number of days to analyze")
):
    """Get market summary and statistics"""
    # This would calculate actual market statistics
    # For now, return sample data
    return {
        "symbol": symbol,
        "period_days": days,
        "statistics": {
            "average_price": 23500,
            "high": 24000,
            "low": 23000,
            "volatility": 0.15,
            "trend": "bullish",
            "support_levels": [23200, 23000, 22800],
            "resistance_levels": [23700, 23900, 24100]
        }
    }


@router.get("/volatility-analysis")
async def analyze_volatility(
    symbol: str = Query(default="NIFTY", description="Symbol to analyze"),
    period: int = Query(default=20, description="Period for volatility calculation"),
    from_date: Optional[date] = None,
    to_date: Optional[date] = None
):
    """Analyze historical and implied volatility"""
    return {
        "symbol": symbol,
        "period": period,
        "historical_volatility": {
            "daily": 0.012,
            "annualized": 0.19,
            "trend": "decreasing"
        },
        "implied_volatility": {
            "atm_iv": 0.16,
            "iv_skew": "negative",
            "term_structure": "normal"
        }
    }


@router.get("/correlation-matrix")
async def get_correlation_matrix(
    symbols: str = Query(default="NIFTY,BANKNIFTY", description="Comma-separated symbols"),
    period: int = Query(default=30, description="Period in days")
):
    """Get correlation matrix for multiple symbols"""
    symbol_list = symbols.split(",")
    
    # Sample correlation matrix
    correlations = {}
    for i, sym1 in enumerate(symbol_list):
        correlations[sym1] = {}
        for j, sym2 in enumerate(symbol_list):
            if i == j:
                correlations[sym1][sym2] = 1.0
            else:
                correlations[sym1][sym2] = 0.75  # Sample correlation
    
    return {
        "symbols": symbol_list,
        "period_days": period,
        "correlation_matrix": correlations
    }


@router.get("/data-availability")
async def get_data_availability(
    from_date: date = Query(..., description="Start date"),
    to_date: date = Query(..., description="End date"),
    symbol: str = Query(default="NIFTY", description="Symbol to check")
):
    """
    Check data availability for a date range
    
    Shows:
    - Total 5-minute records (expected: 74 per day)
    - Total hourly records (expected: 7 per day)
    - Daily breakdown
    """
    from ...infrastructure.database.database_manager import get_db_manager
    from ...infrastructure.database.models import NiftyIndexData
    from sqlalchemy import and_, func
    from datetime import datetime, timedelta
    
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        # Convert dates to datetime
        from_datetime = datetime.combine(from_date, datetime.min.time())
        to_datetime = datetime.combine(to_date, datetime.max.time())
        
        # Get counts
        five_min_count = session.query(NiftyIndexData).filter(
            and_(
                NiftyIndexData.symbol == symbol,
                NiftyIndexData.interval == "5minute",
                NiftyIndexData.timestamp >= from_datetime,
                NiftyIndexData.timestamp <= to_datetime
            )
        ).count()
        
        hourly_count = session.query(NiftyIndexData).filter(
            and_(
                NiftyIndexData.symbol == symbol,
                NiftyIndexData.interval == "hourly",
                NiftyIndexData.timestamp >= from_datetime,
                NiftyIndexData.timestamp <= to_datetime
            )
        ).count()
        
        # Get daily breakdown
        daily_breakdown = []
        current_date = from_date
        
        while current_date <= to_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date, datetime.max.time())
            
            day_5min = session.query(NiftyIndexData).filter(
                and_(
                    NiftyIndexData.symbol == symbol,
                    NiftyIndexData.interval == "5minute",
                    NiftyIndexData.timestamp >= day_start,
                    NiftyIndexData.timestamp <= day_end
                )
            ).count()
            
            day_hourly = session.query(NiftyIndexData).filter(
                and_(
                    NiftyIndexData.symbol == symbol,
                    NiftyIndexData.interval == "hourly",
                    NiftyIndexData.timestamp >= day_start,
                    NiftyIndexData.timestamp <= day_end
                )
            ).count()
            
            if day_5min > 0 or day_hourly > 0:
                daily_breakdown.append({
                    "date": current_date.isoformat(),
                    "five_minute_count": day_5min,
                    "hourly_count": day_hourly,
                    "is_complete": day_5min == 74 and day_hourly == 7
                })
            
            current_date += timedelta(days=1)
    
    # Calculate expected counts
    total_days = (to_date - from_date).days + 1
    weekdays = sum(1 for i in range(total_days) 
                   if (from_date + timedelta(days=i)).weekday() < 5)
    
    return {
        "summary": {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "symbol": symbol,
            "total_days": total_days,
            "trading_days": weekdays,
            "five_minute_records": five_min_count,
            "hourly_records": hourly_count,
            "expected_five_minute": weekdays * 74,
            "expected_hourly": weekdays * 7,
            "data_completeness": f"{(five_min_count / (weekdays * 74) * 100):.1f}%" if weekdays > 0 else "0%"
        },
        "daily_breakdown": daily_breakdown
    }


@router.get("/hourly-candles")
async def get_hourly_candles(
    date: date = Query(..., description="Date to get hourly candles for"),
    symbol: str = Query(default="NIFTY", description="Symbol")
):
    """
    Get hourly candles for a specific date
    
    Returns all 7 hourly candles with OHLC data
    """
    from ...infrastructure.database.database_manager import get_db_manager
    from ...infrastructure.database.models import NiftyIndexData
    from sqlalchemy import and_
    from datetime import datetime
    
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        # Convert date to datetime range
        day_start = datetime.combine(date, datetime.min.time())
        day_end = datetime.combine(date, datetime.max.time())
        
        # Get hourly candles
        hourly_candles = session.query(NiftyIndexData).filter(
            and_(
                NiftyIndexData.symbol == symbol,
                NiftyIndexData.interval == "hourly",
                NiftyIndexData.timestamp >= day_start,
                NiftyIndexData.timestamp <= day_end
            )
        ).order_by(NiftyIndexData.timestamp).all()
        
        candles = []
        for candle in hourly_candles:
            candles.append({
                "time": candle.timestamp.strftime("%H:%M"),
                "timestamp": candle.timestamp.isoformat(),
                "open": float(candle.open),
                "high": float(candle.high),
                "low": float(candle.low),
                "close": float(candle.close),
                "volume": candle.volume
            })
        
        # Get 5-minute data count for verification
        five_min_count = session.query(NiftyIndexData).filter(
            and_(
                NiftyIndexData.symbol == symbol,
                NiftyIndexData.interval == "5minute",
                NiftyIndexData.timestamp >= day_start,
                NiftyIndexData.timestamp <= day_end
            )
        ).count()
        
    return {
        "date": date.isoformat(),
        "symbol": symbol,
        "hourly_candles": candles,
        "candle_count": len(candles),
        "five_minute_data_count": five_min_count,
        "data_complete": len(candles) == 7 and five_min_count == 74
    }