"""
Hourly Exit Analyzer - Fixed for actual schema
"""
import pyodbc
import pandas as pd
from typing import Dict, List, Optional
from datetime import date
import logging

logger = logging.getLogger(__name__)

class HourlyExitAnalyzer:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        
    def get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def get_exit_recommendations(self, from_date: date, to_date: date, signal_types: Optional[List[str]] = None) -> Dict:
        """Get exit timing recommendations"""
        
        query = """
        SELECT 
            bt.SignalType,
            DATEPART(hour, bt.ExitTime) as ExitHour,
            AVG(CAST(bt.TotalPnL AS FLOAT)) as AvgPnL,
            COUNT(*) as TradeCount,
            SUM(CASE WHEN bt.TotalPnL > 0 THEN 1 ELSE 0 END) as WinCount
        FROM BacktestTrades bt
        WHERE bt.WeekStartDate BETWEEN ? AND ?
          {signal_filter}
        GROUP BY bt.SignalType, DATEPART(hour, bt.ExitTime)
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
                
                # Find best exit hour
                best_hour_data = signal_data.loc[signal_data['AvgPnL'].idxmax()]
                
                recommendations[signal] = {
                    'best_exit_hour': f"{int(best_hour_data['ExitHour']):02d}:30",
                    'expected_profit': float(best_hour_data['AvgPnL']),
                    'win_rate': float(best_hour_data['WinCount'] / best_hour_data['TradeCount'] * 100),
                    'confidence_score': min(float(best_hour_data['TradeCount']) / 10 * 100, 100)
                }
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error in hourly exit analysis: {str(e)}")
            return {}
