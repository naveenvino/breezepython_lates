"""
Breeze WebSocket Service for Live Trading
Real-time data feed for NIFTY and Options
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
import os
from dotenv import load_dotenv
import threading
import queue
from collections import deque
import time

try:
    from breeze_connect import BreezeConnect
except ImportError:
    BreezeConnect = None
    logging.warning("breeze_connect not installed - using mock mode")

load_dotenv()
logger = logging.getLogger(__name__)

class BreezeWebSocketLive:
    """Manages live market data feed from Breeze"""
    
    def __init__(self):
        """Initialize Breeze WebSocket connection"""
        self.breeze = None
        self.is_connected = False
        self.subscribers = {}
        self.callbacks = []
        self.data_queue = queue.Queue()
        self.spot_price = None
        self.vix_value = None
        self.option_chain = {}
        self.last_update = None
        self.reconnect_attempts = 0
        self.max_reconnect = 5
        self.last_cache_save = None
        self.cache_save_interval = 300  # 5 minutes
        
        # Price history for calculation
        self.price_history = deque(maxlen=100)
        
        # Initialize connection
        self._initialize_breeze()
        
    def _initialize_breeze(self):
        """Initialize Breeze API connection"""
        try:
            api_key = os.getenv('BREEZE_API_KEY')
            api_secret = os.getenv('BREEZE_API_SECRET')
            session_token = os.getenv('BREEZE_API_SESSION')
            
            if not all([api_key, api_secret, session_token]):
                logger.error("Breeze credentials not found in environment")
                return False
                
            if BreezeConnect is None:
                logger.error("BreezeConnect not imported - breeze_connect library not installed")
                return False
                
            self.breeze = BreezeConnect(api_key=api_key)
            self.breeze.generate_session(
                api_secret=api_secret,
                session_token=session_token
            )
            
            logger.info("Breeze API initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Breeze API: {e}")
            return False
    
    def connect(self):
        """Connect to Breeze WebSocket"""
        try:
            if not self.breeze:
                if not self._initialize_breeze():
                    return False
            
            # Connect to WebSocket
            self.breeze.ws_connect()
            self.is_connected = True
            logger.info("Connected to Breeze WebSocket")
            
            # Set up callbacks
            self.breeze.on_ticks = self._on_tick
            
            # Subscribe to NIFTY spot
            self._subscribe_nifty_spot()
            
            # Subscribe to India VIX
            self._subscribe_india_vix()
            
            # Subscribe to option chain
            self._subscribe_option_chain()
            
            # Start worker thread
            self._start_worker()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect WebSocket: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Disconnect from WebSocket"""
        try:
            if self.breeze and self.is_connected:
                self.breeze.ws_disconnect()
                self.is_connected = False
                logger.info("Disconnected from Breeze WebSocket")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    def _subscribe_nifty_spot(self):
        """Subscribe to NIFTY spot data"""
        try:
            # Subscribe to NIFTY index cash/spot as per official documentation
            response = self.breeze.subscribe_feeds(
                exchange_code="NSE",
                stock_code="NIFTY",
                product_type="cash",
                get_market_depth=False,
                get_exchange_quotes=True
            )
            logger.info(f"Subscribed to NIFTY spot data: {response}")
            
        except Exception as e:
            logger.error(f"Failed to subscribe to NIFTY: {e}")
    
    def _subscribe_india_vix(self):
        """Subscribe to India VIX data"""
        try:
            # Try subscribing to India VIX
            response = self.breeze.subscribe_feeds(
                exchange_code="NSE",
                stock_code="INDIAVIX",
                product_type="cash",
                get_exchange_quotes=True
            )
            logger.info(f"India VIX subscription response: {response}")
        except Exception as e:
            logger.error(f"Failed to subscribe to India VIX: {e}")
            # Try alternative code
            try:
                response = self.breeze.subscribe_feeds(
                    exchange_code="NSE",
                    stock_code="VIX",
                    product_type="cash",
                    get_exchange_quotes=True
                )
                logger.info(f"VIX subscription response: {response}")
            except Exception as e2:
                logger.error(f"Failed to subscribe to VIX: {e2}")
    
    def _subscribe_option_chain(self):
        """Subscribe to option chain around ATM using Breeze subscribe_feeds"""
        try:
            # Only proceed if we have real-time spot price from WebSocket
            # NO API calls allowed - spot price must come from WebSocket ticks only
            if self.spot_price:
                # Calculate ATM strike
                atm_strike = round(self.spot_price / 50) * 50
                
                # Subscribe to strikes around ATM (±500 points)
                strikes = []
                for i in range(-10, 11):  # ±500 points in 50 intervals
                    strike = atm_strike + (i * 50)
                    strikes.append(strike)
                
                # Get current expiry in correct format (e.g., "20-Aug-2025")
                expiry = self._get_current_expiry_formatted()
                
                # Subscribe to each strike using Breeze subscribe_feeds
                for strike in strikes:
                    # Subscribe to CALL option
                    self.breeze.subscribe_feeds(
                        exchange_code="NFO",
                        stock_code="NIFTY",
                        expiry_date=expiry,
                        strike_price=str(strike),
                        right="call",
                        product_type="options",
                        get_market_depth=False,
                        get_exchange_quotes=True,
                        interval="1second"
                    )
                    
                    # Subscribe to PUT option
                    self.breeze.subscribe_feeds(
                        exchange_code="NFO",
                        stock_code="NIFTY",
                        expiry_date=expiry,
                        strike_price=str(strike),
                        right="put",
                        product_type="options",
                        get_market_depth=False,
                        get_exchange_quotes=True,
                        interval="1second"
                    )
                    
                    # Store strike in option chain structure
                    self.option_chain[strike] = {
                        'CE': {'ltp': 0, 'oi': 0, 'volume': 0, 'bid': 0, 'ask': 0},
                        'PE': {'ltp': 0, 'oi': 0, 'volume': 0, 'bid': 0, 'ask': 0}
                    }
                
                logger.info(f"Subscribed to {len(strikes)} strikes for expiry {expiry}")
                
        except Exception as e:
            logger.error(f"Failed to subscribe to option chain: {e}")
    
    def _get_current_spot(self):
        """Get current NIFTY spot price - ONLY from WebSocket, no API calls"""
        # Return None - spot price must come from WebSocket ticks only
        # No API calls allowed as per requirement: "no more hardcoding allowed, no old data from data base"
        return None
    
    def _get_current_expiry(self):
        """Get current week expiry (Thursday)"""
        today = datetime.now()
        days_until_thursday = (3 - today.weekday()) % 7
        
        # If today is Thursday after 3:30 PM, get next Thursday
        if days_until_thursday == 0:
            if today.hour >= 15 and today.minute >= 30:
                days_until_thursday = 7
        
        expiry = today + timedelta(days=days_until_thursday)
        
        # Return in standard format for internal use
        return expiry.strftime('%Y-%m-%d')
    
    def _get_current_expiry_formatted(self) -> str:
        """Get current expiry in Breeze format (e.g., '20-Aug-2025')"""
        expiry_str = self._get_current_expiry()
        expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d')
        # Format: 20-Aug-2025 for Breeze subscribe_feeds
        return expiry_date.strftime("%d-%b-%Y")
    
    def get_option_chain_snapshot(self) -> Dict:
        """Get current option chain snapshot - REAL DATA ONLY"""
        if not self.option_chain:
            # No real-time data available from WebSocket
            return {
                'error': 'Real market data not available',
                'spot_price': 0,
                'chain': [],
                'source': 'NO_DATA'
            }
        
        # Format option chain for API response
        chain = []
        spot_price = self.spot_price  # Only use WebSocket spot price, no API calls
        if not spot_price:
            return {
                'error': 'Real spot price not available from WebSocket',
                'spot_price': 0,
                'chain': [],
                'source': 'NO_DATA'
            }
        atm_strike = round(spot_price / 50) * 50
        
        for strike, data in sorted(self.option_chain.items()):
            chain.append({
                'strike': strike,
                'moneyness': 'ATM' if strike == atm_strike else 'ITM' if strike < spot_price else 'OTM',
                'call_ltp': data.get('CE', {}).get('ltp', 0),
                'call_bid': data.get('CE', {}).get('bid', 0),
                'call_ask': data.get('CE', {}).get('ask', 0),
                'call_oi': data.get('CE', {}).get('oi', 0),
                'call_volume': data.get('CE', {}).get('volume', 0),
                'call_iv': data.get('CE', {}).get('iv', 0.15),
                'put_ltp': data.get('PE', {}).get('ltp', 0),
                'put_bid': data.get('PE', {}).get('bid', 0),
                'put_ask': data.get('PE', {}).get('ask', 0),
                'put_oi': data.get('PE', {}).get('oi', 0),
                'put_volume': data.get('PE', {}).get('volume', 0),
                'put_iv': data.get('PE', {}).get('iv', 0.15)
            })
        
        # Calculate PCR
        total_call_oi = sum(item.get('call_oi', 0) for item in chain)
        total_put_oi = sum(item.get('put_oi', 0) for item in chain)
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1
        
        return {
            'spot_price': spot_price,
            'atm_strike': atm_strike,
            'chain': chain,
            'pcr': {
                'pcr_oi': round(pcr, 3),
                'total_call_oi': total_call_oi,
                'total_put_oi': total_put_oi
            },
            'max_pain': {
                'max_pain_strike': atm_strike,
                'difference': 0
            },
            'time_to_expiry': self._calculate_time_to_expiry(),
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_mock_chain(self) -> Dict:
        """NO MOCK DATA - Return error instead"""
        return {
            'error': 'Real market data required. Mock data not allowed.',
            'spot_price': 0,
            'chain': [],
            'source': 'ERROR'
        }
    
    def _calculate_time_to_expiry(self) -> int:
        """Calculate days to expiry"""
        expiry = self._get_current_expiry()
        expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
        return (expiry_date - datetime.now()).days
    
    def add_callback(self, callback: Callable):
        """Add a callback for data updates"""
        if callback not in self.callbacks:
            self.callbacks.append(callback)
            logger.info(f"Added callback: {callback.__name__}")
    
    def remove_callback(self, callback: Callable):
        """Remove a callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            logger.info(f"Removed callback: {callback.__name__}")
    
    def _on_tick(self, ticks):
        logger.info(f"WebSocket tick received: {ticks}")
        """Handle incoming tick data from Breeze WebSocket
        
        Breeze tick format for NIFTY spot:
        - symbol: '4.1!NIFTY 50' 
        - open, last, high, low, change
        - exchange: 'NSE Equity'
        - stock_name: 'NIFTY 50'
        """
        try:
            # Log raw tick data type and content
            logger.info(f"Received tick data type: {type(ticks)}, content: {ticks}")
            
            # Handle different tick formats
            if isinstance(ticks, str):
                # Try to parse JSON string
                import json
                try:
                    ticks = json.loads(ticks)
                except:
                    logger.warning(f"Could not parse tick string: {ticks}")
                    return
            
            # Ensure ticks is iterable
            if not isinstance(ticks, (list, tuple)):
                ticks = [ticks]
            
            for tick in ticks:
                # Skip if tick is not a dict
                if not isinstance(tick, dict):
                    logger.warning(f"Skipping non-dict tick: {type(tick)}")
                    continue
                    
                # Check if it's NIFTY spot data - look for the symbol format
                symbol = tick.get('symbol', '')
                stock_code = tick.get('stock_code', '')
                
                # Log what we're checking
                logger.debug(f"Checking tick - symbol: {symbol}, stock_code: {stock_code}")
                
                if 'NIFTY' in symbol or 'NIFTY' in stock_code or tick.get('stock_name') == 'NIFTY 50':
                    # Check if it's VIX or NIFTY spot
                    if 'VIX' in symbol or 'VIX' in stock_code:
                        # India VIX data
                        self.vix_value = float(tick.get('last', tick.get('close', tick.get('ltp', 0))))
                        logger.info(f"Updated India VIX: {self.vix_value}")
                    else:
                        # NIFTY spot data
                        old_price = self.spot_price
                        self.spot_price = float(tick.get('last', tick.get('close', tick.get('ltp', 0))))
                        self.last_update = datetime.now()
                        logger.info(f"Updated NIFTY spot price: {self.spot_price}")
                        
                        # Save to cache every update during market hours
                        self._save_spot_to_cache()
                        
                        # If this is the first spot price, subscribe to option chain
                        if old_price is None and self.spot_price and len(self.option_chain) == 0:
                            logger.info("First spot price received, subscribing to option chain...")
                        self._subscribe_option_chain()
                        self._subscribe_india_vix()
                    
                    # Notify callbacks about spot update
                    for callback in self.callbacks:
                        try:
                            callback({'type': 'spot', 'price': self.spot_price})
                        except:
                            pass
                
                # Check if it's India VIX data
                elif 'VIX' in symbol or 'VIX' in stock_code:
                    self.vix_value = float(tick.get('last', tick.get('close', tick.get('ltp', 0))))
                    logger.info(f"Updated India VIX: {self.vix_value}")
                    
                    # Notify callbacks about VIX update
                    for callback in self.callbacks:
                        try:
                            callback({'type': 'vix', 'value': self.vix_value})
                        except:
                            pass
                
                # Check if it's option data
                elif tick.get('exchange_code') == 'NFO' and tick.get('stock_code') == 'NIFTY':
                    strike = int(float(tick.get('strike_price', 0)))
                    right = tick.get('right_type', '').upper()  # CE or PE
                    
                    if strike and right in ['CE', 'PE']:
                        # Initialize strike if not exists
                        if strike not in self.option_chain:
                            self.option_chain[strike] = {
                                'CE': {'ltp': 0, 'oi': 0, 'volume': 0, 'bid': 0, 'ask': 0},
                                'PE': {'ltp': 0, 'oi': 0, 'volume': 0, 'bid': 0, 'ask': 0}
                            }
                        
                        # Update option data
                        option_type = 'CE' if right == 'CE' else 'PE'
                        self.option_chain[strike][option_type] = {
                            'ltp': float(tick.get('close', tick.get('ltp', 0))),
                            'oi': int(tick.get('oi', 0)),
                            'volume': int(tick.get('volume', 0)),
                            'bid': float(tick.get('bid', 0)),
                            'ask': float(tick.get('ask', 0)),
                            'high': float(tick.get('high', 0)),
                            'low': float(tick.get('low', 0)),
                            'open': float(tick.get('open', 0))
                        }
                        
                        # Notify callbacks about option update
                        for callback in self.callbacks:
                            try:
                                callback({
                                    'type': 'option',
                                    'strike': strike,
                                    'right': option_type,
                                    'data': self.option_chain[strike][option_type]
                                })
                            except:
                                pass
                
                # Add to queue for processing
                self.data_queue.put(tick)
                    
        except Exception as e:
            logger.error(f"Error processing tick: {e}")
    
    def _process_tick(self, tick):
        """Process raw tick data"""
        try:
            processed = {
                'symbol': tick.get('stock_code', ''),
                'ltp': float(tick.get('ltp', 0)),
                'volume': int(tick.get('total_quantity_traded', 0)),
                'oi': int(tick.get('open_interest', 0)),
                'bid': float(tick.get('best_bid_price', 0)),
                'ask': float(tick.get('best_ask_price', 0)),
                'timestamp': datetime.now(),
                'exchange': tick.get('exchange_code', '')
            }
            
            return processed
            
        except Exception as e:
            logger.error(f"Failed to process tick: {e}")
            return None
    
    def _update_state(self, tick):
        """Update internal state with tick data"""
        symbol = tick['symbol']
        
        # Update NIFTY spot
        if symbol == 'NIFTY':
            self.spot_price = tick['ltp']
            self.price_history.append({
                'price': tick['ltp'],
                'timestamp': tick['timestamp']
            })
        
        # Update option chain
        elif 'CE' in symbol or 'PE' in symbol:
            self.option_chain[symbol] = tick
        
        self.last_update = tick['timestamp']
    
    def _notify_callbacks(self, tick):
        """Notify all registered callbacks"""
        for callback in self.callbacks:
            try:
                callback(tick)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def register_callback(self, callback: Callable):
        """Register a callback for tick data"""
        self.callbacks.append(callback)
    
    def get_spot_price(self) -> Optional[float]:
        """Get current NIFTY spot price"""
        return self.spot_price
    
    def get_vix(self) -> Optional[float]:
        """Get current India VIX value"""
        return self.vix_value
    
    def get_option_data(self, strike: int, option_type: str) -> Optional[Dict]:
        """Get option data for specific strike"""
        expiry = self._get_current_expiry()
        symbol = f"NIFTY{expiry}{strike}{option_type}"
        return self.option_chain.get(symbol)
    
    def get_option_chain_snapshot(self) -> Dict:
        """Get current option chain snapshot"""
        return self.option_chain.copy()
    
    def get_atm_strikes(self, num_strikes: int = 5) -> List[int]:
        """Get ATM and nearby strikes"""
        if not self.spot_price:
            return []
        
        atm = round(self.spot_price / 50) * 50
        strikes = []
        
        for i in range(-num_strikes//2, num_strikes//2 + 1):
            strikes.append(atm + (i * 50))
        
        return strikes
    
    def _start_worker(self):
        """Start worker thread for processing and keep connection alive"""
        def worker():
            while self.is_connected:
                try:
                    # Process queued data
                    if not self.data_queue.empty():
                        tick = self.data_queue.get(timeout=1)
                        # Additional processing if needed
                    
                    # Keep the WebSocket connection alive
                    time.sleep(0.1)
                        
                except queue.Empty:
                    time.sleep(0.1)
                    continue
                except Exception as e:
                    logger.error(f"Worker error: {e}")
                    time.sleep(1)
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        logger.info("Worker thread started to keep WebSocket alive")
    
    def reconnect(self):
        """Reconnect to WebSocket"""
        if self.reconnect_attempts < self.max_reconnect:
            self.reconnect_attempts += 1
            logger.info(f"Reconnecting... Attempt {self.reconnect_attempts}")
            
            self.disconnect()
            time.sleep(5)  # Wait before reconnecting
            
            if self.connect():
                self.reconnect_attempts = 0
                return True
        
        logger.error("Max reconnection attempts reached")
        return False
    
    def get_connection_status(self) -> Dict:
        """Get connection status"""
        return {
            'connected': self.is_connected,
            'spot_price': self.spot_price,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'option_chain_size': len(self.option_chain),
            'reconnect_attempts': self.reconnect_attempts
        }

    def _save_spot_to_cache(self):
        """Save spot price to cache"""
        try:
            # Check if we should save (every 5 minutes)
            now = datetime.now()
            if self.last_cache_save and (now - self.last_cache_save).seconds < self.cache_save_interval:
                return  # Not time yet
            
            # Import here to avoid circular dependency
            from src.services.market_data_cache_service import get_cache_service
            cache_service = get_cache_service()
            
            # Save spot price
            if self.spot_price:
                asyncio.create_task(cache_service.save_market_data({
                    'symbol': 'NIFTY',
                    'instrument_type': 'SPOT',
                    'last_price': self.spot_price,
                    'spot_price': self.spot_price,
                    'timestamp': now
                }, source='websocket'))
                
                self.last_cache_save = now
                logger.info(f"Saved spot price to cache: {self.spot_price}")
        except Exception as e:
            logger.error(f"Error saving to cache: {e}")
    
    def _save_options_to_cache(self):
        """Save option chain to cache"""
        try:
            from src.services.market_data_cache_service import get_cache_service
            cache_service = get_cache_service()
            
            data_list = []
            expiry = self._get_current_expiry()
            
            for strike, options in self.option_chain.items():
                for opt_type in ['CE', 'PE']:
                    if opt_type in options and options[opt_type].get('ltp'):
                        data_list.append({
                            'symbol': f"NIFTY{expiry}{strike}{opt_type}",
                            'instrument_type': opt_type,
                            'underlying': 'NIFTY',
                            'strike': strike,
                            'last_price': options[opt_type].get('ltp', 0),
                            'bid_price': options[opt_type].get('bid'),
                            'ask_price': options[opt_type].get('ask'),
                            'volume': options[opt_type].get('volume'),
                            'open_interest': options[opt_type].get('oi'),
                            'spot_price': self.spot_price
                        })
            
            if data_list:
                asyncio.create_task(cache_service.save_bulk_market_data(data_list, source='websocket'))
                logger.info(f"Saved {len(data_list)} option prices to cache")
                
        except Exception as e:
            logger.error(f"Error saving options to cache: {e}")

# Global instance
_breeze_ws = None

def get_breeze_websocket() -> BreezeWebSocketLive:
    """Get or create Breeze WebSocket instance"""
    global _breeze_ws
    if _breeze_ws is None:
        _breeze_ws = BreezeWebSocketLive()
    return _breeze_ws

def start_breeze_feed():
    """Start Breeze WebSocket feed"""
    ws = get_breeze_websocket()
    if ws.connect():
        logger.info("Breeze WebSocket feed started successfully")
        return True
    return False

def stop_breeze_feed():
    """Stop Breeze WebSocket feed"""
    ws = get_breeze_websocket()
    ws.disconnect()
    logger.info("Breeze WebSocket feed stopped")

if __name__ == "__main__":
    # Test the WebSocket connection
    import time
    
    logging.basicConfig(level=logging.INFO)
    
    ws = get_breeze_websocket()
    
    def on_tick(tick):
        print(f"Tick: {tick['symbol']} @ {tick['ltp']}")
    
    ws.register_callback(on_tick)
    
    if ws.connect():
        print("Connected! Streaming data...")
        
        # Run for 60 seconds
        time.sleep(60)
        
        # Print status
        print(f"Status: {ws.get_connection_status()}")
        
        ws.disconnect()
    else:
        print("Failed to connect")