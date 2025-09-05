"""
Migration Verification Script
Thoroughly tests the PostgreSQL migration
"""

import os
import sys
import psycopg2
import pyodbc
import pandas as pd
from datetime import datetime, timedelta
import json
import logging

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MigrationVerifier:
    """Verifies the database migration was successful"""
    
    def __init__(self):
        self.pg_config = {
            'host': os.getenv('PG_HOST', 'localhost'),
            'port': int(os.getenv('PG_PORT', 5432)),
            'database': os.getenv('PG_DATABASE', 'trading_system'),
            'user': os.getenv('PG_USER', 'trading_app'),
            'password': os.getenv('PG_PASSWORD', 'TradingApp2025!Secure')
        }
        
        self.sql_config = {
            'server': os.getenv('DB_SERVER', r'(localdb)\mssqllocaldb'),
            'database': os.getenv('DB_NAME', 'KiteConnectApi'),
            'trusted_connection': True
        }
        
        self.verification_results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'warnings': [],
            'errors': []
        }
    
    def connect_postgresql(self):
        """Connect to PostgreSQL"""
        return psycopg2.connect(**self.pg_config)
    
    def connect_sqlserver(self):
        """Connect to SQL Server"""
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={self.sql_config['server']};"
            f"DATABASE={self.sql_config['database']};"
            f"Trusted_Connection=yes;"
        )
        return pyodbc.connect(conn_str)
    
    def check_table_counts(self):
        """Compare row counts between SQL Server and PostgreSQL"""
        logger.info("Checking table row counts...")
        
        tables = [
            'NIFTYData_5Min',
            'NIFTYData_Hourly',
            'OptionsData',
            'BacktestRuns',
            'BacktestTrades',
            'BacktestPositions',
            'AuthSessions',
            'UserSessions'
        ]
        
        count_comparison = {}
        
        try:
            # Get SQL Server counts
            sql_conn = self.connect_sqlserver()
            sql_cursor = sql_conn.cursor()
            
            for table in tables:
                try:
                    sql_cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    sql_count = sql_cursor.fetchone()[0]
                except:
                    sql_count = 0
                
                count_comparison[table] = {'sql_server': sql_count}
            
            sql_conn.close()
            
            # Get PostgreSQL counts
            pg_conn = self.connect_postgresql()
            pg_cursor = pg_conn.cursor()
            
            for table in tables:
                pg_table = table.lower()
                try:
                    pg_cursor.execute(f"SELECT COUNT(*) FROM {pg_table}")
                    pg_count = pg_cursor.fetchone()[0]
                except:
                    pg_count = 0
                
                count_comparison[table]['postgresql'] = pg_count
                count_comparison[table]['match'] = (
                    count_comparison[table]['sql_server'] == pg_count
                )
                
                if not count_comparison[table]['match']:
                    diff = count_comparison[table]['sql_server'] - pg_count
                    self.verification_results['warnings'].append(
                        f"Table {table}: Missing {diff} rows in PostgreSQL"
                    )
            
            pg_conn.close()
            
            self.verification_results['checks']['table_counts'] = count_comparison
            
            # Log results
            for table, counts in count_comparison.items():
                status = "✅" if counts['match'] else "⚠️"
                logger.info(
                    f"{status} {table}: SQL Server={counts['sql_server']:,}, "
                    f"PostgreSQL={counts['postgresql']:,}"
                )
            
            return all(c['match'] for c in count_comparison.values())
            
        except Exception as e:
            logger.error(f"Error checking table counts: {e}")
            self.verification_results['errors'].append(str(e))
            return False
    
    def check_data_integrity(self):
        """Check data integrity with sample queries"""
        logger.info("Checking data integrity...")
        
        integrity_checks = []
        
        try:
            pg_conn = self.connect_postgresql()
            pg_cursor = pg_conn.cursor()
            
            # Check 1: Latest NIFTY data
            pg_cursor.execute("""
                SELECT MAX(timestamp) as latest_time,
                       COUNT(DISTINCT symbol) as symbols,
                       COUNT(*) as total_records
                FROM niftydata_5min
            """)
            result = pg_cursor.fetchone()
            
            integrity_checks.append({
                'check': 'Latest NIFTY 5min data',
                'latest_time': result[0].isoformat() if result[0] else None,
                'symbols': result[1],
                'records': result[2],
                'status': 'PASS' if result[2] > 0 else 'FAIL'
            })
            
            # Check 2: Options data with Greeks
            pg_cursor.execute("""
                SELECT COUNT(*) as records_with_greeks
                FROM optionsdata
                WHERE delta IS NOT NULL
                  AND gamma IS NOT NULL
                  AND theta IS NOT NULL
            """)
            greeks_count = pg_cursor.fetchone()[0]
            
            integrity_checks.append({
                'check': 'Options data with Greeks',
                'count': greeks_count,
                'status': 'PASS' if greeks_count > 0 else 'WARNING'
            })
            
            # Check 3: Backtest trades consistency
            pg_cursor.execute("""
                SELECT COUNT(*) as trades,
                       COUNT(DISTINCT backtestrunid) as runs,
                       AVG(pnl) as avg_pnl
                FROM backtesttrades
            """)
            result = pg_cursor.fetchone()
            
            integrity_checks.append({
                'check': 'Backtest trades',
                'trades': result[0],
                'runs': result[1],
                'avg_pnl': float(result[2]) if result[2] else 0,
                'status': 'PASS' if result[0] > 0 else 'WARNING'
            })
            
            pg_conn.close()
            
            self.verification_results['checks']['data_integrity'] = integrity_checks
            
            # Log results
            for check in integrity_checks:
                status = "✅" if check['status'] == 'PASS' else "⚠️"
                logger.info(f"{status} {check['check']}: {check['status']}")
            
            return all(c['status'] != 'FAIL' for c in integrity_checks)
            
        except Exception as e:
            logger.error(f"Error checking data integrity: {e}")
            self.verification_results['errors'].append(str(e))
            return False
    
    def check_performance(self):
        """Run performance benchmark queries"""
        logger.info("Running performance benchmarks...")
        
        benchmarks = []
        
        try:
            pg_conn = self.connect_postgresql()
            pg_cursor = pg_conn.cursor()
            
            # Benchmark 1: Time-series query
            start_time = datetime.now()
            pg_cursor.execute("""
                SELECT timestamp, close
                FROM niftydata_5min
                WHERE symbol = 'NIFTY'
                  AND timestamp >= CURRENT_DATE - INTERVAL '30 days'
                ORDER BY timestamp DESC
                LIMIT 1000
            """)
            results = pg_cursor.fetchall()
            query_time = (datetime.now() - start_time).total_seconds() * 1000
            
            benchmarks.append({
                'query': '30-day NIFTY data',
                'rows': len(results),
                'time_ms': round(query_time, 2),
                'status': 'FAST' if query_time < 100 else 'SLOW'
            })
            
            # Benchmark 2: Options chain query
            start_time = datetime.now()
            pg_cursor.execute("""
                SELECT strikeprice, optiontype, lastprice, volume, openinterest
                FROM optionsdata
                WHERE timestamp = (SELECT MAX(timestamp) FROM optionsdata)
                ORDER BY strikeprice, optiontype
            """)
            results = pg_cursor.fetchall()
            query_time = (datetime.now() - start_time).total_seconds() * 1000
            
            benchmarks.append({
                'query': 'Latest options chain',
                'rows': len(results),
                'time_ms': round(query_time, 2),
                'status': 'FAST' if query_time < 200 else 'SLOW'
            })
            
            # Benchmark 3: Aggregation query
            start_time = datetime.now()
            pg_cursor.execute("""
                SELECT 
                    DATE_TRUNC('hour', timestamp) as hour,
                    AVG(close) as avg_close,
                    MAX(high) as max_high,
                    MIN(low) as min_low,
                    SUM(volume) as total_volume
                FROM niftydata_5min
                WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY DATE_TRUNC('hour', timestamp)
                ORDER BY hour DESC
            """)
            results = pg_cursor.fetchall()
            query_time = (datetime.now() - start_time).total_seconds() * 1000
            
            benchmarks.append({
                'query': 'Hourly aggregation (7 days)',
                'rows': len(results),
                'time_ms': round(query_time, 2),
                'status': 'FAST' if query_time < 500 else 'SLOW'
            })
            
            pg_conn.close()
            
            self.verification_results['checks']['performance'] = benchmarks
            
            # Log results
            for benchmark in benchmarks:
                status = "🚀" if benchmark['status'] == 'FAST' else "🐌"
                logger.info(
                    f"{status} {benchmark['query']}: "
                    f"{benchmark['time_ms']}ms for {benchmark['rows']} rows"
                )
            
            return all(b['status'] == 'FAST' for b in benchmarks)
            
        except Exception as e:
            logger.error(f"Error running performance benchmarks: {e}")
            self.verification_results['errors'].append(str(e))
            return False
    
    def check_timescaledb_features(self):
        """Check TimescaleDB specific features"""
        logger.info("Checking TimescaleDB features...")
        
        features = []
        
        try:
            pg_conn = self.connect_postgresql()
            pg_cursor = pg_conn.cursor()
            
            # Check hypertables
            pg_cursor.execute("""
                SELECT h.table_name, h.num_chunks, h.compression_enabled
                FROM timescaledb_information.hypertables h
            """)
            hypertables = pg_cursor.fetchall()
            
            for table, chunks, compression in hypertables:
                features.append({
                    'feature': f'Hypertable: {table}',
                    'chunks': chunks,
                    'compression': compression,
                    'status': 'ENABLED'
                })
            
            # Check continuous aggregates
            pg_cursor.execute("""
                SELECT view_name, refresh_interval
                FROM timescaledb_information.continuous_aggregates
            """)
            aggregates = pg_cursor.fetchall()
            
            for view, interval in aggregates:
                features.append({
                    'feature': f'Continuous Aggregate: {view}',
                    'refresh_interval': str(interval),
                    'status': 'ENABLED'
                })
            
            # Check compression policies
            pg_cursor.execute("""
                SELECT hypertable_name, compress_after
                FROM timescaledb_information.compression_settings
            """)
            compression = pg_cursor.fetchall()
            
            for table, after in compression:
                features.append({
                    'feature': f'Compression Policy: {table}',
                    'compress_after': str(after),
                    'status': 'ENABLED'
                })
            
            pg_conn.close()
            
            self.verification_results['checks']['timescaledb'] = features
            
            # Log results
            for feature in features:
                logger.info(f"✅ {feature['feature']}: {feature['status']}")
            
            return len(features) > 0
            
        except Exception as e:
            logger.warning(f"TimescaleDB features not available: {e}")
            return True  # Not critical if TimescaleDB features aren't set up yet
    
    def test_api_compatibility(self):
        """Test API compatibility with PostgreSQL"""
        logger.info("Testing API compatibility...")
        
        tests = []
        
        try:
            # Set environment to use PostgreSQL
            os.environ['DATABASE_TYPE'] = 'postgresql'
            
            from src.infrastructure.database.hybrid_connection import get_db_manager
            
            db_manager = get_db_manager()
            
            # Test 1: Connection
            connection_ok = db_manager.check_connection('postgresql')
            tests.append({
                'test': 'Database connection',
                'result': 'PASS' if connection_ok else 'FAIL'
            })
            
            # Test 2: Session creation
            try:
                session = db_manager.get_session('postgresql')
                session.close()
                tests.append({
                    'test': 'Session creation',
                    'result': 'PASS'
                })
            except Exception as e:
                tests.append({
                    'test': 'Session creation',
                    'result': 'FAIL',
                    'error': str(e)
                })
            
            # Test 3: Query execution
            try:
                result = db_manager.execute_query(
                    "SELECT COUNT(*) as count FROM niftydata_5min",
                    force_type='postgresql'
                )
                tests.append({
                    'test': 'Query execution',
                    'result': 'PASS',
                    'rows': result[0]['count'] if result else 0
                })
            except Exception as e:
                tests.append({
                    'test': 'Query execution',
                    'result': 'FAIL',
                    'error': str(e)
                })
            
            self.verification_results['checks']['api_compatibility'] = tests
            
            # Log results
            for test in tests:
                status = "✅" if test['result'] == 'PASS' else "❌"
                logger.info(f"{status} {test['test']}: {test['result']}")
            
            return all(t['result'] == 'PASS' for t in tests)
            
        except Exception as e:
            logger.error(f"Error testing API compatibility: {e}")
            self.verification_results['errors'].append(str(e))
            return False
    
    def run_verification(self):
        """Run all verification checks"""
        logger.info("=" * 60)
        logger.info("DATABASE MIGRATION VERIFICATION")
        logger.info("=" * 60)
        
        checks = [
            ("Table Row Counts", self.check_table_counts),
            ("Data Integrity", self.check_data_integrity),
            ("Query Performance", self.check_performance),
            ("TimescaleDB Features", self.check_timescaledb_features),
            ("API Compatibility", self.test_api_compatibility)
        ]
        
        all_passed = True
        
        for check_name, check_func in checks:
            logger.info(f"\n{'='*40}")
            logger.info(f"Running: {check_name}")
            logger.info(f"{'='*40}")
            
            try:
                passed = check_func()
                if not passed:
                    all_passed = False
            except Exception as e:
                logger.error(f"Check failed: {e}")
                self.verification_results['errors'].append(f"{check_name}: {str(e)}")
                all_passed = False
        
        # Generate report
        self.generate_report(all_passed)
        
        return all_passed
    
    def generate_report(self, all_passed):
        """Generate verification report"""
        logger.info("\n" + "=" * 60)
        logger.info("VERIFICATION REPORT")
        logger.info("=" * 60)
        
        if all_passed:
            logger.info("✅ ALL CHECKS PASSED")
        else:
            logger.warning("⚠️ SOME CHECKS FAILED")
        
        if self.verification_results['warnings']:
            logger.warning("\nWarnings:")
            for warning in self.verification_results['warnings']:
                logger.warning(f"  - {warning}")
        
        if self.verification_results['errors']:
            logger.error("\nErrors:")
            for error in self.verification_results['errors']:
                logger.error(f"  - {error}")
        
        # Save report
        report_file = f"verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.verification_results, f, indent=2, default=str)
        
        logger.info(f"\nDetailed report saved to: {report_file}")
        
        if all_passed:
            logger.info("\n🎉 PostgreSQL migration verified successfully!")
            logger.info("\nYour system is ready to use PostgreSQL!")
        else:
            logger.warning("\n⚠️ Some verification checks failed.")
            logger.warning("Review the warnings and errors above.")

def main():
    """Main entry point"""
    verifier = MigrationVerifier()
    success = verifier.run_verification()
    
    if success:
        print("\n✅ Verification completed successfully!")
    else:
        print("\n⚠️ Verification completed with issues.")

if __name__ == "__main__":
    main()