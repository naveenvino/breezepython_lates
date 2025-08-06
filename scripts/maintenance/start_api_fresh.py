"""
Start API with explicit reload
"""
import os
import sys
import uvicorn

# Make sure we're using the latest code
print("Starting API from fresh process...")
print(f"Python path: {sys.executable}")
print(f"Current dir: {os.getcwd()}")

# Force reload of the module
if 'main_api' in sys.modules:
    del sys.modules['main_api']

# Start the API
if __name__ == "__main__":
    uvicorn.run(
        "main_api:app", 
        host="0.0.0.0", 
        port=8001, 
        reload=False,  # Disable reload to ensure fresh start
        log_level="info"
    )