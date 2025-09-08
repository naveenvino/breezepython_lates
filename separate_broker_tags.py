"""
Script to separate Breeze and Kite endpoints into their own groups
"""

import re

def separate_broker_endpoints():
    # Read the file
    with open('unified_api_correct.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find and update Breeze-related endpoints
    breeze_patterns = [
        (r'"/breeze/status"', 'Breeze API'),
        (r'"/api/breeze-ws/status"', 'Breeze API'),
        (r'"/api/breeze/hourly-candle"', 'Breeze API'),
        (r'"/ws/breeze-live"', 'Breeze API'),
        (r'"/breeze-health"', 'Breeze API'),
        (r'"/auth/auto-login/breeze"', 'Breeze API'),
        (r'"/auth/db/breeze/login"', 'Breeze API'),
    ]
    
    # Find and update Kite-related endpoints
    kite_patterns = [
        (r'"/kite/status"', 'Kite API'),
        (r'"/kite-health"', 'Kite API'),
        (r'"/kite/auto-login"', 'Kite API'),
        (r'"/auth/auto-login/kite"', 'Kite API'),
        (r'"/auth/db/kite/login"', 'Kite API'),
        (r'"/auth/kite/auto-connect"', 'Kite API'),
        (r'"/api/positions"', 'Kite API'),  # Kite positions endpoint
        (r'"/orders"', 'Kite API'),  # Kite orders
        (r'"/positions/square-off-all"', 'Kite API'),  # Kite square off
    ]
    
    # Update Breeze endpoints
    for pattern, new_tag in breeze_patterns:
        # Find lines with these endpoints and update their tags
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if pattern in line and '@app.' in line and 'tags=' in line:
                # Extract and replace the tag
                old_tag_match = re.search(r'tags=\["([^"]+)"\]', line)
                if old_tag_match:
                    lines[i] = re.sub(r'tags=\["[^"]+"\]', f'tags=["{new_tag}"]', line)
                    print(f"Updated {pattern} to use tag: {new_tag}")
        content = '\n'.join(lines)
    
    # Update Kite endpoints
    for pattern, new_tag in kite_patterns:
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if pattern in line and '@app.' in line and 'tags=' in line:
                # Extract and replace the tag
                old_tag_match = re.search(r'tags=\["([^"]+)"\]', line)
                if old_tag_match:
                    lines[i] = re.sub(r'tags=\["[^"]+"\]', f'tags=["{new_tag}"]', line)
                    print(f"Updated {pattern} to use tag: {new_tag}")
        content = '\n'.join(lines)
    
    # Also update any endpoints that have "breeze" or "kite" in their path but weren't caught
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if '@app.' in line and 'tags=' in line and not line.strip().startswith('#'):
            # Check for breeze in path
            if '/breeze' in line.lower() or 'breeze' in line.lower():
                if 'tags=["Breeze API"]' not in line:
                    endpoint_match = re.search(r'@app\.\w+\("([^"]+)"', line)
                    if endpoint_match and 'breeze' in endpoint_match.group(1).lower():
                        lines[i] = re.sub(r'tags=\["[^"]+"\]', 'tags=["Breeze API"]', line)
                        print(f"Updated line {i+1} to Breeze API tag")
            
            # Check for kite in path  
            elif '/kite' in line.lower() or 'kite' in line.lower():
                if 'tags=["Kite API"]' not in line:
                    endpoint_match = re.search(r'@app\.\w+\("([^"]+)"', line)
                    if endpoint_match and 'kite' in endpoint_match.group(1).lower():
                        lines[i] = re.sub(r'tags=\["[^"]+"\]', 'tags=["Kite API"]', line)
                        print(f"Updated line {i+1} to Kite API tag")
    
    content = '\n'.join(lines)
    
    # Write the updated content back
    with open('unified_api_correct.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("\nBroker endpoint separation complete!")
    
    # Count final tags
    matches = re.findall(r'tags=\["([^"]+)"\]', content)
    tag_counts = {}
    for tag in matches:
        if not content.split('\n')[matches.index(tag)].strip().startswith('#'):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    print("\nUpdated tag distribution:")
    print("-" * 50)
    for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True):
        if 'Breeze' in tag or 'Kite' in tag:
            print(f">>> {tag:<25} {count:>3} endpoints <<<")
        else:
            print(f"{tag:<25} {count:>3} endpoints")
    print("-" * 50)
    print(f"Total unique tags: {len(tag_counts)}")

if __name__ == "__main__":
    separate_broker_endpoints()