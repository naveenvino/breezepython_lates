"""
Breakeven Optimizer - Finds optimal exit strategies based on profit and time thresholds
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pyodbc
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class BreakevenOptimizer:
    """Optimizes breakeven and exit strategies"""
    
    def __init__(self):
        self.conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=(localdb)\\mssqllocaldb;Database=KiteConnectApi;Trusted_Connection=yes;"
        
    def get_connection(self):
        """Get database connection"""
        return pyodbc.connect(self.conn_str)
    
    async def optimize_strategies(
        self,
        from_date: datetime,
        to_date: datetime,
        strategy_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Optimize breakeven strategies for all trades
        Tests different profit and time thresholds
        """
        logger.info(f"Optimizing breakeven strategies from {from_date} to {to_date}")
        
        results = {
            "strategies_tested": [],
            "optimal_strategy": None,
            "trade_analysis": []
        }
        
        with self.get_connection() as conn:
            # Get all trades with minute data
            trades = self._get_trades_with_minute_data(conn, from_date, to_date)
            
            if trades.empty:
                logger.warning("No trades found for breakeven optimization")
                return results
            
            # Test different strategies
            profit_thresholds = strategy_config.get("profit_thresholds", [10, 15, 20, 25, 30])
            time_thresholds = strategy_config.get("time_thresholds", [60, 120, 240, 480])
            
            strategy_results = []
            
            for profit_threshold in profit_thresholds:
                for time_threshold in time_thresholds:
                    strategy_performance = await self._test_strategy(
                        conn,
                        trades,
                        profit_threshold,
                        time_threshold,
                        strategy_config.get("dynamic", True),
                        strategy_config.get("trailing_stop", False)
                    )
                    
                    strategy_results.append({
                        "profit_threshold": profit_threshold,
                        "time_threshold": time_threshold,
                        "performance": strategy_performance
                    })
                    
                    results["strategies_tested"].append(strategy_performance)
            
            # Find optimal strategy
            results["optimal_strategy"] = self._find_optimal_strategy(strategy_results)
            
            # Analyze individual trades with optimal strategy
            if results["optimal_strategy"]:
                results["trade_analysis"] = await self._analyze_trades_with_strategy(
                    conn,
                    trades,
                    results["optimal_strategy"]["profit_threshold"],
                    results["optimal_strategy"]["time_threshold"]
                )
        
        return results
    
    def _get_trades_with_minute_data(self, conn, from_date: datetime, to_date: datetime) -> pd.DataFrame:
        """Get trades with associated minute-by-minute data"""
        query = """
        SELECT 
            bt.Id as TradeId,
            bt.SignalType,
            bt.EntryTime,
            bt.ExitTime,
            bt.TotalPnL as ActualPnL,
            bt.IndexPriceAtEntry,
            bt.IndexPriceAtExit,
            bp_main.StrikePrice as MainStrike,
            bp_main.OptionType,
            bp_main.EntryPrice as MainEntryPrice,
            bp_main.ExitPrice as MainExitPrice,
            bp_main.Quantity,
            bp_hedge.StrikePrice as HedgeStrike,
            bp_hedge.EntryPrice as HedgeEntryPrice,
            bp_hedge.ExitPrice as HedgeExitPrice
        FROM BacktestTrades bt
        JOIN BacktestPositions bp_main ON bt.Id = bp_main.TradeId 
            AND bp_main.PositionType = 'MAIN'
        LEFT JOIN BacktestPositions bp_hedge ON bt.Id = bp_hedge.TradeId 
            AND bp_hedge.PositionType = 'HEDGE'
        WHERE bt.EntryTime >= ? AND bt.ExitTime <= ?
        ORDER BY bt.EntryTime
        """
        
        return pd.read_sql(query, conn, params=[from_date, to_date])
    
    async def _test_strategy(
        self,
        conn,
        trades: pd.DataFrame,
        profit_threshold: float,
        time_threshold: int,
        dynamic: bool,
        trailing_stop: bool
    ) -> Dict[str, Any]:
        """Test a specific breakeven strategy"""
        
        total_trades = len(trades)
        successful_exits = 0
        total_pnl = 0
        stopped_out = 0
        time_exits = 0
        profit_exits = 0
        max_adverse_excursion = []
        
        for _, trade in trades.iterrows():
            # Get minute-by-minute P&L for this trade
            minute_pnl = self._get_minute_pnl_for_trade(
                conn,
                trade['TradeId'],
                trade['EntryTime'],
                trade['ExitTime']
            )
            
            if minute_pnl.empty:
                continue
            
            # Apply strategy
            exit_result = self._apply_strategy(
                minute_pnl,
                profit_threshold,
                time_threshold,
                dynamic,
                trailing_stop,
                trade['MainStrike']
            )
            
            if exit_result['exit_triggered']:
                successful_exits += 1
                total_pnl += exit_result['exit_pnl']
                
                if exit_result['exit_reason'] == 'profit_threshold':
                    profit_exits += 1
                elif exit_result['exit_reason'] == 'time_threshold':
                    time_exits += 1
                elif exit_result['exit_reason'] == 'stop_loss':
                    stopped_out += 1
                
                # Track MAE (Maximum Adverse Excursion)
                max_adverse_excursion.append(exit_result['mae'])
            else:
                # Use actual exit P&L
                total_pnl += trade['ActualPnL']
        
        # Calculate metrics
        avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
        success_rate = (successful_exits / total_trades * 100) if total_trades > 0 else 0
        avg_mae = np.mean(max_adverse_excursion) if max_adverse_excursion else 0
        
        return {
            "strategy": f"{profit_threshold}% profit + {time_threshold} min",
            "total_trades": total_trades,
            "successful_exits": successful_exits,
            "success_rate": success_rate,
            "profit_exits": profit_exits,
            "time_exits": time_exits,
            "stopped_out": stopped_out,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "avg_mae": avg_mae,
            "sharpe_ratio": self._calculate_strategy_sharpe(minute_pnl, total_pnl)
        }
    
    def _get_minute_pnl_for_trade(
        self,
        conn,
        trade_id: str,
        entry_time: datetime,
        exit_time: datetime
    ) -> pd.DataFrame:
        """Get minute-by-minute P&L for a specific trade"""
        
        # First check if we have stored minute P&L data
        query = """
        SELECT 
            Timestamp,
            NetPnL,
            MainLegPrice,
            HedgeLegPrice
        FROM MLMinutePnL
        WHERE TradeId = ?
        ORDER BY Timestamp
        """
        
        df = pd.read_sql(query, conn, params=[trade_id])
        
        if not df.empty:
            return df
        
        # If not, get from options data
        query = """
        SELECT 
            oh.Timestamp,
            oh.Strike,
            oh.[Close] as Price
        FROM OptionsHistoricalData oh
        WHERE oh.Timestamp >= ? AND oh.Timestamp <= ?
        AND DATEPART(minute, oh.Timestamp) % 5 = 0
        ORDER BY oh.Timestamp
        """
        
        return pd.read_sql(query, conn, params=[entry_time, exit_time])
    
    def _apply_strategy(
        self,
        minute_pnl: pd.DataFrame,
        profit_threshold: float,
        time_threshold: int,
        dynamic: bool,
        trailing_stop: bool,
        stop_loss_level: float
    ) -> Dict[str, Any]:
        """Apply breakeven strategy to minute data"""
        
        if minute_pnl.empty:
            return {
                "exit_triggered": False,
                "exit_pnl": 0,
                "mae": 0
            }
        
        peak_pnl = 0
        min_pnl = 0
        trailing_stop_level = 0
        
        for idx, row in minute_pnl.iterrows():
            current_pnl = row.get('NetPnL', 0)
            minutes_elapsed = idx * 5  # Assuming 5-minute intervals
            
            # Track peak and minimum
            if current_pnl > peak_pnl:
                peak_pnl = current_pnl
                if trailing_stop:
                    # Set trailing stop at 50% of peak profit
                    trailing_stop_level = peak_pnl * 0.5
            
            if current_pnl < min_pnl:
                min_pnl = current_pnl
            
            # Check profit threshold
            if current_pnl >= profit_threshold:
                if dynamic and minutes_elapsed >= time_threshold:
                    # Both conditions met
                    return {
                        "exit_triggered": True,
                        "exit_pnl": current_pnl,
                        "exit_minute": minutes_elapsed,
                        "exit_reason": "profit_threshold",
                        "mae": min_pnl
                    }
                elif not dynamic:
                    # Just profit threshold
                    return {
                        "exit_triggered": True,
                        "exit_pnl": current_pnl,
                        "exit_minute": minutes_elapsed,
                        "exit_reason": "profit_threshold",
                        "mae": min_pnl
                    }
            
            # Check time threshold
            if minutes_elapsed >= time_threshold and current_pnl > 0:
                return {
                    "exit_triggered": True,
                    "exit_pnl": current_pnl,
                    "exit_minute": minutes_elapsed,
                    "exit_reason": "time_threshold",
                    "mae": min_pnl
                }
            
            # Check trailing stop
            if trailing_stop and trailing_stop_level > 0:
                if current_pnl <= trailing_stop_level:
                    return {
                        "exit_triggered": True,
                        "exit_pnl": current_pnl,
                        "exit_minute": minutes_elapsed,
                        "exit_reason": "trailing_stop",
                        "mae": min_pnl
                    }
            
            # Check stop loss
            if current_pnl <= -stop_loss_level:
                return {
                    "exit_triggered": True,
                    "exit_pnl": current_pnl,
                    "exit_minute": minutes_elapsed,
                    "exit_reason": "stop_loss",
                    "mae": min_pnl
                }
        
        # No exit triggered
        return {
            "exit_triggered": False,
            "exit_pnl": minute_pnl.iloc[-1].get('NetPnL', 0),
            "mae": min_pnl
        }
    
    def _find_optimal_strategy(self, strategy_results: List[Dict]) -> Dict[str, Any]:
        """Find the optimal strategy based on multiple criteria"""
        
        if not strategy_results:
            return None
        
        best_score = -float('inf')
        best_strategy = None
        
        for strategy in strategy_results:
            perf = strategy['performance']
            
            # Calculate composite score
            # Weight: 40% avg P&L, 30% success rate, 20% Sharpe, 10% low MAE
            score = 0
            
            # Normalize avg P&L (assume max 50000)
            score += (perf['avg_pnl'] / 50000) * 0.4
            
            # Success rate
            score += (perf['success_rate'] / 100) * 0.3
            
            # Sharpe ratio (assume max 3)
            score += (perf.get('sharpe_ratio', 0) / 3) * 0.2
            
            # MAE penalty (lower is better)
            mae_penalty = abs(perf.get('avg_mae', 0)) / 10000
            score -= mae_penalty * 0.1
            
            if score > best_score:
                best_score = score
                best_strategy = {
                    "profit_threshold": strategy['profit_threshold'],
                    "time_threshold": strategy['time_threshold'],
                    "score": score,
                    "performance": perf
                }
        
        return best_strategy
    
    async def _analyze_trades_with_strategy(
        self,
        conn,
        trades: pd.DataFrame,
        profit_threshold: float,
        time_threshold: int
    ) -> List[Dict[str, Any]]:
        """Analyze individual trades with optimal strategy"""
        
        trade_analysis = []
        
        for _, trade in trades.iterrows():
            minute_pnl = self._get_minute_pnl_for_trade(
                conn,
                trade['TradeId'],
                trade['EntryTime'],
                trade['ExitTime']
            )
            
            if minute_pnl.empty:
                continue
            
            # Find breakeven point
            breakeven_minute = None
            for idx, row in minute_pnl.iterrows():
                if row.get('NetPnL', 0) > 0:
                    breakeven_minute = idx * 5
                    break
            
            # Find max profit and time
            max_profit_idx = minute_pnl['NetPnL'].idxmax() if 'NetPnL' in minute_pnl.columns else None
            max_profit = minute_pnl.loc[max_profit_idx, 'NetPnL'] if max_profit_idx is not None else 0
            max_profit_minute = max_profit_idx * 5 if max_profit_idx is not None else None
            
            # Find max drawdown
            cumulative_max = minute_pnl['NetPnL'].cummax() if 'NetPnL' in minute_pnl.columns else pd.Series()
            drawdown = (minute_pnl['NetPnL'] - cumulative_max) if 'NetPnL' in minute_pnl.columns else pd.Series()
            max_drawdown = drawdown.min() if not drawdown.empty else 0
            
            trade_analysis.append({
                "trade_id": trade['TradeId'],
                "signal_type": trade['SignalType'],
                "entry_time": trade['EntryTime'],
                "first_breakeven_minute": breakeven_minute,
                "max_profit": float(max_profit),
                "max_profit_minute": max_profit_minute,
                "max_drawdown": float(max_drawdown),
                "actual_pnl": float(trade['ActualPnL']),
                "would_hit_profit_threshold": max_profit >= profit_threshold,
                "would_exit_on_time": breakeven_minute and breakeven_minute <= time_threshold
            })
        
        return trade_analysis
    
    def _calculate_strategy_sharpe(self, minute_pnl: pd.DataFrame, total_pnl: float) -> float:
        """Calculate Sharpe ratio for strategy"""
        if minute_pnl.empty or 'NetPnL' not in minute_pnl.columns:
            return 0
        
        returns = minute_pnl['NetPnL'].pct_change().dropna()
        if returns.empty:
            return 0
        
        mean_return = returns.mean()
        std_return = returns.std()
        
        if std_return == 0:
            return 0
        
        # Annualized Sharpe (assuming 5-min intervals, 78 per day, 390 per week)
        return (mean_return / std_return) * np.sqrt(390)
    
    async def store_breakeven_analysis(
        self,
        validation_run_id: str,
        optimization_results: Dict[str, Any]
    ):
        """Store breakeven analysis results in database"""
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Store each trade's breakeven analysis
            for trade in optimization_results.get("trade_analysis", []):
                cursor.execute("""
                    INSERT INTO MLBreakevenAnalysis
                    (ValidationRunId, TradeId, SignalType, EntryTime,
                     FirstBreakevenTime, MinutesToBreakeven, MaxProfit,
                     MaxProfitTime, MaxDrawdown, Strategy, ProfitThreshold,
                     TimeThreshold, FinalPnL)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    validation_run_id,
                    trade['trade_id'],
                    trade['signal_type'],
                    trade['entry_time'],
                    trade['entry_time'] + timedelta(minutes=trade['first_breakeven_minute']) 
                        if trade['first_breakeven_minute'] else None,
                    trade['first_breakeven_minute'],
                    trade['max_profit'],
                    trade['entry_time'] + timedelta(minutes=trade['max_profit_minute'])
                        if trade['max_profit_minute'] else None,
                    trade['max_drawdown'],
                    optimization_results['optimal_strategy']['performance']['strategy'],
                    optimization_results['optimal_strategy']['profit_threshold'],
                    optimization_results['optimal_strategy']['time_threshold'],
                    trade['actual_pnl']
                )
            
            conn.commit()
            logger.info(f"Stored breakeven analysis for {len(optimization_results.get('trade_analysis', []))} trades")