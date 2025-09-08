
# =================== UNIFIED SETTINGS ENDPOINTS ===================
# Using ConsolidatedSettingsService for all settings operations

@app.get("/settings", tags=["System - Settings"])
async def get_user_settings():
    """Get all settings for the default user"""
    try:
        all_settings = settings_service.get_all_settings("default")
        
        # Flatten for backward compatibility
        flat_settings = {}
        for namespace, settings in all_settings.items():
            for key, value in settings.items():
                # Use original key names for compatibility
                flat_settings[key] = value
        
        return {"settings": flat_settings}
    except Exception as e:
        logger.error(f"Settings fetch error: {str(e)}")
        return {"settings": {}}

@app.get("/api/settings", tags=["System - Settings"])
async def get_api_settings():
    """Alias endpoint for UI compatibility"""
    return await get_user_settings()

@app.post("/settings", tags=["System - Settings"])
async def save_user_settings(settings: dict):
    """Save user settings"""
    try:
        # Determine namespace for each setting
        for key, value in settings.items():
            namespace = "general"  # Default namespace
            
            # Determine namespace based on key patterns
            if "hedge" in key.lower() or "offset" in key.lower():
                namespace = "hedge"
            elif any(x in key.lower() for x in ["risk", "loss", "profit", "exposure", "stop"]):
                namespace = "risk"
            elif any(x in key.lower() for x in ["signal", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]):
                namespace = "signal"
            elif any(x in key.lower() for x in ["trade", "trading", "lot", "position", "auto"]):
                namespace = "trading"
            elif any(x in key.lower() for x in ["expiry", "exit", "square"]):
                namespace = "expiry"
            
            settings_service.set_setting(key, value, namespace, "default", "api")
        
        return {"status": "success", "message": f"Saved {len(settings)} settings"}
    except Exception as e:
        logger.error(f"Settings save error: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.post("/settings/bulk", tags=["System - Settings"])
async def save_bulk_settings(settings: dict):
    """Bulk save settings"""
    try:
        # Group by namespace
        namespaced = {}
        for key, value in settings.items():
            namespace = "general"
            if "hedge" in key.lower():
                namespace = "hedge"
            elif any(x in key.lower() for x in ["risk", "loss", "profit"]):
                namespace = "risk"
            elif "signal" in key.lower():
                namespace = "signal"
            elif any(x in key.lower() for x in ["trade", "trading", "lot"]):
                namespace = "trading"
            
            if namespace not in namespaced:
                namespaced[namespace] = {}
            namespaced[namespace][key] = value
        
        # Bulk update each namespace
        for namespace, ns_settings in namespaced.items():
            settings_service.bulk_update(ns_settings, namespace, "default", "api")
        
        return {"status": "success", "message": f"Saved {len(settings)} settings"}
    except Exception as e:
        logger.error(f"Bulk settings save error: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.get("/settings/{key}", tags=["System - Settings"])
async def get_setting_by_key(key: str):
    """Get a specific setting by key"""
    try:
        # Try all namespaces
        for namespace in ["general", "trading", "risk", "hedge", "signal", "expiry", "system"]:
            value = settings_service.get_setting(key, namespace, "default")
            if value is not None:
                return {"key": key, "value": value, "namespace": namespace}
        
        return {"key": key, "value": None, "namespace": None}
    except Exception as e:
        logger.error(f"Setting fetch error: {str(e)}")
        return {"error": str(e)}

@app.put("/settings/{key}", tags=["System - Settings"])
async def update_setting(key: str, data: dict):
    """Update a specific setting"""
    try:
        value = data.get("value")
        namespace = data.get("namespace", "general")
        
        success = settings_service.set_setting(key, value, namespace, "default", "api")
        
        if success:
            return {"status": "success", "key": key, "value": value}
        else:
            return {"status": "error", "message": "Failed to update setting"}
    except Exception as e:
        logger.error(f"Setting update error: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.delete("/settings/{key}", tags=["System - Settings"])
async def delete_setting(key: str):
    """Delete a specific setting"""
    try:
        # Try all namespaces
        deleted = False
        for namespace in ["general", "trading", "risk", "hedge", "signal", "expiry", "system"]:
            if settings_service.delete_setting(key, namespace, "default", "api"):
                deleted = True
                break
        
        if deleted:
            return {"status": "success", "message": f"Deleted {key}"}
        else:
            return {"status": "error", "message": f"Setting {key} not found"}
    except Exception as e:
        logger.error(f"Setting delete error: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.get("/settings/all", tags=["System - Settings"])
async def get_all_settings():
    """Get all settings organized by namespace"""
    try:
        all_settings = settings_service.get_all_settings("default")
        return {"settings": all_settings}
    except Exception as e:
        logger.error(f"Settings fetch error: {str(e)}")
        return {"settings": {}}

@app.get("/settings/export", tags=["System - Settings"])
async def export_settings():
    """Export all settings for backup"""
    try:
        export_data = settings_service.export_settings("default")
        return export_data
    except Exception as e:
        logger.error(f"Settings export error: {str(e)}")
        return {"error": str(e)}

@app.post("/settings/import", tags=["System - Settings"])
async def import_settings(data: dict):
    """Import settings from backup"""
    try:
        success = settings_service.import_settings(data, "default", "api_import")
        
        if success:
            return {"status": "success", "message": "Settings imported successfully"}
        else:
            return {"status": "error", "message": "Failed to import settings"}
    except Exception as e:
        logger.error(f"Settings import error: {str(e)}")
        return {"status": "error", "message": str(e)}

# Trading configuration endpoints using unified service
@app.post("/api/trade-config/save", tags=["Settings"])
async def save_trade_config(config: dict):
    """Save trading configuration"""
    try:
        config_name = config.get("config_name", "default")
        settings_service.save_trading_config(config_name, config, "default", "api")
        return {"status": "success", "message": f"Configuration '{config_name}' saved"}
    except Exception as e:
        logger.error(f"Config save error: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.get("/api/trade-config/load/{config_name}", tags=["Settings"])
async def load_trade_config(config_name: str):
    """Load trading configuration"""
    try:
        config = settings_service.get_trading_config(config_name, "default")
        return {"status": "success", "config": config}
    except Exception as e:
        logger.error(f"Config load error: {str(e)}")
        return {"status": "error", "message": str(e)}

# =================== END UNIFIED SETTINGS ENDPOINTS ===================
