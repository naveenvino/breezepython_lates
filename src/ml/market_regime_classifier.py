"""
Market Regime Classifier
Classifies market conditions to adjust trading strategies dynamically
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sqlalchemy import create_engine, text

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    logging.warning("TA-Lib not installed. Using simplified calculations.")

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    """Market regime types"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    BREAKDOWN = "breakdown"
    CHOPPY = "choppy"

@dataclass
class RegimeAnalysis:
    """Market regime analysis result"""
    current_regime: MarketRegime
    confidence: float
    regime_probabilities: Dict[str, float]
    regime_duration: int  # Days in current regime
    regime_strength: float  # 0-1 strength of regime
    
    # Regime characteristics
    trend_strength: float
    volatility_level: float
    momentum: float
    mean_reversion_tendency: float
    
    # Trading implications
    recommended_strategies: List[str]
    avoid_strategies: List[str]
    position_size_adjustment: float  # Multiplier for position size
    stop_loss_adjustment: float  # Multiplier for stop distance
    
    # Forecast
    regime_change_probability: float
    expected_next_regime: Optional[MarketRegime]
    
    def to_dict(self) -> Dict:
        return {
            'current_regime': self.current_regime.value,
            'confidence': self.confidence,
            'regime_probabilities': self.regime_probabilities,
            'regime_duration': self.regime_duration,
            'regime_strength': self.regime_strength,
            'trend_strength': self.trend_strength,
            'volatility_level': self.volatility_level,
            'momentum': self.momentum,
            'mean_reversion_tendency': self.mean_reversion_tendency,
            'recommended_strategies': self.recommended_strategies,
            'avoid_strategies': self.avoid_strategies,
            'position_size_adjustment': self.position_size_adjustment,
            'stop_loss_adjustment': self.stop_loss_adjustment,
            'regime_change_probability': self.regime_change_probability,
            'expected_next_regime': self.expected_next_regime.value if self.expected_next_regime else None
        }

class MarketRegimeClassifier:
    """Classifies market regime using ML and technical analysis"""
    
    def __init__(self, db_connection_string: str):
        """
        Initialize classifier
        
        Args:
            db_connection_string: Database connection
        """
        self.engine = create_engine(db_connection_string)
        self.model = None
        self.scaler = StandardScaler()
        self.regime_history = []
        
    def classify_current_regime(self, 
                               symbol: str = "NIFTY",
                               lookback_days: int = 20) -> RegimeAnalysis:
        """
        Classify current market regime
        
        Args:
            symbol: Symbol to analyze
            lookback_days: Days to look back for analysis
            
        Returns:
            RegimeAnalysis with current market regime
        """
        # Get recent market data
        df = self._get_market_data(symbol, lookback_days)
        
        if df.empty or len(df) < lookback_days:
            logger.warning("Insufficient data for regime classification")
            return self._default_regime()
        
        # Calculate technical indicators
        indicators = self._calculate_indicators(df)
        
        # Classify regime using multiple methods
        regime_scores = {}
        
        # 1. Trend-based classification
        trend_regime = self._classify_by_trend(indicators)
        regime_scores[trend_regime] = regime_scores.get(trend_regime, 0) + 0.3
        
        # 2. Volatility-based classification
        vol_regime = self._classify_by_volatility(indicators)
        regime_scores[vol_regime] = regime_scores.get(vol_regime, 0) + 0.2
        
        # 3. Pattern-based classification
        pattern_regime = self._classify_by_pattern(df)
        regime_scores[pattern_regime] = regime_scores.get(pattern_regime, 0) + 0.2
        
        # 4. ML-based classification (if model trained)
        if self.model:
            ml_regime = self._classify_by_ml(indicators)
            regime_scores[ml_regime] = regime_scores.get(ml_regime, 0) + 0.3
        
        # Determine final regime
        current_regime = max(regime_scores.items(), key=lambda x: x[1])[0]
        confidence = regime_scores[current_regime]
        
        # Calculate regime characteristics
        characteristics = self._calculate_regime_characteristics(indicators, current_regime)
        
        # Get trading recommendations
        recommendations = self._get_regime_recommendations(current_regime, characteristics)
        
        # Estimate regime change probability
        change_prob = self._estimate_regime_change_probability(indicators, current_regime)
        
        # Predict next regime
        next_regime = self._predict_next_regime(current_regime, indicators)
        
        return RegimeAnalysis(
            current_regime=current_regime,
            confidence=confidence,
            regime_probabilities=regime_scores,
            regime_duration=self._get_regime_duration(current_regime),
            regime_strength=characteristics['strength'],
            trend_strength=characteristics['trend_strength'],
            volatility_level=characteristics['volatility'],
            momentum=characteristics['momentum'],
            mean_reversion_tendency=characteristics['mean_reversion'],
            recommended_strategies=recommendations['recommended'],
            avoid_strategies=recommendations['avoid'],
            position_size_adjustment=recommendations['position_size'],
            stop_loss_adjustment=recommendations['stop_loss'],
            regime_change_probability=change_prob,
            expected_next_regime=next_regime
        )
    
    def _get_market_data(self, symbol: str, lookback_days: int) -> pd.DataFrame:
        """Get recent market data"""
        query = """
        SELECT 
            Timestamp,
            [Open],
            High,
            Low,
            [Close],
            Volume
        FROM NiftyIndexData5Minute
        WHERE Symbol = :symbol
            AND Timestamp >= :from_date
        ORDER BY Timestamp
        """
        
        from_date = datetime.now() - timedelta(days=lookback_days)
        
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params={
                'symbol': symbol,
                'from_date': from_date
            })
        
        if not df.empty:
            df.set_index('Timestamp', inplace=True)
            # Resample to daily for regime analysis
            df_daily = df.resample('D').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()
            return df_daily
        
        return df
    
    def _calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate technical indicators for regime classification"""
        indicators = {}
        
        # Trend indicators
        if TALIB_AVAILABLE:
            indicators['sma_20'] = talib.SMA(df['Close'], timeperiod=20)[-1]
            indicators['sma_50'] = talib.SMA(df['Close'], timeperiod=min(50, len(df)))[-1]
            indicators['ema_20'] = talib.EMA(df['Close'], timeperiod=20)[-1]
        else:
            indicators['sma_20'] = df['Close'].rolling(window=20).mean().iloc[-1] if len(df) >= 20 else df['Close'].mean()
            indicators['sma_50'] = df['Close'].rolling(window=min(50, len(df))).mean().iloc[-1]
            indicators['ema_20'] = df['Close'].ewm(span=20).mean().iloc[-1]
        
        # Momentum indicators
        if TALIB_AVAILABLE:
            indicators['rsi'] = talib.RSI(df['Close'], timeperiod=14)[-1]
            macd, signal, hist = talib.MACD(df['Close'])
            indicators['macd'] = macd[-1] if len(macd) > 0 else 0
            indicators['macd_signal'] = signal[-1] if len(signal) > 0 else 0
            indicators['macd_hist'] = hist[-1] if len(hist) > 0 else 0
        else:
            # Simplified RSI
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            indicators['rsi'] = 100 - (100 / (1 + rs)).iloc[-1] if not rs.empty else 50
            # Simplified MACD
            ema12 = df['Close'].ewm(span=12).mean()
            ema26 = df['Close'].ewm(span=26).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9).mean()
            indicators['macd'] = macd_line.iloc[-1] if not macd_line.empty else 0
            indicators['macd_signal'] = signal_line.iloc[-1] if not signal_line.empty else 0
            indicators['macd_hist'] = indicators['macd'] - indicators['macd_signal']
        
        # Volatility indicators  
        if TALIB_AVAILABLE:
            indicators['atr'] = talib.ATR(df['High'], df['Low'], df['Close'], timeperiod=14)[-1]
            indicators['atr_pct'] = indicators['atr'] / df['Close'].iloc[-1] * 100
            upper, middle, lower = talib.BBANDS(df['Close'], timeperiod=20)
            indicators['bb_width'] = (upper[-1] - lower[-1]) / middle[-1] * 100
            indicators['bb_position'] = (df['Close'].iloc[-1] - lower[-1]) / (upper[-1] - lower[-1])
        else:
            # Simplified ATR
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            indicators['atr'] = tr.rolling(window=14).mean().iloc[-1] if not tr.empty else 0
            indicators['atr_pct'] = indicators['atr'] / df['Close'].iloc[-1] * 100 if df['Close'].iloc[-1] != 0 else 0
            # Simplified Bollinger Bands
            middle = df['Close'].rolling(window=20).mean()
            std = df['Close'].rolling(window=20).std()
            upper = middle + 2 * std
            lower = middle - 2 * std
            if not middle.empty and middle.iloc[-1] != 0:
                indicators['bb_width'] = ((upper.iloc[-1] - lower.iloc[-1]) / middle.iloc[-1] * 100)
                divisor = upper.iloc[-1] - lower.iloc[-1]
                if divisor != 0:
                    indicators['bb_position'] = (df['Close'].iloc[-1] - lower.iloc[-1]) / divisor
                else:
                    indicators['bb_position'] = 0.5
            else:
                indicators['bb_width'] = 0
                indicators['bb_position'] = 0.5
        
        # Volume indicators
        indicators['volume_ratio'] = df['Volume'].iloc[-1] / df['Volume'].mean() if df['Volume'].mean() != 0 else 1
        if TALIB_AVAILABLE:
            indicators['obv'] = talib.OBV(df['Close'], df['Volume'])[-1]
        else:
            # Simplified OBV
            obv = (np.sign(df['Close'].diff()) * df['Volume']).cumsum()
            indicators['obv'] = obv.iloc[-1] if not obv.empty else 0
        
        # Price action
        indicators['price_change_5d'] = (df['Close'].iloc[-1] / df['Close'].iloc[-5] - 1) * 100 if df['Close'].iloc[-5] != 0 else 0
        indicators['price_change_10d'] = (df['Close'].iloc[-1] / df['Close'].iloc[-10] - 1) * 100 if len(df) >= 10 and df['Close'].iloc[-10] != 0 else 0
        indicators['price_change_20d'] = (df['Close'].iloc[-1] / df['Close'].iloc[-20] - 1) * 100 if len(df) >= 20 and df['Close'].iloc[-20] != 0 else 0
        
        # Trend strength
        if TALIB_AVAILABLE:
            adx = talib.ADX(df['High'], df['Low'], df['Close'], timeperiod=14)
            indicators['adx'] = adx[-1] if len(adx) > 0 else 0
        else:
            # Simplified ADX (use absolute price change as proxy)
            indicators['adx'] = min(100, abs(indicators['price_change_20d']) * 2.5)
        
        # Support/Resistance
        indicators['distance_from_high'] = (df['High'].max() - df['Close'][-1]) / df['Close'][-1] * 100
        indicators['distance_from_low'] = (df['Close'][-1] - df['Low'].min()) / df['Close'][-1] * 100
        
        # Clean NaN values - replace with 0 or sensible defaults
        for key, value in indicators.items():
            if isinstance(value, (float, np.float64, np.float32)) and np.isnan(value):
                # Use sensible defaults based on indicator type
                if 'rsi' in key:
                    indicators[key] = 50  # Neutral RSI
                elif 'ratio' in key:
                    indicators[key] = 1.0  # Neutral ratio
                elif 'change' in key or 'return' in key:
                    indicators[key] = 0.0  # No change
                else:
                    indicators[key] = 0.0  # Default to 0
        
        return indicators
    
    def _classify_by_trend(self, indicators: Dict) -> MarketRegime:
        """Classify regime based on trend indicators"""
        # Strong uptrend
        if (indicators['sma_20'] > indicators['sma_50'] and
            indicators['price_change_20d'] > 5 and
            indicators['adx'] > 25):
            return MarketRegime.TRENDING_UP
        
        # Strong downtrend
        elif (indicators['sma_20'] < indicators['sma_50'] and
              indicators['price_change_20d'] < -5 and
              indicators['adx'] > 25):
            return MarketRegime.TRENDING_DOWN
        
        # Range bound
        elif (abs(indicators['price_change_20d']) < 3 and
              indicators['adx'] < 20):
            return MarketRegime.RANGE_BOUND
        
        # Breakout
        elif (indicators['bb_position'] > 1.0 and
              indicators['volume_ratio'] > 1.5):
            return MarketRegime.BREAKOUT
        
        # Breakdown
        elif (indicators['bb_position'] < 0.0 and
              indicators['volume_ratio'] > 1.5):
            return MarketRegime.BREAKDOWN
        
        else:
            return MarketRegime.CHOPPY
    
    def _classify_by_volatility(self, indicators: Dict) -> MarketRegime:
        """Classify regime based on volatility"""
        if indicators['atr_pct'] > 2.5:
            return MarketRegime.HIGH_VOLATILITY
        elif indicators['atr_pct'] < 1.0:
            return MarketRegime.LOW_VOLATILITY
        else:
            # Check trend within normal volatility
            if indicators['price_change_10d'] > 3:
                return MarketRegime.TRENDING_UP
            elif indicators['price_change_10d'] < -3:
                return MarketRegime.TRENDING_DOWN
            else:
                return MarketRegime.RANGE_BOUND
    
    def _classify_by_pattern(self, df: pd.DataFrame) -> MarketRegime:
        """Classify regime based on price patterns"""
        # Simple pattern recognition
        closes = df['Close'].values[-10:]  # Last 10 days
        
        if len(closes) < 10:
            return MarketRegime.CHOPPY
        
        # Check for consistent trend
        ups = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
        downs = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i-1])
        
        if ups > 7:
            return MarketRegime.TRENDING_UP
        elif downs > 7:
            return MarketRegime.TRENDING_DOWN
        elif abs(ups - downs) <= 2:
            return MarketRegime.RANGE_BOUND
        else:
            return MarketRegime.CHOPPY
    
    def _classify_by_ml(self, indicators: Dict) -> MarketRegime:
        """Classify using ML model"""
        if not self.model:
            return MarketRegime.CHOPPY
        
        # Prepare features
        features = np.array([
            indicators['rsi'],
            indicators['macd_hist'],
            indicators['atr_pct'],
            indicators['adx'],
            indicators['bb_position'],
            indicators['price_change_5d'],
            indicators['price_change_10d'],
            indicators['volume_ratio']
        ]).reshape(1, -1)
        
        # Scale features
        features_scaled = self.scaler.transform(features)
        
        # Predict
        prediction = self.model.predict(features_scaled)[0]
        
        # Map to regime
        regime_map = {
            0: MarketRegime.TRENDING_UP,
            1: MarketRegime.TRENDING_DOWN,
            2: MarketRegime.RANGE_BOUND,
            3: MarketRegime.HIGH_VOLATILITY,
            4: MarketRegime.CHOPPY
        }
        
        return regime_map.get(prediction, MarketRegime.CHOPPY)
    
    def _calculate_regime_characteristics(self, 
                                         indicators: Dict,
                                         regime: MarketRegime) -> Dict:
        """Calculate detailed regime characteristics"""
        characteristics = {}
        
        # Trend strength (0-1)
        characteristics['trend_strength'] = min(1.0, indicators['adx'] / 50)
        
        # Volatility level (0-1)
        characteristics['volatility'] = min(1.0, indicators['atr_pct'] / 5)
        
        # Momentum (0-1)
        rsi_momentum = abs(indicators['rsi'] - 50) / 50
        macd_momentum = min(1.0, abs(indicators['macd_hist']) / 100)
        characteristics['momentum'] = (rsi_momentum + macd_momentum) / 2
        
        # Mean reversion tendency (0-1)
        bb_extreme = abs(indicators['bb_position'] - 0.5) * 2
        characteristics['mean_reversion'] = bb_extreme if bb_extreme > 0.8 else 0
        
        # Regime strength
        if regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            characteristics['strength'] = characteristics['trend_strength']
        elif regime in [MarketRegime.HIGH_VOLATILITY, MarketRegime.LOW_VOLATILITY]:
            characteristics['strength'] = abs(characteristics['volatility'] - 0.5) * 2
        else:
            characteristics['strength'] = 1 - characteristics['trend_strength']
        
        return characteristics
    
    def _get_regime_recommendations(self, 
                                   regime: MarketRegime,
                                   characteristics: Dict) -> Dict:
        """Get trading recommendations for regime"""
        recommendations = {
            'recommended': [],
            'avoid': [],
            'position_size': 1.0,
            'stop_loss': 1.0
        }
        
        if regime == MarketRegime.TRENDING_UP:
            recommendations['recommended'] = ['S1', 'S2', 'S4', 'S7']  # Bullish signals
            recommendations['avoid'] = ['S3', 'S5', 'S6', 'S8']  # Bearish signals
            recommendations['position_size'] = 1.2  # Increase size in trend
            recommendations['stop_loss'] = 1.2  # Wider stops in trend
            
        elif regime == MarketRegime.TRENDING_DOWN:
            recommendations['recommended'] = ['S3', 'S5', 'S6', 'S8']  # Bearish signals
            recommendations['avoid'] = ['S1', 'S2', 'S4', 'S7']  # Bullish signals
            recommendations['position_size'] = 1.2
            recommendations['stop_loss'] = 1.2
            
        elif regime == MarketRegime.RANGE_BOUND:
            recommendations['recommended'] = ['S2', 'S3']  # Range trading signals
            recommendations['avoid'] = ['S7', 'S8']  # Breakout signals
            recommendations['position_size'] = 1.0
            recommendations['stop_loss'] = 0.8  # Tighter stops in range
            
        elif regime == MarketRegime.HIGH_VOLATILITY:
            recommendations['recommended'] = []  # Avoid new trades
            recommendations['avoid'] = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']
            recommendations['position_size'] = 0.5  # Reduce size
            recommendations['stop_loss'] = 1.5  # Wider stops
            
        elif regime == MarketRegime.LOW_VOLATILITY:
            recommendations['recommended'] = ['S1', 'S2', 'S3', 'S4']  # Safe signals
            recommendations['avoid'] = []
            recommendations['position_size'] = 1.3  # Can increase size
            recommendations['stop_loss'] = 0.7  # Tighter stops
            
        elif regime == MarketRegime.BREAKOUT:
            recommendations['recommended'] = ['S7']  # Breakout signal
            recommendations['avoid'] = ['S2', 'S3']  # Range signals
            recommendations['position_size'] = 0.8  # Careful with size
            recommendations['stop_loss'] = 1.0
            
        elif regime == MarketRegime.BREAKDOWN:
            recommendations['recommended'] = ['S8']  # Breakdown signal
            recommendations['avoid'] = ['S1', 'S2']  # Support signals
            recommendations['position_size'] = 0.8
            recommendations['stop_loss'] = 1.0
            
        else:  # CHOPPY
            recommendations['recommended'] = []  # Avoid trading
            recommendations['avoid'] = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']
            recommendations['position_size'] = 0.5
            recommendations['stop_loss'] = 1.2
        
        return recommendations
    
    def _get_regime_duration(self, current_regime: MarketRegime) -> int:
        """Get duration of current regime in days"""
        # Track regime history
        if not self.regime_history or self.regime_history[-1] != current_regime:
            self.regime_history.append(current_regime)
            return 1
        
        # Count consecutive days in same regime
        duration = 1
        for regime in reversed(self.regime_history[:-1]):
            if regime == current_regime:
                duration += 1
            else:
                break
        
        return duration
    
    def _estimate_regime_change_probability(self, 
                                           indicators: Dict,
                                           current_regime: MarketRegime) -> float:
        """Estimate probability of regime change"""
        change_prob = 0.0
        
        # Trend exhaustion signals
        if current_regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            # RSI divergence
            if (current_regime == MarketRegime.TRENDING_UP and indicators['rsi'] > 70) or \
               (current_regime == MarketRegime.TRENDING_DOWN and indicators['rsi'] < 30):
                change_prob += 0.3
            
            # Trend weakening
            if indicators['adx'] < 20:
                change_prob += 0.2
        
        # Volatility extremes
        if regime == MarketRegime.HIGH_VOLATILITY and indicators['atr_pct'] < 2.0:
            change_prob += 0.4
        elif current_regime == MarketRegime.LOW_VOLATILITY and indicators['atr_pct'] > 1.5:
            change_prob += 0.4
        
        # Range breakout signals
        if current_regime == MarketRegime.RANGE_BOUND:
            if indicators['bb_position'] > 0.9 or indicators['bb_position'] < 0.1:
                change_prob += 0.5
        
        # Time-based (regimes typically last 10-20 days)
        duration = self._get_regime_duration(current_regime)
        if duration > 20:
            change_prob += 0.3
        elif duration > 15:
            change_prob += 0.2
        
        return min(1.0, change_prob)
    
    def _predict_next_regime(self, 
                           current_regime: MarketRegime,
                           indicators: Dict) -> Optional[MarketRegime]:
        """Predict most likely next regime"""
        # Regime transition probabilities
        transitions = {
            MarketRegime.TRENDING_UP: [MarketRegime.RANGE_BOUND, MarketRegime.HIGH_VOLATILITY],
            MarketRegime.TRENDING_DOWN: [MarketRegime.RANGE_BOUND, MarketRegime.HIGH_VOLATILITY],
            MarketRegime.RANGE_BOUND: [MarketRegime.BREAKOUT, MarketRegime.BREAKDOWN],
            MarketRegime.HIGH_VOLATILITY: [MarketRegime.TRENDING_DOWN, MarketRegime.RANGE_BOUND],
            MarketRegime.LOW_VOLATILITY: [MarketRegime.BREAKOUT, MarketRegime.HIGH_VOLATILITY],
            MarketRegime.BREAKOUT: [MarketRegime.TRENDING_UP, MarketRegime.HIGH_VOLATILITY],
            MarketRegime.BREAKDOWN: [MarketRegime.TRENDING_DOWN, MarketRegime.HIGH_VOLATILITY],
            MarketRegime.CHOPPY: [MarketRegime.RANGE_BOUND, MarketRegime.TRENDING_UP]
        }
        
        possible_next = transitions.get(current_regime, [MarketRegime.CHOPPY])
        
        # Use indicators to refine prediction
        if indicators['adx'] > 30:
            # Trend likely to continue or start
            if indicators['macd_hist'] > 0:
                return MarketRegime.TRENDING_UP
            else:
                return MarketRegime.TRENDING_DOWN
        elif indicators['atr_pct'] > 2.5:
            return MarketRegime.HIGH_VOLATILITY
        else:
            return possible_next[0] if possible_next else None
    
    def _default_regime(self) -> RegimeAnalysis:
        """Return default regime when classification fails"""
        return RegimeAnalysis(
            current_regime=MarketRegime.CHOPPY,
            confidence=0.5,
            regime_probabilities={'choppy': 0.5},
            regime_duration=1,
            regime_strength=0.5,
            trend_strength=0.5,
            volatility_level=0.5,
            momentum=0.5,
            mean_reversion_tendency=0.5,
            recommended_strategies=[],
            avoid_strategies=['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8'],
            position_size_adjustment=0.5,
            stop_loss_adjustment=1.2,
            regime_change_probability=0.5,
            expected_next_regime=None
        )
    
    def train_classifier(self, 
                        from_date: datetime,
                        to_date: datetime):
        """
        Train ML classifier on historical regime data
        
        Args:
            from_date: Training start date
            to_date: Training end date
        """
        # This would require labeled historical regime data
        # For now, using unsupervised clustering
        
        logger.info("Training regime classifier...")
        
        # Get historical data
        df = self._get_training_data(from_date, to_date)
        
        if df.empty:
            logger.warning("No training data available")
            return
        
        # Extract features
        features = []
        for i in range(20, len(df)):
            window = df.iloc[i-20:i]
            indicators = self._calculate_indicators(window)
            features.append([
                indicators['rsi'],
                indicators['macd_hist'],
                indicators['atr_pct'],
                indicators['adx'],
                indicators['bb_position'],
                indicators['price_change_5d'],
                indicators['price_change_10d'],
                indicators['volume_ratio']
            ])
        
        X = np.array(features)
        
        # Handle NaN values - replace with median
        if np.isnan(X).any():
            logger.warning("NaN values found in features, replacing with median")
            from sklearn.impute import SimpleImputer
            imputer = SimpleImputer(strategy='median')
            X = imputer.fit_transform(X)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Cluster into regimes
        kmeans = KMeans(n_clusters=5, random_state=42)
        labels = kmeans.fit_predict(X_scaled)
        
        # Train classifier
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X_scaled, labels)
        
        logger.info("Regime classifier trained successfully")
    
    def _get_training_data(self, from_date: datetime, to_date: datetime) -> pd.DataFrame:
        """Get historical data for training"""
        query = """
        SELECT 
            Timestamp,
            [Open],
            High,
            Low,
            [Close],
            Volume
        FROM NiftyIndexData5Minute
        WHERE Timestamp >= :from_date
            AND Timestamp <= :to_date
        ORDER BY Timestamp
        """
        
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params={
                'from_date': from_date,
                'to_date': to_date
            })
        
        if not df.empty:
            df.set_index('Timestamp', inplace=True)
            # Resample to daily
            df_daily = df.resample('D').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()
            return df_daily
        
        return df