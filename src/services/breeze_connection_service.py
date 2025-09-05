"""
Breeze API Connection Service - Real broker integration
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from breeze_connect import BreezeConnect
import asyncio
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class BreezeConnectionService:
    """Manages Breeze API connection with auto-reconnect and session management"""
    
    def __init__(self):
        self.api_key = os.getenv('BREEZE_API_KEY')
        self.api_secret = os.getenv('BREEZE_API_SECRET')
        self.session_token = None
        self.breeze = None
        self.is_connected = False
        self.last_connect_time = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.token_file = 'logs/breeze_session.json'
        
    def initialize(self) -> bool:
        """Initialize Breeze connection"""
        try:
            if not self.api_key or not self.api_secret:
                logger.error("Breeze API credentials not found in environment")
                return False
            
            # Initialize Breeze client
            self.breeze = BreezeConnect(api_key=self.api_key)
            
            # Try to load existing session
            if self._load_session():
                if self._validate_session():
                    logger.info("Using existing Breeze session")
                    self.is_connected = True
                    return True
            
            # Generate new session if needed
            logger.info("Generating new Breeze session...")
            return self._generate_session()
            
        except Exception as e:
            logger.error(f"Failed to initialize Breeze connection: {e}")
            return False
    
    def _load_session(self) -> bool:
        """Load saved session token"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    data = json.load(f)
                    
                # Check if session is still valid (less than 24 hours old)
                session_time = datetime.fromisoformat(data.get('timestamp', ''))
                if datetime.now() - session_time < timedelta(hours=23):
                    self.session_token = data.get('session_token')
                    if self.session_token:
                        self.breeze.generate_session(
                            api_secret=self.api_secret,
                            session_token=self.session_token
                        )
                        return True
        except Exception as e:
            logger.debug(f"Could not load session: {e}")
        return False
    
    def _save_session(self):
        """Save session token for reuse"""
        try:
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            with open(self.token_file, 'w') as f:
                json.dump({
                    'session_token': self.session_token,
                    'timestamp': datetime.now().isoformat()
                }, f)
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
    
    def _generate_session(self) -> bool:
        """Generate new session with OTP"""
        try:
            # Get session token from environment or prompt
            session_token = os.getenv('BREEZE_API_SESSION')
            
            if not session_token:
                logger.error("Session token not found. Please set BREEZE_API_SESSION in .env")
                return False
            
            # Generate session
            self.breeze.generate_session(
                api_secret=self.api_secret,
                session_token=session_token
            )
            
            self.session_token = session_token
            self._save_session()
            self.is_connected = True
            self.last_connect_time = datetime.now()
            logger.info("Breeze session generated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate session: {e}")
            return False
    
    def _validate_session(self) -> bool:
        """Validate current session is active"""
        try:
            # Test with a simple API call
            response = self.breeze.get_funds()
            return response.get('Status') == 200
        except:
            return False
    
    async def reconnect(self) -> bool:
        """Reconnect to Breeze API"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return False
        
        self.reconnect_attempts += 1
        logger.info(f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")
        
        # Wait before reconnecting
        await asyncio.sleep(min(self.reconnect_attempts * 2, 30))
        
        if self.initialize():
            self.reconnect_attempts = 0
            return True
        
        return False
    
    def get_client(self) -> Optional[BreezeConnect]:
        """Get Breeze client instance"""
        if self.is_connected:
            return self.breeze
        return None
    
    # Trading Operations
    async def place_order(self, order_data: Dict) -> Dict:
        """Place order with automatic retry on failure"""
        if not self.is_connected:
            if not await self.reconnect():
                return {'success': False, 'message': 'Not connected to broker'}
        
        try:
            response = self.breeze.place_order(**order_data)
            
            if response.get('Status') == 200:
                return {
                    'success': True,
                    'order_id': response['Success'].get('order_id'),
                    'message': 'Order placed successfully',
                    'data': response['Success']
                }
            else:
                return {
                    'success': False,
                    'message': response.get('Error', 'Order placement failed'),
                    'data': response
                }
                
        except Exception as e:
            logger.error(f"Order placement error: {e}")
            # Try reconnecting for next order
            asyncio.create_task(self.reconnect())
            return {
                'success': False,
                'message': str(e)
            }
    
    async def modify_order(self, order_id: str, modifications: Dict) -> Dict:
        """Modify existing order"""
        if not self.is_connected:
            return {'success': False, 'message': 'Not connected to broker'}
        
        try:
            response = self.breeze.modify_order(
                order_id=order_id,
                **modifications
            )
            
            return {
                'success': response.get('Status') == 200,
                'message': response.get('Error', 'Order modified'),
                'data': response.get('Success', {})
            }
        except Exception as e:
            logger.error(f"Order modification error: {e}")
            return {'success': False, 'message': str(e)}
    
    async def cancel_order(self, order_id: str) -> Dict:
        """Cancel order"""
        if not self.is_connected:
            return {'success': False, 'message': 'Not connected to broker'}
        
        try:
            response = self.breeze.cancel_order(
                exchange_code="NSE",
                order_id=order_id
            )
            
            return {
                'success': response.get('Status') == 200,
                'message': 'Order cancelled' if response.get('Status') == 200 else response.get('Error'),
                'data': response.get('Success', {})
            }
        except Exception as e:
            logger.error(f"Order cancellation error: {e}")
            return {'success': False, 'message': str(e)}
    
    # Market Data Operations
    async def get_quotes(self, symbol: str, exchange: str = "NSE") -> Dict:
        """Get real-time quotes"""
        if not self.is_connected:
            return {}
        
        try:
            response = self.breeze.get_quotes(
                stock_code=symbol,
                exchange_code=exchange
            )
            
            if response.get('Status') == 200:
                return response.get('Success', [{}])[0]
            return {}
        except Exception as e:
            logger.error(f"Error fetching quotes: {e}")
            return {}
    
    async def get_option_chain(self, symbol: str, expiry_date: str) -> Dict:
        """Get option chain data"""
        if not self.is_connected:
            return {}
        
        try:
            response = self.breeze.get_option_chain_quotes(
                stock_code=symbol,
                exchange_code="NFO",
                expiry_date=expiry_date
            )
            
            if response.get('Status') == 200:
                return response.get('Success', [])
            return []
        except Exception as e:
            logger.error(f"Error fetching option chain: {e}")
            return []
    
    # Account Operations
    async def get_funds(self) -> Dict:
        """Get account funds"""
        if not self.is_connected:
            return {}
        
        try:
            response = self.breeze.get_funds()
            if response.get('Status') == 200:
                return response.get('Success', {})
            return {}
        except Exception as e:
            logger.error(f"Error fetching funds: {e}")
            return {}
    
    async def get_positions(self) -> list:
        """Get current positions"""
        if not self.is_connected:
            return []
        
        try:
            response = self.breeze.get_portfolio_positions()
            if response.get('Status') == 200:
                return response.get('Success', [])
            return []
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    async def get_order_list(self) -> list:
        """Get order list"""
        if not self.is_connected:
            return []
        
        try:
            response = self.breeze.get_order_list(
                exchange_code="NSE",
                from_date=datetime.now().strftime("%Y-%m-%d"),
                to_date=datetime.now().strftime("%Y-%m-%d")
            )
            
            if response.get('Status') == 200:
                return response.get('Success', [])
            return []
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            return []
    
    # WebSocket Operations
    async def start_websocket(self, symbols: list, callback):
        """Start WebSocket for real-time data"""
        if not self.is_connected:
            return False
        
        try:
            # Subscribe to ticks
            for symbol in symbols:
                self.breeze.subscribe_feeds(
                    exchange_code="NSE",
                    stock_code=symbol,
                    product_type="",
                    expiry_date="",
                    strike_price="",
                    right="",
                    get_exchange_quotes=True,
                    get_market_depth=False
                )
            
            # Set callback
            self.breeze.on_ticks = callback
            
            # Connect WebSocket
            self.breeze.ws_connect()
            logger.info(f"WebSocket connected for symbols: {symbols}")
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            return False
    
    def stop_websocket(self):
        """Stop WebSocket connection"""
        try:
            if self.breeze:
                self.breeze.ws_disconnect()
                logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket disconnection error: {e}")
    
    def get_connection_status(self) -> Dict:
        """Get connection status"""
        return {
            'connected': self.is_connected,
            'last_connect_time': self.last_connect_time.isoformat() if self.last_connect_time else None,
            'reconnect_attempts': self.reconnect_attempts
        }

# Singleton instance
_breeze_service = None

def get_breeze_service() -> BreezeConnectionService:
    global _breeze_service
    if _breeze_service is None:
        _breeze_service = BreezeConnectionService()
        _breeze_service.initialize()
    return _breeze_service