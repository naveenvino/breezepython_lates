"""
Batch Database Operations for Performance Optimization
Provides efficient batch querying and caching for the trading system
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session, joinedload, selectinload
from functools import lru_cache
import logging
import pandas as pd
import numpy as np

from src.infrastructure.database.models import (
    BacktestTrade, 
    BacktestPosition,
    OptionsHistoricalData,
    NiftyIndexData5Minute
)

logger = logging.getLogger(__name__)


class BatchOperations:
    """Optimized batch operations for database queries"""
    
    def __init__(self, session: Session):
        self.session = session
        self._cache = {}
        
    def get_option_prices_batch(
        self, 
        timestamps: List[datetime],
        strike_prices: List[float],
        option_types: List[str],
        expiry_date: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Batch fetch option prices for multiple strikes and timestamps
        Reduces N queries to 1 query
        """
        try:
            # Create cache key
            cache_key = f"options_{min(timestamps)}_{max(timestamps)}_{min(strike_prices)}_{max(strike_prices)}"
            
            if cache_key in self._cache:
                logger.debug(f"Cache hit for option prices: {cache_key}")
                return self._cache[cache_key]
            
            # Build efficient query with all conditions
            query = self.session.query(OptionsHistoricalData)
            
            # Use IN clause for batch lookup
            query = query.filter(
                and_(
                    OptionsHistoricalData.Timestamp.in_(timestamps),
                    OptionsHistoricalData.StrikePrice.in_(strike_prices),
                    OptionsHistoricalData.OptionType.in_(option_types)
                )
            )
            
            if expiry_date:
                query = query.filter(OptionsHistoricalData.ExpiryDate == expiry_date)
            
            # Fetch all at once
            results = query.all()
            
            # Convert to DataFrame for easy manipulation
            data = []
            for r in results:
                data.append({
                    'timestamp': r.Timestamp,
                    'strike_price': r.StrikePrice,
                    'option_type': r.OptionType,
                    'close': r.Close,
                    'iv': r.IV,
                    'delta': r.Delta,
                    'gamma': r.Gamma,
                    'theta': r.Theta,
                    'vega': r.Vega,
                    'volume': r.Volume,
                    'open_interest': r.OpenInterest
                })
            
            df = pd.DataFrame(data)
            
            # Cache the result
            self._cache[cache_key] = df
            
            logger.info(f"Batch fetched {len(df)} option prices in single query")
            return df
            
        except Exception as e:
            logger.error(f"Error in batch option price fetch: {e}")
            return pd.DataFrame()
    
    def get_trades_with_positions_batch(
        self,
        backtest_run_id: int,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[BacktestTrade]:
        """
        Fetch trades with positions using eager loading
        Eliminates N+1 query problem
        """
        try:
            query = self.session.query(BacktestTrade).options(
                joinedload(BacktestTrade.positions)  # Eager load positions
            ).filter(
                BacktestTrade.BacktestRunId == backtest_run_id
            )
            
            if start_time:
                query = query.filter(BacktestTrade.EntryTime >= start_time)
            if end_time:
                query = query.filter(BacktestTrade.EntryTime <= end_time)
            
            trades = query.all()
            logger.info(f"Batch fetched {len(trades)} trades with positions")
            return trades
            
        except Exception as e:
            logger.error(f"Error in batch trade fetch: {e}")
            return []
    
    def get_nifty_data_batch(
        self,
        start_time: datetime,
        end_time: datetime,
        interval: str = '5min'
    ) -> pd.DataFrame:
        """
        Batch fetch NIFTY data for a time range
        """
        cache_key = f"nifty_{start_time}_{end_time}_{interval}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            if interval == '5min':
                query = self.session.query(NiftyIndexData5Minute).filter(
                    and_(
                        NiftyIndexData5Minute.Timestamp >= start_time,
                        NiftyIndexData5Minute.Timestamp <= end_time
                    )
                ).order_by(NiftyIndexData5Minute.Timestamp)
                
                results = query.all()
                
                data = []
                for r in results:
                    data.append({
                        'timestamp': r.Timestamp,
                        'open': r.Open,
                        'high': r.High,
                        'low': r.Low,
                        'close': r.Close,
                        'volume': r.Volume
                    })
                
                df = pd.DataFrame(data)
                self._cache[cache_key] = df
                
                logger.info(f"Batch fetched {len(df)} NIFTY data points")
                return df
                
        except Exception as e:
            logger.error(f"Error fetching NIFTY data: {e}")
            return pd.DataFrame()
    
    def bulk_insert_trades(self, trades: List[Dict[str, Any]]) -> bool:
        """
        Bulk insert trades for better performance
        """
        try:
            # Use bulk_insert_mappings for efficiency
            self.session.bulk_insert_mappings(BacktestTrade, trades)
            self.session.commit()
            logger.info(f"Bulk inserted {len(trades)} trades")
            return True
            
        except Exception as e:
            logger.error(f"Error in bulk insert: {e}")
            self.session.rollback()
            return False
    
    def bulk_insert_positions(self, positions: List[Dict[str, Any]]) -> bool:
        """
        Bulk insert positions for better performance
        """
        try:
            self.session.bulk_insert_mappings(BacktestPosition, positions)
            self.session.commit()
            logger.info(f"Bulk inserted {len(positions)} positions")
            return True
            
        except Exception as e:
            logger.error(f"Error in bulk position insert: {e}")
            self.session.rollback()
            return False
    
    @lru_cache(maxsize=128)
    def get_strike_range_cached(
        self,
        spot_price: float,
        num_strikes: int = 10
    ) -> Tuple[float, float]:
        """
        Cached calculation of strike range
        """
        strike_interval = 50
        min_strike = (spot_price - (num_strikes * strike_interval))
        max_strike = (spot_price + (num_strikes * strike_interval))
        
        # Round to nearest 50
        min_strike = round(min_strike / 50) * 50
        max_strike = round(max_strike / 50) * 50
        
        return min_strike, max_strike
    
    def clear_cache(self):
        """Clear the internal cache"""
        self._cache.clear()
        logger.info("Cache cleared")


class PerformanceMonitor:
    """Monitor and log performance metrics"""
    
    def __init__(self):
        self.metrics = {}
        self.start_times = {}
    
    def start_timer(self, operation: str):
        """Start timing an operation"""
        self.start_times[operation] = datetime.now()
    
    def end_timer(self, operation: str) -> float:
        """End timing and return duration in seconds"""
        if operation in self.start_times:
            duration = (datetime.now() - self.start_times[operation]).total_seconds()
            
            if operation not in self.metrics:
                self.metrics[operation] = []
            self.metrics[operation].append(duration)
            
            del self.start_times[operation]
            
            # Log if operation took too long
            if duration > 1.0:
                logger.warning(f"Operation '{operation}' took {duration:.2f} seconds")
            
            return duration
        return 0
    
    def get_stats(self, operation: str) -> Dict[str, float]:
        """Get statistics for an operation"""
        if operation in self.metrics:
            times = self.metrics[operation]
            return {
                'count': len(times),
                'total': sum(times),
                'average': np.mean(times),
                'median': np.median(times),
                'p95': np.percentile(times, 95),
                'max': max(times)
            }
        return {}
    
    def print_summary(self):
        """Print performance summary"""
        print("\n=== Performance Summary ===")
        for operation, times in self.metrics.items():
            stats = self.get_stats(operation)
            print(f"\n{operation}:")
            print(f"  Count: {stats['count']}")
            print(f"  Average: {stats['average']:.3f}s")
            print(f"  P95: {stats['p95']:.3f}s")
            print(f"  Max: {stats['max']:.3f}s")