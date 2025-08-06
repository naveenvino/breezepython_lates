"""Verify Breeze Credentials"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials
api_key = os.getenv('BREEZE_API_KEY')
api_secret = os.getenv('BREEZE_API_SECRET')
session_token = os.getenv('BREEZE_API_SESSION')

print("Raw credentials from .env:")
print(f"API Key length: {len(api_key) if api_key else 0}")
print(f"API Key: '{api_key}'")
print(f"API Secret length: {len(api_secret) if api_secret else 0}")
print(f"API Secret: '{api_secret}'")
print(f"Session Token: '{session_token}'")

# Check for any issues
if api_key:
    print(f"\nAPI Key characters: {[c for c in api_key]}")
    
# Try direct reading
print("\n" + "="*50)
print("Direct file reading:")
with open('.env', 'r') as f:
    for line in f:
        if 'BREEZE' in line:
            print(line.strip())