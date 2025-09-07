"""
Production-grade risk management system with position limits and circuit breakers
"""
import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
import threading
import json
from pathlib import Path

from .exceptions import (
    PositionLimitExceededException, RiskLimitException, 
    CircuitBreakerException, InsufficientFundsException,
    MarketClosedException
)

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    """Risk severity levels"""
    LOW = "low"
    MEDIUM = "medium"  
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class RiskLimits:
    """Risk limit configuration"""
    max_position_size: int = 1800  # Maximum position size
    max_daily_loss: float = 50000.0  # Maximum daily loss in Rs
    max_concurrent_positions: int = 3  # Maximum concurrent positions
    max_positions_per_symbol: int = 1  # Maximum positions per symbol
    max_exposure_percentage: float = 80.0  # Maximum portfolio exposure %
    max_single_trade_size: float = 100000.0  # Maximum single trade size
    stop_loss_percentage: float = 30.0  # Default stop loss %
    max_drawdown_percentage: float = 20.0  # Maximum drawdown %
    position_concentration_limit: float = 40.0  # Max % in single position

@dataclass
class Position:
    """Trading position data"""
    symbol: str
    quantity: int
    entry_price: float
    current_price: float
    pnl: float
    position_type: str  # CALL/PUT
    entry_time: datetime
    margin_used: float = 0.0
    
    @property
    def market_value(self) -> float:
        """Current market value of position"""
        return abs(self.quantity * self.current_price)
    
    @property
    def unrealized_pnl(self) -> float:
        """Unrealized P&L"""
        return self.quantity * (self.current_price - self.entry_price)

class RiskManager:
    """Comprehensive risk management system"""
    
    def __init__(self, limits: RiskLimits = None):
        self.limits = limits or RiskLimits()
        self._positions: Dict[str, Position] = {}
        self._daily_pnl = 0.0
        self._total_exposure = 0.0
        self._available_capital = float(os.getenv('INITIAL_CAPITAL', 500000))
        self._circuit_breakers = {}
        self._risk_alerts = []
        self._lock = threading.RLock()
        self._last_reset = date.today()
        
        # Load configuration from environment
        self._load_config()
        
        # Initialize circuit breakers
        self._init_circuit_breakers()
        
        logger.info(f"Risk manager initialized with limits: {self.limits}")
    
    def _load_config(self):
        """Load risk configuration from environment variables"""
        self.limits.max_position_size = int(os.getenv('MAX_POSITION_SIZE', self.limits.max_position_size))
        self.limits.max_daily_loss = float(os.getenv('MAX_DAILY_LOSS', self.limits.max_daily_loss))
        self.limits.max_concurrent_positions = int(os.getenv('MAX_CONCURRENT_POSITIONS', self.limits.max_concurrent_positions))
        self.limits.stop_loss_percentage = float(os.getenv('STOP_LOSS_PERCENTAGE', self.limits.stop_loss_percentage))
        
    def _init_circuit_breakers(self):
        """Initialize circuit breakers"""
        self._circuit_breakers = {
            'daily_loss': {'triggered': False, 'trigger_count': 0, 'last_trigger': None},
            'max_positions': {'triggered': False, 'trigger_count': 0, 'last_trigger': None},
            'exposure_limit': {'triggered': False, 'trigger_count': 0, 'last_trigger': None},
            'drawdown_limit': {'triggered': False, 'trigger_count': 0, 'last_trigger': None}
        }
    
    def _reset_daily_limits(self):
        """Reset daily limits at start of new day"""
        today = date.today()
        if today > self._last_reset:
            with self._lock:
                self._daily_pnl = 0.0
                self._risk_alerts.clear()
                # Reset some circuit breakers
                for breaker in ['daily_loss']:
                    self._circuit_breakers[breaker]['triggered'] = False
                self._last_reset = today
                logger.info("Daily risk limits reset")
    
    def validate_new_position(self, symbol: str, quantity: int, price: float, 
                            position_type: str, margin_required: float = 0.0) -> bool:
        """Validate if new position is within risk limits"""
        
        self._reset_daily_limits()
        
        with self._lock:
            # Check if market is open
            if not self._is_market_open():
                raise MarketClosedException("Market is closed. Cannot place new positions.")
            
            # Check circuit breakers
            self._check_circuit_breakers()
            
            # Calculate position value
            position_value = abs(quantity * price)
            
            # 1. Check maximum position size
            if abs(quantity) > self.limits.max_position_size:
                raise PositionLimitExceededException(
                    f"Position size {abs(quantity)} exceeds limit {self.limits.max_position_size}",
                    abs(quantity), self.limits.max_position_size
                )
            
            # 2. Check maximum concurrent positions
            active_positions = len(self._positions)
            if active_positions >= self.limits.max_concurrent_positions:
                raise PositionLimitExceededException(
                    f"Maximum concurrent positions {self.limits.max_concurrent_positions} reached",
                    active_positions, self.limits.max_concurrent_positions
                )
            
            # 3. Check positions per symbol
            symbol_positions = len([p for p in self._positions.values() if p.symbol == symbol])
            if symbol_positions >= self.limits.max_positions_per_symbol:
                raise PositionLimitExceededException(
                    f"Maximum positions per symbol {self.limits.max_positions_per_symbol} reached for {symbol}",
                    symbol_positions, self.limits.max_positions_per_symbol
                )
            
            # 4. Check single trade size
            if position_value > self.limits.max_single_trade_size:
                raise RiskLimitException(
                    f"Trade size {position_value} exceeds limit {self.limits.max_single_trade_size}",
                    "single_trade_size", position_value, self.limits.max_single_trade_size
                )
            
            # 5. Check total exposure
            new_exposure = self._total_exposure + position_value
            max_exposure = self._available_capital * (self.limits.max_exposure_percentage / 100)
            if new_exposure > max_exposure:
                raise RiskLimitException(
                    f"Total exposure {new_exposure} would exceed limit {max_exposure}",
                    "total_exposure", new_exposure, max_exposure
                )
            
            # 6. Check available capital for margin
            if margin_required > 0 and margin_required > self._available_capital * 0.9:  # 90% of capital
                raise InsufficientFundsException(
                    f"Insufficient capital for margin requirement",
                    margin_required, self._available_capital * 0.9
                )
            
            # 7. Check position concentration
            portfolio_value = self._available_capital + self._daily_pnl
            if portfolio_value > 0:
                concentration = (position_value / portfolio_value) * 100
                if concentration > self.limits.position_concentration_limit:
                    raise RiskLimitException(
                        f"Position concentration {concentration:.1f}% exceeds limit {self.limits.position_concentration_limit}%",
                        "position_concentration", concentration, self.limits.position_concentration_limit
                    )
            
            return True
    
    def add_position(self, position_id: str, symbol: str, quantity: int, 
                    entry_price: float, position_type: str, margin_used: float = 0.0):
        """Add new position to tracking"""
        
        with self._lock:
            position = Position(
                symbol=symbol,
                quantity=quantity,
                entry_price=entry_price,
                current_price=entry_price,  # Initialize with entry price
                pnl=0.0,
                position_type=position_type,
                entry_time=datetime.utcnow(),
                margin_used=margin_used
            )
            
            self._positions[position_id] = position
            self._total_exposure += position.market_value
            
            logger.info(f"Position added: {position_id} - {symbol} {quantity} @ {entry_price}")
            
            # Check if we're approaching limits
            self._check_risk_alerts()
    
    def update_position(self, position_id: str, current_price: float, 
                       unrealized_pnl: float = None):
        """Update existing position with current market data"""
        
        with self._lock:
            if position_id not in self._positions:
                logger.warning(f"Position {position_id} not found for update")
                return
            
            position = self._positions[position_id]
            old_value = position.market_value
            
            position.current_price = current_price
            if unrealized_pnl is not None:
                position.pnl = unrealized_pnl
            else:
                position.pnl = position.unrealized_pnl
            
            # Update total exposure
            new_value = position.market_value
            self._total_exposure = self._total_exposure - old_value + new_value
            
            # Check stop loss
            self._check_stop_loss(position_id, position)
    
    def close_position(self, position_id: str, exit_price: float, realized_pnl: float):
        """Close position and update P&L"""
        
        with self._lock:
            if position_id not in self._positions:
                logger.warning(f"Position {position_id} not found for closing")
                return
            
            position = self._positions[position_id]
            
            # Update daily P&L
            self._daily_pnl += realized_pnl
            
            # Update total exposure
            self._total_exposure -= position.market_value
            
            # Remove position
            del self._positions[position_id]
            
            logger.info(f"Position closed: {position_id} - PnL: {realized_pnl:.2f}")
            
            # Check daily loss limit
            if self._daily_pnl <= -self.limits.max_daily_loss:
                self._trigger_circuit_breaker('daily_loss', 
                    f"Daily loss limit {self.limits.max_daily_loss} exceeded. Current loss: {abs(self._daily_pnl):.2f}")
    
    def _check_stop_loss(self, position_id: str, position: Position):
        """Check if position hits stop loss"""
        
        if self.limits.stop_loss_percentage <= 0:
            return  # Stop loss disabled
        
        # Calculate stop loss level
        stop_loss_amount = (self.limits.stop_loss_percentage / 100) * position.entry_price
        
        # For short positions (typical options selling)
        if position.quantity < 0:
            stop_loss_price = position.entry_price + stop_loss_amount
            if position.current_price >= stop_loss_price:
                logger.warning(f"Stop loss triggered for {position_id}: {position.current_price} >= {stop_loss_price}")
                # Trigger alert - actual closing should be done by trading system
                self._add_risk_alert(RiskLevel.HIGH, f"Stop loss triggered for position {position_id}")
        else:
            # For long positions
            stop_loss_price = position.entry_price - stop_loss_amount
            if position.current_price <= stop_loss_price:
                logger.warning(f"Stop loss triggered for {position_id}: {position.current_price} <= {stop_loss_price}")
                self._add_risk_alert(RiskLevel.HIGH, f"Stop loss triggered for position {position_id}")
    
    def _check_circuit_breakers(self):
        """Check if any circuit breakers are triggered"""
        
        for breaker_name, breaker in self._circuit_breakers.items():
            if breaker['triggered']:
                raise CircuitBreakerException(
                    f"Circuit breaker '{breaker_name}' is active",
                    breaker_name
                )
    
    def _trigger_circuit_breaker(self, breaker_name: str, reason: str):
        """Trigger a circuit breaker"""
        
        with self._lock:
            breaker = self._circuit_breakers[breaker_name]
            breaker['triggered'] = True
            breaker['trigger_count'] += 1
            breaker['last_trigger'] = datetime.utcnow()
            
            logger.critical(f"CIRCUIT BREAKER TRIGGERED: {breaker_name} - {reason}")
            
            # Add critical alert
            self._add_risk_alert(RiskLevel.CRITICAL, f"Circuit breaker triggered: {breaker_name}")
            
            # Close all positions if critical breaker
            if breaker_name in ['daily_loss', 'drawdown_limit']:
                logger.critical("Closing all positions due to critical circuit breaker")
                # This should trigger position closure in the trading system
    
    def _check_risk_alerts(self):
        """Check for risk alert conditions"""
        
        # Check exposure approaching limit
        max_exposure = self._available_capital * (self.limits.max_exposure_percentage / 100)
        exposure_ratio = (self._total_exposure / max_exposure) * 100
        
        if exposure_ratio > 80:  # 80% of limit
            self._add_risk_alert(RiskLevel.HIGH, f"Exposure at {exposure_ratio:.1f}% of limit")
        elif exposure_ratio > 60:  # 60% of limit
            self._add_risk_alert(RiskLevel.MEDIUM, f"Exposure at {exposure_ratio:.1f}% of limit")
        
        # Check daily P&L approaching limit
        if self._daily_pnl < 0:
            loss_ratio = (abs(self._daily_pnl) / self.limits.max_daily_loss) * 100
            if loss_ratio > 80:  # 80% of daily loss limit
                self._add_risk_alert(RiskLevel.HIGH, f"Daily loss at {loss_ratio:.1f}% of limit")
            elif loss_ratio > 60:  # 60% of daily loss limit
                self._add_risk_alert(RiskLevel.MEDIUM, f"Daily loss at {loss_ratio:.1f}% of limit")
    
    def _add_risk_alert(self, level: RiskLevel, message: str):
        """Add risk alert"""
        
        alert = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level.value,
            'message': message
        }
        
        self._risk_alerts.append(alert)
        
        # Keep only last 100 alerts
        if len(self._risk_alerts) > 100:
            self._risk_alerts = self._risk_alerts[-100:]
        
        # Log alert
        log_level = {
            RiskLevel.LOW: logging.INFO,
            RiskLevel.MEDIUM: logging.WARNING,
            RiskLevel.HIGH: logging.ERROR,
            RiskLevel.CRITICAL: logging.CRITICAL
        }.get(level, logging.WARNING)
        
        logger.log(log_level, f"RISK ALERT [{level.value.upper()}]: {message}")
    
    def _is_market_open(self) -> bool:
        """Check if market is currently open"""
        
        now = datetime.now()
        
        # Simple market hours check (9:15 AM to 3:30 PM IST, Mon-Fri)
        if now.weekday() >= 5:  # Weekend
            return False
        
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    
    def reset_circuit_breaker(self, breaker_name: str) -> bool:
        """Reset a specific circuit breaker"""
        
        with self._lock:
            if breaker_name in self._circuit_breakers:
                self._circuit_breakers[breaker_name]['triggered'] = False
                logger.info(f"Circuit breaker {breaker_name} reset")
                return True
            return False
    
    def get_risk_status(self) -> Dict[str, Any]:
        """Get current risk status"""
        
        self._reset_daily_limits()
        
        with self._lock:
            max_exposure = self._available_capital * (self.limits.max_exposure_percentage / 100)
            
            return {
                'positions': {
                    'count': len(self._positions),
                    'limit': self.limits.max_concurrent_positions,
                    'utilization': (len(self._positions) / self.limits.max_concurrent_positions) * 100
                },
                'exposure': {
                    'current': self._total_exposure,
                    'limit': max_exposure,
                    'utilization': (self._total_exposure / max_exposure) * 100 if max_exposure > 0 else 0
                },
                'daily_pnl': {
                    'current': self._daily_pnl,
                    'limit': -self.limits.max_daily_loss,
                    'utilization': (abs(self._daily_pnl) / self.limits.max_daily_loss) * 100 if self._daily_pnl < 0 else 0
                },
                'circuit_breakers': self._circuit_breakers,
                'recent_alerts': self._risk_alerts[-10:],  # Last 10 alerts
                'market_open': self._is_market_open(),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def get_position_details(self) -> List[Dict[str, Any]]:
        """Get detailed position information"""
        
        with self._lock:
            return [
                {
                    'position_id': pos_id,
                    'symbol': pos.symbol,
                    'quantity': pos.quantity,
                    'entry_price': pos.entry_price,
                    'current_price': pos.current_price,
                    'market_value': pos.market_value,
                    'unrealized_pnl': pos.pnl,
                    'position_type': pos.position_type,
                    'entry_time': pos.entry_time.isoformat(),
                    'margin_used': pos.margin_used
                }
                for pos_id, pos in self._positions.items()
            ]
    
    def save_state(self, file_path: str = None):
        """Save risk manager state to file"""
        
        if not file_path:
            file_path = Path("data") / "risk_manager_state.json"
        
        state = {
            'positions': {
                pos_id: {
                    'symbol': pos.symbol,
                    'quantity': pos.quantity,
                    'entry_price': pos.entry_price,
                    'current_price': pos.current_price,
                    'pnl': pos.pnl,
                    'position_type': pos.position_type,
                    'entry_time': pos.entry_time.isoformat(),
                    'margin_used': pos.margin_used
                }
                for pos_id, pos in self._positions.items()
            },
            'daily_pnl': self._daily_pnl,
            'total_exposure': self._total_exposure,
            'circuit_breakers': self._circuit_breakers,
            'last_reset': self._last_reset.isoformat(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        Path(file_path).parent.mkdir(exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        
        logger.info(f"Risk manager state saved to {file_path}")

# Global risk manager instance
_risk_manager: Optional[RiskManager] = None

def get_risk_manager() -> RiskManager:
    """Get global risk manager instance"""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
    return _risk_manager