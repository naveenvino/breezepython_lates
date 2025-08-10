"""
Update Breeze API Session Token
Usage: python update_session.py <session_token_or_url>
"""
import sys
import re
from pathlib import Path

def update_session_token(token_or_url):
    """Extract token from URL or use direct token and update .env file"""
    
    # Extract token from URL if provided
    if 'apisession=' in token_or_url:
        match = re.search(r'apisession=(\d+)', token_or_url)
        if match:
            token = match.group(1)
        else:
            print("Error: Could not extract session token from URL")
            return False
    else:
        # Assume it's a direct token
        token = token_or_url.strip()
    
    # Read .env file
    env_path = Path('.env')
    if not env_path.exists():
        print("Error: .env file not found")
        return False
    
    lines = env_path.read_text().splitlines()
    
    # Update the token
    updated = False
    for i, line in enumerate(lines):
        if line.startswith('BREEZE_API_SESSION='):
            lines[i] = f'BREEZE_API_SESSION={token}'
            updated = True
            break
    
    if not updated:
        # Add the token if not found
        lines.append(f'BREEZE_API_SESSION={token}')
    
    # Write back to file
    env_path.write_text('\n'.join(lines) + '\n')
    
    print(f"✅ Successfully updated Breeze session token to: {token}")
    print("📝 Updated in .env file")
    print("🔄 Please restart your API server for changes to take effect")
    
    return True

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python update_session.py <session_token_or_url>")
        print("\nExamples:")
        print("  python update_session.py 52547680")
        print('  python update_session.py "https://localhost:56412/?apisession=52547680"')
        sys.exit(1)
    
    token_or_url = sys.argv[1]
    
    if update_session_token(token_or_url):
        print("\n💡 Next steps:")
        print("1. Restart the API server: python unified_api_correct.py")
        print("2. Test the connection in your browser dashboard")
        print("3. Run a backtest to verify everything is working")