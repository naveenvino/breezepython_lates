"""
Profit Target Optimizer
Optimizes profit targets dynamically based on market conditions and historical performance
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
from sqlalchemy import create_engine, text
from scipy import stats
import json

logger = logging.getLogger(__name__)

@dataclass
class ProfitTarget:
    """Profit target configuration"""
    signal_type: str
    
    # Target levels
    primary_target: float  # Main profit target
    secondary_target: float  # Stretch target
    minimum_target: float  # Minimum acceptable profit
    
    # Partial exit levels
    first_exit_level: float  # Exit 25% here
    first_exit_percentage: float
    second_exit_level: float  # Exit 50% here
    second_exit_percentage: float
    final_exit_level: float  # Exit remaining
    
    # Time-based adjustments
    day_1_multiplier: float  # Monday
    day_2_multiplier: float  # Tuesday
    day_3_multiplier: float  # Wednesday
    day_4_multiplier: float  # Thursday
    
    # Market regime adjustments
    trending_multiplier: float
    ranging_multiplier: float
    volatile_multiplier: float
    
    # Confidence and statistics
    confidence_level: float
    expected_achievement_rate: float
    historical_achievement_rate: float
    average_time_to_target: float  # Hours
    
    def to_dict(self) -> Dict:
        return {
            'signal_type': self.signal_type,
            'primary_target': self.primary_target,
            'secondary_target': self.secondary_target,
            'minimum_target': self.minimum_target,
            'first_exit_level': self.first_exit_level,
            'first_exit_percentage': self.first_exit_percentage,
            'second_exit_level': self.second_exit_level,
            'second_exit_percentage': self.second_exit_percentage,
            'final_exit_level': self.final_exit_level,
            'day_1_multiplier': self.day_1_multiplier,
            'day_2_multiplier': self.day_2_multiplier,
            'day_3_multiplier': self.day_3_multiplier,
            'day_4_multiplier': self.day_4_multiplier,
            'trending_multiplier': self.trending_multiplier,
            'ranging_multiplier': self.ranging_multiplier,
            'volatile_multiplier': self.volatile_multiplier,
            'confidence_level': self.confidence_level,
            'expected_achievement_rate': self.expected_achievement_rate,
            'historical_achievement_rate': self.historical_achievement_rate,
            'average_time_to_target': self.average_time_to_target
        }

@dataclass
class DynamicTarget:
    """Dynamic profit target for active trade"""
    current_target: float
    adjusted_target: float
    stretch_target: float
    
    # Exit plan
    immediate_exit_qty: float  # % to exit now
    next_exit_level: float
    next_exit_qty: float
    
    # Reasoning
    adjustment_reason: str
    market_factor: float
    time_factor: float
    performance_factor: float
    
    # Probability
    achievement_probability: float
    risk_reward_ratio: float
    
    def to_dict(self) -> Dict:
        return {
            'current_target': self.current_target,
            'adjusted_target': self.adjusted_target,
            'stretch_target': self.stretch_target,
            'immediate_exit_qty': self.immediate_exit_qty,
            'next_exit_level': self.next_exit_level,
            'next_exit_qty': self.next_exit_qty,
            'adjustment_reason': self.adjustment_reason,
            'market_factor': self.market_factor,
            'time_factor': self.time_factor,
            'performance_factor': self.performance_factor,
            'achievement_probability': self.achievement_probability,
            'risk_reward_ratio': self.risk_reward_ratio
        }

class ProfitTargetOptimizer:
    """Optimizes profit targets based on multiple factors"""
    
    def __init__(self, db_connection_string: str):
        """
        Initialize optimizer
        
        Args:
            db_connection_string: Database connection
        """
        self.engine = create_engine(db_connection_string)
        self.optimal_targets = {}
        
    def optimize_targets(self,
                        from_date: datetime,
                        to_date: datetime) -> Dict[str, ProfitTarget]:
        """
        Optimize profit targets for all signals
        
        Args:
            from_date: Start date for analysis
            to_date: End date for analysis
            
        Returns:
            Dictionary of optimized targets per signal
        """
        logger.info("Optimizing profit targets...")
        
        # Get historical performance data
        performance_data = self._get_historical_performance(from_date, to_date)
        
        if performance_data.empty:
            logger.warning("No historical data for optimization")
            return self._get_default_targets()
        
        optimal_targets = {}
        
        for signal_type in ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']:
            signal_data = performance_data[performance_data['SignalType'] == signal_type]
            
            if signal_data.empty:
                optimal_targets[signal_type] = self._get_default_target(signal_type)
                continue
            
            # Calculate optimal targets
            target = self._calculate_optimal_target(signal_type, signal_data)
            optimal_targets[signal_type] = target
            
            logger.info(f"{signal_type}: Primary target Rs.{target.primary_target:,.0f} "
                       f"with {target.expected_achievement_rate:.1%} expected success")
        
        self.optimal_targets = optimal_targets
        return optimal_targets
    
    def _get_historical_performance(self, 
                                   from_date: datetime,
                                   to_date: datetime) -> pd.DataFrame:
        """Get historical trade performance"""
        query = """
        SELECT 
            t.Id,
            t.SignalType,
            t.EntryTime,
            t.ExitTime,
            t.TotalPnL,
            t.IndexPriceAtEntry,
            t.IndexPriceAtExit,
            DATEDIFF(hour, t.EntryTime, t.ExitTime) as HoldingHours,
            DATEPART(dw, t.ExitTime) as ExitDay,
            -- Calculate lifecycle metrics from available data
            t.TotalPnL as MaxProfit,
            DATEDIFF(hour, t.EntryTime, t.ExitTime) as TimeToMaxProfitHours,
            CASE WHEN t.TotalPnL > 0 THEN 1.0 ELSE 0.0 END as ProfitCaptureRatio
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
    
    def _calculate_optimal_target(self, 
                                 signal_type: str,
                                 data: pd.DataFrame) -> ProfitTarget:
        """Calculate optimal profit target for signal"""
        # Basic statistics
        avg_profit = data['TotalPnL'].mean()
        std_profit = data['TotalPnL'].std()
        max_profit = data['TotalPnL'].max()
        percentiles = data['TotalPnL'].quantile([0.25, 0.5, 0.75, 0.9])
        
        # Use lifecycle data if available
        if 'MaxProfit' in data.columns and data['MaxProfit'].notna().any():
            avg_max = data['MaxProfit'].mean()
            avg_capture = data['ProfitCaptureRatio'].mean()
            avg_time_to_max = data['TimeToMaxProfitHours'].mean()
        else:
            avg_max = max_profit
            avg_capture = 0.7  # Assume 70% capture
            avg_time_to_max = 48  # Assume 2 days
        
        # Calculate targets based on statistical analysis
        # Primary target: 75th percentile or average max * capture ratio
        primary_target = max(percentiles[0.75], avg_max * avg_capture)
        
        # Secondary target: 90th percentile
        secondary_target = max(percentiles[0.9], avg_max * 0.9)
        
        # Minimum target: 50th percentile
        minimum_target = max(percentiles[0.5], avg_profit * 0.5)
        
        # Partial exit levels
        first_exit = primary_target * 0.4  # 40% of target
        second_exit = primary_target * 0.7  # 70% of target
        
        # Day-wise multipliers based on historical patterns
        day_multipliers = self._calculate_day_multipliers(data)
        
        # Market regime multipliers
        regime_multipliers = self._calculate_regime_multipliers(signal_type)
        
        # Achievement rates
        historical_rate = len(data[data['TotalPnL'] >= primary_target]) / len(data)
        
        # Expected rate with optimization
        expected_rate = min(0.9, historical_rate * 1.2)  # Expect 20% improvement
        
        return ProfitTarget(
            signal_type=signal_type,
            primary_target=primary_target,
            secondary_target=secondary_target,
            minimum_target=minimum_target,
            first_exit_level=first_exit,
            first_exit_percentage=0.25,
            second_exit_level=second_exit,
            second_exit_percentage=0.50,
            final_exit_level=primary_target,
            day_1_multiplier=day_multipliers[0],
            day_2_multiplier=day_multipliers[1],
            day_3_multiplier=day_multipliers[2],
            day_4_multiplier=day_multipliers[3],
            trending_multiplier=regime_multipliers['trending'],
            ranging_multiplier=regime_multipliers['ranging'],
            volatile_multiplier=regime_multipliers['volatile'],
            confidence_level=self._calculate_confidence(data, primary_target),
            expected_achievement_rate=expected_rate,
            historical_achievement_rate=historical_rate,
            average_time_to_target=avg_time_to_max
        )
    
    def _calculate_day_multipliers(self, data: pd.DataFrame) -> List[float]:
        """Calculate day-wise target multipliers"""
        if 'ExitDay' not in data.columns:
            return [1.0, 1.0, 1.0, 1.0]
        
        # Analyze performance by day (1=Sunday, 2=Monday, etc.)
        day_performance = {}
        for day in [2, 3, 4, 5]:  # Monday to Thursday
            day_data = data[data['ExitDay'] == day]
            if not day_data.empty:
                day_performance[day] = day_data['TotalPnL'].mean()
        
        # Calculate multipliers
        if day_performance:
            avg_performance = np.mean(list(day_performance.values()))
            multipliers = []
            
            for day in [2, 3, 4, 5]:  # Monday to Thursday
                if day in day_performance:
                    multiplier = day_performance[day] / avg_performance
                    multipliers.append(max(0.8, min(1.2, multiplier)))
                else:
                    multipliers.append(1.0)
        else:
            multipliers = [1.0, 1.0, 1.0, 1.0]
        
        return multipliers
    
    def _calculate_regime_multipliers(self, signal_type: str) -> Dict[str, float]:
        """Calculate market regime multipliers"""
        # Default multipliers
        multipliers = {
            'trending': 1.0,
            'ranging': 1.0,
            'volatile': 1.0
        }
        
        # Adjust based on signal characteristics
        if signal_type in ['S1', 'S7']:  # Trend following signals
            multipliers['trending'] = 1.3
            multipliers['ranging'] = 0.8
            multipliers['volatile'] = 0.9
        elif signal_type in ['S2', 'S3']:  # Range trading signals
            multipliers['trending'] = 0.9
            multipliers['ranging'] = 1.2
            multipliers['volatile'] = 0.8
        elif signal_type in ['S5', 'S6', 'S8']:  # Volatility signals
            multipliers['trending'] = 1.1
            multipliers['ranging'] = 0.9
            multipliers['volatile'] = 1.2
        
        return multipliers
    
    def _calculate_confidence(self, data: pd.DataFrame, target: float) -> float:
        """Calculate confidence level for target"""
        if len(data) < 3:
            return 0.5
        
        # Calculate probability of achieving target
        successes = len(data[data['TotalPnL'] >= target])
        total = len(data)
        
        # Use Wilson score interval for confidence
        p = successes / total if total > 0 else 0
        z = 1.96  # 95% confidence
        
        denominator = 1 + z**2 / total
        center = (p + z**2 / (2 * total)) / denominator
        
        confidence = min(0.95, center)
        
        return confidence
    
    def get_dynamic_target(self,
                          signal_type: str,
                          current_state: Dict) -> DynamicTarget:
        """
        Get dynamic profit target for active trade
        
        Args:
            signal_type: Signal type
            current_state: Current trade state
            
        Returns:
            Dynamic target with adjustments
        """
        # Get base target
        if signal_type not in self.optimal_targets:
            self.optimal_targets[signal_type] = self._get_default_target(signal_type)
        
        base_target = self.optimal_targets[signal_type]
        
        # Current values
        current_pnl = current_state.get('current_pnl', 0)
        max_pnl = current_state.get('max_pnl', current_pnl)
        time_in_trade = current_state.get('time_in_trade_hours', 0)
        day_of_week = current_state.get('day_of_week', 'Monday')
        market_regime = current_state.get('market_regime', 'normal')
        
        # Calculate adjustments
        
        # 1. Time factor
        time_factor = self._calculate_time_factor(time_in_trade, day_of_week, base_target)
        
        # 2. Market factor
        market_factor = self._calculate_market_factor(market_regime, base_target)
        
        # 3. Performance factor
        performance_factor = self._calculate_performance_factor(current_pnl, max_pnl, base_target)
        
        # Adjusted target
        adjusted_target = base_target.primary_target * time_factor * market_factor * performance_factor
        
        # Stretch target
        stretch_target = base_target.secondary_target * market_factor
        
        # Determine exit plan
        exit_plan = self._determine_exit_plan(
            current_pnl, adjusted_target, base_target, time_in_trade
        )
        
        # Calculate achievement probability
        achievement_prob = self._calculate_achievement_probability(
            current_pnl, adjusted_target, time_in_trade
        )
        
        # Risk-reward ratio
        risk_reward = adjusted_target / abs(current_state.get('stop_loss', adjusted_target * 0.5))
        
        # Adjustment reason
        reasons = []
        if time_factor != 1.0:
            reasons.append(f"Time adjusted ({time_factor:.2f}x)")
        if market_factor != 1.0:
            reasons.append(f"Market adjusted ({market_factor:.2f}x)")
        if performance_factor != 1.0:
            reasons.append(f"Performance adjusted ({performance_factor:.2f}x)")
        
        adjustment_reason = " | ".join(reasons) if reasons else "No adjustment needed"
        
        return DynamicTarget(
            current_target=base_target.primary_target,
            adjusted_target=adjusted_target,
            stretch_target=stretch_target,
            immediate_exit_qty=exit_plan['immediate_qty'],
            next_exit_level=exit_plan['next_level'],
            next_exit_qty=exit_plan['next_qty'],
            adjustment_reason=adjustment_reason,
            market_factor=market_factor,
            time_factor=time_factor,
            performance_factor=performance_factor,
            achievement_probability=achievement_prob,
            risk_reward_ratio=risk_reward
        )
    
    def _calculate_time_factor(self, 
                              time_in_trade: float,
                              day_of_week: str,
                              target: ProfitTarget) -> float:
        """Calculate time-based adjustment factor"""
        # Day of week factor
        day_map = {
            'Monday': target.day_1_multiplier,
            'Tuesday': target.day_2_multiplier,
            'Wednesday': target.day_3_multiplier,
            'Thursday': target.day_4_multiplier
        }
        day_factor = day_map.get(day_of_week, 1.0)
        
        # Time decay factor (reduce target as expiry approaches)
        if time_in_trade > 60:  # More than 2.5 days
            time_decay = 0.8
        elif time_in_trade > 48:  # More than 2 days
            time_decay = 0.9
        else:
            time_decay = 1.0
        
        return day_factor * time_decay
    
    def _calculate_market_factor(self, 
                                market_regime: str,
                                target: ProfitTarget) -> float:
        """Calculate market regime adjustment factor"""
        regime_map = {
            'trending': target.trending_multiplier,
            'ranging': target.ranging_multiplier,
            'volatile': target.volatile_multiplier,
            'normal': 1.0
        }
        
        return regime_map.get(market_regime, 1.0)
    
    def _calculate_performance_factor(self,
                                     current_pnl: float,
                                     max_pnl: float,
                                     target: ProfitTarget) -> float:
        """Calculate performance-based adjustment"""
        # If already exceeded target, raise it
        if current_pnl > target.primary_target:
            return 1.2
        
        # If losing momentum, lower target
        if max_pnl > current_pnl and (max_pnl - current_pnl) > target.primary_target * 0.2:
            return 0.8
        
        # If on track, no adjustment
        return 1.0
    
    def _determine_exit_plan(self,
                            current_pnl: float,
                            adjusted_target: float,
                            base_target: ProfitTarget,
                            time_in_trade: float) -> Dict:
        """Determine exit plan based on current state"""
        # Already exceeded target
        if current_pnl >= adjusted_target:
            return {
                'immediate_qty': 0.75,  # Exit 75%
                'next_level': adjusted_target * 1.2,  # Trail for 20% more
                'next_qty': 0.25
            }
        
        # Near target
        elif current_pnl >= adjusted_target * 0.8:
            return {
                'immediate_qty': 0.5,  # Exit 50%
                'next_level': adjusted_target,
                'next_qty': 0.5
            }
        
        # At second level
        elif current_pnl >= base_target.second_exit_level:
            return {
                'immediate_qty': 0.25,  # Exit 25%
                'next_level': adjusted_target * 0.9,
                'next_qty': 0.5
            }
        
        # At first level
        elif current_pnl >= base_target.first_exit_level:
            return {
                'immediate_qty': 0,  # Hold
                'next_level': base_target.second_exit_level,
                'next_qty': 0.25
            }
        
        # Thursday special case
        elif time_in_trade > 60:  # Thursday
            return {
                'immediate_qty': 0.5 if current_pnl > 0 else 0,
                'next_level': current_pnl * 1.1,  # 10% more
                'next_qty': 0.5
            }
        
        # Default: hold
        else:
            return {
                'immediate_qty': 0,
                'next_level': base_target.first_exit_level,
                'next_qty': 0.25
            }
    
    def _calculate_achievement_probability(self,
                                          current_pnl: float,
                                          target: float,
                                          time_in_trade: float) -> float:
        """Calculate probability of achieving target"""
        # Already achieved
        if current_pnl >= target:
            return 1.0
        
        # Distance to target
        distance_ratio = (target - current_pnl) / target
        
        # Time remaining (max 72 hours for weekly options)
        time_remaining = max(0, 72 - time_in_trade)
        time_ratio = time_remaining / 72
        
        # Base probability
        base_prob = 0.5
        
        # Adjust based on distance and time
        if distance_ratio < 0.2 and time_ratio > 0.3:
            probability = 0.8
        elif distance_ratio < 0.4 and time_ratio > 0.5:
            probability = 0.6
        elif distance_ratio < 0.6 and time_ratio > 0.7:
            probability = 0.4
        else:
            probability = 0.2
        
        return min(0.95, max(0.05, probability))
    
    def _get_default_target(self, signal_type: str) -> ProfitTarget:
        """Get default profit target"""
        # Default based on historical averages
        defaults = {
            'S1': 26000,
            'S2': 18000,
            'S3': 37000,
            'S4': 33000,
            'S5': 35000,
            'S6': 20000,
            'S7': 25000,
            'S8': 6000
        }
        
        primary = defaults.get(signal_type, 20000)
        
        return ProfitTarget(
            signal_type=signal_type,
            primary_target=primary,
            secondary_target=primary * 1.5,
            minimum_target=primary * 0.5,
            first_exit_level=primary * 0.4,
            first_exit_percentage=0.25,
            second_exit_level=primary * 0.7,
            second_exit_percentage=0.50,
            final_exit_level=primary,
            day_1_multiplier=1.0,
            day_2_multiplier=1.0,
            day_3_multiplier=1.1,
            day_4_multiplier=0.9,
            trending_multiplier=1.0,
            ranging_multiplier=1.0,
            volatile_multiplier=0.8,
            confidence_level=0.7,
            expected_achievement_rate=0.7,
            historical_achievement_rate=0.6,
            average_time_to_target=48
        )
    
    def _get_default_targets(self) -> Dict[str, ProfitTarget]:
        """Get default targets for all signals"""
        return {
            signal: self._get_default_target(signal)
            for signal in ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']
        }
    
    def save_optimal_targets(self, output_path: str = None):
        """Save optimal targets to database or file"""
        if not self.optimal_targets:
            logger.warning("No optimal targets to save")
            return
        
        # Save to database
        try:
            with self.engine.begin() as conn:
                # Create table if not exists
                create_table = """
                IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES 
                              WHERE TABLE_NAME = 'OptimalProfitTargets')
                BEGIN
                    CREATE TABLE OptimalProfitTargets (
                        Id INT IDENTITY(1,1) PRIMARY KEY,
                        SignalType NVARCHAR(10),
                        PrimaryTarget DECIMAL(18,2),
                        SecondaryTarget DECIMAL(18,2),
                        MinimumTarget DECIMAL(18,2),
                        FirstExitLevel DECIMAL(18,2),
                        SecondExitLevel DECIMAL(18,2),
                        ConfidenceLevel DECIMAL(5,2),
                        ExpectedAchievementRate DECIMAL(5,2),
                        CreatedAt DATETIME DEFAULT GETDATE(),
                        ConfigJson NVARCHAR(MAX)
                    )
                END
                """
                conn.execute(text(create_table))
                
                # Clear old targets
                conn.execute(text("DELETE FROM OptimalProfitTargets"))
                
                # Insert new targets
                for signal_type, target in self.optimal_targets.items():
                    insert_query = """
                    INSERT INTO OptimalProfitTargets (
                        SignalType, PrimaryTarget, SecondaryTarget, MinimumTarget,
                        FirstExitLevel, SecondExitLevel, ConfidenceLevel,
                        ExpectedAchievementRate, ConfigJson
                    ) VALUES (
                        :signal_type, :primary, :secondary, :minimum,
                        :first_exit, :second_exit, :confidence,
                        :expected_rate, :config_json
                    )
                    """
                    
                    conn.execute(text(insert_query), {
                        'signal_type': signal_type,
                        'primary': target.primary_target,
                        'secondary': target.secondary_target,
                        'minimum': target.minimum_target,
                        'first_exit': target.first_exit_level,
                        'second_exit': target.second_exit_level,
                        'confidence': target.confidence_level,
                        'expected_rate': target.expected_achievement_rate,
                        'config_json': json.dumps(target.to_dict())
                    })
                
            logger.info(f"Saved optimal targets for {len(self.optimal_targets)} signals")
            
        except Exception as e:
            logger.error(f"Error saving targets: {e}")
        
        # Save to file if specified
        if output_path:
            targets_data = {k: v.to_dict() for k, v in self.optimal_targets.items()}
            with open(output_path, 'w') as f:
                json.dump(targets_data, f, indent=2)
            logger.info(f"Targets saved to {output_path}")