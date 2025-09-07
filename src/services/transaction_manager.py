"""
Transaction Manager for Atomic Database Operations
Ensures data consistency across multiple operations
"""

import sqlite3
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional
import logging
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)

class TransactionManager:
    def __init__(self, db_path: str = 'data/trading_settings.db'):
        self.db_path = db_path
        self.transaction_log = []
        
    @contextmanager
    def atomic_transaction(self):
        """
        Context manager for atomic database transactions
        Automatically handles commit/rollback
        """
        conn = None
        cursor = None
        transaction_id = datetime.now().isoformat()
        
        try:
            conn = sqlite3.connect(self.db_path, isolation_level='IMMEDIATE')
            cursor = conn.cursor()
            
            # Begin explicit transaction
            cursor.execute("BEGIN IMMEDIATE")
            
            self.log_transaction_start(transaction_id)
            
            yield cursor
            
            # If we get here, commit the transaction
            conn.commit()
            self.log_transaction_success(transaction_id)
            
        except Exception as e:
            # Rollback on any error
            if conn:
                conn.rollback()
            
            self.log_transaction_failure(transaction_id, e)
            logger.error(f"Transaction {transaction_id} failed: {str(e)}")
            raise
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def execute_atomic_operations(self, operations: List[Dict[str, Any]]) -> bool:
        """
        Execute multiple operations atomically
        
        Args:
            operations: List of operations, each containing:
                - 'query': SQL query string
                - 'params': Query parameters (optional)
                - 'callback': Function to call after query (optional)
        
        Returns:
            True if all operations succeeded, False otherwise
        """
        try:
            with self.atomic_transaction() as cursor:
                for op in operations:
                    query = op.get('query')
                    params = op.get('params', ())
                    callback = op.get('callback')
                    
                    if not query:
                        raise ValueError("Operation missing required 'query' field")
                    
                    # Execute the query
                    cursor.execute(query, params)
                    
                    # Call callback if provided
                    if callback and callable(callback):
                        callback(cursor)
                
                return True
                
        except Exception as e:
            logger.error(f"Atomic operations failed: {str(e)}")
            return False
    
    def upsert_with_transaction(self, table: str, data: Dict[str, Any], 
                               key_columns: List[str]) -> bool:
        """
        Perform an upsert operation within a transaction
        
        Args:
            table: Table name
            data: Data to insert/update
            key_columns: Columns that form the unique key
        
        Returns:
            True if operation succeeded
        """
        try:
            with self.atomic_transaction() as cursor:
                # Build WHERE clause for key columns
                where_clause = " AND ".join([f"{col} = ?" for col in key_columns])
                key_values = [data[col] for col in key_columns]
                
                # Check if record exists
                check_query = f"SELECT COUNT(*) FROM {table} WHERE {where_clause}"
                cursor.execute(check_query, key_values)
                exists = cursor.fetchone()[0] > 0
                
                if exists:
                    # Update existing record
                    set_clause = ", ".join([
                        f"{col} = ?" 
                        for col in data.keys() 
                        if col not in key_columns
                    ])
                    update_values = [
                        data[col] 
                        for col in data.keys() 
                        if col not in key_columns
                    ]
                    update_values.extend(key_values)
                    
                    update_query = f"""
                        UPDATE {table} 
                        SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                        WHERE {where_clause}
                    """
                    cursor.execute(update_query, update_values)
                else:
                    # Insert new record
                    columns = list(data.keys())
                    placeholders = ", ".join(["?" for _ in columns])
                    column_names = ", ".join(columns)
                    values = [data[col] for col in columns]
                    
                    insert_query = f"""
                        INSERT INTO {table} ({column_names})
                        VALUES ({placeholders})
                    """
                    cursor.execute(insert_query, values)
                
                return True
                
        except Exception as e:
            logger.error(f"Upsert operation failed: {str(e)}")
            return False
    
    def batch_insert_with_transaction(self, table: str, 
                                     records: List[Dict[str, Any]]) -> int:
        """
        Insert multiple records in a single transaction
        
        Args:
            table: Table name
            records: List of records to insert
        
        Returns:
            Number of records inserted
        """
        if not records:
            return 0
        
        inserted_count = 0
        
        try:
            with self.atomic_transaction() as cursor:
                # Get column names from first record
                columns = list(records[0].keys())
                column_names = ", ".join(columns)
                placeholders = ", ".join(["?" for _ in columns])
                
                insert_query = f"""
                    INSERT INTO {table} ({column_names})
                    VALUES ({placeholders})
                """
                
                for record in records:
                    values = [record.get(col) for col in columns]
                    cursor.execute(insert_query, values)
                    inserted_count += 1
                
                return inserted_count
                
        except Exception as e:
            logger.error(f"Batch insert failed: {str(e)}")
            return 0
    
    def execute_with_savepoint(self, operations: List[Callable]) -> bool:
        """
        Execute operations with savepoint support for nested transactions
        
        Args:
            operations: List of callable operations
        
        Returns:
            True if all operations succeeded
        """
        try:
            with self.atomic_transaction() as cursor:
                for i, operation in enumerate(operations):
                    savepoint_name = f"sp_{i}"
                    
                    try:
                        # Create savepoint
                        cursor.execute(f"SAVEPOINT {savepoint_name}")
                        
                        # Execute operation
                        operation(cursor)
                        
                        # Release savepoint on success
                        cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                        
                    except Exception as e:
                        # Rollback to savepoint on failure
                        cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                        logger.warning(f"Operation {i} failed, rolled back to savepoint: {str(e)}")
                        raise
                
                return True
                
        except Exception as e:
            logger.error(f"Operations with savepoints failed: {str(e)}")
            return False
    
    def log_transaction_start(self, transaction_id: str):
        """Log transaction start"""
        self.transaction_log.append({
            'id': transaction_id,
            'status': 'STARTED',
            'timestamp': datetime.now().isoformat()
        })
    
    def log_transaction_success(self, transaction_id: str):
        """Log transaction success"""
        self.transaction_log.append({
            'id': transaction_id,
            'status': 'COMMITTED',
            'timestamp': datetime.now().isoformat()
        })
    
    def log_transaction_failure(self, transaction_id: str, error: Exception):
        """Log transaction failure"""
        self.transaction_log.append({
            'id': transaction_id,
            'status': 'ROLLED_BACK',
            'error': str(error),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        })
    
    def get_transaction_history(self, limit: int = 100) -> List[Dict]:
        """Get recent transaction history"""
        return self.transaction_log[-limit:]
    
    def clear_transaction_log(self):
        """Clear transaction log"""
        self.transaction_log = []

# Global instance
transaction_manager = TransactionManager()