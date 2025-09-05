"""
Slippage Management Service
Handles latency tracking and slippage control for trade execution
"""

import time
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class SlippageAction(Enum):
    EXECUTE = "execute"
    REJECT = "reject"
    REQUOTE = "requote"
    PARTIAL = "partial"

@dataclass
class SlippageConfig:
    """Configuration for slippage tolerance"""
    max_slippage_percent: float = 0.5  # 0.5% max slippage
    max_slippage_points: float = 10.0  # 10 points max for NIFTY options
    max_latency_ms: int = 500  # 500ms max latency
    requote_threshold_percent: float = 0.3  # Requote if slippage > 0.3%
    partial_fill_threshold: float = 0.2  # Allow partial fill if slippage > 0.2%

@dataclass
class LatencyMetrics:
    """Track latency at each step"""
    signal_received_at: datetime
    validation_completed_at: Optional[datetime] = None
    broker_request_at: Optional[datetime] = None
    broker_response_at: Optional[datetime] = None
    total_latency_ms: Optional[int] = None

class SlippageManager:
    """Manages slippage and latency for trade execution"""
    
    def __init__(self, config: Optional[SlippageConfig] = None):
        self.config = config or SlippageConfig()
        self.latency_history = []
        self.slippage_history = []
        self.rejection_count = 0
        
    def check_slippage(
        self, 
        signal_price: float, 
        current_price: float,
        option_type: str
    ) -> Tuple[SlippageAction, Dict]:
        """
        Check if slippage is within acceptable limits
        
        Returns:
            Tuple of (action, details)
        """
        # Calculate slippage
        slippage_points = abs(current_price - signal_price)
        slippage_percent = (slippage_points / signal_price) * 100
        
        # Determine if slippage is favorable
        is_favorable = self._is_favorable_slippage(
            signal_price, current_price, option_type
        )
        
        # Decide action based on slippage
        if is_favorable:
            # Favorable slippage is always accepted
            return SlippageAction.EXECUTE, {
                "slippage_points": slippage_points,
                "slippage_percent": slippage_percent,
                "favorable": True,
                "message": "Favorable slippage, executing immediately"
            }
        
        # Check against max limits
        if slippage_percent > self.config.max_slippage_percent:
            self.rejection_count += 1
            return SlippageAction.REJECT, {
                "slippage_points": slippage_points,
                "slippage_percent": slippage_percent,
                "favorable": False,
                "message": f"Slippage {slippage_percent:.2f}% exceeds max {self.config.max_slippage_percent}%",
                "rejection_count": self.rejection_count
            }
        
        if slippage_points > self.config.max_slippage_points:
            self.rejection_count += 1
            return SlippageAction.REJECT, {
                "slippage_points": slippage_points,
                "slippage_percent": slippage_percent,
                "favorable": False,
                "message": f"Slippage {slippage_points} points exceeds max {self.config.max_slippage_points}",
                "rejection_count": self.rejection_count
            }
        
        # Check if requote needed
        if slippage_percent > self.config.requote_threshold_percent:
            return SlippageAction.REQUOTE, {
                "slippage_points": slippage_points,
                "slippage_percent": slippage_percent,
                "favorable": False,
                "message": "Slippage requires requote",
                "suggested_price": current_price
            }
        
        # Check if partial fill recommended
        if slippage_percent > self.config.partial_fill_threshold:
            return SlippageAction.PARTIAL, {
                "slippage_points": slippage_points,
                "slippage_percent": slippage_percent,
                "favorable": False,
                "message": "Consider partial fill due to slippage",
                "suggested_quantity_percent": 50  # Execute 50% of intended quantity
            }
        
        # Within acceptable limits
        return SlippageAction.EXECUTE, {
            "slippage_points": slippage_points,
            "slippage_percent": slippage_percent,
            "favorable": False,
            "message": "Slippage within acceptable limits"
        }
    
    def _is_favorable_slippage(
        self, 
        signal_price: float, 
        current_price: float,
        option_type: str
    ) -> bool:
        """
        Check if slippage is in our favor
        For SELL orders: Higher price is better
        """
        # Since we're selling options (as per signals S1-S8)
        # Higher price is favorable
        return current_price > signal_price
    
    def track_latency(self, metrics: LatencyMetrics) -> bool:
        """
        Track latency and determine if within limits
        
        Returns:
            True if latency is acceptable, False otherwise
        """
        if metrics.broker_response_at and metrics.signal_received_at:
            total_latency = (metrics.broker_response_at - metrics.signal_received_at).total_seconds() * 1000
            metrics.total_latency_ms = int(total_latency)
            
            # Store in history
            self.latency_history.append({
                "timestamp": datetime.now(),
                "latency_ms": metrics.total_latency_ms,
                "breakdown": {
                    "validation": self._calculate_step_latency(
                        metrics.signal_received_at, 
                        metrics.validation_completed_at
                    ),
                    "broker_request": self._calculate_step_latency(
                        metrics.validation_completed_at,
                        metrics.broker_request_at
                    ),
                    "broker_response": self._calculate_step_latency(
                        metrics.broker_request_at,
                        metrics.broker_response_at
                    )
                }
            })
            
            # Keep only last 100 entries
            if len(self.latency_history) > 100:
                self.latency_history = self.latency_history[-100:]
            
            # Check if within limits
            if metrics.total_latency_ms > self.config.max_latency_ms:
                logger.warning(
                    f"High latency detected: {metrics.total_latency_ms}ms "
                    f"(max: {self.config.max_latency_ms}ms)"
                )
                return False
            
            return True
        
        return True
    
    def _calculate_step_latency(
        self, 
        start: Optional[datetime], 
        end: Optional[datetime]
    ) -> Optional[int]:
        """Calculate latency between two timestamps"""
        if start and end:
            return int((end - start).total_seconds() * 1000)
        return None
    
    def get_average_latency(self) -> Dict:
        """Get average latency statistics"""
        if not self.latency_history:
            return {"average_ms": 0, "samples": 0}
        
        latencies = [h["latency_ms"] for h in self.latency_history]
        return {
            "average_ms": sum(latencies) / len(latencies),
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "samples": len(latencies),
            "last_10_avg": sum(latencies[-10:]) / min(10, len(latencies))
        }
    
    def get_slippage_stats(self) -> Dict:
        """Get slippage statistics"""
        if not self.slippage_history:
            return {
                "average_percent": 0,
                "max_percent": 0,
                "rejection_rate": 0
            }
        
        total_attempts = len(self.slippage_history) + self.rejection_count
        return {
            "average_percent": sum(s["percent"] for s in self.slippage_history) / len(self.slippage_history),
            "max_percent": max(s["percent"] for s in self.slippage_history),
            "favorable_count": sum(1 for s in self.slippage_history if s.get("favorable")),
            "rejection_rate": (self.rejection_count / total_attempts * 100) if total_attempts > 0 else 0,
            "total_trades": len(self.slippage_history),
            "total_rejections": self.rejection_count
        }
    
    def record_slippage(self, signal_price: float, execution_price: float, option_type: str):
        """Record actual slippage after trade execution"""
        slippage_points = execution_price - signal_price
        slippage_percent = (abs(slippage_points) / signal_price) * 100
        is_favorable = self._is_favorable_slippage(signal_price, execution_price, option_type)
        
        self.slippage_history.append({
            "timestamp": datetime.now(),
            "signal_price": signal_price,
            "execution_price": execution_price,
            "points": slippage_points,
            "percent": slippage_percent,
            "favorable": is_favorable,
            "option_type": option_type
        })
        
        # Keep only last 100 entries
        if len(self.slippage_history) > 100:
            self.slippage_history = self.slippage_history[-100:]
    
    def should_pause_trading(self) -> Tuple[bool, str]:
        """
        Determine if trading should be paused due to poor metrics
        
        Returns:
            Tuple of (should_pause, reason)
        """
        # Check rejection rate
        stats = self.get_slippage_stats()
        if stats["rejection_rate"] > 30:  # More than 30% rejections
            return True, f"High rejection rate: {stats['rejection_rate']:.1f}%"
        
        # Check average latency
        latency_stats = self.get_average_latency()
        if latency_stats["samples"] > 5 and latency_stats["last_10_avg"] > self.config.max_latency_ms * 1.5:
            return True, f"Sustained high latency: {latency_stats['last_10_avg']:.0f}ms"
        
        # Check max slippage
        if stats["max_percent"] > self.config.max_slippage_percent * 2:
            return True, f"Extreme slippage detected: {stats['max_percent']:.2f}%"
        
        return False, "Metrics within acceptable range"

# Singleton instance
_slippage_manager = None

def get_slippage_manager() -> SlippageManager:
    """Get singleton instance of SlippageManager"""
    global _slippage_manager
    if _slippage_manager is None:
        _slippage_manager = SlippageManager()
    return _slippage_manager