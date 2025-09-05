# PostgreSQL + TimescaleDB Setup Guide

## Installation Steps

### 1. Install PostgreSQL 16
Download from: https://www.postgresql.org/download/windows/
- Choose PostgreSQL 16.x
- Default port: 5432
- Set superuser password (remember this!)

### 2. Install TimescaleDB Extension
```bash
# After PostgreSQL installation, open command prompt as admin
cd "C:\Program Files\PostgreSQL\16\bin"

# Download TimescaleDB
# Visit: https://docs.timescale.com/self-hosted/latest/install/installation-windows/
```

### 3. Create Database and Enable TimescaleDB
```sql
-- Connect to PostgreSQL as superuser
psql -U postgres

-- Create trading database
CREATE DATABASE trading_system;

-- Connect to the new database
\c trading_system

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enable other useful extensions
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

### 4. Create Application User
```sql
-- Create dedicated user for application
CREATE USER trading_app WITH PASSWORD 'your_secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE trading_system TO trading_app;
GRANT CREATE ON SCHEMA public TO trading_app;
```

### 5. Configure PostgreSQL for Performance
Edit `postgresql.conf` (usually in `C:\Program Files\PostgreSQL\16\data\`):

```conf
# Memory Settings (adjust based on your RAM)
shared_buffers = 2GB
effective_cache_size = 6GB
work_mem = 32MB
maintenance_work_mem = 512MB

# Connection Settings
max_connections = 200
max_prepared_transactions = 100

# TimescaleDB specific
timescaledb.max_background_workers = 8
max_worker_processes = 16
max_parallel_workers_per_gather = 4
max_parallel_workers = 8

# Write Performance
checkpoint_segments = 32
checkpoint_completion_target = 0.9
wal_buffers = 16MB

# Query Optimization
random_page_cost = 1.1
effective_io_concurrency = 200
```

### 6. Configure pg_hba.conf for connections
Add to `pg_hba.conf`:
```
# Allow local connections
host    trading_system    trading_app    127.0.0.1/32    md5
host    trading_system    trading_app    ::1/128         md5
```

### 7. Restart PostgreSQL Service
```bash
# Windows
net stop postgresql-x64-16
net start postgresql-x64-16
```

## Verify Installation
```sql
-- Connect and verify
psql -U trading_app -d trading_system -h localhost

-- Check TimescaleDB version
SELECT default_version, installed_version FROM pg_available_extensions WHERE name = 'timescaledb';

-- Check database size
SELECT pg_database_size('trading_system');
```