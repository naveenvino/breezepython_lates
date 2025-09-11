"""
Feature Engineering Pipeline for ML Trading Models
Generates features from market data for signal prediction and optimization
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

# Try to import talib, but make it optional
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False

logger = logging.getLogger(__name__)

class FeatureEngineer:
    """Feature engineering for trading ML models"""
    
    def __init__(self):
        """Initialize feature engineer"""
        self.feature_columns = []
        
    def generate_features(self, 
                         df: pd.DataFrame,
                         include_ta: bool = True,
                         include_market_structure: bool = True,
                         include_temporal: bool = True) -> pd.DataFrame:
        """
        Generate all features from OHLCV data
        
        Args:
            df: DataFrame with OHLC columns
            include_ta: Include technical indicators
            include_market_structure: Include market microstructure features
            include_temporal: Include time-based features
            
        Returns:
            DataFrame with additional feature columns
        """
        df = df.copy()
        
        # Ensure we have required columns
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"DataFrame must contain columns: {required_cols}")
            
        # Price-based features
        df = self._add_price_features(df)
        
        # Technical indicators (works with or without talib)
        if include_ta:
            df = self._add_technical_indicators(df)
            
        # Market microstructure  
        if include_market_structure:
            df = self._add_market_structure_features(df)
            
        # Temporal features
        if include_temporal and 'Timestamp' in df.columns:
            df = self._add_temporal_features(df)
            
        # Clean up
        df = df.fillna(method='ffill').fillna(0)
        
        # Store feature columns
        self.feature_columns = [col for col in df.columns 
                               if col not in ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
        
        return df
        
    def _add_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add price-based features"""
        # Returns
        df['returns'] = df['Close'].pct_change()
        df['log_returns'] = np.log(df['Close'] / df['Close'].shift(1))
        
        # Price ratios
        df['high_low_ratio'] = df['High'] / df['Low']
        df['close_open_ratio'] = df['Close'] / df['Open']
        
        # Price position in range
        df['price_position'] = (df['Close'] - df['Low']) / (df['High'] - df['Low'] + 1e-10)
        
        # Volatility
        df['volatility'] = df['returns'].rolling(20).std()
        df['volatility_5'] = df['returns'].rolling(5).std()
        
        # Price changes
        for period in [1, 5, 10, 20]:
            df[f'price_change_{period}'] = df['Close'].pct_change(period)
            
        return df
        
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators using pandas (no talib required)"""
        # Moving averages
        df['sma_5'] = df['Close'].rolling(5).mean()
        df['sma_10'] = df['Close'].rolling(10).mean()
        df['sma_20'] = df['Close'].rolling(20).mean()
        
        # EMA
        df['ema_5'] = df['Close'].ewm(span=5, adjust=False).mean()
        df['ema_10'] = df['Close'].ewm(span=10, adjust=False).mean()
        df['ema_20'] = df['Close'].ewm(span=20, adjust=False).mean()
        
        # RSI (pandas implementation)
        df['rsi'] = self._calculate_rsi(df['Close'], 14)
        df['rsi_5'] = self._calculate_rsi(df['Close'], 5)
        
        # MACD (pandas implementation)
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp1 - exp2
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # Bollinger Bands
        bb_period = 20
        bb_std = 2
        df['bb_middle'] = df['Close'].rolling(bb_period).mean()
        bb_std_dev = df['Close'].rolling(bb_period).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * bb_std_dev)
        df['bb_lower'] = df['bb_middle'] - (bb_std * bb_std_dev)
        df['bb_width'] = df['bb_upper'] - df['bb_lower']
        df['bb_position'] = (df['Close'] - df['bb_lower']) / (df['bb_width'] + 1e-10)
        
        # ATR (Average True Range)
        df['atr'] = self._calculate_atr(df, 14)
        
        # Stochastic Oscillator
        df['stoch_k'], df['stoch_d'] = self._calculate_stochastic(df, 14, 3)
        
        # OBV (On Balance Volume)
        df['obv'] = self._calculate_obv(df)
        
        # Money Flow Index
        df['mfi'] = self._calculate_mfi(df, 14)
        
        # ADX (Average Directional Index)
        df['adx'] = self._calculate_adx(df, 14)
        
        return df
        
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI without talib"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return rsi
        
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate ATR without talib"""
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(period).mean()
        return atr
        
    def _calculate_stochastic(self, df: pd.DataFrame, period: int = 14, smooth: int = 3) -> Tuple[pd.Series, pd.Series]:
        """Calculate Stochastic Oscillator without talib"""
        low_min = df['Low'].rolling(period).min()
        high_max = df['High'].rolling(period).max()
        k_percent = 100 * ((df['Close'] - low_min) / (high_max - low_min + 1e-10))
        d_percent = k_percent.rolling(smooth).mean()
        return k_percent, d_percent
        
    def _calculate_obv(self, df: pd.DataFrame) -> pd.Series:
        """Calculate OBV without talib"""
        obv = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
        return obv
        
    def _calculate_mfi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Money Flow Index without talib"""
        typical_price = (df['High'] + df['Low'] + df['Close']) / 3
        money_flow = typical_price * df['Volume']
        
        positive_flow = pd.Series(0, index=df.index)
        negative_flow = pd.Series(0, index=df.index)
        
        # Determine positive and negative money flow
        mask = typical_price > typical_price.shift(1)
        positive_flow[mask] = money_flow[mask]
        negative_flow[~mask] = money_flow[~mask]
        
        positive_mf = positive_flow.rolling(period).sum()
        negative_mf = negative_flow.rolling(period).sum()
        
        mfi = 100 - (100 / (1 + positive_mf / (negative_mf + 1e-10)))
        return mfi
        
    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate ADX without talib (simplified)"""
        # Simplified ADX calculation
        high_diff = df['High'].diff()
        low_diff = -df['Low'].diff()
        
        pos_dm = pd.Series(0, index=df.index)
        neg_dm = pd.Series(0, index=df.index)
        
        pos_dm[(high_diff > low_diff) & (high_diff > 0)] = high_diff
        neg_dm[(low_diff > high_diff) & (low_diff > 0)] = low_diff
        
        atr = self._calculate_atr(df, period)
        
        pos_di = 100 * (pos_dm.rolling(period).mean() / (atr + 1e-10))
        neg_di = 100 * (neg_dm.rolling(period).mean() / (atr + 1e-10))
        
        dx = 100 * np.abs(pos_di - neg_di) / (pos_di + neg_di + 1e-10)
        adx = dx.rolling(period).mean()
        
        return adx
        
    def _add_market_structure_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market microstructure features"""
        # Volume features
        df['volume_ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()
        df['volume_change'] = df['Volume'].pct_change()
        
        # Spread
        df['spread'] = df['High'] - df['Low']
        df['spread_pct'] = df['spread'] / df['Close']
        
        # Liquidity proxy
        df['liquidity'] = df['Volume'] * df['Close']
        
        # Order flow imbalance proxy
        df['order_imbalance'] = (df['Close'] - df['Open']) / (df['High'] - df['Low'] + 1e-10)
        
        # Price efficiency
        df['price_efficiency'] = np.abs(df['Close'] - df['Open']) / (df['High'] - df['Low'] + 1e-10)
        
        return df
        
    def _add_temporal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add time-based features"""
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        
        # Time of day
        df['hour'] = df['Timestamp'].dt.hour
        df['minute'] = df['Timestamp'].dt.minute
        df['time_of_day'] = df['hour'] + df['minute'] / 60
        
        # Day of week
        df['day_of_week'] = df['Timestamp'].dt.dayofweek
        df['is_monday'] = (df['day_of_week'] == 0).astype(int)
        df['is_friday'] = (df['day_of_week'] == 4).astype(int)
        
        # Trading session
        df['is_morning'] = ((df['hour'] >= 9) & (df['hour'] < 12)).astype(int)
        df['is_afternoon'] = ((df['hour'] >= 12) & (df['hour'] < 15)).astype(int)
        df['is_closing'] = ((df['hour'] >= 15) & (df['hour'] < 16)).astype(int)
        
        # Month and quarter
        df['month'] = df['Timestamp'].dt.month
        df['quarter'] = df['Timestamp'].dt.quarter
        
        # Expiry week (Tuesday is expiry)
        df['days_to_thursday'] = (3 - df['day_of_week']) % 7
        df['is_expiry_week'] = (df['days_to_thursday'] <= 3).astype(int)
        
        return df
        
    def create_target_variables(self, df: pd.DataFrame, forward_periods: List[int] = [5, 10, 20]) -> pd.DataFrame:
        """Create target variables for ML training"""
        for period in forward_periods:
            # Future return
            df[f'future_return_{period}'] = df['Close'].shift(-period) / df['Close'] - 1
            
            # Binary target (up/down)
            df[f'target_up_{period}'] = (df[f'future_return_{period}'] > 0).astype(int)
            
            # Multi-class target
            df[f'target_class_{period}'] = pd.cut(
                df[f'future_return_{period}'],
                bins=[-np.inf, -0.01, 0.01, np.inf],
                labels=['down', 'neutral', 'up']
            )
            
        return df
        
    def create_signal_features(self, df: pd.DataFrame, signal_type: str) -> pd.DataFrame:
        """Add signal-specific features"""
        # Add signal indicator
        df[f'signal_{signal_type}'] = 1
        
        # Signal-specific features based on type
        if signal_type in ['S1', 'S2', 'S4', 'S7']:  # Bullish signals
            df['bullish_strength'] = df['close_open_ratio'] * df['volume_ratio']
            df['support_distance'] = (df['Close'] - df['sma_20']) / df['Close']
            
        elif signal_type in ['S3', 'S5', 'S6', 'S8']:  # Bearish signals
            df['bearish_strength'] = (1 / df['close_open_ratio']) * df['volume_ratio']
            df['resistance_distance'] = (df['sma_20'] - df['Close']) / df['Close']
            
        return df
        
    def prepare_ml_dataset(self, 
                          df: pd.DataFrame,
                          target_col: str,
                          test_size: float = 0.2,
                          val_size: float = 0.1) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Prepare dataset for ML training"""
        # Remove NaN values
        df = df.dropna(subset=[target_col])
        
        # Split by time
        n = len(df)
        train_end = int(n * (1 - test_size - val_size))
        val_end = int(n * (1 - test_size))
        
        train_df = df.iloc[:train_end]
        val_df = df.iloc[train_end:val_end]
        test_df = df.iloc[val_end:]
        
        return train_df, val_df, test_df
        
    def scale_features(self, 
                      train_df: pd.DataFrame,
                      val_df: pd.DataFrame,
                      test_df: pd.DataFrame,
                      feature_cols: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Scale features for ML"""
        from sklearn.preprocessing import RobustScaler
        
        scaler = RobustScaler()
        
        # Fit on training data
        train_df[feature_cols] = scaler.fit_transform(train_df[feature_cols])
        
        # Transform validation and test
        val_df[feature_cols] = scaler.transform(val_df[feature_cols])
        test_df[feature_cols] = scaler.transform(test_df[feature_cols])
        
        return train_df, val_df, test_df