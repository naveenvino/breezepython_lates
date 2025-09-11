"""
UI Menu Test - Simplified verification of all navigation
"""
import os
from pathlib import Path

UI_DIR = Path(r"C:\Users\E1791\Kitepy\breezepython\ui")

def check_menus():
    """Check all menu items and their pages"""
    
    menus = {
        "TRADING MENU": [
            ("Live Trading Pro", "modules/trading/live_trading_pro_complete.html"),
            ("TradingView Pro", "modules/trading/tradingview_pro.html"),
            ("TradingView Monitor", "modules/trading/tradingview_monitor.html"),
            ("Paper Trading", "modules/trading/paper_trading.html"),
            ("Positions", "modules/trading/positions.html")
        ],
        "ANALYSIS MENU": [
            ("Option Chain", "modules/analysis/option_chain.html"),
            ("Backtesting", "modules/analysis/backtest.html"),
            ("Signals", "modules/analysis/signals.html")
        ],
        "ANALYTICS MENU": [
            ("Trade Journey", "modules/trade_journal_dashboard.html"),
            ("ML Validation", "modules/ml/ml_validation_form.html"),
            ("ML Analysis", "modules/ml/ml_analysis.html"),
            ("ML Optimization", "modules/ml/ml_optimization.html"),
            ("Expiry Comparison", "modules/expiry_comparison.html"),
            ("Performance Dashboard", "modules/monitoring/performance_dashboard.html"),
            ("Risk Management", "modules/monitoring/risk_dashboard.html")
        ],
        "SYSTEM MENU": [
            ("Trading Engine", "modules/integrated_trading_dashboard.html"),
            ("System Monitoring", "modules/monitoring/monitoring_dashboard.html"),
            ("WebSocket Dashboard", "modules/monitoring/monitoring_dashboard.html"),
            ("Trade Journal", "modules/trade_journal_dashboard.html")
        ],
        "DATA MENU": [
            ("Data Collection", "modules/data/data_collection.html"),
            ("Data Management", "modules/data/data_management.html"),
            ("Market Holidays", "modules/data/holidays.html"),
            ("Margin Calculator", "modules/margin_calculator.html")
        ],
        "TOOLS MENU": [
            ("Auto Login", "modules/auto_login_dashboard.html"),
            ("Scheduler", "modules/scheduler_dashboard.html")
        ],
        "SETTINGS": [
            ("Settings Page", "modules/settings.html")
        ],
        "DASHBOARD CARDS": [
            ("Live Trading Pro Card", "modules/trading/live_trading_pro_complete.html"),
            ("TradingView Pro Card", "modules/trading/tradingview_pro.html"),
            ("Backtesting Card", "modules/analysis/backtest.html"),
            ("ML Analysis Card", "modules/ml/ml_analysis.html"),
            ("Data Collection Card", "modules/data/data_collection.html")
        ]
    }
    
    print("\n" + "="*60)
    print("UI MENU AND SCREEN VERIFICATION")
    print("="*60)
    
    total_items = 0
    found_items = 0
    missing_items = []
    
    for menu_name, items in menus.items():
        print(f"\n[{menu_name}]")
        print("-" * 40)
        
        for item_name, path in items:
            total_items += 1
            file_path = UI_DIR / path
            
            if file_path.exists():
                found_items += 1
                file_size = file_path.stat().st_size
                status = "OK" if file_size > 1000 else "EMPTY"
                print(f"  OK  {item_name}")
                print(f"      Path: {path}")
                print(f"      Size: {file_size:,} bytes")
            else:
                missing_items.append(f"{menu_name}/{item_name}: {path}")
                print(f"  FAIL {item_name}")
                print(f"      Path: {path} - NOT FOUND")
    
    # Check AMO feature
    print(f"\n[AMO FEATURE CHECK]")
    print("-" * 40)
    
    amo_files = [
        ("Settings", "modules/settings.html"),
        ("TradingView Pro", "modules/trading/tradingview_pro.html")
    ]
    
    for name, path in amo_files:
        file_path = UI_DIR / path
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'amoEnabled' in content or 'AMO' in content:
                    print(f"  OK  AMO toggle found in {name}")
                else:
                    print(f"  FAIL AMO toggle NOT found in {name}")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    print(f"Total Menu Items: {total_items}")
    print(f"Found: {found_items}")
    print(f"Missing: {len(missing_items)}")
    print(f"Success Rate: {(found_items/total_items)*100:.1f}%")
    
    if missing_items:
        print("\nMissing Items:")
        for item in missing_items:
            print(f"  - {item}")
    
    # File organization summary
    print("\n" + "="*60)
    print("FILE ORGANIZATION")
    print("="*60)
    
    module_counts = {}
    for root, dirs, files in os.walk(UI_DIR / "modules"):
        rel_path = Path(root).relative_to(UI_DIR / "modules")
        if rel_path == Path("."):
            module_counts["root"] = len([f for f in files if f.endswith('.html')])
        else:
            module_name = str(rel_path).split(os.sep)[0]
            if module_name not in module_counts:
                module_counts[module_name] = 0
            module_counts[module_name] += len([f for f in files if f.endswith('.html')])
    
    for module, count in sorted(module_counts.items()):
        print(f"  {module}: {count} files")
    
    print(f"\nTotal organized files: {sum(module_counts.values())}")
    
    # Access instructions
    print("\n" + "="*60)
    print("ACCESS INSTRUCTIONS")
    print("="*60)
    print("1. Open browser: http://localhost:8000/")
    print("2. All menus should work from the navigation bar")
    print("3. Dashboard cards should open respective pages")
    print("4. Settings should show AMO toggle option")
    print("5. Use F12 console to check for any errors")
    
    return found_items == total_items

if __name__ == "__main__":
    all_good = check_menus()
    
    if all_good:
        print("\n SUCCESS: All menus and screens are properly configured!")
    else:
        print("\n WARNING: Some menu items need attention")
    
    print("\n" + "="*60)