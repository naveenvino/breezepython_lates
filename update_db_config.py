"""
Update database configuration to 5 lots
"""
from src.services.trade_config_service import get_trade_config_service
import json

# Get configuration service
service = get_trade_config_service()

# Load current configuration
current_config = service.load_trade_config(user_id='default', config_name='default')

print("CURRENT Configuration:")
print(f"  num_lots: {current_config.get('num_lots')}")

# Update to 5 lots
current_config['num_lots'] = 5

# Save updated configuration
result = service.save_trade_config(current_config, user_id='default', config_name='default')

print("\nUPDATE Result:", result)

# Verify the update
updated_config = service.load_trade_config(user_id='default', config_name='default')
print("\nNEW Configuration:")
print(f"  num_lots: {updated_config.get('num_lots')}")
print(f"\nActual order quantity will be: {updated_config.get('num_lots')} lots x 75 = {updated_config.get('num_lots') * 75} qty")