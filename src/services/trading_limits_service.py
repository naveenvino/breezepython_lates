"""
Trading Limits Service
Enforces position limits and risk management rules
"""

import json
from datetime import datetime, time
from typing import Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class TradingLimitsService:
    """Enforces trading limits and risk management"""
    
    def __init__(self):
        self.config_file = Path("trading_limits.json")
        self.state_file = Path("data/trading_state.json")
        self.state_file.parent.mkdir(exist_ok=True)
        
        # Default limits
        self.limits = {
            "max_lots_per_trade": 100,
            "max_concurrent_positions": 5,
            "max_positions_per_signal": 1,
            "max_daily_trades": 50,
            "max_exposure_amount": 1000000,  # 10 lakhs
            "max_loss_per_day": 50000,  # 50k daily loss limit
            "freeze_quantity": 1800,  # NIFTY freeze qty
            "market_hours": {
                "start": "09:15",
                "end": "15:30",
                "days": [0, 1, 2, 3, 4]  # Mon-Fri
            }
        }
        
        # Current state
        self.state = {
            "active_positions": [],
            "daily_trades": 0,
            "daily_pnl": 0,
            "total_exposure": 0,
            "positions_by_signal": {},
            "last_reset": datetime.now().date().isoformat()
        }
        
        self._load_config()
        self._load_state()
    
    def _load_config(self):
        """Load limits configuration"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    self.limits.update(loaded)
            except Exception as e:
                logger.error(f"Error loading limits config: {e}")
    
    def _load_state(self):
        """Load current state"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    loaded = json.load(f)
                    # Reset if new day
                    if loaded.get("last_reset") != datetime.now().date().isoformat():
                        self._reset_daily_state()
                    else:
                        self.state.update(loaded)
            except Exception as e:
                logger.error(f"Error loading state: {e}")
    
    def _save_state(self):
        """Save current state"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def _reset_daily_state(self):
        """Reset daily counters"""
        self.state["daily_trades"] = 0
        self.state["daily_pnl"] = 0
        self.state["last_reset"] = datetime.now().date().isoformat()
        self._save_state()
    
    def is_market_hours(self, test_mode: bool = False) -> bool:
        """Check if current time is within market hours"""
        # Allow bypass for testing
        import os
        if test_mode or os.getenv('BYPASS_MARKET_HOURS') == 'true':
            return True
            
        now = datetime.now()
        
        # Check day of week (0=Monday, 6=Sunday)
        if now.weekday() not in self.limits["market_hours"]["days"]:
            logger.warning(f"Market closed: Weekend ({now.strftime('%A')})")
            return False
        
        # Check time
        current_time = now.time()
        market_start = time.fromisoformat(self.limits["market_hours"]["start"])
        market_end = time.fromisoformat(self.limits["market_hours"]["end"])
        
        if not (market_start <= current_time <= market_end):
            logger.warning(f"Market closed: Outside hours ({current_time.strftime('%H:%M')})")
            return False
        
        return True
    
    def check_lot_size_limit(self, lots: int) -> Dict:
        """Check if lot size is within limits"""
        max_lots = self.limits["max_lots_per_trade"]
        freeze_qty = self.limits["freeze_quantity"]
        
        # First check freeze quantity (absolute limit)
        if lots >= freeze_qty:
            return {
                "allowed": False,
                "reason": f"Lot size {lots} exceeds freeze quantity {freeze_qty}"
            }
        
        # Then check configured max
        if lots > max_lots:
            return {
                "allowed": False,
                "reason": f"Lot size {lots} exceeds maximum {max_lots}"
            }
        
        return {"allowed": True}
    
    def check_concurrent_positions(self) -> Dict:
        """Check if new position is allowed"""
        current_positions = len(self.state["active_positions"])
        max_positions = self.limits["max_concurrent_positions"]
        
        if current_positions >= max_positions:
            return {
                "allowed": False,
                "reason": f"Maximum {max_positions} concurrent positions reached"
            }
        
        return {"allowed": True}
    
    def check_signal_limit(self, signal: str) -> Dict:
        """Check if signal has reached position limit"""
        signal_positions = self.state["positions_by_signal"].get(signal, 0)
        max_per_signal = self.limits["max_positions_per_signal"]
        
        if signal_positions >= max_per_signal:
            return {
                "allowed": False,
                "reason": f"Signal {signal} already has {max_per_signal} position(s)"
            }
        
        return {"allowed": True}
    
    def check_exposure_limit(self, new_exposure: float) -> Dict:
        """Check if new exposure is within limits"""
        total_exposure = self.state["total_exposure"] + new_exposure
        max_exposure = self.limits["max_exposure_amount"]
        
        if total_exposure > max_exposure:
            return {
                "allowed": False,
                "reason": f"Total exposure ₹{total_exposure:,.0f} exceeds limit ₹{max_exposure:,.0f}"
            }
        
        return {"allowed": True}
    
    def check_daily_loss_limit(self) -> Dict:
        """Check if daily loss limit reached"""
        daily_pnl = self.state["daily_pnl"]
        max_loss = -abs(self.limits["max_loss_per_day"])
        
        if daily_pnl < max_loss:
            return {
                "allowed": False,
                "reason": f"Daily loss ₹{abs(daily_pnl):,.0f} exceeds limit ₹{abs(max_loss):,.0f}"
            }
        
        return {"allowed": True}
    
    def validate_new_order(self, order_data: Dict) -> Dict:
        """Validate if new order can be placed"""
        validations = []
        
        # Check market hours (with test mode support)
        test_mode = order_data.get("test_mode", False)
        if not self.is_market_hours(test_mode):
            return {
                "allowed": False,
                "reason": "Market is closed",
                "validations": ["market_hours"]
            }
        
        # Check lot size
        lots = order_data.get("lots", 1)
        lot_check = self.check_lot_size_limit(lots)
        if not lot_check["allowed"]:
            return lot_check
        
        # Check concurrent positions
        position_check = self.check_concurrent_positions()
        if not position_check["allowed"]:
            return position_check
        
        # Check signal limit
        signal = order_data.get("signal")
        if signal:
            signal_check = self.check_signal_limit(signal)
            if not signal_check["allowed"]:
                return signal_check
        
        # Check exposure
        exposure = order_data.get("exposure", lots * 5000)  # Estimate
        exposure_check = self.check_exposure_limit(exposure)
        if not exposure_check["allowed"]:
            return exposure_check
        
        # Check daily loss
        loss_check = self.check_daily_loss_limit()
        if not loss_check["allowed"]:
            return loss_check
        
        return {"allowed": True, "validations": "all_passed"}
    
    def register_position(self, position_data: Dict):
        """Register new position"""
        self.state["active_positions"].append({
            "id": position_data.get("id"),
            "signal": position_data.get("signal"),
            "lots": position_data.get("lots"),
            "exposure": position_data.get("exposure"),
            "timestamp": datetime.now().isoformat()
        })
        
        signal = position_data.get("signal")
        if signal:
            self.state["positions_by_signal"][signal] = \
                self.state["positions_by_signal"].get(signal, 0) + 1
        
        self.state["total_exposure"] += position_data.get("exposure", 0)
        self.state["daily_trades"] += 1
        self._save_state()
    
    def close_position(self, position_id: str, pnl: float = 0):
        """Close position and update state"""
        # Remove from active positions
        self.state["active_positions"] = [
            p for p in self.state["active_positions"] 
            if p.get("id") != position_id
        ]
        
        # Update PnL
        self.state["daily_pnl"] += pnl
        
        # Update exposure
        for pos in self.state["active_positions"]:
            if pos.get("id") == position_id:
                self.state["total_exposure"] -= pos.get("exposure", 0)
                signal = pos.get("signal")
                if signal and signal in self.state["positions_by_signal"]:
                    self.state["positions_by_signal"][signal] -= 1
                break
        
        self._save_state()
    
    def get_current_status(self) -> Dict:
        """Get current trading status"""
        return {
            "market_open": self.is_market_hours(),
            "active_positions": len(self.state["active_positions"]),
            "daily_trades": self.state["daily_trades"],
            "daily_pnl": self.state["daily_pnl"],
            "total_exposure": self.state["total_exposure"],
            "limits": self.limits,
            "can_trade": self.check_daily_loss_limit()["allowed"]
        }

# Singleton instance
_limits_service = None

def get_trading_limits_service() -> TradingLimitsService:
    """Get singleton limits service"""
    global _limits_service
    if _limits_service is None:
        _limits_service = TradingLimitsService()
    return _limits_service