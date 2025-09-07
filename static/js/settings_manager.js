/**
 * Unified Settings Manager
 * Replaces all localStorage operations with API-backed storage
 * Provides seamless migration from localStorage to database
 */

class SettingsManager {
    constructor(apiClient) {
        this.apiClient = apiClient || window.apiClient;
        this.cache = new Map();
        this.pendingSync = new Set();
        this.syncInterval = null;
        this.migrationComplete = false;
        
        // Start migration and sync
        this.initialize();
    }

    async initialize() {
        // Migrate existing localStorage data
        await this.migrateFromLocalStorage();
        
        // Start auto-sync
        this.startAutoSync();
        
        // Load initial settings from API
        await this.loadAllSettings();
    }

    /**
     * Get a setting value (replaces localStorage.getItem)
     */
    async getItem(key) {
        // Check cache first
        if (this.cache.has(key)) {
            return this.cache.get(key);
        }

        try {
            // Fetch from API
            const value = await this.apiClient.getSetting(key);
            this.cache.set(key, value);
            return value;
        } catch (error) {
            console.error(`Failed to get setting ${key}:`, error);
            
            // Fallback to localStorage during migration
            if (!this.migrationComplete) {
                return localStorage.getItem(key);
            }
            return null;
        }
    }

    /**
     * Set a setting value (replaces localStorage.setItem)
     */
    async setItem(key, value, category = 'general') {
        // Update cache immediately (optimistic update)
        this.cache.set(key, value);
        
        // Mark for sync
        this.pendingSync.add({key, value, category});
        
        try {
            // Save to API
            await this.apiClient.setSetting(key, value, category);
            
            // Remove from pending sync
            this.pendingSync.delete({key, value, category});
            
            return true;
        } catch (error) {
            console.error(`Failed to set setting ${key}:`, error);
            
            // Keep in pending sync for retry
            return false;
        }
    }

    /**
     * Remove a setting (replaces localStorage.removeItem)
     */
    async removeItem(key) {
        // Remove from cache
        this.cache.delete(key);
        
        try {
            // Delete from API
            await this.apiClient.request('DELETE', `/settings/${key}`);
            return true;
        } catch (error) {
            console.error(`Failed to remove setting ${key}:`, error);
            return false;
        }
    }

    /**
     * Clear all settings (replaces localStorage.clear)
     */
    async clear() {
        // Clear cache
        this.cache.clear();
        
        try {
            // Clear from API
            await this.apiClient.request('DELETE', '/settings/all');
            return true;
        } catch (error) {
            console.error('Failed to clear settings:', error);
            return false;
        }
    }

    /**
     * Get all settings
     */
    async getAllSettings() {
        try {
            const settings = await this.apiClient.getAllSettings();
            
            // Update cache
            for (const [key, value] of Object.entries(settings)) {
                this.cache.set(key, value);
            }
            
            return settings;
        } catch (error) {
            console.error('Failed to get all settings:', error);
            return {};
        }
    }

    /**
     * Migrate existing localStorage data to API
     */
    async migrateFromLocalStorage() {
        console.log('Starting localStorage migration...');
        
        const keysToMigrate = [
            'tradingMode',
            'autoTradeEnabled',
            'numLots',
            'entryTiming',
            'tradeConfig',
            'tradeConfigTimestamp',
            'weekdayExpiryConfig',
            'exitTimingConfig',
            'signalStates',
            'authToken'
        ];

        // Add dynamic keys for signals
        for (let i = 1; i <= 8; i++) {
            keysToMigrate.push(`signalS${i}Active`);
        }

        const migrationData = {};
        
        for (const key of keysToMigrate) {
            const value = localStorage.getItem(key);
            if (value !== null) {
                migrationData[key] = value;
            }
        }

        if (Object.keys(migrationData).length > 0) {
            try {
                // Bulk save to API
                await this.apiClient.bulkUpdateSettings(migrationData);
                
                // Clear localStorage after successful migration
                for (const key of keysToMigrate) {
                    localStorage.removeItem(key);
                }
                
                console.log(`Migrated ${Object.keys(migrationData).length} settings to API`);
            } catch (error) {
                console.error('Migration failed:', error);
            }
        }

        this.migrationComplete = true;
    }

    /**
     * Load all settings from API into cache
     */
    async loadAllSettings() {
        try {
            const settings = await this.getAllSettings();
            console.log(`Loaded ${Object.keys(settings).length} settings from API`);
            return settings;
        } catch (error) {
            console.error('Failed to load settings:', error);
            return {};
        }
    }

    /**
     * Start auto-sync for pending changes
     */
    startAutoSync() {
        // Sync every 5 seconds
        this.syncInterval = setInterval(() => {
            this.syncPendingChanges();
        }, 5000);
    }

    /**
     * Stop auto-sync
     */
    stopAutoSync() {
        if (this.syncInterval) {
            clearInterval(this.syncInterval);
            this.syncInterval = null;
        }
    }

    /**
     * Sync pending changes to API
     */
    async syncPendingChanges() {
        if (this.pendingSync.size === 0) {
            return;
        }

        const changes = Array.from(this.pendingSync);
        const updates = {};
        
        for (const {key, value, category} of changes) {
            updates[key] = {value, category};
        }

        try {
            await this.apiClient.bulkUpdateSettings(updates);
            
            // Clear synced items
            this.pendingSync.clear();
            
            console.log(`Synced ${changes.length} pending changes`);
        } catch (error) {
            console.error('Failed to sync pending changes:', error);
        }
    }

    /**
     * Subscribe to setting changes
     */
    subscribe(key, callback) {
        // Create event listener for setting changes
        window.addEventListener(`setting-changed-${key}`, callback);
    }

    /**
     * Unsubscribe from setting changes
     */
    unsubscribe(key, callback) {
        window.removeEventListener(`setting-changed-${key}`, callback);
    }

    /**
     * Emit setting change event
     */
    emitChange(key, value) {
        const event = new CustomEvent(`setting-changed-${key}`, {
            detail: {key, value}
        });
        window.dispatchEvent(event);
    }

    /**
     * Get setting with default value
     */
    async get(key, defaultValue = null) {
        const value = await this.getItem(key);
        return value !== null ? value : defaultValue;
    }

    /**
     * Set setting and emit change
     */
    async set(key, value, category = 'general') {
        const success = await this.setItem(key, value, category);
        if (success) {
            this.emitChange(key, value);
        }
        return success;
    }

    /**
     * Check if setting exists
     */
    async has(key) {
        const value = await this.getItem(key);
        return value !== null;
    }

    /**
     * Get JSON parsed value
     */
    async getJSON(key, defaultValue = null) {
        const value = await this.getItem(key);
        if (value === null) {
            return defaultValue;
        }
        
        try {
            return JSON.parse(value);
        } catch {
            return defaultValue;
        }
    }

    /**
     * Set JSON stringified value
     */
    async setJSON(key, value, category = 'general') {
        return await this.set(key, JSON.stringify(value), category);
    }

    /**
     * Get boolean value
     */
    async getBool(key, defaultValue = false) {
        const value = await this.getItem(key);
        if (value === null) {
            return defaultValue;
        }
        return value === 'true' || value === true;
    }

    /**
     * Set boolean value
     */
    async setBool(key, value, category = 'general') {
        return await this.set(key, String(value), category);
    }

    /**
     * Get number value
     */
    async getNumber(key, defaultValue = 0) {
        const value = await this.getItem(key);
        if (value === null) {
            return defaultValue;
        }
        const num = Number(value);
        return isNaN(num) ? defaultValue : num;
    }

    /**
     * Set number value
     */
    async setNumber(key, value, category = 'general') {
        return await this.set(key, String(value), category);
    }
}

// Create global settings manager instance
window.settingsManager = new SettingsManager(window.apiClient);

// Provide backward compatibility layer
window.localStorageCompat = {
    getItem: (key) => {
        // Return from cache synchronously if available
        if (window.settingsManager.cache.has(key)) {
            return window.settingsManager.cache.get(key);
        }
        // Otherwise trigger async load and return null
        window.settingsManager.getItem(key).then(value => {
            if (value !== null) {
                window.settingsManager.cache.set(key, value);
            }
        });
        return null;
    },
    
    setItem: (key, value) => {
        // Set in cache immediately
        window.settingsManager.cache.set(key, value);
        // Trigger async save
        window.settingsManager.setItem(key, value);
    },
    
    removeItem: (key) => {
        window.settingsManager.removeItem(key);
    },
    
    clear: () => {
        window.settingsManager.clear();
    }
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SettingsManager;
}