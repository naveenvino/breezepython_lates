// Enhanced Modify Alert Function with Complete Hedge Details
// Replace the existing window.modifyAlert function (lines 3589-3626) with this:

window.modifyAlert = async function(alertId) {
    const alert = window.pendingAlerts[alertId];
    if (!alert) {
        showNotification('Alert not found', 'error');
        return;
    }
    
    // Get current configuration
    const hedgeEnabled = document.getElementById('enableHedge')?.checked || false;
    const currentLots = parseInt(document.getElementById('numLots').value) || 10;
    const hedgeOffset = 200; // Default hedge offset
    
    // Calculate initial hedge strike
    const initialHedgeStrike = alert.type === 'PE' ? alert.strike - hedgeOffset : alert.strike + hedgeOffset;
    
    // Create comprehensive modify dialog with hedge details
    const modalHtml = `
        <div id="modifyModal" class="modal" style="display: block; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 10000;">
            <div class="modal-content" style="max-width: 550px; margin: 40px auto; background: var(--bg-secondary); border-radius: 12px; padding: 25px; max-height: 85vh; overflow-y: auto; border: 1px solid var(--border-color);">
                <h3 style="margin: 0 0 20px 0; color: var(--text-primary); display: flex; align-items: center; gap: 10px;">
                    <i class="fas fa-edit" style="color: var(--accent-blue);"></i>
                    Modify Alert: ${alert.signal} - ${alert.description || ''}
                </h3>
                
                <!-- Main Position Section -->
                <div style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px; border-left: 3px solid var(--accent-yellow);">
                    <h4 style="margin: 0 0 15px 0; color: var(--accent-yellow); font-size: 14px;">
                        <i class="fas fa-chart-line"></i> Main Position (SELL)
                    </h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                        <div class="form-group">
                            <label style="font-size: 12px; color: var(--text-muted);">Strike Price</label>
                            <input type="number" id="modifyStrike" value="${alert.strike}" step="50" class="form-control" 
                                   style="padding: 8px; background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: 4px; color: var(--text-primary);" 
                                   onchange="updateModifyPreview()">
                        </div>
                        <div class="form-group">
                            <label style="font-size: 12px; color: var(--text-muted);">Option Type</label>
                            <select id="modifyType" class="form-control" 
                                    style="padding: 8px; background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: 4px; color: var(--text-primary);" 
                                    onchange="updateModifyPreview()">
                                <option value="PE" ${alert.type === 'PE' ? 'selected' : ''}>PUT (PE)</option>
                                <option value="CE" ${alert.type === 'CE' ? 'selected' : ''}>CALL (CE)</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-group" style="margin-top: 10px;">
                        <label style="font-size: 12px; color: var(--text-muted);">Number of Lots</label>
                        <input type="number" id="modifyLots" value="${currentLots}" min="1" max="30" class="form-control" 
                               style="padding: 8px; background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: 4px; color: var(--text-primary);" 
                               onchange="updateModifyPreview()">
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border-color);">
                        <span style="font-size: 12px; color: var(--text-muted);">Total Quantity:</span>
                        <span id="totalQtyPreview" style="font-size: 12px; font-weight: 600; color: var(--text-primary);">${currentLots * 75}</span>
                    </div>
                </div>
                
                <!-- Hedge Configuration Section -->
                <div style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px; margin-top: 15px; border-left: 3px solid var(--accent-green);">
                    <h4 style="margin: 0 0 15px 0; color: var(--accent-green); font-size: 14px;">
                        <i class="fas fa-shield-alt"></i> Hedge Protection (BUY)
                    </h4>
                    <div class="form-group">
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px;">
                            <input type="checkbox" id="modifyHedgeEnabled" ${hedgeEnabled ? 'checked' : ''} onchange="toggleModifyHedge()">
                            <span>Enable Hedge (30% Premium Rule)</span>
                        </label>
                    </div>
                    <div id="modifyHedgeDetails" style="${hedgeEnabled ? '' : 'display: none;'} margin-top: 15px;">
                        <div style="background: var(--bg-primary); padding: 12px; border-radius: 6px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                <span style="font-size: 12px; color: var(--text-muted);">Hedge Strike:</span>
                                <span id="hedgeStrikeDisplay" style="font-size: 13px; font-weight: 600; color: var(--accent-green);">
                                    ${initialHedgeStrike}${alert.type}
                                </span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span style="font-size: 12px; color: var(--text-muted);">Offset from Main:</span>
                                <span style="font-size: 13px; color: var(--text-primary);">${hedgeOffset} points</span>
                            </div>
                        </div>
                        <div style="margin-top: 10px; padding: 8px; background: rgba(34, 197, 94, 0.1); border-radius: 4px; font-size: 11px; color: var(--text-muted);">
                            <i class="fas fa-info-circle"></i> Hedge will be selected based on 30% of main leg premium
                        </div>
                    </div>
                </div>
                
                <!-- Trade Summary Section -->
                <div style="background: linear-gradient(135deg, var(--bg-tertiary), var(--bg-primary)); padding: 15px; border-radius: 8px; margin-top: 15px; border: 1px solid var(--accent-blue);">
                    <h4 style="margin: 0 0 15px 0; color: var(--accent-blue); font-size: 14px;">
                        <i class="fas fa-clipboard-check"></i> Trade Summary
                    </h4>
                    <div id="modifyTradeSummary" style="font-size: 13px; line-height: 1.8;">
                        <div style="display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid var(--border-color);">
                            <span style="color: var(--text-muted);">Main Leg:</span>
                            <span style="font-weight: 600;">SELL <span id="summaryMainStrike">${alert.strike}</span><span id="summaryMainType">${alert.type}</span></span>
                        </div>
                        <div id="summaryHedgeRow" style="${hedgeEnabled ? '' : 'display: none;'} display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid var(--border-color);">
                            <span style="color: var(--text-muted);">Hedge Leg:</span>
                            <span style="font-weight: 600; color: var(--accent-green);">BUY <span id="summaryHedgeStrike">${initialHedgeStrike}</span><span id="summaryHedgeType">${alert.type}</span></span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid var(--border-color);">
                            <span style="color: var(--text-muted);">Position Size:</span>
                            <span><span id="summaryLots">${currentLots}</span> lots (<span id="summaryQty">${currentLots * 75}</span> qty)</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid var(--border-color);">
                            <span style="color: var(--text-muted);">Est. Margin:</span>
                            <span>₹<span id="summaryMargin">${(currentLots * 15000).toLocaleString()}</span></span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 5px 0;">
                            <span style="color: var(--text-muted);">Max Risk:</span>
                            <span style="color: var(--accent-red); font-weight: 600;">
                                ₹<span id="summaryRisk">${hedgeEnabled ? (currentLots * 75 * hedgeOffset).toLocaleString() : 'Unlimited'}</span>
                            </span>
                        </div>
                    </div>
                </div>
                
                <!-- Stop Loss Configuration (Optional) -->
                <div style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px; margin-top: 15px; border-left: 3px solid var(--accent-red);">
                    <h4 style="margin: 0 0 15px 0; color: var(--accent-red); font-size: 14px;">
                        <i class="fas fa-stop-circle"></i> Stop Loss Settings
                    </h4>
                    <div style="font-size: 12px; line-height: 1.8; color: var(--text-muted);">
                        <div>• Stop Loss: At main strike (${alert.strike})</div>
                        <div>• Entry Timing: ${document.getElementById('entryTiming')?.value || 'Immediate'}</div>
                        ${document.getElementById('profitLockEnabled')?.checked ? 
                            `<div>• Profit Lock: ${document.getElementById('profitTarget')?.value || 10}% target</div>` : ''}
                        ${document.getElementById('trailingStopEnabled')?.checked ? 
                            `<div>• Trailing Stop: ${document.getElementById('trailPercent')?.value || 1}% trail</div>` : ''}
                    </div>
                </div>
                
                <!-- Action Buttons -->
                <div class="modal-buttons" style="display: flex; gap: 10px; margin-top: 20px;">
                    <button onclick="confirmModify('${alertId}')" class="btn btn-primary" 
                            style="flex: 1; padding: 12px; background: var(--accent-green); border: none; border-radius: 6px; color: white; font-weight: 600; cursor: pointer; transition: all 0.2s;">
                        <i class="fas fa-check"></i> Confirm Changes
                    </button>
                    <button onclick="closeModifyModal()" class="btn btn-secondary" 
                            style="flex: 1; padding: 12px; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: 6px; color: var(--text-primary); font-weight: 600; cursor: pointer; transition: all 0.2s;">
                        <i class="fas fa-times"></i> Cancel
                    </button>
                </div>
            </div>
        </div>
    `;
    
    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Add update functions
    window.updateModifyPreview = function() {
        const strike = parseInt(document.getElementById('modifyStrike').value);
        const type = document.getElementById('modifyType').value;
        const lots = parseInt(document.getElementById('modifyLots').value);
        const hedgeEnabled = document.getElementById('modifyHedgeEnabled').checked;
        
        // Update quantities
        document.getElementById('totalQtyPreview').textContent = lots * 75;
        
        // Update hedge display
        if (hedgeEnabled) {
            const hedgeStrike = type === 'PE' ? strike - hedgeOffset : strike + hedgeOffset;
            document.getElementById('hedgeStrikeDisplay').textContent = hedgeStrike + type;
            document.getElementById('summaryHedgeStrike').textContent = hedgeStrike;
            document.getElementById('summaryHedgeType').textContent = type;
        }
        
        // Update summary
        document.getElementById('summaryMainStrike').textContent = strike;
        document.getElementById('summaryMainType').textContent = type;
        document.getElementById('summaryLots').textContent = lots;
        document.getElementById('summaryQty').textContent = lots * 75;
        document.getElementById('summaryMargin').textContent = (lots * 15000).toLocaleString();
        document.getElementById('summaryRisk').textContent = hedgeEnabled ? 
            (lots * 75 * hedgeOffset).toLocaleString() : 'Unlimited';
    };
    
    window.toggleModifyHedge = function() {
        const hedgeEnabled = document.getElementById('modifyHedgeEnabled').checked;
        document.getElementById('modifyHedgeDetails').style.display = hedgeEnabled ? 'block' : 'none';
        document.getElementById('summaryHedgeRow').style.display = hedgeEnabled ? 'flex' : 'none';
        updateModifyPreview();
    };
}

// Also update the confirmModify function to handle hedge settings:
window.confirmModify = function(alertId) {
    const alert = window.pendingAlerts[alertId];
    const newStrike = parseInt(document.getElementById('modifyStrike').value);
    const newType = document.getElementById('modifyType').value;
    const newLots = parseInt(document.getElementById('modifyLots').value);
    const hedgeEnabled = document.getElementById('modifyHedgeEnabled').checked;
    
    // Update alert data
    alert.strike = newStrike;
    alert.type = newType;
    alert.hedgeEnabled = hedgeEnabled;
    window.tempLots = newLots; // Store for execution
    
    // Calculate hedge details for display
    const hedgeOffset = 200;
    const hedgeStrike = hedgeEnabled ? (newType === 'PE' ? newStrike - hedgeOffset : newStrike + hedgeOffset) : null;
    
    // Update display with complete details
    const alertElement = document.getElementById(alertId);
    if (alertElement) {
        const detailsHtml = `
            <div style="font-size: 13px; margin-bottom: 4px;">
                <strong>Main:</strong> SELL ${newStrike}${newType} | 
                <strong>Spot:</strong> ${alert.spot_price || 'N/A'} | 
                <strong>Action:</strong> ${alert.action}
            </div>
            ${hedgeEnabled ? `
                <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                    <i class="fas fa-shield-alt"></i> Hedge: BUY ${hedgeStrike}${newType} (30% rule)
                </div>
            ` : ''}
            <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">
                <i class="fas fa-chart-bar"></i> Lots: ${newLots} (${newLots * 75} qty) | 
                <i class="fas fa-rupee-sign"></i> Est. Margin: ₹${(newLots * 15000).toLocaleString()}
            </div>
            <div style="color: var(--accent-yellow); font-size: 11px; margin-top: 4px;">
                <i class="fas fa-edit"></i> Modified at ${new Date().toLocaleTimeString()}
            </div>
        `;
        
        alertElement.querySelector('.alert-details').innerHTML = detailsHtml;
        
        // Add modified indicator
        alertElement.style.borderColor = 'var(--accent-yellow)';
        alertElement.style.background = 'rgba(255, 193, 7, 0.05)';
    }
    
    closeModifyModal();
    showNotification('Alert modified successfully with hedge configuration', 'success');
}