/**
 * Comprehensive Error Handling System
 * Provides unified error handling for all API calls
 */

class ErrorHandler {
    constructor() {
        this.errorLog = [];
        this.maxRetries = 3;
        this.retryDelay = 1000; // Base delay in ms
        this.circuitBreaker = new Map(); // Track failed endpoints
        this.errorCallbacks = new Set();
    }

    /**
     * Register error callback
     */
    onError(callback) {
        this.errorCallbacks.add(callback);
        return () => this.errorCallbacks.delete(callback);
    }

    /**
     * Notify all error listeners
     */
    notifyError(error) {
        this.errorCallbacks.forEach(callback => {
            try {
                callback(error);
            } catch (e) {
                console.error('Error in error callback:', e);
            }
        });
    }

    /**
     * Log error with context
     */
    logError(error, context = {}) {
        const errorEntry = {
            timestamp: new Date().toISOString(),
            message: error.message || error,
            stack: error.stack,
            context,
            type: error.name || 'Error'
        };

        this.errorLog.push(errorEntry);
        
        // Keep only last 100 errors
        if (this.errorLog.length > 100) {
            this.errorLog.shift();
        }

        // Log to console in development
        console.error('API Error:', errorEntry);

        // Notify listeners
        this.notifyError(errorEntry);

        return errorEntry;
    }

    /**
     * Handle different error types
     */
    async handleError(error, request = {}) {
        // Network errors
        if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
            return this.handleNetworkError(error, request);
        }

        // HTTP errors
        if (error.status) {
            return this.handleHttpError(error, request);
        }

        // Timeout errors
        if (error.name === 'AbortError') {
            return this.handleTimeoutError(error, request);
        }

        // Generic errors
        return this.handleGenericError(error, request);
    }

    /**
     * Handle network errors
     */
    handleNetworkError(error, request) {
        const errorDetails = {
            type: 'NETWORK_ERROR',
            message: 'Network connection failed. Please check your internet connection.',
            canRetry: true,
            originalError: error,
            request
        };

        this.logError(errorDetails, request);

        // Show user-friendly notification
        this.showNotification('Network Error', errorDetails.message, 'error');

        return errorDetails;
    }

    /**
     * Handle HTTP errors
     */
    async handleHttpError(error, request) {
        const statusHandlers = {
            400: () => ({
                type: 'BAD_REQUEST',
                message: 'Invalid request. Please check your input.',
                canRetry: false
            }),
            401: () => ({
                type: 'UNAUTHORIZED',
                message: 'Authentication required. Please log in.',
                canRetry: false,
                action: () => window.location.href = '/login'
            }),
            403: () => ({
                type: 'FORBIDDEN',
                message: 'Access denied. You don\'t have permission for this action.',
                canRetry: false
            }),
            404: () => ({
                type: 'NOT_FOUND',
                message: 'Resource not found.',
                canRetry: false
            }),
            429: () => ({
                type: 'RATE_LIMITED',
                message: 'Too many requests. Please wait before trying again.',
                canRetry: true,
                retryAfter: error.headers?.get('Retry-After') || 60
            }),
            500: () => ({
                type: 'SERVER_ERROR',
                message: 'Server error. Please try again later.',
                canRetry: true
            }),
            502: () => ({
                type: 'BAD_GATEWAY',
                message: 'Server is temporarily unavailable.',
                canRetry: true
            }),
            503: () => ({
                type: 'SERVICE_UNAVAILABLE',
                message: 'Service is temporarily unavailable.',
                canRetry: true
            })
        };

        const handler = statusHandlers[error.status] || (() => ({
            type: 'HTTP_ERROR',
            message: `Request failed with status ${error.status}`,
            canRetry: error.status >= 500
        }));

        const errorDetails = {
            ...handler(),
            status: error.status,
            originalError: error,
            request
        };

        // Try to parse error body
        try {
            const body = await error.json();
            errorDetails.serverMessage = body.message || body.error || body.detail;
        } catch (e) {
            // Body is not JSON or empty
        }

        this.logError(errorDetails, request);
        this.showNotification(errorDetails.type, errorDetails.serverMessage || errorDetails.message, 'error');

        // Execute action if defined
        if (errorDetails.action) {
            setTimeout(errorDetails.action, 2000);
        }

        return errorDetails;
    }

    /**
     * Handle timeout errors
     */
    handleTimeoutError(error, request) {
        const errorDetails = {
            type: 'TIMEOUT',
            message: 'Request timed out. Please try again.',
            canRetry: true,
            originalError: error,
            request
        };

        this.logError(errorDetails, request);
        this.showNotification('Timeout', errorDetails.message, 'warning');

        return errorDetails;
    }

    /**
     * Handle generic errors
     */
    handleGenericError(error, request) {
        const errorDetails = {
            type: 'GENERIC_ERROR',
            message: error.message || 'An unexpected error occurred.',
            canRetry: true,
            originalError: error,
            request
        };

        this.logError(errorDetails, request);
        this.showNotification('Error', errorDetails.message, 'error');

        return errorDetails;
    }

    /**
     * Retry failed request with exponential backoff
     */
    async retryRequest(request, attempt = 1) {
        if (attempt > this.maxRetries) {
            throw new Error(`Max retries (${this.maxRetries}) exceeded`);
        }

        const delay = this.retryDelay * Math.pow(2, attempt - 1);
        
        console.log(`Retrying request (attempt ${attempt}/${this.maxRetries}) after ${delay}ms`);
        
        await new Promise(resolve => setTimeout(resolve, delay));

        try {
            const response = await fetch(request.url, request.options);
            
            if (!response.ok) {
                response.attempt = attempt;
                throw response;
            }

            return response;
        } catch (error) {
            if (attempt < this.maxRetries) {
                return this.retryRequest(request, attempt + 1);
            }
            throw error;
        }
    }

    /**
     * Circuit breaker for failing endpoints
     */
    checkCircuitBreaker(url) {
        const breaker = this.circuitBreaker.get(url);
        
        if (!breaker) {
            return true; // Circuit is closed, allow request
        }

        const now = Date.now();
        
        // Check if circuit should be reset
        if (now - breaker.lastFailure > 60000) { // 1 minute cooldown
            this.circuitBreaker.delete(url);
            return true;
        }

        // Check if circuit is open
        if (breaker.failures >= 5) {
            console.warn(`Circuit breaker OPEN for ${url}`);
            return false;
        }

        return true;
    }

    /**
     * Update circuit breaker state
     */
    updateCircuitBreaker(url, success) {
        if (success) {
            this.circuitBreaker.delete(url);
        } else {
            const breaker = this.circuitBreaker.get(url) || { failures: 0 };
            breaker.failures++;
            breaker.lastFailure = Date.now();
            this.circuitBreaker.set(url, breaker);
        }
    }

    /**
     * Show user notification
     */
    showNotification(title, message, type = 'info') {
        // Check if state manager is available
        if (window.stateManager) {
            window.dispatch({
                type: 'ADD_NOTIFICATION',
                payload: {
                    title,
                    message,
                    type,
                    duration: type === 'error' ? 10000 : 5000
                }
            });
        }

        // Also show in console
        const logMethod = type === 'error' ? 'error' : type === 'warning' ? 'warn' : 'info';
        console[logMethod](`${title}: ${message}`);
    }

    /**
     * Enhanced fetch with error handling
     */
    async safeFetch(url, options = {}) {
        // Check circuit breaker
        if (!this.checkCircuitBreaker(url)) {
            throw new Error(`Circuit breaker is open for ${url}. Too many failures.`);
        }

        // Add timeout
        const timeout = options.timeout || 30000;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        const request = {
            url,
            options: {
                ...options,
                signal: controller.signal
            }
        };

        try {
            const response = await fetch(url, request.options);
            
            clearTimeout(timeoutId);
            
            // Update circuit breaker
            this.updateCircuitBreaker(url, response.ok);

            if (!response.ok) {
                // Create error object with response details
                const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
                error.status = response.status;
                error.response = response;
                throw error;
            }

            return response;
        } catch (error) {
            clearTimeout(timeoutId);
            
            // Update circuit breaker
            this.updateCircuitBreaker(url, false);

            // Handle the error
            const errorDetails = await this.handleError(error, request);

            // Retry if appropriate
            if (errorDetails.canRetry && options.retry !== false) {
                try {
                    return await this.retryRequest(request);
                } catch (retryError) {
                    console.error('Retry failed:', retryError);
                }
            }

            throw errorDetails;
        }
    }

    /**
     * Install global fetch interceptor
     */
    installInterceptor() {
        const originalFetch = window.fetch;
        const errorHandler = this;

        window.fetch = async function(url, options) {
            // Skip interception for specific URLs if needed
            const skipUrls = ['/health', '/api/v1/health'];
            if (skipUrls.some(skip => url.includes(skip))) {
                return originalFetch.call(this, url, options);
            }

            try {
                return await errorHandler.safeFetch(url, options);
            } catch (error) {
                // Allow caller to handle error if they want
                if (options?.throwOnError !== false) {
                    throw error;
                }
                
                // Return error response for backward compatibility
                return {
                    ok: false,
                    status: error.status || 0,
                    json: async () => error,
                    text: async () => JSON.stringify(error)
                };
            }
        };

        console.log('Error handling interceptor installed');
    }

    /**
     * Get error statistics
     */
    getStats() {
        const stats = {
            totalErrors: this.errorLog.length,
            byType: {},
            byEndpoint: {},
            recentErrors: this.errorLog.slice(-10)
        };

        this.errorLog.forEach(error => {
            // Count by type
            stats.byType[error.type] = (stats.byType[error.type] || 0) + 1;

            // Count by endpoint
            if (error.context?.url) {
                const endpoint = new URL(error.context.url).pathname;
                stats.byEndpoint[endpoint] = (stats.byEndpoint[endpoint] || 0) + 1;
            }
        });

        return stats;
    }

    /**
     * Clear error log
     */
    clearLog() {
        this.errorLog = [];
        this.circuitBreaker.clear();
        console.log('Error log cleared');
    }
}

// Create global error handler instance
window.errorHandler = new ErrorHandler();

// Auto-install interceptor when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.errorHandler.installInterceptor();
    });
} else {
    window.errorHandler.installInterceptor();
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ErrorHandler;
}