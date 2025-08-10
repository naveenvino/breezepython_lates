"""
Greeks Analyzer
Analyzes options Greeks (Delta, Gamma, Theta, Vega) for risk management and exit optimization
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging
from sqlalchemy import create_engine, text
import json

logger = logging.getLogger(__name__)

@dataclass
class GreeksSnapshot:
    """Greeks values at a specific point in time"""
    timestamp: datetime
    strike: float
    option_type: str
    spot_price: float
    
    # Greeks
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    
    # Derived metrics
    delta_dollars: float  # Delta * spot * quantity
    gamma_risk: float  # Gamma * spot^2 * quantity / 100
    theta_decay: float  # Daily theta decay in rupees
    vega_risk: float  # Vega exposure in rupees per 1% IV move
    
    # Risk scores
    delta_risk_score: float  # 0-1 score
    gamma_risk_score: float
    theta_benefit_score: float  # Higher is better for sellers
    vega_risk_score: float
    overall_risk_score: float
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'strike': self.strike,
            'option_type': self.option_type,
            'spot_price': self.spot_price,
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'rho': self.rho,
            'delta_dollars': self.delta_dollars,
            'gamma_risk': self.gamma_risk,
            'theta_decay': self.theta_decay,
            'vega_risk': self.vega_risk,
            'delta_risk_score': self.delta_risk_score,
            'gamma_risk_score': self.gamma_risk_score,
            'theta_benefit_score': self.theta_benefit_score,
            'vega_risk_score': self.vega_risk_score,
            'overall_risk_score': self.overall_risk_score
        }

@dataclass
class GreeksAnalysis:
    """Complete Greeks analysis for a trade"""
    trade_id: int
    signal_type: str
    
    # Current Greeks
    current_snapshot: GreeksSnapshot
    
    # Greeks progression
    max_delta_reached: float
    max_gamma_reached: float
    total_theta_collected: float
    max_vega_exposure: float
    
    # Risk events
    delta_breach_times: List[datetime]  # When delta exceeded threshold
    gamma_spike_times: List[datetime]  # When gamma spiked
    theta_acceleration_points: List[datetime]  # When theta decay accelerated
    
    # Recommendations
    current_risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    adjustment_needed: bool
    recommended_action: str
    hedge_recommendation: Optional[Dict]
    
    # Optimal Greeks targets
    target_delta: float
    target_gamma: float
    max_acceptable_vega: float
    
    def to_dict(self) -> Dict:
        return {
            'trade_id': self.trade_id,
            'signal_type': self.signal_type,
            'current_snapshot': self.current_snapshot.to_dict(),
            'max_delta_reached': self.max_delta_reached,
            'max_gamma_reached': self.max_gamma_reached,
            'total_theta_collected': self.total_theta_collected,
            'max_vega_exposure': self.max_vega_exposure,
            'delta_breach_times': [dt.isoformat() for dt in self.delta_breach_times],
            'gamma_spike_times': [dt.isoformat() for dt in self.gamma_spike_times],
            'current_risk_level': self.current_risk_level,
            'adjustment_needed': self.adjustment_needed,
            'recommended_action': self.recommended_action,
            'hedge_recommendation': self.hedge_recommendation,
            'target_delta': self.target_delta,
            'target_gamma': self.target_gamma,
            'max_acceptable_vega': self.max_acceptable_vega
        }

class GreeksAnalyzer:
    """Analyzes options Greeks for risk management"""
    
    def __init__(self, db_connection_string: str):
        """
        Initialize Greeks analyzer
        
        Args:
            db_connection_string: Database connection
        """
        self.engine = create_engine(db_connection_string)
        
        # Risk thresholds
        self.thresholds = {
            'delta': {
                'warning': 0.3,
                'critical': 0.5
            },
            'gamma': {
                'warning': 0.01,
                'critical': 0.02
            },
            'vega': {
                'warning': 100,
                'critical': 200
            }
        }
    
    def analyze_current_greeks(self,
                              trade_id: int,
                              signal_type: str,
                              strike: float,
                              option_type: str,
                              quantity: int = 750) -> GreeksAnalysis:
        """
        Analyze current Greeks for an active trade
        
        Args:
            trade_id: Trade identifier
            signal_type: Signal type
            strike: Strike price
            option_type: CE or PE
            quantity: Option quantity
            
        Returns:
            Complete Greeks analysis
        """
        # Get current Greeks
        current_greeks = self._get_current_greeks(strike, option_type)
        
        if not current_greeks:
            logger.warning(f"No Greeks data available for {strike} {option_type}")
            return self._default_analysis(trade_id, signal_type)
        
        # Get historical Greeks progression
        historical_greeks = self._get_historical_greeks(trade_id, strike, option_type)
        
        # Create current snapshot
        current_snapshot = self._create_snapshot(current_greeks, quantity)
        
        # Analyze progression
        progression = self._analyze_progression(historical_greeks, quantity)
        
        # Identify risk events
        risk_events = self._identify_risk_events(historical_greeks)
        
        # Determine risk level and recommendations
        risk_assessment = self._assess_risk(current_snapshot, progression)
        
        # Get optimal targets
        targets = self._get_optimal_targets(signal_type, current_snapshot)
        
        # Generate hedge recommendation if needed
        hedge_rec = None
        if risk_assessment['adjustment_needed']:
            hedge_rec = self._generate_hedge_recommendation(
                current_snapshot, targets, quantity
            )
        
        return GreeksAnalysis(
            trade_id=trade_id,
            signal_type=signal_type,
            current_snapshot=current_snapshot,
            max_delta_reached=progression['max_delta'],
            max_gamma_reached=progression['max_gamma'],
            total_theta_collected=progression['total_theta'],
            max_vega_exposure=progression['max_vega'],
            delta_breach_times=risk_events['delta_breaches'],
            gamma_spike_times=risk_events['gamma_spikes'],
            theta_acceleration_points=risk_events['theta_accelerations'],
            current_risk_level=risk_assessment['risk_level'],
            adjustment_needed=risk_assessment['adjustment_needed'],
            recommended_action=risk_assessment['recommended_action'],
            hedge_recommendation=hedge_rec,
            target_delta=targets['delta'],
            target_gamma=targets['gamma'],
            max_acceptable_vega=targets['max_vega']
        )
    
    def _get_current_greeks(self, strike: float, option_type: str) -> Optional[Dict]:
        """Get current Greeks from database"""
        query = """
        SELECT TOP 1
            o.Timestamp,
            o.Strike,
            o.OptionType,
            o.Close as OptionPrice,
            o.Delta,
            o.Gamma,
            o.Theta,
            o.Vega,
            o.ImpliedVolatility,
            n.Close as SpotPrice
        FROM OptionsData o
        JOIN NIFTYData_5Min n ON o.Timestamp = n.Timestamp
        WHERE o.Strike = :strike
            AND o.OptionType = :option_type
        ORDER BY o.Timestamp DESC
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(query), {
                'strike': strike,
                'option_type': option_type
            })
            row = result.fetchone()
            
            if row:
                return {
                    'timestamp': row.Timestamp,
                    'strike': row.Strike,
                    'option_type': row.OptionType,
                    'option_price': row.OptionPrice,
                    'delta': row.Delta,
                    'gamma': row.Gamma,
                    'theta': row.Theta,
                    'vega': row.Vega,
                    'iv': row.ImpliedVolatility,
                    'spot': row.SpotPrice
                }
        
        return None
    
    def _get_historical_greeks(self, 
                              trade_id: int,
                              strike: float,
                              option_type: str) -> pd.DataFrame:
        """Get historical Greeks progression"""
        query = """
        SELECT 
            o.Timestamp,
            o.Delta,
            o.Gamma,
            o.Theta,
            o.Vega,
            o.ImpliedVolatility,
            o.Close as OptionPrice,
            n.Close as SpotPrice
        FROM OptionsData o
        JOIN NIFTYData_5Min n ON o.Timestamp = n.Timestamp
        JOIN BacktestTrades t ON t.Id = :trade_id
        WHERE o.Strike = :strike
            AND o.OptionType = :option_type
            AND o.Timestamp >= t.EntryTime
            AND o.Timestamp <= ISNULL(t.ExitTime, GETDATE())
            AND DATEPART(MINUTE, o.Timestamp) % 5 = 0
        ORDER BY o.Timestamp
        """
        
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params={
                'trade_id': trade_id,
                'strike': strike,
                'option_type': option_type
            })
        
        return df
    
    def _create_snapshot(self, greeks_data: Dict, quantity: int) -> GreeksSnapshot:
        """Create Greeks snapshot with risk calculations"""
        delta = greeks_data.get('delta', 0)
        gamma = greeks_data.get('gamma', 0)
        theta = greeks_data.get('theta', 0)
        vega = greeks_data.get('vega', 0)
        spot = greeks_data.get('spot', 25000)
        
        # Calculate dollar Greeks
        delta_dollars = abs(delta * spot * quantity)
        gamma_risk = abs(gamma * spot * spot * quantity / 100)
        theta_decay = abs(theta * quantity)  # Daily decay
        vega_risk = abs(vega * quantity)  # Per 1% IV move
        
        # Calculate risk scores (0-1)
        delta_risk_score = min(1.0, abs(delta) / 0.5)  # 0.5 delta is max risk
        gamma_risk_score = min(1.0, abs(gamma) / 0.02)  # 0.02 gamma is max risk
        theta_benefit_score = min(1.0, abs(theta) * 10)  # Higher theta is better for sellers
        vega_risk_score = min(1.0, abs(vega) / 100)  # 100 vega is max risk
        
        # Overall risk (weighted)
        overall_risk = (
            delta_risk_score * 0.4 +
            gamma_risk_score * 0.3 +
            vega_risk_score * 0.2 +
            (1 - theta_benefit_score) * 0.1  # Inverse for risk
        )
        
        return GreeksSnapshot(
            timestamp=greeks_data.get('timestamp', datetime.now()),
            strike=greeks_data.get('strike', 0),
            option_type=greeks_data.get('option_type', ''),
            spot_price=spot,
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=0,  # Not typically used for short-term options
            delta_dollars=delta_dollars,
            gamma_risk=gamma_risk,
            theta_decay=theta_decay,
            vega_risk=vega_risk,
            delta_risk_score=delta_risk_score,
            gamma_risk_score=gamma_risk_score,
            theta_benefit_score=theta_benefit_score,
            vega_risk_score=vega_risk_score,
            overall_risk_score=overall_risk
        )
    
    def _analyze_progression(self, df: pd.DataFrame, quantity: int) -> Dict:
        """Analyze Greeks progression over time"""
        if df.empty:
            return {
                'max_delta': 0,
                'max_gamma': 0,
                'total_theta': 0,
                'max_vega': 0
            }
        
        return {
            'max_delta': df['Delta'].abs().max(),
            'max_gamma': df['Gamma'].abs().max(),
            'total_theta': df['Theta'].sum() * quantity / len(df) * (len(df) / 12),  # Approximate daily
            'max_vega': df['Vega'].abs().max()
        }
    
    def _identify_risk_events(self, df: pd.DataFrame) -> Dict:
        """Identify risk events in Greeks history"""
        events = {
            'delta_breaches': [],
            'gamma_spikes': [],
            'theta_accelerations': []
        }
        
        if df.empty:
            return events
        
        # Delta breaches
        delta_breaches = df[df['Delta'].abs() > self.thresholds['delta']['warning']]
        events['delta_breaches'] = delta_breaches.index.tolist()
        
        # Gamma spikes
        gamma_spikes = df[df['Gamma'].abs() > self.thresholds['gamma']['warning']]
        events['gamma_spikes'] = gamma_spikes.index.tolist()
        
        # Theta acceleration (sudden increases)
        if len(df) > 1:
            theta_change = df['Theta'].diff().abs()
            theta_accel = df[theta_change > df['Theta'].std() * 2]
            events['theta_accelerations'] = theta_accel.index.tolist()
        
        return events
    
    def _assess_risk(self, snapshot: GreeksSnapshot, progression: Dict) -> Dict:
        """Assess current risk level and recommend actions"""
        risk_level = "LOW"
        adjustment_needed = False
        recommended_action = "HOLD"
        
        # Determine risk level
        if snapshot.overall_risk_score > 0.8:
            risk_level = "CRITICAL"
            adjustment_needed = True
            recommended_action = "IMMEDIATE_ADJUSTMENT"
        elif snapshot.overall_risk_score > 0.6:
            risk_level = "HIGH"
            adjustment_needed = True
            recommended_action = "ADJUST_POSITION"
        elif snapshot.overall_risk_score > 0.4:
            risk_level = "MEDIUM"
            recommended_action = "MONITOR_CLOSELY"
        else:
            risk_level = "LOW"
            recommended_action = "HOLD"
        
        # Special cases
        if snapshot.delta_risk_score > 0.8:
            recommended_action = "DELTA_HEDGE_NEEDED"
            adjustment_needed = True
        
        if snapshot.gamma_risk_score > 0.8:
            recommended_action = "GAMMA_HEDGE_NEEDED"
            adjustment_needed = True
        
        if snapshot.vega_risk_score > 0.8 and snapshot.theta_benefit_score < 0.5:
            recommended_action = "REDUCE_VEGA_EXPOSURE"
            adjustment_needed = True
        
        return {
            'risk_level': risk_level,
            'adjustment_needed': adjustment_needed,
            'recommended_action': recommended_action
        }
    
    def _get_optimal_targets(self, signal_type: str, snapshot: GreeksSnapshot) -> Dict:
        """Get optimal Greeks targets for signal type"""
        # Default targets for option sellers
        targets = {
            'delta': 0.2,  # Keep delta low
            'gamma': 0.01,  # Keep gamma manageable
            'max_vega': 50  # Limit vega exposure
        }
        
        # Adjust based on signal type
        if signal_type in ['S1', 'S2', 'S4', 'S7']:  # Bullish signals
            targets['delta'] = -0.25  # Selling PUTs
        elif signal_type in ['S3', 'S5', 'S6', 'S8']:  # Bearish signals
            targets['delta'] = 0.25  # Selling CALLs
        
        # Adjust based on current market conditions
        if snapshot.spot_price > snapshot.strike:  # ITM
            targets['delta'] = 0.15  # Tighter control
            targets['gamma'] = 0.005
        
        return targets
    
    def _generate_hedge_recommendation(self,
                                      snapshot: GreeksSnapshot,
                                      targets: Dict,
                                      quantity: int) -> Dict:
        """Generate hedge recommendation to reduce risk"""
        hedge = {
            'type': None,
            'strike': None,
            'quantity': 0,
            'action': None,
            'expected_impact': {}
        }
        
        # Delta hedge
        if abs(snapshot.delta) > targets['delta'] * 1.5:
            delta_to_hedge = snapshot.delta - targets['delta']
            hedge['type'] = 'DELTA_HEDGE'
            
            if snapshot.option_type == 'CE':
                # Sold CALL, buy further OTM CALL to reduce delta
                hedge['strike'] = snapshot.strike + 200
                hedge['action'] = 'BUY_CALL'
            else:
                # Sold PUT, buy further OTM PUT
                hedge['strike'] = snapshot.strike - 200
                hedge['action'] = 'BUY_PUT'
            
            hedge['quantity'] = int(abs(delta_to_hedge) * quantity)
            hedge['expected_impact'] = {
                'delta_reduction': delta_to_hedge,
                'cost': hedge['quantity'] * 50  # Approximate
            }
        
        # Gamma hedge
        elif snapshot.gamma > targets['gamma'] * 1.5:
            hedge['type'] = 'GAMMA_HEDGE'
            
            # Buy ATM option to reduce gamma
            hedge['strike'] = round(snapshot.spot_price / 100) * 100
            hedge['action'] = f"BUY_{snapshot.option_type}"
            hedge['quantity'] = int(quantity * 0.5)
            hedge['expected_impact'] = {
                'gamma_reduction': snapshot.gamma * 0.4,
                'cost': hedge['quantity'] * 100
            }
        
        # Vega hedge
        elif snapshot.vega > targets['max_vega']:
            hedge['type'] = 'VEGA_HEDGE'
            
            # Reduce position or buy opposite
            hedge['action'] = 'REDUCE_POSITION'
            hedge['quantity'] = int(quantity * 0.3)
            hedge['expected_impact'] = {
                'vega_reduction': snapshot.vega * 0.3,
                'pnl_impact': 'Positive - reduces risk'
            }
        
        return hedge
    
    def calculate_portfolio_greeks(self, positions: List[Dict]) -> Dict:
        """
        Calculate aggregate Greeks for portfolio
        
        Args:
            positions: List of position dictionaries
            
        Returns:
            Portfolio-level Greeks
        """
        total_delta = 0
        total_gamma = 0
        total_theta = 0
        total_vega = 0
        
        for position in positions:
            greeks = self._get_current_greeks(
                position['strike'],
                position['option_type']
            )
            
            if greeks:
                # Adjust for position direction (sold = negative)
                multiplier = -1 if position.get('sold', True) else 1
                quantity = position.get('quantity', 750)
                
                total_delta += greeks['delta'] * quantity * multiplier
                total_gamma += greeks['gamma'] * quantity * multiplier
                total_theta += greeks['theta'] * quantity * multiplier
                total_vega += greeks['vega'] * quantity * multiplier
        
        # Calculate portfolio risk metrics
        spot = 25000  # Current NIFTY level
        portfolio_delta_dollars = abs(total_delta * spot)
        portfolio_gamma_risk = abs(total_gamma * spot * spot / 100)
        portfolio_theta_daily = abs(total_theta)
        portfolio_vega_risk = abs(total_vega)
        
        return {
            'total_delta': total_delta,
            'total_gamma': total_gamma,
            'total_theta': total_theta,
            'total_vega': total_vega,
            'delta_dollars': portfolio_delta_dollars,
            'gamma_risk': portfolio_gamma_risk,
            'theta_daily': portfolio_theta_daily,
            'vega_risk': portfolio_vega_risk,
            'risk_assessment': self._assess_portfolio_risk(
                total_delta, total_gamma, total_theta, total_vega
            )
        }
    
    def _assess_portfolio_risk(self, delta, gamma, theta, vega) -> str:
        """Assess portfolio-level risk"""
        risk_score = 0
        
        # Delta risk
        if abs(delta) > 500:
            risk_score += 3
        elif abs(delta) > 300:
            risk_score += 2
        elif abs(delta) > 150:
            risk_score += 1
        
        # Gamma risk
        if abs(gamma) > 10:
            risk_score += 3
        elif abs(gamma) > 5:
            risk_score += 2
        elif abs(gamma) > 2:
            risk_score += 1
        
        # Vega risk
        if abs(vega) > 500:
            risk_score += 2
        elif abs(vega) > 300:
            risk_score += 1
        
        # Risk level
        if risk_score >= 6:
            return "CRITICAL - Immediate action required"
        elif risk_score >= 4:
            return "HIGH - Consider adjustments"
        elif risk_score >= 2:
            return "MEDIUM - Monitor closely"
        else:
            return "LOW - Within acceptable limits"
    
    def get_greeks_evolution(self,
                            strike: float,
                            option_type: str,
                            from_date: datetime,
                            to_date: datetime) -> pd.DataFrame:
        """
        Get Greeks evolution over time
        
        Args:
            strike: Strike price
            option_type: CE or PE
            from_date: Start date
            to_date: End date
            
        Returns:
            DataFrame with Greeks evolution
        """
        query = """
        SELECT 
            Timestamp,
            Delta,
            Gamma,
            Theta,
            Vega,
            ImpliedVolatility,
            Close as OptionPrice
        FROM OptionsData
        WHERE Strike = :strike
            AND OptionType = :option_type
            AND Timestamp >= :from_date
            AND Timestamp <= :to_date
            AND DATEPART(MINUTE, Timestamp) % 60 = 0  -- Hourly
        ORDER BY Timestamp
        """
        
        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params={
                'strike': strike,
                'option_type': option_type,
                'from_date': from_date,
                'to_date': to_date
            })
        
        if not df.empty:
            df.set_index('Timestamp', inplace=True)
            
            # Add risk scores
            df['delta_risk'] = df['Delta'].abs() / 0.5
            df['gamma_risk'] = df['Gamma'].abs() / 0.02
            df['vega_risk'] = df['Vega'].abs() / 100
            
        return df
    
    def _default_analysis(self, trade_id: int, signal_type: str) -> GreeksAnalysis:
        """Return default analysis when data unavailable"""
        return GreeksAnalysis(
            trade_id=trade_id,
            signal_type=signal_type,
            current_snapshot=GreeksSnapshot(
                timestamp=datetime.now(),
                strike=0,
                option_type='',
                spot_price=0,
                delta=0,
                gamma=0,
                theta=0,
                vega=0,
                rho=0,
                delta_dollars=0,
                gamma_risk=0,
                theta_decay=0,
                vega_risk=0,
                delta_risk_score=0,
                gamma_risk_score=0,
                theta_benefit_score=0,
                vega_risk_score=0,
                overall_risk_score=0
            ),
            max_delta_reached=0,
            max_gamma_reached=0,
            total_theta_collected=0,
            max_vega_exposure=0,
            delta_breach_times=[],
            gamma_spike_times=[],
            theta_acceleration_points=[],
            current_risk_level="UNKNOWN",
            adjustment_needed=False,
            recommended_action="MONITOR",
            hedge_recommendation=None,
            target_delta=0,
            target_gamma=0,
            max_acceptable_vega=0
        )