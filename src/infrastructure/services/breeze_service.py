"""
Breeze API Service
Service for interacting with Breeze Connect API
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncio
from datetime import timedelta
# from breeze_connect import BreezeConnect  # Commented out for testing

from ...config.settings import get_settings

logger = logging.getLogger(__name__)


class BreezeService:
    """Service for Breeze API interactions"""
    
    def __init__(self):
        self.settings = get_settings()
        self._breeze = None
        self._initialized = False
    
    def _initialize(self):
        """Initialize Breeze connection"""
        if not self._initialized:
            try:
                # Import here to avoid issues if breeze_connect is not installed
                try:
                    from breeze_connect import BreezeConnect
                    # Get credentials - check both standard fields and extra fields
                    api_key = self.settings.breeze.api_key or getattr(self.settings.breeze, 'breeze_api_key', '')
                    api_secret = self.settings.breeze.api_secret or getattr(self.settings.breeze, 'breeze_api_secret', '')
                    session_token = self.settings.breeze.session_token or getattr(self.settings.breeze, 'breeze_api_session', '')
                    
                    if not api_key or not api_secret:
                        raise ValueError("Breeze API credentials not found in settings")
                    
                    self._breeze = BreezeConnect(api_key=api_key)
                    # Generate session without checking customer details
                    try:
                        self._breeze.generate_session(
                            api_secret=api_secret,
                            session_token=session_token
                        )
                        self._initialized = True
                        logger.info("Breeze API session generated successfully")
                    except Exception as session_error:
                        # Log but don't fail - session might still work
                        logger.warning(f"Session generation warning: {session_error}")
                        self._initialized = True  # Still mark as initialized
                except ImportError:
                    logger.warning("breeze_connect module not installed. Install with: pip install breeze-connect")
                    self._breeze = None
                    self._initialized = True  # Mark as initialized to avoid repeated attempts
            except Exception as e:
                logger.error(f"Failed to initialize Breeze API: {e}")
                self._breeze = None
                self._initialized = True  # Mark as initialized to avoid repeated attempts
                # Don't raise - let individual methods handle the None breeze object
    
    async def get_historical_data(
        self,
        interval: str,
        from_date: datetime,
        to_date: datetime,
        stock_code: str,
        exchange_code: str = "NSE",
        product_type: str = "cash",
        strike_price: Optional[str] = None,
        right: Optional[str] = None,
        expiry_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get historical data from Breeze API
        
        Args:
            interval: Time interval (1minute, 5minute, 30minute, 1hour, 1day)
            from_date: Start date
            to_date: End date
            stock_code: Stock symbol
            exchange_code: Exchange code (NSE, NFO, etc.)
            product_type: Product type (cash, futures, options)
            
        Returns:
            Dict containing historical data
        """
        # Initialize connection
        self._initialize()
        
        # Check if Breeze is available
        if self._breeze is None:
            logger.warning("Breeze API not available. Returning empty data.")
            return {
                "Success": [],
                "Error": "Breeze API not initialized. Please check credentials or install breeze-connect"
            }
        
        try:
            # Run in thread pool since breeze_connect is synchronous
            loop = asyncio.get_event_loop()
            # Build parameters based on product type
            if product_type == "options" and strike_price and right and expiry_date:
                # Use lambda to pass keyword arguments
                result = await loop.run_in_executor(
                    None,
                    lambda: self._breeze.get_historical_data_v2(
                        interval=interval,
                        from_date=from_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                        to_date=to_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                        stock_code=stock_code,
                        exchange_code=exchange_code,
                        product_type=product_type,
                        expiry_date=expiry_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                        right=right,
                        strike_price=strike_price
                    )
                )
            else:
                result = await loop.run_in_executor(
                    None,
                    lambda: self._breeze.get_historical_data_v2(
                        interval=interval,
                        from_date=from_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                        to_date=to_date.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                        stock_code=stock_code,
                        exchange_code=exchange_code,
                        product_type=product_type
                    )
                )
            
            logger.debug(f"Breeze API response for {stock_code}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return {
                "Success": [],
                "Error": str(e)
            }
    
    async def get_option_chain(
        self,
        stock_code: str,
        exchange_code: str = "NFO",
        product_type: str = "options",
        expiry_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get option chain data"""
        self._initialize()
        
        # Check if Breeze is available
        if self._breeze is None:
            logger.warning("Breeze API not available. Returning empty data.")
            return {
                "Success": [],
                "Error": "Breeze API not initialized"
            }
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._breeze.get_option_chain_quotes,
                stock_code,
                exchange_code,
                product_type,
                expiry_date.strftime("%Y-%m-%d") if expiry_date else None,
                None  # strike_price
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching option chain: {e}")
            raise
    
    async def _get_simulated_data(
        self,
        interval: str,
        from_date: datetime,
        to_date: datetime,
        stock_code: str,
        exchange_code: str,
        product_type: str
    ) -> Dict[str, Any]:
        """Get simulated data for testing"""
        # Generate some dummy data
        data = []
        current = from_date
        base_price = 20000  # Base price for NIFTY
        
        while current <= to_date:
            # Skip weekends
            if current.weekday() < 5:  # Monday = 0, Friday = 4
                # Generate hourly data for market hours (9:15 AM to 3:30 PM)
                if interval == "1hour":
                    # Generate hourly candles starting from 9:15 AM
                    # First candle: 9:15-10:15 (labeled as 9:00 in some systems)
                    # Second candle: 10:15-11:15 (labeled as 10:00)
                    # And so on...
                    candle_times = []
                    
                    # Option 1: Label with candle start time (9:15, 10:15, etc.)
                    # for h in range(9, 16):
                    #     if h == 9:
                    #         candle_times.append((9, 15))
                    #     else:
                    #         candle_times.append((h, 15))
                    
                    # Option 2: Label with hour (9:00, 10:00, etc.) - matches common convention
                    candle_times = [
                        (9, 0),   # 9:15-10:15 candle labeled as 9:00
                        (10, 0),  # 10:15-11:15 candle labeled as 10:00
                        (11, 0),  # 11:15-12:15 candle labeled as 11:00
                        (12, 0),  # 12:15-13:15 candle labeled as 12:00
                        (13, 0),  # 13:15-14:15 candle labeled as 13:00
                        (14, 0),  # 14:15-15:15 candle labeled as 14:00
                        (15, 0),  # 15:15-15:30 candle labeled as 15:00
                    ]
                    
                    for hour, minute in candle_times:
                        timestamp = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        
                        # Generate OHLC data with some randomness
                        import random
                        open_price = base_price + random.uniform(-100, 100)
                        high_price = open_price + random.uniform(0, 50)
                        low_price = open_price - random.uniform(0, 50)
                        close_price = random.uniform(low_price, high_price)
                        
                        data.append({
                            "datetime": timestamp.isoformat(),
                            "stock_code": stock_code,
                            "exchange_code": exchange_code,
                            "open": open_price,
                            "high": high_price,
                            "low": low_price,
                            "close": close_price,
                            "volume": random.randint(100000, 1000000)
                        })
                        
                        # Update base price for next candle
                        base_price = close_price
            
            # Move to next day
            current = current.replace(hour=0, minute=0, second=0, microsecond=0)
            current += timedelta(days=1)
        
        return {"Success": data}
    
    async def _get_simulated_option_chain(
        self,
        stock_code: str,
        exchange_code: str,
        product_type: str,
        expiry_date: Optional[datetime]
    ) -> Dict[str, Any]:
        """Get simulated option chain for testing"""
        # Generate dummy option chain
        import random
        
        spot_price = 20000
        strikes = list(range(19000, 21000, 50))
        
        data = []
        for strike in strikes:
            for option_type in ['CE', 'PE']:
                # Calculate basic option price (simplified)
                if option_type == 'CE':
                    intrinsic = max(0, spot_price - strike)
                else:
                    intrinsic = max(0, strike - spot_price)
                
                time_value = random.uniform(10, 100)
                option_price = intrinsic + time_value
                
                data.append({
                    "strike_price": strike,
                    "option_type": option_type,
                    "ltp": option_price,
                    "volume": random.randint(1000, 10000),
                    "oi": random.randint(10000, 100000),
                    "bid": option_price - random.uniform(0.5, 2),
                    "ask": option_price + random.uniform(0.5, 2)
                })
        
        return {"Success": data}