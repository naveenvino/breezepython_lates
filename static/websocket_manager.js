/**
 * WebSocket Manager for Real-time Updates
 * Handles WebSocket connections for all trading screens
 */

class WebSocketManager {
    constructor(url = 'ws://localhost:8000/ws') {
        this.url = url;
        this.ws = null;
        this.isConnected = false;
        this.reconnectInterval = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.callbacks = new Map();
        this.subscriptions = new Set();
    }

    connect() {
        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(this.url);
                
                this.ws.onopen = () => {
                    console.log('WebSocket connected');
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    this.resubscribe();
                    resolve(true);
                };
                
                this.ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.handleMessage(data);
                    } catch (error) {
                        console.error('Error parsing WebSocket message:', error);
                    }
                };
                
                this.ws.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    this.isConnected = false;
                };
                
                this.ws.onclose = () => {
                    console.log('WebSocket disconnected');
                    this.isConnected = false;
                    this.reconnect();
                };
            } catch (error) {
                console.error('Failed to connect WebSocket:', error);
                reject(error);
            }
        });
    }
    
    reconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }
        
        this.reconnectAttempts++;
        console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
        
        setTimeout(() => {
            this.connect();
        }, 3000);
    }
    
    resubscribe() {
        // Resubscribe to all channels after reconnection
        for (const channel of this.subscriptions) {
            this.subscribe(channel);
        }
    }
    
    subscribe(channel, callback = null) {
        if (!this.isConnected) {
            console.warn('WebSocket not connected');
            return false;
        }
        
        this.subscriptions.add(channel);
        
        if (callback) {
            if (!this.callbacks.has(channel)) {
                this.callbacks.set(channel, []);
            }
            this.callbacks.get(channel).push(callback);
        }
        
        this.ws.send(JSON.stringify({
            type: 'subscribe',
            channel: channel
        }));
        
        return true;
    }
    
    unsubscribe(channel) {
        this.subscriptions.delete(channel);
        this.callbacks.delete(channel);
        
        if (this.isConnected) {
            this.ws.send(JSON.stringify({
                type: 'unsubscribe',
                channel: channel
            }));
        }
    }
    
    send(data) {
        if (!this.isConnected) {
            console.warn('WebSocket not connected');
            return false;
        }
        
        this.ws.send(JSON.stringify(data));
        return true;
    }
    
    handleMessage(data) {
        // Handle different message types
        switch (data.type) {
            case 'connection':
                console.log('Connection status:', data.message);
                break;
                
            case 'heartbeat':
                // Keep connection alive
                break;
                
            case 'market_data':
                this.handleMarketData(data);
                break;
                
            case 'positions_update':
                this.handlePositionsUpdate(data);
                break;
                
            case 'signals_update':
                this.handleSignalsUpdate(data);
                break;
                
            case 'market_update':
                this.handleMarketUpdate(data);
                break;
                
            default:
                // Call channel-specific callbacks
                if (data.channel && this.callbacks.has(data.channel)) {
                    const callbacks = this.callbacks.get(data.channel);
                    for (const callback of callbacks) {
                        try {
                            callback(data);
                        } catch (error) {
                            console.error('Callback error:', error);
                        }
                    }
                }
        }
    }
    
    handleMarketData(data) {
        if (data.channel === 'option_chain' && data.option_chain) {
            // Trigger option chain update callbacks
            const callbacks = this.callbacks.get('option_chain') || [];
            for (const callback of callbacks) {
                callback(data.option_chain);
            }
        }
        
        if (data.spot_price !== undefined) {
            // Trigger spot price update callbacks
            const callbacks = this.callbacks.get('spot_price') || [];
            for (const callback of callbacks) {
                callback(data.spot_price);
            }
        }
    }
    
    handlePositionsUpdate(data) {
        const callbacks = this.callbacks.get('positions') || [];
        for (const callback of callbacks) {
            callback(data.positions);
        }
    }
    
    handleSignalsUpdate(data) {
        const callbacks = this.callbacks.get('signals') || [];
        for (const callback of callbacks) {
            callback(data.signals);
        }
    }
    
    handleMarketUpdate(data) {
        const callbacks = this.callbacks.get('market_data') || [];
        for (const callback of callbacks) {
            callback(data);
        }
    }
    
    // Helper method to get option chain
    async getOptionChain(symbol = 'NIFTY', expiry = null, strikes = 20) {
        return new Promise((resolve, reject) => {
            // Set up one-time callback
            const callback = (data) => {
                resolve(data);
            };
            
            // Subscribe temporarily
            this.callbacks.set('option_chain_response', [callback]);
            
            // Request option chain
            this.send({
                type: 'get_option_chain',
                symbol: symbol,
                expiry: expiry,
                strikes: strikes
            });
            
            // Timeout after 5 seconds
            setTimeout(() => {
                this.callbacks.delete('option_chain_response');
                reject(new Error('Option chain request timeout'));
            }, 5000);
        });
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
        this.subscriptions.clear();
        this.callbacks.clear();
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WebSocketManager;
}