"""
Automated Database Migration Script
Handles complete migration from SQL Server to PostgreSQL
"""

import os
import sys
import subprocess
import time
import logging
from datetime import datetime
import json
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import pyodbc

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_migration.migrate_data import DataMigrator
from database_migration.schema_converter import SchemaConverter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutomatedMigration:
    """Handles the complete migration process automatically"""
    
    def __init__(self):
        self.pg_config = {
            'host': 'localhost',
            'port': 5432,
            'admin_user': 'postgres',
            'admin_password': input("Enter PostgreSQL admin password: "),
            'database': 'trading_system',
            'app_user': 'trading_app',
            'app_password': 'TradingApp2025!Secure'  # Strong password
        }
        
        self.sql_config = {
            'server': r'(localdb)\mssqllocaldb',
            'database': 'KiteConnectApi',
            'trusted_connection': True
        }
        
        self.migration_status = {
            'steps_completed': [],
            'current_step': None,
            'errors': [],
            'start_time': datetime.now()
        }
    
    def check_postgresql_installed(self) -> bool:
        """Check if PostgreSQL is installed"""
        try:
            result = subprocess.run(['psql', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"PostgreSQL found: {result.stdout.strip()}")
                return True
        except FileNotFoundError:
            pass
        
        logger.error("PostgreSQL not found. Please install PostgreSQL first.")
        logger.info("Download from: https://www.postgresql.org/download/windows/")
        return False
    
    def create_database_and_user(self) -> bool:
        """Create database and user in PostgreSQL"""
        logger.info("Creating database and user...")
        
        try:
            # Connect as admin
            conn = psycopg2.connect(
                host=self.pg_config['host'],
                port=self.pg_config['port'],
                user=self.pg_config['admin_user'],
                password=self.pg_config['admin_password'],
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            
            # Check if database exists
            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{self.pg_config['database']}'")
            if not cursor.fetchone():
                cursor.execute(f"CREATE DATABASE {self.pg_config['database']}")
                logger.info(f"Database '{self.pg_config['database']}' created")
            else:
                logger.info(f"Database '{self.pg_config['database']}' already exists")
            
            # Check if user exists
            cursor.execute(f"SELECT 1 FROM pg_user WHERE usename = '{self.pg_config['app_user']}'")
            if not cursor.fetchone():
                cursor.execute(f"CREATE USER {self.pg_config['app_user']} WITH PASSWORD '{self.pg_config['app_password']}'")
                logger.info(f"User '{self.pg_config['app_user']}' created")
            else:
                logger.info(f"User '{self.pg_config['app_user']}' already exists")
            
            # Grant privileges
            cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE {self.pg_config['database']} TO {self.pg_config['app_user']}")
            
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating database/user: {e}")
            self.migration_status['errors'].append(str(e))
            return False
    
    def enable_extensions(self) -> bool:
        """Enable required PostgreSQL extensions"""
        logger.info("Enabling PostgreSQL extensions...")
        
        try:
            conn = psycopg2.connect(
                host=self.pg_config['host'],
                port=self.pg_config['port'],
                database=self.pg_config['database'],
                user=self.pg_config['admin_user'],
                password=self.pg_config['admin_password']
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            
            # Enable extensions
            extensions = ['timescaledb', 'pgcrypto', 'pg_stat_statements']
            for ext in extensions:
                try:
                    cursor.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")
                    logger.info(f"Extension '{ext}' enabled")
                except Exception as e:
                    logger.warning(f"Could not enable {ext}: {e}")
            
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error enabling extensions: {e}")
            self.migration_status['errors'].append(str(e))
            return False
    
    def create_schema(self) -> bool:
        """Create PostgreSQL schema"""
        logger.info("Creating database schema...")
        
        schema_file = os.path.join(
            os.path.dirname(__file__),
            'postgresql_schema.sql'
        )
        
        if not os.path.exists(schema_file):
            logger.error(f"Schema file not found: {schema_file}")
            return False
        
        try:
            conn = psycopg2.connect(
                host=self.pg_config['host'],
                port=self.pg_config['port'],
                database=self.pg_config['database'],
                user=self.pg_config['app_user'],
                password=self.pg_config['app_password']
            )
            cursor = conn.cursor()
            
            # Read and execute schema
            with open(schema_file, 'r') as f:
                schema_sql = f.read()
            
            # Split by GO statements (SQL Server style) or semicolons
            statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
            
            for statement in statements:
                if statement and not statement.upper().startswith('GO'):
                    try:
                        cursor.execute(statement)
                        conn.commit()
                    except Exception as e:
                        if 'already exists' not in str(e).lower():
                            logger.error(f"Error executing statement: {e}")
                        conn.rollback()
            
            cursor.close()
            conn.close()
            
            logger.info("Schema created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error creating schema: {e}")
            self.migration_status['errors'].append(str(e))
            return False
    
    def migrate_data(self) -> bool:
        """Migrate data from SQL Server to PostgreSQL"""
        logger.info("Starting data migration...")
        
        pg_config = {
            'host': self.pg_config['host'],
            'port': self.pg_config['port'],
            'database': self.pg_config['database'],
            'user': self.pg_config['app_user'],
            'password': self.pg_config['app_password']
        }
        
        migrator = DataMigrator(self.sql_config, pg_config)
        
        # Tables to migrate in order (respecting foreign keys)
        tables = [
            ('BacktestRuns', False),
            ('BacktestTrades', False),
            ('BacktestPositions', False),
            ('NIFTYData_5Min', True),
            ('NIFTYData_Hourly', True),
            ('OptionsData', True),
            ('AuthSessions', False),
            ('UserSessions', False),
        ]
        
        success = migrator.run_migration(tables)
        
        if success:
            logger.info("Data migration completed successfully")
        else:
            logger.error("Data migration failed")
        
        return success
    
    def update_env_file(self) -> bool:
        """Update .env file with PostgreSQL configuration"""
        logger.info("Updating environment configuration...")
        
        env_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            '.env'
        )
        
        env_backup = env_file + '.backup_' + datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Backup existing .env
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    content = f.read()
                with open(env_backup, 'w') as f:
                    f.write(content)
                logger.info(f"Backed up .env to {env_backup}")
            
            # Read PostgreSQL template
            pg_env_file = os.path.join(
                os.path.dirname(__file__),
                '..',
                '.env.postgresql'
            )
            
            with open(pg_env_file, 'r') as f:
                pg_env = f.read()
            
            # Update password
            pg_env = pg_env.replace('your_secure_password_here', self.pg_config['app_password'])
            
            # Add database type indicator
            pg_env += '\n# Database Type (sqlserver or postgresql)\n'
            pg_env += 'DATABASE_TYPE=postgresql\n'
            
            # Write new .env
            with open(env_file, 'w') as f:
                f.write(pg_env)
            
            logger.info(".env file updated with PostgreSQL configuration")
            return True
            
        except Exception as e:
            logger.error(f"Error updating .env file: {e}")
            self.migration_status['errors'].append(str(e))
            return False
    
    def verify_migration(self) -> bool:
        """Verify the migration was successful"""
        logger.info("Verifying migration...")
        
        try:
            # Connect to PostgreSQL
            conn = psycopg2.connect(
                host=self.pg_config['host'],
                port=self.pg_config['port'],
                database=self.pg_config['database'],
                user=self.pg_config['app_user'],
                password=self.pg_config['app_password']
            )
            cursor = conn.cursor()
            
            # Check critical tables
            tables_to_check = [
                'niftydata_5min',
                'niftydata_hourly',
                'optionsdata',
                'backtestruns',
                'backtesttrades'
            ]
            
            verification_results = {}
            all_good = True
            
            for table in tables_to_check:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                verification_results[table] = count
                
                if count == 0:
                    logger.warning(f"Table {table} is empty")
                    all_good = False
                else:
                    logger.info(f"Table {table}: {count:,} rows")
            
            cursor.close()
            conn.close()
            
            # Save verification results
            with open('migration_verification.json', 'w') as f:
                json.dump(verification_results, f, indent=2)
            
            return all_good
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False
    
    def test_api_endpoints(self) -> bool:
        """Test API endpoints with new database"""
        logger.info("Testing API endpoints...")
        
        try:
            # Update environment to use PostgreSQL
            os.environ['DATABASE_TYPE'] = 'postgresql'
            
            # Import and test
            from src.infrastructure.database.hybrid_connection import get_db_manager
            
            db_manager = get_db_manager()
            
            # Test connection
            if not db_manager.check_connection('postgresql'):
                logger.error("PostgreSQL connection test failed")
                return False
            
            logger.info("PostgreSQL connection test passed")
            
            # Test a simple query
            with db_manager.session_scope('postgresql') as session:
                result = session.execute("SELECT COUNT(*) FROM niftydata_5min")
                count = result.fetchone()[0]
                logger.info(f"Query test passed: {count} rows in niftydata_5min")
            
            return True
            
        except Exception as e:
            logger.error(f"API endpoint test failed: {e}")
            return False
    
    def run(self) -> bool:
        """Run the complete migration"""
        logger.info("=" * 60)
        logger.info("AUTOMATED DATABASE MIGRATION")
        logger.info("SQL Server → PostgreSQL + TimescaleDB")
        logger.info("=" * 60)
        
        steps = [
            ("Check PostgreSQL Installation", self.check_postgresql_installed),
            ("Create Database and User", self.create_database_and_user),
            ("Enable Extensions", self.enable_extensions),
            ("Create Schema", self.create_schema),
            ("Migrate Data", self.migrate_data),
            ("Update Environment File", self.update_env_file),
            ("Verify Migration", self.verify_migration),
            ("Test API Endpoints", self.test_api_endpoints)
        ]
        
        for step_name, step_func in steps:
            self.migration_status['current_step'] = step_name
            logger.info(f"\n{'='*40}")
            logger.info(f"Step: {step_name}")
            logger.info(f"{'='*40}")
            
            try:
                if step_func():
                    self.migration_status['steps_completed'].append(step_name)
                    logger.info(f"✅ {step_name} completed successfully")
                else:
                    logger.error(f"❌ {step_name} failed")
                    
                    # Ask user if they want to continue
                    response = input(f"\n{step_name} failed. Continue anyway? (y/n): ")
                    if response.lower() != 'y':
                        break
            except Exception as e:
                logger.error(f"Error in {step_name}: {e}")
                self.migration_status['errors'].append(f"{step_name}: {str(e)}")
                
                response = input(f"\nError occurred. Continue anyway? (y/n): ")
                if response.lower() != 'y':
                    break
        
        # Generate final report
        self.generate_report()
        
        return len(self.migration_status['errors']) == 0
    
    def generate_report(self):
        """Generate migration report"""
        self.migration_status['end_time'] = datetime.now()
        self.migration_status['duration'] = str(
            self.migration_status['end_time'] - self.migration_status['start_time']
        )
        
        logger.info("\n" + "=" * 60)
        logger.info("MIGRATION REPORT")
        logger.info("=" * 60)
        
        logger.info(f"Duration: {self.migration_status['duration']}")
        logger.info(f"Steps Completed: {len(self.migration_status['steps_completed'])}")
        
        if self.migration_status['steps_completed']:
            logger.info("\n✅ Completed Steps:")
            for step in self.migration_status['steps_completed']:
                logger.info(f"  - {step}")
        
        if self.migration_status['errors']:
            logger.error("\n❌ Errors:")
            for error in self.migration_status['errors']:
                logger.error(f"  - {error}")
        
        # Save report
        report_file = f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.migration_status, f, indent=2, default=str)
        
        logger.info(f"\nReport saved to: {report_file}")
        
        if len(self.migration_status['errors']) == 0:
            logger.info("\n🎉 MIGRATION COMPLETED SUCCESSFULLY!")
            logger.info("\nNext steps:")
            logger.info("1. Test your application thoroughly")
            logger.info("2. Monitor performance for 24 hours")
            logger.info("3. Keep SQL Server backup for 7 days")
            logger.info("4. Setup PostgreSQL automated backups")
        else:
            logger.error("\n⚠️ MIGRATION COMPLETED WITH ERRORS")
            logger.error("Please review the errors and retry if needed")

def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("DATABASE MIGRATION TOOL")
    print("SQL Server → PostgreSQL + TimescaleDB")
    print("="*60)
    print("\n⚠️ WARNING: This will migrate your production database.")
    print("Make sure you have a backup before proceeding!")
    
    response = input("\nDo you want to continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Migration cancelled.")
        return
    
    migration = AutomatedMigration()
    success = migration.run()
    
    if success:
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration completed with errors. Check the logs.")

if __name__ == "__main__":
    main()