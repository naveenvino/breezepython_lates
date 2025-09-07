"""
Circuit Breaker Pattern for External Service Calls
Prevents cascading failures and provides graceful degradation
"""

import time
from typing import Any, Callable, Optional, Dict
from enum import Enum
from threading import Lock
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"      # Circuit tripped, rejecting calls
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered

class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        success_threshold: int = 2
    ):
        """
        Initialize circuit breaker
        
        Args:
            name: Name of the service
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open
            expected_exception: Exception type to catch
            success_threshold: Successes needed in half-open to close circuit
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self._lock = Lock()
        
        # Metrics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.circuit_open_count = 0
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        with self._lock:
            self.total_calls += 1
            
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit {self.name} entering HALF_OPEN state")
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit {self.name} is OPEN. Service unavailable."
                    )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    async def async_call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute async function through circuit breaker
        """
        with self._lock:
            self.total_calls += 1
            
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit {self.name} entering HALF_OPEN state")
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit {self.name} is OPEN. Service unavailable."
                    )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            self.total_successes += 1
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    logger.info(f"Circuit {self.name} closed after recovery")
            else:
                self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call"""
        with self._lock:
            self.total_failures += 1
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.circuit_open_count += 1
                logger.warning(f"Circuit {self.name} reopened after test failure")
                
            elif self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.circuit_open_count += 1
                logger.error(
                    f"Circuit {self.name} opened after {self.failure_count} failures"
                )
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try reset"""
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def reset(self):
        """Manually reset the circuit"""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            logger.info(f"Circuit {self.name} manually reset")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit state and metrics"""
        with self._lock:
            return {
                'name': self.name,
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'total_calls': self.total_calls,
                'total_failures': self.total_failures,
                'total_successes': self.total_successes,
                'circuit_open_count': self.circuit_open_count,
                'success_rate': (
                    self.total_successes / self.total_calls 
                    if self.total_calls > 0 else 0
                ),
                'last_failure_time': (
                    datetime.fromtimestamp(self.last_failure_time).isoformat()
                    if self.last_failure_time else None
                )
            }

class CircuitBreakerOpen(Exception):
    """Exception raised when circuit is open"""
    pass

class CircuitBreakerManager:
    """Manages multiple circuit breakers for different services"""
    
    def __init__(self):
        self.breakers = {}
        self._lock = Lock()
    
    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        success_threshold: int = 2
    ) -> CircuitBreaker:
        """
        Get existing circuit breaker or create new one
        """
        with self._lock:
            if name not in self.breakers:
                self.breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    recovery_timeout=recovery_timeout,
                    expected_exception=expected_exception,
                    success_threshold=success_threshold
                )
            return self.breakers[name]
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all circuit breakers"""
        with self._lock:
            return {
                name: breaker.get_state()
                for name, breaker in self.breakers.items()
            }
    
    def reset_all(self):
        """Reset all circuit breakers"""
        with self._lock:
            for breaker in self.breakers.values():
                breaker.reset()
    
    def reset(self, name: str):
        """Reset specific circuit breaker"""
        with self._lock:
            if name in self.breakers:
                self.breakers[name].reset()

# Global circuit breaker manager
circuit_manager = CircuitBreakerManager()

# Pre-configured circuit breakers for common services
def get_breeze_circuit() -> CircuitBreaker:
    """Get circuit breaker for Breeze API"""
    return circuit_manager.get_or_create(
        name="breeze_api",
        failure_threshold=3,
        recovery_timeout=30,
        success_threshold=2
    )

def get_kite_circuit() -> CircuitBreaker:
    """Get circuit breaker for Kite API"""
    return circuit_manager.get_or_create(
        name="kite_api",
        failure_threshold=3,
        recovery_timeout=30,
        success_threshold=2
    )

def get_database_circuit() -> CircuitBreaker:
    """Get circuit breaker for database operations"""
    return circuit_manager.get_or_create(
        name="database",
        failure_threshold=5,
        recovery_timeout=10,
        success_threshold=3
    )