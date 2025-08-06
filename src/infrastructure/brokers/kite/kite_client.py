"""
Kite Connect API Client Wrapper
Handles low-level API interactions with Zerodha Kite
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from kiteconnect import KiteConnect, KiteTicker
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class KiteClient:
    """
    Wrapper for Kite Connect API providing essential trading functionality
    """
    
    def __init__(self):
        self.api_key = os.getenv('KITE_API_KEY')
        self.api_secret = os.getenv('KITE_API_SECRET')
        self.access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Kite API credentials not found in environment")
        
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite_ticker = None
        
        if self.access_token:
            self.set_access_token(self.access_token)
    
    def set_access_token(self, access_token: str):
        """Set access token for authenticated requests"""
        self.access_token = access_token
        self.kite.set_access_token(access_token)
        logger.info("Kite access token set successfully")
    
    def generate_session(self, request_token: str) -> Dict[str, Any]:
        """Generate access token from request token"""
        try:
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            self.set_access_token(data["access_token"])
            return data
        except Exception as e:
            logger.error(f"Failed to generate session: {e}")
            raise
    
    def get_login_url(self) -> str:
        """Get the login URL for user authentication"""
        return self.kite.login_url()
    
    def place_order(self, **kwargs) -> str:
        """
        Place an order
        Returns order_id on success
        """
        try:
            order_id = self.kite.place_order(**kwargs)
            logger.info(f"Order placed successfully: {order_id}")
            return order_id
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            raise
    
    def modify_order(self, order_id: str, **kwargs) -> str:
        """Modify an existing order"""
        try:
            self.kite.modify_order(order_id=order_id, **kwargs)
            logger.info(f"Order modified successfully: {order_id}")
            return order_id
        except Exception as e:
            logger.error(f"Order modification failed: {e}")
            raise
    
    def cancel_order(self, order_id: str, variety: str = "regular", parent_order_id: Optional[str] = None) -> str:
        """Cancel an order"""
        try:
            self.kite.cancel_order(
                order_id=order_id,
                variety=variety,
                parent_order_id=parent_order_id
            )
            logger.info(f"Order cancelled successfully: {order_id}")
            return order_id
        except Exception as e:
            logger.error(f"Order cancellation failed: {e}")
            raise
    
    def get_orders(self) -> List[Dict[str, Any]]:
        """Fetch all orders for the day"""
        try:
            return self.kite.orders()
        except Exception as e:
            logger.error(f"Failed to fetch orders: {e}")
            raise
    
    def get_order_history(self, order_id: str) -> List[Dict[str, Any]]:
        """Get history of an order"""
        try:
            return self.kite.order_history(order_id)
        except Exception as e:
            logger.error(f"Failed to fetch order history: {e}")
            raise
    
    def get_positions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all positions"""
        try:
            return self.kite.positions()
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            raise
    
    def get_holdings(self) -> List[Dict[str, Any]]:
        """Get holdings"""
        try:
            return self.kite.holdings()
        except Exception as e:
            logger.error(f"Failed to fetch holdings: {e}")
            raise
    
    def get_quote(self, instruments: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get market quotes for instruments
        instruments: List of exchange:tradingsymbol strings (e.g., ['NSE:INFY', 'NFO:NIFTY24DEC1925000CE'])
        """
        try:
            return self.kite.quote(instruments)
        except Exception as e:
            logger.error(f"Failed to fetch quotes: {e}")
            raise
    
    def get_ltp(self, instruments: List[str]) -> Dict[str, Dict[str, float]]:
        """Get last traded price for instruments"""
        try:
            return self.kite.ltp(instruments)
        except Exception as e:
            logger.error(f"Failed to fetch LTP: {e}")
            raise
    
    def get_margins(self) -> Dict[str, Dict[str, Any]]:
        """Get account margins"""
        try:
            return self.kite.margins()
        except Exception as e:
            logger.error(f"Failed to fetch margins: {e}")
            raise
    
    def get_instruments(self, exchange: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get instruments dump"""
        try:
            return self.kite.instruments(exchange)
        except Exception as e:
            logger.error(f"Failed to fetch instruments: {e}")
            raise
    
    def get_option_symbol(self, expiry_date: date, strike: int, option_type: str) -> str:
        """
        Generate NIFTY option symbol for Kite
        Format: NIFTY{YY}{MON}{DD}{STRIKE}{CE/PE}
        Example: NIFTY24DEC1925000CE
        """
        year = expiry_date.strftime('%y')
        # Special month formatting for Kite
        month_map = {
            1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR',
            5: 'MAY', 6: 'JUN', 7: 'JUL', 8: 'AUG',
            9: 'SEP', 10: 'O', 11: 'N', 12: 'D'
        }
        month = month_map[expiry_date.month]
        day = expiry_date.strftime('%d')
        
        return f"NIFTY{year}{month}{day}{strike}{option_type}"
    
    def initialize_ticker(self) -> KiteTicker:
        """Initialize WebSocket ticker for streaming data"""
        if not self.access_token:
            raise ValueError("Access token required for WebSocket connection")
        
        self.kite_ticker = KiteTicker(self.api_key, self.access_token)
        return self.kite_ticker