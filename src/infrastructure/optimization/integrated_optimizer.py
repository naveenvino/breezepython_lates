"""
Integrated Performance Optimizer
Combines all optimization techniques for maximum performance
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import asyncio

from .batch_operations import BatchOperations, PerformanceMonitor
from .vectorized_operations import VectorizedBacktest, VectorizedMLFeatures
from ..cache import get_cache
from ..database.optimized_connection import get_optimized_connection

logger = logging.getLogger(__name__)


class IntegratedOptimizer:
    """
    Integrated optimizer combining all performance enhancements:
    - Batch database operations
    - Redis caching
    - Vectorized calculations
    - Connection pooling
    - Parallel processing
    """
    
    def __init__(self):
        self.db = get_optimized_connection()
        self.cache = get_cache()
        self.monitor = PerformanceMonitor()
        self.vectorized = VectorizedBacktest()
        self.ml_features = VectorizedMLFeatures()
        
        # Thread pool for I/O operations
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        
        # Process pool for CPU-intensive operations
        self.process_pool = ProcessPoolExecutor(max_workers=4)
        
        logger.info("Integrated Optimizer initialized with all enhancements")
    
    def optimize_backtest(
        self,
        start_date: datetime,
        end_date: datetime,
        signals_to_test: List[str],
        use_cache: bool = True,
        parallel: bool = True
    ) -> Dict[str, Any]:
        """
        Run optimized backtest with all performance enhancements
        
        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            signals_to_test: List of signals to test
            use_cache: Whether to use Redis caching
            parallel: Whether to use parallel processing
        
        Returns:
            Backtest results with performance metrics
        """
        self.monitor.start_timer("total_backtest")
        
        results = {
            'trades': [],
            'performance_metrics': {},
            'optimization_stats': {}
        }
        
        try:
            # Step 1: Fetch data with caching
            self.monitor.start_timer("data_fetch")
            
            if use_cache:
                # Try cache first
                nifty_data = self.cache.get_nifty_data(start_date, end_date, '5min')
                if nifty_data is None:
                    # Cache miss - fetch from database
                    with self.db.get_session() as session:
                        batch_ops = BatchOperations(session)
                        nifty_data = batch_ops.get_nifty_data_batch(start_date, end_date)
                        # Cache for next time
                        self.cache.set_nifty_data(start_date, end_date, '5min', nifty_data, ttl=3600)
            else:
                with self.db.get_session() as session:
                    batch_ops = BatchOperations(session)
                    nifty_data = batch_ops.get_nifty_data_batch(start_date, end_date)
            
            data_fetch_time = self.monitor.end_timer("data_fetch")
            logger.info(f"Data fetched in {data_fetch_time:.2f}s")
            
            # Step 2: Calculate indicators using vectorized operations
            self.monitor.start_timer("indicators")
            nifty_data = self.vectorized.calculate_indicators_vectorized(nifty_data)
            indicators_time = self.monitor.end_timer("indicators")
            
            # Step 3: Detect signals (parallel if enabled)
            self.monitor.start_timer("signal_detection")
            
            if parallel:
                # Process signals in parallel
                signal_results = self._parallel_signal_detection(
                    nifty_data, signals_to_test
                )
            else:
                # Sequential processing
                signal_results = self._sequential_signal_detection(
                    nifty_data, signals_to_test
                )
            
            signal_time = self.monitor.end_timer("signal_detection")
            
            # Step 4: Process trades with batch operations
            self.monitor.start_timer("trade_processing")
            
            with self.db.get_session() as session:
                batch_ops = BatchOperations(session)
                
                # Collect all option requirements
                all_strikes = set()
                all_timestamps = set()
                
                for signal_data in signal_results:
                    for trade in signal_data['trades']:
                        all_strikes.add(trade['strike'])
                        all_timestamps.add(trade['entry_time'])
                        if trade.get('exit_time'):
                            all_timestamps.add(trade['exit_time'])
                
                # Batch fetch all option prices
                if all_strikes and all_timestamps:
                    option_prices = batch_ops.get_option_prices_batch(
                        list(all_timestamps),
                        list(all_strikes),
                        ['CE', 'PE']
                    )
                    
                    # Cache option prices
                    if use_cache:
                        for timestamp in all_timestamps:
                            timestamp_data = option_prices[
                                option_prices['timestamp'] == timestamp
                            ]
                            self.cache.set_option_prices(
                                timestamp,
                                list(all_strikes),
                                ['CE', 'PE'],
                                timestamp_data,
                                ttl=7200
                            )
            
            trade_time = self.monitor.end_timer("trade_processing")
            
            # Step 5: Calculate PnL using vectorized operations
            self.monitor.start_timer("pnl_calculation")
            
            all_trades = []
            for signal_data in signal_results:
                all_trades.extend(signal_data['trades'])
            
            if all_trades:
                entry_prices = np.array([t['entry_price'] for t in all_trades])
                exit_prices = np.array([t.get('exit_price', t['entry_price']) for t in all_trades])
                quantities = np.array([t.get('quantity', 750) for t in all_trades])
                is_buy = np.array([t.get('direction', 'sell') == 'buy' for t in all_trades])
                
                pnl_array = self.vectorized.calculate_pnl_vectorized(
                    entry_prices, exit_prices, quantities, is_buy
                )
                
                # Add PnL to trades
                for i, trade in enumerate(all_trades):
                    trade['pnl'] = pnl_array[i]
            
            pnl_time = self.monitor.end_timer("pnl_calculation")
            
            # Step 6: Calculate performance metrics
            self.monitor.start_timer("metrics")
            
            if all_trades:
                total_pnl = np.sum([t['pnl'] for t in all_trades])
                win_rate = np.mean([t['pnl'] > 0 for t in all_trades]) * 100
                
                # Vectorized drawdown calculation
                cumulative_pnl = pd.Series([t['pnl'] for t in all_trades]).cumsum()
                drawdown_metrics = self.vectorized.calculate_drawdown_vectorized(cumulative_pnl)
                
                results['performance_metrics'] = {
                    'total_pnl': total_pnl,
                    'total_trades': len(all_trades),
                    'win_rate': win_rate,
                    'max_drawdown': drawdown_metrics['max_drawdown'].iloc[0],
                    'max_drawdown_pct': drawdown_metrics['max_drawdown_pct'].iloc[0]
                }
            
            metrics_time = self.monitor.end_timer("metrics")
            
            # Total time
            total_time = self.monitor.end_timer("total_backtest")
            
            # Add optimization statistics
            results['optimization_stats'] = {
                'total_time': total_time,
                'data_fetch_time': data_fetch_time,
                'indicators_time': indicators_time,
                'signal_detection_time': signal_time,
                'trade_processing_time': trade_time,
                'pnl_calculation_time': pnl_time,
                'metrics_time': metrics_time,
                'cache_enabled': use_cache,
                'parallel_enabled': parallel,
                'db_pool_status': self.db.get_pool_status(),
                'cache_stats': self.cache.get_stats()
            }
            
            results['trades'] = all_trades
            
            # Print performance summary
            self._print_performance_summary(results['optimization_stats'])
            
            return results
            
        except Exception as e:
            logger.error(f"Optimized backtest failed: {e}")
            raise
        finally:
            # Cleanup
            self.monitor.print_summary()
    
    def _parallel_signal_detection(
        self,
        data: pd.DataFrame,
        signals: List[str]
    ) -> List[Dict[str, Any]]:
        """Process signals in parallel"""
        futures = []
        
        for signal in signals:
            future = self.thread_pool.submit(
                self._detect_signal_optimized,
                data.copy(),
                signal
            )
            futures.append(future)
        
        results = []
        for future in futures:
            results.append(future.result())
        
        return results
    
    def _sequential_signal_detection(
        self,
        data: pd.DataFrame,
        signals: List[str]
    ) -> List[Dict[str, Any]]:
        """Process signals sequentially"""
        results = []
        
        for signal in signals:
            result = self._detect_signal_optimized(data.copy(), signal)
            results.append(result)
        
        return results
    
    def _detect_signal_optimized(
        self,
        data: pd.DataFrame,
        signal_type: str
    ) -> Dict[str, Any]:
        """Optimized signal detection using vectorized operations"""
        # This would integrate with your actual signal detection logic
        # Using vectorized operations for maximum speed
        
        # Example implementation
        trades = []
        
        # Vectorized signal detection based on signal type
        if signal_type == 'S1':  # Bear Trap
            mask = (data['low'] < data['support']) & (data['close'] > data['support'])
            signal_indices = data[mask].index
        elif signal_type == 'S2':  # Support Hold
            mask = (data['low'] >= data['support']) & (data['close'] > data['support'])
            signal_indices = data[mask].index
        else:
            signal_indices = []
        
        for idx in signal_indices[:10]:  # Limit for example
            trades.append({
                'signal': signal_type,
                'entry_time': data.loc[idx, 'timestamp'],
                'entry_price': data.loc[idx, 'close'],
                'strike': round(data.loc[idx, 'close'] / 50) * 50,
                'quantity': 750,
                'direction': 'sell'
            })
        
        return {
            'signal': signal_type,
            'trades': trades
        }
    
    def _print_performance_summary(self, stats: Dict[str, Any]):
        """Print performance optimization summary"""
        print("\n" + "="*60)
        print("PERFORMANCE OPTIMIZATION SUMMARY")
        print("="*60)
        
        print(f"\n📊 Execution Times:")
        print(f"  • Total Time:        {stats['total_time']:.2f}s")
        print(f"  • Data Fetch:        {stats['data_fetch_time']:.2f}s")
        print(f"  • Indicators:        {stats['indicators_time']:.2f}s")
        print(f"  • Signal Detection:  {stats['signal_detection_time']:.2f}s")
        print(f"  • Trade Processing:  {stats['trade_processing_time']:.2f}s")
        print(f"  • PnL Calculation:   {stats['pnl_calculation_time']:.2f}s")
        
        print(f"\n⚡ Optimization Status:")
        print(f"  • Cache Enabled:     {stats['cache_enabled']}")
        print(f"  • Parallel Enabled:  {stats['parallel_enabled']}")
        
        if 'cache_stats' in stats and stats['cache_stats']:
            cache = stats['cache_stats']
            if 'hit_rate' in cache:
                print(f"  • Cache Hit Rate:    {cache['hit_rate']:.1%}")
            if 'keys' in cache:
                print(f"  • Cached Items:      {cache['keys']}")
        
        if 'db_pool_status' in stats:
            pool = stats['db_pool_status']
            print(f"\n🔌 Database Pool:")
            print(f"  • Active:            {pool.get('checked_out', 0)}")
            print(f"  • Available:         {pool.get('checked_in', 0)}")
            print(f"  • Total:             {pool.get('total', 0)}")
        
        print("\n" + "="*60)
    
    def cleanup(self):
        """Cleanup resources"""
        self.thread_pool.shutdown(wait=True)
        self.process_pool.shutdown(wait=True)
        logger.info("Optimizer resources cleaned up")


# Example usage
def demonstrate_optimization():
    """Demonstrate the performance improvements"""
    
    optimizer = IntegratedOptimizer()
    
    # Run optimized backtest
    results = optimizer.optimize_backtest(
        start_date=datetime(2024, 7, 14),
        end_date=datetime(2024, 7, 18),
        signals_to_test=['S1', 'S2', 'S3'],
        use_cache=True,
        parallel=True
    )
    
    print(f"\n✅ Backtest completed successfully!")
    print(f"  • Total Trades: {len(results['trades'])}")
    print(f"  • Total PnL: ₹{results['performance_metrics'].get('total_pnl', 0):,.2f}")
    print(f"  • Win Rate: {results['performance_metrics'].get('win_rate', 0):.1f}%")
    
    optimizer.cleanup()
    
    return results