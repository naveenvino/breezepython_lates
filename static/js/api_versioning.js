/**
 * API Versioning and Standardization Layer
 * Provides a unified interface with versioned endpoints
 */

class APIVersioning {
    constructor() {
        this.version = 'v1';
        this.baseUrl = window.location.hostname === 'localhost' 
            ? 'http://localhost:8000' 
            : window.location.origin;
    }

    /**
     * Get versioned API URL
     */
    getUrl(endpoint) {
        // Remove leading slash if present
        endpoint = endpoint.replace(/^\//, '');
        
        // Check if endpoint already has version
        if (endpoint.startsWith('api/v')) {
            return `${this.baseUrl}/${endpoint}`;
        }
        
        // Add version prefix
        return `${this.baseUrl}/api/${this.version}/${endpoint}`;
    }

    /**
     * Standardized endpoint mappings
     */
    endpoints = {
        // Settings endpoints
        settings: {
            get: (key) => this.getUrl(`settings/${key}`),
            getAll: () => this.getUrl('settings'),
            set: () => this.getUrl('settings'),
            bulkUpdate: () => this.getUrl('settings/bulk'),
            delete: (key) => this.getUrl(`settings/${key}`),
            clearAll: () => this.getUrl('settings/all')
        },
        
        // Trading endpoints
        trading: {
            config: () => this.getUrl('trade-config'),
            saveConfig: () => this.getUrl('save-trade-config'),
            autoTrade: () => this.getUrl('auto-trade'),
            positions: () => this.getUrl('positions'),
            orders: () => this.getUrl('orders'),
            placeOrder: () => this.getUrl('place-order'),
            modifyOrder: () => this.getUrl('modify-order'),
            cancelOrder: () => this.getUrl('cancel-order'),
            squareOff: () => this.getUrl('square-off-all')
        },
        
        // Market data endpoints
        market: {
            niftySpot: () => this.getUrl('nifty-spot'),
            optionChain: () => this.getUrl('option-chain'),
            liveData: () => this.getUrl('live-data'),
            candles: () => this.getUrl('candles')
        },
        
        // Expiry endpoints
        expiry: {
            weekdayConfig: () => this.getUrl('weekday-expiry-config'),
            saveWeekdayConfig: () => this.getUrl('save-weekday-expiry-config'),
            exitConfig: () => this.getUrl('exit-timing-config'),
            saveExitConfig: () => this.getUrl('save-exit-timing-config'),
            availableExpiries: () => this.getUrl('available-expiries')
        },
        
        // Signal endpoints
        signals: {
            states: () => this.getUrl('signal-states'),
            saveStates: () => this.getUrl('save-signal-states'),
            process: () => this.getUrl('process-signal'),
            history: () => this.getUrl('signal-history')
        },
        
        // Risk management endpoints
        risk: {
            limits: () => this.getUrl('risk-limits'),
            updateLimits: () => this.getUrl('update-risk-limits'),
            profitLock: () => this.getUrl('profit-lock'),
            updateProfitLock: () => this.getUrl('update-profit-lock'),
            killSwitch: () => this.getUrl('kill-switch'),
            triggerKillSwitch: () => this.getUrl('trigger-kill-switch')
        },
        
        // Health check endpoints
        health: {
            status: () => this.getUrl('health'),
            apiHealth: () => this.getUrl('api-health'),
            breezeHealth: () => this.getUrl('breeze-health'),
            kiteHealth: () => this.getUrl('kite-health')
        },
        
        // WebSocket endpoints (not versioned)
        websocket: {
            positions: () => `ws://${window.location.hostname}:8001/ws/positions`,
            breeze: () => `ws://${window.location.hostname}:8002/ws/breeze`,
            signals: () => `ws://${window.location.hostname}:8003/ws/signals`
        }
    };

    /**
     * Migrate old endpoint to new versioned endpoint
     */
    migrateEndpoint(oldEndpoint) {
        // Map of old endpoints to new standardized ones
        const migrationMap = {
            '/trade_config': this.endpoints.trading.config(),
            '/save_trade_config': this.endpoints.trading.saveConfig(),
            '/auto_trade': this.endpoints.trading.autoTrade(),
            '/weekday_expiry_config': this.endpoints.expiry.weekdayConfig(),
            '/save_weekday_expiry_config': this.endpoints.expiry.saveWeekdayConfig(),
            '/exit_timing_config': this.endpoints.expiry.exitConfig(),
            '/save_exit_timing_config': this.endpoints.expiry.saveExitConfig(),
            '/signal_states': this.endpoints.signals.states(),
            '/save_signal_states': this.endpoints.signals.saveStates(),
            '/process_signal': this.endpoints.signals.process(),
            '/nifty_spot': this.endpoints.market.niftySpot(),
            '/option_chain': this.endpoints.market.optionChain(),
            '/square_off_all': this.endpoints.trading.squareOff(),
            '/place_order': this.endpoints.trading.placeOrder(),
            '/modify_order': this.endpoints.trading.modifyOrder(),
            '/cancel_order': this.endpoints.trading.cancelOrder(),
            '/api_health': this.endpoints.health.apiHealth(),
            '/breeze_health': this.endpoints.health.breezeHealth(),
            '/kite_health': this.endpoints.health.kiteHealth()
        };

        return migrationMap[oldEndpoint] || this.getUrl(oldEndpoint.replace(/^\//, ''));
    }

    /**
     * Update fetch calls to use versioned endpoints
     */
    versionedFetch(endpoint, options = {}) {
        const url = endpoint.startsWith('http') ? endpoint : this.migrateEndpoint(endpoint);
        
        // Add default headers
        const headers = {
            'Content-Type': 'application/json',
            'X-API-Version': this.version,
            ...options.headers
        };

        return fetch(url, {
            ...options,
            headers
        });
    }

    /**
     * Install global fetch interceptor
     */
    installInterceptor() {
        const originalFetch = window.fetch;
        const apiVersioning = this;

        window.fetch = function(url, options) {
            // Only intercept relative URLs or localhost URLs
            if (typeof url === 'string' && 
                (url.startsWith('/') || url.includes('localhost:8000'))) {
                
                // Convert to versioned endpoint
                const versionedUrl = url.startsWith('http') 
                    ? url 
                    : apiVersioning.migrateEndpoint(url);
                
                console.log(`API Call: ${url} -> ${versionedUrl}`);
                
                return originalFetch.call(this, versionedUrl, options);
            }
            
            // Pass through other requests unchanged
            return originalFetch.call(this, url, options);
        };
    }
}

// Create global instance
window.apiVersioning = new APIVersioning();

// Auto-install interceptor when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.apiVersioning.installInterceptor();
        console.log('API versioning layer activated');
    });
} else {
    window.apiVersioning.installInterceptor();
    console.log('API versioning layer activated');
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = APIVersioning;
}