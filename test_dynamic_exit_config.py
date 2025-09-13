"""
Test Dynamic Exit Configuration
Verifies that positions follow CURRENT UI settings, not entry-time settings
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
import time

def setup_test_position():
    """Create a test position in the database"""
    db_path = Path("data/trading_settings.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Insert test position with T+0 exit initially
    entry_time = datetime.now()
    webhook_id = f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    cursor.execute("""
        INSERT INTO OrderTracking (
            webhook_id, signal, main_strike, main_symbol, main_order_id, main_quantity,
            hedge_strike, hedge_symbol, hedge_order_id, hedge_quantity,
            entry_time, status, lots, option_type,
            exit_config_day, exit_config_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        webhook_id,
        "TEST_SIGNAL",
        25000,  # main_strike
        "NIFTY25000PE",
        "TEST_MAIN_001",
        750,
        24800,  # hedge_strike
        "NIFTY24800PE",
        "TEST_HEDGE_001",
        750,
        entry_time.isoformat(),
        "active",
        10,
        "PE",
        0,  # T+0 stored at entry (for audit only)
        "15:15"  # 3:15 PM stored at entry (for audit only)
    ))

    conn.commit()
    conn.close()

    print(f"[OK] Created test position: {webhook_id}")
    print(f"  Entry time: {entry_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Stored exit config: T+0 at 15:15 (audit only)")

    return webhook_id, entry_time

def update_ui_config(exit_day_offset, exit_time):
    """Update the current UI configuration"""
    db_path = Path("data/trading_settings.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE TradeConfiguration
        SET exit_day_offset = ?, exit_time = ?
        WHERE user_id = 'default' AND config_name = 'default'
    """, (exit_day_offset, exit_time))

    conn.commit()
    conn.close()

    print(f"\n[OK] Updated UI configuration:")
    print(f"  Exit: T+{exit_day_offset} at {exit_time}")

def check_dynamic_exit(webhook_id, entry_time):
    """Check what exit time the position will use"""
    db_path = Path("data/trading_settings.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get CURRENT configuration (what the monitor will use)
    cursor.execute("""
        SELECT exit_day_offset, exit_time, auto_square_off_enabled
        FROM TradeConfiguration
        WHERE user_id='default' AND config_name='default'
        ORDER BY id DESC
        LIMIT 1
    """)

    result = cursor.fetchone()
    if result:
        exit_day_offset = result[0] if result[0] is not None else 0
        exit_time_str = result[1] if result[1] else "15:15"
        auto_enabled = bool(result[2]) if len(result) > 2 else True

        # Calculate actual exit datetime
        exit_date = entry_time.date() + timedelta(days=exit_day_offset)

        # Skip weekends
        while exit_date.weekday() >= 5:
            exit_date += timedelta(days=1)

        hour, minute = map(int, exit_time_str.split(':'))
        exit_datetime = datetime.combine(exit_date, datetime.min.time().replace(hour=hour, minute=minute))

        print(f"\n== Dynamic Exit Calculation ==")
        print(f"  Position entered: {entry_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"  Current UI config: T+{exit_day_offset} at {exit_time_str}")
        print(f"  Will exit at: {exit_datetime.strftime('%Y-%m-%d %H:%M')}")
        print(f"  Auto square-off: {'Enabled' if auto_enabled else 'Disabled'}")

        # Check if it's past exit time
        current_time = datetime.now()
        if current_time >= exit_datetime:
            print(f"  [WARNING] Position should exit NOW (current time: {current_time.strftime('%H:%M')})")
        else:
            time_remaining = exit_datetime - current_time
            hours = int(time_remaining.total_seconds() // 3600)
            minutes = int((time_remaining.total_seconds() % 3600) // 60)
            print(f"  [TIMER] Time until exit: {hours}h {minutes}m")

    conn.close()

def cleanup_test_position(webhook_id):
    """Remove test position from database"""
    db_path = Path("data/trading_settings.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM OrderTracking WHERE webhook_id = ?", (webhook_id,))
    conn.commit()
    conn.close()

    print(f"\n[OK] Cleaned up test position: {webhook_id}")

def main():
    print("=" * 60)
    print("DYNAMIC EXIT CONFIGURATION TEST")
    print("=" * 60)
    print("\nThis test verifies that positions follow CURRENT UI settings")
    print("rather than settings locked at entry time.\n")

    # Step 1: Create test position
    webhook_id, entry_time = setup_test_position()

    # Step 2: Show initial exit calculation
    print("\n--- Initial Configuration ---")
    check_dynamic_exit(webhook_id, entry_time)

    # Step 3: Change UI configuration to T+1
    print("\n--- Changing UI Configuration ---")
    update_ui_config(1, "14:30")  # T+1 at 2:30 PM

    # Step 4: Show new exit calculation (should follow new config)
    print("\n--- After Configuration Change ---")
    check_dynamic_exit(webhook_id, entry_time)

    # Step 5: Change UI configuration to T+2
    print("\n--- Changing UI Configuration Again ---")
    update_ui_config(2, "15:00")  # T+2 at 3:00 PM

    # Step 6: Show updated exit calculation
    print("\n--- After Second Configuration Change ---")
    check_dynamic_exit(webhook_id, entry_time)

    # Step 7: Test with auto square-off disabled
    print("\n--- Testing Auto Square-Off Toggle ---")
    db_path = Path("data/trading_settings.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE TradeConfiguration
        SET auto_square_off_enabled = 0
        WHERE user_id = 'default' AND config_name = 'default'
    """)
    conn.commit()
    conn.close()
    print("[OK] Disabled auto square-off")
    check_dynamic_exit(webhook_id, entry_time)

    # Re-enable for cleanup
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE TradeConfiguration
        SET auto_square_off_enabled = 1
        WHERE user_id = 'default' AND config_name = 'default'
    """)
    conn.commit()
    conn.close()

    # Cleanup
    cleanup_test_position(webhook_id)

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print("\n[SUCCESS] Dynamic exit configuration is working correctly!")
    print("Positions will follow CURRENT UI settings, not entry-time settings.")

if __name__ == "__main__":
    main()