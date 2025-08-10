"""
Exit Pattern Analyzer
Discovers optimal exit patterns from historical trades
Identifies day-specific and time-specific exit opportunities
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
from sqlalchemy import create_engine, text
import json
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

@dataclass 
class ExitPattern:
    """Represents an exit pattern discovered from data"""
    pattern_id: str
    signal_type: str
    pattern_type: str  # 'time_based', 'profit_based', 'volatility_based', 'day_based'
    
    # Pattern conditions
    day_of_week: Optional[str]  # Monday, Tuesday, Wednesday, Thursday
    hour_of_day: Optional[int]  # 9-15 (market hours)
    profit_threshold_pct: Optional[float]  # Exit when profit reaches X%
    time_in_trade_hours: Optional[float]  # Exit after X hours
    volatility_condition: Optional[str]  # 'high', 'low', 'increasing', 'decreasing'
    
    # Pattern performance
    occurrences: int
    avg_profit_captured: float
    success_rate: float  # % of times this pattern led to good exit
    avg_profit_left_on_table: float  # Average profit missed by exiting here
    
    # Recommendations
    confidence_score: float  # 0-1 confidence in this pattern
    action: str  # 'full_exit', 'partial_exit', 'trail_stop', 'hold'
    exit_percentage: float  # % of position to exit
    
    def to_dict(self) -> Dict:
        return {
            'pattern_id': self.pattern_id,
            'signal_type': self.signal_type,
            'pattern_type': self.pattern_type,
            'day_of_week': self.day_of_week,
            'hour_of_day': self.hour_of_day,
            'profit_threshold_pct': self.profit_threshold_pct,
            'time_in_trade_hours': self.time_in_trade_hours,
            'volatility_condition': self.volatility_condition,
            'occurrences': self.occurrences,
            'avg_profit_captured': self.avg_profit_captured,
            'success_rate': self.success_rate,
            'avg_profit_left_on_table': self.avg_profit_left_on_table,
            'confidence_score': self.confidence_score,
            'action': self.action,
            'exit_percentage': self.exit_percentage
        }

class ExitPatternAnalyzer:
    """Discovers and analyzes exit patterns from historical trades"""
    
    def __init__(self, db_connection_string: str):
        """
        Initialize analyzer
        
        Args:
            db_connection_string: Database connection string
        """
        self.engine = create_engine(db_connection_string)
        self.patterns = {}
        
    def discover_patterns(self, 
                         from_date: datetime,
                         to_date: datetime,
                         min_pattern_occurrences: int = 2) -> List[ExitPattern]:
        """
        Discover exit patterns from historical trades
        
        Args:
            from_date: Start date for analysis
            to_date: End date for analysis
            min_pattern_occurrences: Minimum occurrences for pattern to be valid
            
        Returns:
            List of discovered exit patterns
        """
        patterns = []
        
        # Get lifecycle analysis data
        lifecycle_data = self._get_lifecycle_data(from_date, to_date)
        
        if lifecycle_data.empty:
            logger.warning("No lifecycle data available for pattern discovery")
            return patterns
        
        # Discover different types of patterns
        patterns.extend(self._discover_time_based_patterns(lifecycle_data))
        patterns.extend(self._discover_profit_based_patterns(lifecycle_data))
        patterns.extend(self._discover_day_specific_patterns(lifecycle_data))
        patterns.extend(self._discover_volatility_patterns(lifecycle_data))
        patterns.extend(self._discover_ml_clusters(lifecycle_data))
        
        # Filter by minimum occurrences
        patterns = [p for p in patterns if p.occurrences >= min_pattern_occurrences]
        
        # Sort by confidence score
        patterns.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return patterns
    
    def _get_lifecycle_data(self, 
                           from_date: datetime,
                           to_date: datetime) -> pd.DataFrame:
        """
        Get trade lifecycle data from database
        
        Args:
            from_date: Start date
            to_date: End date
            
        Returns:
            DataFrame with lifecycle metrics
        """
        query = """
        SELECT 
            t.Id,
            t.SignalType,
            t.EntryTime,
            t.ExitTime,
            t.TotalPnL,
            t.IndexPriceAtEntry,
            t.IndexPriceAtExit,
            t.StopLossPrice,
            t.ExitReason,
            DATENAME(dw, t.EntryTime) as EntryDay,
            DATENAME(dw, t.ExitTime) as ExitDay,
            DATEPART(hour, t.EntryTime) as EntryHour,
            DATEPART(hour, t.ExitTime) as ExitHour,
            DATEDIFF(hour, t.EntryTime, t.ExitTime) as HoldingHours,
            t.TotalPnL as MaxProfit,
            DATEDIFF(hour, t.EntryTime, t.ExitTime) as TimeToMaxProfitHours,
            CASE WHEN t.TotalPnL > 0 THEN 1.0 ELSE 0.0 END as ProfitCaptureRatio,
            0 as ProfitDecayFromPeak,
            DATENAME(dw, t.ExitTime) as BestExitDay,
            DATEPART(hour, t.ExitTime) as BestExitHour,
            0 as MaxDeltaExposure,
            0 as AvgThetaCollected
        FROM BacktestTrades t
        WHERE t.EntryTime >= :from_date
            AND t.EntryTime <= :to_date
            AND t.TotalPnL IS NOT NULL
        """
        
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params={
                'from_date': from_date,
                'to_date': to_date
            })
            
        return df
    
    def _discover_time_based_patterns(self, df: pd.DataFrame) -> List[ExitPattern]:
        """
        Discover patterns based on time in trade
        
        Args:
            df: Lifecycle data
            
        Returns:
            List of time-based patterns
        """
        patterns = []
        
        for signal_type in df['SignalType'].unique():
            signal_df = df[df['SignalType'] == signal_type]
            
            if signal_df.empty:
                continue
            
            # Analyze exits by hour of day
            for hour in range(9, 16):  # Market hours
                hour_exits = signal_df[signal_df['ExitHour'] == hour]
                
                if len(hour_exits) >= 2:
                    avg_capture = hour_exits['ProfitCaptureRatio'].mean() if 'ProfitCaptureRatio' in hour_exits else 0
                    avg_pnl = hour_exits['TotalPnL'].mean()
                    
                    # Calculate profit left on table
                    avg_max = hour_exits['MaxProfit'].mean() if 'MaxProfit' in hour_exits else avg_pnl
                    profit_left = avg_max - avg_pnl if avg_max > avg_pnl else 0
                    
                    pattern = ExitPattern(
                        pattern_id=f"{signal_type}_HOUR_{hour}",
                        signal_type=signal_type,
                        pattern_type='time_based',
                        hour_of_day=hour,
                        day_of_week=None,
                        profit_threshold_pct=None,
                        time_in_trade_hours=None,
                        volatility_condition=None,
                        occurrences=len(hour_exits),
                        avg_profit_captured=avg_pnl,
                        success_rate=len(hour_exits[hour_exits['TotalPnL'] > 0]) / len(hour_exits),
                        avg_profit_left_on_table=profit_left,
                        confidence_score=min(0.5 + (avg_capture * 0.5), 1.0) if avg_capture else 0.5,
                        action='partial_exit' if hour < 14 else 'full_exit',
                        exit_percentage=50 if hour < 14 else 100
                    )
                    
                    patterns.append(pattern)
        
        return patterns
    
    def _discover_profit_based_patterns(self, df: pd.DataFrame) -> List[ExitPattern]:
        """
        Discover patterns based on profit thresholds
        
        Args:
            df: Lifecycle data
            
        Returns:
            List of profit-based patterns
        """
        patterns = []
        
        for signal_type in df['SignalType'].unique():
            signal_df = df[df['SignalType'] == signal_type]
            
            if signal_df.empty or 'MaxProfit' not in signal_df.columns:
                continue
            
            # Define profit thresholds to analyze
            profit_thresholds = [0.5, 0.7, 0.8, 0.9]  # 50%, 70%, 80%, 90% of max profit
            
            for threshold in profit_thresholds:
                # Trades that captured at least this threshold
                high_capture = signal_df[signal_df['ProfitCaptureRatio'] >= threshold] if 'ProfitCaptureRatio' in signal_df else pd.DataFrame()
                
                if len(high_capture) >= 2:
                    avg_pnl = high_capture['TotalPnL'].mean()
                    avg_hours = high_capture['HoldingHours'].mean() if 'HoldingHours' in high_capture else 0
                    
                    pattern = ExitPattern(
                        pattern_id=f"{signal_type}_PROFIT_{int(threshold*100)}",
                        signal_type=signal_type,
                        pattern_type='profit_based',
                        profit_threshold_pct=threshold * 100,
                        time_in_trade_hours=avg_hours,
                        day_of_week=None,
                        hour_of_day=None,
                        volatility_condition=None,
                        occurrences=len(high_capture),
                        avg_profit_captured=avg_pnl,
                        success_rate=1.0,  # By definition, these captured the threshold
                        avg_profit_left_on_table=(1 - threshold) * avg_pnl,
                        confidence_score=0.7 + (threshold * 0.3),
                        action='full_exit' if threshold >= 0.8 else 'partial_exit',
                        exit_percentage=100 if threshold >= 0.8 else 75
                    )
                    
                    patterns.append(pattern)
        
        return patterns
    
    def _discover_day_specific_patterns(self, df: pd.DataFrame) -> List[ExitPattern]:
        """
        Discover patterns specific to days of the week
        
        Args:
            df: Lifecycle data
            
        Returns:
            List of day-specific patterns
        """
        patterns = []
        
        # Special patterns for each day
        day_patterns = {
            'Monday': {'action': 'hold', 'exit_pct': 0, 'reason': 'Fresh weekly levels'},
            'Tuesday': {'action': 'partial_exit', 'exit_pct': 25, 'reason': 'Trending market opportunity'},
            'Wednesday': {'action': 'partial_exit', 'exit_pct': 50, 'reason': 'Peak profit day'},
            'Thursday': {'action': 'full_exit', 'exit_pct': 100, 'reason': 'Expiry day'}
        }
        
        for signal_type in df['SignalType'].unique():
            signal_df = df[df['SignalType'] == signal_type]
            
            for day, day_config in day_patterns.items():
                day_exits = signal_df[signal_df['ExitDay'] == day]
                
                if len(day_exits) >= 1:
                    avg_pnl = day_exits['TotalPnL'].mean()
                    
                    # Wednesday morning special pattern
                    if day == 'Wednesday':
                        wed_morning = day_exits[day_exits['ExitHour'] <= 12]
                        if len(wed_morning) > 0:
                            wed_morning_pnl = wed_morning['TotalPnL'].mean()
                            
                            pattern = ExitPattern(
                                pattern_id=f"{signal_type}_WED_MORNING",
                                signal_type=signal_type,
                                pattern_type='day_based',
                                day_of_week='Wednesday',
                                hour_of_day=11,
                                profit_threshold_pct=None,
                                time_in_trade_hours=48,  # ~2 days
                                volatility_condition=None,
                                occurrences=len(wed_morning),
                                avg_profit_captured=wed_morning_pnl,
                                success_rate=len(wed_morning[wed_morning['TotalPnL'] > 0]) / len(wed_morning),
                                avg_profit_left_on_table=0,
                                confidence_score=0.8,
                                action='partial_exit',
                                exit_percentage=50
                            )
                            patterns.append(pattern)
                    
                    # General day pattern
                    pattern = ExitPattern(
                        pattern_id=f"{signal_type}_{day.upper()}",
                        signal_type=signal_type,
                        pattern_type='day_based',
                        day_of_week=day,
                        hour_of_day=15 if day == 'Thursday' else None,
                        profit_threshold_pct=None,
                        time_in_trade_hours=None,
                        volatility_condition=None,
                        occurrences=len(day_exits),
                        avg_profit_captured=avg_pnl,
                        success_rate=len(day_exits[day_exits['TotalPnL'] > 0]) / len(day_exits) if len(day_exits) > 0 else 0,
                        avg_profit_left_on_table=0,
                        confidence_score=0.9 if day == 'Thursday' else 0.6,
                        action=day_config['action'],
                        exit_percentage=day_config['exit_pct']
                    )
                    
                    patterns.append(pattern)
        
        return patterns
    
    def _discover_volatility_patterns(self, df: pd.DataFrame) -> List[ExitPattern]:
        """
        Discover patterns based on volatility conditions
        
        Args:
            df: Lifecycle data
            
        Returns:
            List of volatility-based patterns
        """
        patterns = []
        
        # This would require additional volatility data
        # For now, using Delta exposure as proxy for volatility risk
        
        if 'MaxDeltaExposure' not in df.columns:
            return patterns
        
        for signal_type in df['SignalType'].unique():
            signal_df = df[df['SignalType'] == signal_type]
            
            # High delta exposure exits
            high_delta_threshold = signal_df['MaxDeltaExposure'].quantile(0.75)
            high_delta_trades = signal_df[signal_df['MaxDeltaExposure'] > high_delta_threshold]
            
            if len(high_delta_trades) >= 2:
                avg_pnl = high_delta_trades['TotalPnL'].mean()
                
                pattern = ExitPattern(
                    pattern_id=f"{signal_type}_HIGH_DELTA",
                    signal_type=signal_type,
                    pattern_type='volatility_based',
                    volatility_condition='high',
                    day_of_week=None,
                    hour_of_day=None,
                    profit_threshold_pct=None,
                    time_in_trade_hours=None,
                    occurrences=len(high_delta_trades),
                    avg_profit_captured=avg_pnl,
                    success_rate=len(high_delta_trades[high_delta_trades['TotalPnL'] > 0]) / len(high_delta_trades),
                    avg_profit_left_on_table=0,
                    confidence_score=0.7,
                    action='full_exit',
                    exit_percentage=100
                )
                
                patterns.append(pattern)
        
        return patterns
    
    def _discover_ml_clusters(self, df: pd.DataFrame) -> List[ExitPattern]:
        """
        Use ML clustering to discover complex patterns
        
        Args:
            df: Lifecycle data
            
        Returns:
            List of ML-discovered patterns
        """
        patterns = []
        
        # Prepare features for clustering
        feature_cols = ['HoldingHours', 'EntryHour', 'ExitHour']
        
        # Add optional features if available
        optional_cols = ['ProfitCaptureRatio', 'TimeToMaxProfitHours', 'MaxDeltaExposure']
        for col in optional_cols:
            if col in df.columns:
                feature_cols.append(col)
        
        # Need enough data for clustering
        if len(df) < 10 or len(feature_cols) < 3:
            return patterns
        
        for signal_type in df['SignalType'].unique():
            signal_df = df[df['SignalType'] == signal_type].copy()
            
            if len(signal_df) < 5:
                continue
            
            # Prepare data
            X = signal_df[feature_cols].fillna(0)
            
            # Standardize features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Perform clustering
            n_clusters = min(3, len(signal_df) // 2)
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            clusters = kmeans.fit_predict(X_scaled)
            
            signal_df['cluster'] = clusters
            
            # Analyze each cluster
            for cluster_id in range(n_clusters):
                cluster_df = signal_df[signal_df['cluster'] == cluster_id]
                
                if len(cluster_df) >= 2:
                    avg_pnl = cluster_df['TotalPnL'].mean()
                    avg_hours = cluster_df['HoldingHours'].mean()
                    
                    # Determine cluster characteristics
                    cluster_profile = self._profile_cluster(cluster_df, feature_cols)
                    
                    pattern = ExitPattern(
                        pattern_id=f"{signal_type}_ML_CLUSTER_{cluster_id}",
                        signal_type=signal_type,
                        pattern_type='ml_discovered',
                        time_in_trade_hours=avg_hours,
                        day_of_week=None,
                        hour_of_day=None,
                        profit_threshold_pct=None,
                        volatility_condition=cluster_profile.get('volatility'),
                        occurrences=len(cluster_df),
                        avg_profit_captured=avg_pnl,
                        success_rate=len(cluster_df[cluster_df['TotalPnL'] > 0]) / len(cluster_df),
                        avg_profit_left_on_table=0,
                        confidence_score=0.6,
                        action=cluster_profile.get('action', 'hold'),
                        exit_percentage=cluster_profile.get('exit_pct', 0)
                    )
                    
                    patterns.append(pattern)
        
        return patterns
    
    def _profile_cluster(self, cluster_df: pd.DataFrame, feature_cols: List[str]) -> Dict:
        """
        Profile a cluster to determine its characteristics
        
        Args:
            cluster_df: DataFrame for this cluster
            feature_cols: Features used for clustering
            
        Returns:
            Dictionary with cluster profile
        """
        profile = {}
        
        # Determine if this is an early/late exit cluster
        avg_hours = cluster_df['HoldingHours'].mean()
        if avg_hours < 24:
            profile['timing'] = 'early'
            profile['action'] = 'partial_exit'
            profile['exit_pct'] = 50
        elif avg_hours > 60:
            profile['timing'] = 'late'
            profile['action'] = 'full_exit'
            profile['exit_pct'] = 100
        else:
            profile['timing'] = 'normal'
            profile['action'] = 'trail_stop'
            profile['exit_pct'] = 0
        
        # Determine volatility profile if delta data available
        if 'MaxDeltaExposure' in cluster_df.columns:
            avg_delta = cluster_df['MaxDeltaExposure'].mean()
            if avg_delta > cluster_df['MaxDeltaExposure'].median():
                profile['volatility'] = 'high'
            else:
                profile['volatility'] = 'low'
        
        return profile
    
    def get_exit_recommendation(self, 
                               signal_type: str,
                               current_state: Dict) -> Dict:
        """
        Get exit recommendation based on discovered patterns
        
        Args:
            signal_type: Signal type of current trade
            current_state: Current trade state (time in trade, P&L, day, etc.)
            
        Returns:
            Dictionary with exit recommendation
        """
        applicable_patterns = []
        
        # Current state variables
        current_day = current_state.get('day_of_week')
        current_hour = current_state.get('hour')
        time_in_trade = current_state.get('time_in_trade_hours', 0)
        current_pnl = current_state.get('current_pnl', 0)
        max_pnl = current_state.get('max_pnl', current_pnl)
        capture_ratio = current_pnl / max_pnl if max_pnl > 0 else 0
        
        # Find applicable patterns
        for pattern_id, pattern in self.patterns.items():
            if pattern.signal_type != signal_type:
                continue
            
            # Check if pattern conditions match
            if pattern.day_of_week and pattern.day_of_week != current_day:
                continue
            
            if pattern.hour_of_day and abs(pattern.hour_of_day - current_hour) > 1:
                continue
            
            if pattern.profit_threshold_pct and capture_ratio * 100 < pattern.profit_threshold_pct:
                continue
            
            applicable_patterns.append(pattern)
        
        if not applicable_patterns:
            return {
                'action': 'hold',
                'exit_percentage': 0,
                'confidence': 0.5,
                'reason': 'No matching exit patterns'
            }
        
        # Select best pattern (highest confidence)
        best_pattern = max(applicable_patterns, key=lambda x: x.confidence_score)
        
        return {
            'action': best_pattern.action,
            'exit_percentage': best_pattern.exit_percentage,
            'confidence': best_pattern.confidence_score,
            'reason': f"Pattern {best_pattern.pattern_id}: {best_pattern.pattern_type}",
            'expected_profit': best_pattern.avg_profit_captured,
            'pattern_details': best_pattern.to_dict()
        }
    
    def save_patterns(self, patterns: List[ExitPattern], output_path: str = None):
        """
        Save discovered patterns
        
        Args:
            patterns: List of patterns to save
            output_path: Optional file path for export
        """
        # Store in memory for quick access
        self.patterns = {p.pattern_id: p for p in patterns}
        
        # Save to database
        try:
            with self.engine.begin() as conn:
                # Create table if not exists
                create_table = """
                IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES 
                              WHERE TABLE_NAME = 'ExitPatterns')
                BEGIN
                    CREATE TABLE ExitPatterns (
                        Id INT IDENTITY(1,1) PRIMARY KEY,
                        PatternId NVARCHAR(50),
                        SignalType NVARCHAR(10),
                        PatternType NVARCHAR(20),
                        DayOfWeek NVARCHAR(20),
                        HourOfDay INT,
                        ProfitThresholdPct DECIMAL(5,2),
                        Occurrences INT,
                        AvgProfitCaptured DECIMAL(18,2),
                        SuccessRate DECIMAL(5,2),
                        ConfidenceScore DECIMAL(3,2),
                        Action NVARCHAR(20),
                        ExitPercentage DECIMAL(5,2),
                        CreatedAt DATETIME DEFAULT GETDATE(),
                        PatternJson NVARCHAR(MAX)
                    )
                END
                """
                conn.execute(text(create_table))
                
                # Clear old patterns
                conn.execute(text("DELETE FROM ExitPatterns"))
                
                # Insert new patterns
                for pattern in patterns:
                    insert_query = """
                    INSERT INTO ExitPatterns (
                        PatternId, SignalType, PatternType, DayOfWeek, HourOfDay,
                        ProfitThresholdPct, Occurrences, AvgProfitCaptured,
                        SuccessRate, ConfidenceScore, Action, ExitPercentage,
                        PatternJson
                    ) VALUES (
                        :pattern_id, :signal_type, :pattern_type, :day, :hour,
                        :profit_threshold, :occurrences, :avg_profit,
                        :success_rate, :confidence, :action, :exit_pct,
                        :json_data
                    )
                    """
                    
                    conn.execute(text(insert_query), {
                        'pattern_id': pattern.pattern_id,
                        'signal_type': pattern.signal_type,
                        'pattern_type': pattern.pattern_type,
                        'day': pattern.day_of_week,
                        'hour': pattern.hour_of_day,
                        'profit_threshold': pattern.profit_threshold_pct,
                        'occurrences': pattern.occurrences,
                        'avg_profit': pattern.avg_profit_captured,
                        'success_rate': pattern.success_rate,
                        'confidence': pattern.confidence_score,
                        'action': pattern.action,
                        'exit_pct': pattern.exit_percentage,
                        'json_data': json.dumps(pattern.to_dict())
                    })
                    
            logger.info(f"Saved {len(patterns)} exit patterns to database")
            
        except Exception as e:
            logger.error(f"Error saving patterns: {e}")
        
        # Save to file if specified
        if output_path:
            patterns_data = [p.to_dict() for p in patterns]
            with open(output_path, 'w') as f:
                json.dump(patterns_data, f, indent=2)
            logger.info(f"Patterns saved to {output_path}")