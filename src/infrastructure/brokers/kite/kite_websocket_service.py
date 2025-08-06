"""
Kite WebSocket Service
Handles real-time market data streaming for options
"""
import logging
import asyncio
from typing import Dict, List, Callable, Optional, Set
from datetime import datetime
from kiteconnect import KiteTicker
import threading
import json

logger = logging.getLogger(__name__)

class KiteWebSocketService:
    """
    Manages WebSocket connection for real-time market data
    """
    
    def __init__(self, api_key: str, access_token: str):
        self.api_key = api_key
        self.access_token = access_token
        self.kws = None
        self.subscribed_tokens = set()
        self.callbacks = {
            'tick': [],
            'connect': [],
            'disconnect': [],
            'error': [],
            'order_update': []
        }
        self.running = False
        self.thread = None
        
    def initialize(self):
        """Initialize KiteTicker instance"""
        self.kws = KiteTicker(self.api_key, self.access_token)
        
        # Set up callbacks
        self.kws.on_ticks = self._on_ticks
        self.kws.on_connect = self._on_connect
        self.kws.on_close = self._on_close
        self.kws.on_error = self._on_error
        self.kws.on_reconnect = self._on_reconnect
        self.kws.on_noreconnect = self._on_noreconnect
        self.kws.on_order_update = self._on_order_update
        
    def add_callback(self, event: str, callback: Callable):
        """Add a callback for specific events"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            logger.info(f"Added callback for {event} event")
    
    def remove_callback(self, event: str, callback: Callable):
        """Remove a callback"""
        if event in self.callbacks and callback in self.callbacks[event]:
            self.callbacks[event].remove(callback)
    
    def subscribe_tokens(self, tokens: List[int], mode: str = "full"):
        """
        Subscribe to instrument tokens
        
        Args:
            tokens: List of instrument tokens
            mode: Subscription mode - "ltp", "quote", or "full"
        """
        if self.kws and self.running:
            self.kws.subscribe(tokens)
            
            # Set mode
            if mode == "ltp":
                self.kws.set_mode(self.kws.MODE_LTP, tokens)
            elif mode == "quote":
                self.kws.set_mode(self.kws.MODE_QUOTE, tokens)
            else:  # full
                self.kws.set_mode(self.kws.MODE_FULL, tokens)
            
            self.subscribed_tokens.update(tokens)
            logger.info(f"Subscribed to {len(tokens)} tokens in {mode} mode")
    
    def unsubscribe_tokens(self, tokens: List[int]):
        """Unsubscribe from tokens"""
        if self.kws and self.running:
            self.kws.unsubscribe(tokens)
            self.subscribed_tokens.difference_update(tokens)
            logger.info(f"Unsubscribed from {len(tokens)} tokens")
    
    def start(self):
        """Start WebSocket connection in a separate thread"""
        if not self.kws:
            self.initialize()
        
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_websocket)
            self.thread.daemon = True
            self.thread.start()
            logger.info("WebSocket service started")
    
    def stop(self):
        """Stop WebSocket connection"""
        self.running = False
        if self.kws:
            self.kws.stop()
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("WebSocket service stopped")
    
    def _run_websocket(self):
        """Run WebSocket in thread"""
        try:
            self.kws.connect(threaded=False)
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            self.running = False
    
    def _on_ticks(self, ws, ticks):
        """Handle incoming ticks"""
        try:
            # Process ticks
            processed_ticks = []
            for tick in ticks:
                processed_tick = self._process_tick(tick)
                processed_ticks.append(processed_tick)
            
            # Call registered callbacks
            for callback in self.callbacks['tick']:
                try:
                    callback(processed_ticks)
                except Exception as e:
                    logger.error(f"Error in tick callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error processing ticks: {e}")
    
    def _process_tick(self, tick: Dict) -> Dict:
        """Process raw tick data"""
        return {
            'token': tick.get('instrument_token'),
            'last_price': tick.get('last_price'),
            'volume': tick.get('volume'),
            'buy_quantity': tick.get('buy_quantity'),
            'sell_quantity': tick.get('sell_quantity'),
            'open': tick.get('ohlc', {}).get('open'),
            'high': tick.get('ohlc', {}).get('high'),
            'low': tick.get('ohlc', {}).get('low'),
            'close': tick.get('ohlc', {}).get('close'),
            'change': tick.get('change'),
            'last_trade_time': tick.get('last_trade_time'),
            'oi': tick.get('oi'),  # Open Interest
            'oi_day_high': tick.get('oi_day_high'),
            'oi_day_low': tick.get('oi_day_low'),
            'timestamp': datetime.now()
        }
    
    def _on_connect(self, ws, response):
        """Handle connection established"""
        logger.info(f"WebSocket connected: {response}")
        
        # Resubscribe to tokens if any
        if self.subscribed_tokens:
            tokens_list = list(self.subscribed_tokens)
            self.subscribed_tokens.clear()  # Clear to resubscribe
            self.subscribe_tokens(tokens_list)
        
        # Call connect callbacks
        for callback in self.callbacks['connect']:
            try:
                callback(response)
            except Exception as e:
                logger.error(f"Error in connect callback: {e}")
    
    def _on_close(self, ws, code, reason):
        """Handle connection closed"""
        logger.warning(f"WebSocket closed: {code} - {reason}")
        
        # Call disconnect callbacks
        for callback in self.callbacks['disconnect']:
            try:
                callback(code, reason)
            except Exception as e:
                logger.error(f"Error in disconnect callback: {e}")
    
    def _on_error(self, ws, code, reason):
        """Handle errors"""
        logger.error(f"WebSocket error: {code} - {reason}")
        
        # Call error callbacks
        for callback in self.callbacks['error']:
            try:
                callback(code, reason)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")
    
    def _on_reconnect(self, ws, attempts_count):
        """Handle reconnection attempts"""
        logger.info(f"WebSocket reconnecting... Attempt {attempts_count}")
    
    def _on_noreconnect(self, ws):
        """Handle when reconnection fails"""
        logger.error("WebSocket reconnection failed")
        self.running = False
    
    def _on_order_update(self, ws, data):
        """Handle order updates"""
        logger.info(f"Order update: {data}")
        
        # Call order update callbacks
        for callback in self.callbacks['order_update']:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in order update callback: {e}")
    
    def get_subscribed_tokens(self) -> Set[int]:
        """Get currently subscribed tokens"""
        return self.subscribed_tokens.copy()
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self.running and self.kws is not None


class OptionChainStreamer:
    """
    Specialized class for streaming NIFTY option chain data
    """
    
    def __init__(self, websocket_service: KiteWebSocketService):
        self.ws_service = websocket_service
        self.option_chain_data = {}
        self.spot_price = None
        
    def stream_option_chain(self, strikes: List[int], expiry_date: str):
        """
        Stream option chain for given strikes
        
        Args:
            strikes: List of strike prices
            expiry_date: Expiry date in format YYMMDD
        """
        tokens = []
        
        # Generate tokens for CE and PE
        for strike in strikes:
            # You need to get actual tokens from instruments dump
            # This is placeholder logic
            ce_token = self._get_option_token(strike, 'CE', expiry_date)
            pe_token = self._get_option_token(strike, 'PE', expiry_date)
            
            if ce_token:
                tokens.append(ce_token)
            if pe_token:
                tokens.append(pe_token)
        
        # Subscribe to tokens
        self.ws_service.subscribe_tokens(tokens, mode="full")
        
        # Add callback for processing option chain data
        self.ws_service.add_callback('tick', self._process_option_tick)
    
    def _get_option_token(self, strike: int, option_type: str, expiry: str) -> Optional[int]:
        """Get instrument token for option (placeholder - implement with actual logic)"""
        # In practice, you need to look up from instruments dump
        # This is just a placeholder
        return None
    
    def _process_option_tick(self, ticks: List[Dict]):
        """Process option ticks and update chain data"""
        for tick in ticks:
            token = tick['token']
            # Update option chain data structure
            self.option_chain_data[token] = {
                'ltp': tick['last_price'],
                'volume': tick['volume'],
                'oi': tick['oi'],
                'bid': tick.get('depth', {}).get('buy', [{}])[0].get('price'),
                'ask': tick.get('depth', {}).get('sell', [{}])[0].get('price'),
                'timestamp': tick['timestamp']
            }
    
    def get_option_chain(self) -> Dict:
        """Get current option chain data"""
        return self.option_chain_data.copy()