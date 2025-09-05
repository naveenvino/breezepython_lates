# Trading System - Production Deployment Guide

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Deployment Options](#deployment-options)
4. [Configuration](#configuration)
5. [Deployment Steps](#deployment-steps)
6. [Post-Deployment](#post-deployment)
7. [Monitoring](#monitoring)
8. [Backup & Recovery](#backup--recovery)
9. [Troubleshooting](#troubleshooting)
10. [Security Checklist](#security-checklist)

## Overview

This guide covers the deployment of the Trading System to a production environment. The system supports both containerized (Docker) and traditional deployment methods.

### System Architecture
- **API Server**: FastAPI application serving REST endpoints
- **Database**: SQL Server for data persistence
- **Cache**: Redis for performance optimization (optional)
- **Monitoring**: Built-in monitoring and alerting system
- **Web Server**: Nginx for reverse proxy and load balancing (optional)

## Prerequisites

### Required Software
- Python 3.11+ OR Docker & Docker Compose
- SQL Server (LocalDB or full instance)
- Git (for version control)

### Optional Software
- Redis (for caching)
- Nginx (for reverse proxy)
- SSL certificates (for HTTPS)

### System Requirements
- **CPU**: 4+ cores recommended
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 50GB+ for data and backups
- **Network**: Stable internet connection for trading APIs

## Deployment Options

### Option 1: Docker Deployment (Recommended)
Best for: Production environments, scalability, isolation

```bash
# Deploy with Docker
./scripts/deploy.sh production
```

### Option 2: Direct Python Deployment
Best for: Development, Windows environments, simpler setups

```batch
# Deploy on Windows
scripts\start_production.bat
```

## Configuration

### 1. Environment Setup

Copy the production environment template:
```bash
cp .env.production .env
```

### 2. Required Configuration

Edit `.env` file with your values:

```env
# Database
DB_SERVER=your_sql_server
DB_NAME=your_database_name
DB_USER=your_db_user        # Optional for Windows Auth
DB_PASSWORD=your_db_password # Optional for Windows Auth

# Breeze API (Required)
BREEZE_API_KEY=your_breeze_api_key
BREEZE_API_SECRET=your_breeze_api_secret
BREEZE_API_SESSION=your_session_token

# Kite API (Optional)
KITE_API_KEY=your_kite_api_key
KITE_API_SECRET=your_kite_api_secret
KITE_ACCESS_TOKEN=your_access_token

# Security (Required - Generate new keys!)
JWT_SECRET_KEY=generate_with_openssl_rand_hex_32
ENCRYPTION_MASTER_KEY=generate_with_openssl_rand_hex_32
ADMIN_PASSWORD=change_this_strong_password
```

### 3. Generate Security Keys

```bash
# Generate JWT Secret
openssl rand -hex 32

# Generate Encryption Key
openssl rand -hex 32
```

### 4. Configure Alerts (Optional)

```env
# Email Alerts
EMAIL_ALERTS_ENABLED=true
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
ALERT_FROM_EMAIL=alerts@yourdomain.com
ALERT_TO_EMAILS=admin@yourdomain.com,trader@yourdomain.com

# Webhook Alerts
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

## Deployment Steps

### Docker Deployment

1. **Build and Deploy**
   ```bash
   # Make scripts executable
   chmod +x scripts/*.sh
   
   # Run deployment
   ./scripts/deploy.sh production
   ```

2. **Verify Deployment**
   ```bash
   # Check services
   docker-compose ps
   
   # View logs
   docker-compose logs -f
   
   # Run smoke tests
   ./scripts/smoke_test.sh
   ```

### Windows Direct Deployment

1. **Install Dependencies**
   ```batch
   pip install -r requirements-prod.txt
   ```

2. **Setup Database**
   ```batch
   python -m src.infrastructure.database.create_tables
   ```

3. **Start Services**
   ```batch
   scripts\start_production.bat
   ```

4. **Verify Deployment**
   ```batch
   scripts\smoke_test.bat
   ```

## Post-Deployment

### 1. Initial Setup

1. **Access Admin Panel**
   - URL: http://your-server:8000/docs
   - Default credentials: admin / [your_configured_password]

2. **Configure Trading Parameters**
   ```json
   POST /trading/engine/config
   {
     "enable_paper_trading": true,
     "enable_live_trading": false,
     "max_positions": 5,
     "default_quantity": 750
   }
   ```

3. **Start Monitoring**
   ```bash
   curl -X POST http://localhost:8000/monitoring/start
   ```

### 2. SSL/HTTPS Setup

For production, always use HTTPS:

1. **Obtain SSL Certificate**
   - Use Let's Encrypt for free certificates
   - Or purchase from a CA

2. **Configure Nginx**
   - Update `nginx.conf` with your domain
   - Place certificates in `ssl/` directory

3. **Update Docker Compose**
   ```yaml
   nginx:
     volumes:
       - ./ssl:/etc/nginx/ssl:ro
   ```

### 3. Domain Setup

1. **Configure DNS**
   - Point your domain to server IP
   - Setup A records for main domain
   - Setup CNAME for subdomains if needed

2. **Update Configuration**
   - Update CORS origins in `.env`
   - Update server_name in `nginx.conf`

## Monitoring

### System Monitoring

1. **Dashboard Access**
   - Monitoring: http://your-server:8000/monitoring_dashboard.html
   - Trading: http://your-server:8000/integrated_trading_dashboard.html

2. **API Endpoints**
   ```bash
   # Check system health
   curl http://localhost:8000/monitoring/health
   
   # Get system status
   curl http://localhost:8000/monitoring/status
   
   # View alerts
   curl http://localhost:8000/monitoring/alerts
   ```

3. **Metrics Tracked**
   - CPU, Memory, Disk usage
   - API response times
   - Error rates
   - Trading P&L
   - Active positions

### Alert Thresholds

Default thresholds (configurable in monitoring_service.py):
- CPU Usage > 80%
- Memory Usage > 85%
- Disk Usage > 90%
- API Error Rate > 10%
- Response Time > 2000ms
- Trading Loss > ₹50,000

## Backup & Recovery

### Automated Backups

1. **Schedule Backups**
   ```bash
   # Add to crontab (Linux/Mac)
   0 2 * * * /path/to/scripts/backup.sh
   
   # Or use Windows Task Scheduler
   schtasks /create /tn "TradingBackup" /tr "C:\path\to\scripts\backup.bat" /sc daily /st 02:00
   ```

2. **Manual Backup**
   ```bash
   ./scripts/backup.sh
   # or
   scripts\backup.bat
   ```

### Recovery Process

1. **Stop Services**
   ```bash
   docker-compose down
   # or
   scripts\stop_production.bat
   ```

2. **Restore from Backup**
   ```bash
   # Extract backup
   tar -xzf backups/trading_backup_YYYYMMDD_HHMMSS.tar.gz
   
   # Restore database
   sqlcmd -S server -d database -i database.bak
   
   # Copy data files
   cp -r backup_data/* ./data/
   ```

3. **Restart Services**
   ```bash
   ./scripts/deploy.sh production
   ```

## Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Find process using port
   netstat -ano | findstr :8000
   
   # Kill process
   taskkill /PID <process_id> /F
   ```

2. **Database Connection Failed**
   - Verify SQL Server is running
   - Check connection string in `.env`
   - Test with: `sqlcmd -S server -U user -P password`

3. **API Authentication Failed**
   - Regenerate Breeze session token
   - Update Kite access token daily
   - Check API rate limits

4. **High Memory Usage**
   - Increase swap space
   - Reduce worker count
   - Enable Redis caching
   - Optimize database queries

### Logs Location

- **Application Logs**: `logs/production.log`
- **Error Logs**: `logs/error.log`
- **Trading Logs**: `logs/trading.log`
- **Docker Logs**: `docker-compose logs [service]`

### Debug Mode

Enable debug logging:
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

## Security Checklist

### Pre-Deployment
- [ ] Change all default passwords
- [ ] Generate new JWT secret key
- [ ] Generate new encryption key
- [ ] Review firewall rules
- [ ] Disable unnecessary services
- [ ] Update all dependencies

### API Security
- [ ] Enable rate limiting
- [ ] Configure CORS properly
- [ ] Use HTTPS in production
- [ ] Implement IP whitelisting
- [ ] Enable authentication on all endpoints
- [ ] Rotate API keys regularly

### Database Security
- [ ] Use strong passwords
- [ ] Enable SQL Server authentication
- [ ] Restrict database access
- [ ] Regular backups
- [ ] Encrypt sensitive data

### Monitoring Security
- [ ] Secure monitoring endpoints
- [ ] Configure alert recipients
- [ ] Review log retention
- [ ] Monitor for anomalies

### Network Security
- [ ] Use VPN for remote access
- [ ] Configure firewall rules
- [ ] Disable unused ports
- [ ] Use fail2ban or similar

## Performance Optimization

### API Performance
- Enable Redis caching
- Use connection pooling
- Optimize database queries
- Enable response compression
- Use CDN for static files

### Database Performance
- Add appropriate indexes
- Regular maintenance tasks
- Query optimization
- Connection pooling
- Archive old data

### System Performance
- Monitor resource usage
- Scale horizontally if needed
- Use load balancer
- Optimize worker count
- Enable swap space

## Support

For issues or questions:
1. Check logs first
2. Review this documentation
3. Check GitHub issues
4. Contact support team

## Version History

- v1.0.0 - Initial production release
- v1.1.0 - Added monitoring system
- v1.2.0 - Enhanced security features
- v1.3.0 - Performance optimizations

---

**Important**: Always test in a staging environment before deploying to production!