"""
Backtesting Router
API endpoints for backtesting operations with 8 signals
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from datetime import datetime, date, timedelta
from pydantic import BaseModel, Field

from ...application.use_cases.run_backtest import RunBacktestUseCase, BacktestParameters
from ...infrastructure.di.container import get_service
from ...infrastructure.database.models import BacktestRun, BacktestTrade, BacktestStatus
from ...infrastructure.database.database_manager import get_db_manager
from sqlalchemy import and_

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class RunBacktestRequest(BaseModel):
    """Request model for running a backtest"""
    from_date: date = Field(..., description="Start date for backtest")
    to_date: date = Field(..., description="End date for backtest")
    initial_capital: float = Field(default=500000, description="Starting capital")
    lot_size: int = Field(default=75, description="NIFTY lot size")
    lots_to_trade: int = Field(default=10, description="Number of lots to trade")
    signals_to_test: List[str] = Field(
        default=["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
        description="List of signals to test"
    )
    use_hedging: bool = Field(default=True, description="Use hedging positions")
    hedge_offset: int = Field(default=500, description="Points offset for hedge strike")
    commission_per_lot: float = Field(default=40, description="Commission per lot")
    slippage_percent: float = Field(default=0.001, description="Slippage percentage")


class BacktestResultResponse(BaseModel):
    """Response model for backtest results"""
    backtest_id: str
    status: str
    from_date: datetime
    to_date: datetime
    initial_capital: float
    final_capital: Optional[float]
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Optional[float]
    total_pnl: Optional[float]
    total_return_percent: Optional[float]
    max_drawdown: Optional[float]
    max_drawdown_percent: Optional[float]
    created_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]


class ZoneInfo(BaseModel):
    """Zone information"""
    resistance_zone_top: float
    resistance_zone_bottom: float
    support_zone_top: float
    support_zone_bottom: float
    margin_high: float = 0.0025
    margin_low: float = 0.0025


class MarketContext(BaseModel):
    """Market context at trade entry"""
    bias: str
    bias_strength: float
    distance_to_resistance: float
    distance_to_support: float
    weekly_max_high: float
    weekly_min_low: float


class SignalTriggerInfo(BaseModel):
    """Signal trigger details"""
    trigger_condition: str
    first_bar_open: Optional[float]
    first_bar_close: Optional[float]
    first_bar_high: Optional[float]
    first_bar_low: Optional[float]
    signal_bar_close: float


class PositionDetail(BaseModel):
    """Option position details"""
    position_type: str  # MAIN/HEDGE
    option_type: str    # CE/PE
    strike_price: int
    entry_price: float
    exit_price: Optional[float]
    quantity: int       # Negative for sell
    lots: int          # Absolute number of lots
    net_pnl: Optional[float]


class TradeDetailResponse(BaseModel):
    """Response model for trade details"""
    trade_id: str
    backtest_id: str
    week_start_date: datetime
    signal_type: str
    direction: str
    entry_time: datetime
    index_price_at_entry: float
    stop_loss_price: float
    exit_time: Optional[datetime]
    index_price_at_exit: Optional[float]
    outcome: str
    exit_reason: Optional[str]
    total_pnl: Optional[float]
    zones: Optional[ZoneInfo]
    market_context: Optional[MarketContext]
    signal_trigger: Optional[SignalTriggerInfo]
    positions: List[PositionDetail]


class SignalPerformanceResponse(BaseModel):
    """Response model for signal performance"""
    signal_type: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl_per_trade: float
    best_trade_pnl: float
    worst_trade_pnl: float


@router.post("/run")
async def run_backtest(
    request: RunBacktestRequest,
    backtest_service: RunBacktestUseCase = Depends(lambda: get_service(RunBacktestUseCase))
):
    """
    Run a backtest with the 8 trading signals
    
    This endpoint will:
    1. Fetch NIFTY index data for the date range (if not available)
    2. Fetch options data for required strikes and expiries
    3. Run all 8 signals on the data
    4. Track exact option entry/exit prices with hedging
    5. Calculate P&L at weekly expiry or stop loss
    
    Returns the backtest ID to track progress and get results
    """
    try:
        # Convert dates to datetime with market hours
        # Start at 9:15 AM IST (market open)
        from_date = datetime.combine(request.from_date, datetime.strptime("09:15", "%H:%M").time())
        # End at 3:30 PM IST (market close)
        to_date = datetime.combine(request.to_date, datetime.strptime("15:30", "%H:%M").time())
        
        # Create backtest parameters
        params = BacktestParameters(
            from_date=from_date,
            to_date=to_date,
            initial_capital=request.initial_capital,
            lot_size=request.lot_size,
            signals_to_test=request.signals_to_test,
            use_hedging=request.use_hedging,
            hedge_offset=request.hedge_offset,
            commission_per_lot=request.commission_per_lot,
            slippage_percent=request.slippage_percent
        )
        
        # Run backtest asynchronously
        backtest_id = await backtest_service.execute(params)
        
        # DEBUG: Check result immediately
        db_manager = get_db_manager()
        with db_manager.get_session() as session:
            run = session.query(BacktestRun).filter_by(id=backtest_id).first()
            logger.info(f"[DEBUG] Backtest {backtest_id} completed with {run.total_trades} trades")
        
        return {
            "success": True,
            "backtest_id": backtest_id,
            "message": "Backtest started successfully",
            "status_url": f"/api/v2/backtest/status/{backtest_id}",
            "results_url": f"/api/v2/backtest/results/{backtest_id}"
        }
        
    except Exception as e:
        logger.error(f"Error starting backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{backtest_id}")
async def get_backtest_status(backtest_id: str):
    """Get current status of a backtest"""
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        backtest = session.query(BacktestRun).filter_by(id=backtest_id).first()
        
        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")
        
        return {
            "backtest_id": backtest.id,
            "status": backtest.status.value,
            "created_at": backtest.created_at,
            "started_at": backtest.started_at,
            "completed_at": backtest.completed_at,
            "progress": {
                "total_trades": backtest.total_trades,
                "current_status": backtest.status.value,
                "error_message": backtest.error_message
            }
        }


@router.get("/latest")
async def get_latest_backtest():
    """Get the most recent backtest results"""
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        latest_backtest = session.query(BacktestRun).filter_by(
            status=BacktestStatus.COMPLETED
        ).order_by(BacktestRun.completed_at.desc()).first()
        
        if not latest_backtest:
            raise HTTPException(status_code=404, detail="No completed backtests found")
        
        return BacktestResultResponse(
            backtest_id=latest_backtest.id,
            status=latest_backtest.status.value,
            from_date=latest_backtest.from_date,
            to_date=latest_backtest.to_date,
            initial_capital=float(latest_backtest.initial_capital),
            final_capital=float(latest_backtest.final_capital) if latest_backtest.final_capital else None,
            total_trades=latest_backtest.total_trades,
            winning_trades=latest_backtest.winning_trades,
            losing_trades=latest_backtest.losing_trades,
            win_rate=float(latest_backtest.win_rate) if latest_backtest.win_rate else None,
            total_pnl=float(latest_backtest.total_pnl) if latest_backtest.total_pnl else None,
            total_return_percent=float(latest_backtest.total_return_percent) if latest_backtest.total_return_percent else None,
            max_drawdown=float(latest_backtest.max_drawdown) if latest_backtest.max_drawdown else None,
            max_drawdown_percent=float(latest_backtest.max_drawdown_percent) if latest_backtest.max_drawdown_percent else None,
            created_at=latest_backtest.created_at,
            completed_at=latest_backtest.completed_at,
            error_message=latest_backtest.error_message
        )


@router.get("/today")
async def get_todays_trades(
    signal_type: Optional[str] = Query(None, description="Filter by signal type (S1-S8)"),
    include_zones: bool = Query(True, description="Include zone and context information")
):
    """Get trades from today's date across all backtests"""
    today = date.today()
    
    # Redirect to trades endpoint with today's date
    return await get_backtest_trades(
        backtest_id=None,
        from_date=today,
        to_date=today,
        signal_type=signal_type,
        outcome=None,
        limit=100,
        offset=0,
        include_zones=include_zones
    )


@router.get("/results")
async def get_backtest_results(
    backtest_id: Optional[str] = Query(None, description="Specific backtest ID"),
    from_date: Optional[date] = Query(None, description="Start date for filtering"),
    to_date: Optional[date] = Query(None, description="End date for filtering"),
    include_trades: bool = Query(default=False, description="Include individual trades")
):
    """
    Get detailed results for backtest(s)
    - Can query by specific backtest_id
    - Or by date range (returns aggregated results if multiple backtests)
    """
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        if backtest_id:
            # Query by specific ID
            backtest = session.query(BacktestRun).filter_by(id=backtest_id).first()
            if not backtest:
                raise HTTPException(status_code=404, detail="Backtest not found")
            
            return BacktestResultResponse(
                backtest_id=backtest.id,
                status=backtest.status.value,
                from_date=backtest.from_date,
                to_date=backtest.to_date,
                initial_capital=float(backtest.initial_capital),
                final_capital=float(backtest.final_capital) if backtest.final_capital else None,
                total_trades=backtest.total_trades,
                winning_trades=backtest.winning_trades,
                losing_trades=backtest.losing_trades,
                win_rate=float(backtest.win_rate) if backtest.win_rate else None,
                total_pnl=float(backtest.total_pnl) if backtest.total_pnl else None,
                total_return_percent=float(backtest.total_return_percent) if backtest.total_return_percent else None,
                max_drawdown=float(backtest.max_drawdown) if backtest.max_drawdown else None,
                max_drawdown_percent=float(backtest.max_drawdown_percent) if backtest.max_drawdown_percent else None,
                created_at=backtest.created_at,
                completed_at=backtest.completed_at,
                error_message=backtest.error_message
            )
        
        elif from_date and to_date:
            # Query by date range
            from_dt = datetime.combine(from_date, datetime.min.time())
            to_dt = datetime.combine(to_date, datetime.max.time())
            
            backtests = session.query(BacktestRun).filter(
                and_(
                    BacktestRun.from_date <= to_dt,
                    BacktestRun.to_date >= from_dt,
                    BacktestRun.status == BacktestStatus.COMPLETED
                )
            ).all()
            
            if not backtests:
                raise HTTPException(status_code=404, detail="No backtests found for the specified date range")
            
            # Aggregate results
            total_trades = sum(bt.total_trades for bt in backtests)
            winning_trades = sum(bt.winning_trades for bt in backtests)
            losing_trades = sum(bt.losing_trades for bt in backtests)
            total_pnl = sum(float(bt.total_pnl) for bt in backtests if bt.total_pnl)
            
            return {
                "query": {
                    "from_date": from_date,
                    "to_date": to_date,
                    "backtest_count": len(backtests)
                },
                "aggregated_results": {
                    "total_trades": total_trades,
                    "winning_trades": winning_trades,
                    "losing_trades": losing_trades,
                    "win_rate": (winning_trades / total_trades * 100) if total_trades > 0 else 0,
                    "total_pnl": total_pnl
                },
                "backtests": [{
                    "backtest_id": bt.id,
                    "from_date": bt.from_date,
                    "to_date": bt.to_date,
                    "total_trades": bt.total_trades,
                    "win_rate": float(bt.win_rate) if bt.win_rate else None,
                    "total_pnl": float(bt.total_pnl) if bt.total_pnl else None
                } for bt in backtests]
            }
        
        else:
            raise HTTPException(status_code=400, detail="Either backtest_id or both from_date and to_date are required")


@router.get("/trades")
async def get_backtest_trades(
    backtest_id: Optional[str] = Query(None, description="Specific backtest ID"),
    from_date: Optional[date] = Query(None, description="Start date for filtering"),
    to_date: Optional[date] = Query(None, description="End date for filtering"),
    signal_type: Optional[str] = Query(None, description="Filter by signal type (S1-S8)"),
    outcome: Optional[str] = Query(None, description="Filter by outcome (WIN/LOSS/STOPPED/EXPIRED)"),
    limit: int = Query(100, description="Maximum number of trades to return"),
    offset: int = Query(0, description="Number of trades to skip"),
    include_zones: bool = Query(True, description="Include zone and context information")
):
    """
    Get individual trades from backtest(s)
    - Can query by specific backtest_id
    - Or by date range (returns trades from all backtests in range)
    """
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        # Build base query
        query = session.query(BacktestTrade)
        
        if backtest_id:
            # Query by specific backtest
            query = query.filter_by(backtest_run_id=backtest_id)
        elif from_date and to_date:
            # Query by date range
            from_dt = datetime.combine(from_date, datetime.min.time())
            to_dt = datetime.combine(to_date, datetime.max.time())
            query = query.filter(
                and_(
                    BacktestTrade.entry_time >= from_dt,
                    BacktestTrade.entry_time <= to_dt
                )
            )
        else:
            raise HTTPException(status_code=400, detail="Either backtest_id or both from_date and to_date are required")
        
        # Apply filters
        if signal_type:
            query = query.filter_by(signal_type=signal_type)
        
        if outcome:
            query = query.filter_by(outcome=outcome)
        
        # Get total count
        total_count = query.count()
        
        # Get trades with pagination
        trades = query.order_by(BacktestTrade.entry_time).limit(limit).offset(offset).all()
        
        trade_details = []
        for trade in trades:
            # Build position details
            position_details = []
            for pos in trade.positions:
                lots = abs(pos.quantity) // 75  # Calculate lots from quantity
                position_details.append(PositionDetail(
                    position_type=pos.position_type,
                    option_type=pos.option_type,
                    strike_price=pos.strike_price,
                    entry_price=float(pos.entry_price),
                    exit_price=float(pos.exit_price) if pos.exit_price else None,
                    quantity=pos.quantity,
                    lots=lots,
                    net_pnl=float(pos.net_pnl) if pos.net_pnl else None
                ))
            
            # Build response with zone information if requested
            trade_detail = TradeDetailResponse(
                trade_id=trade.id,
                backtest_id=trade.backtest_run_id,
                week_start_date=trade.week_start_date,
                signal_type=trade.signal_type,
                direction=trade.direction,
                entry_time=trade.entry_time,
                index_price_at_entry=float(trade.index_price_at_entry),
                stop_loss_price=float(trade.stop_loss_price),
                exit_time=trade.exit_time,
                index_price_at_exit=float(trade.index_price_at_exit) if trade.index_price_at_exit else None,
                outcome=trade.outcome.value,
                exit_reason=trade.exit_reason,
                total_pnl=float(trade.total_pnl) if trade.total_pnl else None,
                positions=position_details
            )
            
            # Add zone information if available and requested
            if include_zones:
                if trade.resistance_zone_top:
                    trade_detail.zones = ZoneInfo(
                        resistance_zone_top=float(trade.resistance_zone_top),
                        resistance_zone_bottom=float(trade.resistance_zone_bottom),
                        support_zone_top=float(trade.support_zone_top),
                        support_zone_bottom=float(trade.support_zone_bottom)
                    )
                
                if trade.bias_direction:
                    trade_detail.market_context = MarketContext(
                        bias=trade.bias_direction,
                        bias_strength=float(trade.bias_strength) if trade.bias_strength else 0.0,
                        distance_to_resistance=float(trade.distance_to_resistance) if trade.distance_to_resistance else 0.0,
                        distance_to_support=float(trade.distance_to_support) if trade.distance_to_support else 0.0,
                        weekly_max_high=float(trade.weekly_max_high) if trade.weekly_max_high else 0.0,
                        weekly_min_low=float(trade.weekly_min_low) if trade.weekly_min_low else 0.0
                    )
                
                # Add signal trigger details
                signal_descriptions = {
                    "S1": "Bear Trap - Fake breakdown below support that recovers",
                    "S2": "Support Hold - Price respects support with bullish bias",
                    "S3": "Resistance Hold - Price fails at resistance with bearish bias",
                    "S4": "Bias Failure Bull - Bearish bias fails, price breaks out",
                    "S5": "Bias Failure Bear - Bullish bias fails, price breaks down",
                    "S6": "Weakness Confirmed - Similar to S3 with different entry",
                    "S7": "1H Breakout Confirmed - Strongest breakout signal",
                    "S8": "1H Breakdown Confirmed - Strongest breakdown signal"
                }
                
                trade_detail.signal_trigger = SignalTriggerInfo(
                    trigger_condition=signal_descriptions.get(trade.signal_type, "Unknown signal"),
                    first_bar_open=float(trade.first_bar_open) if trade.first_bar_open else None,
                    first_bar_close=float(trade.first_bar_close) if trade.first_bar_close else None,
                    first_bar_high=float(trade.first_bar_high) if trade.first_bar_high else None,
                    first_bar_low=float(trade.first_bar_low) if trade.first_bar_low else None,
                    signal_bar_close=float(trade.index_price_at_entry)
                )
            
            trade_details.append(trade_detail)
        
        # Build response based on query type
        response = {
            "total_trades": total_count,
            "trades": trade_details,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            }
        }
        
        if backtest_id:
            response["backtest_id"] = backtest_id
        else:
            response["query"] = {
                "from_date": from_date,
                "to_date": to_date,
                "signal_type": signal_type,
                "outcome": outcome
            }
        
        return response


@router.get("/signal-performance")
async def get_signal_performance(
    backtest_id: Optional[str] = Query(None, description="Specific backtest ID"),
    from_date: Optional[date] = Query(None, description="Start date for filtering"),
    to_date: Optional[date] = Query(None, description="End date for filtering")
):
    """
    Get performance breakdown by signal type
    - Can query by specific backtest_id
    - Or by date range
    """
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        if backtest_id:
            trades = session.query(BacktestTrade).filter_by(backtest_run_id=backtest_id).all()
        elif from_date and to_date:
            from_dt = datetime.combine(from_date, datetime.min.time())
            to_dt = datetime.combine(to_date, datetime.max.time())
            trades = session.query(BacktestTrade).filter(
                and_(
                    BacktestTrade.entry_time >= from_dt,
                    BacktestTrade.entry_time <= to_dt
                )
            ).all()
        else:
            raise HTTPException(status_code=400, detail="Either backtest_id or both from_date and to_date are required")
        
        if not trades:
            raise HTTPException(status_code=404, detail="No trades found for this backtest")
        
        # Group by signal type
        signal_performance = {}
        
        for trade in trades:
            signal = trade.signal_type
            if signal not in signal_performance:
                signal_performance[signal] = {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "total_pnl": 0,
                    "pnl_list": []
                }
            
            stats = signal_performance[signal]
            stats["total_trades"] += 1
            
            if trade.outcome.value == "WIN":
                stats["winning_trades"] += 1
            elif trade.outcome.value in ["LOSS", "STOPPED"]:
                stats["losing_trades"] += 1
            
            if trade.total_pnl:
                pnl = float(trade.total_pnl)
                stats["total_pnl"] += pnl
                stats["pnl_list"].append(pnl)
        
        # Calculate final stats
        results = []
        for signal, stats in signal_performance.items():
            pnl_list = stats["pnl_list"]
            results.append(SignalPerformanceResponse(
                signal_type=signal,
                total_trades=stats["total_trades"],
                winning_trades=stats["winning_trades"],
                losing_trades=stats["losing_trades"],
                win_rate=(stats["winning_trades"] / stats["total_trades"] * 100) if stats["total_trades"] > 0 else 0,
                total_pnl=stats["total_pnl"],
                avg_pnl_per_trade=stats["total_pnl"] / stats["total_trades"] if stats["total_trades"] > 0 else 0,
                best_trade_pnl=max(pnl_list) if pnl_list else 0,
                worst_trade_pnl=min(pnl_list) if pnl_list else 0
            ))
        
        # Sort by total P&L
        results.sort(key=lambda x: x.total_pnl, reverse=True)
        
        return {
            "backtest_id": backtest_id,
            "signal_performance": results
        }


@router.get("/daily-pnl")
async def get_daily_pnl(
    backtest_id: Optional[str] = Query(None, description="Specific backtest ID"),
    from_date: Optional[date] = Query(None, description="Start date for filtering"),
    to_date: Optional[date] = Query(None, description="End date for filtering")
):
    """
    Get daily P&L breakdown
    - Can query by specific backtest_id
    - Or by date range
    """
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        from ...infrastructure.database.models import BacktestDailyResult
        
        if backtest_id:
            daily_results = session.query(BacktestDailyResult).filter_by(
                backtest_run_id=backtest_id
            ).order_by(BacktestDailyResult.date).all()
        elif from_date and to_date:
            from_dt = datetime.combine(from_date, datetime.min.time())
            to_dt = datetime.combine(to_date, datetime.max.time())
            daily_results = session.query(BacktestDailyResult).filter(
                and_(
                    BacktestDailyResult.date >= from_dt,
                    BacktestDailyResult.date <= to_dt
                )
            ).order_by(BacktestDailyResult.date).all()
        else:
            raise HTTPException(status_code=400, detail="Either backtest_id or both from_date and to_date are required")
        
        if not daily_results:
            raise HTTPException(status_code=404, detail="No daily results found")
        
        return {
            "backtest_id": backtest_id,
            "daily_pnl": [{
                "date": result.date.date(),
                "starting_capital": float(result.starting_capital),
                "ending_capital": float(result.ending_capital),
                "daily_pnl": float(result.daily_pnl),
                "daily_return_percent": float(result.daily_return_percent),
                "trades_opened": result.trades_opened,
                "trades_closed": result.trades_closed,
                "open_positions": result.open_positions
            } for result in daily_results]
        }


@router.post("/data/prepare")
async def prepare_backtest_data(
    from_date: date,
    to_date: date,
    data_service = Depends(lambda: get_service("DataCollectionService"))
):
    """
    Prepare data for backtesting by fetching missing NIFTY and options data
    
    This endpoint will:
    1. Check what data is missing in the database
    2. Fetch missing NIFTY hourly data from Breeze API
    3. Fetch missing options data for likely strikes
    4. Return summary of data preparation
    """
    try:
        # Convert dates
        start_dt = datetime.combine(from_date, datetime.min.time())
        end_dt = datetime.combine(to_date, datetime.max.time())
        
        # Fetch NIFTY data
        nifty_added = await data_service.ensure_nifty_data_available(start_dt, end_dt)
        
        # Get expiry dates in range
        expiry_dates = []
        current = start_dt
        while current <= end_dt:
            expiry = await data_service.get_nearest_expiry(current)
            if expiry <= end_dt and expiry not in expiry_dates:
                expiry_dates.append(expiry)
            current = expiry + timedelta(days=1)
        
        # Prepare strikes (simplified - in production, determine dynamically)
        strikes = list(range(15000, 30000, 50))
        
        # Fetch options data
        options_added = await data_service.ensure_options_data_available(
            start_dt, end_dt, strikes, expiry_dates
        )
        
        return {
            "success": True,
            "nifty_records_added": nifty_added,
            "options_records_added": options_added,
            "expiry_dates_covered": len(expiry_dates),
            "date_range": {
                "from": from_date,
                "to": to_date
            },
            "message": f"Data preparation complete. Added {nifty_added} NIFTY and {options_added} options records."
        }
        
    except Exception as e:
        logger.error(f"Error preparing data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_backtests(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, description="Maximum number of backtests to return"),
    offset: int = Query(0, description="Number of backtests to skip")
):
    """List all backtests with optional filtering"""
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        query = session.query(BacktestRun)
        
        if status:
            query = query.filter_by(status=status)
        
        total_count = query.count()
        
        backtests = query.order_by(BacktestRun.created_at.desc()).limit(limit).offset(offset).all()
        
        return {
            "total_count": total_count,
            "backtests": [{
                "id": bt.id,
                "name": bt.name,
                "status": bt.status.value,
                "from_date": bt.from_date,
                "to_date": bt.to_date,
                "initial_capital": float(bt.initial_capital),
                "total_trades": bt.total_trades,
                "win_rate": float(bt.win_rate) if bt.win_rate else None,
                "total_pnl": float(bt.total_pnl) if bt.total_pnl else None,
                "created_at": bt.created_at,
                "completed_at": bt.completed_at
            } for bt in backtests],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            }
        }


@router.delete("/{backtest_id}")
async def delete_backtest(backtest_id: str):
    """Delete a backtest and all its associated data"""
    db_manager = get_db_manager()
    
    with db_manager.get_session() as session:
        backtest = session.query(BacktestRun).filter_by(id=backtest_id).first()
        
        if not backtest:
            raise HTTPException(status_code=404, detail="Backtest not found")
        
        # Delete will cascade to trades, positions, and daily results
        session.delete(backtest)
        session.commit()
        
        return {
            "success": True,
            "message": f"Backtest {backtest_id} deleted successfully"
        }