"""
Signal Performance Analyzer
Analyzes historical performance of trading signals to identify patterns and optimize strategy
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import json

logger = logging.getLogger(__name__)

@dataclass
class SignalMetrics:
    """Metrics for a single signal type"""
    signal_type: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_profit: float
    avg_loss: float
    profit_factor: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    avg_holding_time_hours: float
    best_time_of_day: str
    best_day_of_week: str
    correlation_with_vix: float
    trending_performance: Dict[str, float]
    sideways_performance: Dict[str, float]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            'signal_type': self.signal_type,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': self.win_rate,
            'avg_profit': self.avg_profit,
            'avg_loss': self.avg_loss,
            'profit_factor': self.profit_factor,
            'max_consecutive_wins': self.max_consecutive_wins,
            'max_consecutive_losses': self.max_consecutive_losses,
            'avg_holding_time_hours': self.avg_holding_time_hours,
            'best_time_of_day': self.best_time_of_day,
            'best_day_of_week': self.best_day_of_week,
            'correlation_with_vix': self.correlation_with_vix,
            'trending_performance': self.trending_performance,
            'sideways_performance': self.sideways_performance
        }

class SignalPerformanceAnalyzer:
    """Analyzes historical performance of trading signals"""
    
    def __init__(self, db_connection_string: str):
        """
        Initialize analyzer with database connection
        
        Args:
            db_connection_string: Database connection string
        """
        self.engine = create_engine(db_connection_string)
        self.signal_types = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']
        
    def analyze_all_signals(self, 
                           from_date: datetime,
                           to_date: datetime) -> Dict[str, SignalMetrics]:
        """
        Analyze performance of all signals in date range
        
        Args:
            from_date: Start date for analysis
            to_date: End date for analysis
            
        Returns:
            Dictionary mapping signal type to its metrics
        """
        results = {}
        
        for signal_type in self.signal_types:
            logger.info(f"Analyzing signal {signal_type}")
            metrics = self.analyze_signal(signal_type, from_date, to_date)
            if metrics:
                results[signal_type] = metrics
                
        return results
    
    def analyze_signal(self,
                      signal_type: str,
                      from_date: datetime,
                      to_date: datetime) -> Optional[SignalMetrics]:
        """
        Analyze performance of a specific signal
        
        Args:
            signal_type: Signal type (S1-S8)
            from_date: Start date
            to_date: End date
            
        Returns:
            SignalMetrics object or None if no trades
        """
        # Get trades for this signal
        trades_df = self._get_signal_trades(signal_type, from_date, to_date)
        
        if trades_df.empty:
            logger.warning(f"No trades found for signal {signal_type}")
            return None
            
        # Convert PnL to float if it's Decimal
        trades_df['PnL'] = trades_df['PnL'].astype(float)
        
        # Calculate basic metrics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['PnL'] > 0])
        losing_trades = len(trades_df[trades_df['PnL'] <= 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # Profit metrics
        profits = trades_df[trades_df['PnL'] > 0]['PnL']
        losses = trades_df[trades_df['PnL'] <= 0]['PnL'].abs()
        
        avg_profit = float(profits.mean()) if len(profits) > 0 else 0
        avg_loss = float(losses.mean()) if len(losses) > 0 else 0
        profit_factor = float(profits.sum() / losses.sum()) if losses.sum() > 0 else float('inf')
        
        # Consecutive wins/losses
        max_consecutive_wins = self._calculate_max_consecutive(trades_df['PnL'] > 0)
        max_consecutive_losses = self._calculate_max_consecutive(trades_df['PnL'] <= 0)
        
        # Holding time analysis
        trades_df['holding_hours'] = (
            pd.to_datetime(trades_df['ExitTime']) - 
            pd.to_datetime(trades_df['EntryTime'])
        ).dt.total_seconds() / 3600
        avg_holding_time = trades_df['holding_hours'].mean()
        
        # Time-based analysis
        trades_df['entry_hour'] = pd.to_datetime(trades_df['EntryTime']).dt.hour
        trades_df['entry_dow'] = pd.to_datetime(trades_df['EntryTime']).dt.dayofweek
        
        best_hour = self._find_best_time(trades_df, 'entry_hour')
        best_dow = self._find_best_day(trades_df, 'entry_dow')
        
        # Market regime analysis
        trending_perf = self._analyze_market_regime(trades_df, 'trending')
        sideways_perf = self._analyze_market_regime(trades_df, 'sideways')
        
        # VIX correlation (simplified - would need VIX data)
        vix_correlation = self._calculate_vix_correlation(trades_df)
        
        return SignalMetrics(
            signal_type=signal_type,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_profit=avg_profit,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
            avg_holding_time_hours=avg_holding_time,
            best_time_of_day=f"{best_hour}:00" if best_hour else "N/A",
            best_day_of_week=self._day_name(best_dow) if best_dow is not None else "N/A",
            correlation_with_vix=vix_correlation,
            trending_performance=trending_perf,
            sideways_performance=sideways_perf
        )
    
    def _get_signal_trades(self, 
                          signal_type: str,
                          from_date: datetime,
                          to_date: datetime) -> pd.DataFrame:
        """Get trades for a specific signal from database"""
        query = """
        SELECT 
            bt.Id,
            bt.SignalType,
            bt.EntryTime,
            bt.ExitTime,
            bt.IndexPriceAtEntry as EntryPrice,
            bt.IndexPriceAtExit as ExitPrice,
            bt.TotalPnL as PnL,
            bt.StopLossPrice as StopLoss,
            bt.Direction,
            DATEPART(hour, bt.EntryTime) as EntryHour,
            DATEPART(weekday, bt.EntryTime) as EntryDayOfWeek
        FROM BacktestTrades bt
        WHERE bt.SignalType = :signal_type
            AND bt.EntryTime >= :from_date
            AND bt.EntryTime <= :to_date
        ORDER BY bt.EntryTime
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(
                text(query),
                {
                    'signal_type': signal_type,
                    'from_date': from_date,
                    'to_date': to_date
                }
            )
            rows = result.fetchall()
            if rows:
                # Get column names from the result
                columns = result.keys()
                df = pd.DataFrame(rows, columns=columns)
            else:
                df = pd.DataFrame()
            
        return df
    
    def _calculate_max_consecutive(self, series: pd.Series) -> int:
        """Calculate maximum consecutive True values in series"""
        if series.empty:
            return 0
            
        groups = (series != series.shift()).cumsum()
        consecutive = series.groupby(groups).sum()
        return int(consecutive.max()) if len(consecutive) > 0 else 0
    
    def _find_best_time(self, df: pd.DataFrame, time_col: str) -> Optional[int]:
        """Find best performing time period"""
        if df.empty:
            return None
            
        time_performance = df.groupby(time_col)['PnL'].agg(['sum', 'count', 'mean'])
        # Weight by both total profit and consistency
        time_performance['score'] = (
            time_performance['sum'] * 0.5 + 
            time_performance['mean'] * 0.3 +
            time_performance['count'] * 0.2
        )
        
        if not time_performance.empty:
            return time_performance['score'].idxmax()
        return None
    
    def _find_best_day(self, df: pd.DataFrame, day_col: str) -> Optional[int]:
        """Find best performing day of week"""
        return self._find_best_time(df, day_col)
    
    def _day_name(self, day_num: int) -> str:
        """Convert day number to name"""
        days = ['Monday', 'Tuesday', 'Wednesday', 'Tuesday', 'Friday', 'Saturday', 'Sunday']
        return days[day_num] if 0 <= day_num < 7 else "Unknown"
    
    def _analyze_market_regime(self, 
                               df: pd.DataFrame,
                               regime: str) -> Dict[str, float]:
        """
        Analyze performance in different market regimes
        Would need additional market data to properly classify regimes
        """
        # Simplified regime detection based on volatility
        # In production, would use proper trend detection
        if regime == 'trending':
            # Assume trending if large price moves
            regime_trades = df[df['PnL'].abs() > df['PnL'].abs().median()]
        else:  # sideways
            regime_trades = df[df['PnL'].abs() <= df['PnL'].abs().median()]
            
        if regime_trades.empty:
            return {'win_rate': 0, 'avg_pnl': 0, 'trade_count': 0}
            
        wins = len(regime_trades[regime_trades['PnL'] > 0])
        total = len(regime_trades)
        
        return {
            'win_rate': wins / total if total > 0 else 0,
            'avg_pnl': regime_trades['PnL'].mean(),
            'trade_count': total
        }
    
    def _calculate_vix_correlation(self, df: pd.DataFrame) -> float:
        """
        Calculate correlation with VIX
        Simplified version - would need actual VIX data
        """
        # Placeholder - in production would fetch VIX data and correlate
        return 0.0
    
    def identify_best_conditions(self, 
                                 metrics: Dict[str, SignalMetrics]) -> Dict[str, Dict]:
        """
        Identify best market conditions for each signal
        
        Args:
            metrics: Dictionary of signal metrics
            
        Returns:
            Dictionary with best conditions per signal
        """
        conditions = {}
        
        for signal_type, signal_metrics in metrics.items():
            # Determine best regime
            trending_score = (
                signal_metrics.trending_performance.get('win_rate', 0) * 
                signal_metrics.trending_performance.get('avg_pnl', 0)
            )
            sideways_score = (
                signal_metrics.sideways_performance.get('win_rate', 0) * 
                signal_metrics.sideways_performance.get('avg_pnl', 0)
            )
            
            conditions[signal_type] = {
                'best_regime': 'trending' if trending_score > sideways_score else 'sideways',
                'best_time': signal_metrics.best_time_of_day,
                'best_day': signal_metrics.best_day_of_week,
                'win_rate': signal_metrics.win_rate,
                'profit_factor': signal_metrics.profit_factor,
                'avg_holding_hours': signal_metrics.avg_holding_time_hours,
                'recommendation': self._generate_recommendation(signal_metrics)
            }
            
        return conditions
    
    def _generate_recommendation(self, metrics: SignalMetrics) -> str:
        """Generate clear, actionable trading recommendations based on metrics"""
        recommendations = []
        
        # Priority ranking based on performance
        total_profit = metrics.avg_profit * metrics.total_trades
        
        # Win rate based recommendations
        if metrics.win_rate >= 0.9:
            recommendations.append(f"STRONG BUY: {metrics.win_rate:.1%} win rate - Trade with full 10 lots")
        elif metrics.win_rate >= 0.7:
            recommendations.append(f"BUY: {metrics.win_rate:.1%} win rate - Trade with 7-8 lots")
        elif metrics.win_rate >= 0.5:
            recommendations.append(f"NEUTRAL: {metrics.win_rate:.1%} win rate - Trade with 5 lots max")
        else:
            recommendations.append(f"AVOID: {metrics.win_rate:.1%} win rate - Skip or paper trade only")
            
        # Profit analysis
        if metrics.avg_profit > 30000:
            recommendations.append(f"High profit signal: Avg Rs.{metrics.avg_profit:,.0f} per trade")
        elif metrics.avg_profit > 20000:
            recommendations.append(f"Good profit signal: Avg Rs.{metrics.avg_profit:,.0f} per trade")
        elif metrics.avg_profit > 10000:
            recommendations.append(f"Moderate profit: Avg Rs.{metrics.avg_profit:,.0f} per trade")
        else:
            recommendations.append(f"Low profit: Only Rs.{metrics.avg_profit:,.0f} per trade")
            
        # Trading frequency
        if metrics.total_trades < 3:
            recommendations.append(f"RARE: Only {metrics.total_trades} trades - May need to wait weeks")
        elif metrics.total_trades < 10:
            recommendations.append(f"OCCASIONAL: {metrics.total_trades} trades - Expect 1-2 per month")
        else:
            recommendations.append(f"FREQUENT: {metrics.total_trades} trades - Multiple opportunities monthly")
            
        # Specific timing advice (if best time exists)
        if metrics.best_time_of_day and metrics.best_time_of_day != "N/A":
            hour = metrics.best_time_of_day.split(':')[0]
            if hour == "11":
                recommendations.append("Entry timing: Best at 11:00 AM (second candle after 9:15 open)")
            elif hour == "10":
                recommendations.append("Entry timing: Best at 10:15 AM (first signal candle)")
            elif hour == "14":
                recommendations.append("Entry timing: Best at 2:15 PM (afternoon session)")
            elif hour == "15":
                recommendations.append("Entry timing: Best at 3:15 PM (near expiry)")
            else:
                recommendations.append(f"Entry timing: Best at {metrics.best_time_of_day}")
                
        # Day of week preference
        if metrics.best_day_of_week and metrics.best_day_of_week != "N/A":
            if metrics.best_day_of_week == "Tuesday":
                recommendations.append("EXPIRY DAY: Best on Tuesday - Consider closing before 3:15 PM")
            elif metrics.best_day_of_week == "Monday":
                recommendations.append("WEEK START: Best on Monday - Fresh weekly levels")
            else:
                recommendations.append(f"Best day: {metrics.best_day_of_week}")
                
        # Market regime preference
        if metrics.trending_performance.get('win_rate', 0) > metrics.sideways_performance.get('win_rate', 0):
            recommendations.append("TREND FOLLOWER: Works better in trending markets")
        elif metrics.sideways_performance.get('win_rate', 0) > metrics.trending_performance.get('win_rate', 0):
            recommendations.append("RANGE TRADER: Works better in sideways/choppy markets")
            
        # Risk warnings
        if metrics.max_consecutive_losses > 3:
            recommendations.append(f"RISK WARNING: Had {metrics.max_consecutive_losses} losses in a row before")
            
        # Overall verdict
        if metrics.win_rate >= 0.8 and metrics.avg_profit > 20000:
            recommendations.append("VERDICT: HIGHLY RECOMMENDED - Top performing signal")
        elif metrics.win_rate >= 0.6 and metrics.avg_profit > 15000:
            recommendations.append("VERDICT: RECOMMENDED - Good risk-reward signal")
        elif metrics.win_rate < 0.5 or metrics.avg_profit < 10000:
            recommendations.append("VERDICT: NOT RECOMMENDED - Poor performance")
        else:
            recommendations.append("VERDICT: USE WITH CAUTION - Average performance")
            
        return " | ".join(recommendations) if recommendations else "Insufficient data for recommendations"
    
    def save_analysis_results(self, 
                             metrics: Dict[str, SignalMetrics],
                             output_path: str = None):
        """
        Save analysis results to database or file
        
        Args:
            metrics: Signal metrics dictionary
            output_path: Optional file path for JSON output
        """
        # Try to save to database if table exists
        try:
            with self.engine.begin() as conn:
                # Check if table exists
                check_query = """
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'SignalPerformance'
                """
                result = conn.execute(text(check_query)).fetchone()
                
                if result:
                    for signal_type, signal_metrics in metrics.items():
                        query = """
                        INSERT INTO SignalPerformance (
                            SignalType, Date, WinRate, AvgProfit, AvgLoss,
                            ProfitFactor, TotalTrades, BestTimeOfDay, BestDayOfWeek,
                            MarketRegime, MetricsJson, CreatedAt
                        ) VALUES (
                            :signal_type, :date, :win_rate, :avg_profit, :avg_loss,
                            :profit_factor, :total_trades, :best_time, :best_day,
                            :market_regime, :metrics_json, GETDATE()
                        )
                        """
                        
                        # Determine primary market regime
                        trending_score = signal_metrics.trending_performance.get('win_rate', 0)
                        sideways_score = signal_metrics.sideways_performance.get('win_rate', 0)
                        market_regime = 'trending' if trending_score > sideways_score else 'sideways'
                        
                        conn.execute(text(query), {
                            'signal_type': signal_type,
                            'date': datetime.now().date(),
                            'win_rate': signal_metrics.win_rate * 100,
                            'avg_profit': signal_metrics.avg_profit,
                            'avg_loss': signal_metrics.avg_loss,
                            'profit_factor': signal_metrics.profit_factor,
                            'total_trades': signal_metrics.total_trades,
                            'best_time': signal_metrics.best_time_of_day,
                            'best_day': signal_metrics.best_day_of_week,
                            'market_regime': market_regime,
                            'metrics_json': json.dumps(signal_metrics.to_dict())
                        })
        except Exception as e:
            logger.warning(f"Could not save to database: {e}")
                
        # Optionally save to file
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(
                    {k: v.to_dict() for k, v in metrics.items()},
                    f,
                    indent=2,
                    default=str
                )
                
        logger.info(f"Analysis results saved for {len(metrics)} signals")