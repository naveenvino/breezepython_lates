"""
Kite Market Data Service
Provides market quotes, LTP, OHLC data using Kite Connect API
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from kiteconnect import KiteConnect
import os
from dotenv import load_dotenv
import pandas as pd

load_dotenv()
logger = logging.getLogger(__name__)

class KiteMarketDataService:
    """
    Service for fetching market data from Kite
    """
    
    def __init__(self):
        self.api_key = os.getenv('KITE_API_KEY')
        self.access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        if not self.api_key or not self.access_token:
            raise ValueError("Kite API credentials not found")
        
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        # Cache for frequently accessed data
        self.quote_cache = {}
        self.cache_timestamp = {}
        self.cache_ttl = 1  # Cache TTL in seconds for quotes
        
    def get_quote(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Get full market quote for symbols
        
        Args:
            symbols: List of symbols in format "EXCHANGE:TRADINGSYMBOL"
                    e.g., ["NSE:NIFTY 50", "NFO:NIFTY24DEC1925000CE"]
        """
        try:
            # Check cache first
            now = datetime.now()
            cached_quotes = {}
            symbols_to_fetch = []
            
            for symbol in symbols:
                if symbol in self.quote_cache:
                    cache_time = self.cache_timestamp.get(symbol)
                    if cache_time and (now - cache_time).total_seconds() < self.cache_ttl:
                        cached_quotes[symbol] = self.quote_cache[symbol]
                    else:
                        symbols_to_fetch.append(symbol)
                else:
                    symbols_to_fetch.append(symbol)
            
            # Fetch fresh quotes for non-cached symbols
            if symbols_to_fetch:
                fresh_quotes = self.kite.quote(symbols_to_fetch)
                
                # Update cache
                for symbol, quote in fresh_quotes.items():
                    self.quote_cache[symbol] = quote
                    self.cache_timestamp[symbol] = now
                
                # Merge with cached quotes
                cached_quotes.update(fresh_quotes)
            
            return cached_quotes
            
        except Exception as e:
            logger.error(f"Failed to fetch quotes: {e}")
            return {}
    
    def get_ltp(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get last traded price for symbols
        
        Args:
            symbols: List of symbols
        Returns:
            Dictionary mapping symbol to LTP
        """
        try:
            ltp_data = self.kite.ltp(symbols)
            return {symbol: data.get('last_price', 0) for symbol, data in ltp_data.items()}
        except Exception as e:
            logger.error(f"Failed to fetch LTP: {e}")
            return {}
    
    def get_ohlc(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Get OHLC data for symbols
        
        Args:
            symbols: List of symbols
        Returns:
            Dictionary with OHLC data
        """
        try:
            ohlc_data = self.kite.ohlc(symbols)
            result = {}
            
            for symbol, data in ohlc_data.items():
                ohlc = data.get('ohlc', {})
                result[symbol] = {
                    'open': ohlc.get('open', 0),
                    'high': ohlc.get('high', 0),
                    'low': ohlc.get('low', 0),
                    'close': ohlc.get('close', 0),
                    'ltp': data.get('last_price', 0)
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch OHLC: {e}")
            return {}
    
    def get_spot_price(self, symbol: str) -> float:
        """
        Get spot price for an index
        
        Args:
            symbol: Index symbol (NIFTY, BANKNIFTY)
        """
        index_map = {
            'NIFTY': 'NSE:NIFTY 50',
            'BANKNIFTY': 'NSE:NIFTY BANK',
            'FINNIFTY': 'NSE:NIFTY FIN SERVICE',
            'MIDCPNIFTY': 'NSE:NIFTY MID SELECT'
        }
        
        kite_symbol = index_map.get(symbol, symbol)
        
        try:
            quotes = self.get_quote([kite_symbol])
            if kite_symbol in quotes:
                return quotes[kite_symbol].get('last_price', 0)
            return 0
        except Exception as e:
            logger.error(f"Failed to fetch spot price for {symbol}: {e}")
            return 0
    
    def get_option_greeks(self, symbol: str, strike: int, option_type: str, 
                         expiry_date: datetime) -> Dict:
        """
        Calculate approximate Greeks for an option
        Note: Kite doesn't provide Greeks directly, so this uses quote data
        
        Args:
            symbol: Underlying symbol
            strike: Strike price
            option_type: CE or PE
            expiry_date: Option expiry date
        """
        try:
            # Generate option symbol
            option_symbol = self._generate_option_symbol(symbol, strike, option_type, expiry_date)
            
            # Get quote
            quotes = self.get_quote([f"NFO:{option_symbol}"])
            
            if f"NFO:{option_symbol}" in quotes:
                quote = quotes[f"NFO:{option_symbol}"]
                
                # Extract available data
                return {
                    'symbol': option_symbol,
                    'ltp': quote.get('last_price', 0),
                    'volume': quote.get('volume', 0),
                    'oi': quote.get('oi', 0),
                    'bid': quote.get('depth', {}).get('buy', [{}])[0].get('price', 0),
                    'ask': quote.get('depth', {}).get('sell', [{}])[0].get('price', 0),
                    'change': quote.get('change', 0),
                    'pchange': quote.get('change_percent', 0),
                    # Greeks not available from Kite
                    'delta': None,
                    'gamma': None,
                    'theta': None,
                    'vega': None,
                    'iv': None
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Failed to fetch option data: {e}")
            return {}
    
    def _generate_option_symbol(self, symbol: str, strike: int, 
                               option_type: str, expiry_date: datetime) -> str:
        """
        Generate Kite option symbol format
        Format: SYMBOL{YY}{MON/M/N/D}{DD}{STRIKE}{CE/PE}
        """
        year = expiry_date.strftime('%y')
        
        # Month formatting for weekly/monthly expiry
        month_map = {
            1: 'JAN', 2: 'FEB', 3: 'MAR', 4: 'APR',
            5: 'MAY', 6: 'JUN', 7: 'JUL', 8: 'AUG',
            9: 'SEP', 10: 'O', 11: 'N', 12: 'D'
        }
        
        # For weekly expiry, use single letter months for Oct, Nov, Dec
        # For monthly expiry, use 3-letter months
        # This logic might need adjustment based on Kite's exact format
        month = month_map[expiry_date.month]
        day = expiry_date.strftime('%d')
        
        return f"{symbol}{year}{month}{day}{strike}{option_type}"
    
    def get_market_status(self) -> Dict:
        """
        Get current market status
        """
        try:
            now = datetime.now()
            hour = now.hour
            minute = now.minute
            weekday = now.weekday()
            
            # Market hours: 9:15 AM to 3:30 PM on weekdays
            is_market_open = (
                weekday < 5 and  # Monday to Friday
                ((hour == 9 and minute >= 15) or 
                 (hour > 9 and hour < 15) or 
                 (hour == 15 and minute <= 30))
            )
            
            # Pre-market: 9:00 AM to 9:15 AM
            is_premarket = (
                weekday < 5 and
                hour == 9 and minute < 15
            )
            
            # Post-market: 3:30 PM to 4:00 PM  
            is_postmarket = (
                weekday < 5 and
                ((hour == 15 and minute > 30) or
                 (hour == 16 and minute == 0))
            )
            
            return {
                'is_open': is_market_open,
                'is_premarket': is_premarket,
                'is_postmarket': is_postmarket,
                'current_time': now.isoformat(),
                'next_open': self._get_next_market_open() if not is_market_open else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get market status: {e}")
            return {'is_open': False, 'error': str(e)}
    
    def _get_next_market_open(self) -> str:
        """Calculate next market open time"""
        now = datetime.now()
        
        # If it's before 9:15 AM on a weekday
        if now.weekday() < 5 and (now.hour < 9 or (now.hour == 9 and now.minute < 15)):
            next_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        # If it's after market hours on Friday or weekend
        elif now.weekday() >= 4:  # Friday evening or weekend
            days_ahead = 7 - now.weekday()  # Days until Monday
            next_monday = now + timedelta(days=days_ahead)
            next_open = next_monday.replace(hour=9, minute=15, second=0, microsecond=0)
        else:
            # Next day 9:15 AM
            next_open = (now + timedelta(days=1)).replace(hour=9, minute=15, second=0, microsecond=0)
        
        return next_open.isoformat()
    
    def get_historical_data(self, instrument_token: int, from_date: datetime, 
                           to_date: datetime, interval: str = "minute") -> List[Dict]:
        """
        Get historical OHLC data
        
        Args:
            instrument_token: Instrument token (not symbol)
            from_date: Start date
            to_date: End date  
            interval: Candle interval (minute, 3minute, 5minute, 10minute, 15minute, 30minute, 60minute, day)
        """
        try:
            historical_data = self.kite.historical_data(
                instrument_token,
                from_date,
                to_date,
                interval
            )
            
            return historical_data
            
        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            return []
    
    def get_instrument_token(self, trading_symbol: str, exchange: str = "NFO") -> Optional[int]:
        """
        Get instrument token for a trading symbol
        
        Args:
            trading_symbol: Trading symbol (e.g., "NIFTY24DEC1925000CE")
            exchange: Exchange (NSE, NFO, etc.)
        """
        try:
            instruments = self.kite.instruments(exchange)
            
            for instrument in instruments:
                if instrument['tradingsymbol'] == trading_symbol:
                    return instrument['instrument_token']
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get instrument token: {e}")
            return None

# Singleton instance
_kite_market_data_instance = None

def get_kite_market_data_service() -> KiteMarketDataService:
    """Get or create singleton instance of KiteMarketDataService"""
    global _kite_market_data_instance
    if _kite_market_data_instance is None:
        _kite_market_data_instance = KiteMarketDataService()
    return _kite_market_data_instance