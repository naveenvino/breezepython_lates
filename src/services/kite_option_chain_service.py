"""
Kite Option Chain Service - Replaces Breeze for option chain data
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from kiteconnect import KiteConnect
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class KiteOptionChainService:
    def __init__(self):
        self.api_key = os.getenv('KITE_API_KEY')
        self.access_token = os.getenv('KITE_ACCESS_TOKEN')
        self.kite = None
        self._cache = {}
        self._cache_expiry = {}
        self._cache_duration = 60  # Cache for 60 seconds
        self._connect()
    
    def _connect(self):
        """Initialize Kite connection"""
        try:
            if not self.api_key or not self.access_token:
                logger.error("Kite API credentials not found")
                return False
                
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(self.access_token)
            logger.info("Kite Option Chain Service connected")
            return True
        except Exception as e:
            logger.error(f"Failed to connect Kite: {e}")
            return False
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached data if valid"""
        if key in self._cache and key in self._cache_expiry:
            if datetime.now() < self._cache_expiry[key]:
                return self._cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any):
        """Set cache with expiry"""
        self._cache[key] = value
        self._cache_expiry[key] = datetime.now() + timedelta(seconds=self._cache_duration)
    
    def get_option_chain(self, symbol: str = 'NIFTY', strike_range: int = 10, expiry: Optional[str] = None) -> Dict:
        """Get option chain data from Kite"""
        try:
            cache_key = f"chain_{symbol}_{strike_range}_{expiry}"
            cached = self._get_cached(cache_key)
            if cached:
                return cached
            
            if not self.kite:
                if not self._connect():
                    return {"error": "Not connected to Kite"}
            
            # Get current spot price
            spot_data = self.get_spot_price(symbol)
            spot = spot_data.get('spot', 25000)
            
            # Calculate strike range
            atm_strike = round(spot / 50) * 50
            strikes = []
            for i in range(-strike_range, strike_range + 1):
                strikes.append(atm_strike + (i * 50))
            
            # Get current expiry if not provided
            if not expiry:
                expiry = self._get_current_expiry()
            
            chain_data = {
                "symbol": symbol,
                "spot": spot,
                "atm_strike": atm_strike,
                "timestamp": datetime.now().isoformat(),
                "expiry": expiry,
                "strikes": []
            }
            
            # Fetch data for each strike
            for strike in strikes:
                strike_data = {
                    "strike": strike,
                    "CE": self._get_option_quote(symbol, strike, "CE", expiry),
                    "PE": self._get_option_quote(symbol, strike, "PE", expiry)
                }
                chain_data["strikes"].append(strike_data)
            
            self._set_cache(cache_key, chain_data)
            return chain_data
            
        except Exception as e:
            logger.error(f"Error getting option chain: {e}")
            return {"error": str(e)}
    
    def _get_option_quote(self, symbol: str, strike: int, option_type: str, expiry: str) -> Dict:
        """Get single option quote"""
        try:
            # Kite uses different formats for weekly vs monthly expiry
            # Weekly: NIFTY25916 (for 16-Sep-2025)
            # Monthly: NIFTY25SEP (for last Thursday of Sep 2025)
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d")
            
            # Check if it's a monthly expiry (last Thursday of month)
            # For now, assume weekly format for Thursday expiries
            yy = expiry_date.strftime("%y")
            month = expiry_date.month
            day = expiry_date.day
            
            # Format: YYMDD where M is single digit month (9 not 09)
            expiry_fmt = f"{yy}{month}{day}"
            
            trading_symbol = f"{symbol}{expiry_fmt}{strike}{option_type}"
            instrument = f"NFO:{trading_symbol}"
            
            logger.debug(f"Fetching quote for instrument: {instrument}")
            quote = self.kite.quote([instrument])
            
            if instrument in quote:
                data = quote[instrument]
                logger.debug(f"Got quote for {instrument}: LTP={data.get('last_price', 0)}")
                return {
                    "ltp": data.get("last_price", 0),
                    "bid": data.get("depth", {}).get("buy", [{}])[0].get("price", 0),
                    "ask": data.get("depth", {}).get("sell", [{}])[0].get("price", 0),
                    "volume": data.get("volume", 0),
                    "oi": data.get("oi", 0),
                    "change": data.get("net_change", 0),
                    "pchange": data.get("net_change", 0) / data.get("last_price", 1) * 100 if data.get("last_price", 0) > 0 else 0,
                    "iv": 0,  # Kite doesn't provide IV directly
                    "delta": 0,  # Calculate Greeks separately if needed
                    "gamma": 0,
                    "theta": 0,
                    "vega": 0
                }
            else:
                logger.warning(f"No quote data for {instrument}")
                return {"ltp": 0, "bid": 0, "ask": 0, "volume": 0, "oi": 0}
        except Exception as e:
            logger.error(f"Error getting option quote for {instrument}: {e}")
            return {"ltp": 0, "bid": 0, "ask": 0, "volume": 0, "oi": 0}
    
    def get_spot_price(self, symbol: str = 'NIFTY') -> Dict:
        """Get spot price from Kite"""
        try:
            cache_key = f"spot_{symbol}"
            cached = self._get_cached(cache_key)
            if cached:
                return cached
            
            if not self.kite:
                if not self._connect():
                    return {"spot": 0, "error": "Not connected"}
            
            index_map = {
                'NIFTY': 'NSE:NIFTY 50',
                'BANKNIFTY': 'NSE:NIFTY BANK'
            }
            
            instrument = index_map.get(symbol, 'NSE:NIFTY 50')
            quote = self.kite.quote([instrument])
            
            if instrument in quote:
                spot = quote[instrument].get('last_price', 0)
                result = {
                    "spot": spot,
                    "timestamp": datetime.now().isoformat(),
                    "source": "KITE"
                }
                self._set_cache(cache_key, result)
                return result
                
            return {"spot": 0, "error": "No data"}
            
        except Exception as e:
            logger.error(f"Error getting spot price: {e}")
            return {"spot": 0, "error": str(e)}
    
    def get_option_quote(self, strike: int, option_type: str, expiry: Optional[str] = None) -> Dict:
        """Get single option quote with caching"""
        try:
            if not expiry:
                expiry = self._get_current_expiry()
            
            cache_key = f"quote_NIFTY_{strike}_{option_type}_{expiry}"
            cached = self._get_cached(cache_key)
            if cached:
                return cached
            
            result = self._get_option_quote("NIFTY", strike, option_type, expiry)
            self._set_cache(cache_key, result)
            return result
            
        except Exception as e:
            logger.error(f"Error getting option quote: {e}")
            return {"ltp": 0, "error": str(e)}
    
    def _get_current_expiry(self) -> str:
        """Get current weekly expiry (Tuesday)"""
        today = datetime.now()
        days_until_tuesday = (1 - today.weekday()) % 7
        if days_until_tuesday == 0 and today.hour >= 15:
            days_until_tuesday = 7
        next_tuesday = today + timedelta(days=days_until_tuesday)
        return next_tuesday.strftime("%Y-%m-%d")
    
    def get_ltp(self, strike: int, option_type: str, expiry: Optional[str] = None) -> float:
        """Get Last Traded Price for an option"""
        quote = self.get_option_quote(strike, option_type, expiry)
        return quote.get("ltp", 0)

# Singleton instance
_kite_option_service = None

def get_kite_option_chain_service() -> KiteOptionChainService:
    """Get singleton instance of Kite option chain service"""
    global _kite_option_service
    if _kite_option_service is None:
        _kite_option_service = KiteOptionChainService()
    return _kite_option_service