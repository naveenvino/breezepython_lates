"""
Kite WebSocket Service for Real-time Market Data
Handles live streaming of NIFTY spot, options prices, and order updates
"""
import logging
import asyncio
import json
from typing import Dict, List, Optional, Callable, Set
from datetime import datetime
from kiteconnect import KiteTicker
import os
from dotenv import load_dotenv
import threading
from collections import defaultdict

load_dotenv()
logger = logging.getLogger(__name__)

class KiteWebSocketService:
    """
    Manages Kite WebSocket connection for real-time market data streaming
    """
    
    def __init__(self):
        self.api_key = os.getenv('KITE_API_KEY')
        self.access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        if not self.api_key or not self.access_token:
            raise ValueError("Kite API credentials not found")
        
        self.kite_ticker = None
        self.subscribers = defaultdict(set)  # instrument_token -> set of callbacks
        self.instrument_tokens = {}  # symbol -> token mapping
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # seconds
        
        # Predefined instrument tokens for common symbols
        # These need to be fetched from instruments list ideally
        self.INSTRUMENT_TOKENS = {
            'NIFTY': 256265,  # NIFTY 50 index
            'BANKNIFTY': 260105,  # BANK NIFTY index
            'INDIA VIX': 264969,  # Volatility index
        }
        
        # Store latest quotes
        self.latest_quotes = {}
        
        # WebSocket callbacks
        self.on_tick_callbacks = []
        self.on_connect_callbacks = []
        self.on_error_callbacks = []
        
    def initialize(self):
        """Initialize the KiteTicker WebSocket connection"""
        try:
            self.kite_ticker = KiteTicker(self.api_key, self.access_token)
            
            # Assign callbacks
            self.kite_ticker.on_ticks = self._on_ticks
            self.kite_ticker.on_connect = self._on_connect
            self.kite_ticker.on_close = self._on_close
            self.kite_ticker.on_error = self._on_error
            self.kite_ticker.on_reconnect = self._on_reconnect
            self.kite_ticker.on_noreconnect = self._on_noreconnect
            self.kite_ticker.on_order_update = self._on_order_update
            
            logger.info("KiteTicker initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize KiteTicker: {e}")
            return False
    
    def start(self):
        """Start the WebSocket connection in a separate thread"""
        if not self.kite_ticker:
            if not self.initialize():
                return False
        
        try:
            # Start ticker in a separate thread
            ticker_thread = threading.Thread(target=self._run_ticker, daemon=True)
            ticker_thread.start()
            logger.info("Kite WebSocket started in background thread")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Kite WebSocket: {e}")
            return False
    
    def _run_ticker(self):
        """Run the ticker in blocking mode"""
        try:
            self.kite_ticker.connect(threaded=False)
        except Exception as e:
            logger.error(f"Ticker connection error: {e}")
            self.is_connected = False
    
    def stop(self):
        """Stop the WebSocket connection"""
        if self.kite_ticker and self.is_connected:
            try:
                self.kite_ticker.close()
                self.is_connected = False
                logger.info("Kite WebSocket stopped")
            except Exception as e:
                logger.error(f"Error stopping Kite WebSocket: {e}")
    
    def subscribe_instruments(self, instrument_tokens: List[int], mode: str = "full"):
        """
        Subscribe to instrument updates
        
        Args:
            instrument_tokens: List of instrument tokens to subscribe
            mode: Subscription mode - "ltp", "quote", or "full"
        """
        if not self.is_connected:
            logger.warning("WebSocket not connected, cannot subscribe")
            return False
        
        try:
            self.kite_ticker.subscribe(instrument_tokens)
            
            # Set mode
            if mode == "ltp":
                self.kite_ticker.set_mode(self.kite_ticker.MODE_LTP, instrument_tokens)
            elif mode == "quote":
                self.kite_ticker.set_mode(self.kite_ticker.MODE_QUOTE, instrument_tokens)
            else:  # full
                self.kite_ticker.set_mode(self.kite_ticker.MODE_FULL, instrument_tokens)
            
            logger.info(f"Subscribed to {len(instrument_tokens)} instruments in {mode} mode")
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe instruments: {e}")
            return False
    
    def unsubscribe_instruments(self, instrument_tokens: List[int]):
        """Unsubscribe from instrument updates"""
        if not self.is_connected:
            return
        
        try:
            self.kite_ticker.unsubscribe(instrument_tokens)
            logger.info(f"Unsubscribed from {len(instrument_tokens)} instruments")
        except Exception as e:
            logger.error(f"Failed to unsubscribe instruments: {e}")
    
    def subscribe_nifty(self, callback: Optional[Callable] = None):
        """Subscribe to NIFTY 50 spot price updates"""
        token = self.INSTRUMENT_TOKENS.get('NIFTY')
        if token:
            if callback:
                self.subscribers[token].add(callback)
            return self.subscribe_instruments([token], mode="ltp")
        return False
    
    def subscribe_banknifty(self, callback: Optional[Callable] = None):
        """Subscribe to BANK NIFTY spot price updates"""
        token = self.INSTRUMENT_TOKENS.get('BANKNIFTY')
        if token:
            if callback:
                self.subscribers[token].add(callback)
            return self.subscribe_instruments([token], mode="ltp")
        return False
    
    def subscribe_option(self, symbol: str, instrument_token: int, 
                        callback: Optional[Callable] = None, mode: str = "full"):
        """Subscribe to specific option contract"""
        self.instrument_tokens[symbol] = instrument_token
        if callback:
            self.subscribers[instrument_token].add(callback)
        return self.subscribe_instruments([instrument_token], mode=mode)
    
    def get_latest_quote(self, instrument_token: int) -> Optional[Dict]:
        """Get the latest quote for an instrument"""
        return self.latest_quotes.get(instrument_token)
    
    def add_tick_callback(self, callback: Callable):
        """Add a callback for tick updates"""
        self.on_tick_callbacks.append(callback)
    
    def remove_tick_callback(self, callback: Callable):
        """Remove a tick callback"""
        if callback in self.on_tick_callbacks:
            self.on_tick_callbacks.remove(callback)
    
    # WebSocket event handlers
    def _on_ticks(self, ws, ticks):
        """Handle incoming tick data"""
        try:
            for tick in ticks:
                instrument_token = tick.get('instrument_token')
                
                # Store latest quote
                self.latest_quotes[instrument_token] = tick
                
                # Process tick based on instrument
                if instrument_token == self.INSTRUMENT_TOKENS.get('NIFTY'):
                    self._process_nifty_tick(tick)
                elif instrument_token == self.INSTRUMENT_TOKENS.get('BANKNIFTY'):
                    self._process_banknifty_tick(tick)
                elif instrument_token == self.INSTRUMENT_TOKENS.get('INDIA VIX'):
                    self._process_vix_tick(tick)
                else:
                    self._process_option_tick(tick)
                
                # Call registered callbacks for this instrument
                for callback in self.subscribers.get(instrument_token, []):
                    try:
                        callback(tick)
                    except Exception as e:
                        logger.error(f"Error in subscriber callback: {e}")
                
                # Call general tick callbacks
                for callback in self.on_tick_callbacks:
                    try:
                        callback(tick)
                    except Exception as e:
                        logger.error(f"Error in tick callback: {e}")
                        
        except Exception as e:
            logger.error(f"Error processing ticks: {e}")
    
    def _process_nifty_tick(self, tick):
        """Process NIFTY spot tick"""
        ltp = tick.get('last_price')
        change = tick.get('change', 0)
        volume = tick.get('volume', 0)
        
        logger.debug(f"NIFTY Spot: {ltp} | Change: {change:.2f}% | Volume: {volume}")
    
    def _process_banknifty_tick(self, tick):
        """Process BANK NIFTY spot tick"""
        ltp = tick.get('last_price')
        change = tick.get('change', 0)
        
        logger.debug(f"BANK NIFTY Spot: {ltp} | Change: {change:.2f}%")
    
    def _process_vix_tick(self, tick):
        """Process VIX tick"""
        ltp = tick.get('last_price')
        logger.debug(f"India VIX: {ltp}")
    
    def _process_option_tick(self, tick):
        """Process option contract tick"""
        instrument_token = tick.get('instrument_token')
        ltp = tick.get('last_price')
        volume = tick.get('volume', 0)
        oi = tick.get('oi', 0)
        
        # Get bid/ask if available (only in full mode)
        bid = tick.get('depth', {}).get('buy', [{}])[0].get('price')
        ask = tick.get('depth', {}).get('sell', [{}])[0].get('price')
        
        logger.debug(f"Option {instrument_token}: LTP={ltp} | Bid={bid} | Ask={ask} | OI={oi}")
    
    def _on_connect(self, ws, response):
        """Handle WebSocket connection"""
        self.is_connected = True
        self.reconnect_attempts = 0
        logger.info(f"Kite WebSocket connected: {response}")
        
        # Subscribe to default instruments
        default_tokens = [
            self.INSTRUMENT_TOKENS['NIFTY'],
            self.INSTRUMENT_TOKENS['BANKNIFTY'],
            self.INSTRUMENT_TOKENS['INDIA VIX']
        ]
        self.subscribe_instruments(default_tokens, mode="ltp")
        
        # Call connect callbacks
        for callback in self.on_connect_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in connect callback: {e}")
    
    def _on_close(self, ws, code, reason):
        """Handle WebSocket disconnection"""
        self.is_connected = False
        logger.warning(f"Kite WebSocket closed: {code} - {reason}")
    
    def _on_error(self, ws, code, reason):
        """Handle WebSocket errors"""
        logger.error(f"Kite WebSocket error: {code} - {reason}")
        
        for callback in self.on_error_callbacks:
            try:
                callback(code, reason)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
    
    def _on_reconnect(self, ws, attempts_count):
        """Handle reconnection attempts"""
        self.reconnect_attempts = attempts_count
        logger.info(f"Kite WebSocket reconnecting... Attempt {attempts_count}")
    
    def _on_noreconnect(self, ws):
        """Handle when reconnection fails"""
        logger.error("Kite WebSocket reconnection failed. Manual intervention required.")
        self.is_connected = False
    
    def _on_order_update(self, ws, data):
        """Handle order update postbacks"""
        try:
            order_id = data.get('order_id')
            status = data.get('status')
            
            logger.info(f"Order update: {order_id} - Status: {status}")
            
            # You can emit this to connected clients or process as needed
            # This is useful for real-time order status updates
            
        except Exception as e:
            logger.error(f"Error processing order update: {e}")
    
    def get_connection_status(self) -> Dict:
        """Get current connection status"""
        return {
            'connected': self.is_connected,
            'reconnect_attempts': self.reconnect_attempts,
            'subscribed_instruments': len(self.latest_quotes),
            'last_update': datetime.now().isoformat() if self.latest_quotes else None
        }

# Singleton instance
_kite_ws_instance = None

def get_kite_websocket_service() -> KiteWebSocketService:
    """Get or create singleton instance of KiteWebSocketService"""
    global _kite_ws_instance
    if _kite_ws_instance is None:
        _kite_ws_instance = KiteWebSocketService()
    return _kite_ws_instance