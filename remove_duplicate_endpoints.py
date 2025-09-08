"""
Script to remove duplicate API endpoints from unified_api_correct.py
"""

import re

def remove_duplicates():
    # Read the file
    with open('unified_api_correct.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Track which endpoints we've seen
    seen_endpoints = set()
    lines_to_remove = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this is an endpoint definition
        match = re.search(r'@app\.(get|post|put|delete|patch)\("([^"]+)"', line)
        if match:
            method = match.group(1)
            path = match.group(2)
            endpoint_key = f"{method.upper()} {path}"
            
            if endpoint_key in seen_endpoints:
                # This is a duplicate - mark for removal
                # Find the end of this function (next @app or def at same indentation)
                start_line = i
                i += 1
                
                # Skip to the function definition
                while i < len(lines) and not lines[i].strip().startswith('async def') and not lines[i].strip().startswith('def'):
                    i += 1
                
                if i < len(lines):
                    # Now find the end of the function
                    indent_level = len(lines[i]) - len(lines[i].lstrip())
                    i += 1
                    
                    while i < len(lines):
                        current_line = lines[i]
                        # Check if we've reached another function or decorator at same or lower indentation
                        if current_line.strip() and not current_line.startswith(' ' * (indent_level + 4)):
                            if (current_line.startswith('@') or 
                                current_line.strip().startswith('def ') or 
                                current_line.strip().startswith('async def ') or
                                current_line.strip().startswith('class ') or
                                current_line.strip().startswith('#') and not current_line.startswith(' ' * (indent_level + 4)) or
                                len(current_line) - len(current_line.lstrip()) <= indent_level):
                                break
                        i += 1
                    
                    # Mark lines for removal
                    for j in range(start_line, i):
                        lines_to_remove.append(j)
                    
                    print(f"Removing duplicate endpoint: {endpoint_key} (lines {start_line+1}-{i})")
            else:
                seen_endpoints.add(endpoint_key)
                i += 1
        else:
            i += 1
    
    # Remove marked lines (in reverse order to maintain indices)
    for line_num in sorted(lines_to_remove, reverse=True):
        if line_num < len(lines):
            lines[line_num] = f"# DUPLICATE REMOVED: {lines[line_num]}" if lines[line_num].strip() else lines[line_num]
    
    # Write back
    with open('unified_api_correct.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"\nRemoved {len(set([l for l in lines_to_remove]))} duplicate endpoint lines")
    print("Duplicates have been commented out with '# DUPLICATE REMOVED:' prefix")

if __name__ == "__main__":
    remove_duplicates()