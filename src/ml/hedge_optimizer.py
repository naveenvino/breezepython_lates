"""
Hedge Level Optimizer
Analyzes historical trades to recommend optimal hedge configurations
Since HedgeOffset doesn't exist, we'll analyze based on P&L patterns
"""
import pyodbc
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import date
import logging

logger = logging.getLogger(__name__)

class HedgeOptimizer:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.hedge_levels = [100, 150, 200, 250, 300, 350, 400, 450, 500]
        
    def get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def analyze_hedge_performance(self, from_date: date, to_date: date, signal_types: Optional[List[str]] = None) -> Dict:
        """
        Analyze performance patterns for different theoretical hedge levels
        Since we don't have HedgeOffset, we'll simulate based on P&L distributions
        """
        query = """
        SELECT 
            bt.SignalType,
            COUNT(*) as TotalTrades,
            AVG(CAST(bt.TotalPnL AS FLOAT)) as AvgPnL,
            STDEV(CAST(bt.TotalPnL AS FLOAT)) as PnLStdev,
            MAX(CAST(bt.TotalPnL AS FLOAT)) as MaxProfit,
            MIN(CAST(bt.TotalPnL AS FLOAT)) as MaxLoss,
            SUM(CASE WHEN bt.ExitReason = 'StopLoss' THEN 1 ELSE 0 END) as StopLossCount,
            SUM(CASE WHEN bt.TotalPnL > 0 THEN 1 ELSE 0 END) as WinningTrades
        FROM BacktestTrades bt
        WHERE bt.WeekStartDate BETWEEN ? AND ?
          {signal_filter}
        GROUP BY bt.SignalType
        HAVING COUNT(*) >= 1
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
                logger.warning("No data found for hedge optimization")
                return {}
            
            results = {}
            for _, row in df.iterrows():
                signal = row['SignalType']
                
                # Simulate different hedge levels based on P&L distribution
                hedge_configs = []
                for hedge_offset in self.hedge_levels:
                    # Estimate impact of different hedge levels
                    # Closer hedge = more protection but higher cost
                    hedge_cost_factor = 1 - (hedge_offset / 1000)  # Closer hedge costs more
                    protection_factor = 1 - (hedge_offset / 500)   # Closer hedge protects more
                    
                    # Adjust metrics based on hedge level
                    adjusted_pnl = float(row['AvgPnL']) * (1 - hedge_cost_factor * 0.1)
                    adjusted_loss = float(row['MaxLoss']) * protection_factor
                    stop_loss_reduction = row['StopLossCount'] * protection_factor
                    
                    # Calculate risk-adjusted metrics
                    sharpe = adjusted_pnl / (float(row['PnLStdev']) + 1) if row['PnLStdev'] else 0
                    win_rate = (float(row['WinningTrades']) / float(row['TotalTrades']) * 100) if row['TotalTrades'] > 0 else 0
                    
                    config = {
                        'hedge_offset': hedge_offset,
                        'total_trades': int(row['TotalTrades']),
                        'avg_profit': adjusted_pnl,
                        'stop_loss_rate': max(0, (stop_loss_reduction / row['TotalTrades'] * 100)) if row['TotalTrades'] > 0 else 0,
                        'sharpe_ratio': sharpe,
                        'max_loss': adjusted_loss,
                        'win_rate': win_rate,
                        'risk_reward_ratio': abs(float(row['MaxProfit']) / adjusted_loss) if adjusted_loss != 0 else 0
                    }
                    hedge_configs.append(config)
                
                # Sort by Sharpe ratio and return top 3
                hedge_configs.sort(key=lambda x: x['sharpe_ratio'], reverse=True)
                results[signal] = hedge_configs[:3]
            
            return results
            
        except Exception as e:
            logger.error(f"Error in hedge optimization: {str(e)}")
            return {}
