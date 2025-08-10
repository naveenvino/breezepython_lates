# Data Management Screen - Overview

## What is Data Management?

The Data Management screen is your central hub for managing all trading data in the system. It provides tools to:

1. **View Data** - Browse all database tables and records
2. **Clean Data** - Remove duplicates, fix errors, validate data
3. **Import/Export** - Backup data, import historical data
4. **Monitor Storage** - Track database size and performance
5. **Maintain Data** - Archive old data, optimize tables

## Your Data Tables

### Core Trading Data
- **NiftyIndexData_5Min** - 5-minute NIFTY candles
- **NiftyIndexDataHourly** - Hourly aggregated data
- **OptionsHistoricalData** - Options pricing with Greeks

### Backtest Data
- **BacktestRuns** - Backtest execution records
- **BacktestTrades** - Individual trade records
- **BacktestPositions** - Position details
- **BacktestDailyResults** - Daily P&L summaries

### Live Trading Data
- **LiveTrades** - Real-time trade records
- **LivePositions** - Current open positions
- **LiveTradingConfig** - Trading parameters
- **DailyPnLSummary** - Daily performance

### ML & Analytics
- **MLValidationRuns** - ML model validation results
- **MLPredictions** - ML predictions history
- **SignalPerformance** - Signal statistics
- **MLPerformanceMetrics** - Model performance
- **MLMarketRegime** - Market classification
- **MLBreakevenAnalysis** - Breakeven studies
- **MLHedgeAnalysis** - Hedge optimization results

### Paper Trading
- **PaperTrades** - Simulated trades
- **PaperPositions** - Simulated positions

### Reference Data
- **TradingHolidays** - NSE holiday calendar
- **WeeklySignalInsights** - Signal analysis

## Key Features

### 1. Data Overview Dashboard
- Total records count
- Database size
- Data date ranges
- Missing data gaps
- Data quality score

### 2. Table Browser
- View any table
- Filter and search
- Sort columns
- Export to CSV/Excel
- Edit records

### 3. Data Quality Tools
- **Duplicate Detection** - Find and remove duplicates
- **Gap Analysis** - Identify missing data periods
- **Validation** - Check data integrity
- **Error Correction** - Fix common issues

### 4. Import/Export
- **Bulk Import** - Load historical data
- **Export Backups** - Save data snapshots
- **Format Conversion** - CSV, JSON, Excel
- **Scheduled Backups** - Automatic backups

### 5. Maintenance Tools
- **Archive Old Data** - Move old records to archive
- **Optimize Tables** - Improve query performance
- **Clean Logs** - Remove old log entries
- **Recalculate Stats** - Update statistics

## Common Operations

### Check Data Coverage
```sql
-- See date ranges for each table
SELECT 
    'NiftyData_5Min' as TableName,
    MIN(timestamp) as FirstRecord,
    MAX(timestamp) as LastRecord,
    COUNT(*) as TotalRecords
FROM NiftyIndexData_5Min
```

### Find Missing Data
```sql
-- Find gaps in NIFTY data
WITH DateRange AS (
    SELECT DISTINCT CAST(timestamp AS DATE) as TradingDate
    FROM NiftyIndexData_5Min
)
-- Find missing dates
```

### Clean Duplicates
```sql
-- Remove duplicate trades
DELETE FROM BacktestTrades
WHERE TradeID NOT IN (
    SELECT MIN(TradeID)
    FROM BacktestTrades
    GROUP BY BacktestID, SignalType, EntryTime
)
```

### Export Data
```python
# Export to CSV
SELECT * FROM BacktestTrades
WHERE RunDate >= '2025-07-01'
INTO OUTFILE 'backtest_july.csv'
```

## Data Statistics

### Current Database Size
- **Total Size**: ~2-5 GB typical
- **NIFTY Data**: ~500 MB
- **Options Data**: ~2 GB
- **Backtest Results**: ~300 MB
- **ML Data**: ~200 MB

### Record Counts (Typical)
- **NIFTY 5-min**: 50,000+ records
- **Options Data**: 500,000+ records
- **Backtest Trades**: 10,000+ records
- **ML Predictions**: 5,000+ records

## Data Retention Policy

### Keep Forever
- Backtest results
- Live trade records
- ML model outputs

### Archive After 1 Year
- 5-minute NIFTY data
- Options tick data

### Delete After 90 Days
- Debug logs
- Temporary calculations
- Failed attempts

## Performance Tips

1. **Index Key Columns** - Ensure dates and IDs are indexed
2. **Archive Old Data** - Move old records to archive tables
3. **Regular Maintenance** - Run optimization weekly
4. **Monitor Growth** - Track database size trends
5. **Backup Regularly** - Daily backups recommended

## API Endpoints

```python
GET  /data/overview          # Database statistics
GET  /data/tables            # List all tables
GET  /data/table/{name}      # View table data
POST /data/export            # Export data
POST /data/import            # Import data
POST /data/clean             # Clean duplicates
POST /data/optimize          # Optimize tables
GET  /data/gaps              # Find missing data
POST /data/backup            # Create backup
```

## Security & Access

- **Read-Only by Default** - Viewing doesn't modify
- **Confirmation Required** - For delete operations
- **Audit Trail** - All changes logged
- **Backup Before Delete** - Automatic safety backup

The Data Management screen provides complete control over your trading database with safety features to prevent data loss!