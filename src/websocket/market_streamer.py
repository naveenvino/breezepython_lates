"""
Real-time Market Data Streamer
Connects to broker APIs and streams via ZeroMQ
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
import aiohttp
from src.websocket.zmq_server import get_market_publisher

logger = logging.getLogger(__name__)

class MarketDataStreamer:
    """
    Streams real-time market data from brokers to ZeroMQ
    """
    
    def __init__(self):
        self.publisher = None
        self.active_symbols: Set[str] = set()
        self.streaming = False
        self.breeze_session = None
        self.kite_session = None
        
        # Streaming intervals (milliseconds)
        self.intervals = {
            'market_data': 1000,  # 1 second for spot prices
            'option_chain': 5000,  # 5 seconds for option chain
            'positions': 10000,   # 10 seconds for positions
            'orders': 2000        # 2 seconds for order updates
        }
        
        self.tasks = []
    
    async def start(self, breeze_session=None, kite_session=None):
        """Start streaming market data"""
        self.breeze_session = breeze_session
        self.kite_session = kite_session
        self.publisher = await get_market_publisher()
        self.streaming = True
        
        # Start streaming tasks
        self.tasks = [
            asyncio.create_task(self._stream_market_data()),
            asyncio.create_task(self._stream_option_chain()),
            asyncio.create_task(self._stream_positions()),
            asyncio.create_task(self._stream_orders())
        ]
        
        logger.info("Market data streaming started")
    
    async def stop(self):
        """Stop streaming"""
        self.streaming = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        logger.info("Market data streaming stopped")
    
    def add_symbol(self, symbol: str):
        """Add symbol to streaming list"""
        self.active_symbols.add(symbol)
        logger.info(f"Added {symbol} to streaming")
    
    def remove_symbol(self, symbol: str):
        """Remove symbol from streaming list"""
        self.active_symbols.discard(symbol)
        logger.info(f"Removed {symbol} from streaming")
    
    async def _stream_market_data(self):
        """Stream spot prices and market data"""
        while self.streaming:
            try:
                # Default to NIFTY if no symbols
                symbols = self.active_symbols or {'NIFTY'}
                
                for symbol in symbols:
                    data = await self._fetch_market_data(symbol)
                    if data:
                        await self.publisher.publish('market_data', data)
                
                await asyncio.sleep(self.intervals['market_data'] / 1000)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error streaming market data: {e}")
                await asyncio.sleep(5)
    
    async def _stream_option_chain(self):
        """Stream option chain data"""
        while self.streaming:
            try:
                # Stream NIFTY option chain
                data = await self._fetch_option_chain('NIFTY')
                if data:
                    await self.publisher.publish('option_chain', data)
                
                await asyncio.sleep(self.intervals['option_chain'] / 1000)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error streaming option chain: {e}")
                await asyncio.sleep(10)
    
    async def _stream_positions(self):
        """Stream position updates"""
        while self.streaming:
            try:
                data = await self._fetch_positions()
                if data:
                    await self.publisher.publish('positions', data)
                
                await asyncio.sleep(self.intervals['positions'] / 1000)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error streaming positions: {e}")
                await asyncio.sleep(10)
    
    async def _stream_orders(self):
        """Stream order updates"""
        while self.streaming:
            try:
                data = await self._fetch_orders()
                if data:
                    await self.publisher.publish('orders', data)
                
                await asyncio.sleep(self.intervals['orders'] / 1000)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error streaming orders: {e}")
                await asyncio.sleep(5)
    
    async def _fetch_market_data(self, symbol: str) -> Optional[Dict]:
        """Fetch market data from broker API"""
        try:
            # Try Breeze first
            if self.breeze_session:
                from src.services.real_time_spot_service import get_real_spot_price
                price = get_real_spot_price()
                
                if price:
                    return {
                        'symbol': symbol,
                        'ltp': price,
                        'change': 0,  # Calculate from previous close
                        'change_percent': 0,
                        'volume': 0,
                        'timestamp': datetime.now().isoformat()
                    }
            
            # Fallback to HTTP API
            async with aiohttp.ClientSession() as session:
                async with session.get(f'http://localhost:8000/live/market-data/{symbol}') as resp:
                    if resp.status == 200:
                        return await resp.json()
            
        except Exception as e:
            logger.debug(f"Failed to fetch market data for {symbol}: {e}")
        
        return None
    
    async def _fetch_option_chain(self, symbol: str) -> Optional[Dict]:
        """Fetch option chain from broker API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'http://localhost:8000/option-chain/fast',
                    params={'symbol': symbol, 'strikes': 20}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('data')
        except Exception as e:
            logger.debug(f"Failed to fetch option chain: {e}")
        
        return None
    
    async def _fetch_positions(self) -> Optional[Dict]:
        """Fetch positions from broker API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:8000/live/positions') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            'positions': data.get('positions', []),
                            'total_pnl': data.get('total_pnl', 0),
                            'timestamp': datetime.now().isoformat()
                        }
        except Exception as e:
            logger.debug(f"Failed to fetch positions: {e}")
        
        return None
    
    async def _fetch_orders(self) -> Optional[Dict]:
        """Fetch orders from broker API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:8000/live/orders') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            'orders': data.get('orders', []),
                            'timestamp': datetime.now().isoformat()
                        }
        except Exception as e:
            logger.debug(f"Failed to fetch orders: {e}")
        
        return None


class SignalStreamer:
    """
    Streams trading signals via ZeroMQ
    """
    
    def __init__(self):
        self.publisher = None
        self.streaming = False
    
    async def start(self):
        """Start signal streaming"""
        self.publisher = await get_market_publisher()
        self.streaming = True
        
        # Start signal detection
        asyncio.create_task(self._detect_and_stream_signals())
        
        logger.info("Signal streaming started")
    
    async def stop(self):
        """Stop signal streaming"""
        self.streaming = False
    
    async def _detect_and_stream_signals(self):
        """Detect and stream trading signals"""
        while self.streaming:
            try:
                # Fetch signals from API
                async with aiohttp.ClientSession() as session:
                    async with session.get('http://localhost:8000/live-trading/signals/detect') as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            signals = data.get('signals', [])
                            
                            if signals:
                                await self.publisher.publish('signals', {
                                    'signals': signals,
                                    'timestamp': datetime.now().isoformat()
                                })
                                logger.info(f"Streamed {len(signals)} signals")
                
                # Check for signals every 30 seconds
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error detecting signals: {e}")
                await asyncio.sleep(60)


# Global instances
_market_streamer: Optional[MarketDataStreamer] = None
_signal_streamer: Optional[SignalStreamer] = None

async def get_market_streamer() -> MarketDataStreamer:
    """Get or create market data streamer"""
    global _market_streamer
    if _market_streamer is None:
        _market_streamer = MarketDataStreamer()
    return _market_streamer

async def get_signal_streamer() -> SignalStreamer:
    """Get or create signal streamer"""
    global _signal_streamer
    if _signal_streamer is None:
        _signal_streamer = SignalStreamer()
    return _signal_streamer