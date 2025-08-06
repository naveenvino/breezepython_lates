"""
Breeze Data Collector Service
Concrete implementation of IDataCollector using Breeze API
"""
import logging
import asyncio
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from decimal import Decimal
import pandas as pd

from ...application.interfaces.idata_collector import IDataCollector
from ..brokers.breeze.breeze_client import BreezeClient
from ...config.settings import get_settings
from ...domain.entities.market_data import MarketData, TimeInterval
from ...domain.entities.option import Option, OptionType
from ...domain.value_objects.strike_price import StrikePrice
from ..repositories.market_data_repository import MarketDataRepository
from ..repositories.options_repository import OptionsHistoricalDataRepository

logger = logging.getLogger(__name__)


class BreezeDataCollector(IDataCollector):
    """Breeze API implementation of data collector"""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = BreezeClient()
        self.market_data_repo = MarketDataRepository()
        self.options_data_repo = OptionsHistoricalDataRepository()
        self._initialized = False
    
    async def _ensure_initialized(self):
        """Ensure Breeze client is initialized"""
        if not self._initialized:
            await self.client.initialize()
            self._initialized = True
    
    async def collect_index_data(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
        interval: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Collect index/NIFTY data"""
        await self._ensure_initialized()
        
        try:
            logger.info(f"Collecting {symbol} data from {from_date} to {to_date}, interval: {interval}")
            
            # Map interval to Breeze format
            interval_map = {
                "1minute": "1minute",
                "5minute": "5minute",
                "30minute": "30minute",
                "1hour": "1hour",
                "1day": "1day"
            }
            breeze_interval = interval_map.get(interval, "1hour")
            
            # Collect data from Breeze
            result = await self.client.get_historical_data_v2(
                exchange_code="NSE",
                stock_code=symbol,
                product_type="cash",
                interval=breeze_interval,
                from_date=from_date,
                to_date=to_date
            )
            
            if not result or "Success" not in result:
                return {
                    "records_collected": 0,
                    "records_failed": 0,
                    "errors": [result.get("Error", "Unknown error")]
                }
            
            # Process and save data
            data_list = result.get("Success", [])
            records_collected = 0
            records_failed = 0
            errors = []
            
            # Convert interval string to enum
            time_interval = self._get_time_interval(interval)
            
            # Create MarketData entities
            market_data_entities = []
            for record in data_list:
                try:
                    market_data = MarketData(
                        symbol=f"{symbol} 50",  # e.g., "NIFTY 50"
                        timestamp=datetime.strptime(record['datetime'], '%Y-%m-%d %H:%M:%S'),
                        open=Decimal(str(record['open'])),
                        high=Decimal(str(record['high'])),
                        low=Decimal(str(record['low'])),
                        close=Decimal(str(record['close'])),
                        volume=int(record['volume']),
                        interval=time_interval,
                        open_interest=record.get('open_interest')
                    )
                    market_data_entities.append(market_data)
                except Exception as e:
                    logger.error(f"Error processing record: {e}")
                    records_failed += 1
                    errors.append(str(e))
            
            # Save to database
            if market_data_entities:
                try:
                    saved_count = await self.market_data_repo.save_batch(market_data_entities)
                    records_collected = saved_count
                    logger.info(f"Saved {saved_count} records to database")
                except Exception as e:
                    logger.error(f"Error saving to database: {e}")
                    errors.append(f"Database error: {str(e)}")
                    records_failed = len(market_data_entities)
            
            return {
                "records_collected": records_collected,
                "records_failed": records_failed,
                "total_records": len(data_list),
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error collecting index data: {e}")
            return {
                "records_collected": 0,
                "records_failed": 1,
                "errors": [str(e)]
            }
    
    async def collect_options_data(
        self,
        underlying: str,
        expiry_date: date,
        strikes: List[int],
        from_date: date,
        to_date: date,
        interval: str,
        option_types: List[str] = ["CE", "PE"],
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Collect options data for multiple strikes"""
        await self._ensure_initialized()
        
        records_collected = 0
        records_skipped = 0
        records_failed = 0
        errors = []
        
        for strike in strikes:
            for option_type in option_types:
                try:
                    # Collect data for this strike/type
                    result = await self._collect_single_option_data(
                        underlying=underlying,
                        expiry_date=expiry_date,
                        strike=strike,
                        option_type=option_type,
                        from_date=from_date,
                        to_date=to_date,
                        interval=interval,
                        force_refresh=force_refresh
                    )
                    
                    records_collected += result.get("collected", 0)
                    records_skipped += result.get("skipped", 0)
                    records_failed += result.get("failed", 0)
                    
                    if result.get("error"):
                        errors.append({
                            "strike": strike,
                            "type": option_type,
                            "error": result["error"]
                        })
                        
                except Exception as e:
                    logger.error(f"Error collecting {underlying} {strike} {option_type}: {e}")
                    records_failed += 1
                    errors.append({
                        "strike": strike,
                        "type": option_type,
                        "error": str(e)
                    })
        
        return {
            "records_collected": records_collected,
            "records_skipped": records_skipped,
            "records_failed": records_failed,
            "errors": errors
        }
    
    async def collect_options_data_parallel(
        self,
        underlying: str,
        expiry_date: date,
        strikes: List[int],
        from_date: date,
        to_date: date,
        interval: str,
        option_types: List[str] = ["CE", "PE"],
        max_workers: int = 5,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Collect options data in parallel"""
        await self._ensure_initialized()
        
        # Create tasks for parallel execution
        tasks = []
        for strike in strikes:
            for option_type in option_types:
                task = self._collect_single_option_data(
                    underlying=underlying,
                    expiry_date=expiry_date,
                    strike=strike,
                    option_type=option_type,
                    from_date=from_date,
                    to_date=to_date,
                    interval=interval,
                    force_refresh=force_refresh
                )
                tasks.append(task)
        
        # Execute in batches
        results = []
        for i in range(0, len(tasks), max_workers):
            batch = tasks[i:i + max_workers]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            results.extend(batch_results)
        
        # Aggregate results
        records_collected = 0
        records_skipped = 0
        records_failed = 0
        errors = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                records_failed += 1
                errors.append({"error": str(result)})
            else:
                records_collected += result.get("collected", 0)
                records_skipped += result.get("skipped", 0)
                records_failed += result.get("failed", 0)
                if result.get("error"):
                    errors.append(result["error"])
        
        return {
            "records_collected": records_collected,
            "records_skipped": records_skipped,
            "records_failed": records_failed,
            "errors": errors
        }
    
    async def collect_option_chain(
        self,
        symbol: str,
        expiry_date: Optional[date] = None,
        save_to_db: bool = True
    ) -> Dict[str, Any]:
        """Collect complete option chain"""
        await self._ensure_initialized()
        
        try:
            # Get option chain from Breeze
            result = await self.client.get_option_chain(
                exchange_code="NFO",
                underlying=symbol,
                expiry_date=expiry_date
            )
            
            if not result or "Success" not in result:
                return {
                    "error": result.get("Error", "Failed to fetch option chain"),
                    "chain_data": {}
                }
            
            chain_data = result.get("Success", {})
            
            # Process chain data
            processed_chain = {
                "symbol": symbol,
                "expiry_date": expiry_date,
                "timestamp": datetime.now(),
                "strikes": []
            }
            
            # Extract strikes data
            for strike_data in chain_data.get("strikes", []):
                strike_info = {
                    "strike_price": strike_data.get("strike_price"),
                    "call_data": strike_data.get("call_data"),
                    "put_data": strike_data.get("put_data")
                }
                processed_chain["strikes"].append(strike_info)
            
            # Save to database if requested
            if save_to_db and processed_chain["strikes"]:
                # Implementation would save to database
                pass
            
            return {
                "chain_data": processed_chain,
                "strikes_count": len(processed_chain["strikes"])
            }
            
        except Exception as e:
            logger.error(f"Error collecting option chain: {e}")
            return {
                "error": str(e),
                "chain_data": {}
            }
    
    async def collect_real_time_quotes(
        self,
        symbols: List[str]
    ) -> Dict[str, Any]:
        """Collect real-time quotes for symbols"""
        await self._ensure_initialized()
        
        quotes = {}
        errors = []
        
        for symbol in symbols:
            try:
                result = await self.client.get_quotes(
                    exchange_code="NSE" if "NIFTY" in symbol else "NFO",
                    stock_code=symbol
                )
                
                if result and "Success" in result:
                    quotes[symbol] = result["Success"]
                else:
                    errors.append({
                        "symbol": symbol,
                        "error": result.get("Error", "Unknown error")
                    })
                    
            except Exception as e:
                logger.error(f"Error getting quote for {symbol}: {e}")
                errors.append({
                    "symbol": symbol,
                    "error": str(e)
                })
        
        return {
            "quotes": quotes,
            "errors": errors
        }
    
    async def test_connection(self) -> bool:
        """Test connection to data source"""
        try:
            await self._ensure_initialized()
            
            # Try to get a simple quote
            result = await self.client.get_quotes(
                exchange_code="NSE",
                stock_code="NIFTY"
            )
            
            return result is not None and "Success" in result
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def _collect_single_option_data(
        self,
        underlying: str,
        expiry_date: date,
        strike: int,
        option_type: str,
        from_date: date,
        to_date: date,
        interval: str,
        force_refresh: bool
    ) -> Dict[str, Any]:
        """Collect data for a single option"""
        try:
            # Construct option symbol
            symbol = f"{underlying}{expiry_date.strftime('%y%b').upper()}{strike}{option_type}"
            
            # Get historical data
            result = await self.client.get_historical_data_v2(
                exchange_code="NFO",
                stock_code=symbol,
                product_type="options",
                interval=interval,
                from_date=from_date,
                to_date=to_date,
                strike_price=str(strike),
                expiry_date=expiry_date,
                right=option_type.lower()
            )
            
            if not result or "Success" not in result:
                return {
                    "collected": 0,
                    "skipped": 0,
                    "failed": 1,
                    "error": result.get("Error", "Unknown error")
                }
            
            # Process data
            data_list = result.get("Success", [])
            records_to_save = []
            
            for record in data_list:
                try:
                    option_data = {
                        "symbol": symbol,
                        "underlying": underlying,
                        "strike_price": strike,
                        "expiry_date": expiry_date,
                        "option_type": option_type,
                        "timestamp": datetime.strptime(record['datetime'], '%Y-%m-%d %H:%M:%S'),
                        "open": float(record['open']),
                        "high": float(record['high']),
                        "low": float(record['low']),
                        "close": float(record['close']),
                        "volume": int(record['volume']),
                        "open_interest": record.get('open_interest'),
                        "interval": interval
                    }
                    records_to_save.append(option_data)
                except Exception as e:
                    logger.error(f"Error processing option record: {e}")
            
            # Save to database
            if records_to_save:
                saved_count = await self.options_data_repo.save_historical_data(records_to_save)
                return {
                    "collected": saved_count,
                    "skipped": len(records_to_save) - saved_count,
                    "failed": 0
                }
            
            return {
                "collected": 0,
                "skipped": 0,
                "failed": 0
            }
            
        except Exception as e:
            logger.error(f"Error collecting single option data: {e}")
            return {
                "collected": 0,
                "skipped": 0,
                "failed": 1,
                "error": str(e)
            }
    
    def _get_time_interval(self, interval_str: str) -> TimeInterval:
        """Convert interval string to TimeInterval enum"""
        interval_map = {
            "1minute": TimeInterval.ONE_MINUTE,
            "5minute": TimeInterval.FIVE_MINUTE,
            "30minute": TimeInterval.THIRTY_MINUTE,
            "1hour": TimeInterval.ONE_HOUR,
            "1day": TimeInterval.ONE_DAY
        }
        return interval_map.get(interval_str, TimeInterval.ONE_HOUR)