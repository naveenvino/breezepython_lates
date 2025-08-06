"""
Breeze API Client
Wrapper for Breeze API operations
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import date, datetime
import aiohttp
import json

from ....config.settings import get_settings

logger = logging.getLogger(__name__)


class BreezeClient:
    """Breeze API client for market data and trading operations"""
    
    def __init__(self):
        self.settings = get_settings().breeze
        self.base_url = "https://api.icicidirect.com/breezeapi/api/v1"
        self.headers = {
            "Content-Type": "application/json",
            "X-SessionToken": self.settings.session_token,
            "X-AppKey": self.settings.api_key
        }
        self.session = None
    
    async def initialize(self):
        """Initialize the client session"""
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)
    
    async def close(self):
        """Close the client session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_historical_data_v2(
        self,
        exchange_code: str,
        stock_code: str,
        product_type: str,
        interval: str,
        from_date: date,
        to_date: date,
        **kwargs
    ) -> Dict[str, Any]:
        """Get historical data from Breeze API"""
        try:
            await self.initialize()
            
            # Format dates
            from_date_str = from_date.strftime("%Y-%m-%dT00:00:00.000Z")
            to_date_str = to_date.strftime("%Y-%m-%dT23:59:59.000Z")
            
            # Build request payload
            payload = {
                "exchange_code": exchange_code,
                "stock_code": stock_code,
                "product_type": product_type,
                "interval": interval,
                "from_date": from_date_str,
                "to_date": to_date_str
            }
            
            # Add optional parameters
            if kwargs.get("strike_price"):
                payload["strike_price"] = kwargs["strike_price"]
            if kwargs.get("expiry_date"):
                payload["expiry_date"] = kwargs["expiry_date"].strftime("%Y-%m-%d")
            if kwargs.get("right"):
                payload["right"] = kwargs["right"]
            
            # Make API request
            url = f"{self.base_url}/historicaldataapi"
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    error_text = await response.text()
                    logger.error(f"API error: {response.status} - {error_text}")
                    return {"Error": f"API error: {response.status}"}
                    
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return {"Error": str(e)}
    
    async def get_option_chain(
        self,
        exchange_code: str,
        underlying: str,
        expiry_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get option chain data"""
        try:
            await self.initialize()
            
            payload = {
                "exchange_code": exchange_code,
                "stock_code": underlying
            }
            
            if expiry_date:
                payload["expiry_date"] = expiry_date.strftime("%Y-%m-%d")
            
            url = f"{self.base_url}/optionchain"
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return {"Success": self._parse_option_chain(data)}
                else:
                    error_text = await response.text()
                    logger.error(f"Option chain error: {response.status} - {error_text}")
                    return {"Error": f"API error: {response.status}"}
                    
        except Exception as e:
            logger.error(f"Error fetching option chain: {e}")
            return {"Error": str(e)}
    
    async def get_quotes(
        self,
        exchange_code: str,
        stock_code: str
    ) -> Dict[str, Any]:
        """Get real-time quotes"""
        try:
            await self.initialize()
            
            payload = {
                "exchange_code": exchange_code,
                "stock_code": stock_code
            }
            
            url = f"{self.base_url}/quotes"
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return {"Success": data}
                else:
                    error_text = await response.text()
                    logger.error(f"Quotes error: {response.status} - {error_text}")
                    return {"Error": f"API error: {response.status}"}
                    
        except Exception as e:
            logger.error(f"Error fetching quotes: {e}")
            return {"Error": str(e)}
    
    def _parse_option_chain(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse option chain data into structured format"""
        try:
            # This is a simplified parser - adjust based on actual API response
            strikes = []
            
            if "Success" in raw_data and isinstance(raw_data["Success"], list):
                # Group by strike price
                strike_map = {}
                
                for option in raw_data["Success"]:
                    strike = option.get("strike_price", 0)
                    if strike not in strike_map:
                        strike_map[strike] = {
                            "strike_price": strike,
                            "call_data": None,
                            "put_data": None
                        }
                    
                    option_data = {
                        "last_price": option.get("ltp", 0),
                        "volume": option.get("volume", 0),
                        "open_interest": option.get("open_interest", 0),
                        "bid_price": option.get("best_bid_price", 0),
                        "ask_price": option.get("best_offer_price", 0),
                        "iv": option.get("implied_volatility")
                    }
                    
                    if option.get("right", "").upper() == "CALL":
                        strike_map[strike]["call_data"] = option_data
                    else:
                        strike_map[strike]["put_data"] = option_data
                
                strikes = list(strike_map.values())
            
            return {
                "strikes": strikes,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error parsing option chain: {e}")
            return {"strikes": []}