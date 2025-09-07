#!/usr/bin/env python3
"""
PRODUCTION-READY BreezeConnect Trading API
All critical issues fixed, production-grade implementation
"""
import os
import sys
import logging
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

# Standard library imports
import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import production components
from src.core.exceptions import BaseAppException, exception_handler
from src.core.risk_manager import get_risk_manager
from src.core.audit_logger import get_audit_logger, AuditEventType, AuditSeverity
from src.core.monitoring import get_monitoring_system, record_api_request
from src.core.security import get_security_manager, get_current_user
from src.core.backup_manager import get_backup_manager
from src.infrastructure.database.connection_pool import get_connection_pool, health_check_databases
from src.middleware.rate_limiter import create_rate_limiter_middleware

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/production_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create FastAPI app with production settings
app = FastAPI(
    title="BreezeConnect Trading System - Production",
    version="2.0.0",
    description="Production-grade algorithmic trading system with comprehensive risk management",
    docs_url="/docs",
    redoc_url="/redoc",
    debug=False
)

# Configure CORS for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('ALLOWED_ORIGINS', '*').split(','),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Add rate limiting middleware
rate_limiter = create_rate_limiter_middleware(
    requests_per_minute=int(os.getenv('RATE_LIMIT_PER_MINUTE', '60')),
    requests_per_hour=int(os.getenv('RATE_LIMIT_PER_HOUR', '1000')),
    burst_size=int(os.getenv('BURST_LIMIT', '10'))
)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    return await rate_limiter.middleware(request, call_next)

@app.middleware("http")
async def monitoring_middleware(request: Request, call_next):
    """Monitoring and audit middleware"""
    start_time = datetime.utcnow()
    
    # Get client info
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    try:
        response = await call_next(request)
        
        # Calculate response time
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Record metrics
        record_api_request(
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code,
            response_time_ms=response_time
        )
        
        # Log API access
        audit_logger = get_audit_logger()
        audit_logger.log_api_access(
            endpoint=request.url.path,
            method=request.method,
            status_code=response.status_code,
            ip_address=client_ip,
            user_agent=user_agent,
            response_time=response_time
        )
        
        return response
        
    except Exception as e:
        # Log error
        audit_logger = get_audit_logger()
        audit_logger.log_error(
            f"API error: {str(e)}",
            details={
                'endpoint': request.url.path,
                'method': request.method,
                'client_ip': client_ip
            },
            severity=AuditSeverity.ERROR
        )
        
        # Re-raise for global exception handler
        raise

@app.on_event("startup")
async def startup_event():
    """Production startup sequence"""
    logger.info("Starting BreezeConnect Trading API v2.0.0")
    
    try:
        # Initialize all production systems
        audit_logger = get_audit_logger()
        audit_logger.log_system_event("start", {"version": "2.0.0"})
        
        # Initialize database connection pool
        conn_pool = get_connection_pool()
        health = health_check_databases()
        logger.info(f"Database health: {health}")
        
        # Initialize risk manager
        risk_manager = get_risk_manager()
        logger.info("Risk management system active")
        
        # Initialize monitoring
        monitoring = get_monitoring_system()
        monitoring.start_monitoring()
        logger.info("Monitoring system active")
        
        # Initialize security manager
        security_manager = get_security_manager()
        logger.info("Security system active")
        
        # Initialize backup manager
        backup_manager = get_backup_manager()
        logger.info("Backup system active")
        
        logger.info("✅ All production systems initialized successfully")
        
    except Exception as e:
        logger.critical(f"❌ STARTUP FAILED: {e}")
        sys.exit(1)

@app.on_event("shutdown")
async def shutdown_event():
    """Production shutdown sequence"""
    logger.info("Shutting down BreezeConnect Trading API")
    
    try:
        # Log shutdown
        audit_logger = get_audit_logger()
        audit_logger.log_system_event("stop")
        
        # Stop monitoring
        monitoring = get_monitoring_system()
        monitoring.stop_monitoring()
        
        # Close database connections
        conn_pool = get_connection_pool()
        conn_pool.close_all()
        
        # Save risk manager state
        risk_manager = get_risk_manager()
        risk_manager.save_state()
        
        logger.info("✅ Graceful shutdown completed")
        
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

@app.exception_handler(Exception)
async def production_exception_handler(request: Request, exc: Exception):
    """Production-grade global exception handler"""
    
    # Get client information
    client_ip = request.client.host if request.client else "unknown"
    
    # Log error with audit logger
    audit_logger = get_audit_logger()
    audit_logger.log_error(
        str(exc),
        details={
            "endpoint": str(request.url.path),
            "method": request.method,
            "client_ip": client_ip,
            "user_agent": request.headers.get("user-agent", "unknown")
        },
        severity=AuditSeverity.ERROR
    )
    
    # Handle the exception
    error_response = exception_handler.handle_exception(exc, {
        "endpoint": str(request.url.path),
        "method": request.method,
        "client_ip": client_ip
    })
    
    # Determine appropriate status code
    status_code = 500
    if isinstance(exc, BaseAppException):
        if exc.category.value == "authentication":
            status_code = 401
        elif exc.category.value == "validation":
            status_code = 400
        elif "not_found" in exc.error_code.lower():
            status_code = 404
        elif "rate_limit" in exc.error_code.lower():
            status_code = 429
    
    return JSONResponse(
        status_code=status_code,
        content=error_response
    )

# =============================================================================
# HEALTH CHECK ENDPOINTS
# =============================================================================

@app.get("/health", tags=["System"])
async def comprehensive_health_check():
    """Production health check endpoint"""
    try:
        # Database health
        db_health = health_check_databases()
        
        # Risk manager status
        risk_manager = get_risk_manager()
        risk_status = risk_manager.get_risk_status()
        
        # Security status
        security_manager = get_security_manager()
        security_status = security_manager.get_security_status()
        
        # Monitoring status
        monitoring = get_monitoring_system()
        metrics_summary = monitoring.get_metrics_summary()
        active_alerts = monitoring.get_active_alerts()
        
        # Backup status
        backup_manager = get_backup_manager()
        backup_status = backup_manager.get_backup_status()
        
        overall_health = (
            db_health.get("healthy", False) and
            len(active_alerts) == 0 and
            not any(cb["triggered"] for cb in risk_status["circuit_breakers"].values())
        )
        
        health_data = {
            "status": "healthy" if overall_health else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0",
            "components": {
                "database": db_health,
                "risk_management": {
                    "healthy": risk_status["market_open"],
                    "active_positions": risk_status["positions"]["count"],
                    "circuit_breakers": sum(1 for cb in risk_status["circuit_breakers"].values() if cb["triggered"])
                },
                "security": {
                    "healthy": True,
                    "active_sessions": security_status["active_sessions"],
                    "recent_security_events": security_status["recent_security_events"]
                },
                "monitoring": {
                    "healthy": True,
                    "active_alerts": len(active_alerts),
                    "tracked_metrics": len(metrics_summary["metrics"])
                },
                "backup": {
                    "healthy": True,
                    "total_backups": backup_status["total_backups"],
                    "last_backup": backup_status.get("last_backup")
                }
            }
        }
        
        return health_data
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")

@app.get("/health/readiness", tags=["System"])
async def readiness_probe():
    """Kubernetes readiness probe"""
    try:
        # Quick database check
        health = health_check_databases()
        if not health.get("healthy"):
            raise HTTPException(status_code=503, detail="Database not healthy")
        
        # Check critical systems
        risk_manager = get_risk_manager()
        risk_status = risk_manager.get_risk_status()
        
        # Fail if any critical circuit breakers are triggered
        critical_breakers = ['daily_loss', 'exposure_limit']
        for breaker_name in critical_breakers:
            if risk_status["circuit_breakers"].get(breaker_name, {}).get("triggered"):
                raise HTTPException(status_code=503, detail=f"Critical circuit breaker active: {breaker_name}")
        
        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Not ready: {str(e)}")

# =============================================================================
# SETTINGS ENDPOINTS WITH PRODUCTION FEATURES
# =============================================================================

@app.get("/settings/{key}", tags=["Settings"])
async def get_setting(key: str, current_user: Dict = Depends(get_current_user)):
    """Get setting with authentication and audit logging"""
    try:
        from src.infrastructure.database.connection_pool import get_sqlite_session
        
        with get_sqlite_session() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    category TEXT DEFAULT 'general',
                    created_by TEXT,
                    updated_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute("SELECT value, category FROM settings WHERE key = ?", (key,))
            result = cursor.fetchone()
            
            if result:
                value = json.loads(result[0])
                
                # Audit log the access
                audit_logger = get_audit_logger()
                audit_logger.log_event(
                    AuditEventType.CONFIG_CHANGED,
                    {"action": "read", "key": key},
                    user_id=current_user["user_id"]
                )
                
                return {"key": key, "value": value, "category": result[1]}
            else:
                raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting setting {key}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# =============================================================================
# RISK MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/risk/status", tags=["Risk Management"])
async def get_risk_status(current_user: Dict = Depends(get_current_user)):
    """Get comprehensive risk status"""
    try:
        risk_manager = get_risk_manager()
        return risk_manager.get_risk_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/risk/emergency-stop", tags=["Risk Management"])
async def emergency_stop(current_user: Dict = Depends(get_current_user)):
    """Emergency stop all trading operations"""
    try:
        risk_manager = get_risk_manager()
        
        # Trigger circuit breaker
        risk_manager._trigger_circuit_breaker(
            "emergency_stop", 
            f"Emergency stop triggered by user {current_user['user_id']}"
        )
        
        # Log the action
        audit_logger = get_audit_logger()
        audit_logger.log_event(
            AuditEventType.CIRCUIT_BREAKER_TRIGGERED,
            {"breaker": "emergency_stop", "triggered_by": current_user["user_id"]},
            severity=AuditSeverity.CRITICAL,
            user_id=current_user["user_id"]
        )
        
        return {
            "status": "success",
            "message": "Emergency stop activated",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# MONITORING ENDPOINTS
# =============================================================================

@app.get("/monitoring/metrics", tags=["Monitoring"])
async def get_metrics(current_user: Dict = Depends(get_current_user)):
    """Get system metrics"""
    try:
        monitoring = get_monitoring_system()
        return monitoring.get_metrics_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/monitoring/alerts", tags=["Monitoring"])
async def get_active_alerts(current_user: Dict = Depends(get_current_user)):
    """Get active monitoring alerts"""
    try:
        monitoring = get_monitoring_system()
        alerts = monitoring.get_active_alerts()
        
        return {
            "active_alerts": [
                {
                    "name": alert.name,
                    "severity": alert.severity.value,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "details": alert.details
                }
                for alert in alerts
            ],
            "count": len(alerts),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# BACKUP ENDPOINTS
# =============================================================================

@app.get("/backup/status", tags=["Backup"])
async def get_backup_status(current_user: Dict = Depends(get_current_user)):
    """Get backup system status"""
    try:
        backup_manager = get_backup_manager()
        return backup_manager.get_backup_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/backup/create", tags=["Backup"])
async def create_backup(
    backup_type: str = "full",
    current_user: Dict = Depends(get_current_user)
):
    """Create backup manually"""
    try:
        backup_manager = get_backup_manager()
        
        if backup_type == "full":
            backup_path = backup_manager.create_full_backup()
        elif backup_type == "config":
            backup_path = backup_manager.backup_configuration()
        elif backup_type == "data":
            backup_path = backup_manager.backup_trade_data()
        else:
            raise HTTPException(status_code=400, detail=f"Invalid backup type: {backup_type}")
        
        if backup_path:
            # Log the backup creation
            audit_logger = get_audit_logger()
            audit_logger.log_event(
                AuditEventType.CONFIG_CHANGED,
                {
                    "action": "backup_created",
                    "backup_type": backup_type,
                    "backup_path": backup_path
                },
                user_id=current_user["user_id"]
            )
            
            return {
                "status": "success",
                "backup_path": backup_path,
                "backup_type": backup_type,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Backup creation failed")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# AUDIT ENDPOINTS
# =============================================================================

@app.get("/audit/logs", tags=["Audit"])
async def get_audit_logs(
    event_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    current_user: Dict = Depends(get_current_user)
):
    """Get audit logs with filtering"""
    try:
        audit_logger = get_audit_logger()
        logs = audit_logger.get_audit_logs(
            event_type=event_type,
            user_id=current_user["user_id"],  # Filter by current user
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
        
        return {
            "logs": logs,
            "count": len(logs),
            "filtered_by_user": current_user["user_id"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# STATIC FILE SERVING
# =============================================================================

@app.get("/")
async def serve_index():
    """Serve main dashboard"""
    return FileResponse("tradingview_pro.html")

@app.get("/{filename}.html")
async def serve_html(filename: str):
    """Serve HTML files with security checks"""
    try:
        # Validate filename to prevent path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        
        file_path = f"{filename}.html"
        if not Path(file_path).exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(file_path)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")

# =============================================================================
# PRODUCTION UTILITIES
# =============================================================================

def kill_existing_process_on_port(port: int):
    """Kill existing process on specified port (production-safe)"""
    try:
        import psutil
        for conn in psutil.net_connections():
            if (hasattr(conn, 'laddr') and conn.laddr and 
                conn.laddr.port == port and conn.status == 'LISTEN'):
                try:
                    process = psutil.Process(conn.pid)
                    process.terminate()
                    logger.info(f"Terminated existing process on port {port}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    except ImportError:
        logger.warning("psutil not available - cannot kill existing processes")
    except Exception as e:
        logger.warning(f"Could not kill process on port {port}: {e}")

if __name__ == "__main__":
    # Production startup
    try:
        # Ensure logs directory exists
        Path("logs").mkdir(exist_ok=True)
        Path("data").mkdir(exist_ok=True)
        
        # Kill any existing process
        kill_existing_process_on_port(8000)
        
        # Small delay for port release
        import time
        time.sleep(2)
        
        # Production server configuration
        logger.info("Starting Production BreezeConnect Trading API on port 8000...")
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True,
            workers=1,  # Single worker for trading system consistency
            reload=False,  # No reload in production
            debug=False
        )
        
    except Exception as e:
        logger.critical(f"Failed to start production API: {e}")
        sys.exit(1)