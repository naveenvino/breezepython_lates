"""
Stop Loss Optimizer
ML model to optimize stop loss placement for trading signals
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging
import joblib
from pathlib import Path
from dataclasses import dataclass

from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb
import lightgbm as lgb

logger = logging.getLogger(__name__)

@dataclass
class OptimalStopLoss:
    """Optimal stop loss recommendation"""
    signal_type: str
    current_price: float
    recommended_stop: float
    stop_distance_pct: float
    confidence_score: float
    expected_risk_reward: float
    market_conditions: Dict[str, float]

class StopLossOptimizer:
    """ML model to optimize stop loss placement"""
    
    def __init__(self, model_type: str = 'xgboost'):
        """
        Initialize stop loss optimizer
        
        Args:
            model_type: Type of model ('xgboost', 'lightgbm', 'random_forest')
        """
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.feature_columns = []
        self.performance_metrics = {}
        
    def create_model(self, **kwargs):
        """
        Create regression model for stop loss prediction
        
        Args:
            **kwargs: Model-specific parameters
            
        Returns:
            Model instance
        """
        if self.model_type == 'xgboost':
            default_params = {
                'n_estimators': 100,
                'max_depth': 6,
                'learning_rate': 0.1,
                'objective': 'reg:squarederror',
                'random_state': 42
            }
            default_params.update(kwargs)
            model = xgb.XGBRegressor(**default_params)
            
        elif self.model_type == 'lightgbm':
            default_params = {
                'n_estimators': 100,
                'max_depth': 6,
                'learning_rate': 0.1,
                'objective': 'regression',
                'metric': 'rmse',
                'random_state': 42,
                'verbose': -1
            }
            default_params.update(kwargs)
            model = lgb.LGBMRegressor(**default_params)
            
        elif self.model_type == 'random_forest':
            default_params = {
                'n_estimators': 100,
                'max_depth': 10,
                'min_samples_split': 5,
                'min_samples_leaf': 2,
                'random_state': 42
            }
            default_params.update(kwargs)
            model = RandomForestRegressor(**default_params)
            
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
            
        return model
    
    def prepare_training_data(self,
                             trades_df: pd.DataFrame,
                             market_df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare training data for stop loss optimization
        
        Args:
            trades_df: DataFrame with historical trades
            market_df: DataFrame with market data
            
        Returns:
            DataFrame with features and optimal stop loss targets
        """
        # Calculate optimal stop loss for each trade
        # This is the stop that would have maximized profit while minimizing risk
        
        training_data = []
        
        for _, trade in trades_df.iterrows():
            # Get market data around trade time
            trade_time = pd.to_datetime(trade['EntryTime'])
            market_slice = market_df[
                (market_df.index >= trade_time - pd.Timedelta(hours=2)) &
                (market_df.index <= trade_time + pd.Timedelta(hours=24))
            ]
            
            if market_slice.empty:
                continue
                
            # Calculate features at entry
            features = self._calculate_entry_features(market_slice.iloc[0], trade)
            
            # Calculate optimal stop (simplified - in reality would use more sophisticated logic)
            # Find the maximum adverse excursion that would still result in profit
            entry_price = trade['EntryPrice']
            exit_price = trade['ExitPrice']
            
            if trade['Direction'] == 'BULLISH':
                # For bullish trades, find lowest price that still allows profit
                min_price = market_slice['Low'].min()
                optimal_stop = max(
                    min_price * 0.99,  # Add small buffer
                    entry_price * 0.97  # Maximum 3% stop
                )
            else:
                # For bearish trades, find highest price
                max_price = market_slice['High'].max()
                optimal_stop = min(
                    max_price * 1.01,  # Add small buffer
                    entry_price * 1.03  # Maximum 3% stop
                )
                
            features['optimal_stop_distance'] = abs(optimal_stop - entry_price) / entry_price
            training_data.append(features)
            
        return pd.DataFrame(training_data)
    
    def _calculate_entry_features(self,
                                 market_data: pd.Series,
                                 trade: pd.Series) -> Dict:
        """
        Calculate features at trade entry
        
        Args:
            market_data: Market data at entry
            trade: Trade information
            
        Returns:
            Dictionary of features
        """
        features = {
            'signal_type': trade['SignalType'],
            'entry_price': trade['EntryPrice'],
            'atr': market_data.get('atr_14', 0),
            'volatility': market_data.get('volatility_20', 0),
            'rsi': market_data.get('rsi_14', 50),
            'volume_ratio': market_data.get('volume_ratio', 1),
            'distance_to_resistance': market_data.get('distance_to_high_20', 0),
            'distance_to_support': market_data.get('distance_to_low_20', 0),
            'trend_strength': market_data.get('adx_14', 0),
            'time_of_day': pd.to_datetime(trade['EntryTime']).hour,
            'day_of_week': pd.to_datetime(trade['EntryTime']).dayofweek
        }
        
        return features
    
    def train(self,
             X_train: pd.DataFrame,
             y_train: pd.Series,
             X_val: pd.DataFrame = None,
             y_val: pd.Series = None) -> Dict[str, float]:
        """
        Train stop loss optimizer
        
        Args:
            X_train: Training features
            y_train: Optimal stop distances
            X_val: Validation features
            y_val: Validation stop distances
            
        Returns:
            Training metrics
        """
        self.feature_columns = X_train.columns.tolist()
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        
        # Create and train model
        self.model = self.create_model()
        
        if X_val is not None and y_val is not None:
            X_val_scaled = self.scaler.transform(X_val)
            
            if self.model_type in ['xgboost', 'lightgbm']:
                eval_set = [(X_train_scaled, y_train), (X_val_scaled, y_val)]
                self.model.fit(
                    X_train_scaled, y_train,
                    eval_set=eval_set,
                    early_stopping_rounds=10,
                    verbose=False
                )
            else:
                self.model.fit(X_train_scaled, y_train)
        else:
            self.model.fit(X_train_scaled, y_train)
            
        # Calculate metrics
        train_pred = self.model.predict(X_train_scaled)
        
        metrics = {
            'train_mae': mean_absolute_error(y_train, train_pred),
            'train_rmse': np.sqrt(mean_squared_error(y_train, train_pred)),
            'train_r2': r2_score(y_train, train_pred)
        }
        
        if X_val is not None and y_val is not None:
            val_pred = self.model.predict(X_val_scaled)
            metrics.update({
                'val_mae': mean_absolute_error(y_val, val_pred),
                'val_rmse': np.sqrt(mean_squared_error(y_val, val_pred)),
                'val_r2': r2_score(y_val, val_pred)
            })
            
        self.performance_metrics = metrics
        logger.info(f"Stop loss optimizer trained - Val MAE: {metrics.get('val_mae', metrics['train_mae']):.4f}")
        
        return metrics
    
    def optimize_stop_loss(self,
                          signal_type: str,
                          entry_price: float,
                          market_features: Dict[str, float],
                          direction: str = 'BULLISH') -> OptimalStopLoss:
        """
        Optimize stop loss for a new trade
        
        Args:
            signal_type: Type of signal (S1-S8)
            entry_price: Entry price for the trade
            market_features: Current market features
            direction: Trade direction
            
        Returns:
            OptimalStopLoss recommendation
        """
        if self.model is None:
            raise ValueError("Model not trained yet")
            
        # Prepare features
        features = pd.DataFrame([{
            'signal_type': signal_type,
            'entry_price': entry_price,
            **market_features
        }])
        
        # Ensure all required features are present
        for col in self.feature_columns:
            if col not in features.columns:
                features[col] = 0
                
        features = features[self.feature_columns]
        features_scaled = self.scaler.transform(features)
        
        # Predict optimal stop distance
        stop_distance_pct = self.model.predict(features_scaled)[0]
        
        # Calculate stop price based on direction
        if direction == 'BULLISH':
            stop_price = entry_price * (1 - stop_distance_pct)
        else:
            stop_price = entry_price * (1 + stop_distance_pct)
            
        # Calculate confidence (based on feature importance if available)
        confidence = self._calculate_confidence(features_scaled)
        
        # Calculate expected risk-reward
        expected_rr = self._calculate_risk_reward(
            entry_price, stop_price, market_features, direction
        )
        
        return OptimalStopLoss(
            signal_type=signal_type,
            current_price=entry_price,
            recommended_stop=stop_price,
            stop_distance_pct=stop_distance_pct * 100,
            confidence_score=confidence,
            expected_risk_reward=expected_rr,
            market_conditions=market_features
        )
    
    def _calculate_confidence(self, features_scaled: np.ndarray) -> float:
        """
        Calculate confidence score for prediction
        
        Args:
            features_scaled: Scaled features
            
        Returns:
            Confidence score (0-1)
        """
        # Simple confidence based on prediction variance
        # In production, could use prediction intervals or ensemble disagreement
        
        if hasattr(self.model, 'predict_proba'):
            # For models with probability estimates
            return self.model.predict_proba(features_scaled)[0].max()
        else:
            # Default confidence based on model performance
            return min(0.95, self.performance_metrics.get('val_r2', 0.5) + 0.3)
    
    def _calculate_risk_reward(self,
                              entry_price: float,
                              stop_price: float,
                              market_features: Dict[str, float],
                              direction: str) -> float:
        """
        Calculate expected risk-reward ratio
        
        Args:
            entry_price: Entry price
            stop_price: Stop loss price
            market_features: Market features
            direction: Trade direction
            
        Returns:
            Risk-reward ratio
        """
        risk = abs(entry_price - stop_price)
        
        # Estimate target based on ATR and volatility
        atr = market_features.get('atr', entry_price * 0.01)
        volatility = market_features.get('volatility', 0.01)
        
        # Target is typically 1.5-2x risk
        expected_reward = risk * 1.5 * (1 + volatility)
        
        if direction == 'BULLISH':
            target_price = entry_price + expected_reward
        else:
            target_price = entry_price - expected_reward
            
        return expected_reward / risk if risk > 0 else 0
    
    def adaptive_stop_loss(self,
                          current_price: float,
                          entry_price: float,
                          initial_stop: float,
                          market_features: Dict[str, float],
                          direction: str = 'BULLISH',
                          time_in_trade: int = 0) -> float:
        """
        Dynamically adjust stop loss based on market conditions
        
        Args:
            current_price: Current market price
            entry_price: Original entry price
            initial_stop: Initial stop loss
            market_features: Current market features
            direction: Trade direction
            time_in_trade: Hours since entry
            
        Returns:
            Adjusted stop loss price
        """
        # Calculate profit percentage
        if direction == 'BULLISH':
            profit_pct = (current_price - entry_price) / entry_price
            in_profit = current_price > entry_price
        else:
            profit_pct = (entry_price - current_price) / entry_price
            in_profit = current_price < entry_price
            
        if not in_profit:
            # Don't adjust stop if trade is losing
            return initial_stop
            
        # Trail stop based on profit and volatility
        atr = market_features.get('atr', entry_price * 0.01)
        volatility = market_features.get('volatility', 0.01)
        
        # More aggressive trailing for higher profits
        if profit_pct > 0.02:  # 2% profit
            trail_distance = atr * 1.5
        elif profit_pct > 0.01:  # 1% profit
            trail_distance = atr * 2
        else:
            trail_distance = atr * 2.5
            
        # Adjust for volatility
        trail_distance *= (1 + volatility)
        
        # Calculate new stop
        if direction == 'BULLISH':
            new_stop = current_price - trail_distance
            # Never move stop lower
            new_stop = max(new_stop, initial_stop)
        else:
            new_stop = current_price + trail_distance
            # Never move stop higher
            new_stop = min(new_stop, initial_stop)
            
        # Time decay - tighten stop as trade ages
        if time_in_trade > 24:  # More than a day
            time_factor = 0.9
        elif time_in_trade > 12:  # More than half day
            time_factor = 0.95
        else:
            time_factor = 1.0
            
        if direction == 'BULLISH':
            new_stop = entry_price + (new_stop - entry_price) * time_factor
        else:
            new_stop = entry_price - (entry_price - new_stop) * time_factor
            
        return new_stop
    
    def analyze_stop_effectiveness(self,
                                  trades_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze effectiveness of stop loss optimization
        
        Args:
            trades_df: DataFrame with trades using optimized stops
            
        Returns:
            Analysis results
        """
        results = {
            'total_trades': len(trades_df),
            'stopped_trades': len(trades_df[trades_df['ExitReason'] == 'StopLoss']),
            'stop_rate': len(trades_df[trades_df['ExitReason'] == 'StopLoss']) / len(trades_df),
            'avg_stop_distance': trades_df['StopDistance'].mean(),
            'by_signal': {}
        }
        
        # Analyze by signal type
        for signal in trades_df['SignalType'].unique():
            signal_trades = trades_df[trades_df['SignalType'] == signal]
            
            results['by_signal'][signal] = {
                'total': len(signal_trades),
                'stopped': len(signal_trades[signal_trades['ExitReason'] == 'StopLoss']),
                'avg_pnl': signal_trades['PnL'].mean(),
                'win_rate': len(signal_trades[signal_trades['PnL'] > 0]) / len(signal_trades),
                'avg_stop_distance': signal_trades['StopDistance'].mean()
            }
            
        # Calculate improvement metrics
        if 'OriginalPnL' in trades_df.columns:
            results['pnl_improvement'] = (
                trades_df['PnL'].sum() - trades_df['OriginalPnL'].sum()
            ) / abs(trades_df['OriginalPnL'].sum())
            results['drawdown_reduction'] = self._calculate_drawdown_reduction(
                trades_df['PnL'], trades_df['OriginalPnL']
            )
            
        return results
    
    def _calculate_drawdown_reduction(self,
                                     optimized_pnl: pd.Series,
                                     original_pnl: pd.Series) -> float:
        """
        Calculate reduction in maximum drawdown
        
        Args:
            optimized_pnl: P&L with optimized stops
            original_pnl: P&L with original stops
            
        Returns:
            Percentage reduction in max drawdown
        """
        def max_drawdown(pnl_series):
            cumulative = pnl_series.cumsum()
            running_max = cumulative.expanding().max()
            drawdown = cumulative - running_max
            return abs(drawdown.min())
            
        original_dd = max_drawdown(original_pnl)
        optimized_dd = max_drawdown(optimized_pnl)
        
        if original_dd > 0:
            return (original_dd - optimized_dd) / original_dd
        return 0
    
    def save_model(self, path: str):
        """Save trained model"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        joblib.dump(self.model, path / "stoploss_model.pkl")
        joblib.dump(self.scaler, path / "stoploss_scaler.pkl")
        
        # Save metadata
        metadata = {
            'model_type': self.model_type,
            'feature_columns': self.feature_columns,
            'performance_metrics': self.performance_metrics,
            'trained_at': datetime.now().isoformat()
        }
        
        import json
        with open(path / "stoploss_metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
            
        logger.info(f"Stop loss optimizer saved to {path}")
    
    def load_model(self, path: str):
        """Load trained model"""
        path = Path(path)
        
        self.model = joblib.load(path / "stoploss_model.pkl")
        self.scaler = joblib.load(path / "stoploss_scaler.pkl")
        
        import json
        with open(path / "stoploss_metadata.json", 'r') as f:
            metadata = json.load(f)
            
        self.model_type = metadata['model_type']
        self.feature_columns = metadata['feature_columns']
        self.performance_metrics = metadata['performance_metrics']
        
        logger.info(f"Stop loss optimizer loaded from {path}")