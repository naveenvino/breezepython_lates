from datetime import datetime, timedelta
from src.services.breeze_ws_manager import BreezeWebSocketManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_1min_candles():
    breeze_manager = BreezeWebSocketManager()
    breeze_service = breeze_manager.breeze
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Fetch 1-minute data from 13:00 to 13:20
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
        
        # Filter for 13:10 to 13:15 candles
        target_candles = []
        for candle in data_list:
            if 'datetime' in candle:
                candle_time = candle['datetime']
                # Check if it's between 13:10 and 13:15
                if "13:10" in str(candle_time) or "13:11" in str(candle_time) or \
                   "13:12" in str(candle_time) or "13:13" in str(candle_time) or \
                   "13:14" in str(candle_time) or "13:15" in str(candle_time):
                    target_candles.append(candle)
        
        print("\n=== NIFTY 1-Minute Candles from 13:10 to 13:15 ===\n")
        for candle in sorted(target_candles, key=lambda x: x['datetime']):
            time = candle['datetime']
            open_price = candle.get('open', 0)
            high = candle.get('high', 0)
            low = candle.get('low', 0)
            close = candle.get('close', 0)
            print(f"Time: {time}")
            print(f"  Open:  {open_price}")
            print(f"  High:  {high}")
            print(f"  Low:   {low}")
            print(f"  Close: {close}")
            print("-" * 40)
        
        # Find specific 13:10 candle (runs 13:10:00 to 13:11:00)
        for candle in target_candles:
            if "13:10:00" in str(candle['datetime']):
                print(f"\n=== 13:10 Candle (closes at 13:11) ===")
                print(f"Close: {candle.get('close', 0)}")
                
        # Find specific 13:14 candle (runs 13:14:00 to 13:15:00, represents close at 13:15)
        for candle in target_candles:
            if "13:14:00" in str(candle['datetime']):
                print(f"\n=== 13:14 Candle (closes at 13:15) ===")
                print(f"Close: {candle.get('close', 0)}")
    else:
        print("Failed to fetch data")
        print(result)

if __name__ == "__main__":
    check_1min_candles()