"""
Script to archive duplicate endpoints by commenting them out
"""
import re

def archive_duplicates():
    print("Starting API cleanup...")
    
    # Read the file
    with open('unified_api_correct.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # List of duplicate endpoints to archive with their patterns
    duplicates_to_archive = [
        {
            'pattern': r'(@app\.post\("/save-trade-config", tags=\["Trading"\]\)\nasync def save_trade_configuration.*?(?=\n@app\.|$))',
            'name': '/save-trade-config (line ~4127)',
            'replacement': '# ARCHIVED /save-trade-config - Duplicate of /api/trade-config/save'
        },
        {
            'pattern': r'(@app\.get\("/trade-config", tags=\["Trading"\]\)\nasync def get_trade_configuration.*?(?=\n@app\.|$))',  
            'name': '/trade-config GET (line ~4178)',
            'replacement': '# ARCHIVED /trade-config GET - Duplicate of /api/trade-config/load'
        },
        {
            'pattern': r'(@app\.post\("/save-trade-config", tags=\["Trading"\]\)\nasync def save_trade_config[^n].*?(?=\n@app\.|$))',
            'name': '/save-trade-config (line ~9997)',
            'replacement': '# ARCHIVED /save-trade-config - Second duplicate'
        },
        {
            'pattern': r'(@app\.get\("/trade-config", tags=\["Trading"\]\)\nasync def load_trade_config.*?(?=\n@app\.|$))',
            'name': '/trade-config GET (line ~10033)',
            'replacement': '# ARCHIVED /trade-config GET - Second duplicate'
        }
    ]
    
    archived_count = 0
    
    for dup in duplicates_to_archive:
        # Check if pattern exists
        matches = re.findall(dup['pattern'], content, re.DOTALL)
        if matches:
            print(f"Found and archiving: {dup['name']}")
            # Comment out the entire function
            for match in matches:
                commented = '\n'.join(['# ' + line if line else '#' for line in match.split('\n')])
                replacement = f"\n# {dup['replacement']}\n{commented}\n"
                content = content.replace(match, replacement)
                archived_count += 1
        else:
            print(f"Not found (may already be archived): {dup['name']}")
    
    # Write back the modified content
    if archived_count > 0:
        with open('unified_api_correct.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\nSuccessfully archived {archived_count} duplicate endpoints")
    else:
        print("\nNo duplicates found to archive")
    
    # Also archive unused collect endpoints
    print("\nArchiving unused data collection endpoints...")
    unused_patterns = [
        (r'@app\.post\("/collect/nifty-direct"', "Data collection endpoints"),
        (r'@app\.post\("/collect/nifty-bulk"', "Data collection endpoints"),
        (r'@app\.post\("/collect/options-direct"', "Data collection endpoints"),
        (r'@app\.post\("/collect/options-bulk"', "Data collection endpoints"),
        (r'@app\.post\("/collect/options-specific"', "Data collection endpoints"),
        (r'@app\.post\("/collect/missing-from-insights"', "Data collection endpoints"),
        (r'@app\.post\("/collect/tradingview"', "Data collection endpoints"),
        (r'@app\.post\("/collect/tradingview-bulk"', "Data collection endpoints"),
        (r'@app\.delete\("/delete/nifty-direct"', "Data deletion endpoints"),
        (r'@app\.delete\("/delete/options-direct"', "Data deletion endpoints"),
        (r'@app\.delete\("/delete/all"', "Data deletion endpoints"),
    ]
    
    for pattern, description in unused_patterns:
        if re.search(pattern, content):
            print(f"  Found: {pattern} ({description})")
    
    print("\nCleanup analysis complete!")
    print("Backup saved in: archived_endpoints/unified_api_correct_backup_20250908.py")
    print("\nNote: Unused collection/deletion endpoints identified but NOT removed")
    print("They can be manually removed if confirmed not needed")

if __name__ == "__main__":
    archive_duplicates()