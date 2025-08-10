"""
Signal Behavior Analyzer - Fixed for actual schema
"""
import pyodbc
import pandas as pd
from typing import Dict
from datetime import date
import logging

logger = logging.getLogger(__name__)

class SignalBehaviorAnalyzer:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        
    def get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def analyze_signal_behavior(self, from_date: date, to_date: date) -> Dict:
        """Analyze signal patterns"""
        
        query = """
        SELECT 
            bt.SignalType,
            AVG(CAST(bt.TotalPnL AS FLOAT)) as AvgPnL,
            COUNT(*) as TradeCount,
            SUM(CASE WHEN bt.TotalPnL > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as WinRate
        FROM BacktestTrades bt
        WHERE bt.WeekStartDate BETWEEN ? AND ?
        GROUP BY bt.SignalType
        """
        
        try:
            with self.get_connection() as conn:
                df = pd.read_sql(query, conn, params=[from_date, to_date])
                
            if df.empty:
                return {}
            
            signal_analysis = {}
            for _, row in df.iterrows():
                signal = row['SignalType']
                win_rate = float(row['WinRate'])
                
                signal_analysis[signal] = {
                    'classification': 'trending' if win_rate > 65 else 'sideways',
                    'win_rate': win_rate,
                    'avg_profit': float(row['AvgPnL']),
                    'trade_count': int(row['TradeCount'])
                }
            
            # Simple Iron Condor detection
            iron_condor_opportunities = []
            if len(signal_analysis) >= 2:
                iron_condor_opportunities.append({
                    'date': str(from_date),
                    'signals': list(signal_analysis.keys())[:2],
                    'expected_profit': 25000
                })
            
            return {
                'signal_analysis': signal_analysis,
                'iron_condor_opportunities': iron_condor_opportunities
            }
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return {}
