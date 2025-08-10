"""
Enhanced Hedge Optimizer - Uses NiftyIndexDataHourly for trend analysis
and OptionsHistoricalData for actual P&L calculations
"""
import pyodbc
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class EnhancedHedgeOptimizer:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.hedge_distances = [100, 150, 200, 250, 300, 350, 400]
        
    def get_connection(self):
        return pyodbc.connect(self.connection_string)
    
    def get_nifty_context(self, conn, timestamp: datetime) -> Dict:
        """Get NIFTY market context from hourly data"""
        query = """
        SELECT TOP 1
            [Open], High, Low, [Close],
            (High - Low) as Range,
            CASE 
                WHEN [Close] > [Open] THEN 'Bullish'
                WHEN [Close] < [Open] THEN 'Bearish'
                ELSE 'Neutral'
            END as Direction
        FROM NiftyIndexDataHourly
        WHERE Timestamp <= ?
        ORDER BY Timestamp DESC
        """
        cursor = conn.cursor()
        cursor.execute(query, [timestamp])
        result = cursor.fetchone()
        
        if result:
            return {
                'open': float(result[0]),
                'high': float(result[1]),
                'low': float(result[2]),
                'close': float(result[3]),
                'range': float(result[4]),
                'volatility': float(result[4]) / float(result[0]) * 100,  # Range as % of open
                'direction': result[5]
            }
        return None
    
    def calculate_hourly_atr(self, conn, timestamp: datetime, periods: int = 14) -> float:
        """Calculate ATR from hourly data for volatility assessment"""
        query = """
        SELECT TOP (?) 
            High, Low, [Close]
        FROM NiftyIndexDataHourly
        WHERE Timestamp <= ?
        ORDER BY Timestamp DESC
        """
        cursor = conn.cursor()
        cursor.execute(query, [periods + 1, timestamp])
        rows = cursor.fetchall()
        
        if len(rows) < periods:
            return None
            
        # Calculate True Range for each period
        true_ranges = []
        for i in range(len(rows) - 1):
            high = float(rows[i][0])
            low = float(rows[i][1])
            prev_close = float(rows[i + 1][2])
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        # Return average true range
        return np.mean(true_ranges) if true_ranges else None
    
    def get_option_prices_5min(self, conn, strike: int, option_type: str, 
                               start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """Get 5-minute option prices for precise P&L calculation"""
        query = """
        SELECT 
            Timestamp,
            [Open], High, Low, [Close],
            Volume, OpenInterest,
            Delta, Gamma, Theta, Vega, ImpliedVolatility
        FROM OptionsHistoricalData
        WHERE Strike = ? 
          AND OptionType = ?
          AND Timestamp BETWEEN ? AND ?
        ORDER BY Timestamp
        """
        
        df = pd.read_sql(query, conn, params=[strike, option_type, start_time, end_time])
        return df
    
    def simulate_hedge_performance(self, conn, trade_data: Dict, hedge_distance: int) -> Dict:
        """Simulate performance with specific hedge distance using actual option prices"""
        
        main_strike = trade_data['MainStrike']
        main_type = trade_data['MainOptionType']
        entry_time = trade_data['EntryTime']
        exit_time = trade_data['ExitTime']
        quantity = abs(trade_data['MainQuantity'])
        
        # Calculate hedge strike
        if main_type == 'PE':
            hedge_strike = main_strike - hedge_distance
        else:  # CE
            hedge_strike = main_strike + hedge_distance
        
        # Get 5-minute prices for both legs
        main_prices = self.get_option_prices_5min(conn, main_strike, main_type, entry_time, exit_time)
        hedge_prices = self.get_option_prices_5min(conn, hedge_strike, main_type, entry_time, exit_time)
        
        if main_prices.empty or hedge_prices.empty:
            return None
        
        # Entry prices - check if data exists
        if len(main_prices) == 0 or len(hedge_prices) == 0:
            return None
            
        main_entry = float(main_prices.iloc[0]['Close'])
        hedge_entry = float(hedge_prices.iloc[0]['Close'])
        
        # Exit prices
        main_exit = float(main_prices.iloc[-1]['Close'])
        hedge_exit = float(hedge_prices.iloc[-1]['Close'])
        
        # Calculate P&L
        main_pnl = (main_entry - main_exit) * quantity  # Selling
        hedge_pnl = (hedge_exit - hedge_entry) * quantity  # Buying
        total_pnl = main_pnl + hedge_pnl - 40  # Commission
        
        # Track maximum adverse excursion (MAE)
        running_pnl = []
        for i in range(len(main_prices)):
            main_current = float(main_prices.iloc[i]['Close'])
            hedge_current = float(hedge_prices.iloc[i]['Close'])
            
            current_main_pnl = (main_entry - main_current) * quantity
            current_hedge_pnl = (hedge_current - hedge_entry) * quantity
            current_total = current_main_pnl + current_hedge_pnl - 40
            running_pnl.append(current_total)
        
        mae = min(running_pnl)  # Maximum adverse excursion
        mfe = max(running_pnl)  # Maximum favorable excursion
        
        # Calculate Greeks impact
        avg_main_theta = main_prices['Theta'].mean() if 'Theta' in main_prices else 0
        avg_hedge_theta = hedge_prices['Theta'].mean() if 'Theta' in hedge_prices else 0
        net_theta = (avg_main_theta - avg_hedge_theta) * quantity  # Net theta benefit
        
        return {
            'hedge_distance': hedge_distance,
            'hedge_cost': hedge_entry,
            'total_pnl': total_pnl,
            'main_pnl': main_pnl,
            'hedge_pnl': hedge_pnl,
            'mae': mae,
            'mfe': mfe,
            'max_drawdown': abs(mae) if mae < 0 else 0,
            'net_theta_benefit': net_theta,
            'hedge_efficiency': abs(hedge_pnl / hedge_entry) * 100 if hedge_entry != 0 else 0
        }
    
    def analyze_hedge_performance(self, from_date: date, to_date: date, 
                                 signal_types: Optional[List[str]] = None) -> Dict:
        """
        Comprehensive hedge analysis with risk metrics
        """
        # Get all trades with positions
        query = """
        SELECT 
            bt.Id as TradeId,
            bt.SignalType,
            bt.EntryTime,
            bt.ExitTime,
            bt.ExitReason,
            bt.IndexPriceAtEntry,
            bt.IndexPriceAtExit,
            MAX(CASE WHEN bp.PositionType = 'MAIN' THEN bp.StrikePrice END) as MainStrike,
            MAX(CASE WHEN bp.PositionType = 'MAIN' THEN bp.OptionType END) as MainOptionType,
            MAX(CASE WHEN bp.PositionType = 'MAIN' THEN bp.Quantity END) as MainQuantity,
            MAX(CASE WHEN bp.PositionType = 'MAIN' THEN bp.EntryPrice END) as ActualMainEntry,
            MAX(CASE WHEN bp.PositionType = 'MAIN' THEN bp.ExitPrice END) as ActualMainExit,
            MAX(CASE WHEN bp.PositionType = 'HEDGE' THEN bp.StrikePrice END) as ActualHedgeStrike,
            bt.TotalPnL as ActualTotalPnL
        FROM BacktestTrades bt
        INNER JOIN BacktestPositions bp ON bt.Id = bp.TradeId
        WHERE bt.WeekStartDate BETWEEN ? AND ?
        {signal_filter}
        GROUP BY bt.Id, bt.SignalType, bt.EntryTime, bt.ExitTime, bt.ExitReason, 
                 bt.IndexPriceAtEntry, bt.IndexPriceAtExit, bt.TotalPnL
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
                
                # Analyze each signal type
                for signal in df['SignalType'].unique():
                    signal_df = df[df['SignalType'] == signal]
                    hedge_analysis = []
                    
                    # Test each hedge distance
                    for hedge_distance in self.hedge_distances:
                        distance_results = []
                        
                        for _, trade in signal_df.iterrows():
                            # Get market context at entry
                            nifty_context = self.get_nifty_context(conn, trade['EntryTime'])
                            hourly_atr = self.calculate_hourly_atr(conn, trade['EntryTime'])
                            
                            # Simulate with this hedge distance
                            result = self.simulate_hedge_performance(conn, trade.to_dict(), hedge_distance)
                            
                            if result:
                                result['volatility_regime'] = 'High' if hourly_atr and hourly_atr > 100 else 'Normal'
                                result['market_direction'] = nifty_context['direction'] if nifty_context else 'Unknown'
                                result['exit_reason'] = trade['ExitReason']
                                distance_results.append(result)
                        
                        if distance_results:
                            # Calculate comprehensive statistics
                            df_results = pd.DataFrame(distance_results)
                            
                            total_trades = len(distance_results)
                            profitable_trades = len(df_results[df_results['total_pnl'] > 0])
                            loss_trades = len(df_results[df_results['total_pnl'] <= 0])
                            
                            # Risk metrics
                            avg_profit = df_results['total_pnl'].mean()
                            avg_loss = df_results[df_results['total_pnl'] <= 0]['total_pnl'].mean() if loss_trades > 0 else 0
                            max_loss = df_results['total_pnl'].min()
                            max_profit = df_results['total_pnl'].max()
                            
                            # Calculate Value at Risk (VaR) - 95th percentile of losses
                            var_95 = df_results['total_pnl'].quantile(0.05)
                            
                            # Expected Shortfall (average loss beyond VaR)
                            losses_beyond_var = df_results[df_results['total_pnl'] <= var_95]['total_pnl']
                            expected_shortfall = losses_beyond_var.mean() if len(losses_beyond_var) > 0 else var_95
                            
                            # Sharpe and Sortino ratios
                            returns_std = df_results['total_pnl'].std()
                            downside_returns = df_results[df_results['total_pnl'] < 0]['total_pnl']
                            downside_std = downside_returns.std() if len(downside_returns) > 0 else 1
                            
                            sharpe_ratio = avg_profit / returns_std if returns_std > 0 else 0
                            sortino_ratio = avg_profit / downside_std if downside_std > 0 else 0
                            
                            # Stop-loss analysis
                            sl_hits = len(df_results[df_results['exit_reason'] == 'StopLoss'])
                            
                            hedge_config = {
                                'hedge_offset': hedge_distance,
                                'total_trades': total_trades,
                                'win_rate': (profitable_trades / total_trades * 100) if total_trades > 0 else 0,
                                'loss_frequency': (loss_trades / total_trades * 100) if total_trades > 0 else 0,
                                'avg_profit': avg_profit,
                                'avg_loss': avg_loss,
                                'max_profit': max_profit,
                                'max_loss': max_loss,
                                'max_drawdown': df_results['max_drawdown'].max(),
                                'avg_hedge_cost': df_results['hedge_cost'].mean(),
                                'stoploss_hits': sl_hits,
                                'stoploss_rate': (sl_hits / total_trades * 100) if total_trades > 0 else 0,
                                'value_at_risk_95': var_95,
                                'expected_shortfall': expected_shortfall,
                                'sharpe_ratio': sharpe_ratio,
                                'sortino_ratio': sortino_ratio,
                                'risk_reward_ratio': abs(avg_profit / avg_loss) if avg_loss != 0 else float('inf'),
                                'hedge_efficiency': df_results['hedge_efficiency'].mean(),
                                'theta_benefit': df_results['net_theta_benefit'].mean()
                            }
                            
                            hedge_analysis.append(hedge_config)
                    
                    # Sort by Sortino ratio (better for options selling)
                    hedge_analysis.sort(key=lambda x: x['sortino_ratio'], reverse=True)
                    
                    # Return top 3 with detailed statistics
                    results[signal] = hedge_analysis[:3]
                
                return results
                
        except Exception as e:
            logger.error(f"Error in enhanced hedge optimization: {str(e)}")
            return {}