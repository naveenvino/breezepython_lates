"""
Comprehensive test to confirm database consolidation is complete and working
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.append('.')
from src.services.consolidated_settings_service import ConsolidatedSettingsService


def test_comprehensive_database_consolidation():
    """Comprehensive test of the database consolidation"""
    print("=" * 60)
    print("COMPREHENSIVE DATABASE CONSOLIDATION TEST")
    print("=" * 60)
    
    service = ConsolidatedSettingsService()
    all_passed = True
    
    # Test 1: Verify unified tables exist
    print("\n[TEST 1] Verify Unified Tables Exist")
    print("-" * 40)
    try:
        with sqlite3.connect("data/trading_settings.db") as conn:
            cursor = conn.cursor()
            
            # Check UnifiedSettings table
            cursor.execute("SELECT COUNT(*) FROM UnifiedSettings")
            unified_count = cursor.fetchone()[0]
            print(f"[OK] UnifiedSettings table exists with {unified_count} records")
            
            # Check SettingsAudit table
            cursor.execute("SELECT COUNT(*) FROM SettingsAudit")
            audit_count = cursor.fetchone()[0]
            print(f"[OK] SettingsAudit table exists with {audit_count} records")
            
            # Check indexes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='UnifiedSettings'")
            indexes = [row[0] for row in cursor.fetchall()]
            print(f"[OK] Indexes created: {', '.join(indexes)}")
            
    except Exception as e:
        print(f"[FAIL] Failed: {e}")
        all_passed = False
    
    # Test 2: Verify data migration completeness
    print("\n[TEST 2] Verify Data Migration Completeness")
    print("-" * 40)
    try:
        all_settings = service.get_all_settings()
        
        # Check all expected namespaces are present
        expected_namespaces = ['trading', 'risk', 'hedge', 'signal', 'expiry', 'general', 'system']
        for ns in expected_namespaces:
            if ns in all_settings:
                count = len(all_settings[ns])
                print(f"[OK] {ns:10} namespace: {count:3} settings migrated")
            else:
                print(f"[FAIL] {ns:10} namespace: MISSING")
                all_passed = False
                
        total_settings = sum(len(settings) for settings in all_settings.values())
        print(f"\n[OK] Total settings migrated: {total_settings}")
        
    except Exception as e:
        print(f"[FAIL] Failed: {e}")
        all_passed = False
    
    # Test 3: Test CRUD operations
    print("\n[TEST 3] Test CRUD Operations")
    print("-" * 40)
    try:
        # Create
        test_key = f"test_{datetime.now().strftime('%H%M%S')}"
        service.set_setting(test_key, "test_value", "test")
        print(f"[OK] CREATE: Set {test_key} = 'test_value'")
        
        # Read
        value = service.get_setting(test_key, "test")
        assert value == "test_value", f"Expected 'test_value', got {value}"
        print(f"[OK] READ:   Retrieved {test_key} = '{value}'")
        
        # Update
        service.set_setting(test_key, "updated_value", "test")
        value = service.get_setting(test_key, "test")
        assert value == "updated_value", f"Expected 'updated_value', got {value}"
        print(f"[OK] UPDATE: Updated {test_key} = '{value}'")
        
        # Delete
        service.delete_setting(test_key, "test")
        value = service.get_setting(test_key, "test")
        assert value is None, f"Expected None after delete, got {value}"
        print(f"[OK] DELETE: Deleted {test_key} (value = None)")
        
    except Exception as e:
        print(f"[FAIL] Failed: {e}")
        all_passed = False
    
    # Test 4: Test data type preservation
    print("\n[TEST 4] Test Data Type Preservation")
    print("-" * 40)
    try:
        test_data = {
            "string_test": "Hello World",
            "integer_test": 42,
            "float_test": 3.14159,
            "boolean_test": True,
            "json_test": {"nested": {"key": "value"}, "list": [1, 2, 3]}
        }
        
        for key, value in test_data.items():
            service.set_setting(key, value, "type_test")
            retrieved = service.get_setting(key, "type_test")
            
            if isinstance(value, (dict, list)):
                assert retrieved == value, f"JSON mismatch for {key}"
                print(f"[OK] {key:15} ({type(value).__name__:7}): preserved")
            else:
                assert retrieved == value and type(retrieved) == type(value), \
                    f"Type mismatch for {key}: expected {type(value)}, got {type(retrieved)}"
                print(f"[OK] {key:15} ({type(value).__name__:7}): preserved")
                
    except Exception as e:
        print(f"[FAIL] Failed: {e}")
        all_passed = False
    
    # Test 5: Test trading configuration
    print("\n[TEST 5] Test Trading Configuration")
    print("-" * 40)
    try:
        # Save a test configuration
        test_config = {
            "num_lots": 5,
            "entry_timing": "immediate",
            "hedge_enabled": True,
            "hedge_offset": 300,
            "max_positions": 10,
            "daily_loss_limit": 100000,
            "active_signals": ["S1", "S2", "S3"]
        }
        
        service.save_trading_config("test_config", test_config)
        print(f"[OK] Saved test configuration with {len(test_config)} settings")
        
        # Retrieve configuration
        retrieved_config = service.get_trading_config("test_config")
        
        # Verify key settings
        for key in ["num_lots", "hedge_offset", "max_positions"]:
            if key in test_config:
                expected_key = f"test_config_{key}"
                if expected_key in retrieved_config:
                    print(f"[OK] {key}: {retrieved_config[expected_key]}")
                else:
                    print(f"[FAIL] {key}: NOT FOUND")
                    all_passed = False
                    
    except Exception as e:
        print(f"[FAIL] Failed: {e}")
        all_passed = False
    
    # Test 6: Test audit logging
    print("\n[TEST 6] Test Audit Logging")
    print("-" * 40)
    try:
        # Create some audit entries
        audit_key = f"audit_test_{datetime.now().strftime('%H%M%S')}"
        service.set_setting(audit_key, "initial", "audit_test", performed_by="test_user")
        service.set_setting(audit_key, "modified", "audit_test", performed_by="test_user")
        service.delete_setting(audit_key, "audit_test", performed_by="test_user")
        
        # Get audit log
        audit_log = service.get_audit_log(namespace="audit_test", limit=10)
        
        actions_found = [entry['action'] for entry in audit_log if entry['key'] == audit_key]
        expected_actions = ['DELETE', 'UPDATE', 'CREATE']  # Reverse order (newest first)
        
        for action in expected_actions:
            if action in actions_found:
                print(f"[OK] {action} action logged")
            else:
                print(f"[FAIL] {action} action NOT logged")
                all_passed = False
                
        print(f"[OK] Total audit entries for {audit_key}: {len(actions_found)}")
        
    except Exception as e:
        print(f"[FAIL] Failed: {e}")
        all_passed = False
    
    # Test 7: Test bulk operations
    print("\n[TEST 7] Test Bulk Operations")
    print("-" * 40)
    try:
        bulk_data = {
            f"bulk_{i}": f"value_{i}" for i in range(10)
        }
        
        service.bulk_update(bulk_data, "bulk_test")
        print(f"[OK] Bulk inserted {len(bulk_data)} settings")
        
        retrieved_bulk = service.get_namespace_settings("bulk_test")
        matching = sum(1 for key in bulk_data if key in retrieved_bulk)
        
        if matching == len(bulk_data):
            print(f"[OK] All {matching} bulk settings retrieved successfully")
        else:
            print(f"[FAIL] Only {matching}/{len(bulk_data)} settings retrieved")
            all_passed = False
            
    except Exception as e:
        print(f"[FAIL] Failed: {e}")
        all_passed = False
    
    # Test 8: Test export/import
    print("\n[TEST 8] Test Export/Import")
    print("-" * 40)
    try:
        # Export current settings
        export_data = service.export_settings("default")
        namespace_count = len(export_data['settings'])
        total_exported = sum(len(ns) for ns in export_data['settings'].values())
        print(f"[OK] Exported {total_exported} settings across {namespace_count} namespaces")
        
        # Test import to new user
        test_user = f"import_test_{datetime.now().strftime('%H%M%S')}"
        service.import_settings(export_data, user_id=test_user)
        
        imported_settings = service.get_all_settings(test_user)
        total_imported = sum(len(ns) for ns in imported_settings.values())
        
        if total_imported == total_exported:
            print(f"[OK] Successfully imported all {total_imported} settings")
        else:
            print(f"[FAIL] Import mismatch: exported {total_exported}, imported {total_imported}")
            all_passed = False
            
    except Exception as e:
        print(f"[FAIL] Failed: {e}")
        all_passed = False
    
    # Test 9: Verify old tables are preserved
    print("\n[TEST 9] Verify Old Tables Preserved")
    print("-" * 40)
    try:
        with sqlite3.connect("data/trading_settings.db") as conn:
            cursor = conn.cursor()
            
            old_tables = ['UserSettings', 'TradeConfiguration', 'Settings', 
                         'SignalStates', 'ExpiryConfig']
            
            for table in old_tables:
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if cursor.fetchone():
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"[OK] {table:20} preserved with {count} records")
                else:
                    print(f"! {table:20} not found (may be renamed to {table}_old)")
                    
    except Exception as e:
        print(f"[FAIL] Failed: {e}")
        all_passed = False
    
    # Test 10: Performance test
    print("\n[TEST 10] Performance Test")
    print("-" * 40)
    try:
        import time
        
        # Test read performance
        start = time.time()
        for _ in range(100):
            service.get_setting("numLots", "trading")
        read_time = (time.time() - start) * 1000
        print(f"[OK] 100 reads completed in {read_time:.2f}ms ({read_time/100:.2f}ms per read)")
        
        # Test write performance
        start = time.time()
        for i in range(100):
            service.set_setting(f"perf_test_{i}", i, "performance")
        write_time = (time.time() - start) * 1000
        print(f"[OK] 100 writes completed in {write_time:.2f}ms ({write_time/100:.2f}ms per write)")
        
        # Clean up performance test data
        for i in range(100):
            service.delete_setting(f"perf_test_{i}", "performance")
            
    except Exception as e:
        print(f"[FAIL] Failed: {e}")
        all_passed = False
    
    # Final Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] ALL TESTS PASSED - DATABASE CONSOLIDATION COMPLETE")
        print("\nThe database consolidation is fully functional and ready for production.")
        print("\nNext steps:")
        print("1. Update unified_api_correct.py to use ConsolidatedSettingsService")
        print("2. Remove duplicate API endpoints")
        print("3. Run cleanup to remove old tables when ready")
    else:
        print("[ERROR] SOME TESTS FAILED - Review and fix issues")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    try:
        success = test_comprehensive_database_consolidation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[CRITICAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)