"""
Query the OrderTracking table to show current orders
"""
import sqlite3
from datetime import datetime

def query_order_tracking():
    conn = sqlite3.connect('data/trading_settings.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all orders sorted by entry time
    cursor.execute("""
        SELECT * FROM OrderTracking 
        ORDER BY entry_time DESC
    """)
    
    rows = cursor.fetchall()
    
    print("=" * 120)
    print("ORDER TRACKING TABLE - ALL POSITIONS")
    print("=" * 120)
    
    if not rows:
        print("No orders found in the database")
    else:
        for i, row in enumerate(rows):
            print(f"\n[Order #{i+1}] - Webhook ID: {row['webhook_id']}")
            print("-" * 80)
            print(f"  Signal:        {row['signal']}")
            print(f"  Status:        {row['status']}")
            print(f"  Entry Time:    {row['entry_time']}")
            print(f"  Exit Time:     {row['exit_time'] or 'Still Open'}")
            print()
            print(f"  MAIN POSITION:")
            print(f"    Strike:      {row['main_strike']}")
            print(f"    Symbol:      {row['main_symbol']}")
            print(f"    Order ID:    {row['main_order_id']}")
            print(f"    Quantity:    {row['main_quantity']}")
            print(f"    Type:        {row['option_type']}")
            print()
            print(f"  HEDGE POSITION:")
            print(f"    Strike:      {row['hedge_strike']}")
            print(f"    Symbol:      {row['hedge_symbol']}")
            print(f"    Order ID:    {row['hedge_order_id']}")
            print(f"    Quantity:    {row['hedge_quantity']}")
            print()
            print(f"  TRADE INFO:")
            print(f"    Lots:        {row['lots']}")
            print(f"    PnL:         {row['pnl'] or 'N/A'}")
            print(f"    Exit Reason: {row['exit_reason'] or 'N/A'}")
    
    # Show summary
    cursor.execute("SELECT status, COUNT(*) as count FROM OrderTracking GROUP BY status")
    summary = cursor.fetchall()
    
    print("\n" + "=" * 120)
    print("SUMMARY BY STATUS:")
    print("-" * 40)
    for row in summary:
        print(f"  {row['status']:15} : {row['count']} position(s)")
    
    # Show latest open position if any
    cursor.execute("""
        SELECT * FROM OrderTracking 
        WHERE status = 'open' 
        ORDER BY entry_time DESC 
        LIMIT 1
    """)
    latest_open = cursor.fetchone()
    
    if latest_open:
        print("\n" + "=" * 120)
        print("LATEST OPEN POSITION (Ready for Exit):")
        print("-" * 40)
        print(f"  Webhook ID:    {latest_open['webhook_id']}")
        print(f"  Signal:        {latest_open['signal']}")
        print(f"  Main Strike:   {latest_open['main_strike']} {latest_open['option_type']}")
        print(f"  Hedge Strike:  {latest_open['hedge_strike']} {latest_open['option_type']}")
        print(f"  Entry Time:    {latest_open['entry_time']}")
        print("\n  To exit this position, send webhook with:")
        print(f'    {{"signal": "{latest_open["signal"]}", "strike": {latest_open["main_strike"]}, "type": "{latest_open["option_type"]}", "action": "Exit"}}')
    
    conn.close()
    print("\n" + "=" * 120)

if __name__ == "__main__":
    query_order_tracking()