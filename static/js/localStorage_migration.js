/**
 * localStorage Migration Helper
 * This file provides drop-in replacements for all localStorage operations
 * Simply include this after settings_manager.js and api_client.js
 */

(function() {
    'use strict';
    
    // Wait for settings manager to be ready
    if (!window.settingsManager) {
        console.error('Settings Manager not initialized. Make sure to include settings_manager.js first.');
        return;
    }

    // Store original localStorage for migration purposes
    const originalLocalStorage = window.localStorage;
    
    // Create a proxy for localStorage that redirects to settings manager
    const localStorageProxy = new Proxy({}, {
        get(target, prop) {
            switch(prop) {
                case 'getItem':
                    return function(key) {
                        // Try to get from settings manager synchronously
                        const cachedValue = window.settingsManager.cache.get(key);
                        if (cachedValue !== undefined) {
                            return cachedValue;
                        }
                        
                        // Trigger async load for next time
                        window.settingsManager.getItem(key).then(value => {
                            if (value !== null) {
                                console.log(`Loaded setting ${key} from API:`, value);
                            }
                        }).catch(err => {
                            console.error(`Failed to load setting ${key}:`, err);
                        });
                        
                        // Return null for now (same as localStorage behavior for missing keys)
                        return null;
                    };
                    
                case 'setItem':
                    return function(key, value) {
                        // Update cache immediately
                        window.settingsManager.cache.set(key, value);
                        
                        // Determine category based on key
                        let category = 'general';
                        if (key.includes('trade') || key.includes('Trade')) {
                            category = 'trading';
                        } else if (key.includes('signal') || key.includes('Signal')) {
                            category = 'signals';
                        } else if (key.includes('expiry') || key.includes('Expiry')) {
                            category = 'expiry';
                        } else if (key.includes('exit') || key.includes('Exit')) {
                            category = 'exit';
                        } else if (key === 'authToken') {
                            category = 'auth';
                        }
                        
                        // Trigger async save
                        window.settingsManager.setItem(key, value, category).then(() => {
                            console.log(`Saved setting ${key} to API`);
                        }).catch(err => {
                            console.error(`Failed to save setting ${key}:`, err);
                            // Fallback to original localStorage
                            originalLocalStorage.setItem(key, value);
                        });
                    };
                    
                case 'removeItem':
                    return function(key) {
                        // Remove from cache
                        window.settingsManager.cache.delete(key);
                        
                        // Trigger async removal
                        window.settingsManager.removeItem(key).then(() => {
                            console.log(`Removed setting ${key} from API`);
                        }).catch(err => {
                            console.error(`Failed to remove setting ${key}:`, err);
                        });
                    };
                    
                case 'clear':
                    return function() {
                        // Clear cache
                        window.settingsManager.cache.clear();
                        
                        // Trigger async clear
                        window.settingsManager.clear().then(() => {
                            console.log('Cleared all settings from API');
                        }).catch(err => {
                            console.error('Failed to clear settings:', err);
                        });
                    };
                    
                case 'key':
                    return function(index) {
                        const keys = Array.from(window.settingsManager.cache.keys());
                        return keys[index] || null;
                    };
                    
                case 'length':
                    return window.settingsManager.cache.size;
                    
                default:
                    return target[prop];
            }
        }
    });

    // Replace window.localStorage with our proxy
    try {
        Object.defineProperty(window, 'localStorage', {
            get: function() {
                return localStorageProxy;
            },
            configurable: true
        });
        
        console.log('localStorage has been successfully proxied to Settings Manager');
    } catch (e) {
        console.error('Failed to proxy localStorage:', e);
        
        // Fallback: Replace individual methods
        window.localStorage.getItem = localStorageProxy.getItem;
        window.localStorage.setItem = localStorageProxy.setItem;
        window.localStorage.removeItem = localStorageProxy.removeItem;
        window.localStorage.clear = localStorageProxy.clear;
    }

    // Preload commonly used settings
    const commonSettings = [
        'tradingMode',
        'autoTradeEnabled', 
        'numLots',
        'entryTiming',
        'tradeConfig',
        'weekdayExpiryConfig',
        'exitTimingConfig',
        'signalStates'
    ];

    // Preload settings asynchronously
    Promise.all(commonSettings.map(key => 
        window.settingsManager.getItem(key)
    )).then(() => {
        console.log('Common settings preloaded');
    });

    // Helper functions for specific data types
    window.getSettingJSON = async function(key, defaultValue = null) {
        try {
            const value = await window.settingsManager.getItem(key);
            return value ? JSON.parse(value) : defaultValue;
        } catch (e) {
            console.error(`Failed to parse JSON for ${key}:`, e);
            return defaultValue;
        }
    };

    window.setSettingJSON = async function(key, value, category = 'general') {
        try {
            await window.settingsManager.setItem(key, JSON.stringify(value), category);
            return true;
        } catch (e) {
            console.error(`Failed to save JSON for ${key}:`, e);
            return false;
        }
    };

    window.getSettingBool = async function(key, defaultValue = false) {
        const value = await window.settingsManager.getItem(key);
        if (value === null || value === undefined) {
            return defaultValue;
        }
        return value === 'true' || value === true;
    };

    window.setSettingBool = async function(key, value, category = 'general') {
        await window.settingsManager.setItem(key, String(value), category);
    };

    window.getSettingNumber = async function(key, defaultValue = 0) {
        const value = await window.settingsManager.getItem(key);
        if (value === null || value === undefined) {
            return defaultValue;
        }
        const num = Number(value);
        return isNaN(num) ? defaultValue : num;
    };

    window.setSettingNumber = async function(key, value, category = 'general') {
        await window.settingsManager.setItem(key, String(value), category);
    };

    // Expose migration status
    window.isLocalStorageMigrated = true;
    
    // Log migration completion
    console.log('localStorage migration layer activated. All localStorage operations will now use the API-backed Settings Manager.');
    
})();