"""
Position Stop-Loss Optimizer - Fixed with lower thresholds
"""
import pyodbc
import pandas as pd
from typing import Dict, List, Optional
from datetime import date
import logging

logger = logging.getLogger(__name__)

class PositionStopLossOptimizer:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        
    def get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def optimize_stoploss(self, from_date: date, to_date: date, signal_types: Optional[List[str]] = None) -> Dict:
        """Optimize stop-loss with minimal data"""
        
        query = """
        SELECT 
            SignalType,
            COUNT(*) as TotalTrades,
            AVG(CAST(TotalPnL AS FLOAT)) as AvgPnL,
            MIN(CAST(TotalPnL AS FLOAT)) as MaxLoss,
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
                avg_loss = abs(row['MaxLoss']) if row['MaxLoss'] else 10000
                
                # Simple logic for stop-loss type
                if avg_loss < 20000:
                    stop_type = 'percentage'
                    stop_value = 5
                else:
                    stop_type = 'fixed'
                    stop_value = 30000
                
                recommendations[signal] = {
                    'stop_loss_type': stop_type,
                    'stop_loss_value': stop_value,
                    'win_rate': float(row['WinningTrades'] / row['TotalTrades'] * 100) if row['TotalTrades'] > 0 else 50,
                    'avg_profit': float(row['AvgPnL']),
                    'max_drawdown': float(row['MaxLoss']),
                    'confidence_score': min(row['TotalTrades'] * 10, 100)
                }
            
            return {'recommendations': recommendations}
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return {}
