"""
Live Data Feed Module
Real-time market data streaming and processing
"""
import asyncio
import threading
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
import logging
import json
from queue import Queue, Empty
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from breeze_connect import BreezeConnect
import websocket
from collections import deque

logger = logging.getLogger(__name__)

@dataclass
class MarketTick:
    """Market tick data"""
    symbol: str
    timestamp: datetime
    ltp: float  # Last traded price
    volume: int
    bid: float
    ask: float
    oi: int  # Open interest
    bid_qty: int
    ask_qty: int
    total_buy_qty: int
    total_sell_qty: int
    
@dataclass
class OptionGreeks:
    """Option Greeks data"""
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float  # Implied volatility
    
@dataclass
class OptionTick:
    """Option tick data"""
    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # CE or PE
    tick: MarketTick
    greeks: Optional[OptionGreeks] = None

class LiveDataFeed:
    """Manages live market data feed"""
    
    def __init__(self, breeze_api: BreezeConnect):
        """
        Initialize live data feed
        
        Args:
            breeze_api: Breeze API connection
        """
        self.breeze = breeze_api
        self.is_running = False
        self.subscribers = {}
        self.tick_queue = Queue()
        self.market_depth = {}
        self.tick_history = {}
        self.websocket = None
        self.worker_thread = None
        self.callbacks = []
        
        # Performance metrics
        self.tick_count = 0
        self.last_tick_time = None
        self.latency_history = deque(maxlen=100)
        
    def start(self):
        """Start live data feed"""
        if self.is_running:
            logger.warning("Data feed already running")
            return
            
        logger.info("Starting live data feed...")
        self.is_running = True
        
        # Start worker thread
        self.worker_thread = threading.Thread(target=self._process_ticks)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        
        # Connect to Breeze websocket
        self._connect_websocket()
        
        logger.info("Live data feed started successfully")
        
    def stop(self):
        """Stop live data feed"""
        if not self.is_running:
            return
            
        logger.info("Stopping live data feed...")
        self.is_running = False
        
        # Disconnect websocket
        if self.websocket:
            self.websocket.close()
            
        # Wait for worker thread
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
            
        logger.info("Live data feed stopped")
        
    def subscribe(self, symbols: List[str], callback: Optional[Callable] = None):
        """
        Subscribe to market data for symbols
        
        Args:
            symbols: List of symbols to subscribe
            callback: Optional callback for tick data
        """
        for symbol in symbols:
            if symbol not in self.subscribers:
                self.subscribers[symbol] = []
                self.tick_history[symbol] = deque(maxlen=1000)
                
                # Subscribe via Breeze
                try:
                    self.breeze.subscribe_feeds(
                        stock_token=symbol,
                        exchange_code="NFO" if "NIFTY" in symbol else "NSE",
                        product_type="options" if "CE" in symbol or "PE" in symbol else "futures",
                        feed_type="market_data"
                    )
                    logger.info(f"Subscribed to {symbol}")
                except Exception as e:
                    logger.error(f"Failed to subscribe to {symbol}: {e}")
                    
            if callback:
                self.subscribers[symbol].append(callback)
                
    def unsubscribe(self, symbols: List[str]):
        """Unsubscribe from market data"""
        for symbol in symbols:
            if symbol in self.subscribers:
                # Unsubscribe via Breeze
                try:
                    self.breeze.unsubscribe_feeds(
                        stock_token=symbol,
                        exchange_code="NFO" if "NIFTY" in symbol else "NSE"
                    )
                    del self.subscribers[symbol]
                    logger.info(f"Unsubscribed from {symbol}")
                except Exception as e:
                    logger.error(f"Failed to unsubscribe from {symbol}: {e}")
                    
    def add_callback(self, callback: Callable):
        """Add global callback for all ticks"""
        self.callbacks.append(callback)
        
    def get_latest_tick(self, symbol: str) -> Optional[MarketTick]:
        """Get latest tick for symbol"""
        if symbol in self.tick_history and self.tick_history[symbol]:
            return self.tick_history[symbol][-1]
        return None
        
    def get_tick_history(self, symbol: str, count: int = 100) -> List[MarketTick]:
        """Get tick history for symbol"""
        if symbol in self.tick_history:
            return list(self.tick_history[symbol])[-count:]
        return []
        
    def get_market_depth(self, symbol: str) -> Dict:
        """Get market depth for symbol"""
        return self.market_depth.get(symbol, {})
        
    def get_option_chain(self, underlying: str, expiry: datetime) -> pd.DataFrame:
        """
        Get option chain for underlying
        
        Args:
            underlying: Underlying symbol (e.g., NIFTY)
            expiry: Expiry date
            
        Returns:
            DataFrame with option chain
        """
        chain_data = []
        
        # Get strikes around current price
        current_price = self._get_underlying_price(underlying)
        if not current_price:
            return pd.DataFrame()
            
        strikes = self._get_option_strikes(underlying, current_price)
        
        for strike in strikes:
            # Get CE data
            ce_symbol = f"{underlying}{expiry.strftime('%y%b').upper()}{strike}CE"
            ce_tick = self.get_latest_tick(ce_symbol)
            
            # Get PE data
            pe_symbol = f"{underlying}{expiry.strftime('%y%b').upper()}{strike}PE"
            pe_tick = self.get_latest_tick(pe_symbol)
            
            if ce_tick or pe_tick:
                if not ce_tick:
                    raise ValueError(f"No CE tick data available for {ce_symbol}")
                if not pe_tick:
                    raise ValueError(f"No PE tick data available for {pe_symbol}")
                    
                chain_data.append({
                    'strike': strike,
                    'ce_ltp': ce_tick.ltp,
                    'ce_volume': ce_tick.volume,
                    'ce_oi': ce_tick.oi,
                    'ce_bid': ce_tick.bid,
                    'ce_ask': ce_tick.ask,
                    'pe_ltp': pe_tick.ltp,
                    'pe_volume': pe_tick.volume,
                    'pe_oi': pe_tick.oi,
                    'pe_bid': pe_tick.bid,
                    'pe_ask': pe_tick.ask,
                    'pcr_oi': pe_tick.oi / ce_tick.oi if ce_tick.oi > 0 else None,
                    'pcr_volume': pe_tick.volume / ce_tick.volume if ce_tick.volume > 0 else None
                })
                
        return pd.DataFrame(chain_data)
        
    def calculate_greeks(self, option_symbol: str) -> Optional[OptionGreeks]:
        """
        Calculate option Greeks
        
        Args:
            option_symbol: Option symbol
            
        Returns:
            Option Greeks or None
        """
        # Parse option details
        details = self._parse_option_symbol(option_symbol)
        if not details:
            return None
            
        underlying_price = self._get_underlying_price(details['underlying'])
        option_price = self.get_latest_tick(option_symbol)
        
        if not underlying_price or not option_price:
            return None
            
        # Calculate Greeks (simplified Black-Scholes)
        S = underlying_price  # Spot price
        K = details['strike']  # Strike price
        T = (details['expiry'] - datetime.now()).days / 365  # Time to expiry
        r = 0.05  # Risk-free rate
        sigma = self._calculate_iv(option_price.ltp, S, K, T, r, details['type'])
        
        # Calculate Greeks
        from scipy.stats import norm
        
        d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        
        if details['type'] == 'CE':
            delta = norm.cdf(d1)
            theta = -(S*norm.pdf(d1)*sigma)/(2*np.sqrt(T)) - r*K*np.exp(-r*T)*norm.cdf(d2)
        else:  # PE
            delta = norm.cdf(d1) - 1
            theta = -(S*norm.pdf(d1)*sigma)/(2*np.sqrt(T)) + r*K*np.exp(-r*T)*norm.cdf(-d2)
            
        gamma = norm.pdf(d1) / (S*sigma*np.sqrt(T))
        vega = S*norm.pdf(d1)*np.sqrt(T) / 100
        
        return OptionGreeks(
            delta=delta,
            gamma=gamma,
            theta=theta/365,  # Per day
            vega=vega,
            iv=sigma
        )
        
    def get_performance_stats(self) -> Dict:
        """Get feed performance statistics"""
        avg_latency = np.mean(self.latency_history) if self.latency_history else 0
        
        return {
            'total_ticks': self.tick_count,
            'symbols_subscribed': len(self.subscribers),
            'average_latency_ms': avg_latency * 1000,
            'ticks_per_second': self._calculate_tick_rate(),
            'queue_size': self.tick_queue.qsize(),
            'is_running': self.is_running
        }
        
    def _connect_websocket(self):
        """Connect to Breeze websocket"""
        try:
            # Breeze websocket connection
            ws_url = "wss://breezeapi.icicidirect.com/websocket"
            
            def on_message(ws, message):
                self._on_tick(json.loads(message))
                
            def on_error(ws, error):
                logger.error(f"Websocket error: {error}")
                
            def on_close(ws):
                logger.info("Websocket closed")
                if self.is_running:
                    # Reconnect after delay
                    threading.Timer(5.0, self._connect_websocket).start()
                    
            def on_open(ws):
                logger.info("Websocket connected")
                # Subscribe to all symbols
                for symbol in self.subscribers:
                    self.subscribe([symbol])
                    
            self.websocket = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            
            # Run in separate thread
            ws_thread = threading.Thread(target=self.websocket.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
        except Exception as e:
            logger.error(f"Failed to connect websocket: {e}")
            
    def _on_tick(self, data: Dict):
        """Handle incoming tick data"""
        try:
            # Parse tick data
            tick = self._parse_tick_data(data)
            if not tick:
                return
                
            # Update metrics
            self.tick_count += 1
            current_time = datetime.now()
            if self.last_tick_time:
                latency = (current_time - self.last_tick_time).total_seconds()
                self.latency_history.append(latency)
            self.last_tick_time = current_time
            
            # Store tick
            symbol = tick.symbol
            if symbol in self.tick_history:
                self.tick_history[symbol].append(tick)
                
            # Update market depth
            self._update_market_depth(tick)
            
            # Add to queue for processing
            self.tick_queue.put(tick)
            
        except Exception as e:
            logger.error(f"Error processing tick: {e}")
            
    def _process_ticks(self):
        """Process ticks from queue"""
        while self.is_running:
            try:
                tick = self.tick_queue.get(timeout=1)
                
                # Call symbol-specific callbacks
                if tick.symbol in self.subscribers:
                    for callback in self.subscribers[tick.symbol]:
                        try:
                            callback(tick)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
                            
                # Call global callbacks
                for callback in self.callbacks:
                    try:
                        callback(tick)
                    except Exception as e:
                        logger.error(f"Global callback error: {e}")
                        
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Tick processing error: {e}")
                
    def _parse_tick_data(self, data: Dict) -> Optional[MarketTick]:
        """Parse raw tick data"""
        try:
            return MarketTick(
                symbol=data.get('symbol'),
                timestamp=datetime.fromtimestamp(data.get('timestamp', 0)),
                ltp=float(data.get('ltp', 0)),
                volume=int(data.get('volume', 0)),
                bid=float(data.get('bid', 0)),
                ask=float(data.get('ask', 0)),
                oi=int(data.get('oi', 0)),
                bid_qty=int(data.get('bid_qty', 0)),
                ask_qty=int(data.get('ask_qty', 0)),
                total_buy_qty=int(data.get('total_buy_qty', 0)),
                total_sell_qty=int(data.get('total_sell_qty', 0))
            )
        except Exception as e:
            logger.error(f"Failed to parse tick: {e}")
            return None
            
    def _update_market_depth(self, tick: MarketTick):
        """Update market depth data"""
        self.market_depth[tick.symbol] = {
            'bid': tick.bid,
            'ask': tick.ask,
            'bid_qty': tick.bid_qty,
            'ask_qty': tick.ask_qty,
            'spread': tick.ask - tick.bid,
            'mid': (tick.ask + tick.bid) / 2,
            'imbalance': (tick.bid_qty - tick.ask_qty) / (tick.bid_qty + tick.ask_qty) if (tick.bid_qty + tick.ask_qty) > 0 else 0
        }
        
    def _get_underlying_price(self, underlying: str) -> Optional[float]:
        """Get underlying price"""
        tick = self.get_latest_tick(underlying)
        return tick.ltp if tick else None
        
    def _get_option_strikes(self, underlying: str, spot: float, num_strikes: int = 10) -> List[float]:
        """Get option strikes around spot"""
        # Round to nearest 50 for NIFTY
        base_strike = round(spot / 50) * 50
        
        strikes = []
        for i in range(-num_strikes//2, num_strikes//2 + 1):
            strikes.append(base_strike + i * 50)
            
        return strikes
        
    def _parse_option_symbol(self, symbol: str) -> Optional[Dict]:
        """Parse option symbol"""
        try:
            # Example: NIFTY25JAN25000CE
            if 'CE' in symbol:
                parts = symbol.split('CE')
                option_type = 'CE'
            elif 'PE' in symbol:
                parts = symbol.split('PE')
                option_type = 'PE'
            else:
                return None
                
            # Extract details
            strike = float(parts[0][-5:])
            expiry_str = parts[0][-8:-5]
            underlying = parts[0][:-8]
            
            # Parse expiry (simplified)
            expiry = datetime.strptime(f"25{expiry_str}25", "%y%b%d")
            
            return {
                'underlying': underlying,
                'strike': strike,
                'expiry': expiry,
                'type': option_type
            }
        except Exception:
            return None
            
    def _calculate_iv(self, option_price: float, S: float, K: float, T: float, r: float, option_type: str) -> float:
        """Calculate implied volatility (simplified)"""
        # Newton-Raphson for IV (simplified implementation)
        # In production, use more robust method
        raise ValueError("Implied volatility calculation requires real market data - cannot provide default value")
        
    def _calculate_tick_rate(self) -> float:
        """Calculate ticks per second"""
        if len(self.latency_history) < 2:
            return 0
            
        # Average time between ticks
        avg_interval = np.mean(self.latency_history)
        return 1 / avg_interval if avg_interval > 0 else 0

class SimulatedDataFeed(LiveDataFeed):
    """Simulated data feed for testing"""
    
    def __init__(self):
        """Initialize simulated feed"""
        super().__init__(None)
        self.simulation_thread = None
        self.base_prices = {}
        
    def start(self):
        """Start simulated feed"""
        if self.is_running:
            return
            
        logger.info("Starting simulated data feed...")
        self.is_running = True
        
        # Start worker thread
        self.worker_thread = threading.Thread(target=self._process_ticks)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        
        # Start simulation thread
        self.simulation_thread = threading.Thread(target=self._simulate_ticks)
        self.simulation_thread.daemon = True
        self.simulation_thread.start()
        
        logger.info("Simulated data feed started")
        
    def _simulate_ticks(self):
        """Generate simulated ticks"""
        import time
        
        # Initialize base prices from real market data
        nifty_price = self._get_real_nifty_price()
        if not nifty_price:
            raise RuntimeError("Cannot initialize simulation without real NIFTY price")
        self.base_prices['NIFTY'] = nifty_price
        
        while self.is_running:
            for symbol in self.subscribers:
                # Generate random tick
                if symbol not in self.base_prices:
                    real_price = self._get_real_price(symbol)
                    if not real_price:
                        raise RuntimeError(f"Cannot simulate {symbol} without real price data")
                    self.base_prices[symbol] = real_price
                    
                # Random walk
                change = np.random.normal(0, 0.001)
                self.base_prices[symbol] *= (1 + change)
                
                # Create tick
                tick = MarketTick(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    ltp=self.base_prices[symbol],
                    volume=np.random.randint(1000, 10000),
                    bid=self.base_prices[symbol] * 0.999,
                    ask=self.base_prices[symbol] * 1.001,
                    oi=np.random.randint(10000, 100000),
                    bid_qty=np.random.randint(100, 1000),
                    ask_qty=np.random.randint(100, 1000),
                    total_buy_qty=np.random.randint(10000, 50000),
                    total_sell_qty=np.random.randint(10000, 50000)
                )
                
                self._on_tick({'symbol': symbol, 'data': tick.__dict__})
                
            time.sleep(0.1)  # 10 ticks per second
            
    def _get_real_nifty_price(self) -> Optional[float]:
        """Get real NIFTY price for simulation initialization"""
        # This should connect to real market data source
        # For now, raise an error to force proper implementation
        raise NotImplementedError("Must implement real market data connection for simulation")
        
    def _get_real_price(self, symbol: str) -> Optional[float]:
        """Get real price for symbol"""
        # This should connect to real market data source  
        # For now, raise an error to force proper implementation
        raise NotImplementedError(f"Must implement real market data connection for {symbol}")