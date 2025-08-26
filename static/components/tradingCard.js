class TradingCard {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.positions = [];
    }

    render(position) {
        const pnlClass = position.pnl >= 0 ? 'text-success' : 'text-error';
        const pnlIcon = position.pnl >= 0 ? 'trending_up' : 'trending_down';
        const changePercent = ((position.ltp - position.entry_price) / position.entry_price * 100).toFixed(2);
        
        return `
            <div class="card bg-base-200 shadow-xl hover:shadow-2xl transition-all duration-300">
                <div class="card-body p-4">
                    <div class="flex justify-between items-start">
                        <div>
                            <h3 class="card-title text-lg font-bold">
                                ${position.symbol}
                                <span class="badge badge-sm ${position.side === 'BUY' ? 'badge-success' : 'badge-error'}">
                                    ${position.side}
                                </span>
                            </h3>
                            <p class="text-sm text-base-content/70 mt-1">
                                ${position.quantity} × ₹${position.entry_price.toFixed(2)}
                            </p>
                        </div>
                        <div class="text-right">
                            <div class="${pnlClass} font-bold text-lg flex items-center gap-1">
                                <span class="material-icons text-sm">${pnlIcon}</span>
                                ₹${position.pnl.toFixed(2)}
                            </div>
                            <div class="text-sm text-base-content/70">
                                ${changePercent}%
                            </div>
                        </div>
                    </div>
                    
                    <div class="divider my-2"></div>
                    
                    <div class="grid grid-cols-2 gap-2 text-sm">
                        <div>
                            <span class="text-base-content/50">LTP:</span>
                            <span class="font-semibold ml-1">₹${position.ltp.toFixed(2)}</span>
                        </div>
                        <div>
                            <span class="text-base-content/50">Value:</span>
                            <span class="font-semibold ml-1">₹${(position.quantity * position.ltp).toFixed(2)}</span>
                        </div>
                        <div>
                            <span class="text-base-content/50">Entry:</span>
                            <span class="font-semibold ml-1">₹${position.entry_price.toFixed(2)}</span>
                        </div>
                        <div>
                            <span class="text-base-content/50">Type:</span>
                            <span class="font-semibold ml-1">${position.product_type || 'MIS'}</span>
                        </div>
                    </div>
                    
                    <div class="card-actions justify-end mt-3">
                        <button onclick="tradingCard.squareOff('${position.id}')" 
                                class="btn btn-sm btn-error">
                            Square Off
                        </button>
                        <button onclick="tradingCard.modify('${position.id}')" 
                                class="btn btn-sm btn-primary">
                            Modify
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    renderAll(positions) {
        this.positions = positions;
        const cards = positions.map(pos => this.render(pos)).join('');
        
        if (this.container) {
            this.container.innerHTML = `
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    ${cards}
                </div>
            `;
        }
    }

    async squareOff(positionId) {
        const position = this.positions.find(p => p.id === positionId);
        if (!position) return;
        
        if (confirm(`Square off ${position.symbol}?`)) {
            try {
                const response = await fetch('/live/square-off', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        symbol: position.symbol,
                        quantity: position.quantity
                    })
                });
                
                if (response.ok) {
                    this.showToast('Position squared off successfully', 'success');
                    this.refreshPositions();
                } else {
                    this.showToast('Failed to square off position', 'error');
                }
            } catch (error) {
                this.showToast('Error: ' + error.message, 'error');
            }
        }
    }

    modify(positionId) {
        const position = this.positions.find(p => p.id === positionId);
        if (!position) return;
        
        const modal = document.getElementById('modifyModal');
        if (modal) {
            document.getElementById('modifySymbol').textContent = position.symbol;
            document.getElementById('modifyQuantity').value = position.quantity;
            document.getElementById('modifyPrice').value = position.ltp;
            modal.showModal();
        }
    }

    async refreshPositions() {
        try {
            const response = await fetch('/live/positions');
            if (response.ok) {
                const data = await response.json();
                this.renderAll(data.positions || []);
            }
        } catch (error) {
            console.error('Error refreshing positions:', error);
        }
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-end toast-bottom`;
        toast.innerHTML = `
            <div class="alert alert-${type}">
                <span>${message}</span>
            </div>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    startAutoRefresh(interval = 5000) {
        setInterval(() => {
            this.refreshPositions();
        }, interval);
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TradingCard;
}