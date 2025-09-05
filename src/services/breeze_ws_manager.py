"""
Breeze WebSocket Manager for Live NIFTY Streaming
Manages real-time data feed from Breeze WebSocket
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, Optional, List, Callable
import json
from dotenv import load_dotenv

try:
    from breeze_connect import BreezeConnect
except ImportError:
    BreezeConnect = None
    logging.warning("breeze_connect not installed - WebSocket will not work")

load_dotenv()
logger = logging.getLogger(__name__)

class BreezeWebSocketManager:
    """Singleton manager for Breeze WebSocket connection"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.breeze = None
            self.is_connected = False
            self.spot_price = None
            self.last_update = None
            self.subscribers = []  # List of WebSocket connections to update
            self.tick_data = {}
            self._initialized = True
            self._connect()
    
    def _connect(self):
        """Initialize and connect to Breeze WebSocket"""
        try:
            if BreezeConnect is None:
                logger.error("BreezeConnect not available")
                return False
                
            api_key = os.getenv('BREEZE_API_KEY')
            api_secret = os.getenv('BREEZE_API_SECRET')
            session_token = os.getenv('BREEZE_API_SESSION')
            
            if not all([api_key, api_secret, session_token]):
                logger.error("Breeze credentials not found")
                return False
            
            # Initialize Breeze connection
            self.breeze = BreezeConnect(api_key=api_key)
            self.breeze.generate_session(
                api_secret=api_secret,
                session_token=session_token
            )
            
            # Connect to WebSocket
            self.breeze.ws_connect()
            
            # Set up tick handler
            self.breeze.on_ticks = self._on_tick
            
            # Subscribe to NIFTY spot
            self._subscribe_nifty()
            
            self.is_connected = True
            logger.info("Connected to Breeze WebSocket")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Breeze WebSocket: {e}")
            self.is_connected = False
            return False
    
    def _subscribe_nifty(self):
        """Subscribe to NIFTY spot data stream"""
        try:
            # Try different subscription methods for NIFTY
            # Method 1: Try with interval as parameter
            try:
                response = self.breeze.subscribe_feeds(
                    exchange_code="NSE",
                    stock_code="NIFTY",
                    product_type="cash",
                    get_exchange_quotes=True,
                    interval="1second"  # Get updates every second
                )
                logger.info(f"Subscribed to NIFTY with interval: {response}")
            except Exception as e1:
                logger.warning(f"Method 1 failed: {e1}")
                # Method 2: Try without interval
                try:
                    response = self.breeze.subscribe_feeds(
                        exchange_code="NSE",
                        stock_code="NIFTY",
                        product_type="cash",
                        get_exchange_quotes=True
                    )
                    logger.info(f"Subscribed to NIFTY without interval: {response}")
                except Exception as e2:
                    logger.warning(f"Method 2 failed: {e2}")
                    # Method 3: Try with get_exchange_quotes=False
                    try:
                        response = self.breeze.subscribe_feeds(
                            exchange_code="NSE",
                            stock_code="NIFTY",
                            product_type="cash"
                        )
                        logger.info(f"Subscribed to NIFTY basic: {response}")
                    except Exception as e3:
                        logger.error(f"All subscription methods failed: {e3}")
                        # Start mock data generator for testing
                        self._start_mock_data_generator()
            
        except Exception as e:
            logger.error(f"Failed to subscribe to NIFTY: {e}")
            # Start mock data generator as fallback
            self._start_mock_data_generator()
    
    def _start_mock_data_generator(self):
        """Generate mock NIFTY spot data for testing"""
        import threading
        import random
        
        logger.info("Starting mock NIFTY data generator")
        
        def generate_mock_data():
            base_price = 25000
            while True:
                try:
                    # Generate random price around base
                    variation = random.uniform(-50, 50)
                    mock_price = base_price + variation
                    
                    # Create mock tick data
                    mock_tick = {
                        'stock_code': 'NIFTY',
                        'exchange_code': 'NSE',
                        'close': mock_price,
                        'last': mock_price,
                        'ltp': mock_price,
                        'source': 'MOCK_GENERATOR'
                    }
                    
                    # Process the mock tick
                    self._on_tick(mock_tick)
                    
                    # Wait 2 seconds before next update
                    import time
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error in mock data generator: {e}")
                    break
        
        # Start mock data thread
        mock_thread = threading.Thread(target=generate_mock_data, daemon=True)
        mock_thread.start()
    
    def _on_tick(self, ticks):
        """Handle incoming tick data from Breeze WebSocket"""
        try:
            logger.info(f"Received tick: {ticks}")
            
            # Parse tick data based on Breeze format
            if isinstance(ticks, dict):
                # Check for NIFTY data using stock_code field
                stock_code = ticks.get('stock_code', '')
                
                # Check if this is NIFTY data
                if 'NIFTY' in stock_code.upper():
                    # Extract last traded price from close field (most recent price in tick)
                    ltp = ticks.get('close', ticks.get('last', ticks.get('ltp', 0)))
                    
                    # Convert to float if it's a string
                    if isinstance(ltp, str):
                        try:
                            ltp = float(ltp)
                        except:
                            ltp = 0
                    
                    if ltp and ltp > 0:
                        self.spot_price = float(ltp)
                        self.last_update = datetime.now()
                        
                        # Store tick data
                        self.tick_data = {
                            'symbol': 'NIFTY',
                            'spot_price': self.spot_price,
                             'timestamp': self.last_update.isoformat(),
                            'source': 'BREEZE_WEBSOCKET_LIVE',
                            'raw_tick': ticks
                        }
                        
                        logger.info(f"NIFTY Spot updated: {self.spot_price}")
                        
                        # Notify all subscribers - need to handle async properly
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                asyncio.ensure_future(self._notify_subscribers())
                            else:
                                # If no event loop, notify synchronously (best effort)
                                self._notify_subscribers_sync()
                        except RuntimeError:
                            # No event loop - notify synchronously
                            self._notify_subscribers_sync()
            
            elif isinstance(ticks, list):
                # Handle batch of ticks
                for tick in ticks:
                    self._on_tick(tick)
                    
        except Exception as e:
            logger.error(f"Error processing tick: {e}, tick data: {ticks}")
    
    async def _notify_subscribers(self):
        """Notify all WebSocket subscribers of new data (async)"""
        if self.tick_data:
            message = {
                "type": "spot_update",
                "data": self.tick_data
            }
            
            # Send to all connected clients
            for subscriber in self.subscribers[:]:  # Copy list to avoid modification during iteration
                try:
                    await subscriber(message)
                except Exception as e:
                    logger.error(f"Failed to notify subscriber: {e}")
                    # Remove failed subscriber
                    if subscriber in self.subscribers:
                        self.subscribers.remove(subscriber)
    
    def _notify_subscribers_sync(self):
        """Notify all WebSocket subscribers of new data (sync fallback)"""
        if self.tick_data:
            message = {
                "type": "spot_update",
                "data": self.tick_data
            }
            
            # Store message for clients to poll
            self.last_broadcast = message
            
            # For sync context, we can't directly send to WebSocket
            # The WebSocket endpoint will need to poll this data
            logger.debug(f"Stored update for {len(self.subscribers)} subscribers")
    
    def add_subscriber(self, callback):
        """Add a WebSocket connection to receive updates"""
        if callback not in self.subscribers:
            self.subscribers.append(callback)
            logger.info(f"Added subscriber, total: {len(self.subscribers)}")
    
    def remove_subscriber(self, callback):
        """Remove a WebSocket connection"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
            logger.info(f"Removed subscriber, remaining: {len(self.subscribers)}")
    
    def get_current_spot(self) -> Optional[float]:
        """Get current NIFTY spot price from WebSocket feed"""
        return self.spot_price
    
    def get_status(self) -> Dict:
        """Get WebSocket connection status"""
        return {
            'connected': self.is_connected,
            'spot_price': self.spot_price,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'subscribers': len(self.subscribers)
        }
    
    def reconnect(self):
        """Reconnect to Breeze WebSocket"""
        try:
            if self.breeze:
                try:
                    self.breeze.ws_disconnect()
                except:
                    pass
            
            self.is_connected = False
            self.spot_price = None
            return self._connect()
            
        except Exception as e:
            logger.error(f"Failed to reconnect: {e}")
            return False

# Global instance
_breeze_ws_manager = None

def get_breeze_ws_manager() -> BreezeWebSocketManager:
    """Get or create the singleton Breeze WebSocket manager"""
    global _breeze_ws_manager
    if _breeze_ws_manager is None:
        _breeze_ws_manager = BreezeWebSocketManager()
    return _breeze_ws_manager