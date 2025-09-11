"""
Test expiry date calculation logic
"""
from datetime import datetime, timedelta
from src.services.expiry_management_service import ExpiryManagementService

# Test date: September 11, 2025 (Thursday)
test_date = datetime(2025, 9, 11, 14, 30)  # Thursday 2:30 PM

print(f"Test Date: {test_date.strftime('%A, %B %d, %Y')}")
print(f"Weekday: {test_date.weekday()} (0=Monday, 1=Tuesday, 4=Thursday)")
print("=" * 60)

# Initialize service
service = ExpiryManagementService()

# Get current week expiry
current_week = service.get_current_week_expiry(test_date)
print(f"Current Week Expiry: {current_week.strftime('%A, %B %d, %Y')}")

# Get next week expiry
next_week = service.get_next_week_expiry(test_date)
print(f"Next Week Expiry: {next_week.strftime('%A, %B %d, %Y')}")

print("\n" + "=" * 60)
print("DEBUGGING THE LOGIC:")
print("=" * 60)

# Manual calculation to show the problem
days_ahead = 1 - test_date.weekday()  # Tuesday is 1, Thursday is 4
print(f"days_ahead = 1 - {test_date.weekday()} = {days_ahead}")

if days_ahead <= 0:
    print(f"Since days_ahead ({days_ahead}) <= 0, adding 7 days")
    days_ahead += 7
    print(f"New days_ahead = {days_ahead}")

calculated_tuesday = test_date + timedelta(days=days_ahead)
print(f"Calculated Tuesday: {calculated_tuesday.strftime('%A, %B %d, %Y')}")

print("\n" + "=" * 60)
print("CORRECT LOGIC SHOULD BE:")
print("=" * 60)

# For current week - we want Tuesday of THIS week (Sep 9)
current_weekday = test_date.weekday()  # 4 for Thursday
days_since_monday = current_weekday  # 4
monday_this_week = test_date - timedelta(days=days_since_monday)
tuesday_this_week = monday_this_week + timedelta(days=1)
print(f"Monday of this week: {monday_this_week.strftime('%A, %B %d, %Y')}")
print(f"Tuesday of this week: {tuesday_this_week.strftime('%A, %B %d, %Y')}")

# For next week - add 7 days to this week's Tuesday
next_tuesday = tuesday_this_week + timedelta(days=7)
print(f"Next week Tuesday: {next_tuesday.strftime('%A, %B %d, %Y')}")

print("\n" + "=" * 60)
print("CONFIGURATION CHECK:")
print("=" * 60)

# Check what config says for Thursday
import json
try:
    with open("expiry_weekday_config.json", 'r') as f:
        config = json.load(f)
        thursday_config = config.get('thursday', 'next')
        print(f"Thursday configuration: {thursday_config}")
        
        if thursday_config == 'next':
            print(f"Should use: Next week Tuesday = {next_tuesday.strftime('%B %d')}")
        elif thursday_config == 'current':
            print(f"Should use: Current week Tuesday = {tuesday_this_week.strftime('%B %d')}")
except Exception as e:
    print(f"Error loading config: {e}")