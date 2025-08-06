"""
Optimized signal-based collection service
Uses a materialized view or pre-calculated table for missing strikes
"""
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Tuple, Optional
from sqlalchemy import text
import re

from ..database.database_manager import DatabaseManager
from .data_collection_service import DataCollectionService

logger = logging.getLogger(__name__)


class OptimizedSignalCollectionService:
    """Optimized version that reads pre-calculated missing strikes"""
    
    def __init__(self, data_collection_service: DataCollectionService, db_manager: DatabaseManager):
        self.data_collection = data_collection_service
        self.db_manager = db_manager
    
    async def collect_options_for_signals_optimized(
        self,
        from_date: date,
        to_date: date,
        interval: str = "5minute",
        download_full_week: bool = True
    ) -> Dict:
        """
        Collect options based on pre-calculated missing strikes
        
        This uses a view or table that has the missing strikes pre-calculated
        to avoid running the slow SP every time
        """
        logger.info(f"Optimized signal-based collection from {from_date} to {to_date}")
        
        # Get signals with missing strikes
        signals_data = await self._get_signals_with_missing_strikes(from_date, to_date)
        
        if not signals_data:
            logger.warning("No signals found for the date range")
            return {
                "success": True,
                "weeks_processed": 0,
                "signals_found": 0,
                "missing_strikes_identified": 0,
                "options_downloaded": {"total": 0, "successful": 0, "skipped": 0, "failed": 0},
                "data_points_added": 0,
                "details": []
            }
        
        # Process results
        results = {
            "success": True,
            "weeks_processed": len(signals_data),
            "signals_found": len(signals_data),
            "missing_strikes_identified": 0,
            "options_downloaded": {"total": 0, "successful": 0, "skipped": 0, "failed": 0},
            "data_points_added": 0,
            "details": []
        }
        
        # Process each signal
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
            results["options_downloaded"]["skipped"] += week_result.get("skipped", 0)
            results["options_downloaded"]["failed"] += week_result["failed"]
            results["data_points_added"] += week_result["data_points"]
        
        logger.info(f"Optimized collection completed: {results['options_downloaded']['successful']} options downloaded")
        return results
    
    async def _get_signals_with_missing_strikes(self, from_date: date, to_date: date) -> List[Dict]:
        """Get signals with pre-calculated missing strikes"""
        with self.db_manager.get_session() as session:
            try:
                # First, try to use a materialized view if it exists
                query = text("""
                    SELECT 
                        WeekStartDate,
                        SignalType,
                        WeeklyBias,
                        MainStrikePrice,
                        OptionType as MainOptionType,
                        MissingOptionStrikes,
                        WeeklyExpiryDate
                    FROM vw_SignalInsightsWithMissingStrikes
                    WHERE WeekStartDate >= :start_date
                      AND WeekStartDate <= :end_date
                      AND SignalType IS NOT NULL
                      AND MissingOptionStrikes IS NOT NULL
                    ORDER BY WeekStartDate
                """)
                
                result = session.execute(query, {"start_date": from_date, "end_date": to_date})
                rows = result.fetchall()
                
                if not rows:
                    # Fallback to manual parsing from your provided data
                    logger.info("Using hardcoded missing strikes data")
                    return self._get_hardcoded_missing_strikes(from_date, to_date)
                
                # Convert to list of dicts
                columns = result.keys()
                signals = []
                
                for row in rows:
                    signal_dict = dict(zip(columns, row))
                    signals.append(signal_dict)
                
                return signals
                
            except Exception as e:
                logger.warning(f"View not found, using hardcoded data: {e}")
                return self._get_hardcoded_missing_strikes(from_date, to_date)
    
    def _get_hardcoded_missing_strikes(self, from_date: date, to_date: date) -> List[Dict]:
        """Hardcoded missing strikes from your SP output"""
        all_signals = [
            {
                "WeekStartDate": date(2025, 1, 13),
                "SignalType": "S5",
                "MainStrikePrice": 23300,
                "MainOptionType": "CE",
                "MissingOptionStrikes": "23300CE, 23400CE, 23450CE, 23500CE, 23600CE",
                "WeeklyExpiryDate": date(2025, 1, 16)
            },
            {
                "WeekStartDate": date(2025, 1, 27),
                "SignalType": "S5",
                "MainStrikePrice": 23100,
                "MainOptionType": "CE",
                "MissingOptionStrikes": "23100CE, 23200CE, 23250CE, 23400CE",
                "WeeklyExpiryDate": date(2025, 1, 30)
            },
            {
                "WeekStartDate": date(2025, 2, 3),
                "SignalType": "S7",
                "MainStrikePrice": 23200,
                "MainOptionType": "PE",
                "MissingOptionStrikes": "23200PE, 23100PE, 23050PE, 23000PE, 22900PE",
                "WeeklyExpiryDate": date(2025, 2, 6)
            },
            {
                "WeekStartDate": date(2025, 2, 17),
                "SignalType": "S1",
                "MainStrikePrice": 22600,
                "MainOptionType": "PE",
                "MissingOptionStrikes": "22600PE, 22500PE, 22450PE, 22400PE, 22300PE",
                "WeeklyExpiryDate": date(2025, 2, 20)
            },
            {
                "WeekStartDate": date(2025, 2, 24),
                "SignalType": "S5",
                "MainStrikePrice": 22700,
                "MainOptionType": "CE",
                "MissingOptionStrikes": "22700CE, 22800CE, 22850CE, 22900CE, 23000CE",
                "WeeklyExpiryDate": date(2025, 2, 27)
            },
            {
                "WeekStartDate": date(2025, 3, 3),
                "SignalType": "S1",
                "MainStrikePrice": 21800,
                "MainOptionType": "PE",
                "MissingOptionStrikes": "21800PE, 21700PE, 21650PE, 21600PE, 21500PE",
                "WeeklyExpiryDate": date(2025, 3, 6)
            },
            {
                "WeekStartDate": date(2025, 3, 10),
                "SignalType": "S3",
                "MainStrikePrice": 22700,
                "MainOptionType": "CE",
                "MissingOptionStrikes": "22700CE, 22800CE, 22850CE, 22900CE, 23000CE",
                "WeeklyExpiryDate": date(2025, 3, 13)
            },
            {
                "WeekStartDate": date(2025, 3, 17),
                "SignalType": "S2",
                "MainStrikePrice": 22300,
                "MainOptionType": "PE",
                "MissingOptionStrikes": "22300PE, 22200PE, 22150PE, 22100PE, 22000PE",
                "WeeklyExpiryDate": date(2025, 3, 20)
            },
            {
                "WeekStartDate": date(2025, 3, 24),
                "SignalType": "S4",
                "MainStrikePrice": 23400,
                "MainOptionType": "PE",
                "MissingOptionStrikes": "23400PE, 23300PE, 23250PE, 23200PE, 23100PE",
                "WeeklyExpiryDate": date(2025, 3, 27)
            },
            {
                "WeekStartDate": date(2025, 4, 7),
                "SignalType": "S7",
                "MainStrikePrice": 21700,
                "MainOptionType": "PE",
                "MissingOptionStrikes": "21700PE, 21600PE, 21550PE, 21500PE, 21400PE",
                "WeeklyExpiryDate": date(2025, 4, 10)
            },
            {
                "WeekStartDate": date(2025, 4, 14),
                "SignalType": "S4",
                "MainStrikePrice": 23200,
                "MainOptionType": "PE",
                "MissingOptionStrikes": "23200PE, 23100PE, 23050PE, 23000PE, 22900PE",
                "WeeklyExpiryDate": date(2025, 4, 17)
            },
            {
                "WeekStartDate": date(2025, 4, 21),
                "SignalType": "S4",
                "MainStrikePrice": 23900,
                "MainOptionType": "PE",
                "MissingOptionStrikes": "23900PE, 23800PE, 23750PE, 23700PE, 23600PE",
                "WeeklyExpiryDate": date(2025, 4, 24)
            }
        ]
        
        # Filter by date range
        return [s for s in all_signals if from_date <= s["WeekStartDate"] <= to_date]
    
    async def _process_signal_week(
        self, 
        signal_row: Dict, 
        interval: str,
        download_full_week: bool
    ) -> Dict:
        """Process a single signal week"""
        week_start = signal_row['WeekStartDate']
        signal_type = signal_row['SignalType']
        missing_strikes_str = signal_row.get('MissingOptionStrikes', '')
        expiry_date = signal_row['WeeklyExpiryDate']
        
        logger.info(f"Processing week {week_start}: Signal {signal_type}")
        
        # Parse missing strikes
        missing_strikes = self._parse_missing_strikes(missing_strikes_str, expiry_date)
        
        week_result = {
            "week": week_start.strftime("%Y-%m-%d"),
            "signal": signal_type,
            "missing_strikes": [f"{strike}{opt_type}" for strike, opt_type, _ in missing_strikes],
            "attempted": len(missing_strikes),
            "downloaded": 0,
            "skipped": 0,
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
                    week_result["skipped"] += 1
                    
            except Exception as e:
                logger.error(f"Error downloading {strike}{option_type}: {e}")
                week_result["failed"] += 1
        
        return week_result
    
    def _parse_missing_strikes(self, missing_strikes_str: str, expiry_date: date) -> List[Tuple[int, str, datetime]]:
        """Parse missing strikes string"""
        if not missing_strikes_str or missing_strikes_str.strip() == '':
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