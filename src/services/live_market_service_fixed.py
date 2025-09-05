"""
Live Market Data Service - Fixed Version
Provides real-time market data with fallback to mock data
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import random
from breeze_connect import BreezeConnect
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class LiveMarketService:
    """Service for fetching live market data with fallback"""
    
    def __init__(self):
        self.breeze = None
        self.is_connected = False
        self.last_quotes = {}
        self.option_chain_cache = {}
        self.cache_expiry = {}
        self.use_mock_data = False
        self.last_reconnect_attempt = None
        self.reconnect_cooldown = 60  # seconds
        
        # Breeze API credentials
        self.api_key = os.getenv('BREEZE_API_KEY')
        self.api_secret = os.getenv('BREEZE_API_SECRET')
        self.session_token = os.getenv('BREEZE_API_SESSION')
        
        # Initialize will be called when needed
        
    async def initialize(self):
        """Initialize Breeze connection with fallback"""
        try:
            if not self.breeze and self.api_key and self.api_secret:
                self.breeze = BreezeConnect(api_key=self.api_key)
                
                # Generate session
                self.breeze.generate_session(
                    api_secret=self.api_secret,
                    session_token=self.session_token
                )
                
                # Test connection
                test_response = self.breeze.get_funds()
                if test_response.get('Status') == 200:
                    self.is_connected = True
                    self.use_mock_data = False
                    logger.info("Breeze connection initialized successfully")
                else:
                    raise Exception("Connection test failed")
                    
        except Exception as e:
            logger.error(f"Error initializing Breeze connection: {e}")
            logger.info("Switching to mock data mode")
            self.is_connected = False
            self.use_mock_data = True
    
    async def get_spot_price(self, symbol: str = "NIFTY") -> Dict:
        """Get spot price - REAL DATA ONLY, no mock fallback"""
        
        # Only return real data
        if self.is_connected:
            try:
                # Map symbols to Breeze format
                symbol_map = {
                    "NIFTY": "NIFTY",
                    "BANKNIFTY": "CNXBAN",
                    "INDIAVIX": "INDIA VIX"
                }
                
                breeze_symbol = symbol_map.get(symbol, symbol)
                
                response = self.breeze.get_quotes(
                    stock_code=breeze_symbol,
                    exchange_code="NSE"
                )
                
                if response.get('Status') == 200:
                    data = response.get('Success', [{}])[0]
                    return {
                        'symbol': symbol,
                        'ltp': float(data.get('ltp', 0)),
                        'open': float(data.get('open', 0)),
                        'high': float(data.get('high', 0)),
                        'low': float(data.get('low', 0)),
                        'close': float(data.get('previous_close', 0)),
                        'change': float(data.get('ltp', 0)) - float(data.get('previous_close', 0)),
                        'change_percent': float(data.get('ltp_percent_change', 0)),
                        'volume': int(data.get('total_quantity_traded', 0)),
                        'timestamp': datetime.now().isoformat(),
                        'is_real': True
                    }
            except Exception as e:
                logger.error(f"Error fetching spot price for {symbol}: {e}")
                raise Exception(f"Cannot fetch real data: {str(e)}")
        
        # NO MOCK DATA - Return error instead
        raise Exception("Breeze connection not available - Cannot provide real data")
    
    def _get_mock_spot_price(self, symbol: str) -> Dict:
        """DEPRECATED - No mock data allowed"""
        raise Exception("Mock data is disabled - Only real data allowed")
    
    async def get_all_market_data(self) -> Dict:
        """Get market data for all major indices"""
        try:
            # Get NIFTY data
            nifty_data = await self.get_spot_price("NIFTY")
            
            # Get BANKNIFTY data
            banknifty_data = await self.get_spot_price("BANKNIFTY")
            
            # Get VIX data
            vix_data = await self.get_spot_price("INDIAVIX")
            
            return {
                'NIFTY': nifty_data,
                'BANKNIFTY': banknifty_data,
                'INDIAVIX': vix_data,
                'timestamp': datetime.now().isoformat(),
                'is_mock': self.use_mock_data
            }
            
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return {}
    
    async def get_option_chain(self, symbol: str, strike: int, range_count: int = 5) -> List[Dict]:
        """Get option chain with fallback to mock data"""
        
        # Try real data first
        if self.is_connected and not self.use_mock_data:
            try:
                expiry = self._get_current_expiry()
                
                response = self.breeze.get_option_chain_quotes(
                    stock_code=symbol,
                    exchange_code="NFO",
                    expiry_date=expiry,
                    strike_price=str(strike),
                    option_type="",
                    right=""
                )
                
                if response.get('Status') == 200:
                    # Process and return real data
                    return self._process_option_chain(response.get('Success', []))
            except Exception as e:
                logger.error(f"Error fetching option chain: {e}")
                self.use_mock_data = True
        
        # NO MOCK DATA - Return error
        raise Exception("Cannot fetch real option chain data")
    
    def _get_mock_option_chain(self, symbol: str, strike: int, range_count: int) -> List[Dict]:
        """DEPRECATED - No mock data allowed"""
        raise Exception("Mock data is disabled - Only real data allowed")
        return []  # Never reached but kept for structure
        
    def _get_mock_option_chain_old(self, symbol: str, strike: int, range_count: int) -> List[Dict]:
        """DEPRECATED - Old mock generation code"""
        chain = []
        strikes = []
        
        # Generate strikes
        for i in range(-range_count, range_count + 1):
            if symbol == "NIFTY":
                strikes.append(strike + (i * 50))
            else:
                strikes.append(strike + (i * 100))
        
        spot_price = 24500 if symbol == "NIFTY" else 53500
        
        for strike_price in strikes:
            # Calculate realistic option prices based on moneyness
            moneyness = (spot_price - strike_price) / spot_price
            
            # CE prices - higher for ITM, lower for OTM
            if strike_price < spot_price:  # ITM CE
                ce_price = abs(spot_price - strike_price) + random.uniform(50, 100)
            else:  # OTM CE
                ce_price = max(10, 100 * math.exp(-abs(moneyness) * 10))
            
            # PE prices - opposite of CE
            if strike_price > spot_price:  # ITM PE
                pe_price = abs(strike_price - spot_price) + random.uniform(50, 100)
            else:  # OTM PE
                pe_price = max(10, 100 * math.exp(-abs(moneyness) * 10))
            
            chain.append({
                'strike': strike_price,
                'ce_ltp': round(ce_price, 2),
                'ce_bid': round(ce_price * 0.98, 2),
                'ce_ask': round(ce_price * 1.02, 2),
                'ce_oi': random.randint(10000, 100000),
                'ce_volume': random.randint(1000, 10000),
                'ce_iv': round(random.uniform(12, 25), 2),
                'ce_delta': round(0.5 + moneyness, 2),
                'ce_gamma': round(random.uniform(0.001, 0.01), 4),
                'ce_theta': round(random.uniform(-5, -1), 2),
                'ce_vega': round(random.uniform(0.5, 2), 2),
                'pe_ltp': round(pe_price, 2),
                'pe_bid': round(pe_price * 0.98, 2),
                'pe_ask': round(pe_price * 1.02, 2),
                'pe_oi': random.randint(10000, 100000),
                'pe_volume': random.randint(1000, 10000),
                'pe_iv': round(random.uniform(12, 25), 2),
                'pe_delta': round(-0.5 + moneyness, 2),
                'pe_gamma': round(random.uniform(0.001, 0.01), 4),
                'pe_theta': round(random.uniform(-5, -1), 2),
                'pe_vega': round(random.uniform(0.5, 2), 2),
                'is_mock': True
            })
        
        return chain
    
    def _get_current_expiry(self) -> str:
        """Get current weekly expiry"""
        from datetime import datetime, timedelta
        
        today = datetime.now()
        days_until_thursday = (3 - today.weekday()) % 7
        
        if days_until_thursday == 0 and today.hour >= 15:
            days_until_thursday = 7
        
        expiry = today + timedelta(days=days_until_thursday)
        return expiry.strftime("%Y-%m-%d")
    
    async def get_historical_data(self, symbol: str, interval: str = "5minute", count: int = 100) -> List[Dict]:
        """Get historical candles with mock data fallback"""
        
        # Generate mock candles
        candles = []
        base_price = 24500 if symbol == "NIFTY" else 53500
        current_time = datetime.now()
        
        for i in range(count):
            time_offset = timedelta(minutes=5 * (count - i))
            candle_time = current_time - time_offset
            
            # Generate realistic OHLC
            open_price = base_price * random.uniform(0.998, 1.002)
            close_price = base_price * random.uniform(0.998, 1.002)
            high_price = max(open_price, close_price) * random.uniform(1.0, 1.002)
            low_price = min(open_price, close_price) * random.uniform(0.998, 1.0)
            
            candles.append({
                'datetime': candle_time.isoformat(),
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'close': round(close_price, 2),
                'volume': random.randint(10000, 50000)
            })
            
            # Update base for next candle
            base_price = close_price
        
        return candles
    
    def get_connection_status(self) -> Dict:
        """Get connection status"""
        return {
            'connected': self.is_connected,
            'use_mock_data': self.use_mock_data,
            'api_available': self.breeze is not None,
            'message': 'Using mock data' if self.use_mock_data else 'Connected to Breeze API'
        }

# Import math for calculations
import math

# Singleton instance
_instance = None

def get_live_market_service() -> LiveMarketService:
    global _instance
    if _instance is None:
        _instance = LiveMarketService()
    return _instance