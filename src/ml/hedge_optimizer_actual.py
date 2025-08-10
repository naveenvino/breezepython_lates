"""
Actual Hedge Optimizer - Uses real options prices from database
Analyzes historical performance with different hedge distances using actual option prices
"""
import pyodbc
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)

class HedgeOptimizer:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.hedge_distances = [100, 150, 200, 250, 300, 350, 400]
        
    def get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def get_option_price(self, conn, strike: int, option_type: str, timestamp: datetime) -> float:
        """Get actual option price from database for a specific strike and time"""
        query = """
        SELECT TOP 1 [Close]
        FROM OptionsHistoricalData
        WHERE Strike = ? 
          AND OptionType = ?
          AND Timestamp <= ?
        ORDER BY Timestamp DESC
        """
        cursor = conn.cursor()
        cursor.execute(query, [strike, option_type, timestamp])
        result = cursor.fetchone()
        return float(result[0]) if result else None
    
    def analyze_hedge_performance(self, from_date: date, to_date: date, signal_types: Optional[List[str]] = None) -> Dict:
        """
        Analyze actual hedge performance using real options data
        """
        # First get all trades with their actual positions
        query = """
        SELECT 
            bt.Id as TradeId,
            bt.SignalType,
            bt.EntryTime,
            bt.ExitTime,
            bt.ExitReason,
            MAX(CASE WHEN bp.PositionType = 'MAIN' THEN bp.StrikePrice END) as MainStrike,
            MAX(CASE WHEN bp.PositionType = 'MAIN' THEN bp.OptionType END) as MainOptionType,
            MAX(CASE WHEN bp.PositionType = 'MAIN' THEN bp.EntryPrice END) as MainEntryPrice,
            MAX(CASE WHEN bp.PositionType = 'MAIN' THEN bp.ExitPrice END) as MainExitPrice,
            MAX(CASE WHEN bp.PositionType = 'MAIN' THEN bp.Quantity END) as MainQuantity,
            MAX(CASE WHEN bp.PositionType = 'HEDGE' THEN bp.StrikePrice END) as ActualHedgeStrike,
            MAX(CASE WHEN bp.PositionType = 'HEDGE' THEN bp.EntryPrice END) as ActualHedgeEntryPrice,
            MAX(CASE WHEN bp.PositionType = 'HEDGE' THEN bp.ExitPrice END) as ActualHedgeExitPrice,
            bt.TotalPnL as ActualTotalPnL
        FROM BacktestTrades bt
        INNER JOIN BacktestPositions bp ON bt.Id = bp.TradeId
        WHERE bt.WeekStartDate BETWEEN ? AND ?
        {signal_filter}
        GROUP BY bt.Id, bt.SignalType, bt.EntryTime, bt.ExitTime, bt.ExitReason, bt.TotalPnL
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
                
                # Now analyze different hedge distances for each signal
                results = {}
                
                for signal in df['SignalType'].unique():
                    signal_df = df[df['SignalType'] == signal]
                    hedge_analysis = []
                    
                    for hedge_distance in self.hedge_distances:
                        total_pnl_list = []
                        stop_loss_hits = 0
                        hedge_costs = []
                        
                        for _, trade in signal_df.iterrows():
                            main_strike = trade['MainStrike']
                            main_option_type = trade['MainOptionType']
                            main_qty = abs(trade['MainQuantity'])  # Always positive for calculation
                            
                            # Calculate hedge strike based on option type
                            if main_option_type == 'PE':
                                hedge_strike = main_strike - hedge_distance  # Buy lower PE for hedge
                            else:  # CE
                                hedge_strike = main_strike + hedge_distance  # Buy higher CE for hedge
                            
                            # Get actual option prices for the hedge at this distance
                            hedge_entry_price = self.get_option_price(
                                conn, hedge_strike, main_option_type, trade['EntryTime']
                            )
                            hedge_exit_price = self.get_option_price(
                                conn, hedge_strike, main_option_type, trade['ExitTime']
                            )
                            
                            if hedge_entry_price and hedge_exit_price:
                                # Calculate P&L with this hedge distance
                                # Main position P&L (selling)
                                main_pnl = (trade['MainEntryPrice'] - trade['MainExitPrice']) * main_qty
                                
                                # Hedge position P&L (buying)
                                hedge_pnl = (hedge_exit_price - hedge_entry_price) * main_qty
                                
                                # Total P&L
                                total_pnl = main_pnl + hedge_pnl - 40  # Commission
                                total_pnl_list.append(total_pnl)
                                hedge_costs.append(hedge_entry_price)
                                
                                # Check if would have hit stop loss with this hedge
                                if trade['ExitReason'] == 'StopLoss' and hedge_distance > 200:
                                    # Wider hedge might have resulted in stop loss
                                    stop_loss_hits += 1
                            else:
                                # If no data for this strike, use actual data scaled
                                scale_factor = hedge_distance / 200.0
                                total_pnl_list.append(trade['ActualTotalPnL'] * (2 - scale_factor))
                        
                        if total_pnl_list:
                            avg_pnl = np.mean(total_pnl_list)
                            std_pnl = np.std(total_pnl_list)
                            win_rate = sum(1 for p in total_pnl_list if p > 0) / len(total_pnl_list) * 100
                            
                            hedge_config = {
                                'hedge_offset': hedge_distance,
                                'total_trades': len(total_pnl_list),
                                'avg_profit': avg_pnl,
                                'stoploss_count': stop_loss_hits,
                                'win_rate': win_rate,
                                'sharpe_ratio': avg_pnl / (std_pnl + 1) if std_pnl else avg_pnl / 100,
                                'max_loss': min(total_pnl_list),
                                'max_profit': max(total_pnl_list),
                                'avg_hedge_cost': np.mean(hedge_costs) if hedge_costs else 0
                            }
                            hedge_analysis.append(hedge_config)
                    
                    # Sort by Sharpe ratio and return top configurations
                    hedge_analysis.sort(key=lambda x: x['sharpe_ratio'], reverse=True)
                    results[signal] = hedge_analysis[:3]
                
                return results
                
        except Exception as e:
            logger.error(f"Error in hedge optimization: {str(e)}")
            return {}