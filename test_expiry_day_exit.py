import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from src.services.expiry_management_service import get_expiry_service

def test_expiry_day_exit():
    """Test the expiry day exit functionality"""
    expiry_service = get_expiry_service()
    
    print("Testing Expiry Day Exit Calculation...")
    print("-" * 50)
    
    test_cases = [
        ("Monday Entry", datetime(2025, 1, 6, 10, 0)),   # Monday
        ("Tuesday Entry", datetime(2025, 1, 7, 10, 0)),  # Tuesday  
        ("Wednesday Entry", datetime(2025, 1, 8, 10, 0)), # Wednesday
        ("Thursday Entry", datetime(2025, 1, 9, 10, 0)),  # Thursday
        ("Friday Entry", datetime(2025, 1, 10, 10, 0))    # Friday
    ]
    
    for description, entry_date in test_cases:
        print(f"\n{description}: {entry_date.strftime('%A, %B %d, %Y')}")
        
        # Test T+0 (Expiry Day)
        exit_date, display = expiry_service.calculate_exit_date(entry_date, 0)
        print(f"  Expiry Day Exit: {display}")
        print(f"  Exit Date: {exit_date.strftime('%A, %B %d, %Y')}")
        
        # Test T+2 for comparison
        exit_date_t2, display_t2 = expiry_service.calculate_exit_date(entry_date, 2)
        print(f"  T+2 Exit: {display_t2}")
        print(f"  Exit Date: {exit_date_t2.strftime('%A, %B %d, %Y')}")
    
    print("\n" + "=" * 50)
    print("Expiry Day Exit Calculation Details:")
    print("-" * 50)
    
    # Show how expiry day is determined
    monday_entry = datetime(2025, 1, 6, 10, 0)
    wednesday_entry = datetime(2025, 1, 8, 10, 0)
    
    print("\nMonday Entry (Jan 6, 2025):")
    print("  - Current week expiry available (Monday/Tuesday only)")
    print("  - If config says 'current': Exit on Jan 7 (Tuesday)")
    print("  - If config says 'next': Exit on Jan 14 (Next Tuesday)")
    
    exit_date, display = expiry_service.calculate_exit_date(monday_entry, 0)
    print(f"  - Actual: {display}")
    
    print("\nWednesday Entry (Jan 8, 2025):")
    print("  - Current week expiry NOT available (Wed-Fri)")
    print("  - Always uses next week expiry: Jan 14 (Next Tuesday)")
    
    exit_date, display = expiry_service.calculate_exit_date(wednesday_entry, 0)
    print(f"  - Actual: {display}")
    
    print("\n" + "=" * 50)
    print("TEST COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    test_expiry_day_exit()