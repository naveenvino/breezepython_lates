"""
Live Market Data Service
Provides real-time market data from Breeze API
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
from breeze_connect import BreezeConnect
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class LiveMarketService:
    """Service for fetching live market data"""
    
    def __init__(self):
        self.breeze = None
        self.is_connected = False
        self.last_quotes = {}
        self.option_chain_cache = {}
        self.cache_expiry = {}
        
        # Breeze API credentials
        self.api_key = os.getenv('BREEZE_API_KEY')
        self.api_secret = os.getenv('BREEZE_API_SECRET')
        self.session_token = os.getenv('BREEZE_API_SESSION')
        
    async def initialize(self):
        """Initialize Breeze connection"""
        try:
            if not self.breeze:
                self.breeze = BreezeConnect(api_key=self.api_key)
                
                # Generate session
                self.breeze.generate_session(
                    api_secret=self.api_secret,
                    session_token=self.session_token
                )
                
                self.is_connected = True
                logger.info("Breeze connection initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing Breeze connection: {e}")
            self.is_connected = False
            raise
    
    async def get_spot_price(self, symbol: str = "NIFTY") -> Dict:
        """Get live spot price for index"""
        try:
            if not self.is_connected:
                await self.initialize()
            
            # Get current expiry (Thursday)
            current_date = datetime.now()
            days_until_thursday = (3 - current_date.weekday()) % 7
            if days_until_thursday == 0 and current_date.hour >= 15:
                days_until_thursday = 7
            expiry_date = current_date + timedelta(days=days_until_thursday)
            
            # Map symbols to Breeze API codes
            symbol_map = {
                "NIFTY": "NIFTY",
                "BANKNIFTY": "CNXBAN",  # Bank Nifty code in Breeze
                "INDIAVIX": "INDIAVIX"
            }
            
            breeze_symbol = symbol_map.get(symbol, symbol)
            
            # Fetch quotes
            response = self.breeze.get_quotes(
                stock_code=breeze_symbol,
                exchange_code="NSE",
                product_type="cash",
                right="others",
                strike_price="0"
            )
            
            if response['Status'] == 200:
                data = response['Success'][0]
                
                spot_data = {
                    'symbol': symbol,
                    'ltp': float(data.get('ltp', 0)),
                    'open': float(data.get('open', 0)),
                    'high': float(data.get('high', 0)),
                    'low': float(data.get('low', 0)),
                    'close': float(data.get('close', 0)),
                    'volume': int(data.get('volume', 0)),
                    'change': float(data.get('ltp', 0)) - float(data.get('close', 0)),
                    'changePct': ((float(data.get('ltp', 0)) - float(data.get('close', 0))) / float(data.get('close', 1))) * 100,
                    'timestamp': datetime.now().isoformat()
                }
                
                self.last_quotes[symbol] = spot_data
                return spot_data
            
            return self.last_quotes.get(symbol, {
                'symbol': symbol,
                'ltp': 0,
                'change': 0,
                'changePct': 0,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error fetching spot price for {symbol}: {e}")
            return self.last_quotes.get(symbol, {})
    
    async def get_option_quote(self, strike: int, option_type: str, symbol: str = "NIFTY") -> Dict:
        """Get live option quote"""
        try:
            if not self.is_connected:
                await self.initialize()
            
            # Get current expiry
            expiry_date = self._get_current_expiry()
            
            response = self.breeze.get_quotes(
                stock_code=symbol,
                exchange_code="NFO",
                product_type="options",
                right=option_type.lower(),
                strike_price=str(strike),
                expiry_date=expiry_date.strftime('%Y-%m-%d')
            )
            
            if response['Status'] == 200:
                data = response['Success'][0]
                
                return {
                    'strike': strike,
                    'option_type': option_type,
                    'ltp': float(data.get('ltp', 0)),
                    'bid': float(data.get('best_bid_price', 0)),
                    'ask': float(data.get('best_ask_price', 0)),
                    'volume': int(data.get('volume', 0)),
                    'oi': int(data.get('open_interest', 0)),
                    'iv': float(data.get('implied_volatility', 0)),
                    'delta': float(data.get('delta', 0)),
                    'gamma': float(data.get('gamma', 0)),
                    'theta': float(data.get('theta', 0)),
                    'vega': float(data.get('vega', 0)),
                    'timestamp': datetime.now().isoformat()
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching option quote: {e}")
            return {}
    
    async def get_option_chain(self, center_strike: int, range_count: int = 5, symbol: str = "NIFTY") -> List[Dict]:
        """Get live option chain around center strike"""
        try:
            # Check cache
            cache_key = f"{symbol}_{center_strike}_{range_count}"
            if cache_key in self.option_chain_cache:
                if datetime.now() < self.cache_expiry.get(cache_key, datetime.min):
                    return self.option_chain_cache[cache_key]
            
            if not self.is_connected:
                await self.initialize()
            
            # Calculate strike range
            strike_interval = 50 if symbol == "NIFTY" else 100
            strikes = []
            
            for i in range(-range_count, range_count + 1):
                strike = center_strike + (i * strike_interval)
                strikes.append(strike)
            
            # Fetch data for all strikes
            chain_data = []
            
            for strike in strikes:
                strike_data = {'strike': strike}
                
                # Fetch CE data
                ce_data = await self.get_option_quote(strike, 'CE', symbol)
                if ce_data:
                    strike_data.update({
                        'ce_ltp': ce_data.get('ltp'),
                        'ce_bid': ce_data.get('bid'),
                        'ce_ask': ce_data.get('ask'),
                        'ce_volume': ce_data.get('volume'),
                        'ce_oi': ce_data.get('oi'),
                        'ce_iv': ce_data.get('iv'),
                        'ce_delta': ce_data.get('delta'),
                        'ce_gamma': ce_data.get('gamma'),
                        'ce_theta': ce_data.get('theta')
                    })
                
                # Fetch PE data
                pe_data = await self.get_option_quote(strike, 'PE', symbol)
                if pe_data:
                    strike_data.update({
                        'pe_ltp': pe_data.get('ltp'),
                        'pe_bid': pe_data.get('bid'),
                        'pe_ask': pe_data.get('ask'),
                        'pe_volume': pe_data.get('volume'),
                        'pe_oi': pe_data.get('oi'),
                        'pe_iv': pe_data.get('iv'),
                        'pe_delta': pe_data.get('delta'),
                        'pe_gamma': pe_data.get('gamma'),
                        'pe_theta': pe_data.get('theta')
                    })
                
                chain_data.append(strike_data)
            
            # Cache the result for 30 seconds
            self.option_chain_cache[cache_key] = chain_data
            self.cache_expiry[cache_key] = datetime.now() + timedelta(seconds=30)
            
            return chain_data
            
        except Exception as e:
            logger.error(f"Error fetching option chain: {e}")
            return []
    
    async def get_market_depth(self, symbol: str, strike: int = None, option_type: str = None) -> Dict:
        """Get market depth (5 levels of bid/ask)"""
        try:
            if not self.is_connected:
                await self.initialize()
            
            if strike and option_type:
                # Option market depth
                response = self.breeze.get_quotes(
                    stock_code=symbol,
                    exchange_code="NFO",
                    product_type="options",
                    right=option_type.lower(),
                    strike_price=str(strike)
                )
            else:
                # Index market depth
                response = self.breeze.get_quotes(
                    stock_code=symbol,
                    exchange_code="NSE",
                    product_type="cash"
                )
            
            if response['Status'] == 200:
                data = response['Success'][0]
                
                depth = {
                    'bids': [],
                    'asks': [],
                    'timestamp': datetime.now().isoformat()
                }
                
                # Extract bid levels
                for i in range(1, 6):
                    bid_price = data.get(f'best_bid_price_{i}', 0)
                    bid_qty = data.get(f'best_bid_quantity_{i}', 0)
                    if bid_price:
                        depth['bids'].append({
                            'price': float(bid_price),
                            'quantity': int(bid_qty),
                            'orders': data.get(f'bid_orders_{i}', 0)
                        })
                
                # Extract ask levels
                for i in range(1, 6):
                    ask_price = data.get(f'best_ask_price_{i}', 0)
                    ask_qty = data.get(f'best_ask_quantity_{i}', 0)
                    if ask_price:
                        depth['asks'].append({
                            'price': float(ask_price),
                            'quantity': int(ask_qty),
                            'orders': data.get(f'ask_orders_{i}', 0)
                        })
                
                return depth
            
            return {'bids': [], 'asks': []}
            
        except Exception as e:
            logger.error(f"Error fetching market depth: {e}")
            return {'bids': [], 'asks': []}
    
    async def get_intraday_candles(self, symbol: str = "NIFTY", interval: str = "5minute", count: int = 100) -> List[Dict]:
        """Get intraday candles using Breeze API v2"""
        try:
            if not self.is_connected:
                await self.initialize()
            
            # Map symbols to Breeze API codes
            symbol_map = {
                "NIFTY": "NIFTY",
                "BANKNIFTY": "CNXBAN",
                "INDIAVIX": "INDIA VIX"
            }
            
            breeze_symbol = symbol_map.get(symbol, symbol)
            
            to_date = datetime.now()
            from_date = to_date - timedelta(days=5)  # Get last 5 days of data
            
            # Format dates as required by Breeze API v2
            from_date_str = from_date.strftime('%Y-%m-%dT07:00:00.000Z')
            to_date_str = to_date.strftime('%Y-%m-%dT15:30:00.000Z')
            
            # Try get_historical_data_v2 first, fallback to v1 if not available
            try:
                response = self.breeze.get_historical_data_v2(
                    interval=interval,
                    from_date=from_date_str,
                    to_date=to_date_str,
                    stock_code=breeze_symbol,
                    exchange_code="NSE",
                    product_type="cash"
                )
            except AttributeError:
                # Fallback to v1 API if v2 not available
                response = self.breeze.get_historical_data(
                    interval=interval,
                    from_date=from_date.strftime('%Y-%m-%d'),
                    to_date=to_date.strftime('%Y-%m-%d'),
                    stock_code=breeze_symbol,
                    exchange_code="NSE",
                    product_type="cash"
                )
            
            if response.get('Status') == 200 and response.get('Success'):
                candles = []
                data = response['Success']
                
                # Take last 'count' candles
                for candle in data[-count:] if len(data) > count else data:
                    candles.append({
                        'time': candle.get('datetime', candle.get('date', '')),
                        'open': float(candle.get('open', 0)),
                        'high': float(candle.get('high', 0)),
                        'low': float(candle.get('low', 0)),
                        'close': float(candle.get('close', 0)),
                        'volume': int(candle.get('volume', 0))
                    })
                return candles
            
            logger.warning(f"No historical data available for {symbol}: {response}")
            return []
            
        except Exception as e:
            logger.error(f"Error fetching intraday candles for {symbol}: {e}")
            return []
    
    async def get_vix(self) -> float:
        """Get India VIX value"""
        try:
            # India VIX requires special handling
            if not self.is_connected:
                await self.initialize()
            
            # Try fetching VIX with different parameters
            response = self.breeze.get_quotes(
                stock_code="INDIA VIX",
                exchange_code="NSE",
                product_type="cash",
                right="others",
                strike_price="0"
            )
            
            if response['Status'] == 200:
                data = response['Success'][0]
                return float(data.get('ltp', 0))
            
            # Fallback to a default value if VIX is not available
            logger.warning("VIX data not available, using default value")
            return 15.0  # Default VIX value
            
        except Exception as e:
            logger.error(f"Error fetching VIX: {e}")
            return 15.0  # Default VIX value
    
    async def get_fii_dii_data(self) -> Dict:
        """Get FII/DII data (mock for now, can integrate with NSE API)"""
        # This would need integration with NSE bhav copy or other data source
        return {
            'fii_net': 0,
            'dii_net': 0,
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_current_expiry(self) -> datetime:
        """Get current weekly expiry date (Thursday)"""
        current_date = datetime.now()
        days_until_thursday = (3 - current_date.weekday()) % 7
        
        if days_until_thursday == 0 and current_date.hour >= 15:
            days_until_thursday = 7
        
        expiry_date = current_date + timedelta(days=days_until_thursday)
        return expiry_date
    
    async def get_all_market_data(self) -> Dict:
        """Get comprehensive market data"""
        try:
            # Fetch all data concurrently
            tasks = [
                self.get_spot_price("NIFTY"),
                self.get_spot_price("BANKNIFTY"),
                self.get_vix(),
                self.get_fii_dii_data()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            return {
                'NIFTY': results[0] if not isinstance(results[0], Exception) else {},
                'BANKNIFTY': results[1] if not isinstance(results[1], Exception) else {},
                'VIX': {'ltp': results[2]} if not isinstance(results[2], Exception) else {'ltp': 0},
                'FII_DII': results[3] if not isinstance(results[3], Exception) else {},
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error fetching all market data: {e}")
            return {}

# Singleton instance
_market_service = None

def get_market_service() -> LiveMarketService:
    """Get singleton market service instance"""
    global _market_service
    if _market_service is None:
        _market_service = LiveMarketService()
    return _market_service