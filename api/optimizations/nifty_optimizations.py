"""
Optimized NIFTY index data collection with all performance enhancements
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, time
from typing import List, Dict, Optional, Tuple
import logging
import os

from breeze_connect import BreezeConnect
from src.infrastructure.database.models import NiftyIndexData
from src.infrastructure.services.hourly_aggregation_service import HourlyAggregationService
from src.utils.market_hours import (
    BREEZE_DATA_START_REGULAR, BREEZE_DATA_END_REGULAR,
    BREEZE_DATA_START_EXTENDED, BREEZE_DATA_END_EXTENDED
)

def is_within_regular_hours(timestamp_time):
    """Check if time is within regular trading hours"""
    return BREEZE_DATA_START_REGULAR <= timestamp_time <= BREEZE_DATA_END_REGULAR

def is_within_extended_hours(timestamp_time):
    """Check if time is within extended trading hours"""
    return BREEZE_DATA_START_EXTENDED <= timestamp_time <= BREEZE_DATA_END_EXTENDED

logger = logging.getLogger(__name__)

# Reuse connection pool from options optimization
from enhanced_optimizations import get_breeze_pool, cache

def get_expected_candles_count(extended_hours: bool = False) -> int:
    """Get expected number of 5-minute candles per day"""
    if extended_hours:
        # 9:20 to 15:35 = 375 minutes / 5 = 75 candles + 1 (for 15:35) = 76
        return 76
    else:
        # 9:15 to 15:30 = 375 minutes / 5 = 75 candles + 1 (for 15:30) = 76
        return 76

def check_nifty_data_completeness(db_manager, check_date: date, symbol: str, 
                                 extended_hours: bool = False) -> Tuple[int, bool]:
    """
    Check if NIFTY data is complete for a given date
    Returns: (existing_count, is_complete)
    """
    from_datetime = datetime.combine(check_date, datetime.min.time())
    to_datetime = datetime.combine(check_date, datetime.max.time())
    
    expected_count = get_expected_candles_count(extended_hours)
    
    with db_manager.get_session() as session:
        existing_count = session.query(NiftyIndexData).filter(
            NiftyIndexData.symbol == symbol,
            NiftyIndexData.interval == "5minute",
            NiftyIndexData.timestamp >= from_datetime,
            NiftyIndexData.timestamp <= to_datetime
        ).count()
    
    # Allow for minor variations (some days might have fewer candles)
    is_complete = existing_count >= (expected_count - 2)
    
    return existing_count, is_complete

def collect_nifty_data_ultra_optimized(request, job_id: str = None) -> dict:
    """Ultra-optimized NIFTY collection with all enhancements"""
    from src.infrastructure.database.database_manager import get_db_manager
    
    # Initialize
    db_manager = get_db_manager()
    hourly_service = HourlyAggregationService(db_manager)
    
    # Get connection pool
    pool = get_breeze_pool()
    
    # Process date range
    current_date = request.from_date
    total_added_5min = 0
    total_added_hourly = 0
    total_skipped_days = 0
    total_weekend_days = 0
    errors = []
    daily_results = []
    
    # Calculate total days for progress
    total_days = (request.to_date - request.from_date).days + 1
    processed_days = 0
    
    # Batch dates for parallel processing
    dates_to_process = []
    temp_date = current_date
    
    while temp_date <= request.to_date:
        if temp_date.weekday() < 5:  # Weekday
            dates_to_process.append(temp_date)
        else:
            total_weekend_days += 1
        temp_date += timedelta(days=1)
    
    logger.info(f"Processing {len(dates_to_process)} trading days with optimization")
    
    # Process dates in parallel batches
    batch_size = 5  # Process 5 days at a time
    
    for i in range(0, len(dates_to_process), batch_size):
        batch = dates_to_process[i:i + batch_size]
        
        # Update progress
        if job_id and 'job_status' in globals():
            try:
                from test_direct_endpoint_simple import job_status
                job_status[job_id]["progress"] = round((i / len(dates_to_process)) * 100, 1)
                job_status[job_id]["current_batch"] = f"Processing {batch[0]} to {batch[-1]}"
            except:
                pass
        
        # Process batch in parallel
        with ThreadPoolExecutor(max_workers=min(5, len(batch))) as executor:
            future_to_date = {
                executor.submit(
                    process_single_nifty_date_optimized,
                    pool, db_manager, process_date, request.symbol, 
                    request.extended_hours, request.force_refresh
                ): process_date
                for process_date in batch
            }
            
            # Collect results
            for future in as_completed(future_to_date):
                process_date = future_to_date[future]
                try:
                    result = future.result()
                    daily_results.append(result)
                    
                    if result["status"] == "processed":
                        total_added_5min += result.get("added_5min", 0)
                        if result.get("hourly_generated"):
                            total_added_hourly += len(result["hourly_generated"])
                    elif result["status"] == "skipped":
                        total_skipped_days += 1
                    
                except Exception as e:
                    error_msg = f"{process_date}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"Error processing {process_date}: {e}")
                    daily_results.append({
                        "date": process_date.isoformat(),
                        "status": "error",
                        "error": str(e)
                    })
    
    # Final aggregation if needed
    logger.info("Running final hourly aggregation check...")
    # Aggregate any missing hourly data
    final_hourly_count = 0
    current_check = request.from_date
    while current_check <= request.to_date:
        if current_check.weekday() < 5:  # Weekday
            hourly_generated = hourly_service.generate_hourly_data_for_date(
                request.symbol, current_check
            )
            final_hourly_count += len(hourly_generated)
        current_check += timedelta(days=1)
    
    return {
        "status": "success",
        "summary": {
            "total_days": total_days,
            "weekend_days": total_weekend_days,
            "trading_days": len(dates_to_process),
            "days_processed": len([d for d in daily_results if d.get("status") == "processed"]),
            "days_skipped": total_skipped_days,
            "total_5min_records_added": total_added_5min,
            "total_hourly_records_added": total_added_hourly + final_hourly_count
        },
        "daily_results": daily_results,
        "errors": errors if errors else None,
        "optimization_features": [
            "Parallel date processing (5 dates simultaneously)",
            "Connection pooling",
            "Bulk database inserts",
            "Smart completeness checking",
            "Batch processing"
        ]
    }

def process_single_nifty_date_optimized(pool, db_manager, process_date: date, 
                                       symbol: str, extended_hours: bool, 
                                       force_refresh: bool) -> dict:
    """Process a single date with optimization"""
    from_datetime = datetime.combine(process_date, datetime.min.time())
    to_datetime = datetime.combine(process_date, datetime.max.time())
    
    # Check completeness first
    existing_count, is_complete = check_nifty_data_completeness(
        db_manager, process_date, symbol, extended_hours
    )
    
    if is_complete and not force_refresh:
        logger.info(f"{process_date}: Data complete ({existing_count} records), skipping")
        return {
            "date": process_date.isoformat(),
            "status": "skipped",
            "reason": "data_complete",
            "existing_count": existing_count
        }
    
    # Get connection from pool
    breeze = pool.get_connection()
    
    try:
        # Fetch data
        logger.info(f"{process_date}: Fetching NIFTY data...")
        result = breeze.get_historical_data_v2(
            interval="5minute",
            from_date=from_datetime.strftime("%Y-%m-%dT00:00:00.000Z"),
            to_date=to_datetime.strftime("%Y-%m-%dT23:59:59.000Z"),
            stock_code=symbol,
            exchange_code="NSE",
            product_type="cash"
        )
        
        if result and 'Success' in result:
            records = result['Success']
            
            # Bulk insert with filtering
            added_count = bulk_insert_nifty_data(
                db_manager, records, symbol, extended_hours
            )
            
            # Generate hourly data
            hourly_service = HourlyAggregationService(db_manager)
            hourly_generated = hourly_service.generate_hourly_data_for_date(
                symbol, process_date
            )
            
            logger.info(f"{process_date}: Added {added_count} 5-min records, {len(hourly_generated)} hourly")
            
            return {
                "date": process_date.isoformat(),
                "status": "processed",
                "added_5min": added_count,
                "hourly_generated": hourly_generated,
                "total_records": len(records)
            }
        else:
            return {
                "date": process_date.isoformat(),
                "status": "no_data",
                "reason": "No data from Breeze"
            }
            
    finally:
        # Return connection to pool
        pool.return_connection(breeze)

def bulk_insert_nifty_data(db_manager, records: List[dict], symbol: str, 
                           extended_hours: bool) -> int:
    """Bulk insert NIFTY data with duplicate checking"""
    if not records:
        return 0
    
    # Prepare all records first
    prepared_records = []
    
    for record in records:
        # Add symbol if not present
        record['symbol'] = symbol
        
        # Create NiftyIndexData object
        nifty_data = NiftyIndexData.from_breeze_data(record)
        
        if nifty_data is None:
            continue
            
        # Apply time filtering based on extended_hours
        if extended_hours:
            if not is_within_extended_hours(nifty_data.timestamp.time()):
                continue
        else:
            if not is_within_regular_hours(nifty_data.timestamp.time()):
                continue
        
        prepared_records.append(nifty_data)
    
    if not prepared_records:
        return 0
    
    # Bulk check for existing records
    added_count = 0
    
    with db_manager.get_session() as session:
        # Get all timestamps for efficient duplicate checking
        timestamps = [r.timestamp for r in prepared_records]
        
        # Query existing timestamps in bulk
        existing = session.query(NiftyIndexData.timestamp).filter(
            NiftyIndexData.symbol == symbol,
            NiftyIndexData.interval == "5minute",
            NiftyIndexData.timestamp.in_(timestamps)
        ).all()
        
        existing_timestamps = {e[0] for e in existing}
        
        # Filter new records
        new_records = [
            record for record in prepared_records 
            if record.timestamp not in existing_timestamps
        ]
        
        # Bulk insert
        if new_records:
            session.bulk_save_objects(new_records)
            session.commit()
            added_count = len(new_records)
    
    return added_count

# Function to integrate with main API
def collect_nifty_data_with_optimization_level(request, optimization_level: int) -> dict:
    """Choose NIFTY collection method based on optimization level"""
    if optimization_level >= 2:
        logger.info("Using ULTRA optimized NIFTY collection")
        return collect_nifty_data_ultra_optimized(request)
    else:
        # Fall back to original
        logger.info("Using original NIFTY collection")
        from test_direct_endpoint_simple import collect_nifty_data_sync
        return collect_nifty_data_sync(request)