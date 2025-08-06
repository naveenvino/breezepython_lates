"""
Ultra-fast async implementation for maximum parallelism
"""
import asyncio
import aiohttp
from typing import List, Dict, Tuple
import time
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)

class AsyncBreezeClient:
    """Async wrapper for Breeze API calls"""
    
    def __init__(self, api_key: str, api_secret: str, session_token: str, max_concurrent: int = 20):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session_token = session_token
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
    
    async def get_historical_data_async(self, **params) -> Dict:
        """Async version of get_historical_data_v2"""
        async with self.semaphore:  # Limit concurrent requests
            # Simulate Breeze API call (replace with actual implementation)
            url = "https://api.icicidirect.com/breezeapi/historicalcharts"
            headers = {
                "api-key": self.api_key,
                "api-secret": self.api_secret,
                "session-token": self.session_token
            }
            
            try:
                async with self.session.get(url, params=params, headers=headers) as response:
                    return await response.json()
            except Exception as e:
                logger.error(f"Async API error: {e}")
                return {"Error": str(e)}

async def collect_options_ultra_async(
    request_date: date, 
    symbol: str,
    strikes: List[int],
    expiry_date: date,
    api_credentials: Dict
) -> Dict:
    """Collect all options data asynchronously"""
    
    start_time = time.time()
    tasks = []
    
    async with AsyncBreezeClient(**api_credentials, max_concurrent=20) as client:
        # Create all tasks
        for strike in strikes:
            for option_type in ['CE', 'PE']:
                task = fetch_single_option_async(
                    client, request_date, symbol, strike, option_type, expiry_date
                )
                tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    total_records = 0
    errors = []
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            errors.append(str(result))
        elif result:
            total_records += len(result)
    
    duration = time.time() - start_time
    
    return {
        "total_records": total_records,
        "total_strikes": len(strikes) * 2,
        "errors": errors,
        "duration": duration,
        "avg_time_per_strike": duration / (len(strikes) * 2) if strikes else 0
    }

async def fetch_single_option_async(
    client: AsyncBreezeClient,
    request_date: date,
    symbol: str,
    strike: int,
    option_type: str,
    expiry_date: date
) -> List[Dict]:
    """Fetch single option data asynchronously"""
    
    from_datetime = datetime.combine(request_date, datetime.min.time())
    to_datetime = datetime.combine(request_date, datetime.max.time())
    
    params = {
        "interval": "5minute",
        "from_date": from_datetime.strftime("%Y-%m-%dT00:00:00.000Z"),
        "to_date": to_datetime.strftime("%Y-%m-%dT23:59:59.000Z"),
        "stock_code": symbol,
        "exchange_code": "NFO",
        "product_type": "options",
        "expiry_date": expiry_date.strftime("%Y-%m-%dT00:00:00.000Z"),
        "right": "call" if option_type == "CE" else "put",
        "strike_price": str(strike)
    }
    
    result = await client.get_historical_data_async(**params)
    
    if result and 'Success' in result:
        return result['Success']
    return []

# Example usage
async def test_async_performance():
    """Test async performance"""
    strikes = list(range(24000, 26000, 50))  # 40 strikes
    
    print(f"Testing async collection for {len(strikes)} strikes...")
    
    api_creds = {
        "api_key": "your_key",
        "api_secret": "your_secret", 
        "session_token": "your_token"
    }
    
    result = await collect_options_ultra_async(
        date(2024, 10, 31),
        "NIFTY",
        strikes,
        date(2024, 10, 31),
        api_creds
    )
    
    print(f"Completed in {result['duration']:.2f}s")
    print(f"Average time per strike: {result['avg_time_per_strike']:.3f}s")
    print(f"Total records: {result['total_records']}")

# Run: asyncio.run(test_async_performance())