"""
Performance Analytics Service
Calculates trading performance metrics and analytics
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import numpy as np
import pyodbc
from contextlib import contextmanager

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Trading performance metrics"""
    total_pnl: float
    win_rate: float
    avg_win: float
    avg_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    sharpe_ratio: float
    max_drawdown: float
    profit_factor: float
    risk_reward_ratio: float
    daily_var_95: float
    recovery_factor: float
    
class PerformanceAnalyticsService:
    """
    Service for calculating trading performance analytics
    """
    
    def __init__(self):
        self.conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=(localdb)\\mssqllocaldb;"
            "DATABASE=KiteConnectApi;"
            "Trusted_Connection=yes;"
        )
    
    @contextmanager
    def get_db(self):
        """Database connection context manager"""
        conn = pyodbc.connect(self.conn_str)
        try:
            yield conn
        finally:
            conn.close()
    
    def get_performance_analytics(self, period: str = 'month', start_date: Optional[date] = None, end_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Get comprehensive performance analytics
        
        Args:
            period: 'today', 'week', 'month', 'year', or 'custom'
            start_date: Start date for custom period
            end_date: End date for custom period
        """
        try:
            # Determine date range
            if period == 'custom':
                if not start_date or not end_date:
                    end_date = date.today()
                    start_date = end_date - timedelta(days=30)
            else:
                end_date = date.today()
                if period == 'today':
                    start_date = end_date
                elif period == 'week':
                    start_date = end_date - timedelta(days=7)
                elif period == 'month':
                    start_date = end_date - timedelta(days=30)
                elif period == 'year':
                    start_date = end_date - timedelta(days=365)
                else:
                    start_date = end_date - timedelta(days=30)
            
            # Get trades from database
            trades = self._get_trades(start_date, end_date)
            
            if not trades:
                return self._empty_analytics()
            
            # Calculate metrics
            metrics = self._calculate_metrics(trades)
            
            # Get daily P&L
            daily_pnl = self._calculate_daily_pnl(trades)
            
            # Get cumulative P&L
            cumulative_pnl = self._calculate_cumulative_pnl(daily_pnl)
            
            # Get signal performance
            signal_performance = self._calculate_signal_performance(trades)
            
            # Get hourly performance
            hourly_performance = self._calculate_hourly_performance(trades)
            
            return {
                'success': True,
                'period': period,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'metrics': metrics.__dict__,
                'trades': trades,
                'daily_pnl': daily_pnl,
                'cumulative_pnl': cumulative_pnl,
                'signal_performance': signal_performance,
                'hourly_performance': hourly_performance
            }
            
        except Exception as e:
            logger.error(f"Error calculating analytics: {e}")
            return self._empty_analytics()
    
    def _get_trades(self, start_date: date, end_date: date) -> List[Dict]:
        """Get trades from database"""
        trades = []
        
        try:
            with self.get_db() as conn:
                cursor = conn.cursor()
                
                # Get closed positions
                query = """
                    SELECT 
                        p.id,
                        p.signal_type,
                        p.main_strike,
                        p.main_price,
                        p.main_quantity,
                        p.hedge_strike,
                        p.hedge_price,
                        p.entry_time,
                        p.exit_time,
                        p.pnl,
                        p.status
                    FROM LivePositions p
                    WHERE p.entry_time >= ? AND p.entry_time <= ?
                    ORDER BY p.entry_time DESC
                """
                
                cursor.execute(query, (start_date, datetime.combine(end_date, datetime.max.time())))
                
                for row in cursor.fetchall():
                    trade = {
                        'id': row[0],
                        'signal': row[1],
                        'strike': row[2],
                        'type': 'PE' if row[1] in ['S1', 'S2', 'S4', 'S7'] else 'CE',
                        'entry': float(row[3]) if row[3] else 0,
                        'exit': 0,  # Would need to calculate from exit data
                        'quantity': row[4] * 75 if row[4] else 0,
                        'hedge_strike': row[5],
                        'hedge_price': float(row[6]) if row[6] else 0,
                        'entry_time': row[7],
                        'exit_time': row[8],
                        'pnl': float(row[9]) if row[9] else 0,
                        'status': row[10],
                        'date': row[7]  # For compatibility
                    }
                    trades.append(trade)
                
                # If no real trades, get from BacktestTrades for demo
                if not trades:
                    cursor.execute("""
                        SELECT TOP 100
                            TradeID as id,
                            SignalType as signal,
                            Strike,
                            'PE' as type,
                            EntryPrice as entry,
                            ExitPrice as exit_price,
                            Quantity,
                            EntryTime,
                            ExitTime,
                            PnL,
                            Status
                        FROM BacktestTrades
                        WHERE EntryTime >= ? AND EntryTime <= ?
                        ORDER BY EntryTime DESC
                    """, (start_date, datetime.combine(end_date, datetime.max.time())))
                    
                    for row in cursor.fetchall():
                        trade = {
                            'id': row[0],
                            'signal': row[1],
                            'strike': row[2],
                            'type': row[3],
                            'entry': float(row[4]) if row[4] else 0,
                            'exit': float(row[5]) if row[5] else 0,
                            'quantity': row[6] if row[6] else 0,
                            'entry_time': row[7],
                            'exit_time': row[8],
                            'pnl': float(row[9]) if row[9] else 0,
                            'status': row[10],
                            'date': row[7]
                        }
                        trades.append(trade)
                
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
        
        return trades
    
    def _calculate_metrics(self, trades: List[Dict]) -> PerformanceMetrics:
        """Calculate performance metrics from trades"""
        if not trades:
            return PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        
        # Basic metrics
        total_trades = len(trades)
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] < 0]
        
        total_pnl = sum(t['pnl'] for t in trades)
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = abs(sum(t['pnl'] for t in losing_trades) / len(losing_trades)) if losing_trades else 0
        
        # Risk/Reward ratio
        risk_reward_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0
        
        # Profit factor
        gross_profit = sum(t['pnl'] for t in winning_trades) if winning_trades else 0
        gross_loss = abs(sum(t['pnl'] for t in losing_trades)) if losing_trades else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        # Calculate daily returns for Sharpe ratio
        daily_returns = self._calculate_daily_returns(trades)
        sharpe_ratio = self._calculate_sharpe_ratio(daily_returns)
        
        # Max drawdown
        cumulative = []
        cum_sum = 0
        for t in sorted(trades, key=lambda x: x['entry_time']):
            cum_sum += t['pnl']
            cumulative.append(cum_sum)
        
        max_drawdown = self._calculate_max_drawdown(cumulative) if cumulative else 0
        
        # VaR (95% confidence)
        if daily_returns:
            daily_var_95 = np.percentile(daily_returns, 5) if len(daily_returns) > 1 else 0
        else:
            daily_var_95 = 0
        
        # Recovery factor
        recovery_factor = (total_pnl / abs(max_drawdown)) if max_drawdown != 0 else 0
        
        return PerformanceMetrics(
            total_pnl=total_pnl,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            profit_factor=profit_factor,
            risk_reward_ratio=risk_reward_ratio,
            daily_var_95=daily_var_95,
            recovery_factor=recovery_factor
        )
    
    def _calculate_daily_returns(self, trades: List[Dict]) -> List[float]:
        """Calculate daily returns from trades"""
        daily_pnl = {}
        
        for trade in trades:
            trade_date = trade['entry_time'].date() if isinstance(trade['entry_time'], datetime) else trade['entry_time']
            if trade_date not in daily_pnl:
                daily_pnl[trade_date] = 0
            daily_pnl[trade_date] += trade['pnl']
        
        return list(daily_pnl.values())
    
    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio"""
        if not returns or len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        excess_returns = returns_array - risk_free_rate
        
        if np.std(excess_returns) == 0:
            return 0.0
        
        # Annualized Sharpe ratio (assuming 252 trading days)
        return (np.mean(excess_returns) / np.std(excess_returns)) * np.sqrt(252)
    
    def _calculate_max_drawdown(self, cumulative: List[float]) -> float:
        """Calculate maximum drawdown percentage"""
        if not cumulative:
            return 0.0
        
        peak = cumulative[0]
        max_dd = 0
        
        for value in cumulative:
            if value > peak:
                peak = value
            
            if peak != 0:
                dd = ((peak - value) / abs(peak)) * 100
                if dd > max_dd:
                    max_dd = dd
        
        return max_dd
    
    def _calculate_daily_pnl(self, trades: List[Dict]) -> List[float]:
        """Calculate daily P&L"""
        daily_pnl = {}
        
        for trade in trades:
            trade_date = trade['entry_time'].date() if isinstance(trade['entry_time'], datetime) else trade['entry_time']
            if trade_date not in daily_pnl:
                daily_pnl[trade_date] = 0
            daily_pnl[trade_date] += trade['pnl']
        
        # Sort by date and return values
        sorted_dates = sorted(daily_pnl.keys())
        return [daily_pnl[d] for d in sorted_dates]
    
    def _calculate_cumulative_pnl(self, daily_pnl: List[float]) -> List[float]:
        """Calculate cumulative P&L"""
        cumulative = []
        total = 0
        
        for pnl in daily_pnl:
            total += pnl
            cumulative.append(total)
        
        return cumulative
    
    def _calculate_signal_performance(self, trades: List[Dict]) -> Dict[str, Any]:
        """Calculate performance by signal type"""
        signals = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']
        performance = {}
        
        for signal in signals:
            signal_trades = [t for t in trades if t.get('signal') == signal]
            
            if signal_trades:
                total_pnl = sum(t['pnl'] for t in signal_trades)
                winners = [t for t in signal_trades if t['pnl'] > 0]
                win_rate = (len(winners) / len(signal_trades) * 100) if signal_trades else 0
                
                performance[signal] = {
                    'trades': len(signal_trades),
                    'pnl': total_pnl,
                    'win_rate': win_rate,
                    'avg_pnl': total_pnl / len(signal_trades) if signal_trades else 0
                }
            else:
                performance[signal] = {
                    'trades': 0,
                    'pnl': 0,
                    'win_rate': 0,
                    'avg_pnl': 0
                }
        
        return performance
    
    def _calculate_hourly_performance(self, trades: List[Dict]) -> Dict[str, Any]:
        """Calculate performance by hour"""
        hours = ['09:15', '10:15', '11:15', '12:15', '13:15', '14:15', '15:15']
        performance = {}
        
        for hour_str in hours:
            hour = int(hour_str.split(':')[0])
            hour_trades = []
            
            for trade in trades:
                if isinstance(trade['entry_time'], datetime):
                    trade_hour = trade['entry_time'].hour
                    if trade_hour == hour:
                        hour_trades.append(trade)
            
            if hour_trades:
                total_pnl = sum(t['pnl'] for t in hour_trades)
                performance[hour_str] = {
                    'trades': len(hour_trades),
                    'pnl': total_pnl,
                    'avg_pnl': total_pnl / len(hour_trades) if hour_trades else 0
                }
            else:
                performance[hour_str] = {
                    'trades': 0,
                    'pnl': 0,
                    'avg_pnl': 0
                }
        
        return performance
    
    def _empty_analytics(self) -> Dict[str, Any]:
        """Return empty analytics structure"""
        return {
            'success': False,
            'metrics': PerformanceMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0).__dict__,
            'trades': [],
            'daily_pnl': [],
            'cumulative_pnl': [],
            'signal_performance': {},
            'hourly_performance': {}
        }

# Singleton instance
_instance = None

def get_performance_analytics_service() -> PerformanceAnalyticsService:
    """Get singleton instance"""
    global _instance
    if _instance is None:
        _instance = PerformanceAnalyticsService()
    return _instance