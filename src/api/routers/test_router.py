"""Test router - working backtest implementation"""
from fastapi import APIRouter, Query
from datetime import datetime, date
from pydantic import BaseModel
from typing import List, Optional, Dict
import asyncio

router = APIRouter()

class BacktestRequest(BaseModel):
    """Request model for backtest"""
    from_date: date
    to_date: date
    initial_capital: float = 500000
    lot_size: int = 75
    lots_to_trade: int = 10  # Number of lots to trade (10 lots = 750 quantity)
    signals_to_test: List[str] = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
    use_hedging: bool = True
    hedge_offset: int = 200
    commission_per_lot: float = 40
    slippage_percent: float = 0.001

class TradeResult(BaseModel):
    """Trade result model"""
    signal_type: str
    entry_time: datetime
    stop_loss: float
    direction: str
    outcome: str
    total_pnl: float
    positions: List[dict]

class BacktestResult(BaseModel):
    """Backtest result model"""
    backtest_id: str
    total_trades: int
    final_capital: float
    total_pnl: float
    win_rate: float
    trades: List[TradeResult]
    lot_size: int
    hedge_offset: int

@router.post("/run-backtest")
async def run_backtest_direct(request: BacktestRequest):
    """Run backtest using direct implementation (bypassing DI container)"""
    
    # Import everything we need directly
    from ...infrastructure.database.database_manager import get_db_manager
    from ...infrastructure.services.data_collection_service import DataCollectionService
    from ...infrastructure.services.breeze_service import BreezeService
    from ...infrastructure.services.option_pricing_service import OptionPricingService
    from ...application.use_cases.run_backtest import RunBacktestUseCase, BacktestParameters
    from ...infrastructure.database.models import BacktestRun, BacktestTrade, BacktestPosition
    
    # Setup services directly (no DI container)
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    option_svc = OptionPricingService(data_svc, db)
    backtest = RunBacktestUseCase(data_svc, option_svc)
    
    # Convert dates to datetime
    from_datetime = datetime.combine(request.from_date, datetime.strptime("09:15", "%H:%M").time())
    to_datetime = datetime.combine(request.to_date, datetime.strptime("15:30", "%H:%M").time())
    
    # Create parameters
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
    
    # Run backtest
    backtest_id = await backtest.execute(params)
    
    # Get results
    with db.get_session() as session:
        run = session.query(BacktestRun).filter_by(id=backtest_id).first()
        
        # Get trades
        trades = session.query(BacktestTrade).filter_by(
            backtest_run_id=backtest_id
        ).all()
        
        trade_results = []
        for trade in trades:
            # Get positions
            positions = session.query(BacktestPosition).filter_by(
                trade_id=trade.id
            ).all()
            
            position_data = []
            for pos in positions:
                action = "SELL" if pos.quantity < 0 else "BUY"
                position_data.append({
                    "type": pos.position_type,
                    "action": action,
                    "quantity": abs(pos.quantity),
                    "strike": pos.strike_price,
                    "option_type": pos.option_type,
                    "entry_price": float(pos.entry_price),
                    "exit_price": float(pos.exit_price) if pos.exit_price else None,
                    "pnl": float(pos.net_pnl) if pos.net_pnl else None
                })
            
            trade_results.append(TradeResult(
                signal_type=trade.signal_type,
                entry_time=trade.entry_time,
                stop_loss=float(trade.stop_loss_price),
                direction="BULLISH" if trade.direction == 1 else "BEARISH",
                outcome=trade.outcome.value,
                total_pnl=float(trade.total_pnl) if trade.total_pnl else 0,
                positions=position_data
            ))
        
        # Calculate win rate
        win_rate = 0
        if run.total_trades > 0:
            win_rate = (run.winning_trades / run.total_trades) * 100
        
        return BacktestResult(
            backtest_id=backtest_id,
            total_trades=run.total_trades,
            final_capital=float(run.final_capital),
            total_pnl=float(run.total_pnl) if run.total_pnl else 0,
            win_rate=win_rate,
            trades=trade_results,
            lot_size=run.lot_size,
            hedge_offset=run.hedge_offset
        )

@router.get("/run-backtest-query")
async def run_backtest_with_params(
    from_date: date = Query(default=date(2025, 7, 14), description="Start date (YYYY-MM-DD)"),
    to_date: date = Query(default=date(2025, 7, 14), description="End date (YYYY-MM-DD)"),
    initial_capital: float = Query(default=500000, description="Initial capital"),
    lot_size: int = Query(default=75, description="Lot size (75 for NIFTY)"),
    lots_to_trade: int = Query(default=10, description="Number of lots to trade"),
    use_hedging: bool = Query(default=True, description="Use hedging"),
    hedge_offset: int = Query(default=200, description="Hedge offset in points"),
    commission_per_lot: float = Query(default=40, description="Commission per lot"),
    signal_s1: bool = Query(default=True, description="Test signal S1"),
    signal_s2: bool = Query(default=True, description="Test signal S2"),
    signal_s3: bool = Query(default=True, description="Test signal S3"),
    signal_s4: bool = Query(default=True, description="Test signal S4"),
    signal_s5: bool = Query(default=True, description="Test signal S5"),
    signal_s6: bool = Query(default=True, description="Test signal S6"),
    signal_s7: bool = Query(default=True, description="Test signal S7"),
    signal_s8: bool = Query(default=True, description="Test signal S8")
) -> Dict:
    """
    Run backtest with custom parameters - accepts user input in Swagger
    
    This endpoint bypasses the DI container to avoid caching issues.
    All parameters can be customized in Swagger UI.
    """
    
    # Build signals list based on selections
    signals_to_test = []
    if signal_s1: signals_to_test.append("S1")
    if signal_s2: signals_to_test.append("S2")
    if signal_s3: signals_to_test.append("S3")
    if signal_s4: signals_to_test.append("S4")
    if signal_s5: signals_to_test.append("S5")
    if signal_s6: signals_to_test.append("S6")
    if signal_s7: signals_to_test.append("S7")
    if signal_s8: signals_to_test.append("S8")
    
    # Create request object
    request = BacktestRequest(
        from_date=from_date,
        to_date=to_date,
        initial_capital=initial_capital,
        lot_size=lot_size,
        lots_to_trade=lots_to_trade,
        signals_to_test=signals_to_test,
        use_hedging=use_hedging,
        hedge_offset=hedge_offset,
        commission_per_lot=commission_per_lot,
        slippage_percent=0.001
    )
    
    # Use the direct implementation
    return await run_backtest_direct(request)