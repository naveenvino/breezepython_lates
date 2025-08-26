#!/bin/bash

# Backup Script for Trading System
# Creates timestamped backups of data, logs, and configuration

set -e

# Configuration
BACKUP_DIR=${BACKUP_DIR:-./backups}
RETENTION_DAYS=${RETENTION_DAYS:-30}
TIMESTAMP=$(date +'%Y%m%d_%H%M%S')
BACKUP_NAME="trading_backup_${TIMESTAMP}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

log "Starting backup process..."

# 1. Create temporary backup directory
TEMP_BACKUP_DIR="/tmp/${BACKUP_NAME}"
mkdir -p "$TEMP_BACKUP_DIR"

# 2. Backup database
if command -v sqlcmd >/dev/null 2>&1; then
    log "Backing up database..."
    sqlcmd -S "(localdb)\mssqllocaldb" -d "KiteConnectApi" -Q "BACKUP DATABASE [KiteConnectApi] TO DISK='${TEMP_BACKUP_DIR}/database.bak'" 2>/dev/null || warning "Database backup failed"
fi

# 3. Backup application data
log "Backing up application data..."
directories_to_backup=(
    "data"
    "logs"
    "static"
)

for dir in "${directories_to_backup[@]}"; do
    if [ -d "$dir" ]; then
        cp -r "$dir" "$TEMP_BACKUP_DIR/" || warning "Failed to backup $dir"
        log "Backed up: $dir"
    fi
done

# 4. Backup configuration files
log "Backing up configuration files..."
files_to_backup=(
    ".env"
    "requirements-prod.txt"
    "docker-compose.yml"
    "nginx.conf"
)

for file in "${files_to_backup[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$TEMP_BACKUP_DIR/" || warning "Failed to backup $file"
        log "Backed up: $file"
    fi
done

# 5. Export Docker volumes (if using Docker)
if command -v docker >/dev/null 2>&1; then
    log "Exporting Docker volumes..."
    docker run --rm -v trading-system_redis-data:/data -v "${TEMP_BACKUP_DIR}":/backup alpine tar czf /backup/redis-data.tar.gz -C /data . 2>/dev/null || warning "Redis data export failed"
fi

# 6. Create system info file
log "Creating system info..."
cat > "$TEMP_BACKUP_DIR/backup_info.txt" <<EOF
Backup Information
==================
Date: $(date)
Hostname: $(hostname)
User: $(whoami)
System: $(uname -a)
Docker Version: $(docker --version 2>/dev/null || echo "N/A")
Python Version: $(python --version 2>/dev/null || echo "N/A")

Application Status:
$(curl -s http://localhost:8000/monitoring/status 2>/dev/null || echo "Service not running")

Backup Contents:
$(ls -la "$TEMP_BACKUP_DIR")
EOF

# 7. Compress backup
log "Compressing backup..."
BACKUP_FILE="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
tar -czf "$BACKUP_FILE" -C "/tmp" "${BACKUP_NAME}" || error "Failed to create backup archive"

# 8. Verify backup
log "Verifying backup..."
if tar -tzf "$BACKUP_FILE" >/dev/null 2>&1; then
    log "Backup verified successfully"
else
    error "Backup verification failed"
fi

# 9. Calculate backup size
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "Backup size: $BACKUP_SIZE"

# 10. Cleanup temporary files
rm -rf "$TEMP_BACKUP_DIR"

# 11. Remove old backups
log "Cleaning up old backups (keeping last $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "trading_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

# 12. List recent backups
log "Recent backups:"
ls -lh "$BACKUP_DIR"/trading_backup_*.tar.gz 2>/dev/null | tail -5

log "Backup completed: $BACKUP_FILE"

# Optional: Upload to cloud storage
if [ ! -z "$AWS_S3_BUCKET" ]; then
    log "Uploading to S3..."
    aws s3 cp "$BACKUP_FILE" "s3://${AWS_S3_BUCKET}/backups/" || warning "S3 upload failed"
fi

if [ ! -z "$AZURE_STORAGE_CONTAINER" ]; then
    log "Uploading to Azure..."
    az storage blob upload --container-name "$AZURE_STORAGE_CONTAINER" --file "$BACKUP_FILE" --name "backups/${BACKUP_NAME}.tar.gz" || warning "Azure upload failed"
fi

log "Backup process completed successfully!"