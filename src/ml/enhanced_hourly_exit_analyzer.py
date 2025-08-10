"""
Enhanced Hourly Exit Analyzer - Day-wise breakdown with theta decay analysis
Uses NiftyIndexDataHourly for trend context and OptionsHistoricalData for P&L
"""
import pyodbc
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class EnhancedHourlyExitAnalyzer:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        
    def get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def get_hourly_market_trend(self, conn, timestamp: datetime) -> str:
        """Determine market trend from hourly data"""
        query = """
        SELECT TOP 3
            [Close], [Open], (High - Low) as Range
        FROM NiftyIndexDataHourly
        WHERE Timestamp <= ?
        ORDER BY Timestamp DESC
        """
        cursor = conn.cursor()
        cursor.execute(query, [timestamp])
        rows = cursor.fetchall()
        
        if len(rows) < 2:
            return "Unknown"
        
        # Check if trending or sideways
        closes = [float(row[0]) for row in rows]
        ranges = [float(row[2]) for row in rows]
        
        # Calculate trend
        if closes[0] > closes[1] > closes[2]:
            return "Trending Up"
        elif closes[0] < closes[1] < closes[2]:
            return "Trending Down"
        elif max(ranges) < 50:  # Small hourly ranges
            return "Sideways"
        else:
            return "Volatile"
    
    def calculate_theta_decay(self, conn, trade_id: str, exit_hour: int) -> Dict:
        """Calculate theta decay contribution to P&L"""
        query = """
        SELECT 
            bp.PositionType,
            bp.StrikePrice,
            bp.OptionType,
            bp.EntryTime,
            bp.EntryPrice,
            bp.Quantity
        FROM BacktestPositions bp
        WHERE bp.TradeId = ?
        """
        
        cursor = conn.cursor()
        cursor.execute(query, [trade_id])
        positions = cursor.fetchall()
        
        if not positions:
            return {'theta_contribution': 0, 'delta_contribution': 0}
        
        theta_total = 0
        delta_total = 0
        
        for pos in positions:
            position_type = pos[0]
            strike = pos[1]
            option_type = pos[2]
            entry_time = pos[3]
            quantity = abs(pos[5])
            
            # Calculate exit time based on hour
            exit_time = entry_time.replace(hour=exit_hour, minute=30)
            if exit_time <= entry_time:
                exit_time = entry_time + timedelta(hours=1)
            
            # Get option Greeks at entry and exit
            greeks_query = """
            SELECT AVG(Theta) as AvgTheta, AVG(Delta) as AvgDelta
            FROM OptionsHistoricalData
            WHERE Strike = ? AND OptionType = ?
              AND Timestamp BETWEEN ? AND ?
            """
            
            cursor.execute(greeks_query, [strike, option_type, entry_time, exit_time])
            greeks = cursor.fetchone()
            
            if greeks and greeks[0]:
                avg_theta = float(greeks[0])
                avg_delta = float(greeks[1]) if greeks[1] else 0
                
                # Time in hours
                time_elapsed = (exit_time - entry_time).total_seconds() / 3600
                
                # Theta contribution (negative for options, but we sold main)
                if position_type == 'MAIN':
                    theta_total += avg_theta * time_elapsed * quantity  # Positive for sold options
                else:  # HEDGE
                    theta_total -= avg_theta * time_elapsed * quantity  # Negative for bought options
        
        return {
            'theta_contribution': theta_total,
            'delta_contribution': delta_total
        }
    
    def get_exit_recommendations(self, from_date: date, to_date: date, 
                                signal_types: Optional[List[str]] = None) -> Dict:
        """
        Analyze optimal exit timing with day-wise breakdown
        """
        query = """
        WITH TradeDetails AS (
            SELECT 
                bt.Id,
                bt.SignalType,
                bt.EntryTime,
                bt.ExitTime,
                bt.TotalPnL,
                bt.ExitReason,
                DATEPART(weekday, bt.EntryTime) as DayOfWeek,
                DATENAME(weekday, bt.EntryTime) as DayName,
                DATEPART(hour, bt.EntryTime) as EntryHour,
                DATEPART(hour, bt.ExitTime) as ExitHour,
                DATEDIFF(minute, bt.EntryTime, bt.ExitTime) as HoldingMinutes
            FROM BacktestTrades bt
            WHERE bt.WeekStartDate BETWEEN ? AND ?
            {signal_filter}
        )
        SELECT 
            SignalType,
            DayOfWeek,
            DayName,
            ExitHour,
            COUNT(*) as TradeCount,
            AVG(CAST(TotalPnL AS FLOAT)) as AvgPnL,
            STDEV(CAST(TotalPnL AS FLOAT)) as StdevPnL,
            MAX(CAST(TotalPnL AS FLOAT)) as MaxPnL,
            MIN(CAST(TotalPnL AS FLOAT)) as MinPnL,
            SUM(CASE WHEN TotalPnL > 0 THEN 1 ELSE 0 END) as WinCount,
            AVG(HoldingMinutes) as AvgHoldingMinutes
        FROM TradeDetails
        GROUP BY SignalType, DayOfWeek, DayName, ExitHour
        ORDER BY SignalType, DayOfWeek, ExitHour
        """
        
        signal_filter = ""
        params = [from_date, to_date]
        if signal_types:
            placeholders = ','.join(['?' for _ in signal_types])
            signal_filter = f"AND bt.SignalType IN ({placeholders})"
            params.extend(signal_types)
        
        query = query.format(signal_filter=signal_filter)
        
        try:
            with self.get_connection() as conn:
                df = pd.read_sql(query, conn, params=params)
                
                if df.empty:
                    return {}
                
                recommendations = {}
                
                for signal in df['SignalType'].unique():
                    signal_data = df[df['SignalType'] == signal]
                    
                    # Analyze by day of week
                    day_analysis = {}
                    overall_best = {'hour': None, 'day': None, 'pnl': -float('inf')}
                    
                    for day in signal_data['DayName'].unique():
                        day_data = signal_data[signal_data['DayName'] == day]
                        
                        if not day_data.empty:
                            # Find best hour for this day
                            hourly_stats = []
                            for hour in range(9, 16):  # 9 AM to 3 PM
                                hour_data = day_data[day_data['ExitHour'] == hour]
                                if not hour_data.empty:
                                    avg_pnl = hour_data['AvgPnL'].iloc[0]
                                    win_rate = (hour_data['WinCount'].iloc[0] / hour_data['TradeCount'].iloc[0] * 100) if hour_data['TradeCount'].iloc[0] > 0 else 0
                                    
                                    hourly_stats.append({
                                        'hour': hour,
                                        'avg_pnl': avg_pnl,
                                        'win_rate': win_rate,
                                        'trade_count': int(hour_data['TradeCount'].iloc[0]),
                                        'risk': float(hour_data['StdevPnL'].iloc[0]) if hour_data['StdevPnL'].iloc[0] else 0
                                    })
                                    
                                    # Track overall best
                                    if avg_pnl > overall_best['pnl']:
                                        overall_best = {
                                            'hour': hour,
                                            'day': day,
                                            'pnl': avg_pnl,
                                            'win_rate': win_rate
                                        }
                            
                            if hourly_stats:
                                # Best hour for this day
                                best_for_day = max(hourly_stats, key=lambda x: x['avg_pnl'])
                                day_analysis[day] = best_for_day
                    
                    # Calculate theta decay impact for different exit times
                    theta_analysis = {}
                    sample_trades = pd.read_sql(
                        "SELECT TOP 5 Id FROM BacktestTrades WHERE SignalType = ? AND WeekStartDate BETWEEN ? AND ?",
                        conn, params=[signal, from_date, to_date]
                    )
                    
                    for trade_id in sample_trades['Id']:
                        for hour in [10, 11, 12, 13, 14, 15]:
                            theta_data = self.calculate_theta_decay(conn, trade_id, hour)
                            if hour not in theta_analysis:
                                theta_analysis[hour] = []
                            theta_analysis[hour].append(theta_data['theta_contribution'])
                    
                    # Average theta contribution by hour
                    theta_by_hour = {}
                    for hour, values in theta_analysis.items():
                        if values:
                            theta_by_hour[hour] = np.mean(values)
                    
                    # Build comprehensive recommendation
                    recommendations[signal] = {
                        'best_exit_hour': f"{overall_best['hour']:02d}:30" if overall_best['hour'] else "15:30",
                        'best_exit_day': overall_best['day'],
                        'expected_profit': overall_best['pnl'],
                        'win_rate': overall_best.get('win_rate', 0),
                        'day_wise_analysis': day_analysis,
                        'theta_contribution_by_hour': theta_by_hour,
                        'recommendation': self._generate_recommendation(signal_data, day_analysis, theta_by_hour)
                    }
                
                return {'recommendations': recommendations}
                
        except Exception as e:
            logger.error(f"Error in hourly exit analysis: {str(e)}")
            return {}
    
    def _generate_recommendation(self, signal_data, day_analysis, theta_by_hour) -> str:
        """Generate textual recommendation based on analysis"""
        
        # Find patterns
        if 'Monday' in day_analysis and 'Thursday' in day_analysis:
            mon_pnl = day_analysis['Monday']['avg_pnl']
            thu_pnl = day_analysis['Thursday']['avg_pnl']
            
            if thu_pnl > mon_pnl * 1.5:
                return "Hold till Thursday expiry for maximum theta decay"
            elif mon_pnl > thu_pnl:
                return f"Exit early on Monday at {day_analysis['Monday']['hour']:02d}:30"
        
        # Check theta impact
        if theta_by_hour:
            max_theta_hour = max(theta_by_hour.items(), key=lambda x: x[1])[0]
            if theta_by_hour[max_theta_hour] > 1000:
                return f"Strong theta decay benefit - hold till {max_theta_hour:02d}:30"
        
        return "Exit based on market conditions and profit target"