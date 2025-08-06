"""
Enhanced optimizations for options collection
"""
import queue
import threading
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging
from datetime import datetime, date
import os

logger = logging.getLogger(__name__)

class BreezeConnectionPool:
    """Connection pool for Breeze API to reuse connections"""
    def __init__(self, size=10):
        self._queue = queue.Queue(maxsize=size)
        self._lock = threading.Lock()
        self._created = 0
        self._size = size
        
    def _create_connection(self):
        """Create a new Breeze connection"""
        from breeze_connect import BreezeConnect
        
        breeze = BreezeConnect(api_key=os.getenv('BREEZE_API_KEY'))
        try:
            breeze.generate_session(
                api_secret=os.getenv('BREEZE_API_SECRET'),
                session_token=os.getenv('BREEZE_API_SESSION')
            )
        except Exception as e:
            logger.info(f"Session notice: {e}")
        
        return breeze
    
    def get_connection(self):
        """Get a connection from the pool"""
        try:
            # Try to get existing connection
            conn = self._queue.get_nowait()
            return conn
        except queue.Empty:
            # Create new connection if under limit
            with self._lock:
                if self._created < self._size:
                    self._created += 1
                    return self._create_connection()
            
            # Wait for available connection
            return self._queue.get()
    
    def return_connection(self, conn):
        """Return connection to pool"""
        try:
            self._queue.put_nowait(conn)
        except queue.Full:
            # Pool is full, discard connection
            pass

# Global connection pool
breeze_pool = None

def get_breeze_pool():
    """Get or create the global connection pool"""
    global breeze_pool
    if breeze_pool is None:
        breeze_pool = BreezeConnectionPool(size=10)
    return breeze_pool

class RedisCache:
    """Simple Redis-like in-memory cache (can be replaced with actual Redis)"""
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[str]:
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if expiry is None or time.time() < expiry:
                    return value
                else:
                    del self._cache[key]
        return None
    
    def setex(self, key: str, seconds: int, value: str):
        with self._lock:
            expiry = time.time() + seconds if seconds > 0 else None
            self._cache[key] = (value, expiry)
    
    def delete(self, key: str):
        with self._lock:
            self._cache.pop(key, None)

# Global cache instance
cache = RedisCache()

def get_first_trading_day_open_cached(date: date, symbol: str, db_manager) -> Optional[float]:
    """Get first trading day open price with caching"""
    # Cache key based on week number
    week_num = date.isocalendar()[1]
    year = date.year
    key = f"first_day_open:{symbol}:{year}:{week_num}"
    
    # Check cache
    cached = cache.get(key)
    if cached:
        return float(cached)
    
    # Get from database
    from test_direct_endpoint_simple import get_first_trading_day_open_price
    value = get_first_trading_day_open_price(date, symbol, db_manager)
    
    if value:
        # Cache for 24 hours
        cache.setex(key, 86400, str(value))
    
    return value

def collect_options_for_day_ultra_fast(db_manager, request_date: date, symbol: str,
                                      min_strike: int, max_strike: int, expiry_date: date,
                                      job_id: str = None) -> dict:
    """Ultra-fast options collection with all optimizations"""
    from_datetime = datetime.combine(request_date, datetime.min.time())
    to_datetime = datetime.combine(request_date, datetime.max.time())
    
    # Prepare all tasks
    tasks = []
    for strike in range(min_strike, max_strike + 50, 50):
        for option_type in ['CE', 'PE']:
            tasks.append((strike, option_type))
    
    results = {
        "records_added": 0,
        "strikes_processed": 0,
        "errors": [],
        "performance_metrics": {
            "total_tasks": len(tasks),
            "start_time": time.time()
        }
    }
    
    # Dynamic worker calculation based on task count
    # More workers for more tasks, but cap at 15
    optimal_workers = min(15, max(5, len(tasks) // 10))
    logger.info(f"Using {optimal_workers} workers for {len(tasks)} tasks")
    
    # Prepare for bulk insert
    all_records_to_insert = []
    processed_count = 0
    
    # Get connection pool
    pool = get_breeze_pool()
    
    # Process in parallel with optimized worker count
    with ThreadPoolExecutor(max_workers=optimal_workers) as executor:
        # Submit all tasks
        future_to_strike = {
            executor.submit(
                fetch_option_data_optimized,
                pool, from_datetime, to_datetime,
                symbol, strike, option_type, expiry_date
            ): (strike, option_type)
            for strike, option_type in tasks
        }
        
        # Process completed tasks
        for future in as_completed(future_to_strike):
            strike, option_type = future_to_strike[future]
            processed_count += 1
            
            # Update progress if job_id provided
            if job_id and processed_count % 10 == 0:
                progress = round((processed_count / len(tasks)) * 100, 1)
                if hasattr(__builtins__, 'job_status') and job_id in job_status:
                    job_status[job_id]["task_progress"] = progress
            
            try:
                records = future.result()
                if records:
                    all_records_to_insert.extend(records)
                    results["strikes_processed"] += 1
            except Exception as e:
                error_msg = f"{strike}{option_type}: {str(e)}"
                results["errors"].append(error_msg)
                logger.error(f"Failed to collect {strike}{option_type}: {e}")
    
    # Bulk insert all records at once
    if all_records_to_insert:
        records_added = bulk_insert_options(db_manager, all_records_to_insert)
        results["records_added"] = records_added
    
    # Calculate performance metrics
    results["performance_metrics"]["end_time"] = time.time()
    results["performance_metrics"]["duration"] = results["performance_metrics"]["end_time"] - results["performance_metrics"]["start_time"]
    results["performance_metrics"]["workers_used"] = optimal_workers
    
    logger.info(f"Collected {results['records_added']} records in {results['performance_metrics']['duration']:.1f}s using {optimal_workers} workers")
    
    return results

def fetch_option_data_optimized(pool: BreezeConnectionPool, from_datetime: datetime, to_datetime: datetime,
                               symbol: str, strike: int, option_type: str, expiry_date: date) -> List[dict]:
    """Fetch option data using connection pool"""
    # Get connection from pool
    breeze = pool.get_connection()
    
    try:
        # Construct option symbol
        expiry_str = expiry_date.strftime("%y%b%d").upper()
        option_symbol = f"{symbol}{expiry_str}{strike}{option_type}"
        
        # Convert CE/PE to call/put for Breeze API
        right_type = "call" if option_type == "CE" else "put"
        
        # Fetch data
        result = breeze.get_historical_data_v2(
            interval="5minute",
            from_date=from_datetime.strftime("%Y-%m-%dT00:00:00.000Z"),
            to_date=to_datetime.strftime("%Y-%m-%dT23:59:59.000Z"),
            stock_code=symbol,
            exchange_code="NFO",
            product_type="options",
            expiry_date=expiry_date.strftime("%Y-%m-%dT00:00:00.000Z"),
            right=right_type,
            strike_price=str(strike)
        )
        
        if result and 'Success' in result:
            records = result['Success']
            
            # Prepare records for bulk insert
            prepared_records = []
            for record in records:
                # Add required fields
                record['underlying'] = symbol
                record['strike_price'] = strike
                record['right'] = option_type
                record['expiry_date'] = expiry_date.strftime("%Y-%m-%dT00:00:00.000Z")
                record['trading_symbol'] = option_symbol
                
                prepared_records.append(record)
            
            return prepared_records
        
        return []
        
    finally:
        # Always return connection to pool
        pool.return_connection(breeze)

def bulk_insert_options(db_manager, records: List[dict]) -> int:
    """Bulk insert options records for maximum performance"""
    from src.infrastructure.database.models import OptionsHistoricalData
    
    if not records:
        return 0
    
    # Group by trading symbol for efficient duplicate checking
    records_by_symbol = {}
    for record in records:
        symbol = record.get('trading_symbol')
        if symbol not in records_by_symbol:
            records_by_symbol[symbol] = []
        records_by_symbol[symbol].append(record)
    
    total_added = 0
    
    with db_manager.get_session() as session:
        # Process each symbol's records
        for symbol, symbol_records in records_by_symbol.items():
            # Get all timestamps for this symbol
            timestamps = [r['datetime'] for r in symbol_records]
            
            # Check existing records in bulk
            existing = session.query(OptionsHistoricalData.timestamp).filter(
                OptionsHistoricalData.trading_symbol == symbol,
                OptionsHistoricalData.timestamp.in_(timestamps)
            ).all()
            
            existing_timestamps = {e[0] for e in existing}
            
            # Filter new records
            new_records = []
            for record in symbol_records:
                options_data = OptionsHistoricalData.from_breeze_data(record)
                if options_data and options_data.timestamp not in existing_timestamps:
                    new_records.append(options_data)
            
            # Bulk insert new records
            if new_records:
                session.bulk_save_objects(new_records)
                total_added += len(new_records)
        
        # Single commit for all records
        session.commit()
    
    return total_added

# Export the enhanced collection function
def collect_options_data_ultra_optimized(request, job_id: str) -> dict:
    """Ultra-optimized options collection with all enhancements"""
    from src.infrastructure.database.database_manager import get_db_manager
    from test_direct_endpoint_simple import get_weekly_expiry
    from datetime import timedelta
    
    # Initialize database
    db_manager = get_db_manager()
    
    # Initialize connection pool (singleton)
    get_breeze_pool()
    
    # Process date range
    current_date = request.from_date
    total_added = 0
    total_skipped = 0
    total_processed = 0
    errors = []
    daily_results = []
    
    # Calculate total days for progress tracking
    total_days = (request.to_date - request.from_date).days + 1
    processed_days = 0
    
    # Import job_status from main module
    try:
        from test_direct_endpoint_simple import job_status
        globals()['job_status'] = job_status
    except:
        pass
    
    while current_date <= request.to_date:
        try:
            # Update progress
            if job_id and 'job_status' in globals() and job_id in job_status:
                job_status[job_id]["current_date"] = current_date.isoformat()
                job_status[job_id]["processed_days"] = processed_days
                job_status[job_id]["progress"] = round((processed_days / total_days) * 100, 1)
            
            # Skip weekends
            if current_date.weekday() >= 5:
                daily_results.append({
                    "date": current_date.isoformat(),
                    "status": "skipped",
                    "reason": "weekend"
                })
                current_date += timedelta(days=1)
                processed_days += 1
                continue
            
            # Get first trading day's open price with caching
            first_day_open = get_first_trading_day_open_cached(current_date, request.symbol, db_manager)
            if not first_day_open:
                logger.warning(f"Skipping {current_date}: No trading day found this week")
                daily_results.append({
                    "date": current_date.isoformat(),
                    "status": "skipped",
                    "reason": "no_trading_day_this_week"
                })
                current_date += timedelta(days=1)
                processed_days += 1
                continue
            
            # Calculate strike range
            base_strike = int(round(first_day_open / 50) * 50)
            min_strike = base_strike - 500
            max_strike = base_strike + 500
            
            # Get weekly expiry
            expiry_date = get_weekly_expiry(current_date)
            
            logger.info(f"Processing {current_date}: First day open={first_day_open:.2f}, Strikes={min_strike}-{max_strike}, Expiry={expiry_date}")
            
            # Check existing data (can be optimized with caching)
            from_datetime = datetime.combine(current_date, datetime.min.time())
            to_datetime = datetime.combine(current_date, datetime.max.time())
            
            with db_manager.get_session() as session:
                from src.infrastructure.database.models import OptionsHistoricalData
                existing_count = session.query(OptionsHistoricalData).filter(
                    OptionsHistoricalData.underlying == request.symbol,
                    OptionsHistoricalData.timestamp >= from_datetime,
                    OptionsHistoricalData.timestamp <= to_datetime,
                    OptionsHistoricalData.strike >= min_strike,
                    OptionsHistoricalData.strike <= max_strike
                ).count()
            
            # Skip if significant data exists and force_refresh is False
            if existing_count > 100 and not request.force_refresh:
                logger.info(f"{current_date}: {existing_count} records already exist, skipping")
                daily_results.append({
                    "date": current_date.isoformat(),
                    "status": "skipped",
                    "reason": "data_exists",
                    "existing_count": existing_count
                })
                current_date += timedelta(days=1)
                processed_days += 1
                continue
            
            # Collect data with ultra-fast method
            day_result = collect_options_for_day_ultra_fast(
                db_manager, current_date, request.symbol,
                min_strike, max_strike, expiry_date, job_id
            )
            
            # Update totals
            total_added += day_result["records_added"]
            total_processed += 1
            
            daily_results.append({
                "date": current_date.isoformat(),
                "status": "processed",
                "first_day_open": first_day_open,
                "strike_range": f"{min_strike}-{max_strike}",
                "strikes_processed": day_result["strikes_processed"],
                "records_added": day_result["records_added"],
                "errors": day_result.get("errors") if day_result.get("errors") else None,
                "performance": {
                    "duration": f"{day_result['performance_metrics']['duration']:.1f}s",
                    "workers": day_result['performance_metrics']['workers_used']
                }
            })
            
            logger.info(f"{current_date}: Added {day_result['records_added']} records in {day_result['performance_metrics']['duration']:.1f}s")
            
        except Exception as e:
            logger.error(f"{current_date}: {str(e)}")
            errors.append(f"{current_date}: {str(e)}")
            daily_results.append({
                "date": current_date.isoformat(),
                "status": "error",
                "error": str(e)
            })
        
        current_date += timedelta(days=1)
        processed_days += 1
    
    # Final progress update
    if job_id and 'job_status' in globals() and job_id in job_status:
        job_status[job_id]["progress"] = 100
        job_status[job_id]["processed_days"] = processed_days
    
    return {
        "status": "success",
        "summary": {
            "total_days": total_days,
            "days_processed": total_processed,
            "total_records_added": total_added
        },
        "daily_results": daily_results,
        "errors": errors if errors else None,
        "optimization_features": [
            "Connection pooling (10 connections)",
            "Dynamic worker scaling (5-15 workers)",
            "Bulk database inserts",
            "In-memory caching for first trading day prices",
            "Optimized duplicate checking"
        ]
    }