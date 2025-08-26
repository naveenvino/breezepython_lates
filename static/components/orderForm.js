class OrderForm {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.orderType = 'MARKET';
        this.productType = 'MIS';
    }

    render() {
        return `
            <div class="card bg-base-200 shadow-xl">
                <div class="card-body">
                    <h2 class="card-title mb-4">Place Order</h2>
                    
                    <div class="form-control">
                        <label class="label">
                            <span class="label-text">Symbol</span>
                        </label>
                        <input type="text" id="orderSymbol" 
                               placeholder="e.g., NFO:NIFTY25000CE" 
                               class="input input-bordered" />
                    </div>

                    <div class="grid grid-cols-2 gap-4 mt-4">
                        <div class="form-control">
                            <label class="label">
                                <span class="label-text">Quantity</span>
                            </label>
                            <input type="number" id="orderQuantity" 
                                   placeholder="75" 
                                   class="input input-bordered" />
                        </div>

                        <div class="form-control">
                            <label class="label">
                                <span class="label-text">Price</span>
                            </label>
                            <input type="number" id="orderPrice" 
                                   placeholder="0.00" step="0.05"
                                   class="input input-bordered" 
                                   ${this.orderType === 'MARKET' ? 'disabled' : ''} />
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-4 mt-4">
                        <div class="form-control">
                            <label class="label">
                                <span class="label-text">Order Type</span>
                            </label>
                            <select id="orderType" class="select select-bordered" 
                                    onchange="orderForm.setOrderType(this.value)">
                                <option value="MARKET">Market</option>
                                <option value="LIMIT">Limit</option>
                                <option value="SL">Stop Loss</option>
                                <option value="SL-M">SL Market</option>
                            </select>
                        </div>

                        <div class="form-control">
                            <label class="label">
                                <span class="label-text">Product</span>
                            </label>
                            <select id="productType" class="select select-bordered">
                                <option value="MIS">MIS (Intraday)</option>
                                <option value="CNC">CNC (Delivery)</option>
                                <option value="NRML">NRML (F&O)</option>
                            </select>
                        </div>
                    </div>

                    <div class="form-control mt-4" id="triggerPriceDiv" style="display:none;">
                        <label class="label">
                            <span class="label-text">Trigger Price</span>
                        </label>
                        <input type="number" id="triggerPrice" 
                               placeholder="0.00" step="0.05"
                               class="input input-bordered" />
                    </div>

                    <div class="divider"></div>

                    <div class="flex gap-2">
                        <button onclick="orderForm.analyzeOrder()" 
                                class="btn btn-outline btn-info flex-1">
                            <span class="material-icons text-sm mr-1">analytics</span>
                            Analyze
                        </button>
                        <button onclick="orderForm.placeOrder('BUY')" 
                                class="btn btn-success flex-1">
                            <span class="material-icons text-sm mr-1">shopping_cart</span>
                            Buy
                        </button>
                        <button onclick="orderForm.placeOrder('SELL')" 
                                class="btn btn-error flex-1">
                            <span class="material-icons text-sm mr-1">sell</span>
                            Sell
                        </button>
                    </div>

                    <div id="orderAnalysis" class="mt-4"></div>
                </div>
            </div>
        `;
    }

    init() {
        if (this.container) {
            this.container.innerHTML = this.render();
        }
    }

    setOrderType(type) {
        this.orderType = type;
        const priceInput = document.getElementById('orderPrice');
        const triggerDiv = document.getElementById('triggerPriceDiv');
        
        if (type === 'MARKET') {
            priceInput.disabled = true;
            priceInput.value = '';
            triggerDiv.style.display = 'none';
        } else if (type === 'SL' || type === 'SL-M') {
            priceInput.disabled = type === 'SL-M';
            triggerDiv.style.display = 'block';
        } else {
            priceInput.disabled = false;
            triggerDiv.style.display = 'none';
        }
    }

    async analyzeOrder() {
        const orderData = this.getOrderData();
        
        if (!this.validateOrder(orderData)) {
            return;
        }

        const analysisDiv = document.getElementById('orderAnalysis');
        analysisDiv.innerHTML = `
            <div class="loading loading-spinner loading-md"></div>
            <span class="ml-2">Analyzing order...</span>
        `;

        try {
            const response = await fetch('/api/v1/analyzer/order', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(orderData)
            });

            if (response.ok) {
                const result = await response.json();
                this.displayAnalysis(result.analysis);
            } else {
                this.showAlert('Analysis failed', 'error');
            }
        } catch (error) {
            this.showAlert('Error: ' + error.message, 'error');
        }
    }

    displayAnalysis(analysis) {
        const analysisDiv = document.getElementById('orderAnalysis');
        
        const validClass = analysis.validation.is_valid ? 'alert-success' : 'alert-error';
        const riskClass = analysis.risk_score > 7 ? 'badge-error' : 
                         analysis.risk_score > 4 ? 'badge-warning' : 'badge-success';
        
        analysisDiv.innerHTML = `
            <div class="alert ${validClass} mt-2">
                <div>
                    <h4 class="font-bold">Order Analysis</h4>
                    <div class="mt-2">
                        <div class="flex items-center justify-between">
                            <span>Risk Score:</span>
                            <span class="badge ${riskClass}">${analysis.risk_score}/10</span>
                        </div>
                        ${analysis.costs ? `
                            <div class="flex items-center justify-between mt-1">
                                <span>Total Charges:</span>
                                <span>₹${analysis.costs.total_charges.toFixed(2)}</span>
                            </div>
                            <div class="flex items-center justify-between mt-1">
                                <span>Breakeven:</span>
                                <span>${analysis.costs.breakeven_points.toFixed(2)} points</span>
                            </div>
                        ` : ''}
                    </div>
                    ${analysis.recommendations.length > 0 ? `
                        <div class="mt-2">
                            <strong>Recommendations:</strong>
                            <ul class="list-disc list-inside text-sm mt-1">
                                ${analysis.recommendations.map(r => `<li>${r}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    async placeOrder(side) {
        const orderData = this.getOrderData();
        orderData.side = side;
        
        if (!this.validateOrder(orderData)) {
            return;
        }

        if (!confirm(`Place ${side} order for ${orderData.symbol}?`)) {
            return;
        }

        try {
            const response = await fetch('/api/v1/broker/order', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(orderData)
            });

            if (response.ok) {
                const result = await response.json();
                this.showAlert(`Order placed successfully! ID: ${result.order_id}`, 'success');
                this.resetForm();
            } else {
                const error = await response.json();
                this.showAlert(`Order failed: ${error.detail || error.message}`, 'error');
            }
        } catch (error) {
            this.showAlert('Error: ' + error.message, 'error');
        }
    }

    getOrderData() {
        return {
            symbol: document.getElementById('orderSymbol').value,
            quantity: parseInt(document.getElementById('orderQuantity').value) || 0,
            order_type: document.getElementById('orderType').value,
            product_type: document.getElementById('productType').value,
            price: parseFloat(document.getElementById('orderPrice').value) || null,
            trigger_price: parseFloat(document.getElementById('triggerPrice').value) || null
        };
    }

    validateOrder(orderData) {
        if (!orderData.symbol) {
            this.showAlert('Please enter a symbol', 'warning');
            return false;
        }
        
        if (!orderData.quantity || orderData.quantity <= 0) {
            this.showAlert('Please enter valid quantity', 'warning');
            return false;
        }
        
        if (orderData.order_type === 'LIMIT' && !orderData.price) {
            this.showAlert('Please enter price for limit order', 'warning');
            return false;
        }
        
        return true;
    }

    resetForm() {
        document.getElementById('orderSymbol').value = '';
        document.getElementById('orderQuantity').value = '';
        document.getElementById('orderPrice').value = '';
        document.getElementById('triggerPrice').value = '';
        document.getElementById('orderAnalysis').innerHTML = '';
    }

    showAlert(message, type = 'info') {
        const alertClass = type === 'error' ? 'alert-error' : 
                          type === 'success' ? 'alert-success' : 
                          type === 'warning' ? 'alert-warning' : 'alert-info';
        
        const alert = document.createElement('div');
        alert.className = `alert ${alertClass} mt-2`;
        alert.innerHTML = `<span>${message}</span>`;
        
        const container = document.getElementById('orderAnalysis');
        container.innerHTML = '';
        container.appendChild(alert);
        
        setTimeout(() => {
            alert.remove();
        }, 5000);
    }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = OrderForm;
}