/**
 * Authentication Check Script
 * Include this in all protected pages to enforce authentication
 */

(function() {
    // List of pages that don't require authentication
    const publicPages = [
        '/login_secure.html',
        '/register.html',
        '/forgot-password.html',
        '/auth_redirect.html'
    ];
    
    // Check if current page is public
    const currentPath = window.location.pathname;
    if (publicPages.some(page => currentPath.includes(page))) {
        return; // No auth check needed for public pages
    }
    
    // Check for authentication token
    const token = localStorage.getItem('auth_token');
    
    if (!token) {
        // No token found, redirect to login
        console.log('No auth token found, redirecting to login...');
        window.location.href = '/login_secure.html?redirect=' + encodeURIComponent(window.location.pathname);
        return;
    }
    
    // Verify token with server
    const verifyToken = async () => {
        try {
            const response = await fetch('/auth/verify', {
                method: 'GET',
                headers: {
                    'Authorization': 'Bearer ' + token
                }
            });
            
            if (!response.ok) {
                // Token is invalid or expired
                console.log('Token validation failed, redirecting to login...');
                localStorage.removeItem('auth_token');
                localStorage.removeItem('auth_user');
                localStorage.removeItem('refresh_token');
                window.location.href = '/login_secure.html?redirect=' + encodeURIComponent(window.location.pathname);
            } else {
                // Token is valid
                console.log('Authentication verified');
            }
        } catch (error) {
            console.error('Error verifying authentication:', error);
            // Don't redirect on network errors to avoid loops
        }
    };
    
    // Verify token immediately
    verifyToken();
    
    // Also verify periodically (every 5 minutes)
    setInterval(verifyToken, 5 * 60 * 1000);
})();