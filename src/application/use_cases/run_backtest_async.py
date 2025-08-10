"""
Asynchronous Run Backtest Use Case
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
from ...infrastructure.services.data_collection_service_async import AsyncDataCollectionService
from ...infrastructure.services.option_pricing_service_async import AsyncOptionPricingService
from ...infrastructure.services.holiday_service import HolidayService
from ...infrastructure.validation.market_data_validator import MarketDataValidator
from ...infrastructure.database.models import (
    BacktestRun, BacktestTrade, BacktestPosition, BacktestDailyResult,
    BacktestStatus, NiftyIndexData, NiftyIndexDataHourly, TradeOutcome
)
from ...infrastructure.database.database_manager_async import get_async_db_manager
from ...infrastructure.services.breeze_service_async import AsyncBreezeService
from .run_backtest import BacktestParameters

logger = logging.getLogger(__name__)

class AsyncRunBacktestUseCase:
    """
    Use case for running a complete backtest asynchronously
    """
    
    def __init__(
        self,
        enable_risk_management: bool = False
    ):
        self.breeze_service = AsyncBreezeService()
        self.db_manager = get_async_db_manager()
        self.data_collection = AsyncDataCollectionService(self.breeze_service, self.db_manager)
        self.option_pricing = AsyncOptionPricingService(self.data_collection, self.db_manager)
        self.signal_evaluator = SignalEvaluator()
        self.context_manager = WeeklyContextManager()
        self.holiday_service = HolidayService()
        self.enable_risk_management = enable_risk_management
        
        if enable_risk_management:
            self.margin_calculator = MarginCalculator(lot_size=75)
            self.risk_manager = None
            self.market_calendar = MarketCalendar()
            self.data_validator = MarketDataValidator(max_staleness_minutes=525600)
        else:
            self.margin_calculator = None
            self.risk_manager = None
            self.market_calendar = None
            self.data_validator = None
        
        # Track missing options data
        self.missing_options_data = set()
        self.missing_data_info = None
    
    async def execute(self, params: BacktestParameters) -> str:
        logger.info(f"Starting asynchronous backtest from {params.from_date} to {params.to_date}")
        
        if self.enable_risk_management:
            self.risk_manager = RiskManager(
                initial_capital=Decimal(str(params.initial_capital)),
                lot_size=params.lot_size
            )
        
        backtest_run = await self._create_backtest_run(params)
        
        try:
            await self._update_backtest_status(backtest_run.id, BacktestStatus.RUNNING)
            
            await self._ensure_data_available(params.from_date, params.to_date)
            
            buffer_start = params.from_date - timedelta(days=7)
            nifty_data = await self.data_collection.get_nifty_data(
                buffer_start, params.to_date
            )
            
            if not nifty_data:
                raise ValueError("No NIFTY data available for the specified period")
            
            results = await self._run_backtest_logic(
                backtest_run, nifty_data, params
            )
            
            # Auto-fetch ALL missing options data if enabled
            if params.auto_fetch_missing_data and self.missing_options_data:
                logger.info("Starting auto-fetch of missing options data...")
                fetched_count = await self._auto_fetch_all_missing_options(params)
                
                # Store fetch info for API response
                self.missing_data_info = {
                    'total_missing': len(self.missing_options_data),
                    'records_fetched': fetched_count,
                    'unique_strikes': len(set(s[0] for s in self.missing_options_data))
                }
                
                # Store fetch info in results
                results['missing_data_fetched'] = self.missing_data_info
            
            await self._update_backtest_results(backtest_run.id, results)
            
            await self._update_backtest_status(backtest_run.id, BacktestStatus.COMPLETED)
            
            logger.info(f"Asynchronous backtest completed successfully. ID: {backtest_run.id}")
            return backtest_run.id
            
        except Exception as e:
            logger.error(f"Asynchronous backtest failed: {e}")
            await self._update_backtest_status(
                backtest_run.id, BacktestStatus.FAILED, str(e)
            )
            raise

    async def _create_backtest_run(self, params: BacktestParameters) -> BacktestRun:
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
        
        async with self.db_manager.get_session() as session:
            session.add(backtest_run)
            await session.commit()
            await session.refresh(backtest_run)
        
        return backtest_run

    async def _ensure_data_available(self, from_date: datetime, to_date: datetime):
        buffer_start = from_date - timedelta(days=7)
        
        added = await self.data_collection.ensure_nifty_data_available(
            buffer_start, to_date, fetch_missing=False
        )
        
        if added > 0:
            logger.info(f"Added {added} NIFTY data records")
        
        expiry_dates = self._get_expiry_dates(from_date, to_date)
        
        current_nifty = 25000
        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(NiftyIndexDataHourly.close)
                .filter(NiftyIndexDataHourly.timestamp <= to_date)
                .order_by(NiftyIndexDataHourly.timestamp.desc())
                .limit(1)
            )
            recent_data = result.scalar_one_or_none()
            if recent_data:
                current_nifty = int(recent_data)
        
        min_strike = ((current_nifty - 1000) // 50) * 50
        max_strike = ((current_nifty + 1000) // 50) * 50
        strikes = list(range(min_strike, max_strike + 50, 50))
        
        for expiry in expiry_dates:
            end_date = min(expiry, to_date)
            added = await self.data_collection.ensure_options_data_available(
                from_date, end_date, strikes, [expiry], fetch_missing=False
            )
            
            if added > 0:
                logger.info(f"Added {added} options data records for expiry {expiry.date()}")

    def _get_expiry_dates(self, from_date: datetime, to_date: datetime) -> List[datetime]:
        expiry_dates = []
        current = from_date
        
        while current <= to_date:
            expiry = self.context_manager.get_next_expiry(current)
            if expiry <= to_date and expiry not in expiry_dates:
                expiry_dates.append(expiry)
            current = expiry + timedelta(days=1)
        
        return expiry_dates

    async def _run_backtest_logic(self, backtest_run: BacktestRun, nifty_data: List[NiftyIndexDataHourly], params: BacktestParameters) -> Dict:
        current_capital = float(params.initial_capital)
        open_trades: List[BacktestTrade] = []
        all_trades: List[BacktestTrade] = []
        daily_results: List[BacktestDailyResult] = []
        
        current_date = None
        daily_starting_capital = current_capital
        
        for i, data_point in enumerate(nifty_data):
            current_bar = self.context_manager.create_bar_from_nifty_data(data_point)
            
            if not self.context_manager.is_market_hours(current_bar.timestamp):
                continue
                
            if self.holiday_service.is_trading_holiday(current_bar.timestamp.date(), "NSE"):
                logger.debug(f"Skipping {current_bar.timestamp.date()} - Trading holiday")
                continue
                
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
            
            if current_date != current_bar.timestamp.date():
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
            
            if i < 35:
                continue
            
            prev_week_data = self.context_manager.get_previous_week_data(
                current_bar.timestamp, nifty_data[:i]
            )
            
            if not prev_week_data:
                continue
            
            context = self.context_manager.update_context(current_bar, prev_week_data)
            
            expiry_pnl = await self._check_and_close_expiry_positions(
                open_trades, current_bar, backtest_run.id
            )
            current_capital += expiry_pnl
            
            sl_pnl = await self._check_stop_losses(
                open_trades, current_bar, backtest_run.id
            )
            current_capital += sl_pnl
            
            await self._calculate_wednesday_exit_pnl(
                open_trades, current_bar, backtest_run.id, params
            )
            
            if not open_trades and not context.signal_triggered_this_week:
                signal_result = self.signal_evaluator.evaluate_all_signals(
                    current_bar, context, current_bar.timestamp
                )
                
                if signal_result.is_triggered and signal_result.signal_type.value in params.signals_to_test:
                    trade = await self._open_trade(
                        backtest_run.id,
                        signal_result,
                        current_bar,
                        context,
                        params,
                        current_capital # Pass current capital
                    )
                    
                    if trade:
                        open_trades.append(trade)
                        all_trades.append(trade)
        
        for trade in open_trades:
            if trade.outcome == TradeOutcome.OPEN:
                await self._close_trade(
                    trade, 
                    nifty_data[-1].timestamp,
                    float(nifty_data[-1].close),
                    TradeOutcome.EXPIRED,
                    "Backtest ended"
                )
        
                total_trades = len(all_trades)
        winning_trades = len([t for t in all_trades if t.outcome == TradeOutcome.WIN])
        losing_trades = len([t for t in all_trades if t.outcome == TradeOutcome.LOSS])
        
        total_pnl = current_capital - float(params.initial_capital)
        total_return_percent = (total_pnl / float(params.initial_capital)) * 100

        # Calculate annualized return
        duration_days = (params.to_date - params.from_date).days
        annualized_return = 0.0
        if duration_days > 0 and float(params.initial_capital) > 0:
            annualized_return = ((1 + (total_pnl / float(params.initial_capital))) ** (365 / duration_days)) - 1
            annualized_return *= 100 # Convert to percentage

        results = {
            'final_capital': current_capital,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': (winning_trades / total_trades * 100) if total_trades > 0 else 0,
            'total_pnl': total_pnl,
            'total_return_percent': total_return_percent,
            'annualized_return': annualized_return,
            'trades': all_trades,
            'daily_results': daily_results
        }
        
        daily_returns = [float(d.daily_return_percent) for d in daily_results]
        performance_metrics = self._calculate_performance_metrics(daily_returns)
        results.update(performance_metrics)

        equity_curve = [float(params.initial_capital)]
        for daily in daily_results:
            equity_curve.append(float(daily.ending_capital))
        
        max_drawdown = self._calculate_max_drawdown(equity_curve)
        results['max_drawdown'] = max_drawdown['value']
        results['max_drawdown_percent'] = max_drawdown['percent']
        
        return results

    async def _check_and_close_expiry_positions(self, open_trades: List[BacktestTrade], current_bar: BarData, backtest_run_id: str) -> float:
        total_pnl = 0.0
        trades_to_remove = []
        
        for trade in open_trades:
            if trade.outcome != TradeOutcome.OPEN:
                continue
            
            for position in trade.positions:
                if current_bar.timestamp >= position.expiry_date:
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
        
        for trade in trades_to_remove:
            if trade in open_trades:
                open_trades.remove(trade)
        
        return total_pnl

    async def _check_stop_losses(self, open_trades: List[BacktestTrade], current_bar: BarData, backtest_run_id: str) -> float:
        total_pnl = 0.0
        trades_to_remove = []
        
        for trade in open_trades:
            if trade.outcome != TradeOutcome.OPEN:
                continue
            
            if current_bar.timestamp <= trade.entry_time:
                continue
            
            hit_stop_loss = False
            
            if trade.direction == "1" or trade.direction == 1:
                if current_bar.close <= float(trade.stop_loss_price):
                    hit_stop_loss = True
            else:
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
        
        for trade in trades_to_remove:
            if trade in open_trades:
                open_trades.remove(trade)
        
        return total_pnl

    async def _calculate_wednesday_exit_pnl(self, open_trades: List[BacktestTrade], current_bar: BarData, backtest_run_id: str, params: BacktestParameters) -> None:
        if current_bar.timestamp.weekday() == 2:
            exit_hour, exit_minute = map(int, params.wednesday_exit_time.split(':'))
            
            if (current_bar.timestamp.hour > exit_hour or 
                (current_bar.timestamp.hour == exit_hour and current_bar.timestamp.minute >= exit_minute)):
                
                for trade in open_trades:
                    if trade.outcome != TradeOutcome.OPEN:
                        continue
                    
                    if trade.wednesday_exit_time:
                        continue
                    
                    wednesday_pnl = 0.0
                    commission = 0.0
                    
                    for position in trade.positions:
                        exit_price = await self.option_pricing.get_option_price_at_time(
                            current_bar.timestamp,
                            position.strike_price,
                            position.option_type,
                            position.expiry_date
                        )
                        
                        if position.position_type == "MAIN":
                            position_pnl = (float(position.entry_price) - exit_price) * abs(position.quantity)
                        else:
                            position_pnl = (exit_price - float(position.entry_price)) * abs(position.quantity)
                        
                        wednesday_pnl += position_pnl
                        
                        lots = abs(position.quantity) / params.lot_size
                        commission += lots * params.commission_per_lot
                    
                    trade.wednesday_exit_time = current_bar.timestamp
                    trade.wednesday_exit_pnl = Decimal(str(wednesday_pnl - commission))
                    trade.wednesday_index_price = Decimal(str(current_bar.close))
                    
                    async with self.db_manager.get_session() as session:
                        result = await session.execute(
                            select(BacktestTrade).filter_by(id=trade.id)
                        )
                        db_trade = result.scalar_one_or_none()
                        if db_trade:
                            db_trade.wednesday_exit_time = trade.wednesday_exit_time
                            db_trade.wednesday_exit_pnl = trade.wednesday_exit_pnl
                            db_trade.wednesday_index_price = trade.wednesday_index_price
                            await session.commit()

    async def _open_trade(self, backtest_run_id: str, signal_result, current_bar: BarData, context, params: BacktestParameters, current_capital: float) -> Optional[BacktestTrade]:
        if self.market_calendar and not self.market_calendar.is_market_open(current_bar.timestamp):
            logger.warning(f"Cannot open trade outside market hours: {current_bar.timestamp}")
            return None
            
        try:
            expiry = self.context_manager.get_expiry_for_week(self.context_manager.current_week_start)
            main_strike = signal_result.strike_price
            actual_stop_loss = float(main_strike)
            
            # Calculate stop loss distance
            stop_loss_distance = abs(float(signal_result.entry_price) - actual_stop_loss)
            
            # Calculate position size based on risk management
            calculated_lots_to_trade = self._calculate_position_size(
                capital=current_capital,
                risk_per_trade=params.risk_per_trade,
                stop_loss_distance=stop_loss_distance,
                lot_size=params.lot_size
            )
            
            # Use calculated lots or default if custom lots are not defined for this signal
            lots_to_trade = params.lots_per_signal.get(signal_result.signal_type.value, calculated_lots_to_trade)
            
            if lots_to_trade <= 0:
                logger.warning(f"Calculated lots to trade is 0 for signal {signal_result.signal_type}. Skipping trade.")
                return None
            
            # Create trade record with zone information
            entry_time = current_bar.timestamp + timedelta(hours=1)
            
            trade = BacktestTrade(
                backtest_run_id=backtest_run_id,
                week_start_date=self.context_manager.current_week_start,
                signal_type=signal_result.signal_type.value,
                direction=signal_result.direction.value,
                entry_time=entry_time,
                index_price_at_entry=Decimal(str(current_bar.close)),
                signal_trigger_price=Decimal(str(signal_result.entry_price)),
                stop_loss_price=Decimal(str(actual_stop_loss)),
                outcome=TradeOutcome.OPEN,
                resistance_zone_top=Decimal(str(context.zones.upper_zone_top)),
                resistance_zone_bottom=Decimal(str(context.zones.upper_zone_bottom)),
                support_zone_top=Decimal(str(context.zones.lower_zone_top)),
                support_zone_bottom=Decimal(str(context.zones.lower_zone_bottom)),
                bias_direction=context.bias.bias.value,
                bias_strength=Decimal(str(context.bias.strength)),
                weekly_max_high=Decimal(str(context.weekly_max_high)),
                weekly_min_low=Decimal(str(context.weekly_min_low)),
                first_bar_open=Decimal(str(context.first_hour_bar.open)) if context.first_hour_bar else None,
                first_bar_close=Decimal(str(context.first_hour_bar.close)) if context.first_hour_bar else None,
                first_bar_high=Decimal(str(context.first_hour_bar.high)) if context.first_hour_bar else None,
                first_bar_low=Decimal(str(context.first_hour_bar.low)) if context.first_hour_bar else None,
                distance_to_resistance=Decimal(str(context.bias.distance_to_resistance)),
                distance_to_support=Decimal(str(context.bias.distance_to_support))
            )
            
            option_type = signal_result.option_type
            
            main_price = await self.option_pricing.get_option_price_at_time(
                current_bar.timestamp, main_strike, option_type, expiry
            )
            
            if not main_price:
                logger.warning(f"No option price found for main position {main_strike} {option_type} at {current_bar.timestamp}")
                # Track missing strike for auto-fetch
                self.missing_options_data.add((main_strike, option_type, expiry.date()))
                return None
            
            hedge_price = None
            if params.use_hedging:
                hedge_price = await self.option_pricing.get_option_price_at_time(
                    current_bar.timestamp, hedge_strike, option_type, expiry
                )
                
                if not hedge_price:
                    logger.warning(f"No option price found for hedge position {hedge_strike} {option_type} at {current_bar.timestamp}")
                    # Track missing hedge strike for auto-fetch
                    self.missing_options_data.add((hedge_strike, option_type, expiry.date()))
                    return None
            
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
            
            if self.enable_risk_management and self.margin_calculator and self.risk_manager:
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
                
                position_value = Decimal(str(main_price * params.lot_size * params.lots_to_trade))
                stop_loss_distance = abs(actual_stop_loss - current_bar.close)
                potential_loss = Decimal(str(stop_loss_distance * params.lot_size * params.lots_to_trade))
                
                if margin_req.total_margin > self.risk_manager.current_capital:
                    logger.warning(f"Insufficient capital for margin. Required: {margin_req.total_margin}, Available: {self.risk_manager.current_capital}")
                    return None
            
            async with self.db_manager.get_session() as session:
                session.add(trade)
                await session.commit()
                await session.refresh(trade)
                
                main_position = BacktestPosition(
                    trade_id=trade.id,
                    position_type="MAIN",
                    option_type=option_type,
                    strike_price=main_strike,
                    expiry_date=expiry,
                    entry_time=entry_time,
                    entry_price=Decimal(str(main_price)),
                    quantity=-(params.lot_size * lots_to_trade)
                )
                
                # Calculate Greeks for main position
                time_to_expiry_years = (expiry - current_bar.timestamp).days / 365.0
                # Assuming a constant risk-free rate and volatility for backtesting
                # In a real scenario, these would be dynamic or fetched from data
                risk_free_rate = 0.05  # 5%
                assumed_volatility = 0.20 # 20%

                greeks = self.option_pricing.calculate_greeks(
                    option_type='c' if option_type == 'CE' else 'p',
                    spot_price=float(current_bar.close),
                    strike_price=float(main_strike),
                    time_to_expiry=time_to_expiry_years,
                    risk_free_rate=risk_free_rate,
                    volatility=assumed_volatility,
                    option_price=float(main_price)
                )
                
                main_position.delta_at_entry = Decimal(str(greeks.get('delta', 0.0)))
                main_position.gamma_at_entry = Decimal(str(greeks.get('gamma', 0.0)))
                main_position.theta_at_entry = Decimal(str(greeks.get('theta', 0.0)))
                main_position.vega_at_entry = Decimal(str(greeks.get('vega', 0.0)))
                main_position.rho_at_entry = Decimal(str(greeks.get('rho', 0.0)))
                main_position.implied_volatility_at_entry = Decimal(str(greeks.get('implied_volatility', 0.0)))

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
                        quantity=(params.lot_size * lots_to_trade)
                    )
                    session.add(hedge_position)
                
                await session.commit()
                await session.refresh(trade)
                
                result = await session.execute(
                    select(BacktestTrade).options(
                        joinedload(BacktestTrade.positions)
                    ).filter_by(id=trade.id)
                )
                trade = result.scalar_one_or_none()
            
            logger.info(f"Opened trade: {signal_result.signal_type.value} at {current_bar.timestamp}")
            return trade
            
        except Exception as e:
            logger.error(f"Error opening trade: {e}")
            return None

    async def _close_trade(self, trade: BacktestTrade, exit_time: datetime, index_price: float, outcome: TradeOutcome, reason: str, session = None) -> float:
        trade.exit_time = exit_time
        trade.index_price_at_exit = Decimal(str(index_price))
        trade.outcome = outcome
        trade.exit_reason = reason
        
        total_pnl = 0.0
        
        for position in trade.positions:
            exit_price = await self.option_pricing.get_option_price_at_time(
                exit_time,
                position.strike_price,
                position.option_type,
                position.expiry_date
            )
            
            if not exit_price:
                if exit_time >= position.expiry_date:
                    if position.option_type == "CE":
                        exit_price = max(0, index_price - position.strike_price)
                    else:
                        exit_price = max(0, position.strike_price - index_price)
                else:
                    exit_price = 0
            
            position.exit_time = exit_time
            position.exit_price = Decimal(str(exit_price))
            
            if position.quantity < 0:
                position.gross_pnl = abs(position.quantity) * (position.entry_price - position.exit_price)
            else:
                position.gross_pnl = position.quantity * (position.exit_price - position.entry_price)
            
            lots = abs(position.quantity) // 75
            position.commission = Decimal(str(lots * 40 * 2))
            position.net_pnl = position.gross_pnl - position.commission
            
            total_pnl += float(position.net_pnl)
        
        trade.total_pnl = Decimal(str(total_pnl))
        
        if total_pnl > 0:
            trade.outcome = TradeOutcome.WIN
        elif total_pnl < 0:
            trade.outcome = TradeOutcome.LOSS
        
        async with self.db_manager.get_session() as session:
            await session.merge(trade)
            await session.commit()
        
        logger.info(f"Closed trade: {trade.signal_type} - {outcome.value} - P&L: {total_pnl:.2f}")
        return total_pnl

    def _calculate_max_drawdown(self, equity_curve: List[float]) -> Dict:
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

    def _calculate_performance_metrics(self, daily_returns: List[float], risk_free_rate: float = 0.0) -> Dict:
        if not daily_returns:
            return {'sharpe_ratio': 0, 'sortino_ratio': 0}
        
        import numpy as np
        
        daily_returns = np.array(daily_returns)
        
        # Sharpe Ratio
        avg_return = np.mean(daily_returns)
        std_dev = np.std(daily_returns)
        sharpe_ratio = (avg_return - risk_free_rate) / std_dev if std_dev > 0 else 0
        
        # Sortino Ratio
        negative_returns = daily_returns[daily_returns < 0]
        downside_std_dev = np.std(negative_returns) if len(negative_returns) > 0 else 0
        sortino_ratio = (avg_return - risk_free_rate) / downside_std_dev if downside_std_dev > 0 else 0
        
        return {'sharpe_ratio': sharpe_ratio, 'sortino_ratio': sortino_ratio}

    def _calculate_position_size(self, capital: float, risk_per_trade: float, stop_loss_distance: float, lot_size: int) -> int:
        if stop_loss_distance <= 0:
            return 0
        
        risk_amount = capital * (risk_per_trade / 100)
        position_size_in_units = risk_amount / stop_loss_distance
        position_size_in_lots = int(position_size_in_units / lot_size)
        
        return position_size_in_lots
    
    async def _auto_fetch_all_missing_options(self, params: BacktestParameters) -> int:
        """Fetch ALL missing options data encountered during backtest"""
        if not self.missing_options_data:
            return 0
        
        logger.info(f"Found {len(self.missing_options_data)} missing option contracts during backtest")
        
        # Group by date ranges for efficient fetching
        from collections import defaultdict
        grouped_by_week = defaultdict(set)
        
        for strike, option_type, expiry_date in self.missing_options_data:
            # Group by week for efficient API calls
            week_start = expiry_date - timedelta(days=expiry_date.weekday() + 3)  # Monday before expiry
            week_key = (week_start, expiry_date)
            grouped_by_week[week_key].add(strike)
        
        total_fetched = 0
        total_batches = sum((len(strikes) - 1) // params.fetch_batch_size + 1 for strikes in grouped_by_week.values())
        current_batch = 0
        
        for (from_date, to_date), strikes in grouped_by_week.items():
            unique_strikes = sorted(list(strikes))
            logger.info(f"Fetching {len(unique_strikes)} unique strikes for period {from_date} to {to_date}")
            
            # Process in batches for API efficiency
            for i in range(0, len(unique_strikes), params.fetch_batch_size):
                batch = unique_strikes[i:i+params.fetch_batch_size]
                current_batch += 1
                
                logger.info(f"Batch {current_batch}/{total_batches}: Fetching {len(batch)} strikes...")
                
                try:
                    # Use the existing API endpoint
                    import requests
                    url = "http://localhost:8000/collect/options-specific"
                    request_data = {
                        "from_date": from_date.strftime("%Y-%m-%d"),
                        "to_date": to_date.strftime("%Y-%m-%d"),
                        "strikes": batch,
                        "option_types": ["CE", "PE"],
                        "symbol": "NIFTY"
                    }
                    
                    response = requests.post(url, json=request_data, timeout=120)
                    if response.status_code == 200:
                        result = response.json()
                        records = result.get('records_added', 0)
                        total_fetched += records
                        logger.info(f"  [OK] Fetched {records} records")
                    else:
                        logger.warning(f"  [WARNING] Failed batch {current_batch}: {response.status_code}")
                        
                    # Small delay between batches to avoid overload
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.warning(f"  [WARNING] Error fetching batch {current_batch}: {e}")
                    continue
        
        logger.info(f"Auto-fetch complete: {total_fetched} total records added to database")
        logger.info("Missing options data has been fetched for future backtest runs")
        return total_fetched
    
    async def _update_backtest_results(self, backtest_run_id: str, results: Dict):
        """Update backtest run with final results"""
        async with self.db_manager.get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(BacktestRun).filter_by(id=backtest_run_id)
            )
            backtest_run = result.scalar_one_or_none()
            
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
                backtest_run.sharpe_ratio = Decimal(str(results['sharpe_ratio']))
                backtest_run.sortino_ratio = Decimal(str(results['sortino_ratio']))
                backtest_run.annualized_return = Decimal(str(results['annualized_return']))
                
                for daily_result in results['daily_results']:
                    session.add(daily_result)
                
                await session.commit()
    
    async def _update_backtest_status(self, backtest_run_id: str, status: BacktestStatus, error_message: Optional[str] = None):
        """Update backtest run status"""
        async with self.db_manager.get_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(BacktestRun).filter_by(id=backtest_run_id)
            )
            backtest_run = result.scalar_one_or_none()
            
            if backtest_run:
                backtest_run.status = status
                if error_message:
                    backtest_run.error_message = error_message
                if status == BacktestStatus.COMPLETED:
                    backtest_run.completed_at = datetime.now()
                await session.commit()