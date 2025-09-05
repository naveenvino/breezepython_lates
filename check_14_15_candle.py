from datetime import datetime
from src.services.breeze_ws_manager import BreezeWebSocketManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_14_15_candle():
    breeze_manager = BreezeWebSocketManager()
    breeze_service = breeze_manager.breeze
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Fetch 1-minute data
    result = breeze_service.get_historical_data(
        interval="1minute",
        from_date=today,
        to_date=today,
        stock_code="NIFTY",
        exchange_code="NSE",
        product_type="cash"
    )
    
    if result and result.get('Success'):
        data_list = result.get('Success', [])
        
        # Look for candles around 14:15
        print("\n=== NIFTY 1-Minute Candles around 14:15 ===\n")
        for candle in data_list:
            if 'datetime' in candle:
                candle_time = str(candle['datetime'])
                # Check candles from 14:10 to 14:20
                if any(time in candle_time for time in ["14:10", "14:11", "14:12", "14:13", "14:14", "14:15", "14:16", "14:17", "14:18", "14:19", "14:20"]):
                    print(f"Time: {candle['datetime']}")
                    print(f"  Open:  {candle.get('open', 0)}")
                    print(f"  High:  {candle.get('high', 0)}")
                    print(f"  Low:   {candle.get('low', 0)}")
                    print(f"  Close: {candle.get('close', 0)}")
                    print("-" * 40)
        
        # Specifically look for 14:14 candle
        print("\n=== Looking for 14:14 candle (represents 14:15 close) ===")
        for candle in data_list:
            if 'datetime' in candle:
                if "14:14:00" in str(candle['datetime']):
                    print(f"14:14 Candle (runs 14:14:00 to 14:15:00):")
                    print(f"  Close: {candle.get('close', 0)}")
                    return candle.get('close', 0)
        
        # Also check 14:15 candle  
        print("\n=== Also checking 14:15 candle ===")
        for candle in data_list:
            if 'datetime' in candle:
                if "14:15:00" in str(candle['datetime']):
                    print(f"14:15 Candle (runs 14:15:00 to 14:16:00):")
                    print(f"  Close: {candle.get('close', 0)}")
    else:
        print("Failed to fetch data")
        print(result)

if __name__ == "__main__":
    check_14_15_candle()