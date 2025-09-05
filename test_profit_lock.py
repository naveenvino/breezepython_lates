"""
Test Profit Lock Stop Loss Implementation
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_profit_lock():
    """Test profit lock stop loss with mock position"""
    
    print("=" * 60)
    print("TESTING PROFIT LOCK STOP LOSS")
    print("=" * 60)
    
    # Create a mock position (you would have a real position in production)
    # For testing, we'll use the monitor-all endpoint
    
    print("\n1. Checking current positions...")
    response = requests.get(f"{BASE_URL}/live/stoploss/monitor-all")
    if response.ok:
        data = response.json()
        print(f"Status: {data.get('status')}")
        print(f"Positions monitored: {data.get('positions_monitored', 0)}")
        
        if data.get('positions'):
            for pos in data['positions']:
                print(f"\nPosition {pos['position_id']}:")
                print(f"  Signal: {pos['signal_type']}")
                print(f"  Strike: {pos['main_strike']}")
                print(f"  P&L: Rs.{pos['current_pnl']:.2f} ({pos['pnl_percent']}%)")
                print(f"  Profit Locked: {pos['profit_locked']}")
                
                # Check stop loss status
                for sl_type, sl_status in pos['stop_loss_status'].items():
                    if sl_status['enabled']:
                        print(f"  {sl_type}: {'TRIGGERED' if sl_status['triggered'] else 'Active'}")
                        if sl_type == 'profit_lock':
                            params = sl_status['params']
                            print(f"    Target: {params.get('target_percent')}%")
                            print(f"    Lock: {params.get('lock_percent')}%")
    else:
        print(f"Error: {response.status_code}")
    
    print("\n" + "=" * 60)
    print("PROFIT LOCK TEST SCENARIOS")
    print("=" * 60)
    
    # Simulate different price scenarios
    test_scenarios = [
        {
            "name": "Initial Entry",
            "main_price": 100,
            "hedge_price": 30,
            "expected": "No trigger (0% profit)"
        },
        {
            "name": "Small Profit (5%)",
            "main_price": 95,
            "hedge_price": 31,
            "expected": "No trigger (below 10% target)"
        },
        {
            "name": "Hit Target (10%)",
            "main_price": 90,
            "hedge_price": 32,
            "expected": "Profit lock activated, monitoring starts"
        },
        {
            "name": "Profit Falls to 7%",
            "main_price": 93,
            "hedge_price": 32,
            "expected": "Still OK (above 5% lock level)"
        },
        {
            "name": "Profit Falls Below Lock (4%)",
            "main_price": 96,
            "hedge_price": 32,
            "expected": "STOP LOSS TRIGGERED!"
        }
    ]
    
    print("\nSimulated Test Scenarios:")
    print("-" * 40)
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n{i}. {scenario['name']}:")
        print(f"   Main: Rs.{scenario['main_price']}, Hedge: Rs.{scenario['hedge_price']}")
        
        # Calculate profit
        main_entry = 100 * 10 * 75  # Entry at 100, 10 lots
        main_current = scenario['main_price'] * 10 * 75
        main_profit = main_entry - main_current
        
        hedge_entry = 30 * 3 * 75  # Hedge at 30, 3 lots
        hedge_current = scenario['hedge_price'] * 3 * 75
        hedge_profit = hedge_current - hedge_entry
        
        net_profit = main_profit + hedge_profit
        profit_percent = (net_profit / main_entry) * 100
        
        print(f"   Net P&L: Rs.{net_profit:.2f} ({profit_percent:.2f}%)")
        print(f"   Expected: {scenario['expected']}")
    
    print("\n" + "=" * 60)
    print("HOW PROFIT LOCK WORKS:")
    print("=" * 60)
    print("""
1. CONFIGURATION (User Settings):
   - Target Profit: 10% (When to activate monitoring)
   - Lock Profit: 5% (Minimum profit to maintain)

2. MONITORING PHASES:
   
   Phase 1 - Building Profit (0% to 10%):
   ✓ System watches position P&L
   ✓ No stop loss based on profit yet
   ✓ Only strike-based stop loss active
   
   Phase 2 - Target Reached (10%+ profit):
   [TARGET HIT] Profit lock ACTIVATED!
   ✓ System marks position as "profit locked"
   ✓ Now monitors to maintain minimum 5% profit
   
   Phase 3 - Protecting Profits:
   ✓ If profit stays above 5%: Position continues
   ✓ If profit falls below 5%: STOP LOSS TRIGGERED!
   
3. EXAMPLE TRADE:
   - Entry: Sold 24900 PUT at Rs.100
   - Target hit: Premium drops to Rs.90 (10% profit)
   - Safe zone: As long as premium stays below Rs.95 (5% profit)
   - Trigger: If premium rises above Rs.95, exit immediately

4. WITH HEDGE INCLUDED:
   - Main leg profit: Rs.7,500 (Sold PUT)
   - Hedge leg loss: -Rs.2,250 (Bought PUT)
   - Net profit: Rs.5,250 (7% of entry value)
   - System uses NET profit for all calculations
    """)
    
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    test_profit_lock()