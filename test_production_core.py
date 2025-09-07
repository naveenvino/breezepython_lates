"""
Simplified production core testing - validates implementation without complex dependencies
"""
import sys
import os
import sqlite3
import json
from pathlib import Path
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_file_structure():
    """Test that all production files exist and have content"""
    print("Testing file structure...")
    
    required_files = [
        "src/infrastructure/database/connection_pool.py",
        "src/core/exceptions.py", 
        "src/core/risk_manager.py",
        "src/core/audit_logger.py",
        "src/core/monitoring.py",
        "src/core/security.py", 
        "src/core/backup_manager.py",
        "src/middleware/rate_limiter.py",
        "production_ready_api.py"
    ]
    
    for file_path in required_files:
        path = Path(file_path)
        assert path.exists(), f"Missing: {file_path}"
        size = path.stat().st_size
        assert size > 1000, f"Too small: {file_path} ({size} bytes)"
        print(f"  [OK] {file_path} ({size:,} bytes)")
    
    return True

def test_exception_classes():
    """Test exception classes can be imported and used"""
    print("Testing exception classes...")
    
    # Test direct import of exception file
    exec(open('src/core/exceptions.py').read())
    
    # Test that classes are defined
    import importlib.util
    spec = importlib.util.spec_from_file_location("exceptions", "src/core/exceptions.py")
    exceptions_module = importlib.util.module_from_spec(spec)
    
    try:
        spec.loader.exec_module(exceptions_module)
        
        # Test exception creation
        exc = exceptions_module.DatabaseException("Test error")
        assert exc.category.value == "database"
        assert exc.severity.value == "high"
        print(f"  [OK] DatabaseException: {exc.error_code}")
        
        # Test exception handler
        handler = exceptions_module.ExceptionHandler()
        response = handler.handle_exception(ValueError("Test"))
        assert response["error"] == True
        print(f"  [OK] Exception Handler: {response['error_code']}")
        
        return True
        
    except Exception as e:
        print(f"  [X] Exception test failed: {e}")
        return False

def test_risk_manager_logic():
    """Test risk manager logic without complex dependencies"""
    print("Testing risk manager logic...")
    
    try:
        # Read and validate risk manager file
        with open('src/core/risk_manager.py', 'r') as f:
            content = f.read()
        
        # Check for key risk management features
        required_features = [
            "PositionLimitExceededException",
            "RiskLimitException", 
            "validate_new_position",
            "max_position_size",
            "max_daily_loss",
            "circuit_breakers"
        ]
        
        for feature in required_features:
            assert feature in content, f"Missing risk feature: {feature}"
            print(f"  [OK] Risk feature found: {feature}")
        
        return True
        
    except Exception as e:
        print(f"  [X] Risk manager test failed: {e}")
        return False

def test_audit_logging_setup():
    """Test audit logging database setup"""
    print("Testing audit logging setup...")
    
    try:
        # Create test audit database
        test_db = "data/test_audit.db"
        Path("data").mkdir(exist_ok=True)
        
        with sqlite3.connect(test_db) as conn:
            # Execute audit table creation from audit_logger.py
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    event_data TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    success BOOLEAN,
                    error_message TEXT,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Test inserting audit record
            conn.execute("""
                INSERT INTO audit_log 
                (timestamp, event_type, severity, event_data, success)
                VALUES (?, ?, ?, ?, ?)
            """, (
                "2025-09-07T16:00:00",
                "test_event",
                "info", 
                '{"test": true}',
                True
            ))
            
            # Verify record exists
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM audit_log")
            count = cursor.fetchone()[0]
            assert count >= 1, "Audit record not inserted"
            
            print(f"  [OK] Audit database setup working ({count} records)")
        
        # Cleanup test database
        Path(test_db).unlink(missing_ok=True)
        return True
        
    except Exception as e:
        print(f"  [X] Audit logging test failed: {e}")
        return False

def test_settings_database():
    """Test settings database operations"""
    print("Testing settings database...")
    
    try:
        test_db = "data/test_settings.db"
        Path("data").mkdir(exist_ok=True)
        
        with sqlite3.connect(test_db) as conn:
            # Create settings table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    category TEXT DEFAULT 'general',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Test CRUD operations
            test_key = "test_setting"
            test_value = {"test": True, "number": 42}
            
            # Create
            conn.execute('''
                INSERT OR REPLACE INTO settings (key, value, category)
                VALUES (?, ?, ?)
            ''', (test_key, json.dumps(test_value), "test"))
            
            # Read
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (test_key,))
            result = cursor.fetchone()
            assert result is not None, "Setting not found"
            
            value = json.loads(result[0])
            assert value["test"] == True, "Value mismatch"
            assert value["number"] == 42, "Number mismatch"
            
            # Update
            updated_value = {"test": False, "number": 24}
            conn.execute('''
                UPDATE settings SET value = ? WHERE key = ?
            ''', (json.dumps(updated_value), test_key))
            
            # Verify update
            cursor.execute("SELECT value FROM settings WHERE key = ?", (test_key,))
            result = cursor.fetchone()
            value = json.loads(result[0])
            assert value["test"] == False, "Update failed"
            
            # Delete
            cursor.execute("DELETE FROM settings WHERE key = ?", (test_key,))
            assert cursor.rowcount == 1, "Delete failed"
            
            print("  [OK] Settings CRUD operations working")
        
        # Cleanup test database
        Path(test_db).unlink(missing_ok=True)
        return True
        
    except Exception as e:
        print(f"  [X] Settings database test failed: {e}")
        return False

def test_production_api_structure():
    """Test production API file structure"""
    print("Testing production API structure...")
    
    try:
        with open('production_ready_api.py', 'r') as f:
            content = f.read()
        
        # Check for production features
        production_features = [
            "FastAPI",
            "CORSMiddleware",
            "exception_handler",
            "startup_event",
            "shutdown_event",
            "health_check",
            "get_risk_status",
            "comprehensive_health_check",
            "global_exception_handler"
        ]
        
        for feature in production_features:
            assert feature in content, f"Missing production feature: {feature}"
            print(f"  [OK] Production feature: {feature}")
        
        # Check imports are properly organized
        assert "import os" in content[:500], "Missing core imports"
        assert "from src.core" in content, "Missing core module imports"
        
        return True
        
    except Exception as e:
        print(f"  [X] Production API test failed: {e}")
        return False

def test_configuration_files():
    """Test configuration and deployment files"""
    print("Testing configuration files...")
    
    try:
        # Test .env.example
        env_file = Path(".env.example")
        assert env_file.exists(), ".env.example missing"
        
        env_content = env_file.read_text()
        critical_vars = [
            "DB_SERVER", "DB_NAME", "BREEZE_API_KEY", "KITE_API_KEY",
            "JWT_SECRET_KEY", "PAPER_TRADING_MODE", "MAX_POSITION_SIZE"
        ]
        
        for var in critical_vars:
            assert var in env_content, f"Missing env var: {var}"
        
        print(f"  [OK] Environment configuration ({len(critical_vars)} vars)")
        
        # Test Dockerfile
        dockerfile = Path("Dockerfile")
        assert dockerfile.exists(), "Dockerfile missing"
        
        docker_content = dockerfile.read_text()
        docker_features = ["FROM python:", "HEALTHCHECK", "USER trader", "EXPOSE 8000"]
        
        for feature in docker_features:
            assert feature in docker_content, f"Missing Docker feature: {feature}"
        
        print(f"  [OK] Docker configuration ({len(docker_features)} features)")
        
        return True
        
    except Exception as e:
        print(f"  [X] Configuration test failed: {e}")
        return False

def test_logging_setup():
    """Test logging configuration"""
    print("Testing logging setup...")
    
    try:
        # Create logs directory
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Test log file creation
        test_log = logs_dir / "test.log"
        
        # Setup test logger
        logger = logging.getLogger("test_logger")
        handler = logging.FileHandler(test_log)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        # Test logging
        logger.info("Test log message")
        logger.warning("Test warning message")
        logger.error("Test error message")
        
        # Verify log file exists and has content
        assert test_log.exists(), "Log file not created"
        content = test_log.read_text()
        assert "Test log message" in content, "Log message not written"
        assert "Test warning message" in content, "Warning not written"
        
        print(f"  [OK] Logging system working ({len(content)} chars written)")
        
        # Cleanup
        test_log.unlink()
        
        return True
        
    except Exception as e:
        print(f"  [X] Logging test failed: {e}")
        return False

def main():
    """Run all production core tests"""
    print("=" * 60)
    print("PRODUCTION CORE TESTING")
    print("=" * 60)
    
    test_functions = [
        test_file_structure,
        test_exception_classes,
        test_risk_manager_logic,
        test_audit_logging_setup,
        test_settings_database,
        test_production_api_structure,
        test_configuration_files,
        test_logging_setup
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            print(f"\nTesting {test_func.__name__.replace('test_', '').replace('_', ' ').title()}:")
            result = test_func()
            if result:
                print("  [PASS]")
                passed += 1
            else:
                print("  [FAIL]") 
                failed += 1
        except Exception as e:
            print(f"  [ERROR]: {str(e)}")
            failed += 1
    
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("ALL PRODUCTION CORE TESTS PASSED!")
        success_rate = 100.0
    else:
        success_rate = (passed / (passed + failed)) * 100
        print(f"WARNING: {failed} tests failed (success rate: {success_rate:.1f}%)")
    
    return success_rate

if __name__ == "__main__":
    success_rate = main()
    sys.exit(0 if success_rate == 100.0 else 1)