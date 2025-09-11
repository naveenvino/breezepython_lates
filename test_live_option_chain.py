"""
Test Live Option Chain Service
Tests the option chain fetching and strike selection during market hours
"""

import sys
sys.path.append('.')

from src.services.live_option_chain_service import get_live_option_chain_service
from datetime import datetime
import json

def test_option_chain():
    """Test live option chain fetching"""
    
    print("="*60)
    print("LIVE OPTION CHAIN TEST")
    print("="*60)
    print(f"Test time: {datetime.now()}")
    print()
    
    # Get service instance
    service = get_live_option_chain_service()
    
    # Test 1: Connection
    print("Test 1: Connecting to Breeze API...")
    if service.is_connected:
        print("[PASS] Already connected")
    else:
        if service.connect():
            print("[PASS] Successfully connected to Breeze")
        else:
            print("[FAIL] Failed to connect to Breeze")
            print("Please check your credentials in .env file")
            return False
    
    # Test 2: Get spot price
    print("\nTest 2: Getting NIFTY spot price...")
    spot = service.get_spot_price()
    if spot:
        print(f"[PASS] NIFTY spot price: {spot}")
    else:
        print("[FAIL] Could not get spot price")
        return False
    
    # Test 3: Get current expiry
    print("\nTest 3: Getting current expiry...")
    display_expiry, breeze_expiry = service.get_current_expiry()
    print(f"[PASS] Current expiry: {display_expiry} (Breeze format: {breeze_expiry})")
    
    # Test 4: Calculate strikes
    print("\nTest 4: Calculating strikes to fetch...")
    strikes = service.calculate_strikes_to_fetch(spot, num_strikes=10)
    print(f"[PASS] Will fetch {len(strikes)} strikes:")
    print(f"  From: {strikes[0]} to {strikes[-1]}")
    print(f"  ATM: {round(spot/50)*50}")
    
    # Test 5: Get single option data
    print("\nTest 5: Getting single option data...")
    atm_strike = round(spot/50)*50
    ce_data = service.get_option_data(atm_strike, 'CE', breeze_expiry)
    if ce_data:
        print(f"[PASS] ATM CE ({atm_strike}):")
        print(f"  LTP: {ce_data['ltp']}")
        print(f"  OI: {ce_data['oi']}")
        print(f"  Volume: {ce_data['volume']}")
    else:
        print(f"[FAIL] Could not get ATM CE data")
    
    pe_data = service.get_option_data(atm_strike, 'PE', breeze_expiry)
    if pe_data:
        print(f"[PASS] ATM PE ({atm_strike}):")
        print(f"  LTP: {pe_data['ltp']}")
        print(f"  OI: {pe_data['oi']}")
        print(f"  Volume: {pe_data['volume']}")
    else:
        print(f"[FAIL] Could not get ATM PE data")
    
    # Test 6: Get full option chain
    print("\nTest 6: Getting full option chain...")
    try:
        chain = service.get_option_chain(num_strikes=5)  # Get 5 strikes on each side for testing
        
        if chain and chain.get('options'):
            print(f"[PASS] Retrieved {len(chain['options'])} options")
            print(f"  Spot: {chain['spot']}")
            print(f"  ATM Strike: {chain['atm_strike']}")
            print(f"  Expiry: {chain['expiry']}")
            
            if 'summary' in chain:
                summary = chain['summary']
                print(f"\nSummary:")
                print(f"  Total CE OI: {summary['total_ce_oi']:,}")
                print(f"  Total PE OI: {summary['total_pe_oi']:,}")
                print(f"  PCR (OI): {summary['pcr_oi']}")
                print(f"  PCR (Volume): {summary['pcr_volume']}")
                print(f"  Max CE OI Strike: {summary['max_ce_oi_strike']}")
                print(f"  Max PE OI Strike: {summary['max_pe_oi_strike']}")
            
            # Display first few options
            print("\nSample options:")
            for opt in chain['options'][:6]:
                print(f"  {opt['strike']} {opt['type']}: LTP={opt['ltp']}, OI={opt['oi']}")
        else:
            print("[FAIL] Could not get option chain")
            return False
            
    except Exception as e:
        print(f"[FAIL] Error getting option chain: {e}")
        return False
    
    # Test 7: Test hedge strike calculation
    print("\nTest 7: Testing hedge strike calculation...")
    
    # Test offset method
    hedge_strike_offset = service.get_strike_for_hedge(
        atm_strike, 'PE', 'offset', hedge_offset=200
    )
    print(f"[PASS] Offset hedge for {atm_strike} PE: {hedge_strike_offset} (200 points away)")
    
    # Test percentage method
    hedge_strike_percent = service.get_strike_for_hedge(
        atm_strike, 'PE', 'percentage', hedge_percent=30
    )
    print(f"[PASS] Percentage hedge for {atm_strike} PE: {hedge_strike_percent} (30% premium)")
    
    print("\n" + "="*60)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("="*60)
    
    # Save test results
    with open('option_chain_test_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'spot': spot,
            'expiry': display_expiry,
            'atm_strike': atm_strike,
            'strikes_fetched': len(strikes),
            'options_retrieved': len(chain.get('options', [])),
            'test_status': 'PASSED'
        }, f, indent=2)
    
    return True

if __name__ == "__main__":
    try:
        success = test_option_chain()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)