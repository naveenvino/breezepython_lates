"""
Real Hedge Optimizer - Works with actual database structure
Analyzes actual 200-point hedges and extrapolates to other distances
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
        
    def get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def analyze_hedge_performance(self, from_date: date, to_date: date, signal_types: Optional[List[str]] = None) -> Dict:
        """
        Analyze actual hedge performance at 200 points and estimate other levels
        """
        query = """
        WITH HedgeAnalysis AS (
            SELECT 
                bt.SignalType,
                bt.Id as TradeId,
                bt.ExitReason,
                MAX(CASE WHEN bp.PositionType = 'MAIN' THEN bp.StrikePrice END) as MainStrike,
                MAX(CASE WHEN bp.PositionType = 'HEDGE' THEN bp.StrikePrice END) as HedgeStrike,
                MAX(CASE WHEN bp.PositionType = 'MAIN' THEN bp.NetPnL END) as MainPnL,
                MAX(CASE WHEN bp.PositionType = 'HEDGE' THEN bp.NetPnL END) as HedgePnL,
                MAX(CASE WHEN bp.PositionType = 'MAIN' THEN bp.EntryPrice END) as MainEntryPrice,
                MAX(CASE WHEN bp.PositionType = 'HEDGE' THEN bp.EntryPrice END) as HedgeEntryPrice,
                SUM(bp.NetPnL) as TotalPnL
            FROM BacktestTrades bt
            INNER JOIN BacktestPositions bp ON bt.Id = bp.TradeId
            WHERE bt.WeekStartDate BETWEEN ? AND ?
            {signal_filter}
            GROUP BY bt.SignalType, bt.Id, bt.ExitReason
        )
        SELECT 
            SignalType,
            COUNT(*) as TotalTrades,
            AVG(TotalPnL) as AvgTotalPnL,
            AVG(MainPnL) as AvgMainPnL,
            AVG(HedgePnL) as AvgHedgePnL,
            AVG(HedgeEntryPrice) as AvgHedgeCost,
            SUM(CASE WHEN ExitReason = 'StopLoss' THEN 1 ELSE 0 END) as StopLossHits,
            SUM(CASE WHEN TotalPnL > 0 THEN 1 ELSE 0 END) as WinningTrades,
            STDEV(TotalPnL) as PnLStdev,
            MIN(TotalPnL) as MaxLoss,
            MAX(TotalPnL) as MaxProfit
        FROM HedgeAnalysis
        GROUP BY SignalType
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
            
            results = {}
            for _, row in df.iterrows():
                signal = row['SignalType']
                
                # Analyze different hedge levels based on actual 200-point data
                hedge_configs = []
                
                # Test different hedge distances
                for hedge_distance in [100, 150, 200, 250, 300]:
                    if hedge_distance == 200:
                        # Actual data
                        config = {
                            'hedge_offset': hedge_distance,
                            'total_trades': int(row['TotalTrades']),
                            'avg_profit': float(row['AvgTotalPnL']),
                            'stoploss_count': int(row['StopLossHits']),
                            'win_rate': float(row['WinningTrades']) / float(row['TotalTrades']) * 100,
                            'sharpe_ratio': float(row['AvgTotalPnL']) / (float(row['PnLStdev']) + 1) if row['PnLStdev'] else 0,
                            'max_loss': float(row['MaxLoss']),
                            'hedge_cost': float(row['AvgHedgeCost']),
                            'data_type': 'actual'
                        }
                    else:
                        # Estimate based on distance ratio
                        distance_ratio = hedge_distance / 200.0
                        
                        # Closer hedge = higher cost but better protection
                        # Farther hedge = lower cost but less protection
                        hedge_cost_multiplier = 1.0 / distance_ratio  # Inverse relationship
                        protection_multiplier = 1.0 / (distance_ratio ** 0.5)  # Square root for protection
                        
                        estimated_hedge_cost = float(row['AvgHedgeCost']) * hedge_cost_multiplier
                        estimated_hedge_pnl = float(row['AvgHedgePnL']) * hedge_cost_multiplier
                        
                        # Adjust total P&L based on hedge distance
                        estimated_total_pnl = float(row['AvgMainPnL']) + estimated_hedge_pnl
                        
                        # Closer hedges reduce stop-loss hits
                        estimated_sl_hits = max(0, int(row['StopLossHits'] * distance_ratio))
                        
                        config = {
                            'hedge_offset': hedge_distance,
                            'total_trades': int(row['TotalTrades']),
                            'avg_profit': estimated_total_pnl,
                            'stoploss_count': estimated_sl_hits,
                            'win_rate': float(row['WinningTrades']) / float(row['TotalTrades']) * 100,
                            'sharpe_ratio': estimated_total_pnl / (float(row['PnLStdev']) + 1) if row['PnLStdev'] else 0,
                            'max_loss': float(row['MaxLoss']) * protection_multiplier,
                            'hedge_cost': estimated_hedge_cost,
                            'data_type': 'estimated'
                        }
                    
                    hedge_configs.append(config)
                
                # Sort by sharpe ratio
                hedge_configs.sort(key=lambda x: x['sharpe_ratio'], reverse=True)
                results[signal] = hedge_configs[:3]  # Return top 3
            
            return results
            
        except Exception as e:
            logger.error(f"Error in hedge optimization: {str(e)}")
            return {}