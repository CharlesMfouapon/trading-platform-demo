"""
Terminal visualization for the trading platform demo.
Uses Rich for beautiful TUI output.
"""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box
from datetime import datetime
import time
from typing import Optional

from platform import TradingPlatform, OrderLifecycle

console = Console()

def create_order_table(platform: TradingPlatform) -> Table:
    """Creates a table showing active orders and their status."""
    table = Table(title="📊 Order Lifecycles", box=box.ROUNDED)
    table.add_column("ClOrdID", style="cyan", no_wrap=True)
    table.add_column("Symbol", style="yellow")
    table.add_column("Side", style="bold")
    table.add_column("Price", justify="right")
    table.add_column("Qty", justify="right")
    table.add_column("Filled", justify="right")
    table.add_column("Status", style="bold")
    table.add_column("Settlement", style="green")
    
    for order in platform.order_lifecycles.values():
        side_style = "green" if order.side == "BUY" else "red"
        filled = sum(f['quantity'] for f in order.fills)
        settled = "✅" if order.settlement else "⏳"
        
        status_style = {
            "NEW": "blue",
            "RESTING": "yellow",
            "PARTIALLY_FILLED": "orange1",
            "FILLED": "green",
        }.get(order.status, "white")
        
        table.add_row(
            order.cl_ord_id,
            order.symbol,
            f"[{side_style}]{order.side}[/{side_style}]",
            f"${order.price:.2f}",
            str(order.quantity),
            f"{filled}/{order.quantity}",
            f"[{status_style}]{order.status}[/{status_style}]",
            settled,
        )
    
    return table

def create_ledger_table(platform: TradingPlatform) -> Table:
    """Creates a table showing ledger account balances."""
    table = Table(title="📒 Immutable Ledger", box=box.ROUNDED)
    table.add_column("Account", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Balance ($)", justify="right", style="bold")
    
    total_assets = 0
    total_liabilities = 0
    
    for acct_id, acct in platform.ledger.accounts.items():
        balance = acct.balance_micros / 10_000_000
        style = "green" if balance >= 0 else "red"
        
        table.add_row(
            acct_id,
            acct.account_type.value,
            f"[{style}]${balance:,.2f}[/{style}]",
        )
        
        if acct.account_type.value in ("ASSET", "INCOME"):
            total_assets += balance
        else:
            total_liabilities += balance
    
    table.add_section()
    table.add_row(
        "TOTAL",
        "",
        f"[bold]${total_assets + total_liabilities:,.2f}[/bold]",
    )
    
    return table

def create_depth_chart(platform: TradingPlatform, symbol: str) -> str:
    """Creates an ASCII order book depth chart."""
    if symbol not in platform.order_books:
        return "No data"
    
    book = platform.order_books[symbol]
    depth = book.get_depth()
    
    lines = [f"  📈 {symbol} Order Book Depth"]
    lines.append("  " + "─" * 40)
    
    # Bids (green)
    for price, qty in list(depth['bids'].items())[:5]:
        bar = "█" * min(int(qty / 100), 30)
        lines.append(f"  [green]{bar}[/green] ${price:.2f} ({qty})")
    
    # Spread
    if depth['bids'] and depth['asks']:
        best_bid = max(depth['bids'].keys())
        best_ask = min(depth['asks'].keys())
        spread = best_ask - best_bid
        lines.append(f"  {'─' * 40}")
        lines.append(f"  Spread: ${spread:.4f}")
        lines.append(f"  {'─' * 40}")
    
    # Asks (red)
    for price, qty in list(depth['asks'].items())[:5]:
        bar = "█" * min(int(qty
