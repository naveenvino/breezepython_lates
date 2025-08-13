"""
Run Backtest with Progressive P&L Stop-Loss
Extended backtesting with P&L-based progressive stop-loss management
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import asyncio

from .run_backtest import RunBacktestUseCase, BacktestParameters
from ...domain.services.progressive_sl_manager import ProgressiveSLManager, PositionData
from ...infrastructure.database.models import BacktestTrade, BacktestPosition, BacktestStatus
from ...infrastructure.database.database_manager import get_db_manager

logger = logging.getLogger(__name__)


class ProgressiveSLBacktestParameters(BacktestParameters):
    """Extended parameters for progressive SL backtest"""
    
    def __init__(self, **kwargs):
        # Extract progressive SL specific parameters
        self.use_pnl_stop_loss = kwargs.pop('use_pnl_stop_loss', True)
        self.initial_sl_per_lot = kwargs.pop('initial_sl_per_lot', 6000)
        self.profit_trigger_percent = kwargs.pop('profit_trigger_percent', 40)
        self.day2_sl_factor = kwargs.pop('day2_sl_factor', 0.5)
        self.day3_breakeven = kwargs.pop('day3_breakeven', True)
        self.day4_profit_lock_percent = kwargs.pop('day4_profit_lock_percent', 5)
        self.track_5min_pnl = kwargs.pop('track_5min_pnl', True)
        
        # Initialize base parameters
        super().__init__(**kwargs)


class RunProgressiveSLBacktest(RunBacktestUseCase):
    """
    Extended backtest with P&L-based progressive stop-loss.
    Maintains both index-based and P&L-based stop-losses.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sl_managers = {}  # Track SL manager for each trade
        self.pnl_tracking_data = []  # Store 5-min P&L data
        self.sl_update_logs = []  # Store SL update history
        
    async def execute(self, params: ProgressiveSLBacktestParameters) -> str:
        """
        Execute backtest with progressive SL management
        
        Args:
            params: Extended backtest parameters with progressive SL config
            
        Returns:
            Backtest run ID
        """
        logger.info(f"Starting Progressive SL Backtest from {params.from_date} to {params.to_date}")
        logger.info(f"P&L SL Config: Initial={params.initial_sl_per_lot}/lot, "
                   f"Profit Trigger={params.profit_trigger_percent}%, "
                   f"Day2 Factor={params.day2_sl_factor}")
        
        # Store current parameters for use in other methods
        self._current_params = params
        
        # Run the base backtest with our extended logic
        backtest_id = await super().execute(params)
        
        # Save additional P&L tracking data
        if params.track_5min_pnl and self.pnl_tracking_data:
            await self._save_pnl_tracking_data(backtest_id)
        
        # Save SL update logs
        if self.sl_update_logs:
            await self._save_sl_update_logs(backtest_id)
        
        # Generate comparison report
        await self._generate_comparison_report(backtest_id, params)
        
        return backtest_id
    
    async def _check_stop_losses(
        self,
        open_trades: List[BacktestTrade],
        current_bar,
        backtest_run_id: str
    ) -> float:
        """
        Enhanced stop-loss checking with both index and P&L based SL
        
        Args:
            open_trades: List of open trades
            current_bar: Current market data bar
            backtest_run_id: Backtest run ID
            
        Returns:
            Total P&L from stopped trades
        """
        total_sl_pnl = 0
        trades_to_exit = []
        
        for trade in open_trades:
            # Get trade's SL manager (create if doesn't exist)
            if trade.id not in self.sl_managers:
                # Get trade parameters from the current run
                params = self._get_current_params()
                self.sl_managers[trade.id] = ProgressiveSLManager(
                    initial_sl_per_lot=params.initial_sl_per_lot,
                    lots=params.lots_to_trade,
                    profit_trigger_percent=params.profit_trigger_percent,
                    day2_sl_factor=params.day2_sl_factor,
                    day4_profit_lock_percent=params.day4_profit_lock_percent
                )
                
                # Calculate and store max profit receivable
                positions = await self._get_trade_positions(trade.id)
                main_pos = next(p for p in positions if p.position_type == "MAIN")
                hedge_pos = next(p for p in positions if p.position_type == "HEDGE")
                
                trade.max_profit_receivable = self.sl_managers[trade.id].calculate_max_profit_receivable(
                    float(main_pos.entry_price),
                    float(hedge_pos.entry_price),
                    abs(main_pos.quantity),
                    self._get_current_params().commission_per_lot
                )
            
            sl_manager = self.sl_managers[trade.id]
            
            # 1. Check existing index-based stop-loss
            index_sl_hit = False
            if trade.direction == "BEARISH":  # Sold CALL
                if current_bar.close >= float(trade.stop_loss_price):
                    index_sl_hit = True
                    trades_to_exit.append((trade, "Index SL Hit (CALL)"))
            else:  # BULLISH - Sold PUT
                if current_bar.close <= float(trade.stop_loss_price):
                    index_sl_hit = True
                    trades_to_exit.append((trade, "Index SL Hit (PUT)"))
            
            # 2. If index SL not hit, check P&L-based stop-loss
            if not index_sl_hit and self._get_current_params().use_pnl_stop_loss:
                # Get current option prices and calculate P&L
                current_pnl = await self._calculate_trade_pnl(trade, current_bar.timestamp)
                
                if current_pnl is not None:
                    # Check if P&L stop-loss is hit
                    pnl_sl_hit, sl_reason = sl_manager.check_stop_loss_hit(current_pnl)
                    
                    if pnl_sl_hit:
                        trades_to_exit.append((trade, sl_reason))
                    else:
                        # Update stop-loss progressively
                        days_elapsed = sl_manager.calculate_trading_days(
                            trade.entry_time,
                            current_bar.timestamp
                        )
                        
                        update_reason = sl_manager.update_stop_loss(
                            current_pnl,
                            trade.max_profit_receivable,
                            days_elapsed,
                            current_bar.timestamp
                        )
                        
                        if update_reason:
                            # Log the SL update
                            self.sl_update_logs.append({
                                "trade_id": trade.id,
                                "backtest_run_id": backtest_run_id,
                                "update_time": current_bar.timestamp,
                                "reason": update_reason,
                                "current_pnl": current_pnl,
                                "new_sl": sl_manager.current_sl,
                                "sl_stage": sl_manager.sl_stage.value,
                                "day_number": days_elapsed
                            })
                    
                    # Track 5-min P&L data if enabled
                    if self._get_current_params().track_5min_pnl:
                        self.pnl_tracking_data.append({
                            "trade_id": trade.id,
                            "backtest_run_id": backtest_run_id,
                            "timestamp": current_bar.timestamp,
                            "net_pnl": current_pnl,
                            "pnl_sl_level": sl_manager.current_sl,
                            "sl_stage": sl_manager.sl_stage.value,
                            "nifty_index": current_bar.close,
                            "days_since_entry": days_elapsed
                        })
        
        # Exit trades that hit stop-loss
        for trade, exit_reason in trades_to_exit:
            exit_pnl = await self._exit_trade_with_reason(trade, current_bar, exit_reason)
            total_sl_pnl += exit_pnl
            
            # Remove from open trades
            open_trades.remove(trade)
            
            # Clean up SL manager
            if trade.id in self.sl_managers:
                del self.sl_managers[trade.id]
        
        return total_sl_pnl
    
    async def _calculate_trade_pnl(
        self,
        trade: BacktestTrade,
        timestamp: datetime
    ) -> Optional[float]:
        """
        Calculate current P&L for a trade using 5-min options data
        
        Args:
            trade: Trade to calculate P&L for
            timestamp: Current timestamp
            
        Returns:
            Current P&L or None if data not available
        """
        try:
            # Get trade positions
            positions = await self._get_trade_positions(trade.id)
            
            # Convert to PositionData format
            position_data = []
            strikes_needed = {}
            
            for pos in positions:
                position_data.append(PositionData(
                    position_type=pos.position_type,
                    strike_price=pos.strike_price,
                    option_type=pos.option_type,
                    entry_price=float(pos.entry_price),
                    quantity=pos.quantity
                ))
                strikes_needed[(pos.strike_price, pos.option_type)] = True
            
            # Get current prices from 5-min options data
            current_prices = await self._get_option_prices_5min(
                list(strikes_needed.keys()),
                timestamp
            )
            
            if not current_prices:
                logger.warning(f"No option prices available for trade {trade.id} at {timestamp}")
                return None
            
            # Calculate P&L using the SL manager
            sl_manager = self.sl_managers.get(trade.id)
            if sl_manager:
                pnl = sl_manager.calculate_position_pnl(
                    position_data,
                    current_prices,
                    self._get_current_params().commission_per_lot
                )
                return pnl
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating P&L for trade {trade.id}: {e}")
            return None
    
    async def _get_option_prices_5min(
        self,
        strikes: List[Tuple[int, str]],
        timestamp: datetime
    ) -> Dict[Tuple[int, str], float]:
        """
        Get option prices from 5-min historical data
        
        Args:
            strikes: List of (strike_price, option_type) tuples
            timestamp: Timestamp to get prices for
            
        Returns:
            Dictionary mapping (strike, option_type) to price
        """
        prices = {}
        
        # Round to nearest 5-min interval
        minute = timestamp.minute
        rounded_minute = (minute // 5) * 5
        rounded_time = timestamp.replace(minute=rounded_minute, second=0, microsecond=0)
        
        from sqlalchemy import text
        
        with self.db_manager.get_session() as session:
            for strike, option_type in strikes:
                query = text("""
                SELECT TOP 1 [Close] as Price
                FROM OptionsHistoricalData
                WHERE Strike = :strike
                AND OptionType = :option_type
                AND Timestamp = :timestamp
                """)
                
                result = session.execute(
                    query,
                    {"strike": strike, "option_type": option_type, "timestamp": rounded_time}
                ).fetchone()
                
                if result:
                    prices[(strike, option_type)] = float(result.Price)
                else:
                    # Try to get nearest available price
                    nearest_price = await self._get_nearest_option_price(
                        session, strike, option_type, rounded_time
                    )
                    if nearest_price:
                        prices[(strike, option_type)] = nearest_price
        
        return prices
    
    async def _get_nearest_option_price(
        self,
        session,
        strike: int,
        option_type: str,
        target_time: datetime,
        max_time_diff_minutes: int = 15
    ) -> Optional[float]:
        """Get nearest available option price within time window"""
        from sqlalchemy import text
        
        query = text("""
        SELECT TOP 1 [Close] as Price, ABS(DATEDIFF(MINUTE, Timestamp, :target_time)) as TimeDiff
        FROM OptionsHistoricalData
        WHERE Strike = :strike
        AND OptionType = :option_type
        AND Timestamp BETWEEN DATEADD(MINUTE, -:max_diff, :target_time) 
                          AND DATEADD(MINUTE, :max_diff, :target_time)
        ORDER BY TimeDiff
        """)
        
        result = session.execute(
            query,
            {
                "strike": strike,
                "option_type": option_type,
                "target_time": target_time,
                "max_diff": max_time_diff_minutes
            }
        ).fetchone()
        
        if result:
            return float(result.Price)
        return None
    
    async def _get_trade_positions(self, trade_id: str) -> List[BacktestPosition]:
        """Get positions for a trade"""
        with self.db_manager.get_session() as session:
            return session.query(BacktestPosition).filter_by(trade_id=trade_id).all()
    
    async def _exit_trade_with_reason(
        self,
        trade: BacktestTrade,
        current_bar,
        exit_reason: str
    ) -> float:
        """Exit a trade and return the P&L"""
        # Calculate final P&L
        final_pnl = await self._calculate_trade_pnl(trade, current_bar.timestamp)
        
        if final_pnl is None:
            # Fallback to index-based calculation
            final_pnl = await self._calculate_index_based_pnl(trade, current_bar)
        
        # Update trade record
        trade.exit_time = current_bar.timestamp
        trade.index_price_at_exit = current_bar.close
        trade.exit_reason = exit_reason
        trade.total_pnl = Decimal(str(final_pnl))
        trade.outcome = "STOPPED" if "SL Hit" in exit_reason else "CLOSED"
        
        # Save to database
        with self.db_manager.get_session() as session:
            session.merge(trade)
            session.commit()
        
        logger.info(f"Trade {trade.id} exited: {exit_reason}, P&L: {final_pnl:.2f}")
        
        return final_pnl
    
    async def _save_pnl_tracking_data(self, backtest_id: str):
        """Save 5-min P&L tracking data to database"""
        if not self.pnl_tracking_data:
            return
        
        from sqlalchemy import text
        
        with self.db_manager.get_session() as session:
            for data in self.pnl_tracking_data:
                query = text("""
                INSERT INTO BacktestPnLTracking (
                    TradeId, BacktestRunId, Timestamp, 
                    MainLegStrike, MainLegPrice, HedgeLegStrike, HedgeLegPrice,
                    MainLegPnL, HedgeLegPnL, NetPnL,
                    IndexSLLevel, PnLSLLevel, SLStage,
                    NiftyIndex, DaysSinceEntry
                ) VALUES (
                    :trade_id, :backtest_run_id, :timestamp,
                    0, 0, 0, 0,
                    0, 0, :net_pnl,
                    0, :pnl_sl_level, :sl_stage,
                    :nifty_index, :days_since_entry
                )
                """)
                session.execute(query, data)
            session.commit()
        
        logger.info(f"Saved {len(self.pnl_tracking_data)} P&L tracking records")
    
    async def _save_sl_update_logs(self, backtest_id: str):
        """Save SL update history to database"""
        if not self.sl_update_logs:
            return
        
        from sqlalchemy import text
        
        with self.db_manager.get_session() as session:
            for log in self.sl_update_logs:
                query = text("""
                INSERT INTO BacktestSLUpdates (
                    TradeId, BacktestRunId, UpdateTime,
                    OldPnLSL, NewPnLSL, OldStage, NewStage,
                    CurrentPnL, MaxProfitReceivable, DayNumber, UpdateReason
                ) VALUES (
                    :trade_id, :backtest_run_id, :update_time,
                    0, :new_sl, '', :sl_stage,
                    :current_pnl, 0, :day_number, :reason
                )
                """)
                session.execute(query, log)
            session.commit()
        
        logger.info(f"Saved {len(self.sl_update_logs)} SL update records")
    
    async def _generate_comparison_report(self, backtest_id: str, params):
        """Generate comparison between with and without progressive SL"""
        # This would run a parallel backtest without progressive SL
        # and compare the results
        logger.info("Comparison report generation would be implemented here")
    
    def _get_current_params(self) -> ProgressiveSLBacktestParameters:
        """Get current backtest parameters (stored during execution)"""
        if hasattr(self, '_current_params'):
            return self._current_params
        else:
            # Return default parameters if not set
            logger.warning("Current parameters not set, using defaults")
            return ProgressiveSLBacktestParameters(
                from_date=datetime.now(),
                to_date=datetime.now()
            )
    
    async def _calculate_index_based_pnl(self, trade, current_bar) -> float:
        """Fallback P&L calculation based on index movement"""
        # Simplified calculation when options data not available
        return -self._get_current_params().initial_sl_per_lot * self._get_current_params().lots_to_trade