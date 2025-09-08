"""
Script to reorganize API endpoints with hierarchical broker-based grouping
"""

import re

def reorganize_api_tags():
    # Read the file
    with open('unified_api_correct.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Analyze each endpoint and map to correct hierarchical tag
    endpoint_mappings = {}
    
    for i, line in enumerate(lines):
        if '@app.' in line and not line.strip().startswith('#'):
            # Get endpoint path
            endpoint_match = re.search(r'@app\.\w+\("([^"]+)"', line)
            if endpoint_match:
                endpoint_path = endpoint_match.group(1)
                
                # Check next 30 lines for service usage
                context = ''.join(lines[i:min(i+30, len(lines))]).lower()
                
                # Determine correct tag based on actual usage
                tag = None
                
                # === KITE ENDPOINTS ===
                if 'get_kite_services' in context or 'kite_client' in context or 'kiteconnect' in context:
                    # Categorize Kite endpoints by functionality
                    if '/orders' in endpoint_path or 'place_order' in context:
                        tag = "Kite - Order Management"
                    elif '/positions' in endpoint_path or 'get_positions' in context or 'square_off' in endpoint_path:
                        tag = "Kite - Position Management"
                    elif '/auth' in endpoint_path or 'login' in endpoint_path or 'authentication' in context:
                        tag = "Kite - Authentication"
                    elif '/live/pnl' in endpoint_path or 'get_position_pnl' in context:
                        tag = "Kite - PnL & Analytics"
                    elif 'stop_loss' in endpoint_path or 'stop-loss' in endpoint_path:
                        tag = "Kite - Risk Management"
                    elif '/live/trades' in endpoint_path:
                        tag = "Kite - Trade Monitoring"
                    elif 'execute_trade' in context or 'execute-trade' in endpoint_path:
                        tag = "Kite - Trade Execution"
                    else:
                        tag = "Kite - General"
                
                # === BREEZE ENDPOINTS ===
                elif 'breezeservice' in context or 'breeze_service' in context or 'breeze_ws_manager' in context or 'live_market_service' in context:
                    # Categorize Breeze endpoints by functionality
                    if 'spot' in endpoint_path or 'nifty-spot' in endpoint_path:
                        tag = "Breeze - Spot Prices"
                    elif 'option' in endpoint_path or 'option_chain' in context:
                        tag = "Breeze - Options Data"
                    elif 'candle' in endpoint_path or 'historical' in endpoint_path:
                        tag = "Breeze - Historical Data"
                    elif 'vix' in endpoint_path:
                        tag = "Breeze - Market Indicators"
                    elif '/collect' in endpoint_path or 'data_collection' in context:
                        tag = "Breeze - Data Collection"
                    elif '/ws/' in endpoint_path or 'websocket' in context:
                        tag = "Breeze - WebSocket"
                    elif 'market_depth' in endpoint_path or 'market-depth' in endpoint_path:
                        tag = "Breeze - Market Depth"
                    elif '/backtest' in endpoint_path:
                        tag = "Breeze - Backtesting"
                    else:
                        tag = "Breeze - General"
                
                # Check for specific Breeze/Kite authentication
                elif '/auth/auto-login/breeze' in endpoint_path or '/auth/db/breeze' in endpoint_path:
                    tag = "Breeze - Authentication"
                elif '/auth/auto-login/kite' in endpoint_path or '/auth/db/kite' in endpoint_path or '/auth/kite' in endpoint_path:
                    tag = "Kite - Authentication"
                elif '/breeze' in endpoint_path:
                    tag = "Breeze - Status"
                elif '/kite' in endpoint_path:
                    tag = "Kite - Status"
                
                # === BROKER-AGNOSTIC ENDPOINTS ===
                elif '/webhook' in endpoint_path:
                    tag = "Webhooks - TradingView"
                elif '/settings' in endpoint_path:
                    tag = "System - Settings"
                elif '/config' in endpoint_path:
                    tag = "System - Configuration"
                elif '/health' in endpoint_path:
                    tag = "System - Health"
                elif '/risk' in endpoint_path or 'kill-switch' in endpoint_path:
                    tag = "System - Risk Management"
                elif '/ml/' in endpoint_path:
                    tag = "ML - Analytics"
                elif '/paper' in endpoint_path:
                    tag = "Paper Trading"
                elif '/alerts' in endpoint_path:
                    tag = "System - Alerts"
                elif '/signals' in endpoint_path:
                    tag = "Trading - Signals"
                elif '/session' in endpoint_path:
                    tag = "System - Session Management"
                elif '/holiday' in endpoint_path:
                    tag = "System - Calendar"
                elif '/data/' in endpoint_path or '/table' in endpoint_path:
                    tag = "System - Data Management"
                elif '/auto-trade' in endpoint_path:
                    tag = "Trading - Auto Trade"
                elif '.html' in endpoint_path or endpoint_path == '/':
                    continue  # Skip HTML endpoints
                
                if tag:
                    endpoint_mappings[i] = tag
    
    # Apply the new tags
    for line_num, new_tag in endpoint_mappings.items():
        if 'tags=' in lines[line_num]:
            lines[line_num] = re.sub(r'tags=\["[^"]+"\]', f'tags=["{new_tag}"]', lines[line_num])
    
    # Write back
    with open('unified_api_correct.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("Hierarchical tag reorganization complete!")
    
    # Count and display the tree structure
    tag_counts = {}
    for tag in endpoint_mappings.values():
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    # Sort and display as tree
    print("\n" + "="*70)
    print("API ENDPOINT HIERARCHY")
    print("="*70)
    
    # Group by main category
    kite_tags = {k: v for k, v in sorted(tag_counts.items()) if k.startswith('Kite')}
    breeze_tags = {k: v for k, v in sorted(tag_counts.items()) if k.startswith('Breeze')}
    system_tags = {k: v for k, v in sorted(tag_counts.items()) if k.startswith('System')}
    other_tags = {k: v for k, v in sorted(tag_counts.items()) if not (k.startswith('Kite') or k.startswith('Breeze') or k.startswith('System'))}
    
    print("\n[KITE] Zerodha APIs")
    print("|-- Total:", sum(kite_tags.values()), "endpoints")
    for tag, count in kite_tags.items():
        sub = tag.split(' - ')[1] if ' - ' in tag else tag
        print(f"|-- {sub}: {count} endpoints")
    
    print("\n[BREEZE] APIs")
    print("|-- Total:", sum(breeze_tags.values()), "endpoints")
    for tag, count in breeze_tags.items():
        sub = tag.split(' - ')[1] if ' - ' in tag else tag
        print(f"|-- {sub}: {count} endpoints")
    
    print("\n[SYSTEM] APIs")
    print("|-- Total:", sum(system_tags.values()), "endpoints")
    for tag, count in system_tags.items():
        sub = tag.split(' - ')[1] if ' - ' in tag else tag
        print(f"|-- {sub}: {count} endpoints")
    
    if other_tags:
        print("\n[OTHER] APIs")
        print("|-- Total:", sum(other_tags.values()), "endpoints")
        for tag, count in other_tags.items():
            print(f"|-- {tag}: {count} endpoints")
    
    print("\n" + "="*70)
    print(f"Total Tagged Endpoints: {sum(tag_counts.values())}")
    print(f"Total Unique Tags: {len(tag_counts)}")

if __name__ == "__main__":
    reorganize_api_tags()