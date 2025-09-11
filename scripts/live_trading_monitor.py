"""
Live Trading Monitor
Real-time monitoring dashboard for Kite live trading
"""
import os
import sys
import time
import asyncio
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
import requests

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

console = Console()

class LiveTradingMonitor:
    """Real-time monitoring dashboard"""
    
    def __init__(self, api_base_url="http://localhost:8000"):
        self.api_base_url = api_base_url
        self.running = True
        
    def get_api_data(self, endpoint: str) -> dict:
        """Get data from API endpoint"""
        try:
            response = requests.get(f"{self.api_base_url}{endpoint}")
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            console.print(f"[red]Error fetching {endpoint}: {e}[/red]")
        return {}
    
    def create_header_panel(self) -> Panel:
        """Create header panel"""
        auth_status = self.get_api_data("/live/auth/status")
        
        status_text = Text()
        status_text.append("Live Trading Monitor\n", style="bold cyan")
        status_text.append(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        if auth_status.get('authenticated'):
            status_text.append("Auth: ", style="white")
            status_text.append("Connected ✓", style="green")
        else:
            status_text.append("Auth: ", style="white")
            status_text.append("Disconnected ✗", style="red")
        
        return Panel(status_text, title="System Status", border_style="cyan")
    
    def create_positions_table(self) -> Table:
        """Create positions table"""
        positions_data = self.get_api_data("/live/positions")
        
        table = Table(title="Current Positions", show_header=True, header_style="bold magenta")
        table.add_column("Symbol", style="cyan", width=20)
        table.add_column("Qty", justify="right")
        table.add_column("Avg Price", justify="right")
        table.add_column("LTP", justify="right")
        table.add_column("P&L", justify="right")
        table.add_column("P&L %", justify="right")
        
        positions = positions_data.get('positions', [])
        total_pnl = positions_data.get('total_pnl', 0)
        
        for pos in positions:
            pnl = pos.get('pnl', 0)
            pnl_color = "green" if pnl >= 0 else "red"
            
            avg_price = pos.get('average_price', 0)
            ltp = pos.get('last_price', 0)
            pnl_percent = ((ltp - avg_price) / avg_price * 100) if avg_price > 0 else 0
            
            table.add_row(
                pos.get('symbol', ''),
                str(pos.get('quantity', 0)),
                f"{avg_price:.2f}",
                f"{ltp:.2f}",
                f"[{pnl_color}]{pnl:,.2f}[/{pnl_color}]",
                f"[{pnl_color}]{pnl_percent:.2f}%[/{pnl_color}]"
            )
        
        # Add total row
        if positions:
            table.add_row(
                "[bold]TOTAL[/bold]", "", "", "",
                f"[{'green' if total_pnl >= 0 else 'red'}]{total_pnl:,.2f}[/{'green' if total_pnl >= 0 else 'red'}]",
                ""
            )
        
        return table
    
    def create_active_trades_table(self) -> Table:
        """Create active trades table"""
        trades_data = self.get_api_data("/live/trades/active")
        
        table = Table(title="Active Trades", show_header=True, header_style="bold yellow")
        table.add_column("Signal", style="cyan")
        table.add_column("Entry Time", width=20)
        table.add_column("Main Strike", justify="right")
        table.add_column("Hedge Strike", justify="right")
        table.add_column("Type")
        table.add_column("Direction")
        
        trades = trades_data.get('trades', [])
        
        for trade in trades:
            direction_color = "red" if trade.get('direction') == 'BEARISH' else "green"
            table.add_row(
                trade.get('signal_type', ''),
                datetime.fromisoformat(trade.get('entry_time', '')).strftime('%Y-%m-%d %H:%M'),
                str(trade.get('main_strike', '')),
                str(trade.get('hedge_strike', '')),
                trade.get('option_type', ''),
                f"[{direction_color}]{trade.get('direction', '')}[/{direction_color}]"
            )
        
        return table
    
    def create_pnl_summary(self) -> Panel:
        """Create P&L summary panel"""
        pnl_data = self.get_api_data("/live/pnl")
        sl_summary = self.get_api_data("/live/stop-loss/summary")
        
        summary_text = Text()
        
        total_pnl = pnl_data.get('total_pnl', 0)
        pnl_color = "green" if total_pnl >= 0 else "red"
        
        summary_text.append("Today's P&L: ", style="white")
        summary_text.append(f"₹{total_pnl:,.2f}\n", style=f"bold {pnl_color}")
        
        summary_text.append("\nStop Losses Hit: ", style="white")
        summary_text.append(f"{sl_summary.get('stop_losses_hit_today', 0)}\n", style="yellow")
        
        summary_text.append("SL Loss Amount: ", style="white")
        sl_loss = sl_summary.get('total_stop_loss_amount', 0)
        summary_text.append(f"₹{abs(sl_loss):,.2f}\n", style="red" if sl_loss < 0 else "white")
        
        # Market status
        now = datetime.now()
        market_open = now.replace(hour=9, minute=15)
        market_close = now.replace(hour=15, minute=30)
        
        if now < market_open:
            summary_text.append("\nMarket Status: ", style="white")
            summary_text.append("Pre-Market", style="yellow")
        elif now > market_close:
            summary_text.append("\nMarket Status: ", style="white")
            summary_text.append("Closed", style="red")
        else:
            summary_text.append("\nMarket Status: ", style="white")
            summary_text.append("Open", style="green")
        
        # Expiry warning
        if now.weekday() == 1:  # Tuesday
            time_to_squareoff = (now.replace(hour=15, minute=15) - now).total_seconds() / 60
            if 0 < time_to_squareoff < 60:
                summary_text.append(f"\n\n⚠️  Expiry Square-off in {int(time_to_squareoff)} mins", style="bold red blink")
        
        return Panel(summary_text, title="P&L Summary", border_style="green" if total_pnl >= 0 else "red")
    
    def create_alerts_panel(self) -> Panel:
        """Create alerts panel"""
        # This would fetch from monitoring service
        alerts_text = Text()
        alerts_text.append("Recent Alerts:\n\n", style="bold yellow")
        
        # Placeholder for alerts
        alerts_text.append("• System running normally\n", style="green")
        
        return Panel(alerts_text, title="Alerts", border_style="yellow")
    
    def create_layout(self) -> Layout:
        """Create dashboard layout"""
        layout = Layout()
        
        layout.split(
            Layout(name="header", size=6),
            Layout(name="body"),
            Layout(name="footer", size=8)
        )
        
        layout["body"].split_row(
            Layout(name="positions"),
            Layout(name="trades")
        )
        
        layout["footer"].split_row(
            Layout(name="pnl", ratio=1),
            Layout(name="alerts", ratio=2)
        )
        
        # Update content
        layout["header"].update(self.create_header_panel())
        layout["positions"].update(self.create_positions_table())
        layout["trades"].update(self.create_active_trades_table())
        layout["pnl"].update(self.create_pnl_summary())
        layout["alerts"].update(self.create_alerts_panel())
        
        return layout
    
    def run(self):
        """Run the monitoring dashboard"""
        console.clear()
        
        with Live(self.create_layout(), refresh_per_second=0.5, screen=True) as live:
            try:
                while self.running:
                    live.update(self.create_layout())
                    time.sleep(2)  # Update every 2 seconds
            except KeyboardInterrupt:
                self.running = False
                console.print("\n[yellow]Dashboard stopped by user[/yellow]")

def main():
    """Main entry point"""
    console.print("[bold cyan]Starting Live Trading Monitor...[/bold cyan]")
    
    # Check if API is running
    try:
        response = requests.get("http://localhost:8000/health")
        if response.status_code != 200:
            console.print("[red]Error: API is not running on http://localhost:8000[/red]")
            console.print("[yellow]Please start the API first: python unified_api_correct.py[/yellow]")
            return
    except:
        console.print("[red]Error: Cannot connect to API[/red]")
        console.print("[yellow]Please start the API first: python unified_api_correct.py[/yellow]")
        return
    
    # Run monitor
    monitor = LiveTradingMonitor()
    monitor.run()

if __name__ == "__main__":
    # Check if rich is installed
    try:
        import rich
    except ImportError:
        print("Error: 'rich' library is required for the dashboard")
        print("Install it with: pip install rich")
        sys.exit(1)
    
    main()