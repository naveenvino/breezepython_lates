"""
Kite Hourly Candle Service
Fetches completed hourly candles from Kite historical API
Triggers stop loss checks on hourly candle completion
"""

import logging
import threading
import time
from datetime import datetime, timedelta, time as dt_time
from typing import Optional, Callable, Dict, Any
from src.services.kite_market_data_service import KiteMarketDataService
from src.services.hybrid_data_manager import get_hybrid_data_manager, HourlyCandle

logger = logging.getLogger(__name__)

class KiteHourlyCandleService:
    """
    Fetches completed hourly candles from Kite and triggers stop loss checks
    Runs after each hour completion to fetch the last candle
    """

    def __init__(self):
        self.data_manager = get_hybrid_data_manager()
        self.kite_service = None
        self.monitoring_thread = None
        self.is_running = False

        # Callback for stop loss check
        self.on_hourly_candle_complete: Optional[Callable[[HourlyCandle], None]] = None

        # Market hours
        self.market_open = dt_time(9, 15)
        self.market_close = dt_time(15, 30)

        # Check times - 1 minute after each hour to ensure candle is complete
        self.check_times = [
            dt_time(10, 16),  # Check 9:15-10:15 candle
            dt_time(11, 16),  # Check 10:15-11:15 candle
            dt_time(12, 16),  # Check 11:15-12:15 candle
            dt_time(13, 16),  # Check 12:15-13:15 candle
            dt_time(14, 16),  # Check 13:15-14:15 candle
            dt_time(15, 16),  # Check 14:15-15:15 candle
            dt_time(15, 31),  # Check 15:15-15:30 candle (end of day)
        ]

        # NIFTY instrument token for Kite (hardcoded for NIFTY 50)
        self.nifty_instrument_token = 256265  # NIFTY 50 index

    def start_monitoring(self):
        """Start the hourly candle monitoring"""
        if self.is_running:
            logger.info("Kite hourly candle service already running")
            return

        try:
            # Initialize Kite service
            self.kite_service = KiteMarketDataService()
            logger.info("Kite market data service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Kite service: {e}")
            return

        self.is_running = True
        self.monitoring_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("Kite hourly candle monitoring started")

    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.is_running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("Kite hourly candle monitoring stopped")

    def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Starting Kite hourly candle monitoring loop")

        while self.is_running:
            try:
                now = datetime.now()
                current_time = now.time()

                # Check if market is open
                if not self._is_market_open(current_time):
                    time.sleep(60)  # Check every minute when market closed
                    continue

                # Check if it's time to fetch a candle
                for check_time in self.check_times:
                    if self._should_check_candle(current_time, check_time):
                        logger.info(f"Fetching hourly candle at {current_time}")
                        self._fetch_and_process_candle(now)
                        # Sleep for 2 minutes to avoid duplicate checks
                        time.sleep(120)
                        break

                # Sleep for 30 seconds before next check
                time.sleep(30)

            except Exception as e:
                logger.error(f"Error in candle monitoring loop: {e}")
                time.sleep(60)

    def _is_market_open(self, current_time: dt_time) -> bool:
        """Check if market is currently open"""
        # Market is open Monday-Friday, 9:15 AM to 3:30 PM
        now = datetime.now()
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        return self.market_open <= current_time <= self.market_close

    def _should_check_candle(self, current_time: dt_time, check_time: dt_time) -> bool:
        """Check if we should fetch candle (within 1 minute window of check time)"""
        # Convert times to total seconds for comparison
        current_seconds = current_time.hour * 3600 + current_time.minute * 60 + current_time.second
        check_seconds = check_time.hour * 3600 + check_time.minute * 60

        # Check if within 60 second window
        return 0 <= (current_seconds - check_seconds) < 60

    def _fetch_and_process_candle(self, check_time: datetime):
        """Fetch the last completed hourly candle from Kite"""
        try:
            # Calculate the time range for the last hour
            # If check_time is 10:16, we want candle from 9:15 to 10:15
            candle_end = check_time.replace(minute=15, second=0, microsecond=0)
            if check_time.minute > 15:
                candle_end = candle_end.replace(hour=check_time.hour)
            else:
                candle_end = candle_end.replace(hour=check_time.hour - 1)

            candle_start = candle_end - timedelta(hours=1)

            # Special case for 15:31 check - get 15:15 to 15:30 candle
            if check_time.time() >= dt_time(15, 31):
                candle_end = check_time.replace(hour=15, minute=30, second=0, microsecond=0)
                candle_start = candle_end.replace(minute=15)

            logger.info(f"Fetching candle from {candle_start} to {candle_end}")

            # Fetch historical data from Kite (60minute interval)
            historical_data = self.kite_service.get_historical_data(
                instrument_token=self.nifty_instrument_token,
                from_date=candle_start,
                to_date=candle_end,
                interval="60minute"
            )

            if historical_data and len(historical_data) > 0:
                # Get the last candle
                candle_data = historical_data[-1]

                # Create HourlyCandle object
                hourly_candle = HourlyCandle(
                    timestamp=candle_data['date'],
                    open=candle_data['open'],
                    high=candle_data['high'],
                    low=candle_data['low'],
                    close=candle_data['close'],
                    volume=candle_data.get('volume', 0),
                    tick_count=0,  # Not available from historical
                    is_complete=True
                )

                logger.info(f"Fetched hourly candle: O={hourly_candle.open}, "
                          f"H={hourly_candle.high}, L={hourly_candle.low}, "
                          f"C={hourly_candle.close}")

                # Add to data manager
                self.data_manager.memory_cache['hourly_candles'].append(hourly_candle)

                # Update spot price
                self.data_manager.memory_cache['spot_price'] = hourly_candle.close
                self.data_manager.memory_cache['last_update'] = datetime.now()

                # Trigger stop loss check callback
                if self.on_hourly_candle_complete:
                    logger.info("Triggering stop loss check on hourly candle")
                    self.on_hourly_candle_complete(hourly_candle)

            else:
                logger.warning(f"No candle data received for {candle_start} to {candle_end}")

        except Exception as e:
            logger.error(f"Error fetching hourly candle: {e}")

    def register_stop_loss_callback(self, callback: Callable[[HourlyCandle], None]):
        """Register callback for stop loss checks on candle completion"""
        self.on_hourly_candle_complete = callback
        logger.info("Stop loss callback registered")

# Singleton instance
_kite_candle_service = None

def get_kite_hourly_candle_service() -> KiteHourlyCandleService:
    """Get singleton instance of Kite hourly candle service"""
    global _kite_candle_service
    if _kite_candle_service is None:
        _kite_candle_service = KiteHourlyCandleService()
    return _kite_candle_service