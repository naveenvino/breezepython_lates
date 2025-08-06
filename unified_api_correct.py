from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
import uvicorn
import asyncio
import logging
from uuid import uuid4
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.infrastructure.database.database_manager import get_db_manager
from src.infrastructure.services.breeze_service import BreezeService
from src.infrastructure.services.data_collection_service import DataCollectionService
from src.infrastructure.services.option_pricing_service import OptionPricingService
from src.infrastructure.services.holiday_service import HolidayService
from src.application.use_cases.run_backtest import RunBacktestUseCase, BacktestParameters
from src.application.use_cases.collect_weekly_data_use_case import CollectWeeklyDataUseCase
from src.infrastructure.database.models import BacktestRun, BacktestTrade, BacktestPosition
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Unified Trading API - All Original Features",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

job_status = {}

class BacktestRequest(BaseModel):
    from_date: date = date(2025, 7, 14)
    to_date: date = date(2025, 7, 14)
    initial_capital: float = 500000
    lot_size: int = 75
    lots_to_trade: int = 10
    signals_to_test: List[str] = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
    use_hedging: bool = True
    hedge_offset: int = 200
    commission_per_lot: float = 40
    slippage_percent: float = 0.001

class NiftyCollectionRequest(BaseModel):
    from_date: date
    to_date: date
    symbol: str = "NIFTY"
    force_refresh: bool = False

class OptionsCollectionRequest(BaseModel):
    from_date: date
    to_date: date
    symbol: str = "NIFTY"
    strike_range: int = 1000
    use_optimization: bool = True
    strike_interval: int = 100  # Added strike interval parameter

class TradingViewRequest(BaseModel):
    from_date: date
    to_date: date
    symbol: str = "NIFTY"
    interval: str = "5minute"

class WeeklyDataRequest(BaseModel):
    from_date: date
    to_date: date
    symbol: str = "NIFTY"
    strike_range: int = 1000

class SpecificOptionsRequest(BaseModel):
    from_date: date
    to_date: date
    strikes: List[int]
    option_types: List[str] = ["CE", "PE"]
    symbol: str = "NIFTY"

@app.post("/backtest", tags=["Backtest"])
async def run_backtest(request: BacktestRequest):
    """Run Backtest"""
    try:
        db = get_db_manager()
        breeze = BreezeService()
        data_svc = DataCollectionService(breeze, db)
        option_svc = OptionPricingService(data_svc, db)
        backtest = RunBacktestUseCase(data_svc, option_svc)
        
        from_datetime = datetime.combine(request.from_date, datetime.strptime("09:15", "%H:%M").time())
        to_datetime = datetime.combine(request.to_date, datetime.strptime("15:30", "%H:%M").time())
        
        params = BacktestParameters(
            from_date=from_datetime,
            to_date=to_datetime,
            initial_capital=request.initial_capital,
            lot_size=request.lot_size,
            lots_to_trade=request.lots_to_trade,
            signals_to_test=request.signals_to_test,
            use_hedging=request.use_hedging,
            hedge_offset=request.hedge_offset,
            commission_per_lot=request.commission_per_lot,
            slippage_percent=request.slippage_percent
        )
        
        backtest_id = await backtest.execute(params)
        
        with db.get_session() as session:
            run = session.query(BacktestRun).filter_by(id=backtest_id).first()
            trades = session.query(BacktestTrade).filter_by(backtest_run_id=backtest_id).all()
            
            trade_results = []
            for trade in trades:
                positions = session.query(BacktestPosition).filter_by(trade_id=trade.id).all()
                position_data = []
                for pos in positions:
                    position_data.append({
                        "type": pos.position_type,
                        "action": "SELL" if pos.quantity < 0 else "BUY",
                        "quantity": abs(pos.quantity),
                        "strike": pos.strike_price,
                        "option_type": pos.option_type,
                        "entry_price": float(pos.entry_price),
                        "exit_price": float(pos.exit_price) if pos.exit_price else None,
                        "pnl": float(pos.net_pnl) if pos.net_pnl else None
                    })
                
                # Convert bias from numeric to text
                bias_text = "UNKNOWN"
                if trade.bias_direction:
                    if str(trade.bias_direction) == "1":
                        bias_text = "BULL"
                    elif str(trade.bias_direction) == "-1":
                        bias_text = "BEAR"
                    elif str(trade.bias_direction) == "0":
                        bias_text = "NEUTRAL"
                
                # Fix direction mapping - Direction is stored as string in DB
                direction_text = "UNKNOWN"
                if trade.direction:
                    if str(trade.direction).strip() == "1":
                        direction_text = "BULLISH"
                    elif str(trade.direction).strip() == "-1":
                        direction_text = "BEARISH"
                
                trade_results.append({
                    "signal_type": trade.signal_type,
                    "entry_time": trade.entry_time,
                    "exit_time": trade.exit_time,
                    "stop_loss": float(trade.stop_loss_price),
                    "direction": direction_text,
                    "bias": bias_text,
                    "entry_spot_price": float(trade.index_price_at_entry) if trade.index_price_at_entry else None,
                    "exit_spot_price": float(trade.index_price_at_exit) if trade.index_price_at_exit else None,
                    "outcome": trade.outcome.value,
                    "total_pnl": float(trade.total_pnl) if trade.total_pnl else 0,
                    "positions": position_data
                })
            
            return {
                "status": "success",
                "backtest_id": backtest_id,
                "summary": {
                    "total_trades": run.total_trades,
                    "final_capital": float(run.final_capital),
                    "total_pnl": float(run.total_pnl) if run.total_pnl else 0,
                    "win_rate": (run.winning_trades / run.total_trades * 100) if run.total_trades > 0 else 0,
                    "lot_size": run.lot_size,
                    "hedge_offset": run.hedge_offset
                },
                "trades": trade_results
            }
    except Exception as e:
        logger.error(f"Backtest error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/backtest", tags=["Backtest"])
async def run_backtest_get(
    from_date: date = Query(default=date(2025, 7, 14)),
    to_date: date = Query(default=date(2025, 7, 14)),
    initial_capital: float = Query(default=500000),
    lot_size: int = Query(default=75),
    lots_to_trade: int = Query(default=10),
    signals_to_test: str = Query(default="S1,S2,S3,S4,S5,S6,S7,S8"),
    use_hedging: bool = Query(default=True),
    hedge_offset: int = Query(default=200),
    commission_per_lot: float = Query(default=40)
):
    """Run Backtest Get"""
    request = BacktestRequest(
        from_date=from_date,
        to_date=to_date,
        initial_capital=initial_capital,
        lot_size=lot_size,
        lots_to_trade=lots_to_trade,
        signals_to_test=signals_to_test.split(","),
        use_hedging=use_hedging,
        hedge_offset=hedge_offset,
        commission_per_lot=commission_per_lot
    )
    return await run_backtest(request)

@app.post("/collect/nifty-direct", tags=["NIFTY Collection"])
async def collect_nifty_direct(request: NiftyCollectionRequest):
    """Collect Nifty Direct"""
    try:
        db = get_db_manager()
        breeze = BreezeService()
        data_svc = DataCollectionService(breeze, db)
        
        result = await data_svc.collect_nifty_data(
            request.from_date,
            request.to_date,
            request.symbol,
            request.force_refresh
        )
        
        return {
            "status": "success",
            "message": f"Collected NIFTY data from {request.from_date} to {request.to_date}",
            "records_collected": result
        }
    except Exception as e:
        logger.error(f"NIFTY collection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/collect/nifty-bulk", tags=["NIFTY Collection"])
async def collect_nifty_bulk(request: NiftyCollectionRequest):
    """Collect Nifty Bulk"""
    try:
        # Use the standard data collection service for bulk collection
        db = get_db_manager()
        breeze = BreezeService()
        data_svc = DataCollectionService(breeze, db)
        
        result = await data_svc.collect_nifty_data(
            request.from_date,
            request.to_date,
            request.symbol,
            request.force_refresh
        )
        
        return {
            "status": "success",
            "message": f"Bulk collected NIFTY data from {request.from_date} to {request.to_date}",
            "records_collected": result
        }
    except Exception as e:
        logger.error(f"Bulk NIFTY collection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/collect/options-direct", tags=["Options Collection"])
async def collect_options_direct(request: OptionsCollectionRequest):
    """Collect Options Direct"""
    try:
        db = get_db_manager()
        breeze = BreezeService()
        data_svc = DataCollectionService(breeze, db)
        
        result = await data_svc.collect_options_data(
            request.from_date,
            request.to_date,
            request.symbol,
            request.strike_range,
            strike_interval=request.strike_interval
        )
        
        return {
            "status": "success",
            "message": f"Collected options data from {request.from_date} to {request.to_date}",
            "records_collected": result
        }
    except Exception as e:
        logger.error(f"Options collection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/collect/options-bulk", tags=["Options Collection"])
async def collect_options_bulk(request: OptionsCollectionRequest):
    """Collect Options Bulk"""
    try:
        db = get_db_manager()
        breeze = BreezeService()
        data_svc = DataCollectionService(breeze, db)
        result = await data_svc.collect_options_data(
            request.from_date,
            request.to_date,
            request.symbol,
            request.strike_range,
            strike_interval=request.strike_interval
        )
        
        return {
            "status": "success",
            "message": f"Bulk collected options data from {request.from_date} to {request.to_date}",
            "records_collected": result
        }
    except Exception as e:
        logger.error(f"Bulk options collection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/collect/options-specific", tags=["Options Collection"])
async def collect_specific_options(request: SpecificOptionsRequest):
    """Collect Specific Options Strikes"""
    try:
        db = get_db_manager()
        breeze = BreezeService()
        data_svc = DataCollectionService(breeze, db)
        
        # Collect with specific strikes
        result = await data_svc.collect_options_data(
            request.from_date,
            request.to_date,
            request.symbol,
            specific_strikes=request.strikes  # Pass specific strikes
        )
        
        return {
            "status": "success",
            "message": f"Collected specific options data for {len(request.strikes)} strikes",
            "strikes": request.strikes,
            "records_collected": result
        }
    except Exception as e:
        logger.error(f"Specific options collection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/collect/options-by-signals", tags=["Options Collection"])
async def collect_options_by_signals(request: OptionsCollectionRequest):
    """Collect Options By Signals"""
    try:
        # Use standard collection service
        db = get_db_manager()
        breeze = BreezeService()
        data_svc = DataCollectionService(breeze, db)
        
        result = await data_svc.collect_options_data(
            request.from_date,
            request.to_date,
            request.symbol,
            request.strike_range,
            strike_interval=request.strike_interval
        )
        
        return {
            "status": "success",
            "message": "Collected options data based on signals",
            "records_collected": result
        }
    except Exception as e:
        logger.error(f"Signal-based collection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/collect/options-by-signals-fast", tags=["Options Collection"])
async def collect_options_by_signals_fast(request: OptionsCollectionRequest):
    """Collect Options By Signals Fast"""
    try:
        # Use standard collection service
        db = get_db_manager()
        breeze = BreezeService()
        data_svc = DataCollectionService(breeze, db)
        
        result = await data_svc.collect_options_data(
            request.from_date,
            request.to_date,
            request.symbol,
            request.strike_range,
            strike_interval=request.strike_interval
        )
        
        return {
            "status": "success",
            "message": "Fast collected options data based on signals",
            "records_collected": result
        }
    except Exception as e:
        logger.error(f"Fast signal collection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/collect/options-by-signals-optimized", tags=["Options Collection"])
async def collect_options_by_signals_optimized(request: OptionsCollectionRequest):
    """Collect Options By Signals Optimized"""
    try:
        # Use standard collection service
        db = get_db_manager()
        breeze = BreezeService()
        data_svc = DataCollectionService(breeze, db)
        
        result = await data_svc.collect_options_data(
            request.from_date,
            request.to_date,
            request.symbol,
            request.strike_range,
            strike_interval=request.strike_interval
        )
        
        return {
            "status": "success",
            "message": "Optimized collection of options data based on signals",
            "records_collected": result
        }
    except Exception as e:
        logger.error(f"Optimized collection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/collect/missing-from-insights", tags=["Options Collection"])
async def collect_missing_from_insights():
    """Collect missing strikes from WeeklySignalInsights_ConsolidatedResults table
    
    This endpoint reads the MissingOptionStrikes column from the table
    and fetches only those specific strikes that are missing.
    """
    try:
        import re
        db = get_db_manager()
        breeze = BreezeService()
        data_svc = DataCollectionService(breeze, db)
        
        with db.get_session() as session:
            # Query for records with missing strikes
            result = session.execute(text("""
                SELECT 
                    ResultID,
                    MissingOptionStrikes,
                    EntryTime,
                    ExitTime,
                    WeeklyExpiryDate,
                    MainStrikePrice,
                    MainOptionType,
                    HedgeStrike,
                    yr,
                    wk
                FROM WeeklySignalInsights_ConsolidatedResults
                WHERE MissingOptionStrikes IS NOT NULL 
                    AND MissingOptionStrikes != ''
                    AND MissingOptionStrikes != 'NULL'
                ORDER BY WeeklyExpiryDate DESC
            """))
            
            missing_records = result.fetchall()
        
        if not missing_records:
            return {
                "status": "success",
                "message": "No missing strikes found in the table",
                "records_collected": 0
            }
        
        # Group missing strikes by expiry date
        expiry_strikes = {}
        
        for record in missing_records:
            result_id = record[0]
            missing_strikes_str = record[1]
            entry_time = record[2]
            exit_time = record[3]
            expiry_date = record[4]
            
            # Parse missing strikes string
            if missing_strikes_str:
                strikes_list = [s.strip() for s in missing_strikes_str.split(',')]
                
                for strike_str in strikes_list:
                    # Extract strike price and option type
                    match = re.match(r'(\d+)(CE|PE)', strike_str)
                    if match:
                        strike_price = int(match.group(1))
                        
                        if expiry_date not in expiry_strikes:
                            expiry_strikes[expiry_date] = {
                                'strikes': set(),
                                'date_range': (entry_time, exit_time)
                            }
                        
                        expiry_strikes[expiry_date]['strikes'].add(strike_price)
        
        # Collect missing strikes for each expiry
        total_collected = 0
        details = []
        
        for expiry_date, data in expiry_strikes.items():
            strikes = list(data['strikes'])
            date_range = data['date_range']
            
            # Determine date range
            if date_range[0] and date_range[1]:
                from_date = date_range[0]
                to_date = date_range[1]
            else:
                from_date = expiry_date - timedelta(days=3)
                to_date = expiry_date
            
            try:
                # Collect the missing strikes
                records = await data_svc.ensure_options_data_available(
                    from_date,
                    to_date,
                    strikes,
                    [expiry_date],
                    fetch_missing=True
                )
                
                total_collected += records
                details.append({
                    "expiry": str(expiry_date),
                    "strikes": strikes,
                    "records": records
                })
                
            except Exception as e:
                logger.error(f"Error collecting strikes for {expiry_date}: {e}")
                details.append({
                    "expiry": str(expiry_date),
                    "strikes": strikes,
                    "error": str(e)
                })
        
        return {
            "status": "success",
            "message": f"Collected missing strikes from {len(expiry_strikes)} expiries",
            "records_collected": total_collected,
            "details": details
        }
        
    except Exception as e:
        logger.error(f"Error collecting missing strikes from table: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{job_id}", tags=["Job Management"])
async def get_job_status(job_id: str):
    """Get Job Status"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_status[job_id]

@app.get("/test-background-task", tags=["Testing"])
async def test_background_functionality(background_tasks: BackgroundTasks):
    """Test Background Functionality"""
    job_id = str(uuid4())
    job_status[job_id] = {"status": "pending", "message": "Task queued"}
    
    async def test_task():
        job_status[job_id] = {"status": "running", "message": "Task running"}
        await asyncio.sleep(5)
        job_status[job_id] = {"status": "completed", "message": "Task completed successfully"}
    
    background_tasks.add_task(test_task)
    return {"job_id": job_id, "status": "Task queued"}

@app.get("/data/check", tags=["Data Check"])
async def check_data_availability(
    from_date: date = Query(...),
    to_date: date = Query(...),
    symbol: str = Query(default="NIFTY")
):
    """Check Data Availability"""
    try:
        db = get_db_manager()
        with db.get_session() as session:
            from sqlalchemy import text
            query = text("""
                SELECT COUNT(*) as count, MIN(timestamp) as min_date, MAX(timestamp) as max_date
                FROM NiftyIndexData5Minute
                WHERE timestamp >= :from_date AND timestamp <= :to_date
            """)
            result = session.execute(query, {"from_date": from_date, "to_date": to_date}).fetchone()
            
            return {
                "status": "success",
                "nifty_data": {
                    "records": result.count,
                    "min_date": result.min_date,
                    "max_date": result.max_date,
                    "has_data": result.count > 0
                }
            }
    except Exception as e:
        logger.error(f"Data check error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/data/check-options", tags=["Data Check"])
async def check_options_availability(
    from_date: date = Query(...),
    to_date: date = Query(...),
    symbol: str = Query(default="NIFTY")
):
    """Check Options Availability"""
    try:
        db = get_db_manager()
        with db.get_session() as session:
            from sqlalchemy import text
            query = text("""
                SELECT COUNT(*) as count, COUNT(DISTINCT strike) as strikes
                FROM OptionsHistoricalData
                WHERE timestamp >= :from_date AND timestamp <= :to_date
            """)
            result = session.execute(query, {"from_date": from_date, "to_date": to_date}).fetchone()
            
            return {
                "status": "success",
                "options_data": {
                    "records": result.count,
                    "unique_strikes": result.strikes,
                    "has_data": result.count > 0
                }
            }
    except Exception as e:
        logger.error(f"Options check error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete/nifty-direct", tags=["Data Deletion"])
async def delete_nifty_data(
    from_date: date = Query(...),
    to_date: date = Query(...)
):
    """Delete Nifty Data"""
    try:
        db = get_db_manager()
        with db.get_session() as session:
            from sqlalchemy import text
            query = text("DELETE FROM NiftyIndexData5Minute WHERE timestamp >= :from_date AND timestamp <= :to_date")
            result = session.execute(query, {"from_date": from_date, "to_date": to_date})
            session.commit()
            return {
                "status": "success",
                "message": f"Deleted NIFTY data from {from_date} to {to_date}",
                "rows_affected": result.rowcount
            }
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete/options-direct", tags=["Data Deletion"])
async def delete_options_data(
    from_date: date = Query(...),
    to_date: date = Query(...)
):
    """Delete Options Data"""
    try:
        db = get_db_manager()
        with db.get_session() as session:
            from sqlalchemy import text
            query = text("DELETE FROM OptionsHistoricalData WHERE timestamp >= :from_date AND timestamp <= :to_date")
            result = session.execute(query, {"from_date": from_date, "to_date": to_date})
            session.commit()
            return {
                "status": "success",
                "message": f"Deleted options data from {from_date} to {to_date}",
                "rows_affected": result.rowcount
            }
    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete/all", tags=["Data Deletion"])
async def delete_all_data():
    """Delete All Data"""
    try:
        db = get_db_manager()
        with db.get_session() as session:
            tables = ["NiftyIndexData5Minute", "NiftyIndexDataHourly", "OptionsHistoricalData", "BacktestRuns", "BacktestTrades", "BacktestPositions"]
            total_deleted = 0
            for table in tables:
                result = session.execute(f"DELETE FROM {table}")
                total_deleted += result.rowcount
            session.commit()
            return {
                "status": "success",
                "message": "Deleted all data from all tables",
                "total_rows_deleted": total_deleted
            }
    except Exception as e:
        logger.error(f"Delete all error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/collect/tradingview", tags=["TradingView Collection"])
async def collect_tradingview_data(request: TradingViewRequest):
    """Collect Tradingview Data"""
    return {
        "status": "success",
        "message": "TradingView data collection not implemented",
        "note": "This endpoint is a placeholder"
    }

@app.post("/collect/tradingview-bulk", tags=["TradingView Collection"])
async def collect_tradingview_bulk_data(request: TradingViewRequest):
    """Collect Tradingview Bulk Data"""
    return {
        "status": "success",
        "message": "TradingView bulk collection not implemented",
        "note": "This endpoint is a placeholder"
    }

@app.get("/tradingview/check", tags=["TradingView Collection"])
async def check_tradingview_data(
    from_date: date = Query(...),
    to_date: date = Query(...)
):
    """Check Tradingview Data"""
    return {
        "status": "success",
        "message": "TradingView data check not implemented",
        "has_data": False
    }

@app.get("/api/v1/holidays/{year}", tags=["Holiday Management"])
async def get_holidays(year: int):
    """Get Holidays"""
    try:
        holiday_service = HolidayService(get_db_manager())
        holidays = holiday_service.get_holidays_for_year(year)
        return {
            "status": "success",
            "year": year,
            "holidays": [{"date": h.date, "description": h.description} for h in holidays]
        }
    except Exception as e:
        logger.error(f"Get holidays error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/holidays/load-defaults", tags=["Holiday Management"])
async def load_default_holidays():
    """Load Default Holidays"""
    try:
        holiday_service = HolidayService(get_db_manager())
        result = holiday_service.load_default_holidays()
        return {
            "status": "success",
            "message": "Default holidays loaded",
            "details": result
        }
    except Exception as e:
        logger.error(f"Load holidays error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/holidays/check/{date}", tags=["Holiday Management"])
async def check_holiday(date: date):
    """Check Holiday"""
    try:
        holiday_service = HolidayService(get_db_manager())
        is_holiday = holiday_service.is_holiday(date)
        return {
            "status": "success",
            "date": date,
            "is_holiday": is_holiday
        }
    except Exception as e:
        logger.error(f"Check holiday error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/holidays/trading-days", tags=["Holiday Management"])
async def get_trading_days(
    from_date: date = Query(...),
    to_date: date = Query(...)
):
    """Get Trading Days"""
    try:
        holiday_service = HolidayService(get_db_manager())
        trading_days = holiday_service.get_trading_days(from_date, to_date)
        return {
            "status": "success",
            "from_date": from_date,
            "to_date": to_date,
            "trading_days": trading_days,
            "count": len(trading_days)
        }
    except Exception as e:
        logger.error(f"Get trading days error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/holidays/load-all-defaults", tags=["Holiday Management"])
async def load_all_default_holidays():
    """Load All Default Holidays"""
    try:
        holiday_service = HolidayService(get_db_manager())
        result = holiday_service.load_all_defaults()
        return {
            "status": "success",
            "message": "All default holidays loaded",
            "details": result
        }
    except Exception as e:
        logger.error(f"Load all holidays error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/holidays/fetch-from-nse", tags=["Holiday Management"])
async def fetch_holidays_from_nse():
    """Fetch Holidays From Nse"""
    return {
        "status": "success",
        "message": "NSE holiday fetch not implemented",
        "note": "This endpoint is a placeholder"
    }

@app.post("/api/v1/collect/weekly-data", tags=["Weekly Collection"])
async def collect_weekly_data(request: WeeklyDataRequest):
    """Collect Weekly Data"""
    try:
        db = get_db_manager()
        breeze = BreezeService()
        data_svc = DataCollectionService(breeze, db)
        
        use_case = CollectWeeklyDataUseCase(data_svc)
        result = await use_case.execute(
            request.from_date,
            request.to_date,
            request.symbol,
            request.strike_range
        )
        
        return {
            "status": "success",
            "message": f"Collected weekly data from {request.from_date} to {request.to_date}",
            "details": result
        }
    except Exception as e:
        logger.error(f"Weekly collection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "message": "Unified Trading API",
        "version": "0.1.0",
        "endpoints": {
            "backtest": "/backtest",
            "data_collection": "/collect/*",
            "data_check": "/data/check",
            "holidays": "/api/v1/holidays/*",
            "docs": "/docs"
        }
    }

@app.get("/health", tags=["General"])
async def health_check():
    """Health check endpoint"""
    try:
        db = get_db_manager()
        db_status = "connected" if db.test_connection() else "disconnected"
        return {
            "status": "healthy",
            "database": db_status,
            "timestamp": datetime.now()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now()
        }

# Live Trading Endpoints
from src.infrastructure.brokers.kite import KiteClient, KiteAuthService, KiteOrderService
from src.application.use_cases.live_trading import (
    ExecuteLiveTradeUseCase, MonitorPositionsUseCase, ManageStopLossUseCase
)
from src.infrastructure.services.signal_to_kite_converter import SignalToKiteOrderConverter

# Initialize Kite services (lazy loading)
_kite_client = None
_kite_auth = None
_execute_trade_use_case = None
_monitor_positions_use_case = None
_manage_stop_loss_use_case = None

def get_kite_services():
    """Get or initialize Kite services"""
    global _kite_client, _kite_auth, _execute_trade_use_case
    global _monitor_positions_use_case, _manage_stop_loss_use_case
    
    if _kite_client is None:
        _kite_client = KiteClient()
        _kite_auth = KiteAuthService(_kite_client)
        db = get_db_manager()
        _execute_trade_use_case = ExecuteLiveTradeUseCase(_kite_client, db)
        _monitor_positions_use_case = MonitorPositionsUseCase(_kite_client, db)
        _manage_stop_loss_use_case = ManageStopLossUseCase(_kite_client, db)
    
    return (_kite_client, _kite_auth, _execute_trade_use_case, 
            _monitor_positions_use_case, _manage_stop_loss_use_case)

class LiveTradingConfig(BaseModel):
    enabled: bool = False
    lot_size: int = 75
    num_lots: int = 10
    use_hedging: bool = True
    max_positions: int = 1

class ManualSignalRequest(BaseModel):
    signal_type: str
    current_spot: float

@app.get("/live/auth/status", tags=["Live Trading - Auth"])
async def get_auth_status():
    """Get Kite authentication status"""
    try:
        _, kite_auth, _, _, _ = get_kite_services()
        return kite_auth.get_auth_status()
    except Exception as e:
        logger.error(f"Error getting auth status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live/auth/login-url", tags=["Live Trading - Auth"])
async def get_login_url():
    """Get Kite login URL for authentication"""
    try:
        kite_client, _, _, _, _ = get_kite_services()
        return {"login_url": kite_client.get_login_url()}
    except Exception as e:
        logger.error(f"Error getting login URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/live/auth/complete", tags=["Live Trading - Auth"])
async def complete_authentication(request_token: str = Query(...)):
    """Complete authentication with request token"""
    try:
        _, kite_auth, _, _, _ = get_kite_services()
        user_data = kite_auth.complete_authentication(request_token)
        return {
            "status": "success",
            "user_id": user_data.get("user_id"),
            "user_name": user_data.get("user_name")
        }
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/live/start-trading", tags=["Live Trading - Control"])
async def start_live_trading(config: LiveTradingConfig):
    """Enable live trading with configuration"""
    try:
        _, _, execute_trade_use_case, _, _ = get_kite_services()
        
        # Update configuration
        execute_trade_use_case.lot_size = config.lot_size
        execute_trade_use_case.num_lots = config.num_lots
        execute_trade_use_case.use_hedging = config.use_hedging
        execute_trade_use_case.max_positions = config.max_positions
        
        # Enable trading
        if config.enabled:
            execute_trade_use_case.enable_trading()
        
        return {
            "status": "success",
            "message": "Live trading configuration updated",
            "enabled": config.enabled
        }
    except Exception as e:
        logger.error(f"Error starting live trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/live/stop-trading", tags=["Live Trading - Control"])
async def stop_live_trading():
    """Disable live trading"""
    try:
        _, _, execute_trade_use_case, _, _ = get_kite_services()
        execute_trade_use_case.disable_trading()
        return {"status": "success", "message": "Live trading disabled"}
    except Exception as e:
        logger.error(f"Error stopping live trading: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live/positions", tags=["Live Trading - Monitoring"])
async def get_live_positions():
    """Get current live positions"""
    try:
        _, _, _, monitor_positions_use_case, _ = get_kite_services()
        result = monitor_positions_use_case.execute()
        return result
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/live/execute-signal", tags=["Live Trading - Execution"])
async def execute_manual_signal(request: ManualSignalRequest):
    """Manually execute a trading signal"""
    try:
        _, _, execute_trade_use_case, _, _ = get_kite_services()
        
        # Create signal result
        from src.domain.value_objects.signal_types import SignalResult, TradeDirection
        
        # Determine direction based on signal type
        bearish_signals = ['S3', 'S5', 'S6', 'S8']
        direction = TradeDirection.BEARISH if request.signal_type in bearish_signals else TradeDirection.BULLISH
        
        signal = SignalResult(
            signal_type=request.signal_type,
            direction=direction,
            confidence=1.0,
            bar_index=0
        )
        
        result = execute_trade_use_case.execute(signal, request.current_spot)
        return result
    except Exception as e:
        logger.error(f"Error executing signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live/pnl", tags=["Live Trading - Monitoring"])
async def get_live_pnl():
    """Get real-time P&L"""
    try:
        kite_client, _, _, _, _ = get_kite_services()
        order_service = KiteOrderService(kite_client)
        pnl_data = order_service.get_position_pnl()
        return pnl_data
    except Exception as e:
        logger.error(f"Error getting P&L: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/live/square-off", tags=["Live Trading - Control"])
async def square_off_all_positions():
    """Emergency square-off all positions"""
    try:
        kite_client, _, _, _, _ = get_kite_services()
        order_service = KiteOrderService(kite_client)
        order_ids = order_service.square_off_all_positions()
        return {
            "status": "success",
            "message": "All positions squared off",
            "order_ids": order_ids
        }
    except Exception as e:
        logger.error(f"Error squaring off positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live/stop-loss/status", tags=["Live Trading - Risk Management"])
async def get_stop_loss_status():
    """Get stop loss monitoring status"""
    try:
        _, _, _, _, manage_stop_loss_use_case = get_kite_services()
        result = manage_stop_loss_use_case.execute()
        return result
    except Exception as e:
        logger.error(f"Error checking stop loss: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live/stop-loss/summary", tags=["Live Trading - Risk Management"])
async def get_stop_loss_summary():
    """Get stop loss summary for the day"""
    try:
        _, _, _, _, manage_stop_loss_use_case = get_kite_services()
        summary = manage_stop_loss_use_case.get_stop_loss_summary()
        return summary
    except Exception as e:
        logger.error(f"Error getting stop loss summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/live/trades/active", tags=["Live Trading - Monitoring"])
async def get_active_trades():
    """Get all active trades"""
    try:
        _, _, _, monitor_positions_use_case, _ = get_kite_services()
        trades = monitor_positions_use_case.get_active_trades()
        return {"trades": trades, "count": len(trades)}
    except Exception as e:
        logger.error(f"Error getting active trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def kill_existing_process_on_port(port: int):
    """Kill any existing process using the specified port"""
    import subprocess
    
    try:
        # Find process using the port
        result = subprocess.run(
            f"netstat -ano | findstr :{port}",
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if "LISTENING" in line:
                    # Extract PID from the line
                    parts = line.split()
                    pid = parts[-1]
                    
                    # Kill the process
                    kill_result = subprocess.run(
                        f"taskkill /PID {pid} /F",
                        shell=True,
                        capture_output=True,
                        text=True
                    )
                    
                    if kill_result.returncode == 0:
                        logger.info(f"Successfully killed process {pid} using port {port}")
                    else:
                        logger.warning(f"Failed to kill process {pid}: {kill_result.stderr}")
                    
    except Exception as e:
        logger.error(f"Error checking/killing process on port {port}: {str(e)}")

if __name__ == "__main__":
    # Kill any existing process on port 8000
    kill_existing_process_on_port(8000)
    
    # Wait a moment for the port to be released
    import time
    time.sleep(1)
    
    # Start the server
    logger.info("Starting Unified Trading API on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)