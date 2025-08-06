"""
Optimized Options Bulk Collection with improvements
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
import time
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class OptimizedOptionsBulkCollector:
    def __init__(self, breeze, db_manager, max_workers=5):
        self.breeze = breeze
        self.db_manager = db_manager
        self.max_workers = max_workers
        
    def collect_options_parallel(self, request_date: date, strikes: List[int], expiry_date: date) -> Dict:
        """Collect options data for multiple strikes in parallel"""
        
        results = {
            "success": [],
            "failed": [],
            "total_records": 0
        }
        
        # Create tasks for all strike/type combinations
        tasks = []
        for strike in strikes:
            for option_type in ['CE', 'PE']:
                tasks.append((strike, option_type))
        
        # Process in parallel with thread pool
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_strike = {
                executor.submit(
                    self._fetch_single_option, 
                    request_date, 
                    strike, 
                    option_type, 
                    expiry_date
                ): (strike, option_type)
                for strike, option_type in tasks
            }
            
            # Process completed tasks
            for future in as_completed(future_to_strike):
                strike, option_type = future_to_strike[future]
                try:
                    records_added = future.result()
                    if records_added > 0:
                        results["success"].append(f"{strike}{option_type}")
                        results["total_records"] += records_added
                except Exception as e:
                    results["failed"].append({
                        "strike": f"{strike}{option_type}",
                        "error": str(e)
                    })
                    logger.error(f"Failed to collect {strike}{option_type}: {e}")
        
        return results
    
    def _fetch_single_option(self, request_date: date, strike: int, option_type: str, expiry_date: date) -> int:
        """Fetch data for a single option (called in parallel)"""
        from_datetime = datetime.combine(request_date, datetime.min.time())
        to_datetime = datetime.combine(request_date, datetime.max.time())
        
        # Convert CE/PE to call/put
        right_type = "call" if option_type == "CE" else "put"
        
        # Construct option symbol
        expiry_str = expiry_date.strftime("%y%b%d").upper()
        option_symbol = f"NIFTY{expiry_str}{strike}{option_type}"
        
        # Fetch from Breeze
        result = self.breeze.get_historical_data_v2(
            interval="5minute",
            from_date=from_datetime.strftime("%Y-%m-%dT00:00:00.000Z"),
            to_date=to_datetime.strftime("%Y-%m-%dT23:59:59.000Z"),
            stock_code="NIFTY",
            exchange_code="NFO",
            product_type="options",
            expiry_date=expiry_date.strftime("%Y-%m-%dT00:00:00.000Z"),
            right=right_type,
            strike_price=str(strike)
        )
        
        if result and 'Success' in result:
            records = result['Success']
            return self._store_option_records(records, option_symbol, strike, option_type, expiry_date)
        
        return 0
    
    def _store_option_records(self, records: List[Dict], option_symbol: str, 
                            strike: int, option_type: str, expiry_date: date) -> int:
        """Store option records in batch"""
        from src.infrastructure.database.models import OptionsHistoricalData
        
        added_count = 0
        
        # Prepare all records first
        options_to_add = []
        for record in records:
            # Add required fields
            record['underlying'] = "NIFTY"
            record['strike_price'] = strike
            record['right'] = option_type
            record['expiry_date'] = expiry_date.strftime("%Y-%m-%dT00:00:00.000Z")
            record['trading_symbol'] = option_symbol
            
            options_data = OptionsHistoricalData.from_breeze_data(record)
            if options_data:
                options_to_add.append(options_data)
        
        # Bulk insert
        if options_to_add:
            with self.db_manager.get_session() as session:
                # Check existing in bulk
                existing_timestamps = set()
                existing = session.query(OptionsHistoricalData.timestamp).filter(
                    OptionsHistoricalData.trading_symbol == option_symbol
                ).all()
                existing_timestamps = {e[0] for e in existing}
                
                # Filter new records
                new_records = [
                    opt for opt in options_to_add 
                    if opt.timestamp not in existing_timestamps
                ]
                
                if new_records:
                    session.bulk_save_objects(new_records)
                    session.commit()
                    added_count = len(new_records)
        
        return added_count

# Progress tracking for bulk collection
class BulkProgressTracker:
    def __init__(self, job_id: str, total_days: int):
        self.job_id = job_id
        self.total_days = total_days
        self.processed_days = 0
        self.total_records = 0
        self.start_time = time.time()
        
    def update_progress(self, job_status: Dict):
        """Update job status with progress"""
        self.processed_days += 1
        elapsed = time.time() - self.start_time
        
        # Calculate ETA
        if self.processed_days > 0:
            avg_time_per_day = elapsed / self.processed_days
            remaining_days = self.total_days - self.processed_days
            eta_seconds = remaining_days * avg_time_per_day
        else:
            eta_seconds = 0
        
        job_status[self.job_id].update({
            "progress": round((self.processed_days / self.total_days) * 100, 1),
            "processed_days": self.processed_days,
            "total_days": self.total_days,
            "total_records": self.total_records,
            "elapsed_time": round(elapsed, 1),
            "estimated_time_remaining": round(eta_seconds, 1),
            "current_date": None
        })

# Checkpoint system for resume capability
class CheckpointManager:
    def __init__(self, job_id: str):
        self.checkpoint_file = f"checkpoint_{job_id}.json"
        
    def save_checkpoint(self, last_completed_date: date, records_collected: int):
        """Save progress checkpoint"""
        import json
        checkpoint = {
            "last_completed_date": last_completed_date.isoformat(),
            "records_collected": records_collected,
            "timestamp": datetime.now().isoformat()
        }
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint, f)
    
    def load_checkpoint(self) -> Tuple[date, int]:
        """Load checkpoint if exists"""
        import json
        import os
        
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
                return (
                    date.fromisoformat(checkpoint["last_completed_date"]),
                    checkpoint["records_collected"]
                )
        return None, 0
    
    def cleanup(self):
        """Remove checkpoint file"""
        import os
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)

# Example of optimized bulk collection function
def collect_options_bulk_optimized(request, job_id: str, job_status: Dict):
    """Optimized bulk collection with parallel processing and progress tracking"""
    from src.infrastructure.database.database_manager import get_db_manager
    from breeze_connect import BreezeConnect
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Initialize
    db_manager = get_db_manager()
    breeze = BreezeConnect(api_key=os.getenv('BREEZE_API_KEY'))
    breeze.generate_session(
        api_secret=os.getenv('BREEZE_API_SECRET'),
        session_token=os.getenv('BREEZE_API_SESSION')
    )
    
    # Create optimized collector
    collector = OptimizedOptionsBulkCollector(breeze, db_manager, max_workers=5)
    
    # Progress tracking
    total_days = (request.to_date - request.from_date).days + 1
    tracker = BulkProgressTracker(job_id, total_days)
    
    # Checkpoint manager for resume capability
    checkpoint = CheckpointManager(job_id)
    last_completed, total_records = checkpoint.load_checkpoint()
    
    # Start from checkpoint if exists
    current_date = last_completed + timedelta(days=1) if last_completed else request.from_date
    tracker.total_records = total_records
    
    try:
        while current_date <= request.to_date:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            # Update current processing date
            job_status[job_id]["current_date"] = current_date.isoformat()
            
            # Get first trading day's open price
            from test_direct_endpoint_simple import get_first_trading_day_open_price
            first_day_open = get_first_trading_day_open_price(current_date, "NIFTY", db_manager)
            
            if not first_day_open:
                current_date += timedelta(days=1)
                continue
            
            # Calculate strikes
            base_strike = int(round(first_day_open / 50) * 50)
            min_strike = base_strike - 1000
            max_strike = base_strike + 1000
            strikes = list(range(min_strike, max_strike + 50, 50))
            
            # Get expiry date
            from test_direct_endpoint_simple import get_weekly_expiry
            expiry_date = get_weekly_expiry(current_date)
            
            # Collect in parallel
            logger.info(f"Processing {current_date} with {len(strikes)} strikes in parallel...")
            results = collector.collect_options_parallel(current_date, strikes, expiry_date)
            
            # Update progress
            tracker.total_records += results["total_records"]
            tracker.update_progress(job_status)
            
            # Save checkpoint
            checkpoint.save_checkpoint(current_date, tracker.total_records)
            
            # Move to next day
            current_date += timedelta(days=1)
            
            # Small delay to avoid overwhelming the API
            time.sleep(0.5)
        
        # Cleanup checkpoint on success
        checkpoint.cleanup()
        
        job_status[job_id]["status"] = "completed"
        job_status[job_id]["end_time"] = datetime.now().isoformat()
        job_status[job_id]["result"] = {
            "status": "success",
            "total_records": tracker.total_records,
            "processed_days": tracker.processed_days
        }
        
    except Exception as e:
        job_status[job_id]["status"] = "failed"
        job_status[job_id]["error"] = str(e)
        logger.error(f"Bulk collection failed: {e}")