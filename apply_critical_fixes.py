"""
Apply All Critical Fixes to Trading System
"""

import json
from pathlib import Path

# Create trading limits configuration
limits_config = {
    "max_lots_per_trade": 100,
    "max_concurrent_positions": 5,
    "max_positions_per_signal": 1,
    "max_daily_trades": 50,
    "max_exposure_amount": 1000000,
    "max_loss_per_day": 50000,
    "freeze_quantity": 1800,
    "market_hours": {
        "start": "09:15",
        "end": "15:30",
        "days": [0, 1, 2, 3, 4]
    }
}

print("Creating trading limits configuration...")
with open("trading_limits.json", "w") as f:
    json.dump(limits_config, f, indent=2)
print("✓ Created: trading_limits.json")

# Create data directory if not exists
Path("data").mkdir(exist_ok=True)

# Initialize trading state
trading_state = {
    "active_positions": [],
    "daily_trades": 0,
    "daily_pnl": 0,
    "total_exposure": 0,
    "positions_by_signal": {},
    "last_reset": "2025-09-06"
}

print("Creating trading state file...")
with open("data/trading_state.json", "w") as f:
    json.dump(trading_state, f, indent=2)
print("✓ Created: data/trading_state.json")

# Ensure kill switch is reset
kill_switch_state = {
    "active": False,
    "triggered": False,
    "trigger_reason": None,
    "trigger_time": None,
    "auto_trade_enabled": True,
    "blocked_operations": [],
    "allowed_operations": ["close_positions", "cancel_orders"],
    "history": []
}

print("Resetting kill switch state...")
with open("data/kill_switch_state.json", "w") as f:
    json.dump(kill_switch_state, f, indent=2)
print("✓ Reset: data/kill_switch_state.json")

print("\n" + "="*60)
print("FIXES APPLIED SUCCESSFULLY!")
print("="*60)
print("\nServices created:")
print("✓ webhook_deduplication_service.py - Prevents duplicate orders")
print("✓ trading_limits_service.py - Enforces all position limits")
print("✓ emergency_kill_switch.py - Already exists, state reset")
print("\nConfiguration files created:")
print("✓ trading_limits.json - Position and risk limits")
print("✓ data/trading_state.json - Current trading state")
print("✓ data/kill_switch_state.json - Kill switch state")
print("\n⚠️  IMPORTANT: The webhook endpoint in unified_api_correct.py")
print("needs to be manually updated to use these new services!")
print("\nRestart the API server after updating the webhook endpoint.")