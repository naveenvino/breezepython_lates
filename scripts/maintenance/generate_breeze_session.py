"""
Generate Breeze session - helps with proper authentication
"""
import os
from dotenv import load_dotenv
from breeze_connect import BreezeConnect
import webbrowser

# Load environment variables
load_dotenv()

api_key = os.getenv('BREEZE_API_KEY')
api_secret = os.getenv('BREEZE_API_SECRET')

print("=== Breeze Session Generation ===")
print(f"API Key: {api_key}")
print(f"API Secret: {'*' * 10}")

# Create Breeze instance
breeze = BreezeConnect(api_key=api_key)

# Generate the login URL
login_url = f"https://api.icicidirect.com/apiuser/login?api_key={api_key}"

print(f"\nPlease visit this URL to generate a session:")
print(login_url)
print("\nAfter login, you'll be redirected to a URL like:")
print("https://localhost:56412/?apisession=XXXXXXXX")
print("\nThe session token is the XXXXXXXX part after 'apisession='")
print("\nCurrent session token in .env:", os.getenv('BREEZE_API_SESSION'))

# Open browser
try:
    webbrowser.open(login_url)
    print("\nOpened browser for you...")
except:
    print("\nCouldn't open browser automatically. Please visit the URL manually.")

print("\nOnce you have the new session token, update the .env file:")
print("BREEZE_API_SESSION=<new_session_token>")