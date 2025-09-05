/**
 * Production-Ready Trade Execution Frontend
 * Complete implementation with proper error handling and order tracking
 */

// Production Trade Execution Function
window.executeProductionTrade = async function(signal, strike, type, action = 'ENTRY') {
    const mode = 'LIVE';
    console.log(`[TRADE] Executing production trade: ${signal} ${strike}${type}`);
    
    // Gather all configuration
    const config = gatherTradeConfiguration();
    
    // Validate before execution
    const validation = validateTradeParameters(signal, strike, type, config);
    if (!validation.valid) {
        showNotification(`Validation failed: ${validation.errors.join(', ')}`, 'error');
        return false;
    }
    
    // Get current spot price
    const spotPrice = await fetchCurrentSpotPrice();
    
    // Build complete request payload
    const payload = {
        // Signal and market data
        signal_type: signal,
        current_spot: spotPrice,
        
        // Position details
        strike: strike,
        option_type: type,
        quantity: config.numLots,
        action: action,
        
        // Hedge configuration
        hedge_enabled: config.hedgeEnabled,
        hedge_offset: config.hedgeOffset,
        hedge_percentage: 30.0,
        
        // Stop loss parameters
        profit_lock_enabled: config.profitLockEnabled,
        profit_target: config.profitTarget,
        profit_lock: config.profitLock,
        trailing_stop_enabled: config.trailingStopEnabled,
        trail_percent: config.trailPercent,
        
        // Entry timing
        entry_timing: config.entryTiming,
        
        // Risk limits
        max_loss_per_trade: 5000.0,
        max_position_size: 30
    };
    
    // Show confirmation dialog
    const confirmed = await showTradeConfirmation(payload);
    if (!confirmed) return false;
    
    // Show loading state
    const loadingId = showLoadingOverlay('Executing trade...');
    
    try {
        // Execute the trade
        const response = await fetch('http://localhost:8000/api/v1/execute-trade', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${getAuthToken()}`  // Add auth if needed
            },
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            // Trade successful
            await handleTradeSuccess(result);
            return true;
        } else {
            // Trade failed
            await handleTradeFailure(result, response.status);
            return false;
        }
        
    } catch (error) {
        // Network or other error
        await handleTradeError(error);
        return false;
        
    } finally {
        hideLoadingOverlay(loadingId);
    }
};

// Gather all trade configuration from UI
function gatherTradeConfiguration() {
    return {
        numLots: window.tempLots || parseInt(document.getElementById('numLots')?.value) || 10,
        hedgeEnabled: document.getElementById('enableHedge')?.checked || false,
        hedgeOffset: parseInt(document.getElementById('hedgeOffset')?.value) || 200,
        profitLockEnabled: document.getElementById('profitLockEnabled')?.checked || false,
        profitTarget: parseFloat(document.getElementById('profitTarget')?.value) || 10,
        profitLock: parseFloat(document.getElementById('profitLock')?.value) || 5,
        trailingStopEnabled: document.getElementById('trailingStopEnabled')?.checked || false,
        trailPercent: parseFloat(document.getElementById('trailPercent')?.value) || 1,
        entryTiming: document.getElementById('entryTiming')?.value || 'immediate'
    };
}

// Validate trade parameters
function validateTradeParameters(signal, strike, type, config) {
    const errors = [];
    
    // Validate signal
    const validSignals = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8'];
    if (!validSignals.includes(signal)) {
        errors.push(`Invalid signal: ${signal}`);
    }
    
    // Validate strike
    if (strike < 10000 || strike > 50000) {
        errors.push(`Strike ${strike} out of range`);
    }
    if (strike % 50 !== 0) {
        errors.push('Strike must be multiple of 50');
    }
    
    // Validate option type
    if (!['PE', 'CE'].includes(type)) {
        errors.push(`Invalid option type: ${type}`);
    }
    
    // Validate quantity
    if (config.numLots < 1 || config.numLots > 30) {
        errors.push('Quantity must be between 1 and 30 lots');
    }
    
    // Validate stop loss config
    if (config.profitLockEnabled) {
        if (config.profitTarget <= 0) {
            errors.push('Profit target must be positive');
        }
        if (config.profitLock >= config.profitTarget) {
            errors.push('Profit lock must be less than target');
        }
    }
    
    return {
        valid: errors.length === 0,
        errors: errors
    };
}

// Fetch current NIFTY spot price
async function fetchCurrentSpotPrice() {
    try {
        const response = await fetch('http://localhost:8000/api/live/nifty-spot');
        if (response.ok) {
            const data = await response.json();
            if (data.success && data.data) {
                return data.data.ltp;
            }
        }
    } catch (e) {
        console.warn('Could not fetch spot price, using default');
    }
    return 25000; // Default fallback
}

// Show trade confirmation dialog with full details
async function showTradeConfirmation(payload) {
    const lotSize = 75;
    const totalQty = payload.quantity * lotSize;
    const hedgeStrike = payload.hedge_enabled ? 
        (payload.option_type === 'PE' ? 
            payload.strike - payload.hedge_offset : 
            payload.strike + payload.hedge_offset) : null;
    
    // Create detailed confirmation message
    let message = `
╔══════════════════════════════════════╗
║     PRODUCTION TRADE CONFIRMATION     ║
╚══════════════════════════════════════╝

Signal: ${payload.signal_type}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 POSITION DETAILS:
• Main Leg: SELL ${payload.strike}${payload.option_type}
${payload.hedge_enabled ? `• Hedge Leg: BUY ${hedgeStrike}${payload.option_type}` : '• Hedge: DISABLED ⚠️'}
• Quantity: ${payload.quantity} lots (${totalQty} qty)
• Spot Price: ${payload.current_spot.toFixed(2)}

📈 RISK MANAGEMENT:
• Max Risk: ${payload.hedge_enabled ? `₹${(payload.hedge_offset * totalQty).toLocaleString()}` : 'UNLIMITED ⚠️'}
• Est. Margin: ₹${(payload.quantity * 15000).toLocaleString()}
${payload.profit_lock_enabled ? `• Profit Lock: ${payload.profit_target}% target, ${payload.profit_lock}% lock` : ''}
${payload.trailing_stop_enabled ? `• Trailing Stop: ${payload.trail_percent}%` : ''}

⏰ ENTRY: ${payload.entry_timing === 'immediate' ? 'IMMEDIATE' : 'NEXT CANDLE'}

⚠️ THIS IS A REAL MONEY TRADE ⚠️
`;
    
    return confirm(message);
}

// Show loading overlay
function showLoadingOverlay(message) {
    const overlayId = `loading-${Date.now()}`;
    const overlay = document.createElement('div');
    overlay.id = overlayId;
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.8);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        z-index: 100000;
    `;
    
    overlay.innerHTML = `
        <div style="background: var(--bg-secondary); padding: 30px; border-radius: 12px; text-align: center;">
            <div class="spinner" style="width: 50px; height: 50px; border: 4px solid var(--border-color); border-top-color: var(--accent-blue); border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 20px;"></div>
            <h3 style="color: var(--text-primary); margin: 0 0 10px 0;">${message}</h3>
            <p style="color: var(--text-muted); margin: 0;">Please wait, do not close this window...</p>
        </div>
        <style>
            @keyframes spin { to { transform: rotate(360deg); } }
        </style>
    `;
    
    document.body.appendChild(overlay);
    return overlayId;
}

// Hide loading overlay
function hideLoadingOverlay(overlayId) {
    const overlay = document.getElementById(overlayId);
    if (overlay) {
        overlay.remove();
    }
}

// Handle successful trade execution
async function handleTradeSuccess(result) {
    console.log('[TRADE] Success:', result);
    
    // Create success message
    let message = `✅ Trade Executed Successfully!\n\n`;
    
    if (result.main_order) {
        message += `Main Order: ${result.main_order.order_id}\n`;
        message += `Strike: ${result.main_order.strike}${result.main_order.type}\n`;
        message += `Quantity: ${result.main_order.quantity}\n`;
        message += `Premium: ₹${result.main_order.premium}\n\n`;
    }
    
    if (result.hedge_order) {
        message += `Hedge Order: ${result.hedge_order.order_id}\n`;
        message += `Strike: ${result.hedge_order.strike}${result.hedge_order.type}\n`;
        message += `Quantity: ${result.hedge_order.quantity}\n`;
        message += `Premium: ₹${result.hedge_order.premium}\n\n`;
    }
    
    if (result.risk_metrics) {
        message += `Max Risk: ₹${result.risk_metrics.max_risk.toLocaleString()}\n`;
        message += `Margin Used: ₹${result.risk_metrics.margin_required.toLocaleString()}\n`;
        message += `Breakeven: ${result.risk_metrics.breakeven}`;
    }
    
    // Show detailed success notification
    showDetailedNotification(message, 'success');
    
    // Update UI
    if (window.loadLivePositions) {
        await window.loadLivePositions();
    }
    
    // Track the order
    trackOrderStatus(result.position_id, result.main_order.order_id, result.hedge_order?.order_id);
    
    // Play success sound if available
    playSound('success');
}

// Handle trade failure
async function handleTradeFailure(result, statusCode) {
    console.error('[TRADE] Failed:', result);
    
    let message = '❌ Trade Execution Failed\n\n';
    
    if (statusCode === 400) {
        message += 'Validation Error:\n';
    } else if (statusCode === 403) {
        message += 'Risk Limit Exceeded:\n';
    } else {
        message += 'Server Error:\n';
    }
    
    message += result.detail || result.message || 'Unknown error occurred';
    
    // Add helpful suggestions
    message += '\n\nPlease check:\n';
    message += '• API connection status\n';
    message += '• Broker connection\n';
    message += '• Available margin\n';
    message += '• Market hours (9:15 AM - 3:30 PM)\n';
    
    showDetailedNotification(message, 'error');
    playSound('error');
}

// Handle network or unexpected errors
async function handleTradeError(error) {
    console.error('[TRADE] Error:', error);
    
    let message = '❌ Trade Execution Error\n\n';
    message += error.message || 'Network error occurred';
    message += '\n\nPossible causes:\n';
    message += '• API server not running\n';
    message += '• Network connection issue\n';
    message += '• Invalid API endpoint\n';
    
    showDetailedNotification(message, 'error');
    playSound('error');
}

// Track order status
function trackOrderStatus(positionId, mainOrderId, hedgeOrderId) {
    // Create order tracking entry
    const trackingData = {
        positionId: positionId,
        mainOrderId: mainOrderId,
        hedgeOrderId: hedgeOrderId,
        timestamp: new Date().toISOString(),
        status: 'PENDING'
    };
    
    // Store in session
    if (!window.activeOrders) {
        window.activeOrders = {};
    }
    window.activeOrders[positionId] = trackingData;
    
    // Start polling for status updates
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`http://localhost:8000/api/order-status/${mainOrderId}`);
            if (response.ok) {
                const status = await response.json();
                
                // Update tracking data
                trackingData.status = status.status;
                
                // Update UI if needed
                updateOrderStatusDisplay(positionId, status);
                
                // Stop polling if order is complete or rejected
                if (['COMPLETE', 'REJECTED', 'CANCELLED'].includes(status.status)) {
                    clearInterval(pollInterval);
                }
            }
        } catch (e) {
            console.error('Error polling order status:', e);
        }
    }, 5000); // Poll every 5 seconds
    
    // Stop polling after 5 minutes
    setTimeout(() => clearInterval(pollInterval), 300000);
}

// Update order status display
function updateOrderStatusDisplay(positionId, status) {
    // Find position in UI and update status
    const positionElement = document.querySelector(`[data-position-id="${positionId}"]`);
    if (positionElement) {
        const statusBadge = positionElement.querySelector('.status-badge');
        if (statusBadge) {
            statusBadge.textContent = status.status;
            statusBadge.className = `status-badge status-${status.status.toLowerCase()}`;
        }
    }
}

// Show detailed notification
function showDetailedNotification(message, type) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `detailed-notification ${type}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        max-width: 400px;
        padding: 20px;
        background: ${type === 'success' ? '#1b5e20' : '#b71c1c'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        z-index: 100001;
        font-family: monospace;
        white-space: pre-line;
        animation: slideIn 0.3s ease;
    `;
    
    notification.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <div style="flex: 1;">${message}</div>
            <button onclick="this.parentElement.parentElement.remove()" style="background: none; border: none; color: white; cursor: pointer; font-size: 20px; margin-left: 10px;">×</button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 10 seconds
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 10000);
}

// Play sound notification
function playSound(type) {
    try {
        const audio = new Audio();
        if (type === 'success') {
            audio.src = 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSpopdzxvnkwBz6A0fPTezEHPHvI8NeCLgUjceD47Xg+HUmr3+miXh0wtNfXimcdaaTb1nk6FEGk4OWeMClbo9zbi1ghMLzY2IM1FDmh3OacTRY2n9vWljsWS6rn6Z1RGlCw8OecVhw7k9XikVsyb7Pp6pNXHF2t0sKCWyBbvNjRfS0UN5rv/LJlDwBtp/Dm0YJ0U5vO4KZ+dkt1mce5l4mTV6LZ7q1tFABSgp+iiaB+YGyBgsHI2+2SX0mLu6yVkWdXZHeEqKWtmHVIUYKKk4dqam1ybWpue3p9rLe5g11YVob2/vSmUBEFQ3Tu5VkaBw5v0OLFhB0ECy9w3euygS0FJ3jg5ZcrAQJPydnbsiMDDEzP1+KTIAZJX+TqxGw4FRCmteHIrGQ0FEmNzNWfkUALPYO38NSEJgs2W8rIx3szEAMZm9Xs';
        } else {
            audio.src = 'data:audio/wav;base64,UklGRhYCAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YfIBAACAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIAA';
        }
        audio.play();
    } catch (e) {
        // Ignore audio errors
    }
}

// Get auth token if using authentication
function getAuthToken() {
    return localStorage.getItem('authToken') || '';
}

// Replace the old executeTrade function
window.executeTrade = window.executeProductionTrade;

// Update manual execution to use production function
window.executeManualTrade = async function(alertId) {
    const alert = window.pendingAlerts[alertId];
    if (!alert) {
        showNotification('Alert not found', 'error');
        return;
    }
    
    // Immediately disable all buttons
    const alertElement = document.getElementById(alertId);
    const executeBtn = alertElement.querySelector('.btn-execute');
    const allButtons = alertElement.querySelectorAll('.btn-alert-action');
    
    allButtons.forEach(btn => btn.disabled = true);
    
    // Show loading state
    const originalBtnHTML = executeBtn.innerHTML;
    executeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Executing...';
    
    try {
        // Use production execution
        const success = await executeProductionTrade(
            alert.signal,
            alert.strike,
            alert.type,
            alert.action
        );
        
        if (success) {
            // Mark as executed
            alertElement.classList.add('executed');
            alertElement.style.opacity = '0.7';
            alertElement.style.borderColor = 'var(--accent-green)';
            executeBtn.innerHTML = '<i class="fas fa-check"></i> Executed';
            executeBtn.style.background = 'var(--accent-green)';
            
            // Remove from pending
            delete window.pendingAlerts[alertId];
            updatePendingAlertsCount();
        } else {
            // Re-enable buttons on failure
            allButtons.forEach(btn => btn.disabled = false);
            executeBtn.innerHTML = originalBtnHTML;
        }
    } catch (error) {
        console.error('Manual execution error:', error);
        allButtons.forEach(btn => btn.disabled = false);
        executeBtn.innerHTML = originalBtnHTML;
    }
};

console.log('✅ Production-ready trade execution loaded');