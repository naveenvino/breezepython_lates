/**
 * Unified API Client with Error Handling and Retry Logic
 * Single source of truth - all settings come from API, no localStorage
 */

class UnifiedAPIClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
        this.maxRetries = 3;
        this.retryDelay = 1000;
        this.requestTimeout = 30000;
        this.settingsCache = new Map();
        this.cacheVersion = 0;
        this.cacheTTL = 5000; // 5 seconds cache TTL
    }

    /**
     * Make API request with retry logic and error handling
     */
    async request(method, endpoint, data = null, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const retries = options.retries ?? this.maxRetries;
        const timeout = options.timeout ?? this.requestTimeout;
        
        const config = {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        };

        if (data && method !== 'GET') {
            config.body = JSON.stringify(data);
        }

        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), timeout);
                
                const response = await fetch(url, {
                    ...config,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);

                if (!response.ok) {
                    const error = await this.parseError(response);
                    
                    // Don't retry on client errors (4xx)
                    if (response.status >= 400 && response.status < 500) {
                        throw new APIError(error.message, response.status, error);
                    }
                    
                    // Retry on server errors (5xx)
                    if (attempt < retries) {
                        await this.delay(this.retryDelay * Math.pow(2, attempt));
                        continue;
                    }
                    
                    throw new APIError(error.message, response.status, error);
                }

                const result = await response.json();
                return result;

            } catch (error) {
                if (error instanceof APIError) {
                    throw error;
                }

                if (error.name === 'AbortError') {
                    if (attempt < retries) {
                        await this.delay(this.retryDelay * Math.pow(2, attempt));
                        continue;
                    }
                    throw new APIError('Request timeout', 408, { timeout });
                }

                if (attempt < retries) {
                    console.log(`Retry ${attempt + 1}/${retries} for ${endpoint}`);
                    await this.delay(this.retryDelay * Math.pow(2, attempt));
                    continue;
                }

                throw new APIError(
                    `Network error: ${error.message}`,
                    0,
                    { originalError: error }
                );
            }
        }
    }

    /**
     * Parse error response
     */
    async parseError(response) {
        try {
            const error = await response.json();
            return {
                message: error.detail || error.message || 'Unknown error',
                ...error
            };
        } catch {
            return {
                message: `HTTP ${response.status}: ${response.statusText}`
            };
        }
    }

    /**
     * Delay helper for retry logic
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Get setting from API (with caching)
     */
    async getSetting(key, defaultValue = null) {
        const cacheKey = `${key}_v${this.cacheVersion}`;
        const cached = this.settingsCache.get(cacheKey);
        
        if (cached && Date.now() - cached.timestamp < this.cacheTTL) {
            return cached.value;
        }

        try {
            const response = await this.request('GET', `/settings/${key}`);
            const value = response.value ?? defaultValue;
            
            this.settingsCache.set(cacheKey, {
                value: value,
                timestamp: Date.now()
            });
            
            return value;
        } catch (error) {
            console.error(`Failed to get setting ${key}:`, error);
            return defaultValue;
        }
    }

    /**
     * Set setting via API
     */
    async setSetting(key, value, category = 'general') {
        try {
            const response = await this.request('POST', '/settings', {
                key: key,
                value: value,
                category: category
            });
            
            // Invalidate cache for this key
            this.invalidateCache(key);
            
            return response;
        } catch (error) {
            console.error(`Failed to set setting ${key}:`, error);
            throw error;
        }
    }

    /**
     * Get all settings from API
     */
    async getAllSettings(category = null) {
        const endpoint = category ? `/settings?category=${category}` : '/settings';
        try {
            return await this.request('GET', endpoint);
        } catch (error) {
            console.error('Failed to get settings:', error);
            return {};
        }
    }

    /**
     * Bulk update settings
     */
    async bulkUpdateSettings(updates) {
        try {
            const response = await this.request('POST', '/settings/bulk', updates);
            
            // Invalidate entire cache
            this.invalidateCache();
            
            return response;
        } catch (error) {
            console.error('Failed to bulk update settings:', error);
            throw error;
        }
    }

    /**
     * Invalidate cache
     */
    invalidateCache(key = null) {
        if (key) {
            for (const [cacheKey] of this.settingsCache) {
                if (cacheKey.startsWith(`${key}_`)) {
                    this.settingsCache.delete(cacheKey);
                }
            }
        } else {
            this.settingsCache.clear();
        }
        this.cacheVersion++;
    }

    /**
     * Get positions with error handling
     */
    async getPositions() {
        try {
            return await this.request('GET', '/positions');
        } catch (error) {
            console.error('Failed to get positions:', error);
            this.showError('Failed to fetch positions', error);
            return [];
        }
    }

    /**
     * Square off all positions
     */
    async squareOffAll() {
        try {
            return await this.request('POST', '/positions/square-off-all');
        } catch (error) {
            console.error('Failed to square off positions:', error);
            this.showError('Failed to square off positions', error);
            throw error;
        }
    }

    /**
     * Get kill switch status
     */
    async getKillSwitchStatus() {
        try {
            return await this.request('GET', '/kill-switch/status');
        } catch (error) {
            console.error('Failed to get kill switch status:', error);
            return { triggered: false, state: 'UNKNOWN' };
        }
    }

    /**
     * Trigger kill switch
     */
    async triggerKillSwitch(reason, source = 'ui') {
        try {
            return await this.request('POST', '/kill-switch/trigger', {
                reason: reason,
                source: source
            });
        } catch (error) {
            console.error('Failed to trigger kill switch:', error);
            this.showError('Failed to trigger kill switch', error);
            throw error;
        }
    }

    /**
     * Reset kill switch
     */
    async resetKillSwitch() {
        try {
            return await this.request('POST', '/kill-switch/reset');
        } catch (error) {
            console.error('Failed to reset kill switch:', error);
            this.showError('Failed to reset kill switch', error);
            throw error;
        }
    }

    /**
     * Show error message to user
     */
    showError(title, error) {
        const message = error instanceof APIError ? 
            error.message : 
            'An unexpected error occurred';
        
        // Try to show in UI if element exists
        const errorDiv = document.getElementById('error-message');
        if (errorDiv) {
            errorDiv.innerHTML = `
                <div class="alert alert-danger alert-dismissible fade show" role="alert">
                    <strong>${title}:</strong> ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;
            errorDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            // Fallback to alert
            alert(`${title}: ${message}`);
        }
    }

    /**
     * Show success message to user
     */
    showSuccess(message) {
        const successDiv = document.getElementById('success-message');
        if (successDiv) {
            successDiv.innerHTML = `
                <div class="alert alert-success alert-dismissible fade show" role="alert">
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;
            setTimeout(() => {
                successDiv.innerHTML = '';
            }, 5000);
        }
    }
}

/**
 * Custom API Error class
 */
class APIError extends Error {
    constructor(message, status, details = {}) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.details = details;
    }
}

/**
 * WebSocket Manager with exponential backoff reconnection
 */
class WebSocketManager {
    constructor(url, options = {}) {
        this.url = url;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = options.maxReconnectAttempts ?? 10;
        this.reconnectDelay = options.reconnectDelay ?? 1000;
        this.maxReconnectDelay = options.maxReconnectDelay ?? 30000;
        this.handlers = {
            open: options.onOpen || (() => {}),
            message: options.onMessage || (() => {}),
            error: options.onError || (() => {}),
            close: options.onClose || (() => {})
        };
        this.shouldReconnect = true;
        this.heartbeatInterval = null;
    }

    connect() {
        try {
            this.ws = new WebSocket(this.url);
            
            this.ws.onopen = (event) => {
                console.log(`WebSocket connected to ${this.url}`);
                this.reconnectAttempts = 0;
                this.startHeartbeat();
                this.handlers.open(event);
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    
                    // Handle ping/pong
                    if (data.type === 'ping') {
                        this.send({ type: 'pong' });
                        return;
                    }
                    
                    this.handlers.message(data);
                } catch (error) {
                    console.error('Error processing WebSocket message:', error);
                }
            };

            this.ws.onerror = (event) => {
                console.error(`WebSocket error on ${this.url}:`, event);
                this.handlers.error(event);
            };

            this.ws.onclose = (event) => {
                console.log(`WebSocket disconnected from ${this.url}`);
                this.stopHeartbeat();
                this.handlers.close(event);
                
                if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.scheduleReconnect();
                }
            };

        } catch (error) {
            console.error(`Failed to create WebSocket for ${this.url}:`, error);
            this.scheduleReconnect();
        }
    }

    scheduleReconnect() {
        this.reconnectAttempts++;
        
        // Exponential backoff with jitter
        const baseDelay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            this.maxReconnectDelay
        );
        const jitter = Math.random() * 1000;
        const delay = baseDelay + jitter;
        
        console.log(`Reconnecting WebSocket in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        setTimeout(() => {
            if (this.shouldReconnect) {
                this.connect();
            }
        }, delay);
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
            return true;
        }
        return false;
    }

    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            if (!this.send({ type: 'ping' })) {
                this.reconnect();
            }
        }, 30000); // Ping every 30 seconds
    }

    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    reconnect() {
        this.disconnect();
        this.connect();
    }

    disconnect() {
        this.shouldReconnect = false;
        this.stopHeartbeat();
        
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// Global API client instance
window.apiClient = new UnifiedAPIClient();

// Initialize WebSocket connections with proper reconnection
window.initializeWebSockets = function() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    
    // Live positions WebSocket
    window.positionsWS = new WebSocketManager(
        `${protocol}//${host}:8000/ws/positions`,
        {
            onMessage: (data) => {
                if (data.type === 'position_update') {
                    window.updatePositionsDisplay(data.positions);
                }
            },
            onOpen: () => {
                console.log('Live positions streaming started');
            }
        }
    );
    
    // Breeze data WebSocket
    window.breezeWS = new WebSocketManager(
        `${protocol}//${host}:8000/ws/breeze`,
        {
            onMessage: (data) => {
                if (data.type === 'spot_update') {
                    window.updateSpotPrice(data.spot_price);
                }
            },
            onOpen: () => {
                console.log('Breeze data streaming started');
            }
        }
    );
    
    // TradingView signals WebSocket
    window.tradingViewWS = new WebSocketManager(
        `${protocol}//${host}:8000/ws/tradingview`,
        {
            onMessage: (data) => {
                if (data.type === 'signal') {
                    window.handleTradeSignal(data);
                }
            },
            onOpen: () => {
                console.log('TradingView signals streaming started');
            }
        }
    );
    
    // Connect all WebSockets
    window.positionsWS.connect();
    window.breezeWS.connect();
    window.tradingViewWS.connect();
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { UnifiedAPIClient, WebSocketManager, APIError };
}