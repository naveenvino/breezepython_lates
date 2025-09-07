"""
Trade Execution Verification Service
Verifies trades are executed correctly and safely
"""

import logging
import json
from datetime import datetime, time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

class TradeExecutionVerifier:
    """
    Verifies trade execution and maintains audit trail
    """
    
    def __init__(self):
        self.verification_log = Path("logs/trade_verification.json")
        self.verification_log.parent.mkdir(exist_ok=True)
        self.verifications = self._load_verifications()
        
    def _load_verifications(self) -> List[Dict[str, Any]]:
        """Load verification history"""
        if self.verification_log.exists():
            try:
                with open(self.verification_log, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading verifications: {e}")
        return []
    
    def _save_verifications(self):
        """Save verification history"""
        try:
            with open(self.verification_log, 'w') as f:
                json.dump(self.verifications, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving verifications: {e}")
    
    def verify_pre_trade(self, trade_params: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Verify conditions before trade execution
        
        Args:
            trade_params: Trade parameters to verify
        
        Returns:
            Tuple of (is_valid, message, details)
        """
        verification = {
            "timestamp": datetime.now().isoformat(),
            "type": "pre_trade",
            "params": trade_params,
            "checks": {}
        }
        
        try:
            # Check market hours
            current_time = datetime.now().time()
            market_open = time(9, 15)
            market_close = time(15, 30)
            
            if current_time < market_open or current_time > market_close:
                verification["checks"]["market_hours"] = False
                verification["result"] = "failed"
                verification["reason"] = "Outside market hours"
                self.verifications.append(verification)
                self._save_verifications()
                return False, "Outside market hours", verification
            
            verification["checks"]["market_hours"] = True
            
            # Check for duplicate trades
            signal = trade_params.get('signal')
            recent_trades = [v for v in self.verifications[-10:] 
                           if v.get('params', {}).get('signal') == signal 
                           and v.get('result') == 'success']
            
            if recent_trades:
                last_trade_time = datetime.fromisoformat(recent_trades[-1]['timestamp'])
                time_diff = (datetime.now() - last_trade_time).seconds
                if time_diff < 300:  # 5 minutes
                    verification["checks"]["duplicate"] = False
                    verification["result"] = "failed"
                    verification["reason"] = f"Duplicate trade within 5 minutes"
                    self.verifications.append(verification)
                    self._save_verifications()
                    return False, "Duplicate trade detected", verification
            
            verification["checks"]["duplicate"] = True
            
            # Check strike price validity
            strike = trade_params.get('strike', 0)
            if strike <= 0 or strike % 50 != 0:
                verification["checks"]["strike_valid"] = False
                verification["result"] = "failed"
                verification["reason"] = f"Invalid strike price: {strike}"
                self.verifications.append(verification)
                self._save_verifications()
                return False, f"Invalid strike price: {strike}", verification
            
            verification["checks"]["strike_valid"] = True
            
            # Check position size
            lots = trade_params.get('lots', 1)
            if lots > 10:  # Max 10 lots for safety
                verification["checks"]["position_size"] = False
                verification["result"] = "failed"
                verification["reason"] = f"Position size {lots} exceeds safety limit"
                self.verifications.append(verification)
                self._save_verifications()
                return False, f"Position size exceeds limit", verification
            
            verification["checks"]["position_size"] = True
            
            # All checks passed
            verification["result"] = "success"
            verification["reason"] = "All pre-trade checks passed"
            self.verifications.append(verification)
            self._save_verifications()
            
            return True, "Pre-trade verification passed", verification
            
        except Exception as e:
            logger.error(f"Error in pre-trade verification: {e}")
            verification["result"] = "error"
            verification["reason"] = str(e)
            self.verifications.append(verification)
            self._save_verifications()
            return False, f"Verification error: {str(e)}", verification
    
    def verify_post_trade(
        self, 
        trade_params: Dict[str, Any],
        execution_result: Dict[str, Any]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Verify trade after execution
        
        Args:
            trade_params: Original trade parameters
            execution_result: Result from execution
        
        Returns:
            Tuple of (is_valid, message, details)
        """
        verification = {
            "timestamp": datetime.now().isoformat(),
            "type": "post_trade",
            "params": trade_params,
            "execution": execution_result,
            "checks": {}
        }
        
        try:
            # Check if order was placed
            if not execution_result.get('order_id'):
                verification["checks"]["order_placed"] = False
                verification["result"] = "failed"
                verification["reason"] = "No order ID received"
                self.verifications.append(verification)
                self._save_verifications()
                return False, "Order placement failed", verification
            
            verification["checks"]["order_placed"] = True
            
            # Check execution price
            executed_price = execution_result.get('price', 0)
            expected_price = trade_params.get('premium', 0)
            
            if executed_price <= 0:
                verification["checks"]["price_valid"] = False
                verification["result"] = "failed"
                verification["reason"] = "Invalid execution price"
                self.verifications.append(verification)
                self._save_verifications()
                return False, "Invalid execution price", verification
            
            # Check for excessive slippage (>5%)
            if expected_price > 0:
                slippage = abs(executed_price - expected_price) / expected_price
                if slippage > 0.05:
                    verification["checks"]["slippage"] = False
                    verification["result"] = "warning"
                    verification["reason"] = f"High slippage: {slippage:.2%}"
                    logger.warning(f"High slippage detected: {slippage:.2%}")
                else:
                    verification["checks"]["slippage"] = True
            
            verification["checks"]["price_valid"] = True
            
            # Check quantity
            executed_qty = execution_result.get('quantity', 0)
            expected_qty = trade_params.get('lots', 1) * 75
            
            if executed_qty != expected_qty:
                verification["checks"]["quantity_match"] = False
                verification["result"] = "warning"
                verification["reason"] = f"Quantity mismatch: expected {expected_qty}, got {executed_qty}"
                logger.warning(f"Quantity mismatch in execution")
            else:
                verification["checks"]["quantity_match"] = True
            
            # Overall result
            if all(verification["checks"].values()):
                verification["result"] = "success"
                verification["reason"] = "Trade executed successfully"
            elif verification["result"] != "failed":
                verification["result"] = "partial"
                verification["reason"] = "Trade executed with warnings"
            
            self.verifications.append(verification)
            self._save_verifications()
            
            return verification["result"] != "failed", verification["reason"], verification
            
        except Exception as e:
            logger.error(f"Error in post-trade verification: {e}")
            verification["result"] = "error"
            verification["reason"] = str(e)
            self.verifications.append(verification)
            self._save_verifications()
            return False, f"Verification error: {str(e)}", verification
    
    def get_verification_summary(self) -> Dict[str, Any]:
        """Get summary of recent verifications"""
        if not self.verifications:
            return {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "warnings": 0
            }
        
        recent = self.verifications[-50:]  # Last 50 verifications
        
        return {
            "total": len(recent),
            "successful": len([v for v in recent if v.get('result') == 'success']),
            "failed": len([v for v in recent if v.get('result') == 'failed']),
            "warnings": len([v for v in recent if v.get('result') in ['warning', 'partial']]),
            "last_verification": recent[-1] if recent else None
        }
    
    def verify_safety_conditions(self) -> Tuple[bool, str]:
        """
        Verify overall safety conditions for trading
        
        Returns:
            Tuple of (is_safe, message)
        """
        try:
            # Check recent failure rate
            recent = self.verifications[-20:]
            if len(recent) >= 5:
                failures = len([v for v in recent if v.get('result') == 'failed'])
                if failures > len(recent) * 0.3:  # >30% failure rate
                    return False, f"High failure rate: {failures}/{len(recent)}"
            
            # Check for repeated errors
            recent_errors = [v for v in recent if v.get('result') == 'error']
            if len(recent_errors) >= 3:
                return False, f"Multiple verification errors detected"
            
            # Check kill switch
            from src.services.emergency_kill_switch import get_kill_switch
            kill_switch = get_kill_switch()
            if kill_switch.triggered:
                return False, "Kill switch is active"
            
            return True, "Safety conditions met"
            
        except Exception as e:
            logger.error(f"Error checking safety conditions: {e}")
            return False, f"Safety check error: {str(e)}"


# Singleton instance
_verifier = None

def get_trade_verifier() -> TradeExecutionVerifier:
    """Get singleton instance of trade verifier"""
    global _verifier
    if _verifier is None:
        _verifier = TradeExecutionVerifier()
    return _verifier