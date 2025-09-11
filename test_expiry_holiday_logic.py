"""
Test expiry date calculation with holiday scenarios
"""
from datetime import datetime, timedelta
from src.services.expiry_management_service import ExpiryManagementService

# Initialize service
service = ExpiryManagementService()

# Test 1: Regular week (no holidays)
print("=" * 60)
print("TEST 1: Regular Week (September 11, 2025 - Thursday)")
print("=" * 60)
test_date = datetime(2025, 9, 11, 14, 30)  # Thursday
print(f"Test Date: {test_date.strftime('%A, %B %d, %Y')}")
current_week = service.get_current_week_expiry(test_date)
next_week = service.get_next_week_expiry(test_date)
print(f"Current Week Expiry: {current_week.strftime('%A, %B %d, %Y')}")
print(f"Next Week Expiry: {next_week.strftime('%A, %B %d, %Y')}")

# Test 2: Week with holiday on Tuesday (August 2025)
print("\n" + "=" * 60)
print("TEST 2: Holiday Week (August 14, 2025 - Thursday)")
print("Note: August 15 (Friday) is Independence Day")
print("=" * 60)
test_date = datetime(2025, 8, 14, 14, 30)  # Thursday before Independence Day
print(f"Test Date: {test_date.strftime('%A, %B %d, %Y')}")
current_week = service.get_current_week_expiry(test_date)
next_week = service.get_next_week_expiry(test_date)
print(f"Current Week Expiry: {current_week.strftime('%A, %B %d, %Y')}")
print(f"Next Week Expiry: {next_week.strftime('%A, %B %d, %Y')}")

# Test 3: Manually add a Tuesday holiday to test adjustment
print("\n" + "=" * 60)
print("TEST 3: Simulating Tuesday Holiday")
print("=" * 60)

# Temporarily add September 16, 2025 (Tuesday) as a holiday
test_holiday = datetime(2025, 9, 16)
service.holidays.add(test_holiday.date())
print(f"Added holiday: {test_holiday.strftime('%A, %B %d, %Y')}")

test_date = datetime(2025, 9, 11, 14, 30)  # Thursday
print(f"Test Date: {test_date.strftime('%A, %B %d, %Y')}")
next_week = service.get_next_week_expiry(test_date)
print(f"Next Week Expiry (with Tuesday holiday): {next_week.strftime('%A, %B %d, %Y')}")

# Remove the test holiday
service.holidays.remove(test_holiday.date())

# Test 4: Check actual expiry dates for known holiday weeks
print("\n" + "=" * 60)
print("TEST 4: Checking All Days of a Week")
print("=" * 60)

test_date = datetime(2025, 9, 11, 14, 30)  # Thursday
monday_next_week = test_date - timedelta(days=test_date.weekday()) + timedelta(days=7)

print(f"Checking next week starting {monday_next_week.strftime('%B %d, %Y')}:")
for i in range(5):
    day = monday_next_week + timedelta(days=i)
    is_trading = service.is_trading_day(day)
    day_name = day.strftime('%A')
    status = "[Trading Day]" if is_trading else "[Holiday/Weekend]"
    print(f"  {day_name}, {day.strftime('%B %d')}: {status}")
    
print(f"\nCalculated Next Week Expiry: {service.get_next_week_expiry(test_date).strftime('%A, %B %d, %Y')}")

# Test 5: Week with Republic Day holiday
print("\n" + "=" * 60)
print("TEST 5: Republic Day Week (January 23, 2025 - Thursday)")
print("Note: January 26 (Sunday) is Republic Day - no market impact")
print("=" * 60)
test_date = datetime(2025, 1, 23, 14, 30)  # Thursday
print(f"Test Date: {test_date.strftime('%A, %B %d, %Y')}")
current_week = service.get_current_week_expiry(test_date)
next_week = service.get_next_week_expiry(test_date)
print(f"Current Week Expiry: {current_week.strftime('%A, %B %d, %Y')}")
print(f"Next Week Expiry: {next_week.strftime('%A, %B %d, %Y')}")

print("\n" + "=" * 60)
print("SUMMARY:")
print("=" * 60)
print("The expiry logic now:")
print("1. Checks each day (Mon-Fri) of the target week")
print("2. Prefers Tuesday as the default expiry day")
print("3. If Tuesday is a holiday, finds the next trading day in that week")
print("4. Handles NSE holidays properly for adjusted expiry dates")