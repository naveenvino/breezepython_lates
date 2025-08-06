"""
Collect Weekly Data Use Case
Application use case for collecting weekly options data
"""
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from decimal import Decimal

from ..dto.requests import CollectWeeklyDataRequest
from ..dto.responses import CollectWeeklyDataResponse, DataCollectionStats, BaseResponse, ResponseStatus
from ..interfaces.idata_collector import IDataCollector
from ...domain.repositories.imarket_data_repository import IMarketDataRepository
from ...domain.repositories.ioptions_repository import IOptionsHistoricalDataRepository
from ...domain.entities.market_data import MarketData, TimeInterval
from ...domain.value_objects.strike_price import StrikePrice

logger = logging.getLogger(__name__)


class CollectWeeklyDataUseCase:
    """Use case for collecting weekly options data"""
    
    def __init__(
        self,
        data_collector: IDataCollector,
        market_data_repo: IMarketDataRepository,
        options_data_repo: IOptionsHistoricalDataRepository
    ):
        self.data_collector = data_collector
        self.market_data_repo = market_data_repo
        self.options_data_repo = options_data_repo
    
    async def execute(self, request: CollectWeeklyDataRequest) -> BaseResponse[CollectWeeklyDataResponse]:
        """Execute the use case"""
        try:
            start_time = datetime.now()
            
            # Extend from_date to previous Monday for zone calculations
            extended_from_date = self._extend_to_previous_monday(request.from_date)
            
            logger.info(
                f"Starting weekly data collection from {extended_from_date} to {request.to_date} "
                f"for {request.symbol}"
            )
            
            # Collect NIFTY/index data
            nifty_stats = await self._collect_index_data(
                request.symbol,
                extended_from_date,
                request.to_date,
                request.index_interval,
                request.force_refresh
            )
            
            # Get Mondays in the date range
            mondays = self._get_mondays_in_range(request.from_date, request.to_date)
            mondays_processed = []
            
            # Collect options data for each Monday
            total_options_stats = DataCollectionStats()
            
            for monday in mondays:
                monday_result = await self._process_monday_options(
                    monday,
                    request.symbol,
                    request.strike_range,
                    request.option_interval,
                    request.use_parallel,
                    request.max_workers,
                    request.force_refresh
                )
                
                if monday_result:
                    mondays_processed.append(monday_result)
                    # Aggregate stats
                    total_options_stats.records_collected += monday_result['stats'].records_collected
                    total_options_stats.records_skipped += monday_result['stats'].records_skipped
                    total_options_stats.records_failed += monday_result['stats'].records_failed
                    total_options_stats.errors.extend(monday_result['stats'].errors)
            
            total_time = (datetime.now() - start_time).total_seconds()
            
            response_data = CollectWeeklyDataResponse(
                from_date=request.from_date,
                to_date=request.to_date,
                symbol=request.symbol,
                mondays_processed=mondays_processed,
                nifty_stats=nifty_stats,
                options_stats=total_options_stats,
                total_time_seconds=total_time
            )
            
            return BaseResponse(
                status=ResponseStatus.SUCCESS,
                message=f"Successfully collected data for {len(mondays_processed)} weeks",
                data=response_data
            )
            
        except Exception as e:
            logger.error(f"Error in CollectWeeklyDataUseCase: {e}", exc_info=True)
            return BaseResponse(
                status=ResponseStatus.ERROR,
                message=f"Failed to collect weekly data: {str(e)}",
                errors=[str(e)]
            )
    
    async def _collect_index_data(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
        interval: str,
        force_refresh: bool
    ) -> DataCollectionStats:
        """Collect index/NIFTY data"""
        stats = DataCollectionStats()
        start_time = datetime.now()
        
        try:
            # Convert interval string to TimeInterval enum
            interval_map = {
                "1minute": TimeInterval.ONE_MINUTE,
                "5minute": TimeInterval.FIVE_MINUTE,
                "30minute": TimeInterval.THIRTY_MINUTE,
                "1hour": TimeInterval.ONE_HOUR,
                "1day": TimeInterval.ONE_DAY
            }
            time_interval = interval_map.get(interval, TimeInterval.ONE_HOUR)
            
            # Check existing data if not forcing refresh
            if not force_refresh:
                existing_dates = await self._get_existing_dates(
                    f"{symbol} 50",  # e.g., "NIFTY 50"
                    from_date,
                    to_date,
                    time_interval
                )
                
                if len(existing_dates) > 0:
                    stats.records_skipped = len(existing_dates)
                    logger.info(f"Skipping {len(existing_dates)} existing records for {symbol}")
            
            # Collect new data
            result = await self.data_collector.collect_index_data(
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                interval=interval,
                force_refresh=force_refresh
            )
            
            stats.records_collected = result.get('records_collected', 0)
            stats.records_failed = result.get('records_failed', 0)
            stats.time_taken_seconds = (datetime.now() - start_time).total_seconds()
            
            if result.get('errors'):
                stats.errors = [{'type': 'index_data', 'error': err} for err in result['errors']]
            
        except Exception as e:
            logger.error(f"Error collecting index data: {e}")
            stats.records_failed += 1
            stats.errors.append({'type': 'index_data', 'error': str(e)})
        
        return stats
    
    async def _process_monday_options(
        self,
        monday: date,
        symbol: str,
        strike_range: int,
        interval: str,
        use_parallel: bool,
        max_workers: int,
        force_refresh: bool
    ) -> Optional[Dict[str, Any]]:
        """Process options data for a specific Monday"""
        try:
            # Get spot price for Monday
            spot_price = await self._get_spot_price_for_date(symbol, monday)
            if not spot_price:
                logger.warning(f"No spot price found for {monday}, skipping")
                return None
            
            # Calculate strikes
            strikes = self._calculate_strikes_in_range(spot_price, symbol, strike_range)
            
            # Get weekly expiry
            expiry = self._get_weekly_expiry_for_date(monday, symbol)
            
            # Date range: Monday to Friday
            from_date = monday
            to_date = monday + timedelta(days=4)  # Friday
            
            logger.info(
                f"Processing {monday}: Spot={spot_price}, Strikes={len(strikes)}, "
                f"Expiry={expiry}"
            )
            
            # Collect options data
            stats = DataCollectionStats()
            start_time = datetime.now()
            
            if use_parallel:
                result = await self.data_collector.collect_options_data_parallel(
                    underlying=symbol,
                    expiry_date=expiry,
                    strikes=strikes,
                    from_date=from_date,
                    to_date=to_date,
                    interval=interval,
                    max_workers=max_workers,
                    force_refresh=force_refresh
                )
            else:
                result = await self.data_collector.collect_options_data(
                    underlying=symbol,
                    expiry_date=expiry,
                    strikes=strikes,
                    from_date=from_date,
                    to_date=to_date,
                    interval=interval,
                    force_refresh=force_refresh
                )
            
            stats.records_collected = result.get('records_collected', 0)
            stats.records_skipped = result.get('records_skipped', 0)
            stats.records_failed = result.get('records_failed', 0)
            stats.time_taken_seconds = (datetime.now() - start_time).total_seconds()
            
            if result.get('errors'):
                stats.errors = [
                    {'strike': err.get('strike'), 'error': err.get('error')} 
                    for err in result['errors']
                ]
            
            return {
                'date': monday.isoformat(),
                'spot_price': float(spot_price),
                'strikes_count': len(strikes),
                'strikes_range': {
                    'min': min(strikes),
                    'max': max(strikes)
                },
                'expiry': expiry.isoformat(),
                'stats': stats
            }
            
        except Exception as e:
            logger.error(f"Error processing Monday {monday}: {e}")
            return {
                'date': monday.isoformat(),
                'error': str(e),
                'stats': DataCollectionStats(records_failed=1, errors=[{'error': str(e)}])
            }
    
    def _extend_to_previous_monday(self, from_date: date) -> date:
        """Extend date to previous week's Monday for zone calculations"""
        # Get the Monday of the week containing from_date
        days_to_monday = from_date.weekday()  # 0 = Monday
        monday_of_week = from_date - timedelta(days=days_to_monday)
        
        # Go to previous week's Monday
        previous_monday = monday_of_week - timedelta(days=7)
        
        return previous_monday
    
    def _get_mondays_in_range(self, from_date: date, to_date: date) -> List[date]:
        """Get all Mondays in the date range"""
        mondays = []
        current = from_date
        
        # Find first Monday
        days_to_monday = (7 - current.weekday()) % 7  # Days until next Monday
        if days_to_monday == 0:  # Already Monday
            mondays.append(current)
            current += timedelta(days=7)
        else:
            current += timedelta(days=days_to_monday)
        
        # Collect all Mondays
        while current <= to_date:
            mondays.append(current)
            current += timedelta(days=7)
        
        return mondays
    
    async def _get_spot_price_for_date(self, symbol: str, date: date) -> Optional[Decimal]:
        """Get spot price for a specific date"""
        try:
            # Get market data for the date
            start_time = datetime.combine(date, datetime.min.time())
            end_time = start_time.replace(hour=10, minute=0)  # Look for morning price
            
            market_data = await self.market_data_repo.get_by_symbol_and_date_range(
                symbol=f"{symbol} 50",
                start_date=start_time,
                end_date=end_time,
                interval=TimeInterval.ONE_HOUR
            )
            
            if market_data:
                # Use the first available price
                return market_data[0].close
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting spot price for {date}: {e}")
            return None
    
    def _calculate_strikes_in_range(
        self,
        spot_price: Decimal,
        symbol: str,
        strike_range: int
    ) -> List[int]:
        """Calculate all strikes in the specified range"""
        strikes = StrikePrice.get_strikes_in_range(
            min_strike=float(spot_price) - strike_range,
            max_strike=float(spot_price) + strike_range,
            underlying=symbol
        )
        
        return [int(strike.price) for strike in strikes]
    
    def _get_weekly_expiry_for_date(self, date: date, symbol: str = "NIFTY") -> date:
        """Get weekly expiry (Thursday) for the given date"""
        # Calculate days until Thursday (3 = Thursday)
        days_until_thursday = (3 - date.weekday()) % 7
        
        # If it's already Thursday and past market close, go to next Thursday
        if days_until_thursday == 0:
            # For simplicity, always use the Thursday of the week
            pass
        
        expiry = date + timedelta(days=days_until_thursday)
        
        return expiry
    
    async def _get_existing_dates(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
        interval: TimeInterval
    ) -> List[date]:
        """Get dates that already have data"""
        # This is a placeholder - actual implementation would query the repository
        # to find which dates already have data
        return []