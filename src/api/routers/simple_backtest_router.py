"""Simple backtest router that works"""
from fastapi import APIRouter
from datetime import datetime
from typing import Dict
import asyncio

router = APIRouter()

@router.get("/run")
async def run_simple_backtest() -> Dict:
    """Run backtest for July 14, 2025 with 10 lots"""
    
    # Import everything we need
    from ...infrastructure.database.database_manager import get_db_manager
    from ...infrastructure.services.data_collection_service import DataCollectionService
    from ...infrastructure.services.breeze_service import BreezeService
    from ...infrastructure.services.option_pricing_service import OptionPricingService
    from ...application.use_cases.run_backtest import RunBacktestUseCase, BacktestParameters
    from ...infrastructure.database.models import BacktestRun, BacktestTrade, BacktestPosition
    
    # Setup services
    db = get_db_manager()
    breeze = BreezeService()
    data_svc = DataCollectionService(breeze, db)
    option_svc = OptionPricingService(data_svc, db)
    backtest = RunBacktestUseCase(data_svc, option_svc)
    
    # Parameters for July 14, 2025 with 10 lots
    params = BacktestParameters(
        from_date=datetime(2025, 7, 14, 9, 15),
        to_date=datetime(2025, 7, 14, 15, 30),
        initial_capital=500000,
        lot_size=75,
        lots_to_trade=10,  # 10 lots = 750 quantity
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
        trades = session.query(BacktestTrade).filter_by(
            backtest_run_id=backtest_id
        ).all()
        
        trade_details = []
        for trade in trades:
            positions = session.query(BacktestPosition).filter_by(
                trade_id=trade.id
            ).all()
            
            position_info = []
            for pos in positions:
                action = "SELL" if pos.quantity < 0 else "BUY"
                position_info.append({
                    "type": pos.position_type,
                    "action": action,
                    "lots": abs(pos.quantity) // 75,
                    "quantity": abs(pos.quantity),
                    "strike": pos.strike_price,
                    "option_type": pos.option_type,
                    "entry_price": float(pos.entry_price),
                    "exit_price": float(pos.exit_price) if pos.exit_price else None,
                    "pnl": float(pos.net_pnl) if pos.net_pnl else None
                })
            
            trade_details.append({
                "signal": trade.signal_type,
                "entry_time": trade.entry_time.strftime("%Y-%m-%d %H:%M"),
                "outcome": trade.outcome.value,
                "pnl": float(trade.total_pnl) if trade.total_pnl else 0,
                "positions": position_info
            })
        
        return {
            "success": True,
            "backtest_id": backtest_id,
            "date": "2025-07-14",
            "configuration": {
                "lot_size": run.lot_size,
                "lots_traded": run.lots_to_trade,
                "total_quantity_per_trade": run.lot_size * run.lots_to_trade,
                "hedge_offset": run.hedge_offset,
                "commission_per_lot": float(run.commission_per_lot),
                "initial_capital": float(run.initial_capital)
            },
            "results": {
                "total_trades": run.total_trades,
                "winning_trades": run.winning_trades,
                "losing_trades": run.losing_trades,
                "win_rate": float(run.win_rate) if run.win_rate else 0,
                "final_capital": float(run.final_capital),
                "total_pnl": float(run.total_pnl) if run.total_pnl else 0
            },
            "trades": trade_details
        }