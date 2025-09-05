"""
SQL Server to PostgreSQL Schema Converter
Converts SQL Server table schemas to PostgreSQL with TimescaleDB
"""

import re
from typing import Dict, List, Tuple
from datetime import datetime

class SchemaConverter:
    """Convert SQL Server schemas to PostgreSQL"""
    
    # Data type mappings
    TYPE_MAPPINGS = {
        'NVARCHAR': 'VARCHAR',
        'NCHAR': 'CHAR',
        'NTEXT': 'TEXT',
        'DATETIME': 'TIMESTAMP',
        'DATETIME2': 'TIMESTAMP',
        'SMALLDATETIME': 'TIMESTAMP',
        'BIT': 'BOOLEAN',
        'TINYINT': 'SMALLINT',
        'SMALLMONEY': 'NUMERIC(10,4)',
        'MONEY': 'NUMERIC(19,4)',
        'UNIQUEIDENTIFIER': 'UUID',
        'IMAGE': 'BYTEA',
        'VARBINARY': 'BYTEA',
        'BINARY': 'BYTEA',
        'FLOAT': 'DOUBLE PRECISION',
        'REAL': 'REAL',
        'DECIMAL': 'NUMERIC',
        'NUMERIC': 'NUMERIC',
        'INT': 'INTEGER',
        'BIGINT': 'BIGINT',
        'SMALLINT': 'SMALLINT',
        'VARCHAR': 'VARCHAR',
        'CHAR': 'CHAR',
        'TEXT': 'TEXT',
        'DATE': 'DATE',
        'TIME': 'TIME',
    }
    
    # Tables that should be hypertables (time-series)
    HYPERTABLE_CONFIGS = {
        'NIFTYData_5Min': {
            'time_column': 'Timestamp',
            'chunk_interval': '1 day'
        },
        'NIFTYData_Hourly': {
            'time_column': 'Timestamp', 
            'chunk_interval': '7 days'
        },
        'OptionsData': {
            'time_column': 'Timestamp',
            'chunk_interval': '1 day'
        },
        'LiveTrades': {
            'time_column': 'created_at',
            'chunk_interval': '1 day'
        },
        'TickData': {
            'time_column': 'timestamp',
            'chunk_interval': '1 hour'
        }
    }
    
    def convert_data_type(self, sql_server_type: str) -> str:
        """Convert SQL Server data type to PostgreSQL"""
        # Extract base type and parameters
        match = re.match(r'(\w+)(?:\(([^)]+)\))?', sql_server_type.upper())
        if not match:
            return sql_server_type
        
        base_type = match.group(1)
        params = match.group(2)
        
        # Get PostgreSQL equivalent
        pg_type = self.TYPE_MAPPINGS.get(base_type, base_type)
        
        # Handle special cases
        if base_type in ['NVARCHAR', 'VARCHAR', 'CHAR', 'NCHAR']:
            if params:
                if params.upper() == 'MAX':
                    return 'TEXT'
                else:
                    return f"{pg_type}({params})"
            return pg_type
        
        elif base_type in ['DECIMAL', 'NUMERIC']:
            if params:
                return f"NUMERIC({params})"
            return 'NUMERIC'
        
        return pg_type
    
    def convert_default_value(self, default_val: str) -> str:
        """Convert SQL Server default values to PostgreSQL"""
        if not default_val:
            return ''
        
        # Common conversions
        replacements = {
            'GETDATE()': 'CURRENT_TIMESTAMP',
            'GETUTCDATE()': 'CURRENT_TIMESTAMP AT TIME ZONE \'UTC\'',
            'NEWID()': 'gen_random_uuid()',
            'SYSDATETIME()': 'CURRENT_TIMESTAMP',
            'SYSUTCDATETIME()': 'CURRENT_TIMESTAMP AT TIME ZONE \'UTC\'',
        }
        
        for old, new in replacements.items():
            default_val = default_val.replace(old, new)
        
        return default_val
    
    def parse_sql_server_table(self, create_table_sql: str) -> Dict:
        """Parse SQL Server CREATE TABLE statement"""
        table_info = {
            'name': '',
            'columns': [],
            'primary_key': [],
            'indexes': [],
            'constraints': []
        }
        
        # Extract table name
        table_match = re.search(r'CREATE\s+TABLE\s+(?:\[?(\w+)\]?\.)?(?:\[?(\w+)\]?)', 
                               create_table_sql, re.IGNORECASE)
        if table_match:
            table_info['name'] = table_match.group(2) or table_match.group(1)
        
        # Extract columns
        column_pattern = r'(?:\[?(\w+)\]?)\s+(\w+(?:\([^)]+\))?)\s*((?:NOT\s+)?NULL)?(?:\s+DEFAULT\s+([^,\n]+))?'
        columns = re.findall(column_pattern, create_table_sql)
        
        for col_name, col_type, nullable, default in columns:
            if col_name.upper() not in ['CONSTRAINT', 'PRIMARY', 'FOREIGN', 'INDEX', 'UNIQUE']:
                table_info['columns'].append({
                    'name': col_name,
                    'type': col_type,
                    'nullable': 'NOT NULL' not in (nullable or '').upper(),
                    'default': default.strip() if default else None
                })
        
        # Extract primary key
        pk_match = re.search(r'PRIMARY\s+KEY\s*\(([^)]+)\)', create_table_sql, re.IGNORECASE)
        if pk_match:
            table_info['primary_key'] = [col.strip().strip('[]') for col in pk_match.group(1).split(',')]
        
        return table_info
    
    def generate_postgresql_table(self, table_info: Dict) -> str:
        """Generate PostgreSQL CREATE TABLE statement"""
        lines = []
        lines.append(f"-- Table: {table_info['name']}")
        lines.append(f"CREATE TABLE IF NOT EXISTS {table_info['name']} (")
        
        # Add columns
        col_definitions = []
        for col in table_info['columns']:
            col_def = f"    {col['name']} {self.convert_data_type(col['type'])}"
            
            if not col['nullable']:
                col_def += " NOT NULL"
            
            if col['default']:
                default_val = self.convert_default_value(col['default'])
                if default_val:
                    col_def += f" DEFAULT {default_val}"
            
            col_definitions.append(col_def)
        
        # Add primary key if exists
        if table_info['primary_key']:
            pk_cols = ', '.join(table_info['primary_key'])
            col_definitions.append(f"    PRIMARY KEY ({pk_cols})")
        
        lines.append(',\n'.join(col_definitions))
        lines.append(');')
        
        # Add hypertable conversion if applicable
        if table_info['name'] in self.HYPERTABLE_CONFIGS:
            config = self.HYPERTABLE_CONFIGS[table_info['name']]
            lines.append('')
            lines.append(f"-- Convert to hypertable for time-series optimization")
            lines.append(f"SELECT create_hypertable('{table_info['name']}',")
            lines.append(f"    '{config['time_column']}',")
            lines.append(f"    chunk_time_interval => INTERVAL '{config['chunk_interval']}',")
            lines.append(f"    if_not_exists => TRUE);")
        
        return '\n'.join(lines)
    
    def convert_indexes(self, sql_server_indexes: List[str]) -> List[str]:
        """Convert SQL Server indexes to PostgreSQL"""
        pg_indexes = []
        
        for idx_sql in sql_server_indexes:
            # Parse index definition
            idx_match = re.search(
                r'CREATE\s+(?:(UNIQUE|CLUSTERED|NONCLUSTERED)\s+)?INDEX\s+(?:\[?(\w+)\]?)\s+ON\s+(?:\[?(\w+)\]?)(?:\s*\(([^)]+)\))?',
                idx_sql, re.IGNORECASE
            )
            
            if idx_match:
                idx_type = idx_match.group(1) or ''
                idx_name = idx_match.group(2)
                table_name = idx_match.group(3)
                columns = idx_match.group(4)
                
                # Build PostgreSQL index
                pg_idx = "CREATE"
                if 'UNIQUE' in idx_type.upper():
                    pg_idx += " UNIQUE"
                
                pg_idx += f" INDEX IF NOT EXISTS {idx_name}"
                pg_idx += f" ON {table_name}"
                
                if columns:
                    # Clean column names
                    clean_cols = ', '.join([col.strip().strip('[]') for col in columns.split(',')])
                    pg_idx += f" ({clean_cols})"
                
                pg_indexes.append(pg_idx + ";")
        
        return pg_indexes

def convert_sql_server_schema(sql_file_path: str, output_path: str):
    """Convert entire SQL Server schema file to PostgreSQL"""
    converter = SchemaConverter()
    
    with open(sql_file_path, 'r') as f:
        sql_content = f.read()
    
    # Split into individual CREATE TABLE statements
    create_tables = re.findall(
        r'CREATE\s+TABLE[^;]+;',
        sql_content,
        re.IGNORECASE | re.DOTALL
    )
    
    pg_statements = []
    pg_statements.append("-- PostgreSQL Schema converted from SQL Server")
    pg_statements.append(f"-- Generated: {datetime.now().isoformat()}")
    pg_statements.append("")
    pg_statements.append("-- Enable required extensions")
    pg_statements.append("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    pg_statements.append("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    pg_statements.append("")
    
    for create_table in create_tables:
        table_info = converter.parse_sql_server_table(create_table)
        if table_info['name']:
            pg_table = converter.generate_postgresql_table(table_info)
            pg_statements.append(pg_table)
            pg_statements.append("")
    
    # Write output
    with open(output_path, 'w') as f:
        f.write('\n'.join(pg_statements))
    
    print(f"Schema converted successfully: {output_path}")

if __name__ == "__main__":
    # Convert main production tables
    convert_sql_server_schema(
        r"C:\Users\E1791\Kitepy\breezepython\sql\create_production_tables.sql",
        r"C:\Users\E1791\Kitepy\breezepython\database_migration\postgresql_schema.sql"
    )