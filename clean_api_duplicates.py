"""
Script to safely remove duplicate and unused endpoints from unified_api_correct.py
"""

import re

def clean_api_file():
    # Read the file
    with open('unified_api_correct.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Track what we're removing
    removed_endpoints = []
    in_removal_block = False
    removal_start = -1
    new_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check for duplicate endpoints to remove
        if '@app.post("/save-trade-config"' in line and i in [4126, 9996]:
            # Found duplicate endpoint, mark for removal
            removed_endpoints.append(f"Line {i+1}: /save-trade-config")
            in_removal_block = True
            removal_start = i
            # Add comment about removal
            new_lines.append(f"# ARCHIVED: Duplicate /save-trade-config endpoint removed (was at line {i+1})\n")
            new_lines.append("# Use /api/trade-config/save instead\n")
            new_lines.append("\n")
            
        elif '@app.get("/trade-config"' in line and i in [4177, 10032]:
            # Found duplicate endpoint, mark for removal  
            removed_endpoints.append(f"Line {i+1}: /trade-config GET")
            in_removal_block = True
            removal_start = i
            # Add comment about removal
            new_lines.append(f"# ARCHIVED: Duplicate /trade-config GET endpoint removed (was at line {i+1})\n")
            new_lines.append("# Use /api/trade-config/load instead\n")
            new_lines.append("\n")
            
        elif '@app.get("/health")' in line and i == 1574:
            # Found duplicate health endpoint
            removed_endpoints.append(f"Line {i+1}: /health")
            in_removal_block = True
            removal_start = i
            new_lines.append(f"# ARCHIVED: Duplicate /health endpoint removed (was at line {i+1})\n")
            new_lines.append("# Use /api/health instead\n")
            new_lines.append("\n")
            
        elif '@app.get("/positions")' in line and i == 2419:
            # Found duplicate positions endpoint
            removed_endpoints.append(f"Line {i+1}: /positions")
            in_removal_block = True
            removal_start = i
            new_lines.append(f"# ARCHIVED: Duplicate /positions endpoint removed (was at line {i+1})\n")
            new_lines.append("# Use /api/positions or /api/trading/positions instead\n")
            new_lines.append("\n")
            
        elif '@app.get("/")' in line and i == 1559:
            # Found duplicate root endpoint
            removed_endpoints.append(f"Line {i+1}: / root")
            in_removal_block = True
            removal_start = i
            new_lines.append(f"# ARCHIVED: Duplicate / root endpoint removed (was at line {i+1})\n")
            new_lines.append("# Main root endpoint is at line 114\n")
            new_lines.append("\n")
            
        elif in_removal_block:
            # Check if we've reached the end of the function
            # Functions end when we find another @app. decorator or reach end of indented block
            if (line.startswith('@app.') or 
                (not line.strip() and i+1 < len(lines) and lines[i+1].startswith('@app.')) or
                (line.strip() and not line.startswith(' ') and not line.startswith('\t'))):
                in_removal_block = False
                # Don't skip this line, it's the start of the next endpoint
                new_lines.append(line)
            # Skip lines that are part of the function being removed
            
        else:
            # Keep the line
            new_lines.append(line)
        
        i += 1
    
    # Write the cleaned file
    with open('unified_api_correct.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print("API Cleanup Complete!")
    print(f"Removed {len(removed_endpoints)} duplicate endpoints:")
    for endpoint in removed_endpoints:
        print(f"  - {endpoint}")
    print("\nBackup saved to: archived_endpoints/unified_api_correct_backup_20250908.py")
    print("Duplicates archived in: archived_endpoints/duplicates.py")

if __name__ == "__main__":
    clean_api_file()