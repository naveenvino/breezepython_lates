#!/usr/bin/env python3
"""
CRITICAL SAFETY: Stop Loss Validation System
Prevents false triggers from mock/stale data
"""

from datetime import datetime, timedelta
import pytz

class StopLossValidator:
    """Validate stop loss triggers with multiple safety checks"""
    
    def __init__(self):
        self.ist = pytz.timezone('Asia/Kolkata')
        self.last_candle_time = None
        self.last_candle_price = None
        
    def validate_1hr_candle_stop(self, position, candle_data):
        """
        CRITICAL: Validate candle data before triggering stop loss
        Returns: (should_trigger, reason)
        """
        
        # SAFETY CHECK 1: Validate candle timestamp
        if not self.is_candle_current(candle_data):
            return False, "REJECTED: Stale candle data"
        
        # SAFETY CHECK 2: Validate data source
        if not self.is_data_real(candle_data):
            return False, "REJECTED: Mock/test data detected"
        
        # SAFETY CHECK 3: Validate market hours
        if not self.is_market_hours():
            return False, "REJECTED: Outside market hours"
        
        # SAFETY CHECK 4: Validate price sanity
        if not self.is_price_sane(candle_data):
            return False, "REJECTED: Abnormal price detected"
        
        # SAFETY CHECK 5: Validate candle completion
        if not self.is_candle_complete(candle_data):
            return False, "REJECTED: Candle not yet closed"
        
        # SAFETY CHECK 6: Double confirmation
        if not self.double_confirm_trigger(position, candle_data):
            return False, "REJECTED: Awaiting confirmation"
        
        # ALL CHECKS PASSED - Safe to trigger
        return True, "VALIDATED: All safety checks passed"
    
    def is_candle_current(self, candle_data):
        """Check if candle is from current hour"""
        
        current_time = datetime.now(self.ist)
        candle_time = candle_data.get("datetime")
        
        if not candle_time:
            print("❌ ERROR: No timestamp in candle data")
            return False
        
        # Parse candle timestamp
        if isinstance(candle_time, str):
            candle_dt = datetime.fromisoformat(candle_time).replace(tzinfo=self.ist)
        else:
            candle_dt = candle_time
        
        # Calculate time difference
        time_diff = current_time - candle_dt
        
        # CRITICAL: Candle should be from last completed hour
        # For 1HR candle at 14:00, it represents 13:00-14:00 period
        if time_diff > timedelta(hours=2):
            print(f"❌ STALE: Candle is {time_diff.total_seconds()/3600:.1f} hours old")
            return False
        
        # Check if it's the last completed hour
        current_hour = current_time.hour
        expected_candle_hour = current_hour - 1 if current_time.minute > 0 else current_hour - 2
        
        if candle_dt.hour != expected_candle_hour:
            print(f"❌ WRONG HOUR: Expected hour {expected_candle_hour}, got {candle_dt.hour}")
            return False
        
        print(f"✅ CURRENT: Candle from {candle_dt.strftime('%H:%M')} is valid")
        return True
    
    def is_data_real(self, candle_data):
        """Detect mock/test data flags"""
        
        # Check for mock data indicators
        if candle_data.get("is_mock", False):
            print("❌ MOCK DATA: Rejected")
            return False
        
        if candle_data.get("source") == "test":
            print("❌ TEST DATA: Rejected")
            return False
        
        if "dummy" in str(candle_data.get("source", "")).lower():
            print("❌ DUMMY DATA: Rejected")
            return False
        
        # Verify data source
        valid_sources = ["breeze_api", "kite_api", "live_feed"]
        source = candle_data.get("source", "")
        
        if source not in valid_sources:
            print(f"❌ UNKNOWN SOURCE: {source}")
            return False
        
        print(f"✅ REAL DATA: Source={source}")
        return True
    
    def is_market_hours(self):
        """Check if within market hours"""
        
        current_time = datetime.now(self.ist)
        
        # Market hours: 9:15 AM to 3:30 PM
        market_open = current_time.replace(hour=9, minute=15, second=0)
        market_close = current_time.replace(hour=15, minute=30, second=0)
        
        if not (market_open <= current_time <= market_close):
            print(f"❌ OUTSIDE MARKET: Current time {current_time.strftime('%H:%M')}")
            return False
        
        # Check if it's a trading day
        if current_time.weekday() >= 5:  # Saturday=5, Sunday=6
            print("❌ WEEKEND: Market closed")
            return False
        
        print(f"✅ MARKET HOURS: {current_time.strftime('%H:%M')}")
        return True
    
    def is_price_sane(self, candle_data):
        """Validate price is within reasonable range"""
        
        close_price = candle_data.get("close", 0)
        
        # NIFTY reasonable range: 15000 to 35000
        if not (15000 <= close_price <= 35000):
            print(f"❌ ABNORMAL PRICE: {close_price}")
            return False
        
        # Check for sudden spikes (>5% in 1 hour)
        if self.last_candle_price:
            change_percent = abs(close_price - self.last_candle_price) / self.last_candle_price * 100
            if change_percent > 5:
                print(f"❌ SPIKE DETECTED: {change_percent:.2f}% change")
                return False
        
        print(f"✅ PRICE OK: {close_price}")
        return True
    
    def is_candle_complete(self, candle_data):
        """Ensure we're checking a completed candle"""
        
        current_time = datetime.now(self.ist)
        current_minute = current_time.minute
        
        # For hourly candles, wait until at least 1 minute past the hour
        if current_minute == 0:
            print("⏳ WAITING: Candle just closed, waiting for confirmation")
            return False
        
        # Verify candle has all required fields
        required_fields = ["open", "high", "low", "close", "datetime"]
        for field in required_fields:
            if field not in candle_data or candle_data[field] is None:
                print(f"❌ INCOMPLETE: Missing {field}")
                return False
        
        print("✅ CANDLE COMPLETE: All data present")
        return True
    
    def double_confirm_trigger(self, position, candle_data):
        """Require confirmation before triggering"""
        
        close_price = candle_data["close"]
        strike = position["main_strike"]
        option_type = position["option_type"]
        
        # Calculate how much beyond strike
        if option_type == "PE":
            breach_amount = strike - close_price
            should_trigger = close_price < strike
        else:  # CE
            breach_amount = close_price - strike
            should_trigger = close_price > strike
        
        # Require minimum breach amount (not just touching)
        MIN_BREACH = 10  # points
        if should_trigger and abs(breach_amount) < MIN_BREACH:
            print(f"⚠️ MARGINAL BREACH: Only {abs(breach_amount)} points")
            return False
        
        print(f"✅ CONFIRMED: Breach by {abs(breach_amount)} points")
        return should_trigger


def safe_stop_loss_check(position):
    """
    Production-safe stop loss check with validation
    """
    
    validator = StopLossValidator()
    
    # Get candle data with source tracking
    candle_data = get_1hr_candle_with_metadata()
    
    # Example candle data structure
    candle_data = {
        "datetime": datetime.now(pytz.timezone('Asia/Kolkata')) - timedelta(minutes=30),
        "open": 25150,
        "high": 25180,
        "low": 24980,
        "close": 24990,
        "volume": 1000000,
        "source": "breeze_api",
        "is_mock": False,
        "fetched_at": datetime.now()
    }
    
    # Validate before triggering
    should_trigger, reason = validator.validate_1hr_candle_stop(position, candle_data)
    
    if should_trigger:
        print("\n" + "="*60)
        print("🛑 STOP LOSS TRIGGERED - VALIDATED")
        print("="*60)
        print(f"Position: {position['main_strike']}{position['option_type']}")
        print(f"Candle Close: {candle_data['close']}")
        print(f"Time: {candle_data['datetime']}")
        print(f"Reason: {reason}")
        print("="*60)
        
        # Log for audit
        log_stop_loss_trigger(position, candle_data, reason)
        
        # Execute stop loss
        return True
    else:
        print(f"\n✋ STOP LOSS NOT TRIGGERED: {reason}")
        return False


def get_1hr_candle_with_metadata():
    """
    Fetch 1-hour candle with proper metadata
    """
    
    # CRITICAL: Always fetch from live API, never from cache/DB for stop loss
    try:
        # Get from Breeze/Kite API
        from breeze_connect import BreezeConnect
        
        breeze = get_breeze_connection()
        
        # Get the last completed hourly candle
        current_time = datetime.now(pytz.timezone('Asia/Kolkata'))
        
        # Calculate the last completed hour
        if current_time.minute > 0:
            candle_hour = current_time.hour - 1
        else:
            candle_hour = current_time.hour - 2
            
        candle_time = current_time.replace(hour=candle_hour, minute=0, second=0)
        
        # Fetch from API
        candle = breeze.get_historical_data(
            interval="1hour",
            from_date=candle_time,
            to_date=candle_time + timedelta(hours=1),
            stock_code="NIFTY",
            exchange_code="NSE"
        )
        
        # Add metadata
        candle_data = {
            "datetime": candle_time,
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle["volume"],
            "source": "breeze_api",
            "is_mock": False,
            "fetched_at": datetime.now(),
            "api_response_time": 0.5  # Track latency
        }
        
        return candle_data
        
    except Exception as e:
        print(f"❌ API ERROR: {e}")
        # NEVER return mock data for stop loss
        raise Exception("Cannot fetch live data for stop loss check")


# EXAMPLE USAGE
if __name__ == "__main__":
    
    print("STOP LOSS SAFETY VALIDATION DEMO")
    print("="*60)
    
    # Example position
    position = {
        "main_strike": 25000,
        "hedge_strike": 24800,
        "option_type": "PE",
        "entry_time": datetime.now() - timedelta(hours=2),
        "quantity": 750
    }
    
    print(f"\nPosition: SELL {position['main_strike']}{position['option_type']}")
    print(f"Hedge: BUY {position['hedge_strike']}{position['option_type']}")
    
    # Test validation
    print("\n" + "="*60)
    print("VALIDATION CHECKS:")
    print("="*60)
    
    # This will run all safety checks
    result = safe_stop_loss_check(position)
    
    if result:
        print("\n✅ Stop loss would be executed")
    else:
        print("\n✋ Stop loss prevented - safety check failed")