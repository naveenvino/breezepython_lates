"""
Script to consolidate API tags in unified_api_correct.py for better Swagger organization
"""

import re

def consolidate_tags():
    # Read the file
    with open('unified_api_correct.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Define tag mappings (old tag -> new tag)
    tag_mappings = {
        # Consolidate Live Trading tags
        "Live Trading - Auth": "Trading",
        "Live Trading - Control": "Trading", 
        "Live Trading - Monitoring": "Trading",
        "Live Trading - Execution": "Trading",
        "Live Trading - Risk Management": "Risk Management",
        "TradingView Pro": "Trading",
        "Kite Trading": "Trading",
        "Trading API": "Trading",
        "Production Trading": "Trading",
        
        # Consolidate Authentication tags
        "Auto Login": "Authentication",
        "Database Auth": "Authentication",
        
        # Consolidate Data Collection tags
        "NIFTY Collection": "Data Collection",
        "Options Collection": "Data Collection",
        "TradingView Collection": "Data Collection",
        "Weekly Collection": "Data Collection",
        "Data Check": "Data Collection",
        "Data Deletion": "Data Collection",
        
        # Consolidate Market Data tags
        "Live Market Data": "Market Data",
        "Breeze Market Data": "Market Data",
        
        # Consolidate ML tags
        "ML Validation": "ML & Analytics",
        "ML Optimization": "ML & Analytics",
        "ML Analysis": "ML & Analytics",
        "ML Backtest": "ML & Analytics",
        "ML": "ML & Analytics",
        "Analytics": "ML & Analytics",
        
        # Consolidate Alert tags
        "Alert Notifications": "Alerts",
        
        # Consolidate Configuration tags
        "Trade Config": "Settings",
        "Exit Timing": "Settings",
        "Expiry Management": "Settings",
        "Square Off": "Settings",
        
        # Consolidate System tags
        "System Monitoring": "System",
        "Testing": "System",
        "Job Management": "System",
        "Dashboard": "System",
        
        # Consolidate Health tags
        "Health": "System",
        
        # Rename General to more specific
        "General": "System",
        
        # Consolidate Webhook tags
        "TradingView Webhook": "Webhooks",
        "Webhook": "Webhooks",
        
        # Keep these as-is but ensure consistency
        "Broker Status": "System",
        "Options": "Market Data",
        "Kill Switch": "Risk Management",
        "Slippage Management": "Risk Management",
        "Order Reconciliation": "Risk Management",
    }
    
    # Apply all mappings
    for old_tag, new_tag in tag_mappings.items():
        # Find and replace all occurrences of the old tag
        pattern = f'tags=\\["{re.escape(old_tag)}"\\]'
        replacement = f'tags=["{new_tag}"]'
        content = re.sub(pattern, replacement, content)
    
    # Write the updated content back
    with open('unified_api_correct.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Tag consolidation complete!")
    
    # Count final tags
    matches = re.findall(r'tags=\["([^"]+)"\]', content)
    tag_counts = {}
    for tag in matches:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    print("\nFinal tag distribution:")
    print("-" * 50)
    for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{tag:<25} {count:>3} endpoints")
    print("-" * 50)
    print(f"Total unique tags: {len(tag_counts)}")

if __name__ == "__main__":
    consolidate_tags()