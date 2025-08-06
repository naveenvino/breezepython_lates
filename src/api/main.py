"""
Main API Application
FastAPI application with clean architecture
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from ..config.settings import get_settings
from ..infrastructure.di.container import get_container, get_service
from ..infrastructure.database import get_db_manager

# Import routers
from .routers import backtest_router, signals_router, test_router
from .routers.working_backtest_router import router as working_backtest_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup
    logger.info("Starting KiteApp Python API...")
    
    # Initialize settings
    settings = get_settings()
    logger.info(f"Environment: {settings.app.environment}")
    
    # Test database connection
    db_manager = get_db_manager()
    if db_manager.test_connection():
        logger.info("Database connection successful")
    else:
        logger.warning("Database connection failed")
    
    # Initialize DI container
    container = get_container()
    logger.info("Dependency injection container initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down KiteApp Python API...")
    
    # Close database connections
    db_manager.close()


# Create FastAPI app
app = FastAPI(
    title="KiteApp Python API",
    description="Clean Architecture Trading Platform API",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
# Removed unused routers - only backtest and signals are used
app.include_router(backtest_router.router, prefix="/api/v2/backtest", tags=["Backtesting"])
app.include_router(signals_router.router, tags=["Signal Testing"])
app.include_router(test_router.router, prefix="/api/v2/test", tags=["Testing"])
app.include_router(working_backtest_router, prefix="/api/v2/working", tags=["Working Backtest"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "KiteApp Python API - Clean Architecture",
        "version": "2.0.0",
        "status": "running"
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database
        db_manager = get_db_manager()
        db_healthy = db_manager.test_connection()
        
        # Overall health
        healthy = db_healthy
        
        return {
            "status": "healthy" if healthy else "degraded",
            "checks": {
                "database": "healthy" if db_healthy else "unhealthy"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.app.debug else "An error occurred"
        }
    )


def run():
    """Run the application"""
    settings = get_settings()
    uvicorn.run(
        "src.api.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.environment == "development"
    )


if __name__ == "__main__":
    run()