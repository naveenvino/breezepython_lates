/**
 * State Management System
 * Centralized state management for the trading application
 * Implements Redux-like pattern with actions, reducers, and subscribers
 */

class StateManager {
    constructor() {
        this.state = {};
        this.subscribers = new Map();
        this.middleware = [];
        this.history = [];
        this.maxHistorySize = 50;
        this.isDirty = false;
        this.syncInterval = null;
        
        // Initialize default state
        this.initializeState();
        
        // Start state sync
        this.startStateSync();
    }

    /**
     * Initialize default state structure
     */
    initializeState() {
        this.state = {
            // Trading configuration
            trading: {
                mode: 'LIVE',
                autoTradeEnabled: false,
                numLots: 10,
                entryTiming: 'immediate',
                activeSignals: []
            },
            
            // Position management
            positions: {
                current: [],
                history: [],
                totalPnL: 0,
                dayPnL: 0
            },
            
            // Risk management
            risk: {
                maxLossPerDay: 50000,
                maxPositions: 5,
                stopLossPercent: 30,
                maxLossPerTrade: 20000,
                maxExposure: 200000,
                currentExposure: 0
            },
            
            // Market data
            market: {
                niftySpot: null,
                lastUpdate: null,
                candleData: [],
                vix: null
            },
            
            // Hedge configuration
            hedge: {
                enabled: true,
                method: 'percentage',
                percent: 30,
                offset: 200
            },
            
            // Stop loss configuration
            stopLoss: {
                profitLockEnabled: false,
                profitTarget: 10,
                profitLock: 5,
                trailingStopEnabled: false,
                trailPercent: 1
            },
            
            // Expiry configuration
            expiry: {
                weekdayConfig: {
                    Monday: 'current',
                    Tuesday: 'current',
                    Wednesday: 'current',
                    Thursday: 'current',
                    Friday: 'current'
                },
                selectedExpiry: null,
                exitDayOffset: 2,
                exitTime: '15:15',
                autoSquareOffEnabled: true
            },
            
            // System status
            system: {
                apiConnected: false,
                breezeConnected: false,
                kiteConnected: false,
                killSwitchTriggered: false,
                killSwitchState: 'READY',
                lastError: null
            },
            
            // UI state
            ui: {
                loading: false,
                notifications: [],
                modals: {},
                selectedTab: 'dashboard'
            }
        };
    }

    /**
     * Get current state
     */
    getState() {
        return this.state;
    }

    /**
     * Get specific state path
     */
    get(path) {
        const keys = path.split('.');
        let current = this.state;
        
        for (const key of keys) {
            if (current[key] === undefined) {
                return undefined;
            }
            current = current[key];
        }
        
        return current;
    }

    /**
     * Set state with path
     */
    set(path, value) {
        const keys = path.split('.');
        const lastKey = keys.pop();
        let current = this.state;
        
        // Navigate to parent object
        for (const key of keys) {
            if (current[key] === undefined) {
                current[key] = {};
            }
            current = current[key];
        }
        
        // Store previous value for history
        const previousValue = current[lastKey];
        
        // Update value
        current[lastKey] = value;
        
        // Mark as dirty
        this.isDirty = true;
        
        // Add to history
        this.addToHistory({
            type: 'SET',
            path: path,
            previousValue: previousValue,
            newValue: value,
            timestamp: Date.now()
        });
        
        // Notify subscribers
        this.notifySubscribers(path, value, previousValue);
        
        return value;
    }

    /**
     * Update state (merge)
     */
    update(path, updates) {
        const current = this.get(path);
        
        if (typeof current === 'object' && current !== null) {
            const newValue = { ...current, ...updates };
            return this.set(path, newValue);
        }
        
        return this.set(path, updates);
    }

    /**
     * Dispatch an action
     */
    dispatch(action) {
        // Run through middleware
        for (const middleware of this.middleware) {
            action = middleware(action, this.state);
            if (!action) return; // Middleware can cancel action
        }
        
        // Handle action
        switch (action.type) {
            case 'SET_TRADING_MODE':
                this.set('trading.mode', action.payload);
                break;
                
            case 'TOGGLE_AUTO_TRADE':
                this.set('trading.autoTradeEnabled', action.payload);
                break;
                
            case 'UPDATE_POSITIONS':
                this.set('positions.current', action.payload);
                this.calculateExposure();
                break;
                
            case 'UPDATE_MARKET_DATA':
                this.update('market', action.payload);
                break;
                
            case 'TRIGGER_KILL_SWITCH':
                this.set('system.killSwitchTriggered', true);
                this.set('system.killSwitchState', action.payload.state || 'TRIGGERED');
                break;
                
            case 'RESET_KILL_SWITCH':
                this.set('system.killSwitchTriggered', false);
                this.set('system.killSwitchState', 'READY');
                break;
                
            case 'ADD_NOTIFICATION':
                const notifications = this.get('ui.notifications') || [];
                notifications.push({
                    id: Date.now(),
                    ...action.payload,
                    timestamp: new Date().toISOString()
                });
                this.set('ui.notifications', notifications);
                break;
                
            case 'REMOVE_NOTIFICATION':
                const currentNotifications = this.get('ui.notifications') || [];
                this.set('ui.notifications', 
                    currentNotifications.filter(n => n.id !== action.payload)
                );
                break;
                
            case 'SET_LOADING':
                this.set('ui.loading', action.payload);
                break;
                
            case 'UPDATE_SIGNAL_STATES':
                this.set('trading.activeSignals', action.payload);
                break;
                
            case 'UPDATE_RISK_LIMITS':
                this.update('risk', action.payload);
                break;
                
            case 'UPDATE_HEDGE_CONFIG':
                this.update('hedge', action.payload);
                break;
                
            case 'UPDATE_STOP_LOSS_CONFIG':
                this.update('stopLoss', action.payload);
                break;
                
            case 'UPDATE_EXPIRY_CONFIG':
                this.update('expiry', action.payload);
                break;
                
            case 'SET_API_CONNECTION':
                this.set('system.apiConnected', action.payload);
                break;
                
            case 'SET_BREEZE_CONNECTION':
                this.set('system.breezeConnected', action.payload);
                break;
                
            case 'SET_KITE_CONNECTION':
                this.set('system.kiteConnected', action.payload);
                break;
                
            case 'SET_ERROR':
                this.set('system.lastError', action.payload);
                break;
                
            case 'CLEAR_ERROR':
                this.set('system.lastError', null);
                break;
                
            default:
                console.warn('Unknown action type:', action.type);
        }
        
        // Add action to history
        this.addToHistory(action);
    }

    /**
     * Subscribe to state changes
     */
    subscribe(path, callback) {
        if (!this.subscribers.has(path)) {
            this.subscribers.set(path, new Set());
        }
        this.subscribers.get(path).add(callback);
        
        // Return unsubscribe function
        return () => {
            const subs = this.subscribers.get(path);
            if (subs) {
                subs.delete(callback);
            }
        };
    }

    /**
     * Notify subscribers of state change
     */
    notifySubscribers(path, newValue, oldValue) {
        // Notify exact path subscribers
        const exactSubs = this.subscribers.get(path);
        if (exactSubs) {
            exactSubs.forEach(callback => {
                try {
                    callback(newValue, oldValue, path);
                } catch (error) {
                    console.error('Subscriber error:', error);
                }
            });
        }
        
        // Notify parent path subscribers
        const pathParts = path.split('.');
        for (let i = pathParts.length - 1; i > 0; i--) {
            const parentPath = pathParts.slice(0, i).join('.');
            const parentSubs = this.subscribers.get(parentPath);
            if (parentSubs) {
                const parentValue = this.get(parentPath);
                parentSubs.forEach(callback => {
                    try {
                        callback(parentValue, null, parentPath);
                    } catch (error) {
                        console.error('Parent subscriber error:', error);
                    }
                });
            }
        }
        
        // Notify global subscribers
        const globalSubs = this.subscribers.get('*');
        if (globalSubs) {
            globalSubs.forEach(callback => {
                try {
                    callback(this.state, null, path);
                } catch (error) {
                    console.error('Global subscriber error:', error);
                }
            });
        }
    }

    /**
     * Add middleware
     */
    use(middleware) {
        this.middleware.push(middleware);
    }

    /**
     * Add to history
     */
    addToHistory(entry) {
        this.history.push({
            ...entry,
            timestamp: entry.timestamp || Date.now()
        });
        
        // Limit history size
        if (this.history.length > this.maxHistorySize) {
            this.history.shift();
        }
    }

    /**
     * Get history
     */
    getHistory(limit = 10) {
        return this.history.slice(-limit);
    }

    /**
     * Calculate current exposure
     */
    calculateExposure() {
        const positions = this.get('positions.current') || [];
        let totalExposure = 0;
        
        for (const position of positions) {
            const lotSize = position.lotSize || 75;
            const quantity = position.quantity || 0;
            const price = position.entryPrice || 0;
            totalExposure += Math.abs(quantity * price);
        }
        
        this.set('risk.currentExposure', totalExposure);
    }

    /**
     * Save state to API
     */
    async saveState() {
        if (!this.isDirty) return;
        
        try {
            const stateToSave = {
                trading: this.state.trading,
                risk: this.state.risk,
                hedge: this.state.hedge,
                stopLoss: this.state.stopLoss,
                expiry: this.state.expiry
            };
            
            await window.settingsManager.setJSON('appState', stateToSave, 'state');
            this.isDirty = false;
            
            console.log('State saved to API');
        } catch (error) {
            console.error('Failed to save state:', error);
        }
    }

    /**
     * Load state from API
     */
    async loadState() {
        try {
            const savedState = await window.settingsManager.getJSON('appState');
            if (savedState) {
                // Merge saved state with current state
                this.state = {
                    ...this.state,
                    ...savedState
                };
                
                console.log('State loaded from API');
                
                // Notify all subscribers
                this.notifySubscribers('*', this.state, null);
            }
        } catch (error) {
            console.error('Failed to load state:', error);
        }
    }

    /**
     * Start auto-sync
     */
    startStateSync() {
        // Save state every 10 seconds if dirty
        this.syncInterval = setInterval(() => {
            if (this.isDirty) {
                this.saveState();
            }
        }, 10000);
        
        // Load initial state
        this.loadState();
    }

    /**
     * Stop auto-sync
     */
    stopStateSync() {
        if (this.syncInterval) {
            clearInterval(this.syncInterval);
            this.syncInterval = null;
        }
    }

    /**
     * Reset state to defaults
     */
    reset() {
        this.initializeState();
        this.history = [];
        this.isDirty = true;
        this.notifySubscribers('*', this.state, null);
    }
}

// Create global state manager instance
window.stateManager = new StateManager();

// Helper functions for common operations
window.getState = (path) => window.stateManager.get(path);
window.setState = (path, value) => window.stateManager.set(path, value);
window.updateState = (path, updates) => window.stateManager.update(path, updates);
window.dispatch = (action) => window.stateManager.dispatch(action);
window.subscribeToState = (path, callback) => window.stateManager.subscribe(path, callback);

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StateManager;
}