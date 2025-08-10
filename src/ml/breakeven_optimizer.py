"""
Breakeven Optimizer - Fixed with lower thresholds
"""
import pyodbc
import pandas as pd
from typing import Dict, List, Optional
from datetime import date
import logging

logger = logging.getLogger(__name__)

class BreakevenOptimizer:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        
    def get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def analyze_breakeven_patterns(self, from_date: date, to_date: date, signal_types: Optional[List[str]] = None) -> Dict:
        """Analyze breakeven patterns with minimal data requirements"""
        
        query = """
        SELECT 
            SignalType,
            COUNT(*) as TotalTrades,
            AVG(CAST(TotalPnL AS FLOAT)) as AvgPnL,
            SUM(CASE WHEN TotalPnL > 0 THEN 1 ELSE 0 END) as WinningTrades,
            SUM(CASE WHEN ExitReason = 'StopLoss' THEN 1 ELSE 0 END) as StopLossHits
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
            
            results = {}
            for _, row in df.iterrows():
                signal = row['SignalType']
                total = row['TotalTrades']
                
                # Simple calculation based on available data
                profit_threshold = 10 if row['WinningTrades'] / total > 0.5 else 15
                time_threshold = 45 if row['StopLossHits'] / total < 0.3 else 60
                success_rate = (row['WinningTrades'] / total * 100) if total > 0 else 50
                
                results[signal] = {
                    'strategy': {
                        'time_threshold': time_threshold,
                        'profit_threshold': profit_threshold,
                        'success_rate': float(success_rate),
                        'confidence_score': min(total * 10, 100)
                    }
                }
            
            return {'recommendations': results}
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return {}
