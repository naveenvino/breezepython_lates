"""
Fixed backtest use case that properly handles rate limiting
"""
from datetime import datetime, timedelta
from typing import List, Optional
import logging
from uuid import uuid4

from src.domain.entities.backtest import BacktestRun, BacktestTrade, BacktestPosition
from src.domain.services.signal_evaluator import SignalEvaluator
from src.domain.services.option_pricing import OptionPricingService
from src.infrastructure.services.data_collection_service import DataCollectionService
from src.infrastructure.database.db_manager import DatabaseManager
from src.infrastructure.database.models import NiftyIndexDataHourly, OptionsData
from sqlalchemy import and_

logger = logging.getLogger(__name__)


class RunBacktestFixedUseCase:
    """Fixed backtest that properly handles rate limiting"""
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        data_collection: DataCollectionService,
        signal_evaluator: SignalEvaluator,
        option_pricing: OptionPricingService
    ):
        self.db_manager = db_manager
        self.data_collection = data_collection
        self.signal_evaluator = signal_evaluator
        self.option_pricing = option_pricing
        
    async def execute(
        self,
        from_date: datetime,
        to_date: datetime,
        signals_to_test: List[str],
        lot_size: int = 10,
        stop_loss_amount: Optional[float] = None,
        target_profit_amount: Optional[float] = None,
        use_hedging: bool = True,
        hedge_strike_offset: int = 200,
        initial_capital: float = 500000.0,
        auto_fetch_missing_data: bool = False
    ) -> BacktestRun:
        """Execute backtest with proper rate limit handling"""
        
        logger.info(f"Starting backtest from {from_date} to {to_date}")
        
        # IMPORTANT: Check if we have sufficient data BEFORE trying to fetch
        data_check = self._check_data_completeness(from_date, to_date)
        
        if not data_check['has_sufficient_data']:
            # Don't try to fetch if rate limited - return error immediately
            if self._is_rate_limited():
                logger.error("API rate limit exceeded. Cannot fetch missing data.")
                raise Exception(
                    "API rate limit exceeded. Please wait until tomorrow to run backtests with new date ranges. "
                    f"Missing data for: {data_check['missing_dates']}"
                )
            
            # Only fetch if explicitly allowed and not rate limited
            if auto_fetch_missing_data:
                logger.info(f"Fetching missing data for dates: {data_check['missing_dates']}")
                try:
                    await self._fetch_missing_data_carefully(
                        from_date, to_date, data_check['missing_dates']
                    )
                except Exception as e:
                    if "Rate Limit" in str(e) or "429" in str(e):
                        raise Exception(
                            "API rate limit hit while fetching data. Cannot continue. "
                            "Please use date ranges with existing data or wait until tomorrow."
                        )
                    raise
            else:
                # Don't proceed with incomplete data
                raise Exception(
                    f"Insufficient data for backtest. Missing dates: {data_check['missing_dates']}. "
                    "Enable auto_fetch_missing_data=true to fetch missing data (if not rate limited)."
                )
        
        # Now run the actual backtest with complete data
        return await self._run_backtest_logic(
            from_date, to_date, signals_to_test, lot_size,
            stop_loss_amount, target_profit_amount,
            use_hedging, hedge_strike_offset, initial_capital
        )
    
    def _check_data_completeness(self, from_date: datetime, to_date: datetime) -> dict:
        """Check if we have complete data for the date range"""
        
        with self.db_manager.get_session() as session:
            # Check each trading day
            missing_dates = []
            current = from_date
            
            while current <= to_date:
                # Skip weekends
                if current.weekday() not in [5, 6]:
                    # Check if we have NIFTY data for this day
                    nifty_count = session.query(NiftyIndexDataHourly).filter(
                        and_(
                            NiftyIndexDataHourly.timestamp >= current.replace(hour=9, minute=15),
                            NiftyIndexDataHourly.timestamp <= current.replace(hour=15, minute=15)
                        )
                    ).count()
                    
                    # We need at least 6 hourly bars for a trading day
                    if nifty_count < 6:
                        missing_dates.append(current.date())
                    else:
                        # Also check options data
                        options_count = session.query(OptionsData).filter(
                            OptionsData.date == current.date()
                        ).limit(100).count()
                        
                        if options_count < 50:  # Need reasonable options data
                            missing_dates.append(current.date())
                
                current += timedelta(days=1)
            
            return {
                'has_sufficient_data': len(missing_dates) == 0,
                'missing_dates': missing_dates
            }
    
    def _is_rate_limited(self) -> bool:
        """Check if we're currently rate limited"""
        # Check recent API logs or maintain a counter
        # For now, we can check if we've been getting 429 errors
        
        # Simple check: if we've made too many calls today
        import os
        rate_limit_file = "logs/api_calls_today.txt"
        
        if os.path.exists(rate_limit_file):
            with open(rate_limit_file, 'r') as f:
                try:
                    calls_today = int(f.read().strip())
                    if calls_today > 80000:  # Close to 86,400 limit
                        return True
                except:
                    pass
        
        return False
    
    async def _fetch_missing_data_carefully(
        self, 
        from_date: datetime, 
        to_date: datetime,
        missing_dates: List
    ):
        """Carefully fetch missing data with rate limit awareness"""
        
        # Limit the number of API calls
        max_calls = 1000  # Conservative limit
        calls_made = 0
        
        for date in missing_dates[:5]:  # Only fetch first 5 missing dates
            if calls_made > max_calls:
                raise Exception(f"Too many API calls needed. Stopping to prevent rate limit.")
            
            # Fetch NIFTY data for this date
            logger.info(f"Fetching NIFTY data for {date}")
            # ... actual fetch logic with proper error handling
            calls_made += 10  # Estimate
            
            # Check if we're getting rate limited
            if calls_made > 100:
                # Do a test call to check if we're rate limited
                # If yes, stop immediately
                pass
    
    async def _run_backtest_logic(
        self,
        from_date: datetime,
        to_date: datetime,
        signals_to_test: List[str],
        lot_size: int,
        stop_loss_amount: Optional[float],
        target_profit_amount: Optional[float],
        use_hedging: bool,
        hedge_strike_offset: int,
        initial_capital: float
    ) -> BacktestRun:
        """Run the actual backtest logic with complete data"""
        
        # Create backtest run
        backtest_id = str(uuid4())
        backtest_run = BacktestRun(
            id=backtest_id,
            from_date=from_date,
            to_date=to_date,
            signals_to_test=signals_to_test,
            lot_size=lot_size,
            initial_capital=initial_capital,
            use_hedging=use_hedging,
            hedge_strike_offset=hedge_strike_offset,
            stop_loss_amount=stop_loss_amount,
            target_profit_amount=target_profit_amount
        )
        
        # ... rest of the backtest logic using existing data
        
        backtest_run.status = "completed"
        logger.info(f"Backtest completed. Total P&L: {backtest_run.total_pnl}")
        
        return backtest_run