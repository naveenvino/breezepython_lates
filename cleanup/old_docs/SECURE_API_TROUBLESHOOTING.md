# Secure API Troubleshooting Guide

## Common Issues and Solutions

### 1. Import Errors (redis, distutils, etc.)

**Problem:**
```
KeyboardInterrupt during reload
ImportError: cannot import name 'redis'
ModuleNotFoundError: No module named 'distutils'
```

**Solution:**
Use the stable version instead:
```bash
python unified_api_secure_stable.py
```
Or use the launcher:
```bash
python start_secure_api.py
# Choose option 1 (Stable Version)
```

### 2. Port Already in Use

**Problem:**
```
[Errno 10048] Only one usage of each socket address is permitted
```

**Solution:**
```bash
# Option 1: Use the smart launcher
python start_secure_api.py
# It will offer to kill the existing process

# Option 2: Manually kill the process
netstat -ano | findstr :8001
taskkill /F /PID [PID_NUMBER]

# Option 3: Use a different port
# Edit unified_api_secure_stable.py and change port to 8002
```

### 3. Auto-reload Causing Issues

**Problem:**
```
WatchFiles detected changes... Reloading...
[Import errors follow]
```

**Solution:**
The stable version has reload disabled by default. If using the original version, disable reload:
```python
# In unified_api_secure.py, change:
reload=False  # Instead of True
```

### 4. Authentication Not Working

**Problem:**
```
{"detail": "Not authenticated"}
```

**Solution:**
```bash
# 1. Get a token first:
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}'

# 2. Use the token in requests:
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8001/api/protected-example
```

### 5. Original API Endpoints Not Available

**Problem:**
```
{"detail": "Endpoint /backtest not found"}
```

**Solution:**
The stable version runs independently. To access original endpoints:
1. Run the original API on port 8000: `python unified_api_correct.py`
2. Run secure API on port 8001: `python unified_api_secure_stable.py`
3. Access through the appropriate port

### 6. CORS Errors in Browser

**Problem:**
```
Access to fetch at 'http://localhost:8001' from origin 'http://localhost:8000' has been blocked by CORS
```

**Solution:**
The stable version allows all origins in development. If still having issues:
1. Access the UI through the same port as the API
2. Or add your origin to the CORS configuration

### 7. Rate Limiting Too Strict

**Problem:**
```
{"error": "Rate limit exceeded"}
```

**Solution:**
In development, rate limiting is more lenient. To adjust:
```python
# In unified_api_secure_stable.py
rate_limiter = SimpleRateLimiter(requests_per_minute=120)  # Increase limit
```

## Quick Fixes

### Reset Everything
```bash
# 1. Kill all Python processes
taskkill /F /IM python.exe

# 2. Clear Python cache
rmdir /s /q __pycache__
rmdir /s /q .pytest_cache

# 3. Restart with stable version
python unified_api_secure_stable.py
```

### Test If Working
```bash
# Quick health check
curl http://localhost:8001/health

# Should return:
{
  "status": "healthy",
  "environment": "development",
  "security": "enabled",
  "version": "2.0.0"
}
```

### Switch Between Versions

**Use Stable Version (Recommended):**
```bash
run_secure_api_stable.bat
# OR
python unified_api_secure_stable.py
```

**Use Original Version:**
```bash
run_secure_api.bat
# OR
python unified_api_secure.py
```

**Use Smart Launcher:**
```bash
python start_secure_api.py
# Interactive menu to choose version
```

## File Comparison

| File | Purpose | Stability | Use When |
|------|---------|-----------|----------|
| `unified_api_secure.py` | Original secure wrapper | Medium | Full integration needed |
| `unified_api_secure_stable.py` | Stable standalone version | High | **Recommended for most cases** |
| `start_secure_api.py` | Smart launcher | High | Want easy startup with options |

## Best Practices

1. **Always use the stable version** unless you need specific integration
2. **Don't use auto-reload** with the secure API
3. **Run on different ports** if running multiple versions
4. **Check port availability** before starting
5. **Use the test page** to verify: http://localhost:8001/test_api_switch.html

## Still Having Issues?

1. Check the console output for specific error messages
2. Verify Python version: `python --version` (Should be 3.8+)
3. Check if virtual environment is activated
4. Ensure .env file exists (even if empty)
5. Try the simplest test first: `curl http://localhost:8001/health`

## Emergency Fallback

If nothing works, just use the original API without security:
```bash
python unified_api_correct.py
# Access at http://localhost:8000
# No authentication needed
```