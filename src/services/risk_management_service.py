"""
Risk Management Service
Implements position limits, max daily loss, and exposure monitoring
"""

import logging
from datetime import datetime, date, time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class RiskAction(Enum):
    ALLOW = "allow"
    BLOCK = "block"
    WARN = "warn"
    CLOSE_ALL = "close_all"

@dataclass
class RiskLimits:
    """Risk management limits"""
    max_positions: int = 3
    max_daily_loss: float = 50000
    max_position_size: int = 20
    max_exposure: float = 200000
    max_loss_per_trade: float = 15000
    auto_square_off_time: time = time(15, 15)
    enable_auto_square_off: bool = True
    enable_panic_close: bool = True
    panic_loss_threshold: float = 75000

@dataclass
class RiskStatus:
    """Current risk status"""
    open_positions: int
    total_exposure: float
    daily_pnl: float
    daily_loss_percent: float
    max_drawdown: float
    positions_at_risk: List[int]
    risk_level: str
    warnings: List[str]
    can_open_new: bool

class RiskManagementService:
    """
    Manages trading risk with real-time monitoring
    """
    
    def __init__(self):
        self.limits = RiskLimits()
        self.daily_start_capital = 500000
        self.positions = {}
        self.daily_trades = []
        self.daily_pnl = 0
        self.max_daily_drawdown = 0
        self.risk_events = []
        
    def check_position_entry(self, signal_type: str, main_quantity: int, main_price: float,
                           hedge_quantity: int = 0, hedge_price: float = 0) -> Tuple[RiskAction, str]:
        """
        Check if new position can be opened based on risk limits
        Considers NET exposure (main - hedge)
        
        Returns:
            Tuple of (action, message)
        """
        if len(self.positions) >= self.limits.max_positions:
            return RiskAction.BLOCK, f"Max positions limit reached ({self.limits.max_positions})"
        
        if main_quantity > self.limits.max_position_size:
            return RiskAction.BLOCK, f"Position size {main_quantity} exceeds limit ({self.limits.max_position_size})"
        
        # Calculate NET exposure for new position
        main_value = main_quantity * main_price * 75
        hedge_cost = hedge_quantity * hedge_price * 75
        net_exposure = main_value - hedge_cost  # This is actual risk
        
        # Get current NET exposure from all positions
        current_exposure = sum(p.get('net_exposure', p.get('value', 0)) for p in self.positions.values())
        
        if current_exposure + net_exposure > self.limits.max_exposure:
            return RiskAction.BLOCK, f"Would exceed max exposure limit (₹{self.limits.max_exposure:,.0f}). Current: ₹{current_exposure:,.0f}, New: ₹{net_exposure:,.0f}"
        
        if self.daily_pnl <= -self.limits.max_daily_loss:
            return RiskAction.BLOCK, f"Daily loss limit reached (₹{self.limits.max_daily_loss:,.0f})"
        
        if self.daily_pnl <= -self.limits.max_daily_loss * 0.8:
            # Send risk warning alert
            try:
                from src.services.alert_notification_service import get_alert_service
                alert_service = get_alert_service()
                alert_service.send_risk_warning(
                    message=f"Approaching daily loss limit: ₹{abs(self.daily_pnl):,.0f} of ₹{self.limits.max_daily_loss:,.0f}",
                    risk_level="MEDIUM"
                )
            except Exception as e:
                logger.error(f"Failed to send risk warning: {e}")
            
            return RiskAction.WARN, "Approaching daily loss limit (80% reached)"
        
        logger.info(f"Risk check: Positions {len(self.positions)}/{self.limits.max_positions}, Exposure ₹{current_exposure + net_exposure:,.0f}/₹{self.limits.max_exposure:,.0f}, Daily P&L ₹{self.daily_pnl:,.0f}")
        
        return RiskAction.ALLOW, "Risk check passed"
    
    def update_position_risk(self, position_id: int, current_pnl: float) -> RiskAction:
        """
        Update position risk and check for stop loss
        
        Returns:
            Risk action to take
        """
        if position_id not in self.positions:
            return RiskAction.ALLOW
        
        position = self.positions[position_id]
        position['current_pnl'] = current_pnl
        
        if current_pnl <= -self.limits.max_loss_per_trade:
            self._log_risk_event(
                f"Position {position_id} hit max loss limit",
                "stop_loss_triggered"
            )
            return RiskAction.CLOSE_ALL
        
        if self.limits.enable_panic_close and self.daily_pnl <= -self.limits.panic_loss_threshold:
            self._log_risk_event(
                "Panic close triggered - daily loss exceeded threshold",
                "panic_close"
            )
            return RiskAction.CLOSE_ALL
        
        return RiskAction.ALLOW
    
    def get_risk_status(self) -> RiskStatus:
        """
        Get current risk status
        """
        open_positions = len(self.positions)
        total_exposure = sum(p.get('value', 0) for p in self.positions.values())
        current_pnl = sum(p.get('current_pnl', 0) for p in self.positions.values())
        
        daily_loss_percent = (self.daily_pnl / self.daily_start_capital) * 100 if self.daily_start_capital > 0 else 0
        
        positions_at_risk = [
            pid for pid, pos in self.positions.items()
            if pos.get('current_pnl', 0) <= -self.limits.max_loss_per_trade * 0.7
        ]
        
        warnings = []
        if open_positions >= self.limits.max_positions * 0.8:
            warnings.append(f"Near position limit ({open_positions}/{self.limits.max_positions})")
        
        if self.daily_pnl <= -self.limits.max_daily_loss * 0.6:
            warnings.append(f"Daily loss at {abs(daily_loss_percent):.1f}%")
        
        if total_exposure >= self.limits.max_exposure * 0.8:
            warnings.append(f"High exposure: ₹{total_exposure:,.0f}")
        
        risk_level = self._calculate_risk_level(daily_loss_percent, len(positions_at_risk))
        can_open_new = (
            open_positions < self.limits.max_positions and
            self.daily_pnl > -self.limits.max_daily_loss and
            total_exposure < self.limits.max_exposure
        )
        
        return RiskStatus(
            open_positions=open_positions,
            total_exposure=total_exposure,
            daily_pnl=self.daily_pnl,
            daily_loss_percent=daily_loss_percent,
            max_drawdown=self.max_daily_drawdown,
            positions_at_risk=positions_at_risk,
            risk_level=risk_level,
            warnings=warnings,
            can_open_new=can_open_new
        )
    
    def add_position(self, position_id: int, signal_type: str, 
                    main_quantity: int, main_price: float,
                    hedge_quantity: int = 0, hedge_price: float = 0):
        """Add new position to tracking (including hedge)"""
        # Calculate NET exposure (main premium received - hedge premium paid)
        main_value = main_quantity * main_price * 75  # Premium received
        hedge_cost = hedge_quantity * hedge_price * 75  # Premium paid for hedge
        net_exposure = main_value - hedge_cost  # Net premium at risk
        
        self.positions[position_id] = {
            'signal_type': signal_type,
            'main_quantity': main_quantity,
            'main_price': main_price,
            'hedge_quantity': hedge_quantity,
            'hedge_price': hedge_price,
            'main_value': main_value,
            'hedge_cost': hedge_cost,
            'net_exposure': net_exposure,  # This is what we actually risk
            'value': net_exposure,  # Use net exposure for risk calculations
            'current_pnl': 0,
            'entry_time': datetime.now()
        }
        
        self._log_risk_event(
            f"Position {position_id} added: {signal_type} main={main_quantity}@{main_price} hedge={hedge_quantity}@{hedge_price} net_exposure=₹{net_exposure:,.0f}",
            "position_opened"
        )
    
    def remove_position(self, position_id: int, final_pnl: float):
        """Remove closed position and update daily P&L"""
        if position_id in self.positions:
            del self.positions[position_id]
            self.daily_pnl += final_pnl
            self.daily_trades.append({
                'id': position_id,
                'pnl': final_pnl,
                'time': datetime.now()
            })
            
            if self.daily_pnl < self.max_daily_drawdown:
                self.max_daily_drawdown = self.daily_pnl
            
            self._log_risk_event(
                f"Position {position_id} closed: P&L = ₹{final_pnl:,.2f}",
                "position_closed"
            )
    
    def check_auto_square_off(self) -> bool:
        """
        Check if it's time for auto square off
        
        Returns:
            True if should square off all positions
        """
        if not self.limits.enable_auto_square_off:
            return False
        
        current_time = datetime.now().time()
        
        if current_time >= self.limits.auto_square_off_time:
            self._log_risk_event(
                "Auto square-off time reached",
                "auto_square_off"
            )
            return True
        
        return False
    
    def update_limits(self, new_limits: Dict[str, Any]):
        """Update risk limits"""
        for key, value in new_limits.items():
            if hasattr(self.limits, key):
                setattr(self.limits, key, value)
        
        self._log_risk_event(
            f"Risk limits updated: {new_limits}",
            "limits_updated"
        )
    
    def get_limits(self) -> Dict[str, Any]:
        """Get current risk limits"""
        return asdict(self.limits)
    
    def get_risk_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent risk events"""
        return self.risk_events[-limit:]
    
    def reset_daily_tracking(self):
        """Reset daily tracking at start of day"""
        self.daily_pnl = 0
        self.daily_trades = []
        self.max_daily_drawdown = 0
        
        self._log_risk_event(
            "Daily tracking reset",
            "daily_reset"
        )
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive risk metrics
        """
        total_trades = len(self.daily_trades)
        winning_trades = [t for t in self.daily_trades if t['pnl'] > 0]
        losing_trades = [t for t in self.daily_trades if t['pnl'] < 0]
        
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = abs(sum(t['pnl'] for t in losing_trades) / len(losing_trades)) if losing_trades else 0
        
        current_exposure = sum(p.get('value', 0) for p in self.positions.values())
        exposure_percent = (current_exposure / self.daily_start_capital * 100) if self.daily_start_capital > 0 else 0
        
        return {
            'daily_pnl': self.daily_pnl,
            'daily_trades': total_trades,
            'open_positions': len(self.positions),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': self.max_daily_drawdown,
            'current_exposure': current_exposure,
            'exposure_percent': exposure_percent,
            'risk_level': self._calculate_risk_level(
                self.daily_pnl / self.daily_start_capital * 100,
                len([p for p in self.positions.values() if p.get('current_pnl', 0) < 0])
            ),
            'can_trade': self.get_risk_status().can_open_new
        }
    
    def _calculate_risk_level(self, loss_percent: float, positions_at_risk: int) -> str:
        """Calculate overall risk level"""
        if loss_percent <= -5 or positions_at_risk >= 2:
            return "HIGH"
        elif loss_percent <= -3 or positions_at_risk >= 1:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _log_risk_event(self, message: str, event_type: str):
        """Log risk management event"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'message': message
        }
        self.risk_events.append(event)
        logger.info(f"Risk Event: {message}")
        
        if len(self.risk_events) > 1000:
            self.risk_events = self.risk_events[-500:]

_instance = None

def get_risk_management_service() -> RiskManagementService:
    """Get singleton instance"""
    global _instance
    if _instance is None:
        _instance = RiskManagementService()
    return _instance