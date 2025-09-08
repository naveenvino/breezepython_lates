"""
Test script for the unified settings system
"""

import sys
sys.path.append('.')

from src.services.consolidated_settings_service import ConsolidatedSettingsService


def test_unified_settings():
    print("=== Testing Unified Settings System ===\n")
    
    # Initialize service
    service = ConsolidatedSettingsService()
    
    # Test 1: Get existing settings
    print("Test 1: Get existing settings from migrated data")
    trading_settings = service.get_namespace_settings("trading")
    print(f"Trading settings count: {len(trading_settings)}")
    for key, value in list(trading_settings.items())[:3]:
        print(f"  {key}: {value}")
    
    # Test 2: Get specific setting
    print("\nTest 2: Get specific setting")
    num_lots = service.get_setting("numLots", "trading", default=1)
    print(f"numLots: {num_lots}")
    
    # Test 3: Set new setting
    print("\nTest 3: Set new setting")
    success = service.set_setting("test_setting", "test_value", "general", performed_by="test_script")
    print(f"Setting saved: {success}")
    retrieved = service.get_setting("test_setting", "general")
    print(f"Retrieved value: {retrieved}")
    
    # Test 4: Update existing setting
    print("\nTest 4: Update existing setting")
    old_value = service.get_setting("test_setting", "general")
    success = service.set_setting("test_setting", "updated_value", "general", performed_by="test_script")
    new_value = service.get_setting("test_setting", "general")
    print(f"Old value: {old_value}, New value: {new_value}")
    
    # Test 5: Bulk update
    print("\nTest 5: Bulk update settings")
    test_settings = {
        "bulk_test_1": "value1",
        "bulk_test_2": 42,
        "bulk_test_3": True,
        "bulk_test_4": {"nested": "json"}
    }
    success = service.bulk_update(test_settings, "test", performed_by="test_script")
    print(f"Bulk update success: {success}")
    
    # Verify bulk update
    retrieved_bulk = service.get_namespace_settings("test")
    print(f"Retrieved bulk settings:")
    for key, value in retrieved_bulk.items():
        print(f"  {key}: {value} (type: {type(value).__name__})")
    
    # Test 6: Get trading configuration
    print("\nTest 6: Get trading configuration")
    config = service.get_trading_config()
    print(f"Config keys: {list(config.keys())[:5]}...")
    
    # Test 7: Get all settings
    print("\nTest 7: Get all settings by namespace")
    all_settings = service.get_all_settings()
    for namespace, settings in all_settings.items():
        print(f"  {namespace}: {len(settings)} settings")
    
    # Test 8: Audit log
    print("\nTest 8: Check audit log")
    audit_log = service.get_audit_log(limit=5)
    print(f"Recent audit entries: {len(audit_log)}")
    for entry in audit_log[:2]:
        print(f"  {entry['action']}: {entry['namespace']}.{entry['key']} by {entry['performed_by']}")
    
    # Test 9: Delete setting
    print("\nTest 9: Delete setting (soft delete)")
    success = service.delete_setting("test_setting", "general", performed_by="test_script")
    print(f"Delete success: {success}")
    deleted_value = service.get_setting("test_setting", "general")
    print(f"Value after delete: {deleted_value} (should be None)")
    
    # Test 10: Export/Import
    print("\nTest 10: Export/Import settings")
    export_data = service.export_settings()
    print(f"Exported namespaces: {list(export_data['settings'].keys())}")
    
    print("\n[SUCCESS] All tests completed!")
    return True


if __name__ == "__main__":
    try:
        test_unified_settings()
    except Exception as e:
        print(f"[ERROR] Test failed: {str(e)}")
        import traceback
        traceback.print_exc()