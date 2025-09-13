"""
Test script for updated Kite-based monitoring system
Tests the three-layer monitoring with Kite API integration
"""

import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_kite_market_data_service():
    """Test Kite market data service for fetching option prices"""
    logger.info("Testing Kite Market Data Service...")

    try:
        from src.services.kite_market_data_service import KiteMarketDataService

        # Initialize service
        kite_service = KiteMarketDataService()
        logger.info("[OK] Kite service initialized")

        # Test fetching NIFTY spot price
        spot_price = kite_service.get_spot_price('NIFTY')
        logger.info(f"[OK] NIFTY Spot Price: {spot_price}")

        # Test fetching option price
        expiry = datetime.now()
        # Adjust to next Thursday
        days_until_thursday = (3 - expiry.weekday()) % 7
        if days_until_thursday == 0 and expiry.hour >= 15:
            days_until_thursday = 7

        # Test symbol format
        test_strike = 25000
        symbol = f"NFO:NIFTY{expiry.strftime('%y%b').upper()}{test_strike}CE"
        logger.info(f"Testing option symbol: {symbol}")

        ltp_data = kite_service.get_ltp([symbol])
        if symbol in ltp_data:
            logger.info(f"[OK] Option LTP: {ltp_data[symbol]}")
        else:
            logger.warning(f"[WARN] Could not fetch price for {symbol}")

        return True

    except Exception as e:
        logger.error(f"[FAIL] Kite service test failed: {e}")
        return False

def test_kite_hourly_candle_service():
    """Test Kite hourly candle service"""
    logger.info("\nTesting Kite Hourly Candle Service...")

    try:
        from src.services.kite_hourly_candle_service import get_kite_hourly_candle_service

        # Get service instance
        candle_service = get_kite_hourly_candle_service()
        logger.info("[OK] Candle service obtained")

        # Test fetching historical data
        from datetime import timedelta
        now = datetime.now()

        # Only test during market hours
        if now.weekday() < 5 and now.time() > datetime.strptime("09:15", "%H:%M").time():
            candle_service.start_monitoring()
            logger.info("[OK] Candle monitoring started")

            # Wait a bit to see if it works
            logger.info("Waiting 5 seconds for monitoring to initialize...")
            time.sleep(5)

            candle_service.stop_monitoring()
            logger.info("[OK] Candle monitoring stopped")
        else:
            logger.info("[SKIP] Market closed - skipping live test")

        return True

    except Exception as e:
        logger.error(f"[FAIL] Candle service test failed: {e}")
        return False

def test_realtime_stop_loss_monitor():
    """Test real-time stop loss monitor with Kite"""
    logger.info("\nTesting Real-time Stop Loss Monitor...")

    try:
        from src.services.realtime_stop_loss_monitor import get_realtime_monitor

        # Get monitor instance
        monitor = get_realtime_monitor()
        logger.info("[OK] Real-time monitor obtained")

        # Check monitoring interval
        logger.info(f"Monitoring interval: {monitor.monitoring_interval} seconds")

        # Start monitoring
        monitor.start_monitoring()
        logger.info("[OK] Real-time monitoring started")

        # Let it run for a few seconds
        logger.info("Monitoring for 10 seconds...")
        time.sleep(10)

        # Stop monitoring
        monitor.stop_monitoring()
        logger.info("[OK] Real-time monitoring stopped")

        return True

    except Exception as e:
        logger.error(f"[FAIL] Real-time monitor test failed: {e}")
        return False

def test_trailing_stop_configuration():
    """Test trailing stop configuration loading"""
    logger.info("\nTesting Trailing Stop Configuration...")

    try:
        from src.services.live_stoploss_monitor import get_live_stoploss_monitor

        # Get monitor instance
        monitor = get_live_stoploss_monitor()
        logger.info("[OK] Live stop loss monitor obtained")

        # Check trailing stop rule
        trailing_rule = None
        for rule in monitor.stop_loss_rules:
            if rule.type.value == 'trailing':
                trailing_rule = rule
                break

        if trailing_rule:
            logger.info(f"[OK] Trailing Stop - Enabled: {trailing_rule.enabled}")
            logger.info(f"     Trail Percent: {trailing_rule.params.get('trail_percent')}%")
        else:
            logger.warning("[WARN] Trailing stop rule not found")

        # Check profit lock rule
        profit_lock_rule = None
        for rule in monitor.stop_loss_rules:
            if rule.type.value == 'profit_lock':
                profit_lock_rule = rule
                break

        if profit_lock_rule:
            logger.info(f"[OK] Profit Lock - Enabled: {profit_lock_rule.enabled}")
            logger.info(f"     Target: {profit_lock_rule.params.get('target_percent')}%")
            logger.info(f"     Lock: {profit_lock_rule.params.get('lock_percent')}%")
        else:
            logger.warning("[WARN] Profit lock rule not found")

        return True

    except Exception as e:
        logger.error(f"[FAIL] Configuration test failed: {e}")
        return False

def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("KITE MONITORING SYSTEM TEST")
    logger.info("=" * 60)

    all_passed = True

    # Test 1: Kite Market Data Service
    if not test_kite_market_data_service():
        all_passed = False

    # Test 2: Kite Hourly Candle Service
    if not test_kite_hourly_candle_service():
        all_passed = False

    # Test 3: Real-time Stop Loss Monitor
    if not test_realtime_stop_loss_monitor():
        all_passed = False

    # Test 4: Trailing Stop Configuration
    if not test_trailing_stop_configuration():
        all_passed = False

    logger.info("\n" + "=" * 60)
    if all_passed:
        logger.info("[SUCCESS] All tests passed!")
    else:
        logger.error("[FAILURE] Some tests failed - check logs above")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()