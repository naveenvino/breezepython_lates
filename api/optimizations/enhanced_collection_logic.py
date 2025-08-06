"""
Enhanced collection logic with proper validation and retry
"""
from typing import List, Dict, Set, Tuple
from datetime import date, datetime
import logging

logger = logging.getLogger(__name__)

def get_expected_strikes(min_strike: int, max_strike: int) -> List[int]:
    """Get list of expected strikes in the range"""
    return list(range(min_strike, max_strike + 50, 50))

def check_missing_strikes(db_manager, date: date, symbol: str, 
                         min_strike: int, max_strike: int) -> Tuple[Set[Tuple[int, str]], int]:
    """
    Check which strikes are missing for a given date
    Returns: (set of missing (strike, type) tuples, existing record count)
    """
    from_datetime = datetime.combine(date, datetime.min.time())
    to_datetime = datetime.combine(date, datetime.max.time())
    
    expected_strikes = get_expected_strikes(min_strike, max_strike)
    expected_combinations = set()
    
    # Generate all expected strike/type combinations
    for strike in expected_strikes:
        for option_type in ['CE', 'PE']:
            expected_combinations.add((strike, option_type))
    
    # Query existing strikes
    with db_manager.get_session() as session:
        from src.infrastructure.database.models import OptionsHistoricalData
        
        # Get existing strike/type combinations
        existing = session.query(
            OptionsHistoricalData.strike,
            OptionsHistoricalData.option_type
        ).filter(
            OptionsHistoricalData.underlying == symbol,
            OptionsHistoricalData.timestamp >= from_datetime,
            OptionsHistoricalData.timestamp <= to_datetime,
            OptionsHistoricalData.strike >= min_strike,
            OptionsHistoricalData.strike <= max_strike
        ).distinct().all()
        
        existing_combinations = {(strike, opt_type) for strike, opt_type in existing}
        
        # Also get total record count
        total_records = session.query(OptionsHistoricalData).filter(
            OptionsHistoricalData.underlying == symbol,
            OptionsHistoricalData.timestamp >= from_datetime,
            OptionsHistoricalData.timestamp <= to_datetime,
            OptionsHistoricalData.strike >= min_strike,
            OptionsHistoricalData.strike <= max_strike
        ).count()
    
    # Find missing combinations
    missing_combinations = expected_combinations - existing_combinations
    
    return missing_combinations, total_records

def collect_missing_strikes_only(breeze, db_manager, request_date: date, symbol: str,
                                missing_strikes: Set[Tuple[int, str]], expiry_date: date) -> Dict:
    """Collect only the missing strikes"""
    from_datetime = datetime.combine(request_date, datetime.min.time())
    to_datetime = datetime.combine(request_date, datetime.max.time())
    
    results = {
        "records_added": 0,
        "strikes_processed": 0,
        "errors": []
    }
    
    logger.info(f"Collecting {len(missing_strikes)} missing strike/type combinations")
    
    # Group by strike for efficient processing
    strikes_to_collect = {}
    for strike, option_type in missing_strikes:
        if strike not in strikes_to_collect:
            strikes_to_collect[strike] = []
        strikes_to_collect[strike].append(option_type)
    
    # Use parallel processing for missing strikes only
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        
        for strike, option_types in strikes_to_collect.items():
            for option_type in option_types:
                future = executor.submit(
                    fetch_and_store_single_option_safe,
                    breeze, db_manager, from_datetime, to_datetime,
                    symbol, strike, option_type, expiry_date
                )
                futures.append((future, strike, option_type))
        
        # Process results
        for future, strike, option_type in futures:
            try:
                records_added = future.result()
                if records_added > 0:
                    results["records_added"] += records_added
                    results["strikes_processed"] += 1
                    logger.info(f"Successfully collected {strike}{option_type}: {records_added} records")
                else:
                    logger.warning(f"No records returned for {strike}{option_type}")
            except Exception as e:
                error_msg = f"{strike}{option_type}: {str(e)}"
                results["errors"].append(error_msg)
                logger.error(f"Failed to collect {strike}{option_type}: {e}")
    
    return results

def fetch_and_store_single_option_safe(breeze, db_manager, from_datetime, to_datetime,
                                      symbol, strike, option_type, expiry_date):
    """Fetch single option with error handling and retry"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Import the function from main module
            from test_direct_endpoint_simple import fetch_and_store_single_option
            return fetch_and_store_single_option(
                breeze, db_manager, from_datetime, to_datetime,
                symbol, strike, option_type, expiry_date
            )
        except Exception as e:
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"Retry {retry_count} for {strike}{option_type}: {e}")
                import time
                time.sleep(2)  # Wait before retry
            else:
                raise

def verify_collection_completeness(db_manager, date: date, symbol: str,
                                  min_strike: int, max_strike: int) -> Dict:
    """Verify if collection is complete for a date"""
    expected_strikes = get_expected_strikes(min_strike, max_strike)
    expected_count = len(expected_strikes) * 2  # CE and PE
    
    missing_combinations, total_records = check_missing_strikes(
        db_manager, date, symbol, min_strike, max_strike
    )
    
    actual_count = expected_count - len(missing_combinations)
    completeness_percent = (actual_count / expected_count) * 100 if expected_count > 0 else 0
    
    return {
        "date": date.isoformat(),
        "expected_strikes": expected_count,
        "actual_strikes": actual_count,
        "missing_strikes": len(missing_combinations),
        "completeness_percent": round(completeness_percent, 1),
        "total_records": total_records,
        "is_complete": len(missing_combinations) == 0,
        "missing_details": [f"{s}{t}" for s, t in sorted(missing_combinations)][:10]  # First 10
    }

def collect_options_with_validation(request, job_id: str = None):
    """Enhanced collection with validation and retry for missing strikes"""
    from src.infrastructure.database.database_manager import get_db_manager
    from breeze_connect import BreezeConnect
    from test_direct_endpoint_simple import get_first_trading_day_open_price, get_weekly_expiry
    import os
    from datetime import timedelta
    
    # Initialize
    db_manager = get_db_manager()
    breeze = BreezeConnect(api_key=os.getenv('BREEZE_API_KEY'))
    try:
        breeze.generate_session(
            api_secret=os.getenv('BREEZE_API_SECRET'),
            session_token=os.getenv('BREEZE_API_SESSION')
        )
    except Exception as e:
        logger.info(f"Session notice: {e}")
    
    current_date = request.from_date
    total_added = 0
    daily_results = []
    
    while current_date <= request.to_date:
        # Skip weekends
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue
        
        # Get strike range
        first_day_open = get_first_trading_day_open_price(current_date, request.symbol, db_manager)
        if not first_day_open:
            current_date += timedelta(days=1)
            continue
        
        base_strike = int(round(first_day_open / 50) * 50)
        min_strike = base_strike - 500
        max_strike = base_strike + 500
        expiry_date = get_weekly_expiry(current_date)
        
        logger.info(f"Processing {current_date}: Strikes {min_strike}-{max_strike}")
        
        # Check what's missing
        missing_combinations, existing_records = check_missing_strikes(
            db_manager, current_date, request.symbol, min_strike, max_strike
        )
        
        if not missing_combinations and not request.force_refresh:
            logger.info(f"{current_date}: All strikes present ({existing_records} records)")
            daily_results.append({
                "date": current_date.isoformat(),
                "status": "skipped",
                "reason": "complete",
                "existing_records": existing_records
            })
        else:
            # Collect missing strikes
            if missing_combinations:
                logger.info(f"{current_date}: Missing {len(missing_combinations)} strike/type combinations")
                result = collect_missing_strikes_only(
                    breeze, db_manager, current_date, request.symbol,
                    missing_combinations, expiry_date
                )
            else:
                # Force refresh - collect all
                logger.info(f"{current_date}: Force refresh requested")
                from enhanced_optimizations import collect_options_for_day_ultra_fast
                result = collect_options_for_day_ultra_fast(
                    db_manager, current_date, request.symbol,
                    min_strike, max_strike, expiry_date, job_id
                )
            
            total_added += result["records_added"]
            
            # Verify completeness after collection
            verification = verify_collection_completeness(
                db_manager, current_date, request.symbol, min_strike, max_strike
            )
            
            daily_results.append({
                "date": current_date.isoformat(),
                "status": "processed",
                "records_added": result["records_added"],
                "strikes_processed": result["strikes_processed"],
                "completeness": verification["completeness_percent"],
                "is_complete": verification["is_complete"],
                "errors": result.get("errors", [])
            })
            
            if not verification["is_complete"]:
                logger.warning(f"{current_date}: Collection incomplete! Missing: {verification['missing_details']}")
        
        current_date += timedelta(days=1)
    
    return {
        "status": "success",
        "total_records_added": total_added,
        "daily_results": daily_results
    }