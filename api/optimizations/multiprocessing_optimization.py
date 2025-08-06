"""
Multi-processing for CPU-bound operations
"""
from multiprocessing import Pool, cpu_count, Manager
from functools import partial
import numpy as np
from typing import List, Dict, Tuple
from datetime import date, datetime
import time

def process_options_chunk(
    chunk_data: Tuple[List[int], date, str, date],
    shared_credentials: Dict
) -> Dict:
    """Process a chunk of strikes in a separate process"""
    strikes, request_date, symbol, expiry_date = chunk_data
    
    # Each process gets its own Breeze connection
    from breeze_connect import BreezeConnect
    breeze = BreezeConnect(api_key=shared_credentials['api_key'])
    breeze.generate_session(
        api_secret=shared_credentials['api_secret'],
        session_token=shared_credentials['session_token']
    )
    
    results = []
    for strike in strikes:
        for option_type in ['CE', 'PE']:
            # Fetch data
            # ... (actual implementation)
            results.append({
                'strike': strike,
                'type': option_type,
                'records': 75  # Placeholder
            })
    
    return results

def collect_options_multiprocess(
    request_date: date,
    symbol: str,
    strikes: List[int],
    expiry_date: date,
    credentials: Dict
) -> Dict:
    """Collect options using multiple processes"""
    
    start_time = time.time()
    
    # Determine optimal number of processes
    num_processes = min(cpu_count(), 8)  # Cap at 8 to avoid overwhelming API
    
    # Split strikes into chunks
    strikes_array = np.array(strikes)
    chunks = np.array_split(strikes_array, num_processes)
    
    # Prepare data for each process
    chunk_data = [
        (chunk.tolist(), request_date, symbol, expiry_date)
        for chunk in chunks
    ]
    
    # Use multiprocessing
    with Pool(processes=num_processes) as pool:
        # Partial function with shared credentials
        process_func = partial(process_options_chunk, shared_credentials=credentials)
        
        # Process all chunks in parallel
        results = pool.map(process_func, chunk_data)
    
    # Combine results
    all_results = []
    for chunk_results in results:
        all_results.extend(chunk_results)
    
    duration = time.time() - start_time
    
    return {
        'total_strikes': len(strikes) * 2,
        'duration': duration,
        'processes_used': num_processes,
        'results': all_results
    }

# Optimized data processing using NumPy
def process_market_data_numpy(records: List[Dict]) -> np.ndarray:
    """Process market data using NumPy for speed"""
    
    # Convert to NumPy arrays for faster processing
    timestamps = np.array([r['timestamp'] for r in records])
    opens = np.array([r['open'] for r in records], dtype=np.float32)
    highs = np.array([r['high'] for r in records], dtype=np.float32)
    lows = np.array([r['low'] for r in records], dtype=np.float32)
    closes = np.array([r['close'] for r in records], dtype=np.float32)
    volumes = np.array([r['volume'] for r in records], dtype=np.int32)
    
    # Vectorized calculations
    # Example: Calculate VWAP
    vwap = np.sum(closes * volumes) / np.sum(volumes)
    
    # Example: Find support/resistance levels
    resistance = np.max(highs)
    support = np.min(lows)
    
    return {
        'vwap': vwap,
        'resistance': resistance,
        'support': support,
        'avg_volume': np.mean(volumes)
    }