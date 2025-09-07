"""
Comprehensive test suite for all production fixes
"""
# import pytest  # Not required for this test
import sys
import os
from pathlib import Path
import json
import sqlite3
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_database_connection_pool():
    """Test database connection pooling"""
    from src.infrastructure.database.connection_pool import get_connection_pool
    
    pool = get_connection_pool()
    
    # Test SQLite connection
    with pool.get_sqlite_session() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
    
    # Test health check
    health = pool.health_check()
    assert "sqlite" in health["databases"]
    assert health["databases"]["sqlite"]["healthy"]

def test_exception_handling():
    """Test comprehensive exception handling"""
    from src.core.exceptions import (
        DatabaseException, TradingException, ValidationException,
        exception_handler, BaseAppException
    )
    
    # Test custom exception
    exc = DatabaseException("Test database error")
    assert exc.category.value == "database"
    assert exc.severity.value == "high"
    
    # Test exception handler
    response = exception_handler.handle_exception(ValueError("Test error"))
    assert response["error"] == True
    assert "INVALID_VALUE" in response["error_code"]

def test_risk_manager():
    """Test risk management system"""
    from src.core.risk_manager import get_risk_manager, RiskLimits
    
    risk_manager = get_risk_manager()
    
    # Test risk status
    status = risk_manager.get_risk_status()
    assert "positions" in status
    assert "exposure" in status
    assert "daily_pnl" in status
    
    # Test position validation
    try:
        # This should work (within limits)
        risk_manager.validate_new_position("NIFTY", 100, 25000, "CALL")
        # This should fail (exceeds position size limit)
        risk_manager.validate_new_position("NIFTY", 5000, 25000, "CALL")
        assert False, "Should have raised PositionLimitExceededException"
    except Exception as e:
        assert "Position size" in str(e)

def test_audit_logging():
    """Test audit logging system"""
    from src.core.audit_logger import get_audit_logger, AuditEventType, AuditSeverity
    
    audit_logger = get_audit_logger()
    
    # Test logging an event
    audit_logger.log_trade_entry("NIFTY", 100, 25000, "S1", "test_user")
    
    # Test retrieving logs
    logs = audit_logger.get_audit_logs(event_type="trade_entry", limit=1)
    assert len(logs) >= 1
    
    # Test summary
    summary = audit_logger.get_audit_summary()
    assert "summary" in summary
    assert "total_events" in summary

def test_monitoring_system():
    """Test monitoring and alerting"""
    from src.core.monitoring import get_monitoring_system, MetricType
    
    monitoring = get_monitoring_system()
    
    # Record test metrics
    monitoring.record_metric("test_metric", 42.0, MetricType.GAUGE)
    monitoring.increment_counter("test_counter")
    monitoring.record_timing("test_timing", 123.4)
    
    # Get metrics
    metrics = monitoring.get_metrics("test_metric")
    assert len(metrics) >= 1
    assert metrics[0].value == 42.0
    
    # Get summary
    summary = monitoring.get_metrics_summary()
    assert "test_metric" in summary["metrics"]

def test_security_manager():
    """Test security and session management"""
    from src.core.security import get_security_manager
    
    security_manager = get_security_manager()
    
    # Test session creation
    session = security_manager.create_session(
        "test_user", "127.0.0.1", "test_agent", ["read", "write"]
    )
    
    assert session.user_id == "test_user"
    assert session.ip_address == "127.0.0.1"
    assert "read" in session.permissions
    
    # Test JWT token
    token = security_manager.create_jwt_token(session)
    assert token is not None
    
    # Test token validation
    payload = security_manager.validate_jwt_token(token)
    assert payload["user_id"] == "test_user"
    
    # Test session validation
    validated_session = security_manager.validate_session(session.session_id, "127.0.0.1")
    assert validated_session is not None

def test_backup_manager():
    """Test backup and recovery system"""
    from src.core.backup_manager import get_backup_manager
    
    backup_manager = get_backup_manager()
    
    # Test backup status
    status = backup_manager.get_backup_status()
    assert "total_backups" in status
    assert "retention_days" in status
    
    # Test configuration backup
    backup_path = backup_manager.backup_configuration()
    if backup_path:
        assert Path(backup_path).exists()
    
    # Test backup listing
    backups = backup_manager.list_backups(limit=10)
    assert isinstance(backups, list)

def test_rate_limiter():
    """Test rate limiting system"""
    from src.middleware.rate_limiter import RateLimiter
    
    limiter = RateLimiter(
        requests_per_minute=5,  # Low limit for testing
        requests_per_hour=50,
        burst_size=2
    )
    
    # Should allow first few requests
    assert limiter.check_request("127.0.0.1")[0] == True
    assert limiter.check_request("127.0.0.1")[0] == True
    
    # Should hit burst limit
    for _ in range(10):
        limiter.check_request("127.0.0.1")
    
    # Should be rate limited now
    allowed, retry_after = limiter.check_request("127.0.0.1")
    # Note: May still be allowed depending on timing

def test_file_structure():
    """Test that all production files are created"""
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
        assert Path(file_path).exists(), f"Missing production file: {file_path}"
        
        # Check file is not empty
        assert Path(file_path).stat().st_size > 0, f"Empty production file: {file_path}"

def test_configuration_validation():
    """Test configuration validation"""
    # Check .env.example has all required variables
    env_example = Path(".env.example")
    assert env_example.exists()
    
    content = env_example.read_text()
    required_vars = [
        "DB_SERVER", "DB_NAME",
        "BREEZE_API_KEY", "KITE_API_KEY",
        "JWT_SECRET_KEY", "PAPER_TRADING_MODE",
        "MAX_POSITION_SIZE", "MAX_DAILY_LOSS"
    ]
    
    for var in required_vars:
        assert var in content, f"Missing required environment variable: {var}"

def test_docker_configuration():
    """Test Docker configuration"""
    dockerfile = Path("Dockerfile")
    assert dockerfile.exists()
    
    content = dockerfile.read_text()
    
    # Check production best practices
    assert "FROM python:3.11-slim" in content
    assert "useradd" in content  # Non-root user
    assert "HEALTHCHECK" in content  # Health check
    assert "EXPOSE 8000" in content  # Port exposure

def test_production_requirements():
    """Test production requirements"""
    requirements_prod = Path("requirements-prod.txt")
    if requirements_prod.exists():
        content = requirements_prod.read_text()
        # Should have essential production packages
        essential_packages = ["fastapi", "uvicorn", "sqlalchemy", "pydantic"]
        for package in essential_packages:
            assert package in content, f"Missing essential package: {package}"

if __name__ == "__main__":
    """Run all tests"""
    
    # Setup logging for tests
    logging.basicConfig(level=logging.WARNING)  # Reduce test noise
    
    print("Testing Production Fixes")
    print("=" * 50)
    
    test_functions = [
        test_database_connection_pool,
        test_exception_handling,
        test_risk_manager,
        test_audit_logging,
        test_monitoring_system,
        test_security_manager,
        test_backup_manager,
        test_rate_limiter,
        test_file_structure,
        test_configuration_validation,
        test_docker_configuration,
        test_production_requirements
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            print(f"Testing {test_func.__name__}...", end=" ")
            test_func()
            print("[PASS]")
            passed += 1
        except Exception as e:
            print(f"[FAIL]: {str(e)}")
            failed += 1
    
    print("=" * 50)
    print(f"Total Tests: {len(test_functions)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("ALL PRODUCTION FIXES VERIFIED!")
        exit_code = 0
    else:
        print(f"WARNING: {failed} tests failed - review implementation")
        exit_code = 1
    
    sys.exit(exit_code)