"""
Position Adjustment Engine
Manages dynamic position adjustments including rolling, hedging, and conversion strategies
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

class AdjustmentType(Enum):
    """Types of position adjustments"""
    ROLL_STRIKE = "roll_strike"  # Roll to different strike
    ROLL_EXPIRY = "roll_expiry"  # Roll to next expiry
    ADD_HEDGE = "add_hedge"  # Add protective position
    REMOVE_HEDGE = "remove_hedge"  # Remove hedge
    CONVERT_SPREAD = "convert_spread"  # Convert to spread
    PARTIAL_CLOSE = "partial_close"  # Close part of position
    DELTA_HEDGE = "delta_hedge"  # Delta neutral adjustment
    RATIO_SPREAD = "ratio_spread"  # Convert to ratio spread
    IRON_CONDOR = "iron_condor"  # Convert to iron condor
    CALENDAR_SPREAD = "calendar_spread"  # Add calendar spread

@dataclass
class AdjustmentRecommendation:
    """Position adjustment recommendation"""
    adjustment_type: AdjustmentType
    urgency: str  # IMMEDIATE, HIGH, MEDIUM, LOW
    
    # Current position
    current_strike: float
    current_type: str  # CE/PE
    current_quantity: int
    current_pnl: float
    
    # Recommended adjustment
    new_strike: Optional[float]
    new_expiry: Optional[datetime]
    additional_legs: List[Dict]  # Additional positions to add
    close_quantity: int  # Quantity to close
    
    # Impact analysis
    expected_pnl_impact: float
    expected_risk_reduction: float
    expected_margin_impact: float
    breakeven_change: float
    max_profit_change: float
    max_loss_change: float
    
    # Reasoning
    trigger_reason: str
    market_conditions: Dict
    confidence_score: float
    
    # Execution
    execution_steps: List[str]
    estimated_cost: float
    
    def to_dict(self) -> Dict:
        return {
            'adjustment_type': self.adjustment_type.value,
            'urgency': self.urgency,
            'current_strike': self.current_strike,
            'current_type': self.current_type,
            'current_quantity': self.current_quantity,
            'current_pnl': self.current_pnl,
            'new_strike': self.new_strike,
            'new_expiry': self.new_expiry.isoformat() if self.new_expiry else None,
            'additional_legs': self.additional_legs,
            'close_quantity': self.close_quantity,
            'expected_pnl_impact': self.expected_pnl_impact,
            'expected_risk_reduction': self.expected_risk_reduction,
            'expected_margin_impact': self.expected_margin_impact,
            'breakeven_change': self.breakeven_change,
            'max_profit_change': self.max_profit_change,
            'max_loss_change': self.max_loss_change,
            'trigger_reason': self.trigger_reason,
            'market_conditions': self.market_conditions,
            'confidence_score': self.confidence_score,
            'execution_steps': self.execution_steps,
            'estimated_cost': self.estimated_cost
        }

@dataclass
class PositionState:
    """Current position state"""
    trade_id: int
    signal_type: str
    entry_time: datetime
    current_time: datetime
    
    # Position details
    main_strike: float
    main_type: str
    main_quantity: int
    main_entry_price: float
    main_current_price: float
    
    # Hedge details (if any)
    hedge_strike: Optional[float]
    hedge_type: Optional[str]
    hedge_quantity: Optional[int]
    hedge_current_price: Optional[float]
    
    # Market data
    spot_price: float
    implied_volatility: float
    days_to_expiry: int
    
    # Greeks
    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float
    
    # P&L
    current_pnl: float
    max_pnl: float
    unrealized_pnl: float

class PositionAdjustmentEngine:
    """Manages position adjustments and conversions"""
    
    def __init__(self, db_connection_string: str):
        """
        Initialize adjustment engine
        
        Args:
            db_connection_string: Database connection
        """
        self.engine = create_engine(db_connection_string)
        
        # Adjustment thresholds
        self.thresholds = {
            'itm_threshold': 0.8,  # 80% probability of ITM triggers adjustment
            'profit_lock_threshold': 0.75,  # Lock 75% of max profit
            'loss_limit': -50000,  # Maximum acceptable loss
            'delta_limit': 0.4,  # Maximum delta exposure
            'days_to_roll': 2,  # Roll when 2 days to expiry
            'volatility_spike': 1.5  # 50% IV increase triggers adjustment
        }
    
    def analyze_position(self, position: PositionState) -> AdjustmentRecommendation:
        """
        Analyze position and recommend adjustments
        
        Args:
            position: Current position state
            
        Returns:
            Adjustment recommendation
        """
        # Check various adjustment triggers
        adjustments = []
        
        # 1. Check if position is deep ITM
        itm_adj = self._check_itm_adjustment(position)
        if itm_adj:
            adjustments.append(itm_adj)
        
        # 2. Check if near expiry
        expiry_adj = self._check_expiry_adjustment(position)
        if expiry_adj:
            adjustments.append(expiry_adj)
        
        # 3. Check Greeks exposure
        greeks_adj = self._check_greeks_adjustment(position)
        if greeks_adj:
            adjustments.append(greeks_adj)
        
        # 4. Check profit protection
        profit_adj = self._check_profit_protection(position)
        if profit_adj:
            adjustments.append(profit_adj)
        
        # 5. Check loss mitigation
        loss_adj = self._check_loss_mitigation(position)
        if loss_adj:
            adjustments.append(loss_adj)
        
        # 6. Check volatility adjustment
        vol_adj = self._check_volatility_adjustment(position)
        if vol_adj:
            adjustments.append(vol_adj)
        
        # Select best adjustment
        if adjustments:
            # Sort by urgency and confidence
            adjustments.sort(key=lambda x: (
                self._urgency_score(x.urgency),
                x.confidence_score
            ), reverse=True)
            
            return adjustments[0]
        
        # No adjustment needed
        return self._no_adjustment_needed(position)
    
    def _check_itm_adjustment(self, position: PositionState) -> Optional[AdjustmentRecommendation]:
        """Check if position needs ITM adjustment"""
        # Calculate moneyness
        if position.main_type == 'CE':
            moneyness = position.spot_price / position.main_strike
            is_itm = moneyness > 1.0
        else:  # PE
            moneyness = position.main_strike / position.spot_price
            is_itm = moneyness > 1.0
        
        # Check if significantly ITM
        if is_itm and moneyness > 1.02:  # 2% ITM
            # Recommend rolling to OTM strike
            new_strike = self._calculate_roll_strike(position)
            
            return AdjustmentRecommendation(
                adjustment_type=AdjustmentType.ROLL_STRIKE,
                urgency="HIGH",
                current_strike=position.main_strike,
                current_type=position.main_type,
                current_quantity=position.main_quantity,
                current_pnl=position.current_pnl,
                new_strike=new_strike,
                new_expiry=None,
                additional_legs=[],
                close_quantity=position.main_quantity,
                expected_pnl_impact=self._estimate_roll_impact(position, new_strike),
                expected_risk_reduction=0.3,
                expected_margin_impact=0,
                breakeven_change=new_strike - position.main_strike,
                max_profit_change=-position.current_pnl * 0.2,
                max_loss_change=position.current_pnl * 0.5,
                trigger_reason="Position is ITM, rolling to protect profit",
                market_conditions={'moneyness': moneyness, 'spot': position.spot_price},
                confidence_score=0.8,
                execution_steps=[
                    f"1. Buy back {position.main_type} {position.main_strike}",
                    f"2. Sell {position.main_type} {new_strike}",
                    "3. Maintain hedge position if exists"
                ],
                estimated_cost=abs(position.main_current_price - self._estimate_new_strike_price(new_strike)) * position.main_quantity
            )
        
        return None
    
    def _check_expiry_adjustment(self, position: PositionState) -> Optional[AdjustmentRecommendation]:
        """Check if position needs expiry roll"""
        if position.days_to_expiry <= self.thresholds['days_to_roll']:
            # Close or roll to next expiry
            if position.current_pnl > 0:
                # Profitable - consider closing
                return AdjustmentRecommendation(
                    adjustment_type=AdjustmentType.PARTIAL_CLOSE,
                    urgency="IMMEDIATE",
                    current_strike=position.main_strike,
                    current_type=position.main_type,
                    current_quantity=position.main_quantity,
                    current_pnl=position.current_pnl,
                    new_strike=None,
                    new_expiry=None,
                    additional_legs=[],
                    close_quantity=position.main_quantity,
                    expected_pnl_impact=position.current_pnl,
                    expected_risk_reduction=1.0,
                    expected_margin_impact=-position.main_quantity * 50000,
                    breakeven_change=0,
                    max_profit_change=0,
                    max_loss_change=0,
                    trigger_reason=f"Expiry in {position.days_to_expiry} days - close profitable position",
                    market_conditions={'days_to_expiry': position.days_to_expiry},
                    confidence_score=0.95,
                    execution_steps=[
                        f"1. Buy back {position.main_type} {position.main_strike}",
                        "2. Close hedge if exists",
                        "3. Book profit"
                    ],
                    estimated_cost=position.main_current_price * position.main_quantity
                )
            else:
                # Loss - consider rolling
                next_expiry = position.current_time + timedelta(days=7)
                
                return AdjustmentRecommendation(
                    adjustment_type=AdjustmentType.ROLL_EXPIRY,
                    urgency="HIGH",
                    current_strike=position.main_strike,
                    current_type=position.main_type,
                    current_quantity=position.main_quantity,
                    current_pnl=position.current_pnl,
                    new_strike=position.main_strike,
                    new_expiry=next_expiry,
                    additional_legs=[],
                    close_quantity=position.main_quantity,
                    expected_pnl_impact=position.current_pnl * 0.5,
                    expected_risk_reduction=0.2,
                    expected_margin_impact=0,
                    breakeven_change=0,
                    max_profit_change=position.main_entry_price * position.main_quantity * 0.8,
                    max_loss_change=-position.main_entry_price * position.main_quantity * 0.5,
                    trigger_reason=f"Expiry in {position.days_to_expiry} days - roll to next week",
                    market_conditions={'days_to_expiry': position.days_to_expiry},
                    confidence_score=0.7,
                    execution_steps=[
                        f"1. Buy back current week {position.main_type} {position.main_strike}",
                        f"2. Sell next week {position.main_type} {position.main_strike}",
                        "3. Adjust hedge if needed"
                    ],
                    estimated_cost=position.main_current_price * position.main_quantity * 1.2
                )
        
        return None
    
    def _check_greeks_adjustment(self, position: PositionState) -> Optional[AdjustmentRecommendation]:
        """Check if Greeks exposure needs adjustment"""
        # High delta exposure
        if abs(position.net_delta) > self.thresholds['delta_limit']:
            # Add delta hedge
            hedge_quantity = int(abs(position.net_delta) * position.main_quantity * 0.5)
            
            return AdjustmentRecommendation(
                adjustment_type=AdjustmentType.DELTA_HEDGE,
                urgency="MEDIUM",
                current_strike=position.main_strike,
                current_type=position.main_type,
                current_quantity=position.main_quantity,
                current_pnl=position.current_pnl,
                new_strike=None,
                new_expiry=None,
                additional_legs=[{
                    'action': 'BUY',
                    'strike': position.spot_price,
                    'type': position.main_type,
                    'quantity': hedge_quantity
                }],
                close_quantity=0,
                expected_pnl_impact=-hedge_quantity * 50,
                expected_risk_reduction=0.4,
                expected_margin_impact=hedge_quantity * 10000,
                breakeven_change=0,
                max_profit_change=-hedge_quantity * 50,
                max_loss_change=hedge_quantity * 50,
                trigger_reason=f"High delta exposure ({position.net_delta:.2f})",
                market_conditions={'delta': position.net_delta},
                confidence_score=0.75,
                execution_steps=[
                    f"1. Buy {hedge_quantity} qty of ATM {position.main_type}",
                    "2. Monitor combined position Greeks"
                ],
                estimated_cost=hedge_quantity * 100
            )
        
        # High gamma risk
        if abs(position.net_gamma) > 0.02:
            # Convert to spread
            spread_strike = position.main_strike + (200 if position.main_type == 'CE' else -200)
            
            return AdjustmentRecommendation(
                adjustment_type=AdjustmentType.CONVERT_SPREAD,
                urgency="MEDIUM",
                current_strike=position.main_strike,
                current_type=position.main_type,
                current_quantity=position.main_quantity,
                current_pnl=position.current_pnl,
                new_strike=None,
                new_expiry=None,
                additional_legs=[{
                    'action': 'BUY',
                    'strike': spread_strike,
                    'type': position.main_type,
                    'quantity': position.main_quantity
                }],
                close_quantity=0,
                expected_pnl_impact=-position.main_quantity * 30,
                expected_risk_reduction=0.5,
                expected_margin_impact=-position.main_quantity * 20000,
                breakeven_change=20,
                max_profit_change=-position.main_quantity * 30,
                max_loss_change=position.main_quantity * 170,
                trigger_reason=f"High gamma risk ({position.net_gamma:.3f})",
                market_conditions={'gamma': position.net_gamma},
                confidence_score=0.7,
                execution_steps=[
                    f"1. Buy {position.main_type} {spread_strike} as protection",
                    "2. Creates credit spread with defined risk"
                ],
                estimated_cost=position.main_quantity * 30
            )
        
        return None
    
    def _check_profit_protection(self, position: PositionState) -> Optional[AdjustmentRecommendation]:
        """Check if profits need protection"""
        if position.current_pnl > 0 and position.max_pnl > 0:
            profit_ratio = position.current_pnl / position.max_pnl
            
            # Profit declining significantly
            if profit_ratio < self.thresholds['profit_lock_threshold'] and position.max_pnl > 20000:
                # Partial close to lock profits
                close_qty = int(position.main_quantity * 0.5)
                
                return AdjustmentRecommendation(
                    adjustment_type=AdjustmentType.PARTIAL_CLOSE,
                    urgency="HIGH",
                    current_strike=position.main_strike,
                    current_type=position.main_type,
                    current_quantity=position.main_quantity,
                    current_pnl=position.current_pnl,
                    new_strike=None,
                    new_expiry=None,
                    additional_legs=[],
                    close_quantity=close_qty,
                    expected_pnl_impact=position.current_pnl * 0.5,
                    expected_risk_reduction=0.5,
                    expected_margin_impact=-close_qty * 50000,
                    breakeven_change=0,
                    max_profit_change=-position.current_pnl * 0.5,
                    max_loss_change=position.current_pnl * 0.5,
                    trigger_reason=f"Profit declined from peak ({profit_ratio:.1%} of max)",
                    market_conditions={'profit_ratio': profit_ratio, 'max_pnl': position.max_pnl},
                    confidence_score=0.85,
                    execution_steps=[
                        f"1. Buy back {close_qty} qty to lock profit",
                        f"2. Keep {position.main_quantity - close_qty} qty running",
                        "3. Tighten stop loss on remaining"
                    ],
                    estimated_cost=position.main_current_price * close_qty
                )
        
        return None
    
    def _check_loss_mitigation(self, position: PositionState) -> Optional[AdjustmentRecommendation]:
        """Check if losses need mitigation"""
        if position.current_pnl < self.thresholds['loss_limit']:
            # Convert to Iron Condor to limit further loss
            put_strike = position.spot_price - 500
            call_strike = position.spot_price + 500
            
            return AdjustmentRecommendation(
                adjustment_type=AdjustmentType.IRON_CONDOR,
                urgency="IMMEDIATE",
                current_strike=position.main_strike,
                current_type=position.main_type,
                current_quantity=position.main_quantity,
                current_pnl=position.current_pnl,
                new_strike=None,
                new_expiry=None,
                additional_legs=[
                    {
                        'action': 'SELL',
                        'strike': put_strike if position.main_type == 'CE' else call_strike,
                        'type': 'PE' if position.main_type == 'CE' else 'CE',
                        'quantity': position.main_quantity
                    },
                    {
                        'action': 'BUY',
                        'strike': put_strike - 200 if position.main_type == 'CE' else call_strike + 200,
                        'type': 'PE' if position.main_type == 'CE' else 'CE',
                        'quantity': position.main_quantity
                    }
                ],
                close_quantity=0,
                expected_pnl_impact=position.main_quantity * 50,
                expected_risk_reduction=0.6,
                expected_margin_impact=0,
                breakeven_change=0,
                max_profit_change=position.main_quantity * 50,
                max_loss_change=position.main_quantity * 150,
                trigger_reason=f"Loss exceeds limit ({position.current_pnl:,.0f})",
                market_conditions={'current_loss': position.current_pnl},
                confidence_score=0.9,
                execution_steps=[
                    "1. Add opposite side credit spread",
                    "2. Creates Iron Condor with limited risk",
                    "3. Collect additional premium to reduce loss"
                ],
                estimated_cost=-position.main_quantity * 50  # Credit received
            )
        
        return None
    
    def _check_volatility_adjustment(self, position: PositionState) -> Optional[AdjustmentRecommendation]:
        """Check if volatility spike needs adjustment"""
        # This would need historical IV data
        # For now, using current IV as proxy
        if position.implied_volatility > 25:  # High IV
            # Consider ratio spread
            additional_strike = position.main_strike + (300 if position.main_type == 'CE' else -300)
            
            return AdjustmentRecommendation(
                adjustment_type=AdjustmentType.RATIO_SPREAD,
                urgency="LOW",
                current_strike=position.main_strike,
                current_type=position.main_type,
                current_quantity=position.main_quantity,
                current_pnl=position.current_pnl,
                new_strike=None,
                new_expiry=None,
                additional_legs=[{
                    'action': 'SELL',
                    'strike': additional_strike,
                    'type': position.main_type,
                    'quantity': position.main_quantity
                }],
                close_quantity=0,
                expected_pnl_impact=position.main_quantity * 40,
                expected_risk_reduction=-0.2,  # Increases risk
                expected_margin_impact=position.main_quantity * 50000,
                breakeven_change=30,
                max_profit_change=position.main_quantity * 40,
                max_loss_change=-position.main_quantity * 200,  # Increased risk
                trigger_reason=f"High IV ({position.implied_volatility:.1f}%) - collect more premium",
                market_conditions={'iv': position.implied_volatility},
                confidence_score=0.6,
                execution_steps=[
                    f"1. Sell additional {position.main_type} at {additional_strike}",
                    "2. Creates 1:2 ratio spread",
                    "3. Monitor for IV crush"
                ],
                estimated_cost=-position.main_quantity * 40  # Credit
            )
        
        return None
    
    def _calculate_roll_strike(self, position: PositionState) -> float:
        """Calculate new strike for rolling"""
        # Roll to OTM strike
        if position.main_type == 'CE':
            # For CALL, roll higher
            new_strike = max(
                position.spot_price + 100,
                position.main_strike + 200
            )
        else:
            # For PUT, roll lower
            new_strike = min(
                position.spot_price - 100,
                position.main_strike - 200
            )
        
        # Round to nearest 100
        return round(new_strike / 100) * 100
    
    def _estimate_roll_impact(self, position: PositionState, new_strike: float) -> float:
        """Estimate P&L impact of rolling"""
        # Simplified estimate
        strike_distance = abs(new_strike - position.main_strike)
        impact = -strike_distance * 0.5 * position.main_quantity
        
        # Add current P&L
        impact += position.current_pnl * 0.8  # Expect to keep 80% of current profit
        
        return impact
    
    def _estimate_new_strike_price(self, strike: float) -> float:
        """Estimate option price for new strike"""
        # Simplified Black-Scholes approximation
        # In production, would use actual pricing model
        return 100  # Placeholder
    
    def _urgency_score(self, urgency: str) -> int:
        """Convert urgency to numeric score"""
        scores = {
            'IMMEDIATE': 4,
            'HIGH': 3,
            'MEDIUM': 2,
            'LOW': 1
        }
        return scores.get(urgency, 0)
    
    def _no_adjustment_needed(self, position: PositionState) -> AdjustmentRecommendation:
        """Return recommendation when no adjustment needed"""
        return AdjustmentRecommendation(
            adjustment_type=AdjustmentType.PARTIAL_CLOSE,
            urgency="LOW",
            current_strike=position.main_strike,
            current_type=position.main_type,
            current_quantity=position.main_quantity,
            current_pnl=position.current_pnl,
            new_strike=None,
            new_expiry=None,
            additional_legs=[],
            close_quantity=0,
            expected_pnl_impact=0,
            expected_risk_reduction=0,
            expected_margin_impact=0,
            breakeven_change=0,
            max_profit_change=0,
            max_loss_change=0,
            trigger_reason="Position healthy - no adjustment needed",
            market_conditions={
                'spot': position.spot_price,
                'iv': position.implied_volatility,
                'days_to_expiry': position.days_to_expiry
            },
            confidence_score=1.0,
            execution_steps=["Continue monitoring position"],
            estimated_cost=0
        )
    
    def simulate_adjustment(self, 
                           position: PositionState,
                           adjustment: AdjustmentRecommendation) -> Dict:
        """
        Simulate the impact of an adjustment
        
        Args:
            position: Current position
            adjustment: Proposed adjustment
            
        Returns:
            Simulated results
        """
        results = {
            'current_pnl': position.current_pnl,
            'projected_pnl': position.current_pnl + adjustment.expected_pnl_impact,
            'current_risk': self._calculate_risk_score(position),
            'projected_risk': 0,
            'margin_change': adjustment.expected_margin_impact,
            'breakeven_change': adjustment.breakeven_change,
            'max_profit_change': adjustment.max_profit_change,
            'max_loss_change': adjustment.max_loss_change,
            'execution_cost': adjustment.estimated_cost,
            'net_benefit': 0
        }
        
        # Calculate projected risk
        projected_risk = self._calculate_risk_score(position) * (1 - adjustment.expected_risk_reduction)
        results['projected_risk'] = projected_risk
        
        # Calculate net benefit
        pnl_benefit = adjustment.expected_pnl_impact
        risk_benefit = (results['current_risk'] - projected_risk) * 10000  # Risk in rupees
        cost_penalty = -adjustment.estimated_cost
        
        results['net_benefit'] = pnl_benefit + risk_benefit + cost_penalty
        
        return results
    
    def _calculate_risk_score(self, position: PositionState) -> float:
        """Calculate overall risk score for position"""
        risk_score = 0
        
        # Delta risk
        risk_score += abs(position.net_delta) * 2
        
        # Gamma risk
        risk_score += abs(position.net_gamma) * 100
        
        # Time risk
        if position.days_to_expiry < 2:
            risk_score += 2
        elif position.days_to_expiry < 4:
            risk_score += 1
        
        # P&L risk
        if position.current_pnl < -30000:
            risk_score += 3
        elif position.current_pnl < -15000:
            risk_score += 2
        elif position.current_pnl < 0:
            risk_score += 1
        
        # Normalize to 0-1
        return min(1.0, risk_score / 10)