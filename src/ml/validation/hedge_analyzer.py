"""
Hedge Analyzer - Analyzes different hedge strategies with 5-minute P&L tracking
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pyodbc
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class HedgeAnalyzer:
    """Analyzes hedge performance with minute-by-minute tracking"""
    
    def __init__(self):
        self.conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=(localdb)\\mssqllocaldb;Database=KiteConnectApi;Trusted_Connection=yes;"
        
    def get_connection(self):
        """Get database connection"""
        return pyodbc.connect(self.conn_str)
    
    async def analyze_all_hedges(
        self,
        from_date: datetime,
        to_date: datetime,
        hedge_distances: List[int],
        track_minute_pnl: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Analyze all hedge distances for trades in the period
        with optional 5-minute P&L tracking
        """
        logger.info(f"Analyzing hedges from {from_date} to {to_date}")
        
        all_results = []
        
        with self.get_connection() as conn:
            # Get all trades
            trades = self._get_trades_with_positions(conn, from_date, to_date)
            
            for _, trade in trades.iterrows():
                trade_results = {
                    "trade_id": trade['TradeId'],
                    "signal_type": trade['SignalType'],
                    "entry_time": trade['EntryTime'],
                    "exit_time": trade['ExitTime'],
                    "actual_hedge_distance": abs(trade['HedgeStrike'] - trade['MainStrike']),
                    "hedge_analysis": {}
                }
                
                # Analyze each hedge distance
                for hedge_distance in hedge_distances:
                    hedge_result = await self._analyze_single_hedge(
                        conn,
                        trade,
                        hedge_distance,
                        track_minute_pnl
                    )
                    trade_results["hedge_analysis"][hedge_distance] = hedge_result
                
                # Find optimal hedge for this trade
                trade_results["optimal_hedge"] = self._find_optimal_hedge_for_trade(
                    trade_results["hedge_analysis"]
                )
                
                all_results.append(trade_results)
        
        return all_results
    
    def _get_trades_with_positions(self, conn, from_date: datetime, to_date: datetime) -> pd.DataFrame:
        """Get trades with position details"""
        query = """
        SELECT 
            bt.Id as TradeId,
            bt.SignalType,
            bt.EntryTime,
            bt.ExitTime,
            bt.IndexPriceAtEntry,
            bt.IndexPriceAtExit,
            bt.TotalPnL as ActualPnL,
            bp_main.StrikePrice as MainStrike,
            bp_main.OptionType as OptionType,
            bp_main.EntryPrice as MainEntryPrice,
            bp_main.ExitPrice as MainExitPrice,
            bp_main.Quantity,
            bp_main.ExpiryDate,
            bp_hedge.StrikePrice as HedgeStrike,
            bp_hedge.EntryPrice as HedgeEntryPrice,
            bp_hedge.ExitPrice as HedgeExitPrice
        FROM BacktestTrades bt
        JOIN BacktestPositions bp_main ON bt.Id = bp_main.TradeId 
            AND bp_main.PositionType = 'MAIN'
        LEFT JOIN BacktestPositions bp_hedge ON bt.Id = bp_hedge.TradeId 
            AND bp_hedge.PositionType = 'HEDGE'
        WHERE bt.EntryTime >= ? AND bt.EntryTime <= DATEADD(day, 1, ?)
        ORDER BY bt.EntryTime
        """
        
        return pd.read_sql(query, conn, params=[from_date, to_date])
    
    async def _analyze_single_hedge(
        self,
        conn,
        trade: pd.Series,
        hedge_distance: int,
        track_minute_pnl: bool
    ) -> Dict[str, Any]:
        """Analyze a single hedge distance for a trade"""
        
        # Calculate hedge strike
        main_strike = trade['MainStrike']
        option_type = trade['OptionType']
        
        if option_type == 'PE':
            hedge_strike = main_strike - hedge_distance  # Lower strike for PUT hedge
        else:
            hedge_strike = main_strike + hedge_distance  # Higher strike for CALL hedge
        
        # Get entry and exit prices for hedge
        hedge_prices = self._get_hedge_prices(
            conn,
            hedge_strike,
            option_type,
            trade['EntryTime'],
            trade['ExitTime'],
            trade['ExpiryDate']
        )
        
        if not hedge_prices:
            return {
                "available": False,
                "reason": f"No option data for strike {hedge_strike}"
            }
        
        # Calculate P&L
        # Handle negative quantity for MAIN position (selling is stored as negative)
        quantity = abs(trade['Quantity'])  # Use absolute value for calculations
        
        # Main leg P&L (we sell, so profit when price decreases)
        main_pnl = (trade['MainEntryPrice'] - trade['MainExitPrice']) * quantity
        
        # Hedge leg P&L (we buy, so profit when price increases)
        hedge_pnl = (hedge_prices['exit_price'] - hedge_prices['entry_price']) * quantity
        
        # Net P&L
        net_pnl = main_pnl + hedge_pnl
        
        # Commission (Rs 40 per lot, assuming 75 quantity per lot)
        lots = quantity / 75
        commission = lots * 40 * 2  # Entry and exit
        
        # Slippage estimate (0.1% of entry prices)
        slippage = (trade['MainEntryPrice'] + hedge_prices['entry_price']) * quantity * 0.001
        
        # Final P&L after costs
        final_pnl = net_pnl - commission - slippage
        
        result = {
            "available": True,
            "hedge_strike": hedge_strike,
            "main_entry": float(trade['MainEntryPrice']),
            "main_exit": float(trade['MainExitPrice']),
            "hedge_entry": hedge_prices['entry_price'],
            "hedge_exit": hedge_prices['exit_price'],
            "main_pnl": float(main_pnl),
            "hedge_pnl": float(hedge_pnl),
            "net_pnl": float(net_pnl),
            "commission": float(commission),
            "slippage": float(slippage),
            "final_pnl": float(final_pnl),
            "otm_penalty": self._calculate_otm_penalty(
                hedge_strike,
                trade['IndexPriceAtExit'],
                option_type,
                hedge_pnl
            )
        }
        
        # Track minute-by-minute P&L if requested
        if track_minute_pnl:
            minute_pnl = await self._track_minute_pnl(
                conn,
                trade,
                hedge_strike,
                hedge_prices['entry_price']
            )
            result["minute_pnl"] = minute_pnl
            
            # Find breakeven time
            breakeven_info = self._find_breakeven_time(minute_pnl)
            result["breakeven_minutes"] = breakeven_info["minutes"]
            result["max_profit"] = breakeven_info["max_profit"]
            result["max_drawdown"] = breakeven_info["max_drawdown"]
        
        # Calculate risk metrics
        result["sharpe_ratio"] = self._calculate_sharpe_for_trade(final_pnl, trade['ActualPnL'])
        result["risk_reward_ratio"] = abs(final_pnl / result.get("max_drawdown", 1)) if result.get("max_drawdown", 0) < 0 else 0
        
        return result
    
    def _get_hedge_prices(
        self,
        conn,
        strike: int,
        option_type: str,
        entry_time: datetime,
        exit_time: datetime,
        expiry_date: datetime
    ) -> Optional[Dict[str, float]]:
        """Get entry and exit prices for hedge option"""
        
        # Get entry price (closest to entry time)
        entry_query = """
        SELECT TOP 1 [Close] as Price
        FROM OptionsHistoricalData
        WHERE Strike = ? 
        AND OptionType = ?
        AND ExpiryDate >= ? AND ExpiryDate < DATEADD(day, 1, ?)
        AND Timestamp >= ? AND Timestamp <= DATEADD(minute, 60, ?)
        ORDER BY ABS(DATEDIFF(second, Timestamp, ?))
        """
        
        cursor = conn.cursor()
        
        # Handle expiry date properly
        expiry_start = expiry_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        cursor.execute(entry_query, strike, option_type, expiry_start, expiry_start,
                      entry_time, entry_time, entry_time)
        entry_result = cursor.fetchone()
        
        if not entry_result:
            return None
        
        # Get exit price (closest to exit time)
        exit_query = """
        SELECT TOP 1 [Close] as Price
        FROM OptionsHistoricalData
        WHERE Strike = ? 
        AND OptionType = ?
        AND ExpiryDate >= ? AND ExpiryDate < DATEADD(day, 1, ?)
        AND Timestamp >= DATEADD(minute, -60, ?) AND Timestamp <= ?
        ORDER BY ABS(DATEDIFF(second, Timestamp, ?))
        """
        
        cursor.execute(exit_query, strike, option_type, expiry_start, expiry_start,
                      exit_time, exit_time, exit_time)
        exit_result = cursor.fetchone()
        
        if not exit_result:
            # Try to get any price near expiry
            cursor.execute("""
                SELECT TOP 1 [Close] as Price
                FROM OptionsHistoricalData
                WHERE Strike = ? 
                AND OptionType = ?
                AND ExpiryDate >= ? AND ExpiryDate < DATEADD(day, 1, ?)
                ORDER BY Timestamp DESC
            """, strike, option_type, expiry_start, expiry_start)
            exit_result = cursor.fetchone()
            
            if not exit_result:
                return None
        
        return {
            "entry_price": float(entry_result[0]),
            "exit_price": float(exit_result[0])
        }
    
    async def _track_minute_pnl(
        self,
        conn,
        trade: pd.Series,
        hedge_strike: int,
        hedge_entry_price: float
    ) -> List[Dict[str, Any]]:
        """Track P&L every 5 minutes from entry to exit"""
        
        minute_data = []
        
        # Query for 5-minute prices
        query = """
        SELECT 
            Timestamp,
            Strike,
            [Close] as Price
        FROM OptionsHistoricalData
        WHERE Strike IN (?, ?)
        AND OptionType = ?
        AND Timestamp >= ? AND Timestamp <= ?
        AND DATEPART(minute, Timestamp) % 5 = 0  -- Every 5 minutes
        ORDER BY Timestamp
        """
        
        cursor = conn.cursor()
        cursor.execute(query, trade['MainStrike'], hedge_strike, trade['OptionType'],
                      trade['EntryTime'], trade['ExitTime'])
        
        prices_df = pd.DataFrame(cursor.fetchall(), columns=['Timestamp', 'Strike', 'Price'])
        
        if prices_df.empty:
            return minute_data
        
        # Group by timestamp
        for timestamp in prices_df['Timestamp'].unique():
            ts_prices = prices_df[prices_df['Timestamp'] == timestamp]
            
            main_price = ts_prices[ts_prices['Strike'] == trade['MainStrike']]['Price'].values
            hedge_price = ts_prices[ts_prices['Strike'] == hedge_strike]['Price'].values
            
            if len(main_price) > 0 and len(hedge_price) > 0:
                # Calculate P&L at this moment
                quantity = abs(trade['Quantity'])  # Use absolute value
                main_pnl = (trade['MainEntryPrice'] - main_price[0]) * quantity
                hedge_pnl = (hedge_price[0] - hedge_entry_price) * quantity
                combined_pnl = main_pnl + hedge_pnl
                
                minutes_elapsed = (timestamp - trade['EntryTime']).total_seconds() / 60
                
                minute_data.append({
                    "timestamp": timestamp,
                    "minutes": int(minutes_elapsed),
                    "main_price": float(main_price[0]),
                    "hedge_price": float(hedge_price[0]),
                    "main_pnl": float(main_pnl),
                    "hedge_pnl": float(hedge_pnl),
                    "combined_pnl": float(combined_pnl),
                    "net_pnl": float(combined_pnl - 80)  # Subtract commission
                })
        
        return minute_data
    
    def _calculate_otm_penalty(
        self,
        hedge_strike: int,
        index_price: float,
        option_type: str,
        hedge_pnl: float
    ) -> float:
        """Calculate penalty if OTM hedge became ITM"""
        
        if option_type == 'PE':
            # PUT: ITM if index < strike
            if index_price < hedge_strike:
                # Hedge became ITM
                intrinsic_value = (hedge_strike - index_price) * 75  # 1 lot
                # Penalty is extra loss beyond normal hedge cost
                return min(0, hedge_pnl - intrinsic_value)
        else:
            # CALL: ITM if index > strike
            if index_price > hedge_strike:
                intrinsic_value = (index_price - hedge_strike) * 75
                return min(0, hedge_pnl - intrinsic_value)
        
        return 0
    
    def _find_breakeven_time(self, minute_pnl: List[Dict]) -> Dict[str, Any]:
        """Find when trade first becomes profitable"""
        
        if not minute_pnl:
            return {"minutes": None, "max_profit": 0, "max_drawdown": 0}
        
        breakeven_minutes = None
        max_profit = 0
        max_drawdown = 0
        peak = 0
        
        for data in minute_pnl:
            pnl = data['net_pnl']
            
            # Track breakeven
            if breakeven_minutes is None and pnl > 0:
                breakeven_minutes = data['minutes']
            
            # Track max profit
            if pnl > max_profit:
                max_profit = pnl
                peak = pnl
            
            # Track drawdown from peak
            drawdown = pnl - peak
            if drawdown < max_drawdown:
                max_drawdown = drawdown
        
        return {
            "minutes": breakeven_minutes,
            "max_profit": max_profit,
            "max_drawdown": max_drawdown
        }
    
    def _calculate_sharpe_for_trade(self, actual_pnl: float, expected_pnl: float) -> float:
        """Calculate Sharpe-like metric for single trade"""
        # Simple approach: ratio of actual to expected
        if expected_pnl == 0:
            return 0
        return actual_pnl / abs(expected_pnl)
    
    def _find_optimal_hedge_for_trade(self, hedge_analysis: Dict[int, Dict]) -> Dict[str, Any]:
        """Find optimal hedge distance for a specific trade"""
        
        best_hedge = 200  # Default
        best_score = float('-inf')
        best_metrics = {}
        
        for distance, metrics in hedge_analysis.items():
            if not metrics.get("available", False):
                continue
            
            # Score based on final P&L and risk metrics
            score = metrics.get("final_pnl", 0)
            
            # Penalize high drawdowns
            if metrics.get("max_drawdown", 0) < 0:
                score += metrics["max_drawdown"] * 0.5  # 50% weight on drawdown
            
            # Bonus for quick breakeven
            if metrics.get("breakeven_minutes"):
                score += 1000 / (1 + metrics["breakeven_minutes"])  # Inverse time bonus
            
            # Penalty for OTM issues
            score += metrics.get("otm_penalty", 0)
            
            if score > best_score:
                best_score = score
                best_hedge = distance
                best_metrics = metrics
        
        return {
            "distance": best_hedge,
            "score": best_score,
            "final_pnl": best_metrics.get("final_pnl", 0),
            "breakeven_minutes": best_metrics.get("breakeven_minutes"),
            "max_drawdown": best_metrics.get("max_drawdown", 0)
        }
    
    async def store_hedge_analysis_results(
        self,
        validation_run_id: str,
        hedge_results: List[Dict]
    ):
        """Store hedge analysis results in database"""
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for trade_result in hedge_results:
                trade_id = trade_result['trade_id']
                signal_type = trade_result['signal_type']
                
                for hedge_distance, metrics in trade_result['hedge_analysis'].items():
                    if not metrics.get("available", False):
                        continue
                    
                    # Store hedge analysis
                    cursor.execute("""
                        INSERT INTO MLHedgeAnalysis
                        (ValidationRunId, TradeId, SignalType, HedgeDistance,
                         MainEntryPrice, HedgeEntryPrice, MainExitPrice, HedgeExitPrice,
                         MainPnL, HedgePnL, NetPnL, OTMPenalty, SharpeRatio)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, validation_run_id, trade_id, signal_type, hedge_distance,
                        metrics['main_entry'], metrics['hedge_entry'],
                        metrics['main_exit'], metrics['hedge_exit'],
                        metrics['main_pnl'], metrics['hedge_pnl'],
                        metrics['net_pnl'], metrics.get('otm_penalty', 0),
                        metrics.get('sharpe_ratio', 0))
                    
                    # Store minute P&L data if available
                    if 'minute_pnl' in metrics:
                        for minute_data in metrics['minute_pnl']:
                            cursor.execute("""
                                INSERT INTO MLMinutePnL
                                (ValidationRunId, TradeId, SignalType, Timestamp,
                                 MainLegPrice, HedgeLegPrice, CombinedPnL, NetPnL)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, validation_run_id, trade_id, signal_type,
                                minute_data['timestamp'], minute_data['main_price'],
                                minute_data['hedge_price'], minute_data['combined_pnl'],
                                minute_data['net_pnl'])
            
            conn.commit()
            logger.info(f"Stored hedge analysis for {len(hedge_results)} trades")