"""
Emergency Kill Switch Service
Critical safety mechanism for immediate trading halt
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncio

logger = logging.getLogger(__name__)

class EmergencyKillSwitch:
    """
    Emergency kill switch for immediate trading halt
    """
    
    def __init__(self):
        self.kill_switch_file = Path("data/kill_switch_state.json")
        self.kill_switch_file.parent.mkdir(exist_ok=True)
        self.state = self._load_state()
        self.triggered = False
        self.trigger_reason = None
        self.trigger_time = None
        
    def _load_state(self) -> Dict[str, Any]:
        """Load kill switch state from file"""
        if self.kill_switch_file.exists():
            try:
                with open(self.kill_switch_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading kill switch state: {e}")
        
        return {
            "active": False,
            "triggered": False,
            "trigger_reason": None,
            "trigger_time": None,
            "auto_trade_enabled": False,
            "blocked_operations": [],
            "allowed_operations": ["close_positions", "cancel_orders"],
            "history": []
        }
    
    def _save_state(self):
        """Save kill switch state to file"""
        try:
            with open(self.kill_switch_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving kill switch state: {e}")
    
    def trigger(self, reason: str, source: str = "manual") -> Dict[str, Any]:
        """
        Trigger the emergency kill switch
        
        Args:
            reason: Reason for triggering
            source: Source of trigger (manual, auto, system)
        
        Returns:
            Status dict
        """
        try:
            self.triggered = True
            self.trigger_reason = reason
            self.trigger_time = datetime.now()
            
            # Update state
            self.state.update({
                "active": True,
                "triggered": True,
                "trigger_reason": reason,
                "trigger_time": self.trigger_time.isoformat(),
                "auto_trade_enabled": False,
                "blocked_operations": [
                    "new_positions",
                    "increase_positions", 
                    "auto_trading",
                    "webhook_entry"
                ]
            })
            
            # Add to history
            self.state["history"].append({
                "action": "TRIGGERED",
                "reason": reason,
                "source": source,
                "timestamp": self.trigger_time.isoformat()
            })
            
            self._save_state()
            
            # Log critical event
            logger.critical(f"EMERGENCY KILL SWITCH TRIGGERED! Reason: {reason}")
            
            # Disable auto trading
            self._disable_auto_trading()
            
            return {
                "status": "triggered",
                "message": f"Kill switch activated: {reason}",
                "timestamp": self.trigger_time.isoformat(),
                "actions_taken": [
                    "Auto trading disabled",
                    "New positions blocked",
                    "Webhook entries blocked",
                    "Only position closing allowed"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error triggering kill switch: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def reset(self, authorized_by: str = "admin") -> Dict[str, Any]:
        """
        Reset the kill switch (requires authorization)
        
        Args:
            authorized_by: Who authorized the reset
        
        Returns:
            Status dict
        """
        try:
            if not self.triggered:
                return {
                    "status": "not_triggered",
                    "message": "Kill switch is not currently triggered"
                }
            
            # Reset state
            self.triggered = False
            self.trigger_reason = None
            self.trigger_time = None
            
            self.state.update({
                "active": False,
                "triggered": False,
                "trigger_reason": None,
                "trigger_time": None,
                "blocked_operations": []
            })
            
            # Add to history
            self.state["history"].append({
                "action": "RESET",
                "authorized_by": authorized_by,
                "timestamp": datetime.now().isoformat()
            })
            
            self._save_state()
            
            logger.warning(f"Kill switch reset by {authorized_by}")
            
            return {
                "status": "reset",
                "message": "Kill switch has been reset",
                "authorized_by": authorized_by,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error resetting kill switch: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def check_operation_allowed(self, operation: str) -> bool:
        """
        Check if an operation is allowed
        
        Args:
            operation: Operation to check
        
        Returns:
            True if allowed, False if blocked
        """
        if not self.triggered:
            return True
        
        # Check if operation is explicitly blocked
        if operation in self.state.get("blocked_operations", []):
            logger.warning(f"Operation '{operation}' blocked by kill switch")
            return False
        
        # Check if operation is explicitly allowed
        if operation in self.state.get("allowed_operations", []):
            return True
        
        # Default to blocking if kill switch is triggered
        logger.warning(f"Operation '{operation}' blocked by kill switch (default)")
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current kill switch status"""
        return {
            "active": self.triggered,
            "trigger_reason": self.trigger_reason,
            "trigger_time": self.trigger_time.isoformat() if self.trigger_time else None,
            "blocked_operations": self.state.get("blocked_operations", []),
            "allowed_operations": self.state.get("allowed_operations", []),
            "auto_trade_enabled": self.state.get("auto_trade_enabled", False),
            "history": self.state.get("history", [])[-5:]  # Last 5 events
        }
    
    def _disable_auto_trading(self):
        """Disable auto trading in all relevant files"""
        try:
            # Update auto_trade_state.json
            auto_trade_file = Path("auto_trade_state.json")
            if auto_trade_file.exists():
                with open(auto_trade_file, 'r') as f:
                    auto_state = json.load(f)
                
                auto_state["enabled"] = False
                auto_state["kill_switch_triggered"] = True
                auto_state["last_updated"] = datetime.now().isoformat()
                
                with open(auto_trade_file, 'w') as f:
                    json.dump(auto_state, f, indent=2)
                
                logger.info("Auto trading disabled in auto_trade_state.json")
                
        except Exception as e:
            logger.error(f"Error disabling auto trading: {e}")
    
    def check_auto_triggers(self, metrics: Dict[str, Any]) -> Optional[str]:
        """
        Check for automatic trigger conditions
        
        Args:
            metrics: Current trading metrics
        
        Returns:
            Trigger reason if triggered, None otherwise
        """
        # Check for rapid loss
        if metrics.get("loss_rate_per_minute", 0) > 10000:
            return "Rapid loss detected: >10k per minute"
        
        # Check for connection issues
        if metrics.get("failed_orders", 0) > 5:
            return "Multiple order failures detected"
        
        # Check for unusual activity
        if metrics.get("orders_per_minute", 0) > 20:
            return "Unusual trading activity detected"
        
        return None


# Singleton instance
_kill_switch = None

def get_kill_switch() -> EmergencyKillSwitch:
    """Get singleton instance of kill switch"""
    global _kill_switch
    if _kill_switch is None:
        _kill_switch = EmergencyKillSwitch()
    return _kill_switch