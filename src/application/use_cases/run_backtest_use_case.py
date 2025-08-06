"""
Run Backtest Use Case
Application use case for running trading strategy backtests
"""
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal
from dataclasses import dataclass

from ..dto.requests import RunBacktestRequest
from ..dto.responses import (
    RunBacktestResponse,
    BacktestMetrics,
    BacktestTrade,
    BaseResponse,
    ResponseStatus
)
from ...domain.repositories.imarket_data_repository import IMarketDataRepository
from ...domain.repositories.ioptions_repository import IOptionsHistoricalDataRepository
from ...domain.services.irisk_manager import IRiskManager
from ...domain.entities.market_data import MarketData, TimeInterval
from ...domain.entities.trade import Trade, TradeType, TradeStatus
from ...domain.value_objects.trading_symbol import TradingSymbol

logger = logging.getLogger(__name__)


@dataclass
class BacktestState:
    """Backtest execution state"""
    current_capital: Decimal
    trades: List[BacktestTrade]
    open_positions: List[Trade]
    equity_curve: List[Dict[str, Any]]
    daily_returns: List[Decimal]
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: Decimal = Decimal('0')
    max_equity: Decimal = Decimal('0')
    max_drawdown: Decimal = Decimal('0')


class RunBacktestUseCase:
    """Use case for running backtests"""
    
    def __init__(
        self,
        market_data_repo: IMarketDataRepository,
        options_data_repo: IOptionsHistoricalDataRepository,
        risk_manager: IRiskManager
    ):
        self.market_data_repo = market_data_repo
        self.options_data_repo = options_data_repo
        self.risk_manager = risk_manager
    
    async def execute(
        self,
        request: RunBacktestRequest
    ) -> BaseResponse[RunBacktestResponse]:
        """Execute the backtest"""
        try:
            start_time = datetime.now()
            
            logger.info(
                f"Starting backtest for {request.strategy_name} "
                f"from {request.from_date} to {request.to_date}"
            )
            
            # Initialize backtest state
            state = BacktestState(
                current_capital=request.initial_capital,
                trades=[],
                open_positions=[],
                equity_curve=[{
                    "date": request.from_date.isoformat(),
                    "equity": float(request.initial_capital)
                }]
            )
            
            # Get strategy implementation
            strategy = self._get_strategy(request.strategy_name, request.parameters)
            
            # Load historical data
            market_data = await self._load_market_data(
                request.symbol,
                request.from_date,
                request.to_date
            )
            
            if not market_data:
                return BaseResponse(
                    status=ResponseStatus.ERROR,
                    message="No historical data available for backtest period",
                    errors=["Insufficient data"]
                )
            
            # Run backtest day by day
            current_date = request.from_date
            while current_date <= request.to_date:
                # Skip weekends
                if current_date.weekday() >= 5:
                    current_date += timedelta(days=1)
                    continue
                
                # Process day
                await self._process_trading_day(
                    current_date,
                    state,
                    strategy,
                    market_data,
                    request
                )
                
                # Update equity curve
                state.equity_curve.append({
                    "date": current_date.isoformat(),
                    "equity": float(state.current_capital + self._calculate_open_pnl(state))
                })
                
                current_date += timedelta(days=1)
            
            # Close any remaining positions
            await self._close_all_positions(state, market_data, request.to_date)
            
            # Calculate final metrics
            metrics = self._calculate_metrics(state, request)
            
            # Prepare response
            response_data = RunBacktestResponse(
                strategy_name=request.strategy_name,
                from_date=request.from_date,
                to_date=request.to_date,
                initial_capital=request.initial_capital,
                final_capital=state.current_capital,
                metrics=metrics,
                trades=state.trades,
                equity_curve=state.equity_curve,
                execution_time_seconds=(datetime.now() - start_time).total_seconds()
            )
            
            return BaseResponse(
                status=ResponseStatus.SUCCESS,
                message=f"Backtest completed with {len(state.trades)} trades",
                data=response_data
            )
            
        except Exception as e:
            logger.error(f"Error in RunBacktestUseCase: {e}", exc_info=True)
            return BaseResponse(
                status=ResponseStatus.ERROR,
                message=f"Failed to run backtest: {str(e)}",
                errors=[str(e)]
            )
    
    def _get_strategy(self, strategy_name: str, parameters: Dict[str, Any]):
        """Get strategy implementation"""
        # This is a simplified example - in real implementation,
        # this would load the actual strategy class
        if strategy_name == "WeeklySignals":
            return WeeklySignalsStrategy(parameters)
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")
    
    async def _load_market_data(
        self,
        symbol: str,
        from_date: date,
        to_date: date
    ) -> List[MarketData]:
        """Load historical market data"""
        start_datetime = datetime.combine(from_date, datetime.min.time())
        end_datetime = datetime.combine(to_date, datetime.max.time())
        
        data = await self.market_data_repo.get_by_symbol_and_date_range(
            symbol=f"{symbol} 50",
            start_date=start_datetime,
            end_date=end_datetime,
            interval=TimeInterval.ONE_HOUR
        )
        
        return data
    
    async def _process_trading_day(
        self,
        current_date: date,
        state: BacktestState,
        strategy: Any,
        market_data: List[MarketData],
        request: RunBacktestRequest
    ):
        """Process a single trading day"""
        # Get data for current day
        day_data = [
            d for d in market_data 
            if d.timestamp.date() == current_date
        ]
        
        if not day_data:
            return
        
        # Check and close positions based on exit rules
        await self._check_exit_conditions(state, day_data, request)
        
        # Generate signals (simplified - only at market open)
        morning_data = day_data[0]  # 9:15 AM data
        signal = strategy.generate_signal(morning_data, state)
        
        if signal and len(state.open_positions) < request.max_positions:
            # Calculate position size
            position_size = self._calculate_position_size(
                state.current_capital,
                request.position_size_pct,
                morning_data.close,
                request.symbol
            )
            
            if position_size > 0:
                # Open new position
                trade = await self._open_position(
                    signal,
                    morning_data,
                    position_size,
                    state,
                    request
                )
                
                if trade:
                    state.open_positions.append(trade)
    
    async def _check_exit_conditions(
        self,
        state: BacktestState,
        day_data: List[MarketData],
        request: RunBacktestRequest
    ):
        """Check exit conditions for open positions"""
        positions_to_close = []
        
        for position in state.open_positions:
            for data in day_data:
                should_exit = False
                exit_reason = ""
                
                # Check stop loss
                if request.stop_loss_pct and position.trade_type == TradeType.BUY:
                    stop_price = position.entry_price * (1 - request.stop_loss_pct / 100)
                    if data.low <= stop_price:
                        should_exit = True
                        exit_reason = "Stop Loss"
                elif request.stop_loss_pct and position.trade_type == TradeType.SELL:
                    stop_price = position.entry_price * (1 + request.stop_loss_pct / 100)
                    if data.high >= stop_price:
                        should_exit = True
                        exit_reason = "Stop Loss"
                
                # Check take profit
                if request.take_profit_pct and position.trade_type == TradeType.BUY:
                    target_price = position.entry_price * (1 + request.take_profit_pct / 100)
                    if data.high >= target_price:
                        should_exit = True
                        exit_reason = "Take Profit"
                elif request.take_profit_pct and position.trade_type == TradeType.SELL:
                    target_price = position.entry_price * (1 - request.take_profit_pct / 100)
                    if data.low <= target_price:
                        should_exit = True
                        exit_reason = "Take Profit"
                
                if should_exit:
                    positions_to_close.append((position, data.close, exit_reason))
                    break
        
        # Close positions
        for position, exit_price, exit_reason in positions_to_close:
            await self._close_position(position, exit_price, exit_reason, state, request)
            state.open_positions.remove(position)
    
    async def _open_position(
        self,
        signal: Dict[str, Any],
        market_data: MarketData,
        position_size: int,
        state: BacktestState,
        request: RunBacktestRequest
    ) -> Optional[Trade]:
        """Open a new position"""
        try:
            # Apply slippage
            entry_price = market_data.close
            if signal["type"] == "BUY":
                entry_price = entry_price * (1 + request.slippage_pct / 100)
            else:
                entry_price = entry_price * (1 - request.slippage_pct / 100)
            
            # Calculate commission
            trade_value = entry_price * position_size
            commission = trade_value * request.commission_pct / 100
            
            # Check if we have enough capital
            required_capital = trade_value + commission
            if required_capital > state.current_capital:
                return None
            
            # Create trade
            trade = Trade(
                symbol=request.symbol,
                trade_type=TradeType.BUY if signal["type"] == "BUY" else TradeType.SELL,
                entry_price=entry_price,
                quantity=position_size,
                entry_time=market_data.timestamp,
                status=TradeStatus.OPEN
            )
            
            # Deduct capital
            state.current_capital -= commission
            
            # Create backtest trade record
            backtest_trade = BacktestTrade(
                trade_id=f"BT_{len(state.trades) + 1}",
                symbol=request.symbol,
                entry_time=market_data.timestamp,
                entry_price=entry_price,
                quantity=position_size,
                trade_type=signal["type"]
            )
            
            state.trades.append(backtest_trade)
            
            return trade
            
        except Exception as e:
            logger.error(f"Error opening position: {e}")
            return None
    
    async def _close_position(
        self,
        position: Trade,
        exit_price: Decimal,
        exit_reason: str,
        state: BacktestState,
        request: RunBacktestRequest
    ):
        """Close an existing position"""
        # Apply slippage
        if position.trade_type == TradeType.BUY:
            exit_price = exit_price * (1 - request.slippage_pct / 100)
        else:
            exit_price = exit_price * (1 + request.slippage_pct / 100)
        
        # Calculate P&L
        if position.trade_type == TradeType.BUY:
            pnl = (exit_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - exit_price) * position.quantity
        
        # Calculate commission
        trade_value = exit_price * position.quantity
        commission = trade_value * request.commission_pct / 100
        
        # Net P&L
        net_pnl = pnl - commission
        pnl_percentage = (net_pnl / (position.entry_price * position.quantity)) * 100
        
        # Update capital
        state.current_capital += net_pnl
        
        # Update statistics
        state.total_pnl += net_pnl
        if net_pnl > 0:
            state.winning_trades += 1
        else:
            state.losing_trades += 1
        
        # Update trade record
        for trade in state.trades:
            if trade.symbol == position.symbol and trade.exit_time is None:
                trade.exit_time = datetime.now()
                trade.exit_price = exit_price
                trade.pnl = net_pnl
                trade.pnl_percentage = pnl_percentage
                trade.exit_reason = exit_reason
                break
    
    async def _close_all_positions(
        self,
        state: BacktestState,
        market_data: List[MarketData],
        end_date: date
    ):
        """Close all remaining positions at end of backtest"""
        if not state.open_positions:
            return
        
        # Get last available price
        last_data = market_data[-1] if market_data else None
        if not last_data:
            return
        
        for position in state.open_positions[:]:
            await self._close_position(
                position,
                last_data.close,
                "Backtest End",
                state,
                RunBacktestRequest(
                    strategy_name="",
                    from_date=end_date,
                    to_date=end_date,
                    slippage_pct=Decimal('0.05'),
                    commission_pct=Decimal('0.02')
                )
            )
    
    def _calculate_position_size(
        self,
        capital: Decimal,
        position_size_pct: Decimal,
        price: Decimal,
        symbol: str
    ) -> int:
        """Calculate position size based on capital and risk"""
        # Calculate position value
        position_value = capital * position_size_pct / 100
        
        # Calculate quantity
        quantity = int(position_value / price)
        
        # Round to lot size (e.g., 50 for NIFTY)
        lot_size = 50 if "NIFTY" in symbol else 1
        quantity = (quantity // lot_size) * lot_size
        
        return quantity
    
    def _calculate_open_pnl(self, state: BacktestState) -> Decimal:
        """Calculate unrealized P&L for open positions"""
        # Simplified - in real implementation would use current market prices
        return Decimal('0')
    
    def _calculate_metrics(
        self,
        state: BacktestState,
        request: RunBacktestRequest
    ) -> BacktestMetrics:
        """Calculate backtest performance metrics"""
        total_trades = len(state.trades)
        if total_trades == 0:
            return BacktestMetrics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_pnl=Decimal('0'),
                total_return_pct=Decimal('0'),
                average_win=Decimal('0'),
                average_loss=Decimal('0'),
                largest_win=Decimal('0'),
                largest_loss=Decimal('0'),
                max_drawdown=Decimal('0'),
                max_drawdown_pct=Decimal('0'),
                expectancy=Decimal('0')
            )
        
        # Calculate win/loss statistics
        completed_trades = [t for t in state.trades if t.pnl is not None]
        winning_trades = [t for t in completed_trades if t.pnl > 0]
        losing_trades = [t for t in completed_trades if t.pnl <= 0]
        
        win_rate = (len(winning_trades) / len(completed_trades) * 100) if completed_trades else 0
        
        # Calculate average win/loss
        average_win = (
            sum(t.pnl for t in winning_trades) / len(winning_trades)
            if winning_trades else Decimal('0')
        )
        average_loss = (
            sum(abs(t.pnl) for t in losing_trades) / len(losing_trades)
            if losing_trades else Decimal('0')
        )
        
        # Calculate largest win/loss
        largest_win = max((t.pnl for t in winning_trades), default=Decimal('0'))
        largest_loss = min((t.pnl for t in losing_trades), default=Decimal('0'))
        
        # Calculate returns
        total_return_pct = (
            (state.current_capital - request.initial_capital) / request.initial_capital * 100
        )
        
        # Calculate max drawdown
        max_drawdown, max_drawdown_pct = self._calculate_max_drawdown(state.equity_curve)
        
        # Calculate expectancy
        expectancy = self._calculate_expectancy(win_rate, average_win, average_loss)
        
        # Calculate Sharpe ratio (simplified)
        sharpe_ratio = self._calculate_sharpe_ratio(state.equity_curve)
        
        # Calculate profit factor
        total_wins = sum(t.pnl for t in winning_trades) if winning_trades else Decimal('0')
        total_losses = sum(abs(t.pnl) for t in losing_trades) if losing_trades else Decimal('1')
        profit_factor = float(total_wins / total_losses) if total_losses > 0 else None
        
        return BacktestMetrics(
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            total_pnl=state.total_pnl,
            total_return_pct=total_return_pct,
            average_win=average_win,
            average_loss=average_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
            expectancy=expectancy
        )
    
    def _calculate_max_drawdown(
        self,
        equity_curve: List[Dict[str, Any]]
    ) -> tuple[Decimal, Decimal]:
        """Calculate maximum drawdown"""
        if len(equity_curve) < 2:
            return Decimal('0'), Decimal('0')
        
        peak = equity_curve[0]['equity']
        max_dd = 0
        max_dd_pct = 0
        
        for point in equity_curve[1:]:
            equity = point['equity']
            if equity > peak:
                peak = equity
            else:
                dd = peak - equity
                dd_pct = (dd / peak * 100) if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
                    max_dd_pct = dd_pct
        
        return Decimal(str(max_dd)), Decimal(str(max_dd_pct))
    
    def _calculate_expectancy(
        self,
        win_rate: float,
        average_win: Decimal,
        average_loss: Decimal
    ) -> Decimal:
        """Calculate trade expectancy"""
        if average_loss == 0:
            return average_win
        
        win_rate_decimal = Decimal(str(win_rate / 100))
        loss_rate = 1 - win_rate_decimal
        
        return (win_rate_decimal * average_win) - (loss_rate * average_loss)
    
    def _calculate_sharpe_ratio(
        self,
        equity_curve: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Calculate Sharpe ratio (simplified)"""
        if len(equity_curve) < 2:
            return None
        
        # Calculate daily returns
        returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i-1]['equity']
            curr_equity = equity_curve[i]['equity']
            if prev_equity > 0:
                daily_return = (curr_equity - prev_equity) / prev_equity
                returns.append(daily_return)
        
        if not returns:
            return None
        
        # Calculate average return and standard deviation
        avg_return = sum(returns) / len(returns)
        
        if len(returns) < 2:
            return None
        
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return None
        
        # Annualize (assuming 252 trading days)
        annualized_return = avg_return * 252
        annualized_std = std_dev * (252 ** 0.5)
        
        # Risk-free rate (simplified as 5% annual)
        risk_free_rate = 0.05
        
        sharpe = (annualized_return - risk_free_rate) / annualized_std
        
        return float(sharpe)


class WeeklySignalsStrategy:
    """Example strategy implementation"""
    
    def __init__(self, parameters: Dict[str, Any]):
        self.parameters = parameters
    
    def generate_signal(self, data: MarketData, state: BacktestState) -> Optional[Dict[str, Any]]:
        """Generate trading signal"""
        # Simplified signal generation
        # In real implementation, this would contain actual strategy logic
        
        # Example: Simple moving average crossover
        # This is just a placeholder
        if data.timestamp.hour == 9:  # Only trade at market open
            # Random signal for demonstration
            import random
            if random.random() > 0.9:  # 10% chance of signal
                return {
                    "type": "BUY" if random.random() > 0.5 else "SELL",
                    "strength": 0.7,
                    "reason": "Strategy Signal"
                }
        
        return None