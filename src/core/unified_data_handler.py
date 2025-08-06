"""
Unified Data Handler - Single Source of Truth for All Data Operations
Implements all standards from TECHNICAL_SPEC.md
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, time
from decimal import Decimal
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import func

from ..infrastructure.services.breeze_service_simple import BreezeServiceSimple as BreezeService
from ..infrastructure.database.models import NiftyIndexData, OptionsHistoricalData
from ..infrastructure.database.database_manager import get_db_manager
from ..utils.market_hours import is_within_market_hours, BREEZE_DATA_START, BREEZE_DATA_END
from ..infrastructure.services.hourly_aggregation_service import HourlyAggregationService

logger = logging.getLogger(__name__)


class DataFetchResult:
    """Result of data fetch operation with metrics"""
    def __init__(self):
        self.total_records = 0
        self.records_added = 0
        self.records_skipped = 0
        self.errors = []
        self.start_time = datetime.now()
        self.five_minute_records = 0
        self.hourly_records = 0
    
    @property
    def elapsed_seconds(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()
    
    @property
    def records_per_second(self) -> float:
        elapsed = self.elapsed_seconds
        return self.records_added / elapsed if elapsed > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_records": self.total_records,
            "records_added": {
                "five_minute": self.five_minute_records,
                "hourly": self.hourly_records,
                "total": self.records_added
            },
            "records_skipped": self.records_skipped,
            "errors": self.errors,
            "performance": {
                "time_taken_seconds": round(self.elapsed_seconds, 2),
                "records_per_second": round(self.records_per_second, 2)
            }
        }


class UnifiedDataHandler:
    """
    Single source of truth for all data operations
    Implements ALL standards from TECHNICAL_SPEC.md
    """
    
    def __init__(self, breeze_service: BreezeService = None, db_manager=None):
        self.breeze_service = breeze_service or BreezeService()
        self.db_manager = db_manager or get_db_manager()
        self.hourly_aggregation_service = HourlyAggregationService(self.db_manager)
        
        # Performance settings
        self.max_workers = 5
        self.rate_limit_delay = 0.5
        self._last_api_call = 0
        
        logger.info("UnifiedDataHandler initialized with correct standards")
    
    async def fetch_nifty_data(
        self, 
        from_date: datetime, 
        to_date: datetime,
        symbol: str = "NIFTY",
        force_refresh: bool = False
    ) -> DataFetchResult:
        """
        Fetch NIFTY data with ALL corrections applied:
        - 5-minute intervals (NOT 30-minute)
        - IST timezone (NO UTC conversion)
        - Market hours filtering (9:20-15:35)
        - Automatic hourly aggregation
        """
        result = DataFetchResult()
        logger.info(f"Fetching NIFTY data from {from_date} to {to_date} with CORRECT standards")
        
        try:
            logger.info(f"About to call breeze_service.get_historical_data...")
            logger.info(f"Breeze service type: {type(self.breeze_service)}")
            
            # CRITICAL: Must use 5-minute data
            data = await self.breeze_service.get_historical_data(
                interval="5minute",  # MUST be 5minute as per TECHNICAL_SPEC.md
                from_date=from_date,
                to_date=to_date,
                stock_code=symbol,
                exchange_code="NSE",
                product_type="cash"
            )
            
            logger.info(f"Breeze API call completed. Result type: {type(data)}")
            logger.info(f"Data keys: {data.keys() if data else 'None'}")
            logger.info(f"Has Success key: {'Success' in data if data else False}")
            
            if data and 'Success' in data:
                records = data['Success']
                result.total_records = len(records)
                
                # Log sample timestamp to verify format
                if records:
                    logger.info(f"Sample NIFTY timestamp from Breeze: '{records[0].get('datetime', '')}'")
                
                # Process and store 5-minute data
                with self.db_manager.get_session() as session:
                    for record in records:
                        try:
                            # Use our correct implementation
                            nifty_data = NiftyIndexData.from_breeze_data(record, symbol)
                            
                            if nifty_data is None:
                                # Filtered out (outside market hours)
                                result.records_skipped += 1
                                continue
                            
                            # Check if exists
                            exists = session.query(NiftyIndexData).filter(
                                NiftyIndexData.symbol == symbol,
                                NiftyIndexData.timestamp == nifty_data.timestamp,
                                NiftyIndexData.interval == "5minute"
                            ).first()
                            
                            if not exists:
                                session.add(nifty_data)
                                result.five_minute_records += 1
                                result.records_added += 1
                            else:
                                result.records_skipped += 1
                                
                        except Exception as e:
                            logger.error(f"Error processing record: {e}")
                            result.errors.append(str(e))
                    
                    session.commit()
                
                # Create hourly aggregations
                if result.five_minute_records > 0:
                    logger.info("Creating hourly aggregations from 5-minute data")
                    hourly_count = await self._create_hourly_aggregations(from_date, to_date, symbol)
                    result.hourly_records = hourly_count
                    result.records_added += hourly_count
                    
            else:
                error_msg = f"No data returned from Breeze API: {data}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error fetching NIFTY data: {e}", exc_info=True)
            
            # If it's the customer details error, try direct approach
            if "Unable to retrieve customer details" in error_msg:
                logger.info("Got customer details error, trying direct sync approach...")
                try:
                    # Try synchronous call directly
                    if hasattr(self.breeze_service, 'get_historical_data_sync'):
                        data = self.breeze_service.get_historical_data_sync(
                            interval="5minute",
                            from_date=from_date,
                            to_date=to_date,
                            stock_code=symbol
                        )
                        
                        if data and 'Success' in data:
                            # Process the data as normal
                            records = data['Success']
                            result.total_records = len(records)
                            logger.info(f"Direct sync approach worked! Got {len(records)} records")
                            
                            # Continue with normal processing
                            with self.db_manager.get_session() as session:
                                for record in records:
                                    try:
                                        nifty_data = NiftyIndexData.from_breeze_data(record, symbol)
                                        if nifty_data is None:
                                            result.records_skipped += 1
                                            continue
                                        
                                        exists = session.query(NiftyIndexData).filter(
                                            NiftyIndexData.symbol == symbol,
                                            NiftyIndexData.timestamp == nifty_data.timestamp,
                                            NiftyIndexData.interval == "5minute"
                                        ).first()
                                        
                                        if not exists:
                                            session.add(nifty_data)
                                            result.five_minute_records += 1
                                            result.records_added += 1
                                        else:
                                            result.records_skipped += 1
                                    except Exception as e:
                                        logger.error(f"Error processing record: {e}")
                                        result.errors.append(str(e))
                                
                                session.commit()
                            
                            # Create hourly aggregations if needed
                            if result.five_minute_records > 0:
                                logger.info("Creating hourly aggregations from 5-minute data")
                                hourly_count = await self._create_hourly_aggregations(from_date, to_date, symbol)
                                result.hourly_records = hourly_count
                                result.records_added += hourly_count
                            
                            # Return without adding error
                            logger.info(f"NIFTY data fetch completed via sync fallback: {result.to_dict()}")
                            return result
                except Exception as e2:
                    logger.error(f"Direct sync approach also failed: {e2}")
                    result.errors.append(f"Customer details error and fallback failed: {str(e2)}")
            elif "Session expired" in error_msg:
                result.errors.append("Session expired - please provide a fresh session token in .env file (BREEZE_API_SESSION)")
            else:
                result.errors.append(f"Unexpected error: {error_msg}")
            
            # Log the type of exception for debugging
            logger.error(f"Exception type: {type(e).__name__}")
        
        logger.info(f"NIFTY data fetch completed: {result.to_dict()}")
        return result
    
    async def fetch_options_data_batch(
        self,
        strikes: List[int],
        expiry_date: datetime,
        from_date: datetime,
        to_date: datetime,
        symbol: str = "NIFTY",
        option_types: List[str] = ["CE", "PE"]
    ) -> DataFetchResult:
        """
        Fetch options data in parallel batches
        Uses correct timezone handling for options (UTC to IST conversion)
        """
        result = DataFetchResult()
        logger.info(f"Fetching options data for {len(strikes)} strikes in parallel")
        
        # Create tasks for all strike/option type combinations
        tasks = []
        for strike in strikes:
            for option_type in option_types:
                tasks.append({
                    'strike': strike,
                    'option_type': option_type,
                    'symbol': symbol,
                    'expiry_date': expiry_date,
                    'from_date': from_date,
                    'to_date': to_date
                })
        
        # Process in parallel with thread pool
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._fetch_single_option, task): task
                for task in tasks
            }
            
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    option_result = future.result()
                    result.records_added += option_result['records_added']
                    result.records_skipped += option_result['records_skipped']
                    result.total_records += option_result['total_records']
                    
                    if option_result['errors']:
                        result.errors.extend(option_result['errors'])
                        
                except Exception as e:
                    error_msg = f"Error fetching {task['strike']}{task['option_type']}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
        
        logger.info(f"Options batch fetch completed: {result.to_dict()}")
        return result
    
    def _fetch_single_option(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch single option contract with rate limiting"""
        option_result = {
            'records_added': 0,
            'records_skipped': 0,
            'total_records': 0,
            'errors': []
        }
        
        try:
            # Rate limiting
            time_since_last = datetime.now().timestamp() - self._last_api_call
            if time_since_last < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - time_since_last)
            self._last_api_call = datetime.now().timestamp()
            
            # Fetch from Breeze (synchronous call)
            # Note: This needs to be converted to sync or use asyncio properly
            data = self._fetch_option_data_sync(
                task['symbol'],
                task['strike'],
                task['option_type'],
                task['expiry_date'],
                task['from_date'],
                task['to_date']
            )
            
            if data and 'Success' in data:
                records = data['Success']
                option_result['total_records'] = len(records)
                
                # Process and store
                with self.db_manager.get_session() as session:
                    for record in records:
                        try:
                            # Options use from_breeze_data (handles UTC correctly)
                            option_data = OptionsHistoricalData.from_breeze_data(record)
                            
                            if option_data is None:
                                option_result['records_skipped'] += 1
                                continue
                            
                            # Check if exists
                            exists = session.query(OptionsHistoricalData).filter(
                                OptionsHistoricalData.trading_symbol == option_data.trading_symbol,
                                OptionsHistoricalData.timestamp == option_data.timestamp
                            ).first()
                            
                            if not exists:
                                session.add(option_data)
                                option_result['records_added'] += 1
                            else:
                                option_result['records_skipped'] += 1
                                
                        except Exception as e:
                            option_result['errors'].append(str(e))
                    
                    session.commit()
                    
        except Exception as e:
            option_result['errors'].append(str(e))
        
        return option_result
    
    def _fetch_option_data_sync(
        self, 
        symbol: str,
        strike: int,
        option_type: str,
        expiry: datetime,
        from_date: datetime,
        to_date: datetime
    ) -> Dict[str, Any]:
        """Synchronous wrapper for option data fetching"""
        # This is a simplified version - in production, handle async properly
        try:
            loop = asyncio.new_event_loop()
            return loop.run_until_complete(
                self.breeze_service.get_historical_data(
                    interval="5minute",
                    from_date=from_date,
                    to_date=to_date,
                    stock_code=f"{symbol}{expiry.strftime('%y%b').upper()}{strike}{option_type}",
                    exchange_code="NFO",
                    product_type="options",
                    expiry_date=expiry.strftime("%Y-%m-%dT07:00:00.000Z"),
                    right=option_type,
                    strike_price=str(strike)
                )
            )
        except Exception as e:
            logger.error(f"Error in sync fetch: {e}")
            return {}
    
    async def _create_hourly_aggregations(
        self, 
        from_date: datetime,
        to_date: datetime,
        symbol: str
    ) -> int:
        """Create hourly candles from 5-minute data using END TIME convention"""
        hourly_count = 0
        
        try:
            # Get 5-minute data
            with self.db_manager.get_session() as session:
                five_min_data = session.query(NiftyIndexData).filter(
                    NiftyIndexData.symbol == symbol,
                    NiftyIndexData.interval == "5minute",
                    NiftyIndexData.timestamp >= from_date,
                    NiftyIndexData.timestamp <= to_date
                ).order_by(NiftyIndexData.timestamp).all()
                
                if not five_min_data:
                    return 0
                
                # Group by date
                current_date = from_date.date()
                while current_date <= to_date.date():
                    # Get data for this day
                    day_data = [d for d in five_min_data if d.timestamp.date() == current_date]
                    
                    if day_data:
                        # Create hourly candles using our service
                        hourly_candles = self.hourly_aggregation_service.create_hourly_bars_from_5min(day_data)
                        
                        # Store each hourly candle
                        for candle in hourly_candles:
                            if self.hourly_aggregation_service.store_hourly_candle(candle):
                                hourly_count += 1
                    
                    current_date += timedelta(days=1)
                    
        except Exception as e:
            logger.error(f"Error creating hourly aggregations: {e}")
        
        return hourly_count
    
    async def get_data_availability(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        symbol: str = "NIFTY"
    ) -> Dict[str, Any]:
        """Get data availability summary"""
        with self.db_manager.get_session() as session:
            query = session.query(NiftyIndexData).filter(
                NiftyIndexData.symbol == symbol
            )
            
            if from_date:
                query = query.filter(NiftyIndexData.timestamp >= from_date)
            if to_date:
                query = query.filter(NiftyIndexData.timestamp <= to_date)
            
            # Get counts by interval
            five_min_count = query.filter(NiftyIndexData.interval == "5minute").count()
            hourly_count = query.filter(NiftyIndexData.interval == "hourly").count()
            
            # Get date range
            data_range = session.query(
                func.min(NiftyIndexData.timestamp),
                func.max(NiftyIndexData.timestamp)
            ).filter(NiftyIndexData.symbol == symbol).first()
            
            return {
                "symbol": symbol,
                "data_range": {
                    "earliest": data_range[0].isoformat() if data_range[0] else None,
                    "latest": data_range[1].isoformat() if data_range[1] else None
                },
                "record_counts": {
                    "five_minute": five_min_count,
                    "hourly": hourly_count,
                    "total": five_min_count + hourly_count
                },
                "date_range_requested": {
                    "from": from_date.isoformat() if from_date else None,
                    "to": to_date.isoformat() if to_date else None
                }
            }