"""
Position Size Validation Service
Ensures trade sizes are within safe limits
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class PositionValidator:
    """
    Validates position sizes and trading parameters
    """
    
    def __init__(self):
        self.min_lots = 1
        self.max_lots = 100
        self.default_lots = 10
        self.lot_size = 75
        self.max_exposure_per_trade = 1000000  # 10 lakh max per trade
        self.min_capital_required = 100000  # 1 lakh minimum
        
    def validate_position_size(
        self, 
        lots: int, 
        premium: float,
        capital: float
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validate position size before trade execution
        
        Args:
            lots: Number of lots to trade
            premium: Option premium per lot
            capital: Available capital
        
        Returns:
            Tuple of (is_valid, message, details)
        """
        try:
            # Check lot size bounds
            if lots < self.min_lots:
                return False, f"Position size {lots} lots below minimum {self.min_lots}", {
                    "requested_lots": lots,
                    "min_lots": self.min_lots
                }
            
            if lots > self.max_lots:
                return False, f"Position size {lots} lots exceeds maximum {self.max_lots}", {
                    "requested_lots": lots,
                    "max_lots": self.max_lots
                }
            
            # Calculate exposure
            total_quantity = lots * self.lot_size
            exposure = total_quantity * premium
            
            # Check exposure limits
            if exposure > self.max_exposure_per_trade:
                return False, f"Exposure {exposure:.0f} exceeds max {self.max_exposure_per_trade:.0f}", {
                    "exposure": exposure,
                    "max_exposure": self.max_exposure_per_trade,
                    "lots": lots,
                    "premium": premium
                }
            
            # Check capital adequacy
            if capital < self.min_capital_required:
                return False, f"Insufficient capital {capital:.0f} < minimum {self.min_capital_required:.0f}", {
                    "available_capital": capital,
                    "min_required": self.min_capital_required
                }
            
            # Check if exposure exceeds available capital
            if exposure > capital:
                return False, f"Exposure {exposure:.0f} exceeds available capital {capital:.0f}", {
                    "exposure": exposure,
                    "available_capital": capital,
                    "lots": lots
                }
            
            # Calculate margin requirement (approx 15% for option selling)
            margin_required = exposure * 0.15
            if margin_required > capital:
                return False, f"Margin required {margin_required:.0f} exceeds capital {capital:.0f}", {
                    "margin_required": margin_required,
                    "available_capital": capital,
                    "lots": lots
                }
            
            # All validations passed
            return True, "Position size valid", {
                "lots": lots,
                "exposure": exposure,
                "margin_required": margin_required,
                "capital_utilization": (margin_required / capital) * 100,
                "within_limits": True
            }
            
        except Exception as e:
            logger.error(f"Error validating position size: {e}")
            return False, f"Validation error: {str(e)}", {}
    
    def suggest_safe_position_size(
        self,
        premium: float,
        capital: float,
        risk_percentage: float = 2.0
    ) -> Dict[str, Any]:
        """
        Suggest a safe position size based on capital and risk
        
        Args:
            premium: Option premium per lot
            capital: Available capital
            risk_percentage: Max risk per trade (default 2%)
        
        Returns:
            Suggested position details
        """
        try:
            # Calculate max risk amount
            max_risk = capital * (risk_percentage / 100)
            
            # Calculate margin per lot (15% of exposure)
            exposure_per_lot = self.lot_size * premium
            margin_per_lot = exposure_per_lot * 0.15
            
            # Calculate lots based on margin
            lots_by_margin = int(capital / margin_per_lot) if margin_per_lot > 0 else 0
            
            # Calculate lots based on max risk
            max_loss_per_lot = premium * self.lot_size * 0.3  # Assume 30% stop loss
            lots_by_risk = int(max_risk / max_loss_per_lot) if max_loss_per_lot > 0 else 0
            
            # Take the minimum of both calculations
            suggested_lots = min(lots_by_margin, lots_by_risk)
            
            # Apply bounds
            suggested_lots = max(self.min_lots, min(suggested_lots, self.max_lots))
            
            # For production start, limit to minimal size
            if suggested_lots > 1:
                logger.info(f"Limiting position to 1 lot for initial production testing")
                suggested_lots = 1
            
            return {
                "suggested_lots": suggested_lots,
                "exposure": suggested_lots * self.lot_size * premium,
                "margin_required": suggested_lots * margin_per_lot,
                "max_loss": suggested_lots * max_loss_per_lot,
                "capital_utilization": (suggested_lots * margin_per_lot / capital) * 100,
                "risk_percentage": (suggested_lots * max_loss_per_lot / capital) * 100
            }
            
        except Exception as e:
            logger.error(f"Error calculating safe position size: {e}")
            return {
                "suggested_lots": self.min_lots,
                "error": str(e)
            }
    
    def validate_trade_parameters(self, params: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate all trade parameters
        
        Args:
            params: Trade parameters to validate
        
        Returns:
            Tuple of (is_valid, message)
        """
        required_fields = ['signal', 'strike', 'option_type', 'lots']
        
        # Check required fields
        for field in required_fields:
            if field not in params or params[field] is None:
                return False, f"Missing required field: {field}"
        
        # Validate signal
        valid_signals = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8']
        if params['signal'] not in valid_signals:
            return False, f"Invalid signal: {params['signal']}"
        
        # Validate option type
        if params['option_type'] not in ['CE', 'PE']:
            return False, f"Invalid option type: {params['option_type']}"
        
        # Validate strike price
        if params['strike'] <= 0 or params['strike'] % 50 != 0:
            return False, f"Invalid strike price: {params['strike']}"
        
        return True, "Parameters valid"


# Singleton instance
_validator = None

def get_position_validator() -> PositionValidator:
    """Get singleton instance of position validator"""
    global _validator
    if _validator is None:
        _validator = PositionValidator()
    return _validator