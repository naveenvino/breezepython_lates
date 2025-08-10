"""
Performance Tracker for Paper Trading
Comprehensive performance analytics and reporting
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta, date
from dataclasses import dataclass, field
import logging
from collections import defaultdict
import json
from sqlalchemy import create_engine, text
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import base64

logger = logging.getLogger(__name__)

@dataclass
class TradeMetrics:
    """Individual trade metrics"""
    trade_id: str
    signal_type: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    direction: str
    pnl: float
    pnl_percent: float
    holding_period: Optional[timedelta]
    max_profit: float
    max_loss: float
    risk_reward_ratio: float
    commission: float

@dataclass
class DailyMetrics:
    """Daily performance metrics"""
    date: date
    total_trades: int
    winning_trades: int
    losing_trades: int
    gross_pnl: float
    net_pnl: float
    commission: float
    win_rate: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    total_volume: float
    ending_capital: float

@dataclass
class PerformanceReport:
    """Comprehensive performance report"""
    total_return: float
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    win_rate: float
    profit_factor: float
    expectancy: float
    avg_trade_pnl: float
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float
    total_trades: int
    total_commission: float
    avg_holding_period: timedelta
    kelly_criterion: float
    risk_adjusted_return: float

class PerformanceTracker:
    """Tracks and analyzes paper trading performance"""
    
    def __init__(self, db_connection_string: str, initial_capital: float = 500000):
        """
        Initialize performance tracker
        
        Args:
            db_connection_string: Database connection
            initial_capital: Starting capital
        """
        self.engine = create_engine(db_connection_string)
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.trades = []
        self.daily_metrics = {}
        self.equity_curve = []
        self.drawdown_series = []
        self.signal_performance = defaultdict(list)
        
    def record_trade(self, trade: Dict[str, Any]):
        """
        Record a paper trade
        
        Args:
            trade: Trade details
        """
        try:
            # Create trade metrics
            metrics = TradeMetrics(
                trade_id=trade['trade_id'],
                signal_type=trade['signal_type'],
                entry_time=trade['entry_time'],
                exit_time=trade.get('exit_time'),
                entry_price=trade['entry_price'],
                exit_price=trade.get('exit_price'),
                quantity=trade['quantity'],
                direction=trade['direction'],
                pnl=trade.get('pnl', 0),
                pnl_percent=trade.get('pnl_percent', 0),
                holding_period=None,
                max_profit=trade.get('max_profit', 0),
                max_loss=trade.get('max_loss', 0),
                risk_reward_ratio=0,
                commission=trade.get('commission', 0)
            )
            
            # Calculate holding period
            if metrics.exit_time:
                metrics.holding_period = metrics.exit_time - metrics.entry_time
                
            # Calculate risk-reward ratio
            if metrics.max_loss != 0:
                metrics.risk_reward_ratio = abs(metrics.max_profit / metrics.max_loss)
                
            # Store trade
            self.trades.append(metrics)
            self.signal_performance[metrics.signal_type].append(metrics)
            
            # Update capital
            self.current_capital += metrics.pnl - metrics.commission
            
            # Update equity curve
            self.equity_curve.append({
                'timestamp': metrics.exit_time or datetime.now(),
                'capital': self.current_capital,
                'trade_id': metrics.trade_id
            })
            
            # Save to database
            self._save_trade_to_db(metrics)
            
            # Update daily metrics
            trade_date = metrics.entry_time.date()
            self._update_daily_metrics(trade_date)
            
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
            
    def get_performance_report(self, 
                              from_date: Optional[datetime] = None,
                              to_date: Optional[datetime] = None) -> PerformanceReport:
        """
        Generate comprehensive performance report
        
        Args:
            from_date: Start date for analysis
            to_date: End date for analysis
            
        Returns:
            PerformanceReport object
        """
        # Filter trades by date
        filtered_trades = self._filter_trades(from_date, to_date)
        
        if not filtered_trades:
            return self._empty_report()
            
        # Calculate metrics
        total_trades = len(filtered_trades)
        winning_trades = [t for t in filtered_trades if t.pnl > 0]
        losing_trades = [t for t in filtered_trades if t.pnl <= 0]
        
        # Basic metrics
        total_pnl = sum(t.pnl for t in filtered_trades)
        total_commission = sum(t.commission for t in filtered_trades)
        net_pnl = total_pnl - total_commission
        
        # Returns
        total_return = net_pnl
        total_return_pct = (net_pnl / self.initial_capital) * 100
        
        # Win/Loss metrics
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        
        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Expectancy
        expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
        
        # Risk metrics
        returns = self._calculate_returns()
        sharpe_ratio = self._calculate_sharpe_ratio(returns)
        sortino_ratio = self._calculate_sortino_ratio(returns)
        calmar_ratio = self._calculate_calmar_ratio(returns)
        
        # Drawdown
        max_dd, max_dd_duration = self._calculate_max_drawdown()
        
        # Best/Worst trades
        best_trade = max(t.pnl for t in filtered_trades) if filtered_trades else 0
        worst_trade = min(t.pnl for t in filtered_trades) if filtered_trades else 0
        
        # Average holding period
        holding_periods = [t.holding_period for t in filtered_trades if t.holding_period]
        avg_holding = np.mean(holding_periods) if holding_periods else timedelta(0)
        
        # Kelly Criterion
        kelly = self._calculate_kelly_criterion(win_rate, avg_win, avg_loss)
        
        # Risk-adjusted return
        risk_adj_return = total_return_pct / abs(max_dd) if max_dd != 0 else 0
        
        return PerformanceReport(
            total_return=total_return,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_dd,
            max_drawdown_duration=max_dd_duration,
            win_rate=win_rate * 100,
            profit_factor=profit_factor,
            expectancy=expectancy,
            avg_trade_pnl=net_pnl / total_trades if total_trades > 0 else 0,
            avg_win=avg_win,
            avg_loss=avg_loss,
            best_trade=best_trade,
            worst_trade=worst_trade,
            total_trades=total_trades,
            total_commission=total_commission,
            avg_holding_period=avg_holding,
            kelly_criterion=kelly,
            risk_adjusted_return=risk_adj_return
        )
        
    def get_signal_performance(self) -> Dict[str, Dict]:
        """
        Get performance breakdown by signal type
        
        Returns:
            Dictionary with signal-wise performance
        """
        signal_stats = {}
        
        for signal_type, trades in self.signal_performance.items():
            if not trades:
                continue
                
            winning = [t for t in trades if t.pnl > 0]
            
            signal_stats[signal_type] = {
                'total_trades': len(trades),
                'win_rate': len(winning) / len(trades) * 100 if trades else 0,
                'total_pnl': sum(t.pnl for t in trades),
                'avg_pnl': np.mean([t.pnl for t in trades]),
                'best_trade': max(t.pnl for t in trades),
                'worst_trade': min(t.pnl for t in trades),
                'avg_holding_period': np.mean([t.holding_period.total_seconds()/3600 
                                              for t in trades if t.holding_period]),
                'profit_factor': self._calculate_profit_factor(trades)
            }
            
        return signal_stats
        
    def get_daily_performance(self) -> pd.DataFrame:
        """
        Get daily performance metrics
        
        Returns:
            DataFrame with daily metrics
        """
        daily_data = []
        
        for date, metrics in sorted(self.daily_metrics.items()):
            daily_data.append({
                'date': date,
                'trades': metrics.total_trades,
                'gross_pnl': metrics.gross_pnl,
                'net_pnl': metrics.net_pnl,
                'win_rate': metrics.win_rate,
                'commission': metrics.commission,
                'capital': metrics.ending_capital
            })
            
        return pd.DataFrame(daily_data)
        
    def get_trade_distribution(self) -> Dict[str, Any]:
        """
        Get trade distribution statistics
        
        Returns:
            Dictionary with distribution metrics
        """
        if not self.trades:
            return {}
            
        pnls = [t.pnl for t in self.trades]
        
        return {
            'mean': np.mean(pnls),
            'median': np.median(pnls),
            'std': np.std(pnls),
            'skew': pd.Series(pnls).skew(),
            'kurtosis': pd.Series(pnls).kurtosis(),
            'percentiles': {
                '5%': np.percentile(pnls, 5),
                '25%': np.percentile(pnls, 25),
                '50%': np.percentile(pnls, 50),
                '75%': np.percentile(pnls, 75),
                '95%': np.percentile(pnls, 95)
            },
            'histogram': np.histogram(pnls, bins=20)
        }
        
    def generate_charts(self) -> Dict[str, str]:
        """
        Generate performance charts
        
        Returns:
            Dictionary with base64 encoded chart images
        """
        charts = {}
        
        # Equity curve
        charts['equity_curve'] = self._generate_equity_curve()
        
        # Drawdown chart
        charts['drawdown'] = self._generate_drawdown_chart()
        
        # PnL distribution
        charts['pnl_distribution'] = self._generate_pnl_distribution()
        
        # Signal performance
        charts['signal_performance'] = self._generate_signal_chart()
        
        # Daily returns
        charts['daily_returns'] = self._generate_daily_returns_chart()
        
        # Rolling metrics
        charts['rolling_metrics'] = self._generate_rolling_metrics()
        
        return charts
        
    def export_report(self, filepath: str, format: str = 'excel'):
        """
        Export performance report
        
        Args:
            filepath: Output file path
            format: Export format (excel, csv, json, html)
        """
        try:
            report = self.get_performance_report()
            signal_perf = self.get_signal_performance()
            daily_perf = self.get_daily_performance()
            
            if format == 'excel':
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    # Summary sheet
                    summary_df = pd.DataFrame([report.__dict__])
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                    
                    # Signal performance
                    signal_df = pd.DataFrame(signal_perf).T
                    signal_df.to_excel(writer, sheet_name='Signal Performance')
                    
                    # Daily performance
                    daily_perf.to_excel(writer, sheet_name='Daily Performance', index=False)
                    
                    # Trade log
                    trades_df = pd.DataFrame([t.__dict__ for t in self.trades])
                    trades_df.to_excel(writer, sheet_name='Trade Log', index=False)
                    
            elif format == 'csv':
                # Export to multiple CSV files
                summary_df = pd.DataFrame([report.__dict__])
                summary_df.to_csv(filepath.replace('.csv', '_summary.csv'), index=False)
                
                signal_df = pd.DataFrame(signal_perf).T
                signal_df.to_csv(filepath.replace('.csv', '_signals.csv'))
                
                daily_perf.to_csv(filepath.replace('.csv', '_daily.csv'), index=False)
                
            elif format == 'json':
                export_data = {
                    'summary': report.__dict__,
                    'signal_performance': signal_perf,
                    'daily_performance': daily_perf.to_dict('records'),
                    'trades': [t.__dict__ for t in self.trades]
                }
                
                with open(filepath, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
                    
            elif format == 'html':
                self._generate_html_report(filepath, report, signal_perf, daily_perf)
                
            logger.info(f"Report exported to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to export report: {e}")
            
    def _filter_trades(self, from_date: Optional[datetime], to_date: Optional[datetime]) -> List[TradeMetrics]:
        """Filter trades by date range"""
        filtered = self.trades
        
        if from_date:
            filtered = [t for t in filtered if t.entry_time >= from_date]
        if to_date:
            filtered = [t for t in filtered if t.entry_time <= to_date]
            
        return filtered
        
    def _calculate_returns(self) -> np.ndarray:
        """Calculate period returns"""
        if len(self.equity_curve) < 2:
            return np.array([])
            
        capitals = [e['capital'] for e in self.equity_curve]
        returns = np.diff(capitals) / capitals[:-1]
        
        return returns
        
    def _calculate_sharpe_ratio(self, returns: np.ndarray, risk_free_rate: float = 0.05) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) == 0:
            return 0
            
        daily_rf = risk_free_rate / 252
        excess_returns = returns - daily_rf
        
        if excess_returns.std() == 0:
            return 0
            
        return np.sqrt(252) * excess_returns.mean() / excess_returns.std()
        
    def _calculate_sortino_ratio(self, returns: np.ndarray, target: float = 0) -> float:
        """Calculate Sortino ratio"""
        if len(returns) == 0:
            return 0
            
        downside_returns = returns[returns < target]
        
        if len(downside_returns) == 0:
            return float('inf') if returns.mean() > target else 0
            
        downside_std = np.sqrt(np.mean((downside_returns - target) ** 2))
        
        if downside_std == 0:
            return 0
            
        return np.sqrt(252) * (returns.mean() - target) / downside_std
        
    def _calculate_calmar_ratio(self, returns: np.ndarray) -> float:
        """Calculate Calmar ratio"""
        if len(returns) == 0:
            return 0
            
        annual_return = (1 + returns.mean()) ** 252 - 1
        max_dd, _ = self._calculate_max_drawdown()
        
        if max_dd == 0:
            return 0
            
        return annual_return / abs(max_dd)
        
    def _calculate_max_drawdown(self) -> Tuple[float, int]:
        """Calculate maximum drawdown and duration"""
        if not self.equity_curve:
            return 0, 0
            
        capitals = [e['capital'] for e in self.equity_curve]
        
        # Calculate drawdown series
        peak = capitals[0]
        drawdowns = []
        
        for capital in capitals:
            if capital > peak:
                peak = capital
            drawdown = (capital - peak) / peak
            drawdowns.append(drawdown)
            
        self.drawdown_series = drawdowns
        
        # Find maximum drawdown
        max_dd = min(drawdowns) if drawdowns else 0
        
        # Calculate max drawdown duration
        duration = 0
        current_duration = 0
        
        for dd in drawdowns:
            if dd < 0:
                current_duration += 1
                duration = max(duration, current_duration)
            else:
                current_duration = 0
                
        return max_dd * 100, duration
        
    def _calculate_kelly_criterion(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Calculate Kelly criterion for position sizing"""
        if avg_loss == 0:
            return 0
            
        b = abs(avg_win / avg_loss)  # Win/loss ratio
        p = win_rate
        q = 1 - p
        
        if b == 0:
            return 0
            
        kelly = (p * b - q) / b
        
        # Apply Kelly fraction (typically 25% of full Kelly)
        return max(0, min(0.25, kelly * 0.25))
        
    def _calculate_profit_factor(self, trades: List[TradeMetrics]) -> float:
        """Calculate profit factor for trades"""
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl <= 0))
        
        return gross_profit / gross_loss if gross_loss > 0 else 0
        
    def _update_daily_metrics(self, date: date):
        """Update daily performance metrics"""
        daily_trades = [t for t in self.trades if t.entry_time.date() == date]
        
        if not daily_trades:
            return
            
        winning = [t for t in daily_trades if t.pnl > 0]
        losing = [t for t in daily_trades if t.pnl <= 0]
        
        self.daily_metrics[date] = DailyMetrics(
            date=date,
            total_trades=len(daily_trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            gross_pnl=sum(t.pnl for t in daily_trades),
            net_pnl=sum(t.pnl - t.commission for t in daily_trades),
            commission=sum(t.commission for t in daily_trades),
            win_rate=len(winning) / len(daily_trades) if daily_trades else 0,
            avg_win=np.mean([t.pnl for t in winning]) if winning else 0,
            avg_loss=np.mean([t.pnl for t in losing]) if losing else 0,
            largest_win=max([t.pnl for t in winning]) if winning else 0,
            largest_loss=min([t.pnl for t in losing]) if losing else 0,
            total_volume=sum(t.quantity for t in daily_trades),
            ending_capital=self.current_capital
        )
        
    def _save_trade_to_db(self, trade: TradeMetrics):
        """Save trade to database"""
        try:
            with self.engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO PaperTrades (
                        TradeId, SignalType, EntryTime, ExitTime,
                        EntryPrice, ExitPrice, Quantity, Direction,
                        PnL, PnLPercent, Commission, Status
                    ) VALUES (
                        :trade_id, :signal_type, :entry_time, :exit_time,
                        :entry_price, :exit_price, :quantity, :direction,
                        :pnl, :pnl_percent, :commission, :status
                    )
                """), {
                    'trade_id': trade.trade_id,
                    'signal_type': trade.signal_type,
                    'entry_time': trade.entry_time,
                    'exit_time': trade.exit_time,
                    'entry_price': trade.entry_price,
                    'exit_price': trade.exit_price,
                    'quantity': trade.quantity,
                    'direction': trade.direction,
                    'pnl': trade.pnl,
                    'pnl_percent': trade.pnl_percent,
                    'commission': trade.commission,
                    'status': 'CLOSED' if trade.exit_time else 'OPEN'
                })
        except Exception as e:
            logger.error(f"Failed to save trade to database: {e}")
            
    def _generate_equity_curve(self) -> str:
        """Generate equity curve chart"""
        if not self.equity_curve:
            return ""
            
        fig, ax = plt.subplots(figsize=(12, 6))
        
        timestamps = [e['timestamp'] for e in self.equity_curve]
        capitals = [e['capital'] for e in self.equity_curve]
        
        ax.plot(timestamps, capitals, linewidth=2)
        ax.axhline(y=self.initial_capital, color='r', linestyle='--', alpha=0.5)
        ax.fill_between(timestamps, self.initial_capital, capitals, 
                        where=[c >= self.initial_capital for c in capitals],
                        color='green', alpha=0.3)
        ax.fill_between(timestamps, self.initial_capital, capitals,
                        where=[c < self.initial_capital for c in capitals],
                        color='red', alpha=0.3)
        
        ax.set_title('Equity Curve')
        ax.set_xlabel('Date')
        ax.set_ylabel('Capital')
        ax.grid(True, alpha=0.3)
        
        return self._fig_to_base64(fig)
        
    def _generate_drawdown_chart(self) -> str:
        """Generate drawdown chart"""
        if not self.drawdown_series:
            return ""
            
        fig, ax = plt.subplots(figsize=(12, 4))
        
        timestamps = [e['timestamp'] for e in self.equity_curve]
        
        ax.fill_between(timestamps, 0, [d*100 for d in self.drawdown_series],
                        color='red', alpha=0.3)
        ax.plot(timestamps, [d*100 for d in self.drawdown_series], 
               color='red', linewidth=1)
        
        ax.set_title('Drawdown')
        ax.set_xlabel('Date')
        ax.set_ylabel('Drawdown %')
        ax.grid(True, alpha=0.3)
        
        return self._fig_to_base64(fig)
        
    def _generate_pnl_distribution(self) -> str:
        """Generate PnL distribution chart"""
        if not self.trades:
            return ""
            
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        pnls = [t.pnl for t in self.trades]
        
        # Histogram
        ax1.hist(pnls, bins=30, edgecolor='black', alpha=0.7)
        ax1.axvline(x=0, color='r', linestyle='--')
        ax1.set_title('PnL Distribution')
        ax1.set_xlabel('PnL')
        ax1.set_ylabel('Frequency')
        
        # Box plot
        ax2.boxplot(pnls, vert=True)
        ax2.set_title('PnL Box Plot')
        ax2.set_ylabel('PnL')
        
        return self._fig_to_base64(fig)
        
    def _generate_signal_chart(self) -> str:
        """Generate signal performance chart"""
        signal_perf = self.get_signal_performance()
        
        if not signal_perf:
            return ""
            
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        signals = list(signal_perf.keys())
        win_rates = [signal_perf[s]['win_rate'] for s in signals]
        total_pnls = [signal_perf[s]['total_pnl'] for s in signals]
        
        # Win rate by signal
        ax1.bar(signals, win_rates, color=['green' if w > 50 else 'red' for w in win_rates])
        ax1.axhline(y=50, color='black', linestyle='--', alpha=0.5)
        ax1.set_title('Win Rate by Signal')
        ax1.set_xlabel('Signal Type')
        ax1.set_ylabel('Win Rate %')
        
        # Total PnL by signal
        colors = ['green' if p > 0 else 'red' for p in total_pnls]
        ax2.bar(signals, total_pnls, color=colors)
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax2.set_title('Total PnL by Signal')
        ax2.set_xlabel('Signal Type')
        ax2.set_ylabel('PnL')
        
        return self._fig_to_base64(fig)
        
    def _generate_daily_returns_chart(self) -> str:
        """Generate daily returns chart"""
        daily_perf = self.get_daily_performance()
        
        if daily_perf.empty:
            return ""
            
        fig, ax = plt.subplots(figsize=(12, 5))
        
        colors = ['green' if p > 0 else 'red' for p in daily_perf['net_pnl']]
        ax.bar(daily_perf['date'], daily_perf['net_pnl'], color=colors, alpha=0.7)
        
        ax.set_title('Daily Returns')
        ax.set_xlabel('Date')
        ax.set_ylabel('Net PnL')
        ax.grid(True, alpha=0.3)
        
        return self._fig_to_base64(fig)
        
    def _generate_rolling_metrics(self) -> str:
        """Generate rolling metrics chart"""
        if len(self.trades) < 20:
            return ""
            
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # Prepare data
        trade_dates = [t.entry_time for t in self.trades]
        trade_pnls = [t.pnl for t in self.trades]
        
        # Rolling win rate
        window = 20
        rolling_wins = pd.Series([1 if p > 0 else 0 for p in trade_pnls]).rolling(window).mean() * 100
        axes[0, 0].plot(trade_dates, rolling_wins)
        axes[0, 0].axhline(y=50, color='r', linestyle='--', alpha=0.5)
        axes[0, 0].set_title(f'Rolling Win Rate ({window} trades)')
        axes[0, 0].set_ylabel('Win Rate %')
        
        # Rolling average PnL
        rolling_pnl = pd.Series(trade_pnls).rolling(window).mean()
        axes[0, 1].plot(trade_dates, rolling_pnl)
        axes[0, 1].axhline(y=0, color='r', linestyle='--', alpha=0.5)
        axes[0, 1].set_title(f'Rolling Average PnL ({window} trades)')
        axes[0, 1].set_ylabel('Average PnL')
        
        # Rolling Sharpe
        rolling_sharpe = pd.Series(trade_pnls).rolling(window).apply(
            lambda x: np.sqrt(252) * x.mean() / x.std() if x.std() > 0 else 0
        )
        axes[1, 0].plot(trade_dates, rolling_sharpe)
        axes[1, 0].axhline(y=1, color='r', linestyle='--', alpha=0.5)
        axes[1, 0].set_title(f'Rolling Sharpe Ratio ({window} trades)')
        axes[1, 0].set_ylabel('Sharpe Ratio')
        
        # Cumulative PnL
        cumulative_pnl = pd.Series(trade_pnls).cumsum()
        axes[1, 1].plot(trade_dates, cumulative_pnl)
        axes[1, 1].fill_between(trade_dates, 0, cumulative_pnl,
                               where=cumulative_pnl >= 0, color='green', alpha=0.3)
        axes[1, 1].fill_between(trade_dates, 0, cumulative_pnl,
                               where=cumulative_pnl < 0, color='red', alpha=0.3)
        axes[1, 1].set_title('Cumulative PnL')
        axes[1, 1].set_ylabel('Cumulative PnL')
        
        plt.tight_layout()
        return self._fig_to_base64(fig)
        
    def _fig_to_base64(self, fig) -> str:
        """Convert matplotlib figure to base64 string"""
        buf = BytesIO()
        fig.savefig(buf, format='png')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return img_base64
        
    def _generate_html_report(self, filepath: str, report: PerformanceReport, 
                             signal_perf: Dict, daily_perf: pd.DataFrame):
        """Generate HTML report"""
        charts = self.generate_charts()
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Paper Trading Performance Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; 
                          background: #f9f9f9; border-radius: 5px; }}
                .positive {{ color: green; }}
                .negative {{ color: red; }}
                img {{ max-width: 100%; height: auto; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>Paper Trading Performance Report</h1>
            
            <h2>Summary Metrics</h2>
            <div>
                <div class="metric">
                    <strong>Total Return:</strong> 
                    <span class="{'positive' if report.total_return > 0 else 'negative'}">
                        ₹{report.total_return:,.2f} ({report.total_return_pct:.2f}%)
                    </span>
                </div>
                <div class="metric">
                    <strong>Sharpe Ratio:</strong> {report.sharpe_ratio:.2f}
                </div>
                <div class="metric">
                    <strong>Win Rate:</strong> {report.win_rate:.2f}%
                </div>
                <div class="metric">
                    <strong>Profit Factor:</strong> {report.profit_factor:.2f}
                </div>
                <div class="metric">
                    <strong>Max Drawdown:</strong> {report.max_drawdown:.2f}%
                </div>
                <div class="metric">
                    <strong>Total Trades:</strong> {report.total_trades}
                </div>
            </div>
            
            <h2>Charts</h2>
            <h3>Equity Curve</h3>
            <img src="data:image/png;base64,{charts.get('equity_curve', '')}" />
            
            <h3>Drawdown</h3>
            <img src="data:image/png;base64,{charts.get('drawdown', '')}" />
            
            <h3>PnL Distribution</h3>
            <img src="data:image/png;base64,{charts.get('pnl_distribution', '')}" />
            
            <h3>Signal Performance</h3>
            <img src="data:image/png;base64,{charts.get('signal_performance', '')}" />
            
            <h3>Daily Returns</h3>
            <img src="data:image/png;base64,{charts.get('daily_returns', '')}" />
            
            <h3>Rolling Metrics</h3>
            <img src="data:image/png;base64,{charts.get('rolling_metrics', '')}" />
            
            <h2>Signal Performance Table</h2>
            <table>
                <tr>
                    <th>Signal</th>
                    <th>Trades</th>
                    <th>Win Rate</th>
                    <th>Total PnL</th>
                    <th>Avg PnL</th>
                    <th>Profit Factor</th>
                </tr>
                {''.join([f'''
                <tr>
                    <td>{signal}</td>
                    <td>{stats['total_trades']}</td>
                    <td>{stats['win_rate']:.2f}%</td>
                    <td class="{'positive' if stats['total_pnl'] > 0 else 'negative'}">
                        ₹{stats['total_pnl']:,.2f}
                    </td>
                    <td>₹{stats['avg_pnl']:,.2f}</td>
                    <td>{stats['profit_factor']:.2f}</td>
                </tr>
                ''' for signal, stats in signal_perf.items()])}
            </table>
            
            <p><i>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i></p>
        </body>
        </html>
        """
        
        with open(filepath, 'w') as f:
            f.write(html_content)
            
    def _empty_report(self) -> PerformanceReport:
        """Return empty performance report"""
        return PerformanceReport(
            total_return=0,
            total_return_pct=0,
            sharpe_ratio=0,
            sortino_ratio=0,
            calmar_ratio=0,
            max_drawdown=0,
            max_drawdown_duration=0,
            win_rate=0,
            profit_factor=0,
            expectancy=0,
            avg_trade_pnl=0,
            avg_win=0,
            avg_loss=0,
            best_trade=0,
            worst_trade=0,
            total_trades=0,
            total_commission=0,
            avg_holding_period=timedelta(0),
            kelly_criterion=0,
            risk_adjusted_return=0
        )