"""
Portfolio Backtester
Run multiple strategies concurrently and analyze portfolio-level performance
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from sqlalchemy import create_engine, text
import uuid

logger = logging.getLogger(__name__)

@dataclass
class StrategyConfig:
    """Configuration for a single strategy in portfolio"""
    name: str
    signal_types: List[str]
    weight: float
    max_positions: int = 5
    position_size: float = 0.1  # Percentage of portfolio
    use_ml_filter: bool = True
    ml_threshold: float = 0.6
    stop_loss_type: str = 'fixed'  # 'fixed', 'dynamic', 'optimized'
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PortfolioMetrics:
    """Portfolio-level performance metrics"""
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    calmar_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    correlation_matrix: pd.DataFrame
    strategy_contributions: Dict[str, float]
    risk_metrics: Dict[str, float]

class PortfolioBacktester:
    """Portfolio-level backtesting engine"""
    
    def __init__(self, 
                 db_connection_string: str,
                 initial_capital: float = 500000):
        """
        Initialize portfolio backtester
        
        Args:
            db_connection_string: Database connection
            initial_capital: Starting capital for portfolio
        """
        self.engine = create_engine(db_connection_string)
        self.initial_capital = initial_capital
        self.strategies = []
        self.ml_models = {}
        self.risk_free_rate = 0.05  # 5% annual risk-free rate
        
    def add_strategy(self, config: StrategyConfig):
        """
        Add a strategy to the portfolio
        
        Args:
            config: Strategy configuration
        """
        self.strategies.append(config)
        logger.info(f"Added strategy: {config.name} with weight {config.weight}")
        
    def run_backtest(self,
                    from_date: datetime,
                    to_date: datetime,
                    allocation_method: str = 'equal_weight',
                    rebalance_frequency: str = 'weekly') -> PortfolioMetrics:
        """
        Run portfolio backtest
        
        Args:
            from_date: Start date
            to_date: End date
            allocation_method: Portfolio allocation method
            rebalance_frequency: How often to rebalance
            
        Returns:
            Portfolio performance metrics
        """
        run_id = str(uuid.uuid4())
        logger.info(f"Starting portfolio backtest {run_id} from {from_date} to {to_date}")
        
        # Normalize weights
        total_weight = sum(s.weight for s in self.strategies)
        for strategy in self.strategies:
            strategy.weight /= total_weight
            
        # Initialize portfolio state
        portfolio_value = self.initial_capital
        cash = self.initial_capital
        positions = {}
        portfolio_history = []
        all_trades = []
        
        # Run strategies in parallel
        strategy_results = self._run_strategies_parallel(from_date, to_date)
        
        # Combine strategy signals and execute portfolio
        current_date = from_date
        while current_date <= to_date:
            # Get signals for current period
            daily_signals = self._get_daily_signals(strategy_results, current_date)
            
            # Apply portfolio allocation
            allocations = self._calculate_allocations(
                daily_signals, 
                portfolio_value,
                positions,
                allocation_method
            )
            
            # Execute trades
            trades = self._execute_portfolio_trades(
                allocations,
                positions,
                cash,
                current_date
            )
            all_trades.extend(trades)
            
            # Update portfolio value
            portfolio_value, position_values = self._update_portfolio_value(
                positions, cash, current_date
            )
            
            # Record history
            portfolio_history.append({
                'date': current_date,
                'portfolio_value': portfolio_value,
                'cash': cash,
                'positions': len(positions),
                'position_values': position_values
            })
            
            # Rebalance if needed
            if self._should_rebalance(current_date, rebalance_frequency):
                cash, positions = self._rebalance_portfolio(
                    positions, cash, portfolio_value, current_date
                )
                
            current_date += timedelta(days=1)
            
        # Calculate metrics
        metrics = self._calculate_portfolio_metrics(
            portfolio_history,
            all_trades,
            strategy_results
        )
        
        # Save results to database
        self._save_backtest_results(run_id, metrics, portfolio_history, all_trades)
        
        return metrics
    
    def _run_strategies_parallel(self,
                                from_date: datetime,
                                to_date: datetime) -> Dict[str, pd.DataFrame]:
        """
        Run all strategies in parallel
        
        Args:
            from_date: Start date
            to_date: End date
            
        Returns:
            Dictionary of strategy results
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=len(self.strategies)) as executor:
            future_to_strategy = {
                executor.submit(
                    self._run_single_strategy,
                    strategy,
                    from_date,
                    to_date
                ): strategy for strategy in self.strategies
            }
            
            for future in as_completed(future_to_strategy):
                strategy = future_to_strategy[future]
                try:
                    strategy_results = future.result()
                    results[strategy.name] = strategy_results
                    logger.info(f"Completed backtest for strategy: {strategy.name}")
                except Exception as e:
                    logger.error(f"Strategy {strategy.name} failed: {e}")
                    results[strategy.name] = pd.DataFrame()
                    
        return results
    
    def _run_single_strategy(self,
                           strategy: StrategyConfig,
                           from_date: datetime,
                           to_date: datetime) -> pd.DataFrame:
        """
        Run backtest for a single strategy
        
        Args:
            strategy: Strategy configuration
            from_date: Start date
            to_date: End date
            
        Returns:
            DataFrame with strategy signals and trades
        """
        # Query for signals
        signals_query = """
        SELECT 
            t.EntryTime,
            t.ExitTime,
            t.SignalType,
            t.Direction,
            t.EntryPrice,
            t.ExitPrice,
            t.StopLoss,
            t.PnL,
            t.PnLPercent
        FROM BacktestTrades t
        WHERE t.SignalType IN :signal_types
            AND t.EntryTime >= :from_date
            AND t.EntryTime <= :to_date
        ORDER BY t.EntryTime
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(
                text(signals_query),
                {
                    'signal_types': tuple(strategy.signal_types),
                    'from_date': from_date,
                    'to_date': to_date
                }
            )
            df = pd.DataFrame(result.fetchall())
            
        if df.empty:
            return pd.DataFrame()
            
        # Apply ML filter if enabled
        if strategy.use_ml_filter and strategy.name in self.ml_models:
            df['ml_score'] = self._apply_ml_filter(df, strategy)
            df = df[df['ml_score'] >= strategy.ml_threshold]
            
        # Apply position limits
        df['position_count'] = df.groupby(pd.Grouper(key='EntryTime', freq='D')).cumcount()
        df = df[df['position_count'] < strategy.max_positions]
        
        return df
    
    def _apply_ml_filter(self,
                        trades_df: pd.DataFrame,
                        strategy: StrategyConfig) -> pd.Series:
        """
        Apply ML model to filter trades
        
        Args:
            trades_df: DataFrame with trades
            strategy: Strategy configuration
            
        Returns:
            Series with ML scores
        """
        # Placeholder - would use actual ML model
        # In production, load and apply trained ML model
        return pd.Series(np.random.uniform(0.4, 0.9, len(trades_df)), index=trades_df.index)
    
    def _get_daily_signals(self,
                         strategy_results: Dict[str, pd.DataFrame],
                         date: datetime) -> List[Dict]:
        """
        Get all signals for a specific date
        
        Args:
            strategy_results: Results from all strategies
            date: Current date
            
        Returns:
            List of signals for the date
        """
        daily_signals = []
        
        for strategy_name, results_df in strategy_results.items():
            if results_df.empty:
                continue
                
            # Filter for current date
            mask = pd.to_datetime(results_df['EntryTime']).dt.date == date.date()
            day_trades = results_df[mask]
            
            for _, trade in day_trades.iterrows():
                strategy = next(s for s in self.strategies if s.name == strategy_name)
                daily_signals.append({
                    'strategy': strategy_name,
                    'signal_type': trade['SignalType'],
                    'direction': trade['Direction'],
                    'entry_price': trade['EntryPrice'],
                    'stop_loss': trade['StopLoss'],
                    'weight': strategy.weight,
                    'ml_score': trade.get('ml_score', 0.5)
                })
                
        return daily_signals
    
    def _calculate_allocations(self,
                              signals: List[Dict],
                              portfolio_value: float,
                              current_positions: Dict,
                              method: str) -> Dict[str, float]:
        """
        Calculate portfolio allocations
        
        Args:
            signals: List of signals
            portfolio_value: Current portfolio value
            current_positions: Current positions
            method: Allocation method
            
        Returns:
            Dictionary of allocations by strategy
        """
        allocations = {}
        
        if method == 'equal_weight':
            # Equal weight across all signals
            if signals:
                allocation_per_signal = portfolio_value / len(signals)
                for signal in signals:
                    allocations[f"{signal['strategy']}_{signal['signal_type']}"] = allocation_per_signal
                    
        elif method == 'risk_parity':
            # Allocate based on inverse volatility
            volatilities = self._calculate_signal_volatilities(signals)
            inv_vols = {k: 1/v for k, v in volatilities.items()}
            total_inv_vol = sum(inv_vols.values())
            
            for signal in signals:
                key = f"{signal['strategy']}_{signal['signal_type']}"
                weight = inv_vols.get(key, 1) / total_inv_vol if total_inv_vol > 0 else 1/len(signals)
                allocations[key] = portfolio_value * weight
                
        elif method == 'kelly':
            # Kelly criterion based allocation
            for signal in signals:
                key = f"{signal['strategy']}_{signal['signal_type']}"
                kelly_fraction = self._calculate_kelly_fraction(signal)
                allocations[key] = portfolio_value * min(kelly_fraction, 0.25)  # Cap at 25%
                
        elif method == 'ml_weighted':
            # Weight by ML confidence scores
            total_score = sum(s.get('ml_score', 0.5) for s in signals)
            for signal in signals:
                key = f"{signal['strategy']}_{signal['signal_type']}"
                weight = signal.get('ml_score', 0.5) / total_score if total_score > 0 else 1/len(signals)
                allocations[key] = portfolio_value * weight * signal['weight']
                
        return allocations
    
    def _calculate_signal_volatilities(self, signals: List[Dict]) -> Dict[str, float]:
        """Calculate historical volatility for each signal type"""
        volatilities = {}
        
        for signal in signals:
            key = f"{signal['strategy']}_{signal['signal_type']}"
            # Query historical volatility from database
            # Simplified - using fixed values
            volatilities[key] = np.random.uniform(0.01, 0.03)
            
        return volatilities
    
    def _calculate_kelly_fraction(self, signal: Dict) -> float:
        """
        Calculate Kelly fraction for position sizing
        
        Args:
            signal: Signal information
            
        Returns:
            Kelly fraction (0-1)
        """
        # Simplified Kelly calculation
        # In production, would use actual win rate and profit/loss ratios
        win_prob = signal.get('ml_score', 0.5)
        win_loss_ratio = 1.5  # Assumed average
        
        kelly = (win_prob * win_loss_ratio - (1 - win_prob)) / win_loss_ratio
        return max(0, min(kelly, 0.25))  # Cap between 0 and 25%
    
    def _execute_portfolio_trades(self,
                                 allocations: Dict[str, float],
                                 positions: Dict,
                                 cash: float,
                                 date: datetime) -> List[Dict]:
        """
        Execute portfolio trades based on allocations
        
        Args:
            allocations: Position allocations
            positions: Current positions
            cash: Available cash
            date: Current date
            
        Returns:
            List of executed trades
        """
        trades = []
        
        for position_id, allocation in allocations.items():
            if allocation > cash:
                allocation = cash  # Can't allocate more than available cash
                
            if allocation > 0:
                trade = {
                    'position_id': position_id,
                    'date': date,
                    'allocation': allocation,
                    'action': 'BUY'
                }
                trades.append(trade)
                
                # Update positions
                if position_id in positions:
                    positions[position_id]['size'] += allocation
                else:
                    positions[position_id] = {
                        'size': allocation,
                        'entry_date': date,
                        'entry_price': allocation  # Simplified
                    }
                    
                cash -= allocation
                
        return trades
    
    def _update_portfolio_value(self,
                               positions: Dict,
                               cash: float,
                               date: datetime) -> Tuple[float, Dict]:
        """
        Update portfolio value based on current positions
        
        Args:
            positions: Current positions
            cash: Cash balance
            date: Current date
            
        Returns:
            Tuple of (portfolio_value, position_values)
        """
        position_values = {}
        total_position_value = 0
        
        for position_id, position in positions.items():
            # Get current value (simplified - would fetch from market data)
            current_value = position['size'] * (1 + np.random.uniform(-0.02, 0.02))
            position_values[position_id] = current_value
            total_position_value += current_value
            
        portfolio_value = cash + total_position_value
        return portfolio_value, position_values
    
    def _should_rebalance(self,
                         date: datetime,
                         frequency: str) -> bool:
        """
        Check if portfolio should be rebalanced
        
        Args:
            date: Current date
            frequency: Rebalance frequency
            
        Returns:
            True if should rebalance
        """
        if frequency == 'daily':
            return True
        elif frequency == 'weekly':
            return date.weekday() == 0  # Monday
        elif frequency == 'monthly':
            return date.day == 1
        elif frequency == 'quarterly':
            return date.month in [1, 4, 7, 10] and date.day == 1
        else:
            return False
    
    def _rebalance_portfolio(self,
                           positions: Dict,
                           cash: float,
                           portfolio_value: float,
                           date: datetime) -> Tuple[float, Dict]:
        """
        Rebalance portfolio to target weights
        
        Args:
            positions: Current positions
            cash: Cash balance
            portfolio_value: Total portfolio value
            date: Current date
            
        Returns:
            Tuple of (new_cash, new_positions)
        """
        target_allocations = {}
        
        # Calculate target allocations for each strategy
        for strategy in self.strategies:
            target_value = portfolio_value * strategy.weight
            target_allocations[strategy.name] = target_value
            
        # Rebalance positions (simplified)
        new_positions = {}
        new_cash = cash
        
        for strategy_name, target_value in target_allocations.items():
            # Find positions for this strategy
            strategy_positions = {k: v for k, v in positions.items() if strategy_name in k}
            
            if strategy_positions:
                current_value = sum(p['size'] for p in strategy_positions.values())
                adjustment = target_value - current_value
                
                if adjustment > 0:
                    # Buy more
                    new_cash -= adjustment
                else:
                    # Sell some
                    new_cash += abs(adjustment)
                    
                # Update positions (simplified)
                for pos_id in strategy_positions:
                    scale_factor = target_value / current_value if current_value > 0 else 1
                    new_positions[pos_id] = {
                        'size': positions[pos_id]['size'] * scale_factor,
                        'entry_date': positions[pos_id]['entry_date'],
                        'entry_price': positions[pos_id]['entry_price']
                    }
                    
        return new_cash, new_positions
    
    def _calculate_portfolio_metrics(self,
                                    history: List[Dict],
                                    trades: List[Dict],
                                    strategy_results: Dict) -> PortfolioMetrics:
        """
        Calculate portfolio performance metrics
        
        Args:
            history: Portfolio value history
            trades: All executed trades
            strategy_results: Individual strategy results
            
        Returns:
            PortfolioMetrics object
        """
        df = pd.DataFrame(history)
        df['returns'] = df['portfolio_value'].pct_change()
        
        # Basic metrics
        total_return = (df['portfolio_value'].iloc[-1] - self.initial_capital) / self.initial_capital
        
        # Annualized metrics
        days = (df['date'].iloc[-1] - df['date'].iloc[0]).days
        years = days / 365.25
        annualized_return = (1 + total_return) ** (1/years) - 1 if years > 0 else 0
        
        # Risk metrics
        volatility = df['returns'].std() * np.sqrt(252)  # Annualized
        
        # Sharpe ratio
        excess_returns = df['returns'] - self.risk_free_rate/252
        sharpe_ratio = excess_returns.mean() / excess_returns.std() * np.sqrt(252) if excess_returns.std() > 0 else 0
        
        # Sortino ratio (downside deviation)
        downside_returns = df['returns'][df['returns'] < 0]
        downside_std = downside_returns.std() * np.sqrt(252)
        sortino_ratio = (annualized_return - self.risk_free_rate) / downside_std if downside_std > 0 else 0
        
        # Maximum drawdown
        cumulative = (1 + df['returns']).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdown.min())
        
        # Drawdown duration
        drawdown_start = drawdown[drawdown < 0].index[0] if any(drawdown < 0) else None
        drawdown_end = drawdown[drawdown == drawdown.min()].index[0] if any(drawdown < 0) else None
        max_drawdown_duration = (drawdown_end - drawdown_start) if drawdown_start and drawdown_end else 0
        
        # Calmar ratio
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0
        
        # Trade metrics
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # Profit factor
        gross_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Strategy correlation matrix
        correlation_matrix = self._calculate_strategy_correlations(strategy_results)
        
        # Strategy contributions
        strategy_contributions = self._calculate_strategy_contributions(strategy_results, total_return)
        
        # Risk metrics
        risk_metrics = {
            'var_95': df['returns'].quantile(0.05) * df['portfolio_value'].iloc[-1],
            'cvar_95': df['returns'][df['returns'] <= df['returns'].quantile(0.05)].mean() * df['portfolio_value'].iloc[-1],
            'skewness': df['returns'].skew(),
            'kurtosis': df['returns'].kurtosis()
        }
        
        return PortfolioMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_duration=max_drawdown_duration,
            calmar_ratio=calmar_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades,
            correlation_matrix=correlation_matrix,
            strategy_contributions=strategy_contributions,
            risk_metrics=risk_metrics
        )
    
    def _calculate_strategy_correlations(self,
                                        strategy_results: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Calculate correlation matrix between strategies"""
        returns_dict = {}
        
        for strategy_name, df in strategy_results.items():
            if not df.empty:
                # Calculate daily returns for strategy
                df['date'] = pd.to_datetime(df['EntryTime']).dt.date
                daily_returns = df.groupby('date')['PnLPercent'].sum()
                returns_dict[strategy_name] = daily_returns
                
        if returns_dict:
            returns_df = pd.DataFrame(returns_dict).fillna(0)
            return returns_df.corr()
        else:
            return pd.DataFrame()
    
    def _calculate_strategy_contributions(self,
                                         strategy_results: Dict[str, pd.DataFrame],
                                         total_return: float) -> Dict[str, float]:
        """Calculate each strategy's contribution to total return"""
        contributions = {}
        
        for strategy_name, df in strategy_results.items():
            if not df.empty:
                strategy_return = df['PnL'].sum() / self.initial_capital
                contribution = strategy_return / total_return if total_return != 0 else 0
                contributions[strategy_name] = contribution
                
        return contributions
    
    def _save_backtest_results(self,
                              run_id: str,
                              metrics: PortfolioMetrics,
                              history: List[Dict],
                              trades: List[Dict]):
        """Save backtest results to database"""
        with self.engine.begin() as conn:
            # Save main run information
            conn.execute(text("""
                INSERT INTO PortfolioBacktests (
                    RunId, Name, FromDate, ToDate, InitialCapital,
                    FinalCapital, TotalReturn, SharpeRatio, MaxDrawdown,
                    WinRate, Results, Status, CompletedAt
                ) VALUES (
                    :run_id, :name, :from_date, :to_date, :initial_capital,
                    :final_capital, :total_return, :sharpe_ratio, :max_drawdown,
                    :win_rate, :results, 'COMPLETED', GETDATE()
                )
            """), {
                'run_id': run_id,
                'name': f"Portfolio_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'from_date': history[0]['date'],
                'to_date': history[-1]['date'],
                'initial_capital': self.initial_capital,
                'final_capital': history[-1]['portfolio_value'],
                'total_return': metrics.total_return * 100,
                'sharpe_ratio': metrics.sharpe_ratio,
                'max_drawdown': metrics.max_drawdown * 100,
                'win_rate': metrics.win_rate * 100,
                'results': json.dumps({
                    'metrics': {
                        'annualized_return': metrics.annualized_return,
                        'volatility': metrics.volatility,
                        'sortino_ratio': metrics.sortino_ratio,
                        'calmar_ratio': metrics.calmar_ratio,
                        'profit_factor': metrics.profit_factor
                    },
                    'risk_metrics': metrics.risk_metrics,
                    'strategy_contributions': metrics.strategy_contributions
                }, default=str)
            })
            
        logger.info(f"Portfolio backtest {run_id} completed and saved")