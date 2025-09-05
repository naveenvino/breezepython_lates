// Fix for Real Trade Execution - Update the executeTrade function
// This ensures the frontend sends the correct parameters to the API

window.executeTrade = async function(signal, strike, type, action = 'ENTRY') {
    const mode = 'LIVE'; // Live trading only
    console.log(`[TRADE] Executing in ${mode} mode: ${signal} ${strike}${type}`);
    
    // GET ACTUAL SETTINGS
    const numLots = window.tempLots || parseInt(document.getElementById('numLots').value) || 10;
    const entryTiming = document.getElementById('entryTiming').value || 'immediate';
    const totalQuantity = numLots * 75; // NIFTY lot size = 75
    
    // GET HEDGE CONFIGURATION
    const hedgeEnabled = document.getElementById('enableHedge')?.checked || false;
    const hedgeOffset = 200; // Default hedge offset
    
    // GET STOP LOSS SETTINGS
    const profitLockEnabled = document.getElementById('profitLockEnabled')?.checked || false;
    const profitTarget = profitLockEnabled ? parseFloat(document.getElementById('profitTarget')?.value || 10) : null;
    const profitLock = profitLockEnabled ? parseFloat(document.getElementById('profitLock')?.value || 5) : null;
    
    const trailingStopEnabled = document.getElementById('trailingStopEnabled')?.checked || false;
    const trailPercent = trailingStopEnabled ? parseFloat(document.getElementById('trailPercent')?.value || 1) : null;
    
    console.log(`[SETTINGS] Lots: ${numLots}, Quantity: ${totalQuantity}, Entry: ${entryTiming}`);
    console.log(`[HEDGE] Enabled: ${hedgeEnabled}, Offset: ${hedgeOffset}`);
    console.log(`[STOP LOSS] ProfitLock: ${profitLockEnabled} (${profitTarget}%/${profitLock}%), Trailing: ${trailingStopEnabled} (${trailPercent}%)`);
    
    // Handle entry timing
    if (entryTiming === 'next_candle' && action === 'ENTRY') {
        console.log('[TIMING] Waiting for next candle...');
    }
    
    // Get current spot price
    let currentSpot = 25000; // Default
    try {
        const spotResponse = await fetch('http://localhost:8000/api/live/nifty-spot');
        if (spotResponse.ok) {
            const spotData = await spotResponse.json();
            if (spotData.success && spotData.data) {
                currentSpot = spotData.data.ltp;
            }
        }
    } catch (e) {
        console.warn('Could not fetch spot price, using default');
    }
    
    // Prepare the correct payload for the API
    const endpoint = '/live/execute-signal';
    const payload = {
        // Required fields for ManualSignalRequest
        signal_type: signal,  // S1, S2, etc.
        current_spot: currentSpot,
        
        // Position details
        strike: strike,
        option_type: type,  // PE or CE
        quantity: numLots,  // Number of lots
        action: action,     // ENTRY or EXIT
        
        // Hedge configuration
        hedge_enabled: hedgeEnabled,
        hedge_offset: hedgeOffset,
        
        // Stop loss parameters (matching API expectations)
        profit_lock_enabled: profitLockEnabled,
        profit_target: profitTarget,
        profit_lock: profitLock,
        trailing_stop_enabled: trailingStopEnabled,
        trail_percent: trailPercent,
        
        // Entry timing
        entry_timing: entryTiming
    };
    
    console.log('[TRADE] Sending payload:', payload);
    
    // Build confirmation message
    let confirmMsg = `LIVE TRADE CONFIRMATION\n\n`;
    confirmMsg += `Signal: ${signal}\n`;
    confirmMsg += `Main Leg: SELL ${strike}${type}\n`;
    if (hedgeEnabled) {
        const hedgeStrike = type === 'PE' ? strike - hedgeOffset : strike + hedgeOffset;
        confirmMsg += `Hedge Leg: BUY ${hedgeStrike}${type}\n`;
    }
    confirmMsg += `\nLots: ${numLots} (${totalQuantity} qty)\n`;
    confirmMsg += `Spot Price: ${currentSpot.toFixed(2)}\n`;
    if (profitLockEnabled) {
        confirmMsg += `\nProfit Lock: Target ${profitTarget}%, Lock ${profitLock}%\n`;
    }
    if (trailingStopEnabled) {
        confirmMsg += `Trailing Stop: ${trailPercent}%\n`;
    }
    confirmMsg += `\n⚠️ This will use REAL money!`;
    
    // Confirmation for live trades
    if (!confirm(confirmMsg)) {
        return false;
    }
    
    try {
        const response = await fetch('http://localhost:8000' + endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            const result = await response.json();
            console.log(`[TRADE] Success:`, result);
            
            // Show success notification with details
            let successMsg = `Trade Executed: ${signal} ${strike}${type}`;
            if (result.main_order_id) {
                successMsg += ` | Order ID: ${result.main_order_id}`;
            }
            if (hedgeEnabled && result.hedge_order_id) {
                successMsg += ` | Hedge: ${result.hedge_order_id}`;
            }
            
            if (window.showNotification) {
                window.showNotification(successMsg, 'success');
            }
            
            // Update positions display
            if (window.loadLivePositions) {
                window.loadLivePositions();
            }
            
            return true;
        } else {
            const error = await response.json();
            console.error(`[TRADE] Failed:`, error);
            
            // Show detailed error message
            let errorMsg = 'Trade failed: ';
            if (error.detail) {
                errorMsg += error.detail;
            } else if (error.message) {
                errorMsg += error.message;
            } else {
                errorMsg += 'Unknown error';
            }
            
            if (window.showNotification) {
                window.showNotification(errorMsg, 'error');
            }
            
            // Alert user with detailed error
            alert(`Trade Execution Failed!\n\n${errorMsg}\n\nPlease check:\n1. API is running\n2. Broker connection is active\n3. Market hours\n4. Sufficient margin`);
            
            return false;
        }
    } catch (error) {
        console.error(`[TRADE] Error:`, error);
        
        if (window.showNotification) {
            window.showNotification(`Trade error: ${error.message}`, 'error');
        }
        
        alert(`Trade Execution Error!\n\n${error.message}\n\nPlease ensure the API is running on port 8000`);
        
        return false;
    }
}

// Also update the executeManualTrade function to properly use the modified settings
window.executeManualTrade = async function(alertId) {
    const alert = window.pendingAlerts[alertId];
    if (!alert) {
        showNotification('Alert not found', 'error');
        return;
    }
    
    // Immediately disable all buttons to prevent double-click
    const alertElement = document.getElementById(alertId);
    const executeBtn = alertElement.querySelector('.btn-execute');
    const allButtons = alertElement.querySelectorAll('.btn-alert-action');
    
    allButtons.forEach(btn => {
        btn.disabled = true;
    });
    
    // Show loading state
    const originalBtnHTML = executeBtn.innerHTML;
    executeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Executing...';
    
    // Get current settings (including any modifications)
    const numLots = window.tempLots || parseInt(document.getElementById('numLots').value) || 10;
    const totalQuantity = numLots * 75;
    const hedgeEnabled = alert.hedgeEnabled !== undefined ? alert.hedgeEnabled : document.getElementById('enableHedge')?.checked || false;
    
    // Use the modified values if they exist
    const actualStrike = alert.strike;
    const actualType = alert.type;
    
    try {
        // Call the fixed executeTrade function
        const success = await executeTrade(alert.signal, actualStrike, actualType, alert.action);
        
        if (success) {
            // Mark alert as executed
            alertElement.classList.add('executed');
            alertElement.style.opacity = '0.7';
            alertElement.style.borderColor = 'var(--accent-green)';
            
            // Update button text to show success
            executeBtn.innerHTML = '<i class="fas fa-check"></i> Executed';
            executeBtn.style.background = 'var(--accent-green)';
            
            showNotification(`Trade executed: ${alert.signal}`, 'success');
            
            // Remove from pending
            delete window.pendingAlerts[alertId];
            
            // Reload positions
            loadLivePositions();
            updatePendingAlertsCount();
        } else {
            // Re-enable buttons if execution failed
            allButtons.forEach(btn => {
                btn.disabled = false;
            });
            executeBtn.innerHTML = originalBtnHTML;
        }
    } catch (error) {
        console.error('Manual execution failed:', error);
        showNotification('Execution failed: ' + error.message, 'error');
        
        // Re-enable buttons on error
        allButtons.forEach(btn => {
            btn.disabled = false;
        });
        executeBtn.innerHTML = originalBtnHTML;
    }
}