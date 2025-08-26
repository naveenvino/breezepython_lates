/**
 * Option Chain Widget for index_hybrid.html
 * Loads option chain data directly without iframe
 */

class OptionChainWidget {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.spotPrice = 0;
        this.chainData = null;
        this.autoRefreshInterval = null;
    }

    async init() {
        // Load initial data
        await this.loadExpiryDates();
        await this.loadOptionChain();
        
        // Set up auto-refresh
        this.autoRefreshInterval = setInterval(() => {
            this.loadOptionChain();
        }, 30000);
    }

    async loadExpiryDates() {
        try {
            const response = await fetch('/option-chain/expiry-dates');
            if (response.ok) {
                const data = await response.json();
                this.expiryDates = data.data;
            }
        } catch (error) {
            console.error('Error loading expiry dates:', error);
        }
    }

    async loadOptionChain() {
        try {
            const response = await fetch('/option-chain/fast?symbol=NIFTY&strikes=20');
            if (response.ok) {
                const result = await response.json();
                this.chainData = result.data;
                this.spotPrice = result.data.spot_price;
                this.render();
            }
        } catch (error) {
            console.error('Error loading option chain:', error);
            this.container.innerHTML = '<div class="error">Failed to load option chain data</div>';
        }
    }

    render() {
        if (!this.chainData) return;

        const html = `
            <div class="option-chain-header">
                <div class="spot-info">
                    <span class="label">NIFTY Spot:</span>
                    <span class="value">${this.spotPrice.toFixed(2)}</span>
                    <span class="label">ATM:</span>
                    <span class="value">${this.chainData.atm_strike}</span>
                </div>
                <div class="pcr-info">
                    <span class="label">PCR:</span>
                    <span class="value">${this.chainData.pcr.pcr_oi.toFixed(3)}</span>
                </div>
            </div>
            
            <div class="option-chain-table">
                <table>
                    <thead>
                        <tr>
                            <th colspan="5" class="call-header">CALLS</th>
                            <th class="strike-header">STRIKE</th>
                            <th colspan="5" class="put-header">PUTS</th>
                        </tr>
                        <tr>
                            <th>OI</th>
                            <th>Volume</th>
                            <th>Bid</th>
                            <th>LTP</th>
                            <th>Ask</th>
                            <th>Strike</th>
                            <th>Bid</th>
                            <th>LTP</th>
                            <th>Ask</th>
                            <th>Volume</th>
                            <th>OI</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${this.renderChainRows()}
                    </tbody>
                </table>
            </div>
            
            <div class="last-update">
                Last Update: ${new Date().toLocaleTimeString()} | Source: ${this.chainData.source}
            </div>
        `;

        this.container.innerHTML = html;
    }

    renderChainRows() {
        if (!this.chainData || !this.chainData.chain) return '';
        
        return this.chainData.chain.map(row => {
            const rowClass = row.moneyness === 'ATM' ? 'atm-row' : 
                           row.moneyness === 'ITM' && row.strike < this.spotPrice ? 'itm-call' :
                           row.moneyness === 'ITM' && row.strike > this.spotPrice ? 'itm-put' : '';
            
            return `
                <tr class="${rowClass}">
                    <td>${this.formatNumber(row.call_oi)}</td>
                    <td>${this.formatNumber(row.call_volume)}</td>
                    <td>${row.call_bid.toFixed(2)}</td>
                    <td class="call-ltp"><strong>${row.call_ltp.toFixed(2)}</strong></td>
                    <td>${row.call_ask.toFixed(2)}</td>
                    <td class="strike-cell"><strong>${row.strike}</strong></td>
                    <td>${row.put_bid.toFixed(2)}</td>
                    <td class="put-ltp"><strong>${row.put_ltp.toFixed(2)}</strong></td>
                    <td>${row.put_ask.toFixed(2)}</td>
                    <td>${this.formatNumber(row.put_volume)}</td>
                    <td>${this.formatNumber(row.put_oi)}</td>
                </tr>
            `;
        }).join('');
    }

    formatNumber(num) {
        if (num === 0) return '0';
        if (num < 1000) return num.toString();
        if (num < 1000000) return (num / 1000).toFixed(1) + 'K';
        return (num / 1000000).toFixed(1) + 'M';
    }

    destroy() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
    }
}