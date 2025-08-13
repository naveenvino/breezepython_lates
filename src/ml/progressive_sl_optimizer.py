"""
ML Progressive Stop-Loss Optimizer
Optimizes progressive SL parameters using machine learning
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pyodbc
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

logger = logging.getLogger(__name__)


class MLProgressiveSLOptimizer:
    """
    Optimizes progressive stop-loss parameters using ML analysis of historical data.
    Learns optimal profit triggers, day-based rules, and signal-specific parameters.
    """
    
    def __init__(self, db_connection_string: str):
        """
        Initialize ML Progressive SL Optimizer
        
        Args:
            db_connection_string: Database connection string
        """
        self.conn_str = db_connection_string
        self.models = {}  # Store trained models per signal
        self.optimal_params = {}  # Store optimized parameters
        self.feature_importance = {}  # Track important features
        
    def get_connection(self):
        """Get database connection"""
        return pyodbc.connect(self.conn_str)
        
    async def optimize_for_signal(
        self,
        signal_type: str,
        from_date: datetime,
        to_date: datetime
    ) -> Dict:
        """
        Optimize progressive SL parameters for a specific signal
        
        Args:
            signal_type: Signal to optimize (S1-S8)
            from_date: Start date for training data
            to_date: End date for training data
            
        Returns:
            Optimized parameters for the signal
        """
        logger.info(f"Optimizing progressive SL for signal {signal_type}")
        
        with self.get_connection() as conn:
            # Get historical trade data
            trades_df = self._get_signal_trades(conn, signal_type, from_date, to_date)
            
            if trades_df.empty or len(trades_df) < 10:
                logger.warning(f"Insufficient data for signal {signal_type}")
                return self._get_default_params()
                
            # Extract features for ML
            features_df = self._extract_features(conn, trades_df)
            
            # Train model to predict optimal parameters
            model, optimal_params = self._train_optimization_model(
                features_df, trades_df
            )
            
            # Store model and parameters
            self.models[signal_type] = model
            self.optimal_params[signal_type] = optimal_params
            
            # Analyze feature importance
            self.feature_importance[signal_type] = self._analyze_feature_importance(
                model, features_df.columns
            )
            
            return optimal_params
            
    def _get_signal_trades(
        self,
        conn,
        signal_type: str,
        from_date: datetime,
        to_date: datetime
    ) -> pd.DataFrame:
        """Get historical trades for a signal"""
        query = """
        SELECT 
            bt.Id as TradeId,
            bt.SignalType,
            bt.EntryTime,
            bt.ExitTime,
            bt.TotalPnL,
            bt.IndexPriceAtEntry,
            bt.IndexPriceAtExit,
            bt.StopLossPrice,
            bt.Outcome,
            DATEDIFF(hour, bt.EntryTime, bt.ExitTime) as HoldingHours,
            bp_main.StrikePrice as MainStrike,
            bp_main.EntryPrice as MainEntryPrice,
            bp_main.ExitPrice as MainExitPrice,
            bp_hedge.StrikePrice as HedgeStrike,
            bp_hedge.EntryPrice as HedgeEntryPrice,
            bp_hedge.ExitPrice as HedgeExitPrice
        FROM BacktestTrades bt
        LEFT JOIN BacktestPositions bp_main ON bt.Id = bp_main.TradeId 
            AND bp_main.PositionType = 'MAIN'
        LEFT JOIN BacktestPositions bp_hedge ON bt.Id = bp_hedge.TradeId 
            AND bp_hedge.PositionType = 'HEDGE'
        WHERE bt.SignalType = ?
            AND bt.EntryTime >= ?
            AND bt.EntryTime <= ?
        ORDER BY bt.EntryTime
        """
        
        return pd.read_sql(query, conn, params=[signal_type, from_date, to_date])
        
    def _extract_features(self, conn, trades_df: pd.DataFrame) -> pd.DataFrame:
        """Extract ML features from trades"""
        features = []
        
        for _, trade in trades_df.iterrows():
            # Get intraday P&L progression
            pnl_progression = self._get_pnl_progression(
                conn, trade['TradeId'], 
                trade['EntryTime'], trade['ExitTime']
            )
            
            if pnl_progression.empty:
                continue
                
            # Calculate features
            feature_dict = {
                # Entry conditions
                'entry_index': trade['IndexPriceAtEntry'],
                'main_premium': trade['MainEntryPrice'],
                'hedge_premium': trade['HedgeEntryPrice'],
                'net_premium': trade['MainEntryPrice'] - trade['HedgeEntryPrice'],
                
                # P&L progression features
                'max_profit': pnl_progression['NetPnL'].max(),
                'min_profit': pnl_progression['NetPnL'].min(),
                'profit_volatility': pnl_progression['NetPnL'].std(),
                'time_to_max_profit': pnl_progression['NetPnL'].idxmax() * 5,  # minutes
                'time_to_min_profit': pnl_progression['NetPnL'].idxmin() * 5,
                
                # Drawdown features
                'max_drawdown': self._calculate_max_drawdown(pnl_progression['NetPnL']),
                'recovery_time': self._calculate_recovery_time(pnl_progression['NetPnL']),
                
                # Day-wise features
                'day1_close_pnl': self._get_day_close_pnl(pnl_progression, 1),
                'day2_close_pnl': self._get_day_close_pnl(pnl_progression, 2),
                'day3_close_pnl': self._get_day_close_pnl(pnl_progression, 3),
                
                # Outcome
                'final_pnl': trade['TotalPnL'],
                'was_profitable': 1 if trade['TotalPnL'] > 0 else 0
            }
            
            features.append(feature_dict)
            
        return pd.DataFrame(features)
        
    def _get_pnl_progression(
        self,
        conn,
        trade_id: str,
        entry_time: datetime,
        exit_time: datetime
    ) -> pd.DataFrame:
        """Get minute-by-minute P&L progression"""
        query = """
        SELECT 
            Timestamp,
            NetPnL,
            NiftyIndex
        FROM BacktestPnLTracking
        WHERE TradeId = ?
        ORDER BY Timestamp
        """
        
        df = pd.read_sql(query, conn, params=[trade_id])
        
        if df.empty:
            # Fallback: calculate from options data
            return self._calculate_pnl_from_options(
                conn, trade_id, entry_time, exit_time
            )
            
        return df
        
    def _train_optimization_model(
        self,
        features_df: pd.DataFrame,
        trades_df: pd.DataFrame
    ) -> Tuple:
        """Train ML model to predict optimal parameters"""
        
        # Prepare training data
        X = features_df.drop(['final_pnl', 'was_profitable'], axis=1)
        y = features_df['final_pnl']
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Train Random Forest model
        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        model.fit(X_train, y_train)
        
        # Evaluate model
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        logger.info(f"Model MAE: {mae:.2f}")
        
        # Optimize parameters based on model insights
        optimal_params = self._derive_optimal_params(
            model, features_df, trades_df
        )
        
        return model, optimal_params
        
    def _derive_optimal_params(
        self,
        model,
        features_df: pd.DataFrame,
        trades_df: pd.DataFrame
    ) -> Dict:
        """Derive optimal progressive SL parameters from model"""
        
        # Analyze profitable trades
        profitable_trades = features_df[features_df['was_profitable'] == 1]
        
        if len(profitable_trades) == 0:
            return self._get_default_params()
            
        # Calculate optimal profit trigger
        # Find the profit level where most trades become profitable
        profit_levels = profitable_trades['max_profit'].values
        profit_trigger = np.percentile(profit_levels, 25)  # Conservative trigger
        
        # Calculate optimal day-based factors
        day2_factor = self._calculate_optimal_day_factor(
            features_df, 'day2_close_pnl', profitable_trades
        )
        
        # Determine profit lock percentage
        final_profits = profitable_trades['final_pnl'].values
        profit_lock = np.percentile(final_profits, 10) / np.mean(profit_levels) * 100
        
        return {
            'initial_sl_per_lot': 6000,  # Keep default
            'profit_trigger_percent': min(max(profit_trigger / 100, 20), 60),
            'day2_sl_factor': min(max(day2_factor, 0.3), 0.7),
            'day3_breakeven': True,
            'day4_profit_lock_percent': min(max(profit_lock, 3), 10),
            'confidence': len(profitable_trades) / len(features_df)
        }
        
    def _calculate_optimal_day_factor(
        self,
        all_trades: pd.DataFrame,
        day_column: str,
        profitable_trades: pd.DataFrame
    ) -> float:
        """Calculate optimal factor for a specific day"""
        if day_column not in all_trades.columns:
            return 0.5
            
        # Find the factor that maximizes profitable trades
        day_pnls = all_trades[day_column].dropna()
        if len(day_pnls) == 0:
            return 0.5
            
        # Calculate what percentage of initial SL works best
        initial_sl = -6000 * 10  # Assuming 10 lots
        factors = []
        
        for pnl in day_pnls:
            if pnl < 0:
                factor = abs(pnl / initial_sl)
                factors.append(min(factor, 1.0))
                
        return np.median(factors) if factors else 0.5
        
    def _calculate_max_drawdown(self, pnl_series: pd.Series) -> float:
        """Calculate maximum drawdown from P&L series"""
        cummax = pnl_series.cummax()
        drawdown = pnl_series - cummax
        return abs(drawdown.min()) if len(drawdown) > 0 else 0
        
    def _calculate_recovery_time(self, pnl_series: pd.Series) -> int:
        """Calculate time to recover from drawdown (in 5-min intervals)"""
        cummax = pnl_series.cummax()
        drawdown = pnl_series - cummax
        
        if drawdown.min() >= 0:
            return 0
            
        # Find the worst drawdown point
        worst_idx = drawdown.idxmin()
        
        # Find recovery point
        for idx in range(worst_idx + 1, len(pnl_series)):
            if pnl_series.iloc[idx] >= cummax.iloc[worst_idx]:
                return idx - worst_idx
                
        return len(pnl_series) - worst_idx
        
    def _get_day_close_pnl(
        self,
        pnl_df: pd.DataFrame,
        day_number: int
    ) -> float:
        """Get P&L at day close"""
        if pnl_df.empty:
            return 0
            
        # Assuming 78 5-min intervals per day (9:15 AM to 3:30 PM)
        day_end_idx = day_number * 78
        
        if day_end_idx < len(pnl_df):
            return pnl_df.iloc[day_end_idx]['NetPnL']
        else:
            return pnl_df.iloc[-1]['NetPnL']
            
    def _get_default_params(self) -> Dict:
        """Get default parameters when optimization not possible"""
        return {
            'initial_sl_per_lot': 6000,
            'profit_trigger_percent': 40,
            'day2_sl_factor': 0.5,
            'day3_breakeven': True,
            'day4_profit_lock_percent': 5,
            'confidence': 0
        }
        
    def _analyze_feature_importance(
        self,
        model,
        feature_names: List[str]
    ) -> Dict:
        """Analyze and return feature importance"""
        importances = model.feature_importances_
        feature_importance = dict(zip(feature_names, importances))
        
        # Sort by importance
        sorted_importance = dict(
            sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
        )
        
        # Log top features
        top_features = list(sorted_importance.items())[:5]
        logger.info(f"Top 5 important features: {top_features}")
        
        return sorted_importance
        
    def _calculate_pnl_from_options(
        self,
        conn,
        trade_id: str,
        entry_time: datetime,
        exit_time: datetime
    ) -> pd.DataFrame:
        """Calculate P&L from options data if tracking not available"""
        # This would calculate P&L from OptionsHistoricalData
        # Similar to what we did in progressive_sl_manager
        return pd.DataFrame()  # Placeholder
        
    async def optimize_all_signals(
        self,
        from_date: datetime,
        to_date: datetime
    ) -> Dict:
        """
        Optimize progressive SL for all signals
        
        Returns:
            Dictionary of optimized parameters per signal
        """
        all_params = {}
        
        for signal in ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]:
            params = await self.optimize_for_signal(signal, from_date, to_date)
            all_params[signal] = params
            
        return all_params
        
    def get_regime_adjusted_params(
        self,
        signal_type: str,
        market_regime: str
    ) -> Dict:
        """
        Get parameters adjusted for market regime
        
        Args:
            signal_type: Signal type (S1-S8)
            market_regime: Current market regime (trending/ranging/volatile)
            
        Returns:
            Adjusted parameters
        """
        base_params = self.optimal_params.get(
            signal_type, 
            self._get_default_params()
        )
        
        # Adjust based on regime
        if market_regime == "volatile":
            # Tighter stop-losses in volatile markets
            base_params['initial_sl_per_lot'] *= 0.8
            base_params['profit_trigger_percent'] *= 0.8
            
        elif market_regime == "trending":
            # Wider stop-losses in trending markets
            base_params['initial_sl_per_lot'] *= 1.2
            base_params['day4_profit_lock_percent'] *= 1.5
            
        elif market_regime == "ranging":
            # Quicker profit taking in ranging markets
            base_params['profit_trigger_percent'] *= 0.7
            base_params['day2_sl_factor'] = 0.4
            
        return base_params