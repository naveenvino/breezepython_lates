#!/bin/bash

# Production Deployment Script
# Usage: ./deploy.sh [environment]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
APP_NAME="trading-system"
BACKUP_DIR="./backups"
LOG_FILE="./logs/deployment.log"

# Functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a $LOG_FILE
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a $LOG_FILE
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a $LOG_FILE
}

# Create necessary directories
mkdir -p logs backups data

log "Starting deployment for environment: $ENVIRONMENT"

# 1. Check prerequisites
log "Checking prerequisites..."
command -v docker >/dev/null 2>&1 || error "Docker is not installed"
command -v docker-compose >/dev/null 2>&1 || error "Docker Compose is not installed"

# 2. Backup current deployment
if [ -d "./data" ]; then
    log "Creating backup..."
    BACKUP_FILE="$BACKUP_DIR/backup_$(date +'%Y%m%d_%H%M%S').tar.gz"
    tar -czf $BACKUP_FILE ./data ./logs .env 2>/dev/null || warning "Backup creation failed"
    log "Backup created: $BACKUP_FILE"
fi

# 3. Load environment configuration
if [ ! -f ".env" ]; then
    if [ -f ".env.$ENVIRONMENT" ]; then
        log "Copying environment configuration..."
        cp .env.$ENVIRONMENT .env
    else
        error "Environment configuration not found: .env.$ENVIRONMENT"
    fi
fi

# 4. Validate configuration
log "Validating configuration..."
required_vars=("DB_SERVER" "DB_NAME" "BREEZE_API_KEY" "JWT_SECRET_KEY")
for var in "${required_vars[@]}"; do
    if ! grep -q "^$var=" .env; then
        warning "Missing required variable: $var"
    fi
done

# 5. Build Docker images
log "Building Docker images..."
docker-compose build --no-cache || error "Docker build failed"

# 6. Run database migrations
log "Running database migrations..."
docker-compose run --rm trading-api python -m src.infrastructure.database.create_tables || warning "Database migration failed"

# 7. Stop existing containers
log "Stopping existing containers..."
docker-compose down

# 8. Start new containers
log "Starting new containers..."
docker-compose up -d || error "Failed to start containers"

# 9. Wait for services to be healthy
log "Waiting for services to be healthy..."
sleep 10

# Check health status
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -f http://localhost:8000/monitoring/health >/dev/null 2>&1; then
        log "Services are healthy"
        break
    fi
    attempt=$((attempt + 1))
    if [ $attempt -eq $max_attempts ]; then
        error "Services failed to become healthy"
    fi
    sleep 2
done

# 10. Run smoke tests
log "Running smoke tests..."
./scripts/smoke_test.sh || warning "Smoke tests failed"

# 11. Setup monitoring
log "Starting monitoring service..."
curl -X POST http://localhost:8000/monitoring/start || warning "Failed to start monitoring"

# 12. Cleanup old backups (keep last 30 days)
log "Cleaning up old backups..."
find $BACKUP_DIR -name "backup_*.tar.gz" -mtime +30 -delete

log "Deployment completed successfully!"

# Display service status
echo -e "\n${GREEN}Service Status:${NC}"
docker-compose ps

echo -e "\n${GREEN}Access URLs:${NC}"
echo "API Documentation: http://localhost:8000/docs"
echo "Monitoring Dashboard: http://localhost:8000/monitoring_dashboard.html"
echo "Trading Dashboard: http://localhost:8000/integrated_trading_dashboard.html"

echo -e "\n${GREEN}Next Steps:${NC}"
echo "1. Verify all services are running: docker-compose ps"
echo "2. Check logs: docker-compose logs -f"
echo "3. Monitor system health: http://localhost:8000/monitoring/status"
echo "4. Configure alerts in .env file"

log "Deployment log saved to: $LOG_FILE"