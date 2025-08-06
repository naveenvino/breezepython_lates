"""
Signal-Based Option Collection Service
Intelligently collects option data based on signal detection results
"""
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple, Optional
from sqlalchemy import text
import re

from ..database.database_manager import DatabaseManager
from .data_collection_service import DataCollectionService

logger = logging.getLogger(__name__)


class SignalBasedCollectionService:
    """Service for collecting option data based on detected signals"""
    
    def __init__(self, data_collection_service: DataCollectionService, db_manager: DatabaseManager):
        self.data_collection = data_collection_service
        self.db_manager = db_manager
    
    async def collect_options_for_signals(
        self,
        from_date: date,
        to_date: date,
        interval: str = "5minute",
        download_full_week: bool = True
    ) -> Dict:
        """
        Collect option data based on signals detected by sp_GetWeeklySignalInsights
        
        Args:
            from_date: Start date for signal detection
            to_date: End date for signal detection
            interval: Data interval (5minute or 1hour)
            download_full_week: If True, downloads Monday to expiry for each week
            
        Returns:
            Dictionary with collection results
        """
        logger.info(f"Starting signal-based option collection from {from_date} to {to_date}")
        
        # Execute stored procedure to get signals and missing strikes
        signals_data = await self._execute_signal_detection_sp(from_date, to_date)
        
        if not signals_data:
            logger.warning("No signals found in the specified date range")
            return {
                "success": True,
                "weeks_processed": 0,
                "signals_found": 0,
                "missing_strikes_identified": 0,
                "options_downloaded": {"total": 0, "successful": 0, "failed": 0},
                "data_points_added": 0,
                "details": []
            }
        
        # Process results
        results = {
            "success": True,
            "weeks_processed": len(signals_data),
            "signals_found": len(signals_data),
            "missing_strikes_identified": 0,
            "options_downloaded": {"total": 0, "successful": 0, "failed": 0},
            "data_points_added": 0,
            "details": []
        }
        
        # Group by week and process
        for signal_row in signals_data:
            week_result = await self._process_signal_week(
                signal_row, 
                interval, 
                download_full_week
            )
            results["details"].append(week_result)
            
            # Update totals
            results["missing_strikes_identified"] += len(week_result["missing_strikes"])
            results["options_downloaded"]["total"] += week_result["attempted"]
            results["options_downloaded"]["successful"] += week_result["downloaded"]
            results["options_downloaded"]["failed"] += week_result["failed"]
            results["data_points_added"] += week_result["data_points"]
        
        logger.info(f"Signal-based collection completed: {results['options_downloaded']['successful']} options downloaded")
        return results
    
    async def _execute_signal_detection_sp(self, from_date: date, to_date: date) -> List[Dict]:
        """Execute sp_GetWeeklySignalInsights and return results"""
        with self.db_manager.get_session() as session:
            try:
                # Execute stored procedure
                result = session.execute(
                    text("""
                        EXEC sp_GetWeeklySignalInsights 
                        @StartDate = :start_date,
                        @EndDate = :end_date
                    """),
                    {"start_date": from_date, "end_date": to_date}
                )
                
                # Fetch all results
                rows = result.fetchall()
                
                # Convert to list of dicts
                columns = result.keys()
                return [dict(zip(columns, row)) for row in rows]
                
            except Exception as e:
                logger.error(f"Error executing signal detection SP: {e}")
                return []
    
    async def _process_signal_week(
        self, 
        signal_row: Dict, 
        interval: str,
        download_full_week: bool
    ) -> Dict:
        """Process a single week's signal and download missing options"""
        week_start = signal_row['WeekStartDate']
        expiry_date = signal_row['WeeklyExpiryDate']
        signal_type = signal_row['SignalType']
        missing_strikes_str = signal_row.get('MissingOptionStrikes', '')
        
        logger.info(f"Processing week {week_start}: Signal {signal_type}")
        
        # Parse missing strikes
        missing_strikes = self._parse_missing_strikes(missing_strikes_str, expiry_date)
        
        week_result = {
            "week": week_start.strftime("%Y-%m-%d"),
            "signal": signal_type,
            "missing_strikes": [f"{strike}{opt_type}" for strike, opt_type, _ in missing_strikes],
            "attempted": len(missing_strikes),
            "downloaded": 0,
            "failed": 0,
            "data_points": 0
        }
        
        if not missing_strikes:
            logger.info(f"No missing strikes for week {week_start}")
            return week_result
        
        # Determine date range for download
        if download_full_week:
            # Download from Monday to expiry (Thursday)
            download_from = datetime.combine(week_start, datetime.min.time().replace(hour=9, minute=15))
            download_to = datetime.combine(expiry_date, datetime.min.time().replace(hour=15, minute=30))
        else:
            # Download only for the signal day
            download_from = datetime.combine(week_start, datetime.min.time().replace(hour=9, minute=15))
            download_to = datetime.combine(week_start, datetime.min.time().replace(hour=15, minute=30))
        
        # Download each missing option
        for strike, option_type, expiry in missing_strikes:
            try:
                logger.info(f"Downloading {strike}{option_type} from {download_from} to {download_to}")
                
                # Use existing data collection method
                added = await self.data_collection._fetch_and_store_option_data(
                    strike=strike,
                    option_type=option_type,
                    expiry=expiry,
                    from_date=download_from,
                    to_date=download_to,
                    interval=interval
                )
                
                if added > 0:
                    week_result["downloaded"] += 1
                    week_result["data_points"] += added
                else:
                    week_result["failed"] += 1
                    
            except Exception as e:
                logger.error(f"Error downloading {strike}{option_type}: {e}")
                week_result["failed"] += 1
        
        return week_result
    
    def _parse_missing_strikes(self, missing_strikes_str: str, expiry_date: date) -> List[Tuple[int, str, datetime]]:
        """
        Parse missing strikes string into structured format
        
        Args:
            missing_strikes_str: e.g., "25000PE, 25100PE, 25150CE"
            expiry_date: Expiry date for these options
            
        Returns:
            List of tuples: [(strike, option_type, expiry_datetime), ...]
        """
        # Handle None, empty string, or NULL from database
        if not missing_strikes_str or missing_strikes_str.strip() == '' or missing_strikes_str == 'None':
            return []
        
        strikes = []
        # Split by comma and process each
        for strike_str in missing_strikes_str.split(','):
            strike_str = strike_str.strip()
            
            # Use regex to extract strike and type
            match = re.match(r'(\d+)(CE|PE)', strike_str)
            if match:
                strike = int(match.group(1))
                option_type = match.group(2)
                
                # Convert date to datetime with market close time
                expiry_datetime = datetime.combine(
                    expiry_date, 
                    datetime.min.time().replace(hour=15, minute=30)
                )
                
                strikes.append((strike, option_type, expiry_datetime))
            else:
                logger.warning(f"Could not parse strike: {strike_str}")
        
        return strikes
    
    def get_week_range_for_expiry(self, expiry_date: date) -> Tuple[date, date]:
        """
        Get Monday and expiry date for a given week
        
        Args:
            expiry_date: Thursday expiry date
            
        Returns:
            Tuple of (Monday date, Thursday date)
        """
        # Go back to Monday (weekday 0)
        days_back = expiry_date.weekday() - 0  # Monday is 0
        if days_back < 0:
            days_back += 7
        
        monday = expiry_date - timedelta(days=days_back)
        
        return monday, expiry_date