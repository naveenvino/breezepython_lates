"""Working backtest router - completely bypasses DI container"""
from fastapi import APIRouter
from datetime import datetime
import asyncio

router = APIRouter()

@router.get("/july14")
async def backtest_july14():
    """Run backtest for July 14, 2025 - Direct implementation"""
    
    # Import at runtime to avoid caching
    from src.infrastructure.database.database_manager import get_db_manager
    from src.infrastructure.services.data_collection_service import DataCollectionService
    from src.infrastructure.services.breeze_service import BreezeService
    from src.infrastructure.services.option_pricing_service import OptionPricingService
    from src.application.use_cases.run_backtest import RunBacktestUseCase, BacktestParameters
    from src.infrastructure.database.models import BacktestRun, BacktestTrade, BacktestPosition
    
    # Create fresh instances
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    option_svc = OptionPricingService(data_svc, db)
    backtest = RunBacktestUseCase(data_svc, option_svc)
    
    # Fixed parameters
    params = BacktestParameters(
        from_date=datetime(2025, 7, 14, 9, 15),
        to_date=datetime(2025, 7, 14, 15, 30),
        initial_capital=500000,
        lot_size=75,
        lots_to_trade=10,
        signals_to_test=["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
        use_hedging=True,
        hedge_offset=200,
        commission_per_lot=40,
        slippage_percent=0.001
    )
    
    # Run backtest
    backtest_id = await backtest.execute(params)
    
    # Get results
    with db.get_session() as session:
        run = session.query(BacktestRun).filter_by(id=backtest_id).first()
        trades = session.query(BacktestTrade).filter_by(backtest_run_id=backtest_id).all()
        
        trade_details = []
        for trade in trades:
            positions = session.query(BacktestPosition).filter_by(trade_id=trade.id).all()
            
            pos_details = []
            for pos in positions:
                pos_details.append({
                    "type": pos.position_type,
                    "action": "SELL" if pos.quantity < 0 else "BUY",
                    "lots": abs(pos.quantity) // 75,
                    "quantity": abs(pos.quantity),
                    "strike": pos.strike_price,
                    "option_type": pos.option_type
                })
            
            trade_details.append({
                "signal": trade.signal_type,
                "entry_time": str(trade.entry_time),
                "outcome": trade.outcome.value,
                "pnl": float(trade.total_pnl) if trade.total_pnl else 0,
                "positions": pos_details
            })
        
        return {
            "backtest_id": backtest_id,
            "date": "2025-07-14",
            "total_trades": run.total_trades,
            "winning_trades": run.winning_trades, 
            "losing_trades": run.losing_trades,
            "win_rate": float(run.win_rate) if run.win_rate else 0,
            "initial_capital": float(run.initial_capital),
            "final_capital": float(run.final_capital),
            "total_pnl": float(run.total_pnl) if run.total_pnl else 0,
            "lot_size": run.lot_size,
            "lots_traded": run.lots_to_trade,
            "hedge_offset": run.hedge_offset,
            "trades": trade_details
        }