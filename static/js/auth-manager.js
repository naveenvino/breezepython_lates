/**
 * Authentication Manager for Secure API
 * Handles login, token storage, and automatic token injection
 */

class AuthManager {
    constructor() {
        this.token = localStorage.getItem('auth_token');
        this.user = localStorage.getItem('auth_user');
        this.apiBase = 'http://localhost:8001';
        this.modalShowing = false;  // Flag to prevent multiple modals
        this.initializeAuth();
    }

    /**
     * Initialize authentication - check if token is valid
     */
    async initializeAuth() {
        if (this.token) {
            // Verify existing token
            try {
                const response = await fetch(`${this.apiBase}/auth/verify`, {
                    headers: {
                        'Authorization': `Bearer ${this.token}`
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    console.log('Authentication valid:', data.user);
                    this.showAuthStatus(true);
                } else {
                    // Token invalid or expired
                    this.clearAuth();
                    this.showAuthStatus(false);
                }
            } catch (error) {
                console.error('Auth verification failed:', error);
                this.showAuthStatus(false);
            }
        } else {
            this.showAuthStatus(false);
        }
    }

    /**
     * Login function
     */
    async login(username, password) {
        try {
            const response = await fetch(`${this.apiBase}/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });

            if (response.ok) {
                const data = await response.json();
                
                // Store token and user info
                this.token = data.access_token;
                this.user = username;
                
                localStorage.setItem('auth_token', this.token);
                localStorage.setItem('auth_user', username);
                
                // Update UI
                this.showAuthStatus(true);
                this.showNotification('Login successful!', 'success');
                
                // Reload page to apply authentication
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
                
                return true;
            } else {
                const error = await response.json();
                this.showNotification(error.detail || 'Login failed', 'error');
                return false;
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showNotification('Connection error', 'error');
            return false;
        }
    }

    /**
     * Logout function
     */
    async logout() {
        // Call logout endpoint (optional, for server-side session cleanup)
        try {
            await fetch(`${this.apiBase}/auth/logout`, {
                method: 'POST',
                headers: this.getAuthHeaders()
            });
        } catch (error) {
            console.log('Logout endpoint error:', error);
        }
        
        // Clear local authentication
        this.clearAuth();
        this.showAuthStatus(false);
        this.showNotification('Logged out successfully', 'info');
        
        // Redirect to login page
        setTimeout(() => {
            window.location.href = '/login_secure.html';
        }, 1000);
    }

    /**
     * Clear authentication data
     */
    clearAuth() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
    }

    /**
     * Get headers with authentication
     */
    getAuthHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };
        
        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        return headers;
    }

    /**
     * Make authenticated fetch request
     */
    async authenticatedFetch(url, options = {}) {
        // Add authentication headers
        options.headers = {
            ...options.headers,
            ...this.getAuthHeaders()
        };
        
        const response = await fetch(url, options);
        
        // Don't automatically show login modal for 401s
        // Let the calling code handle it
        if (response.status === 401) {
            console.warn('Authentication failed for:', url);
            // Don't clear auth or show modal automatically
            // throw new Error('Authentication required');
        }
        
        return response;
    }

    /**
     * Show authentication status in UI
     */
    showAuthStatus(isAuthenticated) {
        const statusElement = document.getElementById('auth-status');
        if (statusElement) {
            if (isAuthenticated) {
                // Parse user data if it's a string
                let username = 'User';
                try {
                    if (typeof this.user === 'string') {
                        const userData = JSON.parse(this.user);
                        username = userData.username || userData.email || 'User';
                    } else if (this.user) {
                        username = this.user.username || this.user.email || 'User';
                    }
                } catch (e) {
                    console.error('Error parsing user data:', e);
                }
                
                statusElement.innerHTML = `
                    <span style="color: #10b981; font-weight: 500;">
                        <i class="fas fa-user-circle"></i> ${username}
                    </span>
                    <button onclick="authManager.logout()" class="btn-sm" style="
                        background: #ef4444;
                        color: white;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 14px;
                        transition: background 0.2s;
                    " onmouseover="this.style.background='#dc2626'" onmouseout="this.style.background='#ef4444'">
                        <i class="fas fa-sign-out-alt"></i> Logout
                    </button>
                `;
            } else {
                statusElement.innerHTML = `
                    <span style="color: #f59e0b;">
                        <i class="fas fa-user-slash"></i> Not authenticated
                    </span>
                    <button onclick="authManager.showLoginModal()" class="btn-sm" style="
                        background: #667eea;
                        color: white;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 14px;
                        transition: background 0.2s;
                    " onmouseover="this.style.background='#5a67d8'" onmouseout="this.style.background='#667eea'">
                        <i class="fas fa-sign-in-alt"></i> Login
                    </button>
                `;
            }
        }
    }

    /**
     * Show login modal
     */
    showLoginModal() {
        // Don't show if already showing
        if (this.modalShowing) {
            return;
        }
        
        // Remove existing modal if any
        const existingModal = document.getElementById('auth-modal');
        if (existingModal) {
            existingModal.remove();
        }
        
        this.modalShowing = true;

        const modal = document.createElement('div');
        modal.id = 'auth-modal';
        modal.innerHTML = `
            <div class="auth-modal-overlay" onclick="authManager.hideLoginModal()"></div>
            <div class="auth-modal-content">
                <h2>Login Required</h2>
                <div class="auth-modal-body">
                    <input type="text" id="auth-username" placeholder="Username" />
                    <input type="password" id="auth-password" placeholder="Password" />
                    <div class="auth-modal-buttons">
                        <button onclick="authManager.handleLogin()" class="btn-primary">Login</button>
                        <button onclick="authManager.hideLoginModal()" class="btn-secondary">Cancel</button>
                    </div>
                    <div class="auth-modal-note">
                        <small>Please enter your credentials</small>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Focus on username field
        document.getElementById('auth-username').focus();
        
        // Handle Enter key
        document.getElementById('auth-password').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.handleLogin();
            }
        });
    }

    /**
     * Hide login modal
     */
    hideLoginModal() {
        const modal = document.getElementById('auth-modal');
        if (modal) {
            modal.remove();
        }
        this.modalShowing = false;  // Reset flag
    }

    /**
     * Handle login from modal
     */
    async handleLogin() {
        const username = document.getElementById('auth-username').value;
        const password = document.getElementById('auth-password').value;
        
        if (!username || !password) {
            this.showNotification('Please enter username and password', 'error');
            return;
        }
        
        const success = await this.login(username, password);
        if (success) {
            this.hideLoginModal();
        }
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Remove existing notification
        const existing = document.getElementById('auth-notification');
        if (existing) {
            existing.remove();
        }
        
        const notification = document.createElement('div');
        notification.id = 'auth-notification';
        notification.className = `auth-notification auth-notification-${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Auto-hide after 3 seconds
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}

// Create global instance
const authManager = new AuthManager();

// Ensure auth status is shown when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        authManager.initializeAuth();
    });
} else {
    // DOM is already loaded
    authManager.initializeAuth();
}

// Override global fetch to add authentication automatically
const originalFetch = window.fetch;
window.fetch = function(url, options = {}) {
    // Only add auth headers for API calls to our server
    if (url.includes(window.location.origin) || url.startsWith('/')) {
        options.headers = {
            ...options.headers,
            ...authManager.getAuthHeaders()
        };
    }
    
    return originalFetch(url, options).then(response => {
        // Don't show login modal for these endpoints that might fail for other reasons
        const skipModalEndpoints = ['/positions', '/orders', '/live/', '/kite/', '/breeze/'];
        const shouldSkipModal = skipModalEndpoints.some(endpoint => url.includes(endpoint));
        
        // Only show login modal for true auth failures, not for broker API failures
        if (response.status === 401 && !url.includes('/auth/') && !shouldSkipModal) {
            // Check if we have a token - if yes, don't show modal (it's a different issue)
            const token = localStorage.getItem('auth_token');
            if (!token) {
                authManager.showLoginModal();
            }
        }
        return response;
    });
};

// Add CSS styles
const style = document.createElement('style');
style.textContent = `
    /* Authentication Status - Removed fixed positioning to work inline */
    #auth-status {
        /* Inline styles, no fixed positioning */
        padding: 5px 10px;
        border-radius: 5px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        z-index: 1000;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    #auth-status .btn-sm {
        padding: 5px 10px;
        border: none;
        border-radius: 3px;
        background: #007bff;
        color: white;
        cursor: pointer;
    }
    
    #auth-status .btn-sm:hover {
        background: #0056b3;
    }
    
    /* Login Modal */
    .auth-modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.5);
        z-index: 2000;
    }
    
    .auth-modal-content {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: white;
        padding: 30px;
        border-radius: 10px;
        box-shadow: 0 5px 20px rgba(0,0,0,0.3);
        z-index: 2001;
        min-width: 300px;
    }
    
    .auth-modal-content h2 {
        margin: 0 0 20px 0;
        color: #333;
    }
    
    .auth-modal-body input {
        width: 100%;
        padding: 10px;
        margin-bottom: 15px;
        border: 1px solid #ddd;
        border-radius: 5px;
        font-size: 14px;
    }
    
    .auth-modal-buttons {
        display: flex;
        gap: 10px;
        justify-content: flex-end;
    }
    
    .auth-modal-buttons button {
        padding: 10px 20px;
        border: none;
        border-radius: 5px;
        cursor: pointer;
        font-size: 14px;
    }
    
    .btn-primary {
        background: #007bff;
        color: white;
    }
    
    .btn-primary:hover {
        background: #0056b3;
    }
    
    .btn-secondary {
        background: #6c757d;
        color: white;
    }
    
    .btn-secondary:hover {
        background: #545b62;
    }
    
    .auth-modal-note {
        margin-top: 15px;
        text-align: center;
        color: #666;
    }
    
    /* Notifications */
    .auth-notification {
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        padding: 15px 30px;
        border-radius: 5px;
        color: white;
        z-index: 3000;
        animation: slideDown 0.3s ease;
    }
    
    .auth-notification-success {
        background: #28a745;
    }
    
    .auth-notification-error {
        background: #dc3545;
    }
    
    .auth-notification-info {
        background: #17a2b8;
    }
    
    @keyframes slideDown {
        from {
            opacity: 0;
            transform: translateX(-50%) translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
        }
    }
`;
document.head.appendChild(style);

// Add auth status div if not exists and DOM is ready
if (document.body && !document.getElementById('auth-status')) {
    const statusDiv = document.createElement('div');
    statusDiv.id = 'auth-status';
    document.body.appendChild(statusDiv);
}

console.log('Authentication Manager loaded. Use authManager.login(username, password) to login.');