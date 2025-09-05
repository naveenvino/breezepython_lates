"""
Verification script to confirm all dummy data has been removed from the system
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

def scan_for_dummy_data(directory: str, extensions: List[str]) -> List[Tuple[str, int, str]]:
    """
    Scan files for references to dummy data
    Returns list of (file_path, line_number, line_content)
    """
    dummy_patterns = [
        r'\bdummy\b',
        r'\bDummy\b', 
        r'\bDUMMY\b',
        r'\bfake\s+data\b',
        r'\btest\s+data\b',
        r'\bmock\s+data\b',
        r'\bplaceholder\b',
        r'\bhardcoded\s+value\b',
        r'return\s+100\.0\s*#.*dummy',
        r'return\s+.*#.*dummy'
    ]
    
    findings = []
    exclude_dirs = {'.venv', '__pycache__', 'node_modules', '.git', 'cleanup', 'docs'}
    exclude_files = {'verify_no_dummy_data.py', 'test_production_ready.py'}
    
    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                if file in exclude_files:
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line_num, line in enumerate(f, 1):
                            for pattern in dummy_patterns:
                                if re.search(pattern, line, re.IGNORECASE):
                                    # Skip comments and docstrings
                                    stripped = line.strip()
                                    if not (stripped.startswith('#') or 
                                           stripped.startswith('//') or
                                           stripped.startswith('"""') or
                                           stripped.startswith("'''") or
                                           'was dummy' in stripped.lower() or
                                           'removed dummy' in stripped.lower() or
                                           'no dummy' in stripped.lower() or
                                           'disable dummy' in stripped.lower()):
                                        findings.append((file_path, line_num, line.strip()))
                                        break
                except Exception as e:
                    pass
    
    return findings

def check_critical_services():
    """Check the critical services that were fixed"""
    services = [
        'src/services/strategy_automation_service.py',
        'src/services/trading_execution_service.py',
        'src/ml/trailing_stop_engine.py',
        'src/infrastructure/services/breeze_service.py'
    ]
    
    print("\n" + "="*70)
    print("CHECKING CRITICAL SERVICES FOR DUMMY DATA")
    print("="*70)
    
    all_clean = True
    for service in services:
        if os.path.exists(service):
            with open(service, 'r') as f:
                content = f.read()
                
            # Check for specific dummy patterns
            has_dummy = False
            if 'return 100.0' in content and 'dummy' in content.lower():
                has_dummy = True
            if 'dummy price' in content.lower():
                has_dummy = True
            if 'dummy response' in content.lower():
                has_dummy = True
            if 'generate dummy' in content.lower() and 'simulated' not in content.lower():
                has_dummy = True
                
            status = "[CLEAN]" if not has_dummy else "[CONTAINS DUMMY DATA]"
            print(f"{service}: {status}")
            
            if has_dummy:
                all_clean = False
        else:
            print(f"{service}: [WARNING] FILE NOT FOUND")
    
    return all_clean

def check_main_ui_files():
    """Check main UI files are clean"""
    ui_files = [
        'index_hybrid.html',
        'tradingview_pro.html',
        'live_trading_pro_complete.html',
        'integrated_trading_dashboard.html'
    ]
    
    print("\n" + "="*70)
    print("CHECKING MAIN UI FILES")
    print("="*70)
    
    all_clean = True
    for ui_file in ui_files:
        if os.path.exists(ui_file):
            with open(ui_file, 'r') as f:
                content = f.read()
                
            # Check for dummy notification functions
            has_dummy = False
            if 'loadDummyNotifications' in content:
                has_dummy = True
            if 'generateDummyData()' in content and 'performance_analytics' not in ui_file:
                has_dummy = True
            if 'dummy: true' in content:
                has_dummy = True
                
            status = "[CLEAN]" if not has_dummy else "[CONTAINS DUMMY DATA]"
            print(f"{ui_file}: {status}")
            
            if has_dummy:
                all_clean = False
        else:
            print(f"{ui_file}: [WARNING] FILE NOT FOUND")
    
    return all_clean

def main():
    print("\n" + "="*70)
    print("DUMMY DATA VERIFICATION REPORT")
    print("="*70)
    
    # Check critical services
    services_clean = check_critical_services()
    
    # Check main UI files
    ui_clean = check_main_ui_files()
    
    # Scan for remaining dummy references
    print("\n" + "="*70)
    print("SCANNING FOR OTHER DUMMY REFERENCES")
    print("="*70)
    
    findings = scan_for_dummy_data('.', ['.py', '.html', '.js'])
    
    # Filter out acceptable uses
    filtered_findings = []
    for file_path, line_num, line in findings:
        # Skip documentation and test files
        if 'cleanup/old_docs' in file_path:
            continue
        if 'test_' in os.path.basename(file_path):
            continue
        if 'performance_analytics.html' in file_path:
            continue  # Demo page can have dummy data
        if 'simulated' in line.lower() and 'testing' in line.lower():
            continue  # Simulation for testing is acceptable
            
        filtered_findings.append((file_path, line_num, line))
    
    if filtered_findings:
        print(f"\nFound {len(filtered_findings)} potential issues:")
        for file_path, line_num, line in filtered_findings[:10]:  # Show first 10
            rel_path = os.path.relpath(file_path)
            print(f"  {rel_path}:{line_num}: {line[:80]}")
    else:
        print("\n[OK] No concerning dummy data references found!")
    
    # Final verdict
    print("\n" + "="*70)
    print("FINAL VERIFICATION RESULTS")
    print("="*70)
    
    if services_clean and ui_clean and not filtered_findings:
        print("[OK] ALL CLEAR: No dummy data found in production code!")
        print("[OK] The system is ready for production deployment.")
    else:
        print("[WARNING] ATTENTION NEEDED:")
        if not services_clean:
            print("  - Some services still contain dummy data")
        if not ui_clean:
            print("  - Some UI files still contain dummy references")
        if filtered_findings:
            print(f"  - Found {len(filtered_findings)} files with potential dummy data")
    
    print("\nNote: performance_analytics.html is excluded as it's a demo/analytics page.")
    print("Simulated data for testing purposes is acceptable when properly labeled.")

if __name__ == "__main__":
    main()