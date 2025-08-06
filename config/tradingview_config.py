"""TradingView Configuration"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# TradingView Credentials
TRADINGVIEW_USERNAME = os.getenv('TRADINGVIEW_USERNAME', '')
TRADINGVIEW_PASSWORD = os.getenv('TRADINGVIEW_PASSWORD', '')

# You can also hardcode them here (not recommended for production)
# TRADINGVIEW_USERNAME = 'your_username'
# TRADINGVIEW_PASSWORD = 'your_password'

def get_tv_credentials():
    """Get TradingView credentials"""
    return TRADINGVIEW_USERNAME, TRADINGVIEW_PASSWORD