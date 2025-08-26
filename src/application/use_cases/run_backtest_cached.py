"""
Cached version of backtest that ONLY uses database data
No API calls - prevents rate limiting issues
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
from uuid import uuid4

from src.domain.entities.trade import Trade, TradeStatus
from src.domain.entities.backtest import BacktestRun, BacktestTrade, BacktestPosition
from src.domain.services.signal_evaluator import SignalEvaluator
from src.domain.services.option_pricing import OptionPricingService
from src.domain.value_objects.signal_types import SignalType
from src.infrastructure.database.models import NiftyIndexDataHourly, OptionsData
from src.infrastructure.database.db_manager import DatabaseManager
from sqlalchemy import and_

logger = logging.getLogger(__name__)


class RunBacktestCachedUseCase:
    """Backtest use case that ONLY uses cached database data"""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        signal_evaluator: SignalEvaluator,
        option_pricing: OptionPricingService
    ):
        self.db_manager = db_manager
        self.signal_evaluator = signal_evaluator
        self.option_pricing = option_pricing
        
    async def execute(
        self,
        from_date: datetime,
        to_date: datetime,
        signals_to_test: List[str],
        lot_size: int = 10,
        stop_loss_amount: Optional[float] = None,
        target_profit_amount: Optional[float] = None,
        use_hedging: bool = True,
        hedge_strike_offset: int = 200,
        initial_capital: float = 500000.0
    ) -> BacktestRun:
        """Execute backtest using ONLY cached database data"""
        
        logger.info(f"Starting CACHED backtest from {from_date} to {to_date}")
        logger.info(f"Using ONLY database data - no API calls")
        
        # Create backtest run
        backtest_id = str(uuid4())
        backtest_run = BacktestRun(
            id=backtest_id,
            from_date=from_date,
            to_date=to_date,
            signals_to_test=signals_to_test,
            lot_size=lot_size,
            initial_capital=initial_capital,
            use_hedging=use_hedging,
            hedge_strike_offset=hedge_strike_offset,
            stop_loss_amount=stop_loss_amount,
            target_profit_amount=target_profit_amount
        )
        
        # Check data availability BEFORE starting
        if not self._check_data_availability(from_date, to_date):
            logger.warning("Insufficient data in database for the requested period")
            # Return empty backtest result
            backtest_run.status = "insufficient_data"
            return backtest_run
        
        # Process each trading day
        current_date = from_date
        open_trades: List[Trade] = []
        capital = initial_capital
        signal_triggered_this_week = False
        
        while current_date <= to_date:
            # Skip weekends
            if current_date.weekday() in [5, 6]:
                current_date += timedelta(days=1)
                continue
            
            # Process hourly bars from 9:15 to 15:15
            for hour in range(9, 16):
                for minute in [15]:
                    if hour == 9 and minute < 15:
                        continue
                    if hour == 15 and minute > 15:
                        continue
                    
                    bar_time = current_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    # Get hourly data from database
                    with self.db_manager.get_session() as session:
                        hourly_data = session.query(NiftyIndexDataHourly).filter(
                            NiftyIndexDataHourly.timestamp == bar_time
                        ).first()
                        
                        if not hourly_data:
                            continue
                        
                        # Evaluate signals
                        if not signal_triggered_this_week and not open_trades:
                            signal_result = self.signal_evaluator.evaluate(bar_time)
                            
                            if signal_result and signal_result.signal_type.value in signals_to_test:
                                logger.info(f"Signal {signal_result.signal_type.value} triggered at {bar_time}")
                                
                                # Open trade
                                trade = self._open_trade_cached(
                                    signal_result.signal_type,
                                    signal_result.strike_price,
                                    bar_time,
                                    hourly_data.close,
                                    lot_size,
                                    use_hedging,
                                    hedge_strike_offset
                                )
                                
                                if trade:
                                    open_trades.append(trade)
                                    signal_triggered_this_week = True
                                    backtest_run.add_trade(trade)
                        
                        # Check exits for open trades
                        for trade in open_trades[:]:
                            should_exit, exit_reason = self._check_exit_conditions_cached(
                                trade, bar_time, hourly_data.close,
                                stop_loss_amount, target_profit_amount
                            )
                            
                            if should_exit:
                                self._close_trade_cached(trade, bar_time, hourly_data.close, exit_reason)
                                open_trades.remove(trade)
                                capital += trade.total_pnl
            
            # Reset weekly flag on Monday
            if current_date.weekday() == 0:
                signal_triggered_this_week = False
            
            current_date += timedelta(days=1)
        
        # Close any remaining open trades
        for trade in open_trades:
            self._close_trade_cached(trade, to_date, None, "BACKTEST_END")
            capital += trade.total_pnl
        
        # Calculate final metrics
        backtest_run.final_capital = capital
        backtest_run.total_pnl = capital - initial_capital
        backtest_run.calculate_metrics()
        backtest_run.status = "completed"
        
        logger.info(f"Cached backtest completed. Total P&L: {backtest_run.total_pnl}")
        
        return backtest_run
    
    def _check_data_availability(self, from_date: datetime, to_date: datetime) -> bool:
        """Check if we have sufficient data in database"""
        with self.db_manager.get_session() as session:
            # Check NIFTY data
            nifty_count = session.query(NiftyIndexDataHourly).filter(
                and_(
                    NiftyIndexDataHourly.timestamp >= from_date,
                    NiftyIndexDataHourly.timestamp <= to_date
                )
            ).count()
            
            if nifty_count < 10:  # Need at least some data
                logger.warning(f"Only {nifty_count} NIFTY data points available")
                return False
            
            # Check options data
            options_count = session.query(OptionsData).filter(
                and_(
                    OptionsData.date >= from_date.date(),
                    OptionsData.date <= to_date.date()
                )
            ).count()
            
            if options_count < 100:  # Need reasonable options data
                logger.warning(f"Only {options_count} options data points available")
                return False
            
            return True
    
    def _open_trade_cached(
        self,
        signal_type: SignalType,
        strike: int,
        entry_time: datetime,
        spot_price: float,
        lot_size: int,
        use_hedging: bool,
        hedge_offset: int
    ) -> Optional[BacktestTrade]:
        """Open trade using cached data only"""
        
        # Get option prices from database
        with self.db_manager.get_session() as session:
            # Determine option type based on signal
            if signal_type in [SignalType.S1, SignalType.S2, SignalType.S4, SignalType.S7]:
                option_type = 'PE'
            else:
                option_type = 'CE'
            
            # Get expiry (next Thursday)
            expiry = self._get_next_expiry(entry_time)
            
            # Get main position price
            main_option = session.query(OptionsData).filter(
                and_(
                    OptionsData.strike == strike,
                    OptionsData.option_type == option_type,
                    OptionsData.expiry == expiry.date(),
                    OptionsData.date == entry_time.date(),
                    OptionsData.time == entry_time.time()
                )
            ).first()
            
            if not main_option:
                logger.warning(f"No option data for {strike}{option_type} at {entry_time}")
                return None
            
            # Create trade
            trade = BacktestTrade(
                id=str(uuid4()),
                signal_type=signal_type.value,
                entry_time=entry_time,
                entry_spot_price=spot_price,
                stop_loss=float(strike),
                direction="BULLISH" if option_type == 'PE' else "BEARISH"
            )
            
            # Add main position
            main_position = BacktestPosition(
                type="MAIN",
                action="SELL",
                quantity=lot_size * 75,
                strike=strike,
                option_type=option_type,
                entry_price=float(main_option.ltp)
            )
            trade.positions.append(main_position)
            
            # Add hedge if required
            if use_hedging:
                hedge_strike = strike - hedge_offset if option_type == 'PE' else strike + hedge_offset
                
                hedge_option = session.query(OptionsData).filter(
                    and_(
                        OptionsData.strike == hedge_strike,
                        OptionsData.option_type == option_type,
                        OptionsData.expiry == expiry.date(),
                        OptionsData.date == entry_time.date(),
                        OptionsData.time == entry_time.time()
                    )
                ).first()
                
                if hedge_option:
                    hedge_position = BacktestPosition(
                        type="HEDGE",
                        action="BUY",
                        quantity=lot_size * 75,
                        strike=hedge_strike,
                        option_type=option_type,
                        entry_price=float(hedge_option.ltp)
                    )
                    trade.positions.append(hedge_position)
            
            return trade
    
    def _check_exit_conditions_cached(
        self,
        trade: BacktestTrade,
        current_time: datetime,
        spot_price: float,
        stop_loss_amount: Optional[float],
        target_amount: Optional[float]
    ) -> tuple[bool, str]:
        """Check exit conditions using cached data"""
        
        # Check expiry
        expiry = self._get_next_expiry(trade.entry_time)
        if current_time >= expiry:
            return True, "EXPIRED"
        
        # Check stop loss (if spot crosses strike)
        if trade.stop_loss:
            if trade.direction == "BULLISH" and spot_price <= trade.stop_loss:
                return True, "STOP_LOSS"
            elif trade.direction == "BEARISH" and spot_price >= trade.stop_loss:
                return True, "STOP_LOSS"
        
        # Check P&L based exits if amounts are set
        if stop_loss_amount or target_amount:
            current_pnl = self._calculate_current_pnl_cached(trade, current_time)
            
            if stop_loss_amount and current_pnl <= -abs(stop_loss_amount):
                return True, "STOP_LOSS_AMOUNT"
            
            if target_amount and current_pnl >= abs(target_amount):
                return True, "TARGET_PROFIT"
        
        return False, ""
    
    def _close_trade_cached(
        self,
        trade: BacktestTrade,
        exit_time: datetime,
        spot_price: Optional[float],
        exit_reason: str
    ):
        """Close trade using cached data"""
        
        trade.exit_time = exit_time
        trade.outcome = exit_reason
        
        if spot_price:
            trade.exit_spot_price = spot_price
        
        # Get exit prices for all positions
        with self.db_manager.get_session() as session:
            total_pnl = 0
            
            for position in trade.positions:
                # Get expiry
                expiry = self._get_next_expiry(trade.entry_time)
                
                # Get exit price
                exit_option = session.query(OptionsData).filter(
                    and_(
                        OptionsData.strike == position.strike,
                        OptionsData.option_type == position.option_type,
                        OptionsData.expiry == expiry.date(),
                        OptionsData.date == exit_time.date(),
                        OptionsData.time == exit_time.time()
                    )
                ).first()
                
                if exit_option:
                    position.exit_price = float(exit_option.ltp)
                else:
                    # Use intrinsic value at expiry
                    if exit_reason == "EXPIRED" and spot_price:
                        if position.option_type == 'CE':
                            position.exit_price = max(0, spot_price - position.strike)
                        else:
                            position.exit_price = max(0, position.strike - spot_price)
                    else:
                        position.exit_price = position.entry_price  # No change
                
                # Calculate P&L
                if position.action == "SELL":
                    position.pnl = (position.entry_price - position.exit_price) * position.quantity
                else:
                    position.pnl = (position.exit_price - position.entry_price) * position.quantity
                
                total_pnl += position.pnl
            
            trade.total_pnl = total_pnl
            trade.outcome = "WIN" if total_pnl > 0 else "LOSS"
    
    def _calculate_current_pnl_cached(self, trade: BacktestTrade, current_time: datetime) -> float:
        """Calculate current P&L using cached data"""
        
        with self.db_manager.get_session() as session:
            total_pnl = 0
            expiry = self._get_next_expiry(trade.entry_time)
            
            for position in trade.positions:
                current_option = session.query(OptionsData).filter(
                    and_(
                        OptionsData.strike == position.strike,
                        OptionsData.option_type == position.option_type,
                        OptionsData.expiry == expiry.date(),
                        OptionsData.date == current_time.date(),
                        OptionsData.time == current_time.time()
                    )
                ).first()
                
                if current_option:
                    current_price = float(current_option.ltp)
                    if position.action == "SELL":
                        pnl = (position.entry_price - current_price) * position.quantity
                    else:
                        pnl = (current_price - position.entry_price) * position.quantity
                    total_pnl += pnl
            
            return total_pnl
    
    def _get_next_expiry(self, date: datetime) -> datetime:
        """Get next Thursday expiry"""
        days_ahead = 3 - date.weekday()  # Thursday is 3
        if days_ahead <= 0:
            days_ahead += 7
        expiry = date + timedelta(days=days_ahead)
        return expiry.replace(hour=15, minute=30, second=0, microsecond=0)