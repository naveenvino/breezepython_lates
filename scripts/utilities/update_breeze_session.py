"""
Update Breeze API session token
"""
import sys
import re

def update_session_token(url):
    # Extract session token from URL
    match = re.search(r'apisession=(\d+)', url)
    if not match:
        print("Error: Could not extract session token from URL")
        return
    
    session_token = match.group(1)
    print(f"Extracted session token: {session_token}")
    
    # Read current .env file
    try:
        with open('.env', 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("Error: .env file not found")
        return
    
    # Update BREEZE_API_SESSION line
    updated = False
    for i, line in enumerate(lines):
        if line.startswith('BREEZE_API_SESSION='):
            lines[i] = f'BREEZE_API_SESSION={session_token}\n'
            updated = True
            break
    
    if not updated:
        # Add the line if it doesn't exist
        lines.append(f'BREEZE_API_SESSION={session_token}\n')
    
    # Write back to .env
    with open('.env', 'w') as f:
        f.writelines(lines)
    
    print(f"Successfully updated .env with session token: {session_token}")
    print("Please restart the API for changes to take effect")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_breeze_session.py <breeze_url>")
        sys.exit(1)
    
    update_session_token(sys.argv[1])