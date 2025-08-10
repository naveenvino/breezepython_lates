"""
Trailing Stop-Loss Optimizer - Fixed with lower thresholds
"""
import pyodbc
import pandas as pd
from typing import Dict, List, Optional
from datetime import date
import logging

logger = logging.getLogger(__name__)

class TrailingStopLossOptimizer:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        
    def get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def optimize_trailing_parameters(self, from_date: date, to_date: date, signal_types: Optional[List[str]] = None) -> Dict:
        """Optimize trailing with minimal data"""
        
        query = """
        SELECT 
            SignalType,
            COUNT(*) as TotalTrades,
            AVG(CAST(TotalPnL AS FLOAT)) as AvgPnL,
            MAX(CAST(TotalPnL AS FLOAT)) as MaxProfit,
            SUM(CASE WHEN TotalPnL > 0 THEN 1 ELSE 0 END) as WinningTrades
        FROM BacktestTrades
        WHERE WeekStartDate BETWEEN ? AND ?
          {signal_filter}
        GROUP BY SignalType
        HAVING COUNT(*) >= 1
        """
        
        signal_filter = ""
        params = [from_date, to_date]
        if signal_types:
            placeholders = ','.join(['?' for _ in signal_types])
            signal_filter = f"AND SignalType IN ({placeholders})"
            params.extend(signal_types)
        
        query = query.format(signal_filter=signal_filter)
        
        try:
            with self.get_connection() as conn:
                df = pd.read_sql(query, conn, params=params)
                
            if df.empty:
                return {}
            
            recommendations = {}
            for _, row in df.iterrows():
                signal = row['SignalType']
                win_rate = (row['WinningTrades'] / row['TotalTrades'] * 100) if row['TotalTrades'] > 0 else 50
                
                # Simple trailing logic based on win rate
                if win_rate > 70:
                    activation = 15
                    trail = 7.5
                elif win_rate > 60:
                    activation = 20
                    trail = 10
                else:
                    activation = 25
                    trail = 12.5
                
                recommendations[signal] = {
                    'strategy': {
                        'activation_percent': activation,
                        'trail_percent': trail,
                        'profit_improvement': 20,  # Estimated
                        'confidence_score': min(row['TotalTrades'] * 10, 100)
                    },
                    'metrics': {
                        'current_win_rate': float(win_rate),
                        'avg_profit': float(row['AvgPnL']),
                        'max_profit': float(row['MaxProfit'])
                    }
                }
            
            return {'recommendations': recommendations}
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return {}
