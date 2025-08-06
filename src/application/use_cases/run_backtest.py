"""
Run Backtest Use Case
Main backtesting logic that orchestrates the entire backtest process
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import asyncio

from ...domain.value_objects.signal_types import SignalType, BarData
from ...domain.services.signal_evaluator import SignalEvaluator
from ...domain.services.weekly_context_manager import WeeklyContextManager
from ...domain.services.margin_calculator import MarginCalculator
from ...domain.services.risk_manager import RiskManager
from ...domain.services.market_calendar import MarketCalendar
from ...infrastructure.services.data_collection_service import DataCollectionService
from ...infrastructure.services.option_pricing_service import OptionPricingService
from ...infrastructure.services.holiday_service import HolidayService
from ...infrastructure.validation.market_data_validator import MarketDataValidator
from ...infrastructure.database.models import (
    BacktestRun, BacktestTrade, BacktestPosition, BacktestDailyResult,
    BacktestStatus, NiftyIndexData, NiftyIndexDataHourly, TradeOutcome
)
from ...infrastructure.database.database_manager import get_db_manager


logger = logging.getLogger(__name__)


class BacktestParameters:
    """Parameters for running a backtest"""
    def __init__(
        self,
        from_date: datetime,
        to_date: datetime,
        initial_capital: float = 500000,
        lot_size: int = 75,  # Changed to 75 as per requirement
        lots_to_trade: int = 10,  # Default 10 lots = 750 quantity
        lots_per_signal: Dict[str, int] = None,  # Custom lots per signal
        signals_to_test: List[str] = None,
        use_hedging: bool = True,
        hedge_offset: int = 200,
        commission_per_lot: float = 40,
        slippage_percent: float = 0.001
    ):
        self.from_date = from_date
        self.to_date = to_date
        self.initial_capital = initial_capital
        self.lot_size = lot_size
        self.lots_to_trade = lots_to_trade
        self.lots_per_signal = lots_per_signal or {}  # e.g., {"S1": 10, "S2": 5, ...}
        self.signals_to_test = signals_to_test or ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
        self.use_hedging = use_hedging
        self.hedge_offset = hedge_offset
        self.commission_per_lot = commission_per_lot
        self.slippage_percent = slippage_percent


class RunBacktestUseCase:
    """
    Use case for running a complete backtest
    """
    
    def __init__(
        self,
        data_collection_service: DataCollectionService,
        option_pricing_service: OptionPricingService,
        enable_risk_management: bool = False  # Disable by default for backtesting
    ):
        self.data_collection = data_collection_service
        self.option_pricing = option_pricing_service
        self.signal_evaluator = SignalEvaluator()
        self.context_manager = WeeklyContextManager()
        self.holiday_service = HolidayService()
        self.db_manager = get_db_manager()
        self.enable_risk_management = enable_risk_management
        
        # Initialize new services only if risk management is enabled
        if enable_risk_management:
            self.margin_calculator = MarginCalculator(lot_size=75)
            self.risk_manager = None  # Will be initialized with parameters
            self.market_calendar = MarketCalendar()
            self.data_validator = MarketDataValidator(max_staleness_minutes=525600)  # 1 year for backtesting
        else:
            self.margin_calculator = None
            self.risk_manager = None
            self.market_calendar = None
            self.data_validator = None
    
    async def execute(self, params: BacktestParameters) -> str:
        """
        Execute backtest and return backtest run ID
        
        Args:
            params: Backtest parameters
            
        Returns:
            Backtest run ID
        """
        logger.info(f"Starting backtest from {params.from_date} to {params.to_date}")
        
        # Initialize risk manager with initial capital if enabled
        if self.enable_risk_management:
            self.risk_manager = RiskManager(
                initial_capital=Decimal(str(params.initial_capital)),
                lot_size=params.lot_size
            )
        
        # Create backtest run record
        backtest_run = await self._create_backtest_run(params)
        
        try:
            # Update status to running
            await self._update_backtest_status(backtest_run.id, BacktestStatus.RUNNING)
            
            # Ensure data is available
            await self._ensure_data_available(params.from_date, params.to_date)
            
            # Get NIFTY data for the period (including buffer for previous week)
            buffer_start = params.from_date - timedelta(days=7)
            nifty_data = await self.data_collection.get_nifty_data(
                buffer_start, params.to_date
            )
            
            if not nifty_data:
                raise ValueError("No NIFTY data available for the specified period")
            
            # Run backtest
            results = await self._run_backtest_logic(
                backtest_run, nifty_data, params
            )
            
            # Update backtest run with results
            await self._update_backtest_results(backtest_run.id, results)
            
            # Update status to completed
            await self._update_backtest_status(backtest_run.id, BacktestStatus.COMPLETED)
            
            logger.info(f"Backtest completed successfully. ID: {backtest_run.id}")
            return backtest_run.id
            
        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            await self._update_backtest_status(
                backtest_run.id, BacktestStatus.FAILED, str(e)
            )
            raise
    
    async def _create_backtest_run(self, params: BacktestParameters) -> BacktestRun:
        """Create backtest run record in database"""
        backtest_run = BacktestRun(
            name=f"Backtest {params.from_date.date()} to {params.to_date.date()}",
            from_date=params.from_date,
            to_date=params.to_date,
            initial_capital=Decimal(str(params.initial_capital)),
            lot_size=params.lot_size,
            lots_to_trade=params.lots_to_trade,
            signals_to_test=",".join(params.signals_to_test),
            use_hedging=params.use_hedging,
            hedge_offset=params.hedge_offset,
            commission_per_lot=Decimal(str(params.commission_per_lot)),
            slippage_percent=Decimal(str(params.slippage_percent)),
            status=BacktestStatus.PENDING
        )
        
        with self.db_manager.get_session() as session:
            session.add(backtest_run)
            session.commit()
            session.refresh(backtest_run)
        
        return backtest_run
    
    async def _ensure_data_available(self, from_date: datetime, to_date: datetime):
        """Ensure all required data is available"""
        # Add buffer for previous week data needed for zone calculation
        buffer_start = from_date - timedelta(days=7)
        
        # Ensure NIFTY data - don't fetch from API during backtesting
        added = await self.data_collection.ensure_nifty_data_available(
            buffer_start, to_date, fetch_missing=False
        )
        
        if added > 0:
            logger.info(f"Added {added} NIFTY data records")
        
        # Get all potential expiry dates in the period
        expiry_dates = self._get_expiry_dates(from_date, to_date)
        
        # Get required strikes (only fetch around current NIFTY level)
        # Get current NIFTY level from recent data
        current_nifty = 25000  # Default fallback
        with self.db_manager.get_session() as session:
            recent_data = session.query(NiftyIndexDataHourly).filter(
                NiftyIndexDataHourly.timestamp <= to_date
            ).order_by(NiftyIndexDataHourly.timestamp.desc()).first()
            if recent_data:
                current_nifty = int(recent_data.close)
        
        # Only fetch strikes within reasonable range (±1000 points from current level)
        # This covers main positions and hedges
        min_strike = ((current_nifty - 1000) // 50) * 50
        max_strike = ((current_nifty + 1000) // 50) * 50
        strikes = list(range(min_strike, max_strike + 50, 50))
        
        # Ensure options data for all expiries
        for expiry in expiry_dates:
            # Only fetch data up to expiry date
            end_date = min(expiry, to_date)
            added = await self.data_collection.ensure_options_data_available(
                from_date, end_date, strikes, [expiry], fetch_missing=False
            )
            
            if added > 0:
                logger.info(f"Added {added} options data records for expiry {expiry.date()}")
    
    def _get_expiry_dates(self, from_date: datetime, to_date: datetime) -> List[datetime]:
        """Get all Thursday expiry dates in the period"""
        expiry_dates = []
        current = from_date
        
        while current <= to_date:
            expiry = self.context_manager.get_next_expiry(current)
            if expiry <= to_date and expiry not in expiry_dates:
                expiry_dates.append(expiry)
            current = expiry + timedelta(days=1)
        
        return expiry_dates
    
    async def _run_backtest_logic(
        self,
        backtest_run: BacktestRun,
        nifty_data: List[NiftyIndexDataHourly],
        params: BacktestParameters
    ) -> Dict:
        """Main backtest logic"""
        # Initialize tracking variables
        current_capital = float(params.initial_capital)
        open_trades: List[BacktestTrade] = []
        all_trades: List[BacktestTrade] = []
        daily_results: List[BacktestDailyResult] = []
        
        # Track daily P&L
        current_date = None
        daily_starting_capital = current_capital
        
        # Process each hourly bar
        for i, data_point in enumerate(nifty_data):
            current_bar = self.context_manager.create_bar_from_nifty_data(data_point)
            
            # Skip non-market hours
            if not self.context_manager.is_market_hours(current_bar.timestamp):
                continue
                
            # Skip holidays
            if self.holiday_service.is_trading_holiday(current_bar.timestamp.date(), "NSE"):
                logger.debug(f"Skipping {current_bar.timestamp.date()} - Trading holiday")
                continue
                
            # Validate NIFTY data if validator is enabled
            if self.data_validator:
                prev_close = nifty_data[i-1].close if i > 0 else None
                validation_result = self.data_validator.validate_nifty_data(
                    timestamp=current_bar.timestamp,
                    open_price=current_bar.open,
                    high_price=current_bar.high,
                    low_price=current_bar.low,
                    close_price=current_bar.close,
                    volume=data_point.volume if hasattr(data_point, 'volume') else 1000,
                    prev_close=float(prev_close) if prev_close else None
                )
                
                if not validation_result.is_valid:
                    logger.warning(f"Invalid NIFTY data at {current_bar.timestamp}: {validation_result.error_message}")
                    continue
            
            # Check for new day
            if current_date != current_bar.timestamp.date():
                # Save previous day's results
                if current_date:
                    daily_result = BacktestDailyResult(
                        backtest_run_id=backtest_run.id,
                        date=datetime.combine(current_date, datetime.min.time()),
                        starting_capital=Decimal(str(daily_starting_capital)),
                        ending_capital=Decimal(str(current_capital)),
                        daily_pnl=Decimal(str(current_capital - daily_starting_capital)),
                        daily_return_percent=Decimal(str(
                            ((current_capital - daily_starting_capital) / daily_starting_capital) * 100
                        )),
                        trades_opened=len([t for t in all_trades if t.entry_time.date() == current_date]),
                        trades_closed=len([t for t in all_trades if t.exit_time and t.exit_time.date() == current_date]),
                        open_positions=len(open_trades)
                    )
                    daily_results.append(daily_result)
                
                current_date = current_bar.timestamp.date()
                daily_starting_capital = current_capital
            
            # Get previous week data for context
            # We need at least previous week's data (5 days * 7 hours = 35 bars)
            if i < 35:  # Changed from 7*6=42 to 35
                continue
            
            prev_week_data = self.context_manager.get_previous_week_data(
                current_bar.timestamp, nifty_data[:i]
            )
            
            if not prev_week_data:
                continue
            
            # Update weekly context
            context = self.context_manager.update_context(current_bar, prev_week_data)
            
            # Debug logging for first few bars of Monday
            if current_bar.timestamp.date() == datetime(2025, 7, 14).date() and i < 40:
                logger.info(f"DEBUG Bar {i}: {current_bar.timestamp}, Open: {current_bar.open}, Close: {current_bar.close}")
                if context.zones:
                    logger.info(f"  Zones - Support: {context.zones.lower_zone_bottom:.2f}-{context.zones.lower_zone_top:.2f}")
                logger.info(f"  Weekly bars count: {len(context.weekly_bars)}")
                logger.info(f"  Open trades: {len(open_trades)}, Signal triggered this week: {context.signal_triggered_this_week}")
            
            # Check for expiry and close positions
            expiry_pnl = await self._check_and_close_expiry_positions(
                open_trades, current_bar, backtest_run.id
            )
            current_capital += expiry_pnl
            
            # Check stop losses
            sl_pnl = await self._check_stop_losses(
                open_trades, current_bar, backtest_run.id
            )
            current_capital += sl_pnl
            
            # Evaluate signals (only if no open position)
            if not open_trades and not context.signal_triggered_this_week:
                # Debug logging
                if i < 10:  # Log first 10 bars
                    logger.info(f"Bar {i+1}: {current_bar.timestamp}, evaluating signals...")
                signal_result = self.signal_evaluator.evaluate_all_signals(
                    current_bar, context, current_bar.timestamp
                )
                
                # Debug log for Monday
                if current_bar.timestamp.date() == datetime(2025, 7, 14).date():
                    logger.info(f"  Signal evaluation result: {signal_result.is_triggered}")
                    if signal_result.is_triggered:
                        logger.info(f"    Signal: {signal_result.signal_type}, Strike: {signal_result.strike_price}")
                
                if signal_result.is_triggered:
                    logger.info(f"Signal detected: {signal_result.signal_type.value}")
                    logger.info(f"Signals to test: {params.signals_to_test}")
                    logger.info(f"Signal in test list: {signal_result.signal_type.value in params.signals_to_test}")
                    
                if signal_result.is_triggered and signal_result.signal_type.value in params.signals_to_test:
                    logger.info(f"SIGNAL TRIGGERED! Type: {signal_result.signal_type}, Strike: {signal_result.strike_price}")
                    # Open new trade
                    trade = await self._open_trade(
                        backtest_run.id,
                        signal_result,
                        current_bar,
                        context,
                        params
                    )
                    
                    if trade:
                        logger.info(f"Trade created successfully with ID: {trade.id}")
                        open_trades.append(trade)
                        all_trades.append(trade)
                        
                        # For option selling, capital doesn't change when entering trade
                        # Premium is not realized until trade is closed
                        # Margin requirements are handled separately in real trading
                    else:
                        logger.error("Failed to create trade despite signal trigger!")
        
        # Close any remaining open trades at end
        for trade in open_trades:
            if trade.outcome == TradeOutcome.OPEN:
                await self._close_trade(
                    trade, 
                    nifty_data[-1].timestamp,
                    float(nifty_data[-1].close),
                    TradeOutcome.EXPIRED,
                    "Backtest ended"
                )
        
        # Calculate final metrics
        total_trades = len(all_trades)
        winning_trades = len([t for t in all_trades if t.outcome == TradeOutcome.WIN])
        losing_trades = len([t for t in all_trades if t.outcome == TradeOutcome.LOSS])
        
        results = {
            'final_capital': current_capital,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
            'total_pnl': current_capital - float(params.initial_capital),
            'total_return_percent': ((current_capital - float(params.initial_capital)) / float(params.initial_capital)) * 100,
            'trades': all_trades,
            'daily_results': daily_results
        }
        
        # Calculate max drawdown
        equity_curve = [float(params.initial_capital)]
        for daily in daily_results:
            equity_curve.append(float(daily.ending_capital))
        
        max_drawdown = self._calculate_max_drawdown(equity_curve)
        results['max_drawdown'] = max_drawdown['value']
        results['max_drawdown_percent'] = max_drawdown['percent']
        
        return results
    
    async def _open_trade(
        self,
        backtest_run_id: str,
        signal_result,
        current_bar: BarData,
        context,
        params: BacktestParameters
    ) -> Optional[BacktestTrade]:
        """Open a new trade based on signal"""
        logger.info(f"_open_trade called for {signal_result.signal_type} at {current_bar.timestamp}")
        
        # Market hours validation if enabled
        if self.market_calendar and not self.market_calendar.is_market_open(current_bar.timestamp):
            logger.warning(f"Cannot open trade outside market hours: {current_bar.timestamp}")
            return None
            
        try:
            # Get expiry for current week
            expiry = self.context_manager.get_expiry_for_week(self.context_manager.current_week_start)
            logger.info(f"Expiry for trade: {expiry}")
            
            # Use strike from signal result (calculated based on stop loss)
            main_strike = signal_result.strike_price
            
            # For option selling, stop loss is the main strike price itself
            actual_stop_loss = float(main_strike)
            
            # Calculate hedge strike based on signal direction
            if signal_result.signal_type.is_bullish:
                # For PE sell, hedge is further OTM (lower strike)
                hedge_strike = main_strike - params.hedge_offset
            else:
                # For CE sell, hedge is further OTM (higher strike)
                hedge_strike = main_strike + params.hedge_offset
            
            # Create trade record with zone information
            # Entry time is at the close of next candle (signal at 10:15, enter at 11:15 close)
            entry_time = current_bar.timestamp + timedelta(hours=1)
            
            trade = BacktestTrade(
                backtest_run_id=backtest_run_id,
                week_start_date=self.context_manager.current_week_start,
                signal_type=signal_result.signal_type.value,
                direction=signal_result.direction.value,
                entry_time=entry_time,
                index_price_at_entry=Decimal(str(current_bar.close)),
                signal_trigger_price=Decimal(str(signal_result.entry_price)),
                stop_loss_price=Decimal(str(actual_stop_loss)),  # Use strike as stop loss
                outcome=TradeOutcome.OPEN,
                # Zone information
                resistance_zone_top=Decimal(str(context.zones.upper_zone_top)),
                resistance_zone_bottom=Decimal(str(context.zones.upper_zone_bottom)),
                support_zone_top=Decimal(str(context.zones.lower_zone_top)),
                support_zone_bottom=Decimal(str(context.zones.lower_zone_bottom)),
                # Market bias
                bias_direction=context.bias.bias.value,
                bias_strength=Decimal(str(context.bias.strength)),
                # Weekly extremes
                weekly_max_high=Decimal(str(context.weekly_max_high)),
                weekly_min_low=Decimal(str(context.weekly_min_low)),
                # First bar details (if available)
                first_bar_open=Decimal(str(context.first_hour_bar.open)) if context.first_hour_bar else None,
                first_bar_close=Decimal(str(context.first_hour_bar.close)) if context.first_hour_bar else None,
                first_bar_high=Decimal(str(context.first_hour_bar.high)) if context.first_hour_bar else None,
                first_bar_low=Decimal(str(context.first_hour_bar.low)) if context.first_hour_bar else None,
                # Distance metrics
                distance_to_resistance=Decimal(str(context.bias.distance_to_resistance)),
                distance_to_support=Decimal(str(context.bias.distance_to_support))
            )
            
            # Get option prices first to validate we can create the trade
            option_type = signal_result.option_type
            
            # Main position (sell)
            # Use current bar timestamp for price lookup (data availability)
            # but entry_time for trade record (candle close)
            main_price = await self.option_pricing.get_option_price_at_time(
                current_bar.timestamp, main_strike, option_type, expiry
            )
            
            if not main_price:
                logger.warning(f"No option price found for main position {main_strike} {option_type} at {current_bar.timestamp}")
                return None  # Cannot create trade without option data
            
            # Hedge position (buy) if enabled
            hedge_price = None
            if params.use_hedging:
                hedge_price = await self.option_pricing.get_option_price_at_time(
                    current_bar.timestamp, hedge_strike, option_type, expiry
                )
                
                if not hedge_price:
                    logger.warning(f"No option price found for hedge position {hedge_strike} {option_type} at {current_bar.timestamp}")
                    return None  # Cannot create trade without hedge data when hedging is enabled
            
            # Validate option prices if validator is enabled
            if self.data_validator:
                validation_result = self.data_validator.validate_option_price(
                    timestamp=current_bar.timestamp,
                    strike=main_strike,
                    option_type=option_type,
                    spot_price=current_bar.close,
                    option_price=main_price
                )
                
                if not validation_result.is_valid:
                    logger.warning(f"Option price validation failed: {validation_result.error_message}")
                    return None
                
            # Skip margin calculations and risk checks when risk management is disabled
            # This matches the original backtest behavior
            if self.enable_risk_management and self.margin_calculator and self.risk_manager:
                # Calculate margin requirement
                if params.use_hedging:
                    margin_req = self.margin_calculator.get_margin_for_strategy(
                        strategy_type=f"{'put' if option_type == 'PE' else 'call'}_spread",
                        spot_price=current_bar.close,
                        strikes={'main': main_strike, 'hedge': hedge_strike},
                        lots=params.lots_to_trade
                    )
                else:
                    margin_req = self.margin_calculator.get_margin_for_strategy(
                        strategy_type=f"naked_{'put' if option_type == 'PE' else 'call'}",
                        spot_price=current_bar.close,
                        strikes={'main': main_strike},
                        lots=params.lots_to_trade
                    )
                
                # Calculate position value and potential loss
                position_value = Decimal(str(main_price * params.lot_size * params.lots_to_trade))
                stop_loss_distance = abs(actual_stop_loss - current_bar.close)
                potential_loss = Decimal(str(stop_loss_distance * params.lot_size * params.lots_to_trade))
                
                # Risk management checks
                logger.info(f"Margin check: Required={margin_req.total_margin}, Available={self.risk_manager.current_capital}")
                if margin_req.total_margin > self.risk_manager.current_capital:
                    logger.warning(f"Insufficient capital for margin. Required: {margin_req.total_margin}, Available: {self.risk_manager.current_capital}")
                    return None
            
            # Save trade to database first to get ID
            with self.db_manager.get_session() as session:
                session.add(trade)
                session.commit()
                session.refresh(trade)
                
                # Now create positions with the trade ID
                main_position = BacktestPosition(
                    trade_id=trade.id,
                    position_type="MAIN",
                    option_type=option_type,
                    strike_price=main_strike,
                    expiry_date=expiry,
                    entry_time=entry_time,
                    entry_price=Decimal(str(main_price)),
                    quantity=-(params.lot_size * params.lots_to_trade)  # Negative for sell
                )
                session.add(main_position)
                
                if params.use_hedging and hedge_price:
                    hedge_position = BacktestPosition(
                        trade_id=trade.id,
                        position_type="HEDGE",
                        option_type=option_type,
                        strike_price=hedge_strike,
                        expiry_date=expiry,
                        entry_time=entry_time,
                        entry_price=Decimal(str(hedge_price)),
                        quantity=(params.lot_size * params.lots_to_trade)  # Positive for buy
                    )
                    session.add(hedge_position)
                
                session.commit()
                session.refresh(trade)
                
                # Eager load positions to avoid detached instance error
                from sqlalchemy.orm import joinedload
                trade = session.query(BacktestTrade).options(
                    joinedload(BacktestTrade.positions)
                ).filter_by(id=trade.id).first()
            
            # In production, we would record position with risk manager
            # For backtesting, we skip this to match original behavior
            
            logger.info(f"Opened trade: {signal_result.signal_type.value} at {current_bar.timestamp}")
            return trade
            
        except Exception as e:
            logger.error(f"Error opening trade: {e}")
            return None
    
    async def _check_and_close_expiry_positions(
        self,
        open_trades: List[BacktestTrade],
        current_bar: BarData,
        backtest_run_id: str
    ) -> float:
        """Check and close positions at expiry"""
        total_pnl = 0.0
        trades_to_remove = []
        
        for trade in open_trades:
            if trade.outcome != TradeOutcome.OPEN:
                continue
            
            # Check if any position has expired
            for position in trade.positions:
                if current_bar.timestamp >= position.expiry_date:
                    # Close at expiry
                    pnl = await self._close_trade(
                        trade,
                        current_bar.timestamp,
                        current_bar.close,
                        TradeOutcome.EXPIRED,
                        "Weekly expiry"
                    )
                    total_pnl += pnl
                    trades_to_remove.append(trade)
                    break
        
        # Remove closed trades
        for trade in trades_to_remove:
            if trade in open_trades:
                open_trades.remove(trade)
        
        return total_pnl
    
    async def _check_stop_losses(
        self,
        open_trades: List[BacktestTrade],
        current_bar: BarData,
        backtest_run_id: str
    ) -> float:
        """Check and trigger stop losses"""
        total_pnl = 0.0
        trades_to_remove = []
        
        for trade in open_trades:
            if trade.outcome != TradeOutcome.OPEN:
                continue
            
            # Skip stop loss check if trade hasn't entered yet
            if current_bar.timestamp <= trade.entry_time:
                continue
            
            # Check stop loss based on signal direction
            hit_stop_loss = False
            
            # Direction is stored as integer: 1 for BULLISH, -1 for BEARISH
            if trade.direction == "1" or trade.direction == 1:
                # For bullish trades (sold PUT), stop if price goes below stop loss
                if current_bar.close <= float(trade.stop_loss_price):
                    hit_stop_loss = True
            else:
                # For bearish trades (sold CALL), stop if price goes above stop loss
                if current_bar.close >= float(trade.stop_loss_price):
                    hit_stop_loss = True
            
            if hit_stop_loss:
                pnl = await self._close_trade(
                    trade,
                    current_bar.timestamp,
                    current_bar.close,
                    TradeOutcome.STOPPED,
                    "Stop loss hit"
                )
                total_pnl += pnl
                trades_to_remove.append(trade)
        
        # Remove closed trades
        for trade in trades_to_remove:
            if trade in open_trades:
                open_trades.remove(trade)
        
        return total_pnl
    
    async def _close_trade(
        self,
        trade: BacktestTrade,
        exit_time: datetime,
        index_price: float,
        outcome: TradeOutcome,
        reason: str,
        session = None
    ) -> float:
        """Close a trade and calculate P&L"""
        trade.exit_time = exit_time
        trade.index_price_at_exit = Decimal(str(index_price))
        trade.outcome = outcome
        trade.exit_reason = reason
        
        total_pnl = 0.0
        
        # Close all positions
        for position in trade.positions:
            # Get exit price
            exit_price = await self.option_pricing.get_option_price_at_time(
                exit_time,
                position.strike_price,
                position.option_type,
                position.expiry_date
            )
            
            if not exit_price:
                # If at expiry, calculate intrinsic value
                if exit_time >= position.expiry_date:
                    if position.option_type == "CE":
                        exit_price = max(0, index_price - position.strike_price)
                    else:  # PE
                        exit_price = max(0, position.strike_price - index_price)
                else:
                    exit_price = 0
            
            position.exit_time = exit_time
            position.exit_price = Decimal(str(exit_price))
            
            # Calculate P&L
            if position.quantity < 0:  # Sold option
                position.gross_pnl = abs(position.quantity) * (position.entry_price - position.exit_price)
            else:  # Bought option
                position.gross_pnl = position.quantity * (position.exit_price - position.entry_price)
            
            # Commission (entry + exit)
            # Using lot size of 75 (as per requirements)
            lots = abs(position.quantity) // 75
            position.commission = Decimal(str(lots * 40 * 2))  # Rs. 40 per lot, 2 for entry+exit
            position.net_pnl = position.gross_pnl - position.commission
            
            total_pnl += float(position.net_pnl)
        
        trade.total_pnl = Decimal(str(total_pnl))
        
        # Determine if win or loss
        if total_pnl > 0:
            trade.outcome = TradeOutcome.WIN
        elif total_pnl < 0:
            trade.outcome = TradeOutcome.LOSS
        
        # Update in database
        with self.db_manager.get_session() as session:
            session.merge(trade)
            session.commit()
        
        # In production, we would record position closure with risk manager
        # For backtesting, we skip this to match original behavior
        
        logger.info(f"Closed trade: {trade.signal_type} - {outcome.value} - P&L: {total_pnl:.2f}")
        return total_pnl
    
    async def _calculate_position_cost(self, trade: BacktestTrade) -> float:
        """Calculate initial cost/margin for positions"""
        net_premium = 0.0
        
        for position in trade.positions:
            if position.quantity > 0:  # Bought option (hedge)
                # Pay premium (cost)
                net_premium -= float(position.entry_price) * position.quantity
            else:  # Sold option (main position)
                # Receive premium (income)
                net_premium += float(position.entry_price) * abs(position.quantity)
        
        # Return negative of net_premium because:
        # - If net_premium is positive (received more than paid), we subtract negative = add to capital
        # - If net_premium is negative (paid more than received), we subtract positive = reduce capital
        return -net_premium
    
    def _calculate_max_drawdown(self, equity_curve: List[float]) -> Dict:
        """Calculate maximum drawdown from equity curve"""
        if not equity_curve:
            return {'value': 0, 'percent': 0}
        
        peak = equity_curve[0]
        max_dd = 0
        max_dd_pct = 0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            
            drawdown = peak - value
            drawdown_pct = (drawdown / peak) * 100 if peak > 0 else 0
            
            if drawdown > max_dd:
                max_dd = drawdown
                max_dd_pct = drawdown_pct
        
        return {'value': max_dd, 'percent': max_dd_pct}
    
    async def _update_backtest_status(
        self,
        backtest_run_id: str,
        status: BacktestStatus,
        error_message: str = None
    ):
        """Update backtest run status"""
        with self.db_manager.get_session() as session:
            backtest_run = session.query(BacktestRun).filter_by(id=backtest_run_id).first()
            if backtest_run:
                backtest_run.status = status
                if status == BacktestStatus.RUNNING:
                    backtest_run.started_at = datetime.now()
                elif status == BacktestStatus.COMPLETED:
                    backtest_run.completed_at = datetime.now()
                if error_message:
                    backtest_run.error_message = error_message
                session.commit()
    
    async def _update_backtest_results(self, backtest_run_id: str, results: Dict):
        """Update backtest run with final results"""
        with self.db_manager.get_session() as session:
            backtest_run = session.query(BacktestRun).filter_by(id=backtest_run_id).first()
            if backtest_run:
                backtest_run.final_capital = Decimal(str(results['final_capital']))
                backtest_run.total_trades = results['total_trades']
                backtest_run.winning_trades = results['winning_trades']
                backtest_run.losing_trades = results['losing_trades']
                backtest_run.win_rate = Decimal(str(results['win_rate']))
                backtest_run.total_pnl = Decimal(str(results['total_pnl']))
                backtest_run.total_return_percent = Decimal(str(results['total_return_percent']))
                backtest_run.max_drawdown = Decimal(str(results['max_drawdown']))
                backtest_run.max_drawdown_percent = Decimal(str(results['max_drawdown_percent']))
                
                # Save daily results
                for daily_result in results['daily_results']:
                    session.add(daily_result)
                
                session.commit()