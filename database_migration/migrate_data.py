"""
Data Migration Script: SQL Server to PostgreSQL
Migrates all trading system data with validation
"""

import pyodbc
import psycopg2
from psycopg2.extras import execute_batch
import pandas as pd
from datetime import datetime
import logging
import os
from typing import Dict, List, Tuple
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DataMigrator:
    """Handles data migration from SQL Server to PostgreSQL"""
    
    def __init__(self, sql_server_config: Dict, postgresql_config: Dict):
        self.sql_config = sql_server_config
        self.pg_config = postgresql_config
        self.sql_conn = None
        self.pg_conn = None
        self.migration_stats = {}
    
    def connect_sql_server(self):
        """Connect to SQL Server"""
        try:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.sql_config['server']};"
                f"DATABASE={self.sql_config['database']};"
            )
            
            if self.sql_config.get('trusted_connection'):
                conn_str += "Trusted_Connection=yes;"
            else:
                conn_str += f"UID={self.sql_config['username']};PWD={self.sql_config['password']};"
            
            self.sql_conn = pyodbc.connect(conn_str)
            logger.info("Connected to SQL Server successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to SQL Server: {e}")
            return False
    
    def connect_postgresql(self):
        """Connect to PostgreSQL"""
        try:
            self.pg_conn = psycopg2.connect(
                host=self.pg_config['host'],
                port=self.pg_config['port'],
                database=self.pg_config['database'],
                user=self.pg_config['user'],
                password=self.pg_config['password']
            )
            self.pg_conn.autocommit = False
            logger.info("Connected to PostgreSQL successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            return False
    
    def get_table_count(self, table_name: str, connection, is_postgresql: bool = False) -> int:
        """Get row count for a table"""
        try:
            cursor = connection.cursor()
            query = f"SELECT COUNT(*) FROM {table_name}"
            cursor.execute(query)
            count = cursor.fetchone()[0]
            cursor.close()
            return count
        except Exception as e:
            logger.error(f"Error getting count for {table_name}: {e}")
            return 0
    
    def migrate_table(self, table_name: str, batch_size: int = 10000):
        """Migrate a single table with batching"""
        logger.info(f"Starting migration for table: {table_name}")
        
        try:
            # Get source row count
            source_count = self.get_table_count(table_name, self.sql_conn)
            logger.info(f"Source table {table_name} has {source_count:,} rows")
            
            if source_count == 0:
                logger.warning(f"Table {table_name} is empty, skipping")
                return
            
            # Create cursors
            sql_cursor = self.sql_conn.cursor()
            pg_cursor = self.pg_conn.cursor()
            
            # Get column information
            sql_cursor.execute(f"""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = '{table_name}'
                ORDER BY ORDINAL_POSITION
            """)
            columns = [row[0] for row in sql_cursor.fetchall()]
            
            # Prepare insert query
            placeholders = ', '.join(['%s'] * len(columns))
            column_names = ', '.join([f'"{col}"' for col in columns])
            insert_query = f"""
                INSERT INTO {table_name} ({column_names})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            
            # Migrate in batches
            offset = 0
            total_migrated = 0
            
            while offset < source_count:
                # Fetch batch from SQL Server
                query = f"""
                    SELECT {', '.join(columns)}
                    FROM {table_name}
                    ORDER BY {columns[0]}
                    OFFSET {offset} ROWS
                    FETCH NEXT {batch_size} ROWS ONLY
                """
                
                sql_cursor.execute(query)
                batch_data = sql_cursor.fetchall()
                
                if not batch_data:
                    break
                
                # Process data for PostgreSQL compatibility
                processed_data = []
                for row in batch_data:
                    processed_row = []
                    for value in row:
                        # Handle SQL Server specific types
                        if isinstance(value, bytes):
                            # Convert binary to hex string for UUID compatibility
                            processed_row.append(value.hex())
                        elif value is None:
                            processed_row.append(None)
                        else:
                            processed_row.append(value)
                    processed_data.append(tuple(processed_row))
                
                # Insert batch into PostgreSQL
                execute_batch(pg_cursor, insert_query, processed_data, page_size=batch_size)
                self.pg_conn.commit()
                
                total_migrated += len(batch_data)
                offset += batch_size
                
                # Progress update
                progress = (total_migrated / source_count) * 100
                logger.info(f"{table_name}: Migrated {total_migrated:,}/{source_count:,} rows ({progress:.1f}%)")
            
            # Verify migration
            dest_count = self.get_table_count(table_name, self.pg_conn, True)
            
            self.migration_stats[table_name] = {
                'source_count': source_count,
                'dest_count': dest_count,
                'status': 'SUCCESS' if dest_count == source_count else 'PARTIAL',
                'difference': source_count - dest_count
            }
            
            if dest_count == source_count:
                logger.info(f"✅ Table {table_name} migrated successfully: {dest_count:,} rows")
            else:
                logger.warning(f"⚠️ Table {table_name} partial migration: {dest_count:,}/{source_count:,} rows")
            
            # Close cursors
            sql_cursor.close()
            pg_cursor.close()
            
        except Exception as e:
            logger.error(f"Error migrating table {table_name}: {e}")
            self.pg_conn.rollback()
            self.migration_stats[table_name] = {
                'status': 'FAILED',
                'error': str(e)
            }
    
    def migrate_time_series_optimized(self, table_name: str, time_column: str = 'Timestamp'):
        """Optimized migration for time-series tables"""
        logger.info(f"Starting optimized time-series migration for: {table_name}")
        
        try:
            sql_cursor = self.sql_conn.cursor()
            pg_cursor = self.pg_conn.cursor()
            
            # Get date range
            sql_cursor.execute(f"""
                SELECT MIN({time_column}), MAX({time_column})
                FROM {table_name}
            """)
            min_date, max_date = sql_cursor.fetchone()
            
            if not min_date:
                logger.warning(f"Table {table_name} has no data")
                return
            
            logger.info(f"Date range: {min_date} to {max_date}")
            
            # Use COPY for faster bulk insert
            output_file = f"temp_{table_name}.csv"
            
            # Export from SQL Server to CSV
            query = f"""
                SELECT * FROM {table_name}
                ORDER BY {time_column}
            """
            
            df = pd.read_sql(query, self.sql_conn)
            df.to_csv(output_file, index=False, header=False)
            
            # Import to PostgreSQL using COPY
            with open(output_file, 'r') as f:
                pg_cursor.copy_expert(
                    f"COPY {table_name} FROM STDIN WITH CSV",
                    f
                )
            
            self.pg_conn.commit()
            
            # Clean up temp file
            os.remove(output_file)
            
            # Get final count
            pg_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            final_count = pg_cursor.fetchone()[0]
            
            logger.info(f"✅ Time-series table {table_name} migrated: {final_count:,} rows")
            
            sql_cursor.close()
            pg_cursor.close()
            
        except Exception as e:
            logger.error(f"Error in time-series migration for {table_name}: {e}")
            self.pg_conn.rollback()
    
    def run_migration(self, tables_to_migrate: List[str] = None):
        """Run the complete migration"""
        logger.info("=" * 60)
        logger.info("Starting Database Migration")
        logger.info("=" * 60)
        
        # Connect to databases
        if not self.connect_sql_server() or not self.connect_postgresql():
            logger.error("Failed to establish database connections")
            return False
        
        # Default tables if not specified
        if not tables_to_migrate:
            tables_to_migrate = [
                # Time-series tables (migrate with optimization)
                ('NIFTYData_5Min', True),
                ('NIFTYData_Hourly', True),
                ('OptionsData', True),
                
                # Regular tables
                ('BacktestRuns', False),
                ('BacktestTrades', False),
                ('BacktestPositions', False),
                ('AuthSessions', False),
                ('UserSessions', False),
                ('LiveTrades', False),
                ('PaperTrades', False),
                ('PaperPortfolios', False),
                ('AlertConfigurations', False),
                ('AlertHistory', False),
                ('WebhookEvents', False),
                ('PerformanceMetrics', False),
            ]
        
        # Migrate each table
        for table_info in tables_to_migrate:
            if isinstance(table_info, tuple):
                table_name, is_timeseries = table_info
                if is_timeseries:
                    self.migrate_time_series_optimized(table_name)
                else:
                    self.migrate_table(table_name)
            else:
                self.migrate_table(table_info)
        
        # Generate migration report
        self.generate_report()
        
        # Close connections
        if self.sql_conn:
            self.sql_conn.close()
        if self.pg_conn:
            self.pg_conn.close()
        
        logger.info("Migration completed!")
        return True
    
    def generate_report(self):
        """Generate migration report"""
        logger.info("\n" + "=" * 60)
        logger.info("MIGRATION REPORT")
        logger.info("=" * 60)
        
        total_success = 0
        total_partial = 0
        total_failed = 0
        
        for table, stats in self.migration_stats.items():
            status = stats.get('status', 'UNKNOWN')
            if status == 'SUCCESS':
                total_success += 1
                logger.info(f"✅ {table}: SUCCESS - {stats.get('dest_count', 0):,} rows")
            elif status == 'PARTIAL':
                total_partial += 1
                logger.warning(f"⚠️ {table}: PARTIAL - Missing {stats.get('difference', 0):,} rows")
            else:
                total_failed += 1
                logger.error(f"❌ {table}: FAILED - {stats.get('error', 'Unknown error')}")
        
        logger.info("-" * 60)
        logger.info(f"Summary: {total_success} successful, {total_partial} partial, {total_failed} failed")
        
        # Save report to file
        with open('migration_report.json', 'w') as f:
            json.dump(self.migration_stats, f, indent=2, default=str)
        
        logger.info("Report saved to migration_report.json")

def main():
    """Main migration entry point"""
    
    # SQL Server configuration
    sql_server_config = {
        'server': r'(localdb)\mssqllocaldb',
        'database': 'KiteConnectApi',
        'trusted_connection': True  # Use Windows Authentication
    }
    
    # PostgreSQL configuration
    postgresql_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'trading_system',
        'user': 'trading_app',
        'password': 'your_secure_password'  # Change this!
    }
    
    # Create migrator
    migrator = DataMigrator(sql_server_config, postgresql_config)
    
    # Run migration
    migrator.run_migration()

if __name__ == "__main__":
    main()