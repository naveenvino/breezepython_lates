"""
Test Kite Option Chain Fetching
"""
import os
from dotenv import load_dotenv
from kiteconnect import KiteConnect
from datetime import datetime, timedelta
import pandas as pd

load_dotenv()

api_key = os.getenv('KITE_API_KEY')
access_token = os.getenv('KITE_ACCESS_TOKEN')

print("Testing Kite Option Chain")
print("=" * 50)

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

# Test 1: Get NIFTY spot price
print("\n1. Testing NIFTY Spot Price:")
try:
    quote = kite.quote(["NSE:NIFTY 50"])
    spot_price = quote["NSE:NIFTY 50"]["last_price"]
    print(f"   NIFTY Spot: {spot_price}")
    atm_strike = round(spot_price / 50) * 50
    print(f"   ATM Strike: {atm_strike}")
except Exception as e:
    print(f"   Error: {e}")
    spot_price = 25000
    atm_strike = 25000

# Test 2: Get instruments for NFO
print("\n2. Fetching NFO Instruments:")
try:
    instruments = kite.instruments("NFO")
    df = pd.DataFrame(instruments)
    print(f"   Total NFO instruments: {len(df)}")
    
    # Filter NIFTY options for current week
    today = datetime.now()
    # Tuesday is weekday 1
    days_until_tuesday = (1 - today.weekday()) % 7
    if days_until_tuesday == 0 and today.hour >= 15:
        days_until_tuesday = 7
    next_tuesday = today + timedelta(days=days_until_tuesday)
    
    nifty_options = df[
        (df['name'] == 'NIFTY') &
        (df['instrument_type'].isin(['CE', 'PE'])) &
        (df['expiry'] == next_tuesday.date())
    ]
    
    print(f"   NIFTY options for {next_tuesday.date()}: {len(nifty_options)}")
    
    # Check specific strikes around ATM
    strikes_to_check = [atm_strike - 100, atm_strike - 50, atm_strike, atm_strike + 50, atm_strike + 100]
    
    for strike in strikes_to_check:
        ce_options = nifty_options[
            (nifty_options['strike'] == strike) &
            (nifty_options['instrument_type'] == 'CE')
        ]
        pe_options = nifty_options[
            (nifty_options['strike'] == strike) &
            (nifty_options['instrument_type'] == 'PE')
        ]
        
        if not ce_options.empty:
            ce_symbol = ce_options.iloc[0]['tradingsymbol']
            ce_token = ce_options.iloc[0]['instrument_token']
            print(f"   {strike} CE: {ce_symbol} (Token: {ce_token})")
        
        if not pe_options.empty:
            pe_symbol = pe_options.iloc[0]['tradingsymbol']
            pe_token = pe_options.iloc[0]['instrument_token']
            print(f"   {strike} PE: {pe_symbol} (Token: {pe_token})")
    
    # Test 3: Get quotes for these options
    print("\n3. Fetching Option Quotes:")
    
    test_strikes = nifty_options[
        nifty_options['strike'].isin([atm_strike - 50, atm_strike, atm_strike + 50])
    ]
    
    if not test_strikes.empty:
        tokens = test_strikes['instrument_token'].tolist()[:6]  # Get up to 6 options
        
        try:
            quotes = kite.quote(tokens)
            
            for token, quote_data in quotes.items():
                option_info = test_strikes[test_strikes['instrument_token'] == token].iloc[0]
                symbol = option_info['tradingsymbol']
                strike = option_info['strike']
                option_type = option_info['instrument_type']
                
                ltp = quote_data.get('last_price', 0)
                volume = quote_data.get('volume', 0)
                oi = quote_data.get('oi', 0)
                
                print(f"   {strike} {option_type}: LTP={ltp}, Volume={volume}, OI={oi}")
                
        except Exception as e:
            print(f"   Error fetching quotes: {e}")
    else:
        print("   No test strikes found")
        
except Exception as e:
    print(f"   Error fetching instruments: {e}")

print("\n" + "=" * 50)
print("Test Complete")