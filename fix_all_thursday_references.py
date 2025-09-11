"""
Fix all remaining Thursday references to Tuesday
"""

import os
import re
from pathlib import Path

def fix_thursday_references(file_path):
    """Fix Thursday references in a single file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Replace Thursday with Tuesday in comments and strings
    content = re.sub(r'\bThursday\b', 'Tuesday', content)
    content = re.sub(r'\bthursday\b', 'tuesday', content)
    content = re.sub(r'\bTHURSDAY\b', 'TUESDAY', content)
    
    # Replace weekday == 3 with weekday == 1
    content = re.sub(r'weekday\(\)\s*==\s*3', 'weekday() == 1', content)
    content = re.sub(r'\.weekday\(\)\s*==\s*3', '.weekday() == 1', content)
    
    # Replace 3 - today.weekday() with 1 - today.weekday()
    content = re.sub(r'3\s*-\s*today\.weekday\(\)', '1 - today.weekday()', content)
    content = re.sub(r'3\s*-\s*\w+\.weekday\(\)', lambda m: m.group(0).replace('3', '1'), content)
    
    # Replace days_until_thursday with days_until_tuesday
    content = re.sub(r'days_until_thursday', 'days_until_tuesday', content, flags=re.IGNORECASE)
    
    # Replace next_thursday with next_tuesday
    content = re.sub(r'next_thursday', 'next_tuesday', content, flags=re.IGNORECASE)
    
    # Replace thursday_expiry with tuesday_expiry
    content = re.sub(r'thursday_expiry', 'tuesday_expiry', content, flags=re.IGNORECASE)
    
    # Fix specific patterns
    # Pattern: (3 - date.weekday()) % 7
    content = re.sub(r'\(3\s*-\s*(\w+)\.weekday\(\)\)\s*%\s*7', r'(1 - \1.weekday()) % 7', content)
    
    # Pattern: timedelta(days=(3 - today.weekday()) % 7)
    content = re.sub(r'timedelta\(days=\(3\s*-\s*(\w+)\.weekday\(\)\)\s*%\s*7\)', 
                     r'timedelta(days=(1 - \1.weekday()) % 7)', content)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    """Fix all Thursday references in the codebase"""
    
    # List of files to fix
    files_to_fix = [
        'src/ml/enhanced_hourly_exit_analyzer.py',
        'src/ml/feature_engineering.py',
        'src/ml/feature_engineering_fixed.py',
        'src/services/live_market_service.py',
        'src/services/live_market_service_fixed.py',
        'src/services/live_order_executor.py',
        'src/services/live_trading_executor_kite.py',
        'src/services/market_data_cache_service.py',
        'src/services/option_chain_cache_service.py',
        'src/services/option_chain_service.py',
        'src/services/option_greeks_service.py',
        'src/services/signals_producer.py',
        'src/services/telegram_service.py',
        'src/services/trading_executor.py',
        'src/services/zerodha_order_executor.py',
        'src/ml/exit_time_predictor.py',
        'src/trading/signal_generator.py',
        'src/services/option_chain_analyzer.py',
        'src/monitoring/trade_monitor.py',
        'src/live_trading/zerodha_executor.py',
        'api/endpoints/data_collection.py',
        'api/endpoints/signals.py',
        'api/endpoints/option_chain.py',
        'deployment/scripts/setup_database.py',
        'src/utils/date_utils.py',
        'src/services/expiry_service.py',
        'src/live_trading/position_manager.py',
        'src/ml/model_trainer.py',
        'src/services/backtest_service.py',
        'src/services/data_service.py',
        'src/services/position_tracker.py',
        'src/services/risk_manager.py'
    ]
    
    # Also find all Python files that might have Thursday references
    for file_path in Path('.').rglob('*.py'):
        if '.venv' not in str(file_path) and 'test_security' not in str(file_path) and 'fix_all_thursday' not in str(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if any(pattern in content for pattern in ['Thursday', 'thursday', 'weekday() == 3', '3 - today.weekday()']):
                        if str(file_path) not in files_to_fix:
                            files_to_fix.append(str(file_path))
            except:
                pass
    
    print(f"Found {len(files_to_fix)} files to fix")
    
    fixed_count = 0
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            try:
                if fix_thursday_references(file_path):
                    print(f"Fixed: {file_path}")
                    fixed_count += 1
            except Exception as e:
                print(f"Error fixing {file_path}: {e}")
    
    print(f"\nFixed {fixed_count} files")
    print("All Thursday references have been updated to Tuesday")

if __name__ == "__main__":
    main()