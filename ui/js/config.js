/**
 * Unified Configuration for Trading System UI
 * Central configuration file for all modules
 */

const CONFIG = {
    // API Configuration
    API: {
        BASE_URL: 'http://localhost:8000',
        TIMEOUT: 30000,
        RETRY_ATTEMPTS: 3,
        RETRY_DELAY: 1000
    },

    // WebSocket Configuration
    WEBSOCKET: {
        URL: 'ws://localhost:8000/ws',
        RECONNECT_INTERVAL: 5000,
        MAX_RECONNECT_ATTEMPTS: 10,
        HEARTBEAT_INTERVAL: 30000
    },

    // Trading Configuration
    TRADING: {
        DEFAULT_LOTS: 10,
        LOT_SIZE: 75,
        MAX_LOTS_PER_ORDER: 24,
        DEFAULT_HEDGE_OFFSET: 200,
        STOP_LOSS_POINTS: 100,
        MAX_DAILY_LOSS: -50000,
        AUTO_SQUARE_OFF_TIME: '15:15',
        MARKET_OPEN_TIME: '09:15',
        MARKET_CLOSE_TIME: '15:30'
    },

    // UI Configuration
    UI: {
        THEME: 'dark',
        REFRESH_INTERVAL: 5000,
        CHART_UPDATE_INTERVAL: 1000,
        NOTIFICATION_DURATION: 5000,
        TABLE_PAGE_SIZE: 50,
        MAX_NOTIFICATIONS: 10
    },

    // Data Configuration
    DATA: {
        CANDLE_INTERVALS: ['1min', '5min', '15min', '30min', '60min'],
        DEFAULT_INTERVAL: '5min',
        MAX_CANDLES: 500,
        CACHE_DURATION: 300000, // 5 minutes
    },

    // Monitoring Configuration
    MONITORING: {
        ALERT_LEVELS: ['INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        DEFAULT_ALERT_LEVEL: 'WARNING',
        LOG_RETENTION_DAYS: 30,
        PERFORMANCE_SAMPLE_RATE: 1000 // ms
    },

    // Storage Configuration
    STORAGE: {
        PREFIX: 'trading_',
        SETTINGS_KEY: 'trading_settings',
        POSITIONS_KEY: 'trading_positions',
        ALERTS_KEY: 'trading_alerts',
        CACHE_KEY: 'trading_cache'
    },

    // Feature Flags
    FEATURES: {
        ENABLE_AMO: true,
        ENABLE_PAPER_TRADING: true,
        ENABLE_ML_ANALYSIS: true,
        ENABLE_AUTO_LOGIN: true,
        ENABLE_SCHEDULER: true,
        ENABLE_WEBSOCKET: true,
        ENABLE_NOTIFICATIONS: true,
        ENABLE_DARK_MODE: true
    },

    // API Endpoints
    ENDPOINTS: {
        // Authentication
        LOGIN: '/login',
        LOGOUT: '/logout',
        STATUS: '/status/all',
        
        // Trading
        PLACE_ORDER: '/orders/place',
        CANCEL_ORDER: '/orders/cancel',
        MODIFY_ORDER: '/orders/modify',
        ORDER_STATUS: '/orders/status',
        
        // Positions
        POSITIONS: '/positions',
        POSITION_UPDATE: '/positions/update_prices',
        SQUARE_OFF: '/positions/square_off',
        DAILY_PNL: '/positions/daily_pnl',
        
        // Webhooks
        WEBHOOK_ENTRY: '/webhook/entry',
        WEBHOOK_EXIT: '/webhook/exit',
        
        // Data
        CANDLES: '/data/candles',
        OPTION_CHAIN: '/data/option_chain',
        MARKET_DATA: '/data/market',
        
        // Backtest
        BACKTEST_RUN: '/backtest',
        BACKTEST_RESULTS: '/backtest/results',
        
        // Settings
        SETTINGS_GET: '/settings',
        SETTINGS_UPDATE: '/settings/update',
        
        // Kill Switch
        KILLSWITCH_STATUS: '/killswitch/status',
        KILLSWITCH_ACTIVATE: '/killswitch/activate',
        KILLSWITCH_DEACTIVATE: '/killswitch/deactivate',
        
        // Monitoring
        SYSTEM_STATUS: '/system/status',
        WEBSOCKET_STATUS: '/websocket/status',
        PERFORMANCE_METRICS: '/metrics/performance'
    },

    // Signal Types
    SIGNALS: {
        S1: { name: 'Bear Trap', type: 'BULLISH', action: 'SELL_PUT' },
        S2: { name: 'Support Hold', type: 'BULLISH', action: 'SELL_PUT' },
        S3: { name: 'Resistance Hold', type: 'BEARISH', action: 'SELL_CALL' },
        S4: { name: 'Bias Failure Bull', type: 'BULLISH', action: 'SELL_PUT' },
        S5: { name: 'Bias Failure Bear', type: 'BEARISH', action: 'SELL_CALL' },
        S6: { name: 'Weakness Confirmed', type: 'BEARISH', action: 'SELL_CALL' },
        S7: { name: 'Breakout Confirmed', type: 'BULLISH', action: 'SELL_PUT' },
        S8: { name: 'Breakdown Confirmed', type: 'BEARISH', action: 'SELL_CALL' }
    },

    // Error Messages
    ERRORS: {
        CONNECTION_FAILED: 'Failed to connect to server',
        ORDER_FAILED: 'Failed to place order',
        INVALID_CREDENTIALS: 'Invalid credentials',
        SESSION_EXPIRED: 'Session expired, please login again',
        NETWORK_ERROR: 'Network error occurred',
        UNKNOWN_ERROR: 'An unknown error occurred'
    },

    // Success Messages
    SUCCESS: {
        ORDER_PLACED: 'Order placed successfully',
        ORDER_CANCELLED: 'Order cancelled successfully',
        POSITION_CLOSED: 'Position closed successfully',
        SETTINGS_SAVED: 'Settings saved successfully',
        LOGIN_SUCCESS: 'Login successful'
    }
};

// Utility Functions
const API = {
    /**
     * Make API request with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${CONFIG.API.BASE_URL}${endpoint}`;
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, defaultOptions);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    },

    /**
     * GET request
     */
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request(url, { method: 'GET' });
    },

    /**
     * POST request
     */
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /**
     * PUT request
     */
    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    /**
     * DELETE request
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }
};

// Storage Utility
const Storage = {
    /**
     * Get item from localStorage
     */
    get(key) {
        try {
            const item = localStorage.getItem(CONFIG.STORAGE.PREFIX + key);
            return item ? JSON.parse(item) : null;
        } catch (error) {
            console.error('Storage get error:', error);
            return null;
        }
    },

    /**
     * Set item in localStorage
     */
    set(key, value) {
        try {
            localStorage.setItem(CONFIG.STORAGE.PREFIX + key, JSON.stringify(value));
            return true;
        } catch (error) {
            console.error('Storage set error:', error);
            return false;
        }
    },

    /**
     * Remove item from localStorage
     */
    remove(key) {
        try {
            localStorage.removeItem(CONFIG.STORAGE.PREFIX + key);
            return true;
        } catch (error) {
            console.error('Storage remove error:', error);
            return false;
        }
    },

    /**
     * Clear all storage
     */
    clear() {
        try {
            const keys = Object.keys(localStorage);
            keys.forEach(key => {
                if (key.startsWith(CONFIG.STORAGE.PREFIX)) {
                    localStorage.removeItem(key);
                }
            });
            return true;
        } catch (error) {
            console.error('Storage clear error:', error);
            return false;
        }
    }
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CONFIG, API, Storage };
}