"""
Test script for stop-loss alert functionality
"""

import asyncio
import aiohttp
import json
import time

API_URL = "http://localhost:8000"

async def test_stoploss_alerts():
    """Test different stop-loss alert levels"""
    
    test_cases = [
        {
            'level': 'warning',
            'title': 'STOP LOSS WARNING TEST',
            'message': 'Only 25 pts to SL. NIFTY at 24975.00, Strike 25000 PE.',
            'data': {
                'strike': 25000,
                'optionType': 'PE',
                'currentSpot': 24975.00,
                'distance': -25,
                'signalType': 'S1'
            }
        },
        {
            'level': 'breach',
            'title': 'STOP LOSS BREACH TEST!',
            'message': 'NIFTY at 24995.00, Strike 25000 PE breached. Manual exit recommended.',
            'data': {
                'strike': 25000,
                'optionType': 'PE',
                'currentSpot': 24995.00,
                'distance': -5,
                'signalType': 'S1'
            }
        },
        {
            'level': 'recovery',
            'title': 'Position Recovered TEST',
            'message': 'Position back to safe zone. 150 pts from SL.',
            'data': {
                'strike': 25000,
                'optionType': 'PE',
                'currentSpot': 25150.00,
                'distance': 150,
                'signalType': 'S1'
            }
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        print("=" * 60)
        print("Testing Stop-Loss Alert System")
        print("=" * 60)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\nTest {i}: {test_case['level'].upper()} Alert")
            print("-" * 40)
            
            try:
                # Send stop-loss alert
                async with session.post(
                    f"{API_URL}/api/alerts/stoploss",
                    json=test_case
                ) as response:
                    result = await response.json()
                    
                    if response.status == 200 and result.get('success'):
                        print(f"SUCCESS: {test_case['level'].upper()} alert sent successfully!")
                        print(f"   Title: {test_case['title']}")
                        print(f"   Message: {test_case['message']}")
                        print(f"   Response: {result.get('message')}")
                    else:
                        print(f"FAILED: Failed to send {test_case['level']} alert")
                        print(f"   Status: {response.status}")
                        print(f"   Response: {result}")
                        
            except Exception as e:
                print(f"ERROR: Error sending {test_case['level']} alert: {e}")
            
            # Wait between tests
            if i < len(test_cases):
                print("\nWaiting 2 seconds before next test...")
                await asyncio.sleep(2)
        
        print("\n" + "=" * 60)
        print("Test Complete!")
        print("=" * 60)
        
        # Check alert configuration
        print("\nChecking Alert Configuration...")
        try:
            async with session.get(f"{API_URL}/alerts/config") as response:
                if response.status == 200:
                    config = await response.json()
                    print("\nAlert Configuration:")
                    print(f"  - Telegram: {'Enabled' if config.get('telegram_enabled') else 'Disabled'}")
                    print(f"  - Email: {'Enabled' if config.get('email_enabled') else 'Disabled'}")
                    print(f"  - Sound: {'Enabled' if config.get('sound_enabled') else 'Disabled'}")
                    print(f"  - Desktop Notifications: {'Enabled' if config.get('desktop_notifications') else 'Disabled'}")
                    
                    if not config.get('telegram_enabled'):
                        print("\nWARNING: Telegram alerts are disabled. To enable:")
                        print("   1. Configure bot token and chat ID in settings")
                        print("   2. Enable Telegram alerts in the dashboard")
        except Exception as e:
            print(f"Could not fetch alert configuration: {e}")

if __name__ == "__main__":
    print("Starting Stop-Loss Alert Test...")
    print("Note: Make sure the unified API is running on port 8000")
    print()
    
    asyncio.run(test_stoploss_alerts())