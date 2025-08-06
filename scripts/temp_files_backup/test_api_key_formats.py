"""Test different API key formats"""
from breeze_connect import BreezeConnect

# The credentials from .env
api_key_original = "23(326O4280m9516L8F4!1]R"
api_secret = "83^48s3V1X4K0@7~m1H57T9^2*96~09"
session_token = "52469011"

# Try different variations of the API key
test_keys = [
    ("Original", api_key_original),
    ("Without special chars", "23326O4280m9516L8F41R"),
    ("Lowercase O to 0", api_key_original.replace('O', '0')),
    ("Check if it's actually zeros", "23(326042809516L8F4!1]R"),
]

for name, api_key in test_keys:
    print(f"\nTrying: {name}")
    print(f"API Key: {api_key}")
    try:
        breeze = BreezeConnect(api_key=api_key)
        breeze.generate_session(api_secret=api_secret, session_token=session_token)
        print(f"SUCCESS with {name}!")
        
        # Try to get customer details
        customer = breeze.get_customer_details()
        print(f"Customer details: {customer}")
        break
    except Exception as e:
        print(f"Failed: {str(e)[:100]}")

print("\n" + "="*50)
print("Note: The API key might need to be regenerated from ICICI Direct portal")
print("Or the session token might have expired")