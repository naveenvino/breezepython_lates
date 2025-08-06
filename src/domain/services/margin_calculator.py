"""
Margin Calculator Service
Calculates SPAN margins for NIFTY options trading
"""
from decimal import Decimal
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MarginRequirement:
    """Margin requirement details for a position"""
    span_margin: Decimal
    exposure_margin: Decimal
    total_margin: Decimal
    notional_value: Decimal
    margin_percentage: float
    

@dataclass
class PortfolioMargin:
    """Total margin requirements for portfolio"""
    total_span: Decimal
    total_exposure: Decimal
    total_margin: Decimal
    available_margin: Decimal
    margin_utilization: float
    can_trade: bool
    message: Optional[str] = None


class MarginCalculator:
    """
    Calculate SPAN margins for NIFTY options
    Based on NSE margin requirements
    """
    
    def __init__(self, lot_size: int = 75):
        self.lot_size = lot_size
        
        # NIFTY option margin parameters (approximate)
        self.span_percentage = 0.03  # 3% base SPAN margin
        self.exposure_percentage = 0.01  # 1% exposure margin
        
        # OTM reduction factors
        self.otm_reduction_factor = 0.7  # 30% reduction for OTM
        self.deep_otm_reduction_factor = 0.5  # 50% reduction for deep OTM
        
    def calculate_option_margin(
        self,
        strike: int,
        option_type: str,
        spot_price: float,
        lots: int,
        option_premium: float = 0
    ) -> MarginRequirement:
        """
        Calculate margin for selling options
        
        Args:
            strike: Strike price
            option_type: 'CE' or 'PE'
            spot_price: Current NIFTY spot price
            lots: Number of lots
            option_premium: Current option premium (reduces margin)
            
        Returns:
            MarginRequirement object with detailed breakdown
        """
        # Calculate notional value
        notional = Decimal(str(spot_price * lots * self.lot_size))
        
        # Calculate moneyness
        if option_type == "CE":
            moneyness = spot_price - strike  # Negative for OTM
        else:  # PE
            moneyness = strike - spot_price  # Negative for OTM
            
        # Base SPAN margin
        span_margin = notional * Decimal(str(self.span_percentage))
        
        # Apply OTM reduction
        if moneyness < 0:  # OTM option
            otm_percentage = abs(moneyness) / spot_price
            
            if otm_percentage > 0.05:  # Deep OTM (> 5%)
                reduction = self.deep_otm_reduction_factor
            elif otm_percentage > 0.02:  # OTM (2-5%)
                reduction = self.otm_reduction_factor
            else:  # Near ATM
                reduction = 0.9  # 10% reduction
                
            span_margin = span_margin * Decimal(str(reduction))
            
        # Reduce margin by option premium received
        if option_premium > 0:
            premium_credit = Decimal(str(option_premium * lots * self.lot_size))
            span_margin = max(span_margin - premium_credit, span_margin * Decimal("0.2"))
            
        # Exposure margin (always fixed percentage)
        exposure_margin = notional * Decimal(str(self.exposure_percentage))
        
        # Total margin
        total_margin = span_margin + exposure_margin
        
        # Calculate margin percentage
        margin_percentage = float(total_margin / notional) * 100
        
        return MarginRequirement(
            span_margin=span_margin,
            exposure_margin=exposure_margin,
            total_margin=total_margin,
            notional_value=notional,
            margin_percentage=margin_percentage
        )
    
    def calculate_hedge_benefit(
        self,
        main_strike: int,
        hedge_strike: int,
        option_type: str,
        spot_price: float,
        lots: int
    ) -> Decimal:
        """
        Calculate margin benefit from hedge position
        
        Selling option with buying protective option reduces margin
        """
        # For a spread, the margin should be based on max loss
        # which is the spread width * lots * lot_size
        spread_width = abs(hedge_strike - main_strike)
        max_loss = Decimal(str(spread_width * lots * self.lot_size))
        
        # The hedge benefit should reduce the margin significantly
        # For spreads, typically only the max loss amount is required as margin
        # So the benefit is the difference between naked margin and max loss
        
        # Calculate naked margin first
        naked_margin = self.calculate_option_margin(
            strike=main_strike,
            option_type=option_type,
            spot_price=spot_price,
            lots=lots
        )
        
        # The hedge benefit is the difference between naked margin and max loss
        # For a spread, you only need to block the max loss amount
        hedge_benefit = naked_margin.span_margin - max_loss
        
        # Ensure benefit is not negative
        return max(hedge_benefit, Decimal("0"))
    
    def calculate_portfolio_margin(
        self,
        positions: List[Dict],
        capital: Decimal,
        existing_margin_blocked: Decimal = Decimal("0")
    ) -> PortfolioMargin:
        """
        Calculate total margin for portfolio of positions
        
        Args:
            positions: List of position dicts with keys:
                - strike, option_type, lots, is_sell, premium
            capital: Available capital
            existing_margin_blocked: Already blocked margin
            
        Returns:
            PortfolioMargin with utilization details
        """
        total_span = Decimal("0")
        total_exposure = Decimal("0")
        
        # Group positions by expiry for spread recognition
        sell_positions = [p for p in positions if p.get("is_sell", True)]
        buy_positions = [p for p in positions if not p.get("is_sell", True)]
        
        # Calculate margin for sell positions
        for pos in sell_positions:
            margin_req = self.calculate_option_margin(
                strike=pos["strike"],
                option_type=pos["option_type"],
                spot_price=pos.get("spot_price", 25000),  # Default if not provided
                lots=pos["lots"],
                option_premium=pos.get("premium", 0)
            )
            
            total_span += margin_req.span_margin
            total_exposure += margin_req.exposure_margin
            
        # Apply hedge benefits if any
        if buy_positions:
            # Simplified: assume first buy position hedges first sell
            # In practice, this would be more sophisticated
            hedge_benefit = Decimal("0")
            
            for sell_pos, buy_pos in zip(sell_positions[:len(buy_positions)], buy_positions):
                if sell_pos["option_type"] == buy_pos["option_type"]:
                    benefit = self.calculate_hedge_benefit(
                        main_strike=sell_pos["strike"],
                        hedge_strike=buy_pos["strike"],
                        option_type=sell_pos["option_type"],
                        spot_price=sell_pos.get("spot_price", 25000),
                        lots=min(sell_pos["lots"], buy_pos["lots"])
                    )
                    hedge_benefit += benefit
                    
            # Reduce SPAN by hedge benefit
            total_span = max(total_span - hedge_benefit, total_span * Decimal("0.2"))
            
        # Total margin required
        total_margin = total_span + total_exposure + existing_margin_blocked
        
        # Available margin
        available_margin = capital - total_margin
        
        # Utilization
        utilization = float(total_margin / capital) * 100 if capital > 0 else 0
        
        # Can trade check
        can_trade = available_margin > capital * Decimal("0.1")  # Keep 10% buffer
        
        message = None
        if not can_trade:
            if utilization >= 100:
                message = f"Margin utilization at {utilization:.1f}%. No margin available."
            else:
                message = f"Insufficient margin buffer. Only {float(available_margin):.0f} available."
                
        return PortfolioMargin(
            total_span=total_span,
            total_exposure=total_exposure,
            total_margin=total_margin,
            available_margin=available_margin,
            margin_utilization=utilization,
            can_trade=can_trade,
            message=message
        )
    
    def get_margin_for_strategy(
        self,
        strategy_type: str,
        spot_price: float,
        strikes: Dict,
        lots: int
    ) -> MarginRequirement:
        """
        Calculate margin for common option strategies
        
        Args:
            strategy_type: 'naked_put', 'naked_call', 'put_spread', 'call_spread'
            spot_price: Current spot price
            strikes: Dict with strike prices (main, hedge)
            lots: Number of lots
            
        Returns:
            MarginRequirement for the strategy
        """
        if strategy_type == "naked_put":
            return self.calculate_option_margin(
                strike=strikes["main"],
                option_type="PE",
                spot_price=spot_price,
                lots=lots
            )
            
        elif strategy_type == "naked_call":
            return self.calculate_option_margin(
                strike=strikes["main"],
                option_type="CE",
                spot_price=spot_price,
                lots=lots
            )
            
        elif strategy_type in ["put_spread", "call_spread"]:
            option_type = "PE" if strategy_type == "put_spread" else "CE"
            
            # Calculate margin for naked position
            naked_margin = self.calculate_option_margin(
                strike=strikes["main"],
                option_type=option_type,
                spot_price=spot_price,
                lots=lots
            )
            
            # Calculate hedge benefit
            hedge_benefit = self.calculate_hedge_benefit(
                main_strike=strikes["main"],
                hedge_strike=strikes["hedge"],
                option_type=option_type,
                spot_price=spot_price,
                lots=lots
            )
            
            # Adjust margins
            adjusted_span = naked_margin.span_margin - hedge_benefit
            adjusted_total = adjusted_span + naked_margin.exposure_margin
            
            return MarginRequirement(
                span_margin=adjusted_span,
                exposure_margin=naked_margin.exposure_margin,
                total_margin=adjusted_total,
                notional_value=naked_margin.notional_value,
                margin_percentage=float(adjusted_total / naked_margin.notional_value) * 100
            )
            
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")