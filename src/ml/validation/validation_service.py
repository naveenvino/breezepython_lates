"""
ML Validation Service - Core orchestration for comprehensive backtesting
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import pyodbc
import pandas as pd
import numpy as np
from uuid import uuid4

logger = logging.getLogger(__name__)

class MLValidationService:
    """Main service for ML validation and backtesting"""
    
    def __init__(self):
        self.conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=(localdb)\\mssqllocaldb;Database=KiteConnectApi;Trusted_Connection=yes;"
        self.signals = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
        
    def get_connection(self):
        """Get database connection"""
        return pyodbc.connect(self.conn_str)
    
    async def validate_hedge_optimization(
        self,
        from_date: date,
        to_date: date,
        hedge_distances: List[int]
    ) -> Dict[str, Any]:
        """
        Validate different hedge distances for all signals
        Returns comprehensive analysis of hedge performance
        """
        logger.info(f"Starting hedge optimization from {from_date} to {to_date}")
        
        results = {}
        
        with self.get_connection() as conn:
            # Get all trades in the period
            trades_df = self._get_trades_for_period(conn, from_date, to_date)
            
            if trades_df.empty:
                logger.warning("No trades found for the specified period")
                return {}
            
            # Analyze each signal
            for signal in self.signals:
                signal_trades = trades_df[trades_df['SignalType'] == signal]
                
                if signal_trades.empty:
                    continue
                
                signal_results = {
                    "trade_count": len(signal_trades),
                    "hedge_analysis": {}
                }
                
                # Test each hedge distance
                for hedge_distance in hedge_distances:
                    hedge_performance = self._analyze_hedge_distance(
                        conn,
                        signal_trades,
                        hedge_distance
                    )
                    signal_results["hedge_analysis"][hedge_distance] = hedge_performance
                
                # Find optimal hedge distance
                signal_results["optimal_hedge"] = self._find_optimal_hedge(
                    signal_results["hedge_analysis"]
                )
                
                results[signal] = signal_results
        
        return results
    
    def _get_trades_for_period(self, conn, from_date: date, to_date: date) -> pd.DataFrame:
        """Get all trades within specified period"""
        query = """
        SELECT 
            bt.Id as TradeId,
            bt.SignalType,
            bt.EntryTime,
            bt.ExitTime,
            bt.TotalPnL,
            bt.IndexPriceAtEntry,
            bt.IndexPriceAtExit,
            bp_main.StrikePrice as MainStrike,
            bp_main.OptionType as MainOptionType,
            bp_main.EntryPrice as MainEntryPrice,
            bp_main.ExitPrice as MainExitPrice,
            bp_main.Quantity,
            bp_hedge.StrikePrice as HedgeStrike,
            bp_hedge.EntryPrice as HedgeEntryPrice,
            bp_hedge.ExitPrice as HedgeExitPrice
        FROM BacktestTrades bt
        LEFT JOIN BacktestPositions bp_main ON bt.Id = bp_main.TradeId 
            AND bp_main.PositionType = 'MAIN'
        LEFT JOIN BacktestPositions bp_hedge ON bt.Id = bp_hedge.TradeId 
            AND bp_hedge.PositionType = 'HEDGE'
        WHERE bt.EntryTime >= ? AND bt.EntryTime <= DATEADD(day, 1, ?)
        ORDER BY bt.EntryTime
        """
        
        return pd.read_sql(query, conn, params=[from_date, to_date])
    
    def _analyze_hedge_distance(
        self, 
        conn, 
        trades_df: pd.DataFrame, 
        hedge_distance: int
    ) -> Dict[str, Any]:
        """Analyze performance of specific hedge distance"""
        
        total_pnl = 0
        trade_results = []
        otm_penalties = []
        
        for _, trade in trades_df.iterrows():
            # Calculate new hedge strike
            main_strike = trade['MainStrike']
            
            # For PUT selling (bullish signals), hedge is at lower strike
            # For CALL selling (bearish signals), hedge is at higher strike
            if trade['MainOptionType'] == 'PE':
                hedge_strike = main_strike - hedge_distance
            else:
                hedge_strike = main_strike + hedge_distance
            
            # Get option prices for this hedge strike
            hedge_prices = self._get_option_prices(
                conn,
                hedge_strike,
                trade['MainOptionType'],
                trade['EntryTime'],
                trade['ExitTime']
            )
            
            if hedge_prices is None:
                # No data for this strike - skip
                continue
            
            # Calculate P&L with new hedge
            main_pnl = (trade['MainEntryPrice'] - trade['MainExitPrice']) * trade['Quantity']
            
            # For hedge, we buy it (opposite of main position)
            hedge_pnl = (hedge_prices['exit_price'] - hedge_prices['entry_price']) * trade['Quantity']
            
            net_pnl = main_pnl + hedge_pnl
            
            # Calculate OTM penalty if hedge became ITM
            otm_penalty = self._calculate_otm_penalty(
                hedge_strike,
                trade['IndexPriceAtExit'],
                trade['MainOptionType'],
                hedge_pnl
            )
            
            total_pnl += net_pnl
            otm_penalties.append(otm_penalty)
            
            trade_results.append({
                "trade_id": trade['TradeId'],
                "main_pnl": main_pnl,
                "hedge_pnl": hedge_pnl,
                "net_pnl": net_pnl,
                "otm_penalty": otm_penalty
            })
        
        # Calculate metrics
        if trade_results:
            pnl_values = [t['net_pnl'] for t in trade_results]
            
            return {
                "total_pnl": total_pnl,
                "avg_pnl": np.mean(pnl_values),
                "max_pnl": max(pnl_values),
                "min_pnl": min(pnl_values),
                "std_pnl": np.std(pnl_values),
                "sharpe_ratio": self._calculate_sharpe_ratio(pnl_values),
                "sortino_ratio": self._calculate_sortino_ratio(pnl_values),
                "max_drawdown": self._calculate_max_drawdown(pnl_values),
                "win_rate": sum(1 for p in pnl_values if p > 0) / len(pnl_values) * 100,
                "avg_otm_penalty": np.mean(otm_penalties),
                "trades_analyzed": len(trade_results)
            }
        else:
            return {
                "total_pnl": 0,
                "avg_pnl": 0,
                "trades_analyzed": 0,
                "error": "No data available for this hedge distance"
            }
    
    def _get_option_prices(
        self, 
        conn, 
        strike: int, 
        option_type: str,
        entry_time: datetime, 
        exit_time: datetime
    ) -> Optional[Dict[str, float]]:
        """Get option prices at entry and exit times"""
        
        # Query for entry price
        entry_query = """
        SELECT TOP 1 [Close] as Price
        FROM OptionsHistoricalData
        WHERE Strike = ? 
        AND OptionType = ?
        AND Timestamp >= ?
        AND Timestamp <= DATEADD(minute, 30, ?)
        ORDER BY ABS(DATEDIFF(second, Timestamp, ?))
        """
        
        cursor = conn.cursor()
        cursor.execute(entry_query, strike, option_type, entry_time, entry_time, entry_time)
        entry_result = cursor.fetchone()
        
        if not entry_result:
            return None
        
        # Query for exit price
        exit_query = """
        SELECT TOP 1 [Close] as Price
        FROM OptionsHistoricalData
        WHERE Strike = ? 
        AND OptionType = ?
        AND Timestamp >= DATEADD(minute, -30, ?)
        AND Timestamp <= ?
        ORDER BY ABS(DATEDIFF(second, Timestamp, ?))
        """
        
        cursor.execute(exit_query, strike, option_type, exit_time, exit_time, exit_time)
        exit_result = cursor.fetchone()
        
        if not exit_result:
            return None
        
        return {
            "entry_price": entry_result[0],
            "exit_price": exit_result[0]
        }
    
    def _calculate_otm_penalty(
        self, 
        hedge_strike: int, 
        index_price_at_exit: float,
        option_type: str,
        hedge_pnl: float
    ) -> float:
        """Calculate penalty if OTM hedge became ITM"""
        
        # Check if hedge became ITM
        if option_type == 'PE':
            # PUT hedge becomes ITM if index goes below hedge strike
            if index_price_at_exit < hedge_strike:
                # Hedge became ITM - calculate penalty
                intrinsic_value = hedge_strike - index_price_at_exit
                # Penalty is the additional loss from hedge becoming ITM
                return min(0, hedge_pnl - intrinsic_value * 75)  # Assuming 1 lot = 75 qty
        else:
            # CALL hedge becomes ITM if index goes above hedge strike
            if index_price_at_exit > hedge_strike:
                intrinsic_value = index_price_at_exit - hedge_strike
                return min(0, hedge_pnl - intrinsic_value * 75)
        
        return 0  # No penalty if hedge remained OTM
    
    def _calculate_sharpe_ratio(self, pnl_values: List[float]) -> float:
        """Calculate Sharpe ratio"""
        if not pnl_values or len(pnl_values) < 2:
            return 0
        
        mean_return = np.mean(pnl_values)
        std_return = np.std(pnl_values)
        
        if std_return == 0:
            return 0
        
        # Annualized Sharpe ratio (assuming weekly trades, 52 weeks/year)
        return (mean_return / std_return) * np.sqrt(52)
    
    def _calculate_sortino_ratio(self, pnl_values: List[float]) -> float:
        """Calculate Sortino ratio (focuses on downside risk)"""
        if not pnl_values or len(pnl_values) < 2:
            return 0
        
        mean_return = np.mean(pnl_values)
        
        # Calculate downside deviation
        negative_returns = [r for r in pnl_values if r < 0]
        
        if not negative_returns:
            # No negative returns - very high Sortino ratio
            return 10.0  # Cap at 10
        
        downside_deviation = np.std(negative_returns)
        
        if downside_deviation == 0:
            return 10.0
        
        # Annualized Sortino ratio
        return (mean_return / downside_deviation) * np.sqrt(52)
    
    def _calculate_max_drawdown(self, pnl_values: List[float]) -> float:
        """Calculate maximum drawdown"""
        if not pnl_values:
            return 0
        
        cumulative = np.cumsum(pnl_values)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = cumulative - running_max
        
        return min(drawdown) if len(drawdown) > 0 else 0
    
    def _find_optimal_hedge(self, hedge_analysis: Dict[int, Dict]) -> Dict[str, Any]:
        """Find optimal hedge distance based on multiple criteria"""
        
        if not hedge_analysis:
            return {"distance": 200, "reason": "Default"}
        
        # Score each hedge distance
        scores = {}
        
        for distance, metrics in hedge_analysis.items():
            if metrics.get("trades_analyzed", 0) == 0:
                continue
            
            # Calculate composite score
            score = 0
            
            # Sharpe ratio (weight: 30%)
            score += metrics.get("sharpe_ratio", 0) * 0.3
            
            # Sortino ratio (weight: 20%)
            score += metrics.get("sortino_ratio", 0) * 0.2
            
            # Win rate (weight: 20%)
            score += metrics.get("win_rate", 0) / 100 * 0.2
            
            # Average P&L (normalized, weight: 20%)
            max_avg_pnl = max(m.get("avg_pnl", 0) for m in hedge_analysis.values())
            if max_avg_pnl > 0:
                score += (metrics.get("avg_pnl", 0) / max_avg_pnl) * 0.2
            
            # Penalty for OTM issues (weight: 10%)
            avg_penalty = metrics.get("avg_otm_penalty", 0)
            if avg_penalty < 0:
                score += (1 + avg_penalty / 10000) * 0.1  # Normalize penalty
            else:
                score += 0.1
            
            scores[distance] = score
        
        if not scores:
            return {"distance": 200, "reason": "No valid data"}
        
        # Find best hedge distance
        optimal_distance = max(scores, key=scores.get)
        optimal_metrics = hedge_analysis[optimal_distance]
        
        return {
            "distance": optimal_distance,
            "score": scores[optimal_distance],
            "sharpe_ratio": optimal_metrics.get("sharpe_ratio", 0),
            "avg_pnl": optimal_metrics.get("avg_pnl", 0),
            "win_rate": optimal_metrics.get("win_rate", 0),
            "reason": f"Best composite score: {scores[optimal_distance]:.2f}"
        }
    
    async def validate_all_strategies(
        self,
        from_date: date,
        to_date: date,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run complete validation including hedge optimization,
        market classification, and breakeven analysis
        """
        validation_id = str(uuid4())
        
        logger.info(f"Starting complete validation {validation_id}")
        
        # Store validation run in database
        self._store_validation_run(validation_id, from_date, to_date, config)
        
        try:
            # 1. Hedge optimization
            hedge_results = await self.validate_hedge_optimization(
                from_date,
                to_date,
                config.get("hedge_distances", [100, 150, 200, 250, 300])
            )
            
            # 2. Store hedge analysis results
            self._store_hedge_analysis(validation_id, hedge_results)
            
            # 3. Calculate performance metrics
            performance_metrics = self._calculate_performance_metrics(hedge_results)
            
            # 4. Store performance metrics
            self._store_performance_metrics(validation_id, performance_metrics)
            
            # 5. Update validation status
            self._update_validation_status(validation_id, "COMPLETED", {
                "hedge_results": hedge_results,
                "performance_metrics": performance_metrics
            })
            
            return {
                "validation_id": validation_id,
                "status": "COMPLETED",
                "hedge_results": hedge_results,
                "performance_metrics": performance_metrics
            }
            
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            self._update_validation_status(validation_id, "FAILED", {"error": str(e)})
            raise
    
    def _store_validation_run(self, validation_id: str, from_date: date, to_date: date, config: Dict):
        """Store validation run in database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO MLValidationRuns 
                (Id, RunDate, FromDate, ToDate, Parameters, Status, CreatedAt)
                VALUES (?, GETDATE(), ?, ?, ?, 'PROCESSING', GETDATE())
            """, validation_id, from_date, to_date, str(config))
            conn.commit()
    
    def _store_hedge_analysis(self, validation_id: str, hedge_results: Dict):
        """Store hedge analysis results in database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for signal, signal_results in hedge_results.items():
                for hedge_distance, metrics in signal_results.get("hedge_analysis", {}).items():
                    cursor.execute("""
                        INSERT INTO MLHedgeAnalysis
                        (ValidationRunId, SignalType, HedgeDistance, NetPnL, 
                         SharpeRatio, SortinoRatio, TradeId)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, validation_id, signal, hedge_distance, 
                        metrics.get("avg_pnl", 0),
                        metrics.get("sharpe_ratio", 0),
                        metrics.get("sortino_ratio", 0),
                        f"{signal}_{hedge_distance}")
            
            conn.commit()
    
    def _calculate_performance_metrics(self, hedge_results: Dict) -> Dict[str, Any]:
        """Calculate overall performance metrics"""
        metrics = {}
        
        for signal, signal_results in hedge_results.items():
            optimal = signal_results.get("optimal_hedge", {})
            
            metrics[signal] = {
                "optimal_hedge_distance": optimal.get("distance"),
                "sharpe_ratio": optimal.get("sharpe_ratio", 0),
                "avg_pnl": optimal.get("avg_pnl", 0),
                "win_rate": optimal.get("win_rate", 0),
                "trade_count": signal_results.get("trade_count", 0)
            }
        
        return metrics
    
    def _store_performance_metrics(self, validation_id: str, metrics: Dict):
        """Store performance metrics in database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for signal, signal_metrics in metrics.items():
                cursor.execute("""
                    INSERT INTO MLPerformanceMetrics
                    (ValidationRunId, SignalType, TotalTrades, WinRate, 
                     AvgPnL, SharpeRatio)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, validation_id, signal, 
                    signal_metrics.get("trade_count", 0),
                    signal_metrics.get("win_rate", 0),
                    signal_metrics.get("avg_pnl", 0),
                    signal_metrics.get("sharpe_ratio", 0))
            
            conn.commit()
    
    def _update_validation_status(self, validation_id: str, status: str, results: Dict):
        """Update validation run status"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE MLValidationRuns
                SET Status = ?, Results = ?, CompletedAt = GETDATE()
                WHERE Id = ?
            """, status, str(results), validation_id)
            conn.commit()