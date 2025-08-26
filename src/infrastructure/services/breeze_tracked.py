"""
Breeze API wrapper with REAL call tracking
NO ESTIMATION - Actual counting of every API call
"""
import logging
from typing import Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TrackedBreezeAPI:
    """
    Wrapper around Breeze API that tracks EVERY call
    """
    
    def __init__(self, breeze_instance):
        """
        Initialize with actual Breeze instance
        
        Args:
            breeze_instance: The actual BreezeConnect instance
        """
        self._breeze = breeze_instance
        self._tracker = None
        self._init_tracker()
    
    def _init_tracker(self):
        """Initialize the rate limit tracker"""
        try:
            from src.infrastructure.services.rate_limit_tracker import get_rate_limit_tracker
            self._tracker = get_rate_limit_tracker()
        except Exception as e:
            logger.error(f"Could not initialize rate limit tracker: {e}")
    
    def _track_call(self, method_name: str, response: Any = None) -> Any:
        """
        Track an API call
        
        Args:
            method_name: Name of the API method called
            response: The response from the API
            
        Returns:
            The response (unchanged)
        """
        if self._tracker:
            try:
                # Always increment - we made a call regardless of response
                self._tracker.increment_calls(1)
                
                # Check if it's a rate limit error
                if isinstance(response, dict):
                    if response.get('Status') == 429 or response.get('Error') == 'Rate Limit Exceeded':
                        logger.error(f"RATE LIMIT HIT on {method_name}!")
                        # Mark as rate limited
                        for _ in range(100000):  # Force rate limit state
                            self._tracker.increment_calls(1)
                            
                count = self._tracker.get_current_count()
                logger.info(f"API CALL TRACKED: {method_name} | Total today: {count}")
                
            except Exception as e:
                logger.error(f"Error tracking API call: {e}")
        
        return response
    
    def _check_rate_limit(self, method_name: str):
        """Check if we're rate limited BEFORE making a call"""
        if self._tracker and self._tracker.is_rate_limited():
            logger.error(f"BLOCKED: {method_name} - Rate limit exceeded")
            raise Exception("API rate limit exceeded. Cannot make any more calls today.")
    
    # Wrap EVERY Breeze API method
    
    def generate_session(self, *args, **kwargs):
        """Track generate_session calls"""
        self._check_rate_limit("generate_session")
        response = self._breeze.generate_session(*args, **kwargs)
        return self._track_call("generate_session", response)
    
    def get_historical_data_v2(self, *args, **kwargs):
        """Track get_historical_data_v2 calls"""
        self._check_rate_limit("get_historical_data_v2")
        response = self._breeze.get_historical_data_v2(*args, **kwargs)
        return self._track_call("get_historical_data_v2", response)
    
    def get_option_chain_quotes(self, *args, **kwargs):
        """Track get_option_chain_quotes calls"""
        self._check_rate_limit("get_option_chain_quotes")
        response = self._breeze.get_option_chain_quotes(*args, **kwargs)
        return self._track_call("get_option_chain_quotes", response)
    
    def get_quotes(self, *args, **kwargs):
        """Track get_quotes calls"""
        self._check_rate_limit("get_quotes")
        response = self._breeze.get_quotes(*args, **kwargs)
        return self._track_call("get_quotes", response)
    
    def place_order(self, *args, **kwargs):
        """Track place_order calls"""
        self._check_rate_limit("place_order")
        response = self._breeze.place_order(*args, **kwargs)
        return self._track_call("place_order", response)
    
    def modify_order(self, *args, **kwargs):
        """Track modify_order calls"""
        self._check_rate_limit("modify_order")
        response = self._breeze.modify_order(*args, **kwargs)
        return self._track_call("modify_order", response)
    
    def cancel_order(self, *args, **kwargs):
        """Track cancel_order calls"""
        self._check_rate_limit("cancel_order")
        response = self._breeze.cancel_order(*args, **kwargs)
        return self._track_call("cancel_order", response)
    
    def get_order_detail(self, *args, **kwargs):
        """Track get_order_detail calls"""
        self._check_rate_limit("get_order_detail")
        response = self._breeze.get_order_detail(*args, **kwargs)
        return self._track_call("get_order_detail", response)
    
    def get_order_list(self, *args, **kwargs):
        """Track get_order_list calls"""
        self._check_rate_limit("get_order_list")
        response = self._breeze.get_order_list(*args, **kwargs)
        return self._track_call("get_order_list", response)
    
    def get_portfolio_positions(self, *args, **kwargs):
        """Track get_portfolio_positions calls"""
        self._check_rate_limit("get_portfolio_positions")
        response = self._breeze.get_portfolio_positions(*args, **kwargs)
        return self._track_call("get_portfolio_positions", response)
    
    def get_portfolio_holdings(self, *args, **kwargs):
        """Track get_portfolio_holdings calls"""
        self._check_rate_limit("get_portfolio_holdings")
        response = self._breeze.get_portfolio_holdings(*args, **kwargs)
        return self._track_call("get_portfolio_holdings", response)
    
    def get_funds(self, *args, **kwargs):
        """Track get_funds calls"""
        self._check_rate_limit("get_funds")
        response = self._breeze.get_funds(*args, **kwargs)
        return self._track_call("get_funds", response)
    
    def square_off(self, *args, **kwargs):
        """Track square_off calls"""
        self._check_rate_limit("square_off")
        response = self._breeze.square_off(*args, **kwargs)
        return self._track_call("square_off", response)
    
    def get_trade_list(self, *args, **kwargs):
        """Track get_trade_list calls"""
        self._check_rate_limit("get_trade_list")
        response = self._breeze.get_trade_list(*args, **kwargs)
        return self._track_call("get_trade_list", response)
    
    def get_trade_detail(self, *args, **kwargs):
        """Track get_trade_detail calls"""
        self._check_rate_limit("get_trade_detail")
        response = self._breeze.get_trade_detail(*args, **kwargs)
        return self._track_call("get_trade_detail", response)
    
    # WebSocket methods (also count as API calls)
    
    def subscribe_feeds(self, *args, **kwargs):
        """Track subscribe_feeds calls"""
        self._check_rate_limit("subscribe_feeds")
        response = self._breeze.subscribe_feeds(*args, **kwargs)
        return self._track_call("subscribe_feeds", response)
    
    def unsubscribe_feeds(self, *args, **kwargs):
        """Track unsubscribe_feeds calls"""
        self._check_rate_limit("unsubscribe_feeds")
        response = self._breeze.unsubscribe_feeds(*args, **kwargs)
        return self._track_call("unsubscribe_feeds", response)
    
    # Pass through any other attributes to the real Breeze instance
    def __getattr__(self, name):
        """Pass through any other method calls with tracking"""
        attr = getattr(self._breeze, name)
        
        # If it's a callable, wrap it with tracking
        if callable(attr):
            def tracked_method(*args, **kwargs):
                self._check_rate_limit(name)
                response = attr(*args, **kwargs)
                return self._track_call(name, response)
            return tracked_method
        
        return attr


def wrap_breeze_with_tracking(breeze_instance):
    """
    Wrap a Breeze instance with tracking
    
    Args:
        breeze_instance: The original BreezeConnect instance
        
    Returns:
        TrackedBreezeAPI instance that tracks all calls
    """
    return TrackedBreezeAPI(breeze_instance)