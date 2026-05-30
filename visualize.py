"""
Trading Platform Visualization
Institutional-grade terminal display.
No emojis. No fluff. Pure data density.
"""
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box
from rich.columns import Columns
from datetime import datetime
from typing import Optional

from platform import TradingPlatform, OrderLifecycle

console = Console()

# Color palette: Bloomberg-inspired
HEADER_BG = "grey15"
ACCENT = "bright_cyan"
BID_COLOR = "green"
ASK_COLOR = "red"
DIM = "dim"
HIGHLIGHT = "bold white"
WARN = "yellow"
GOOD = "green"
BAD = "red"
NEUTRAL = "bright_black"

def timestamp_now() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def format_money(amount: float) -> str:
    if abs(amount) >= 1_000_000:
        return f"${amount/1_000_000:,.2f}M"
    if abs(amount) >= 1_000:
        return f"${amount/1_000:,.2f}K"
    return f"${amount:,.2f}"

def status_indicator(status: str) -> str:
    indicators = {
        "NEW":               f"[{NEUTRAL}]---[/{NEUTRAL}]",
        "RESTING":           f"[{WARN}]RST[/{WARN}]",
        "PARTIALLY_FILLED":  f"[{ACCENT}]PFIL[/{ACCENT}]",
        "FILLED":            f"[{GOOD}]FIL[/{GOOD}]",
        "CANCELLED":         f"[{BAD}]CAN[/{BAD}]",
        "REJECTED":          f"[{BAD}]REJ[/{BAD}]",
    }
    return indicators.get(status, f"[{NEUTRAL}]{status[:3].upper()}[/{NEUTRAL}]")

def side_badge(side: str) -> str:
    if side == "BUY":
        return f"[{BID_COLOR}]BUY [/{BID_COLOR}]"
    return f"[{ASK_COLOR}]SELL[/{ASK_COLOR}]"


def render_header() -> Panel:
    now = datetime.now().strftime("%Y-%m-%d  %H:%M:%S UTC")
    grid = Table.grid(padding=(0, 4))
    grid.add_column(justify="left")
    grid.add_column(justify="right")
    grid.add_row(
        Text("TRADING PLATFORM", style=f"bold {ACCENT}"),
        Text(now, style=DIM),
    )
    grid.add_row(
        Text("FIX Engine  |  Order Book  |  Immutable Ledger", style=DIM),
        Text("SIMULATION", style=DIM),
    )
    return Panel(grid, style=ACCENT, box=box.HEAVY)


def render_order_blotter(platform: TradingPlatform) -> Panel:
    table = Table(
        box=box.SIMPLE_HEAVY,
        expand=True,
        pad_edge=False,
        header_style=DIM,
    )
    table.add_column("ClOrdID", style=ACCENT, width=12, no_wrap=True)
    table.add_column("Symbol", style=HIGHLIGHT, width=8)
    table.add_column("Side", width=6)
    table.add_column("Limit", justify="right", width=10)
    table.add_column("Qty", justify="right", width=8)
    table.add_column("Filled", justify="right", width=10)
    table.add_column("Leaves", justify="right", width=8)
    table.add_column("Status", width=8)
    table.add_column("Settled", justify="center", width=8)

    for order in platform.order_lifecycles.values():
        filled_qty = sum(f['quantity'] for f in order.fills)
        leaves_qty = order.quantity - filled_qty
        settled = "Yes" if order.settlement else "--"

        table.add_row(
            order.cl_ord_id,
            order.symbol,
            side_badge(order.side),
            f"${order.price:.2f}",
            str(order.quantity),
            str(filled_qty),
            str(leaves_qty),
            status_indicator(order.status),
            settled,
        )

    if not platform.order_lifecycles:
        table.add_row("--", "--", "--", "--", "--", "--", "--", "NO ORDERS", "--")

    return Panel(table, title="Order Blotter", title_align="left", border_style=DIM)


def render_market_depth(platform: TradingPlatform, symbol: str) -> Panel:
    if symbol not in platform.order_books:
        return Panel("No market data", title=f"Market Depth: {symbol}", border_style=DIM)

    book = platform.order_books[symbol]
    depth = book.get_depth()

    # Build bids and asks columns
    bids_table = Table(box=None, pad_edge=False, show_header=False, expand=True)
    bids_table.add_column("Qty", justify="right", style=GOOD, width=8)
    bids_table.add_column("Bid", justify="right", style=GOOD, width=10)

    asks_table = Table(box=None, pad_edge=False, show_header=False, expand=True)
    asks_table.add_column("Ask", justify="left", style=BAD, width=10)
    asks_table.add_column("Qty", justify="left", style=BAD, width=8)

    max_rows = 8
    bid_items = list(depth['bids'].items())[:max_rows]
    ask_items = list(depth['asks'].items())[:max_rows]

    for i in range(max_rows):
        bid_price = f"${bid_items[i][0]:.2f}" if i < len(bid_items) else ""
        bid_qty = str(bid_items[i][1]) if i < len(bid_items) else ""
        ask_price = f"${ask_items[i][0]:.2f}" if i < len(ask_items) else ""
        ask_qty = str(ask_items[i][1]) if i < len(ask_items) else ""
        bids_table.add_row(bid_qty, bid_price)
        asks_table.add_row(ask_price, ask_qty)

    # Spread calculation
    spread_line = ""
    if bid_items and ask_items:
        best_bid = bid_items[0][0]
        best_ask = ask_items[0][0]
        spread = best_ask - best_bid
        mid = (best_bid + best_ask) / 2
        spread_line = f"Spread: ${spread:.4f}  |  Mid: ${mid:.2f}"

    grid = Table.grid(pad_edge=False)
    grid.add_column()
    grid.add_column(width=20)
    grid.add_column()
    grid.add_row(bids_table, Text(spread_line, justify="center", style=DIM), asks_table)

    return Panel(
        grid,
        title=f"Market Depth: {symbol}",
        title_align="left",
        border_style=DIM,
    )


def render_ledger_accounts(platform: TradingPlatform) -> Panel:
    table = Table(
        box=box.SIMPLE_HEAVY,
        expand=True,
        pad_edge=False,
        header_style=DIM,
    )
    table.add_column("Account", style=ACCENT)
    table.add_column("Type", style=DIM, width=12)
    table.add_column("Balance", justify="right", style=HIGHLIGHT)
    table.add_column("Status", justify="center", width=10)

    total_debit = 0.0
    total_credit = 0.0

    for acct_id, acct in platform.ledger.accounts.items():
        balance = acct.balance_micros / 10_000_000
        bal_style = GOOD if balance >= 0 else BAD
        formatted = f"[{bal_style}]{format_money(balance)}[/{bal_style}]"

        if balance >= 0:
            total_debit += balance
        else:
            total_credit += abs(balance)

        status = "DR" if balance > 0 else ("CR" if balance < 0 else "--")
        table.add_row(acct_id, acct.account_type.value, formatted, status)

    table.add_section()
    table.add_row(
        "",
        "",
        f"[{DIM}]DR: {format_money(total_debit)}  CR: {format_money(total_credit)}[/{DIM}]",
        "",
    )
    table.add_row(
        "",
        "NET",
        f"[{HIGHLIGHT}]{format_money(total_debit - total_credit)}[/{HIGHLIGHT}]",
        "",
    )

    return Panel(table, title="General Ledger", title_align="left", border_style=DIM)


def render_settlements(platform: TradingPlatform) -> Panel:
    table = Table(
        box=box.SIMPLE_HEAVY,
        expand=True,
        pad_edge=False,
        header_style=DIM,
    )
    table.add_column("Trade ID", style=ACCENT, width=12)
    table.add_column("Symbol", width=8)
    table.add_column("Price", justify="right", width=10)
    table.add_column("Qty", justify="right", width=8)
    table.add_column("Value", justify="right", width=12)
    table.add_column("Entry #", justify="right", width=8)
    table.add_column("Time", style=DIM, width=14)

    for s in platform.settlements[-10:]:  # Last 10 settlements
        value = s.price * s.quantity
        table.add_row(
            s.trade_id,
            s.symbol,
            f"${s.price:.2f}",
            str(s.quantity),
            format_money(value),
            str(s.settlement_entry_id),
            s.timestamp.strftime("%H:%M:%S"),
        )

    if not platform.settlements:
        table.add_row("--", "--", "--", "--", "--", "--", "--")

    return Panel(table, title="Settlement Log", title_align="left", border_style=DIM)


def render_audit_status(platform: TradingPlatform) -> Panel:
    report = platform.get_audit_report()
    ledger = report['ledger_state']

    chain_ok = ledger['chain_valid']
    conservation_ok = ledger['conservation_valid']

    content = f"""
  Hash Chain Integrity    [{GOOD}PASS[/{GOOD}] if {chain_ok} else [{BAD}FAIL[/{BAD}]]    {ledger['chain_head'][:24]}...
  Conservation Invariant  [{GOOD}PASS[/{GOOD}] if {conservation_ok} else [{BAD}FAIL[/{BAD}]]    Sum = 0 by construction
  Total Journal Entries   {ledger['total_entries']}
  Settled Trades          {report['settlements_count']}
  Active Orders           {report['active_orders']}
  Filled Orders           {report['filled_orders']}
    """.strip()

    return Panel(
        Text(content),
        title="Audit Verification",
        title_align="left",
        border_style=GOOD if (chain_ok and conservation_ok) else BAD,
    )


def render_chain_view(platform: TradingPlatform) -> Panel:
    if not platform.ledger.entries:
        return Panel("No entries in chain", title="Hash Chain", border_style=DIM)

    entries = platform.ledger.entries
    lines = []
    start = max(0, len(entries) - 6)  # Show last 6 entries

    for i in range(start, len(entries)):
        entry = entries[i]
        entry_hash = platform.ledger._compute_entry_hash(entry)
        short_hash = entry_hash.hex()[:12]
        parent_short = entry.parent_hash.hex()[:12]

        prefix = "  |--"
        if i == len(entries) - 1:
            prefix = "  +--"  # Chain head

        lines.append(
            f"{prefix} [{ACCENT}]{entry.entry_id:04d}[/{ACCENT}]  "
            f"{entry.debit_account[:12]:<12} -> {entry.credit_account[:12]:<12}  "
            f"[{DIM}]{short_hash}[/{DIM}]"
        )

    return Panel(
        Text("\n".join(lines)),
        title="Hash Chain (Last 6 Blocks)",
        title_align="left",
        border_style=DIM,
    )


def visualize_platform(platform: TradingPlatform, symbol: str = "AAPL"):
    """Render the complete platform dashboard."""
    console.clear()

    # Header
    console.print(render_header())

    # Top row: Order Blotter + Market Depth
    top_row = Columns(
        [render_order_blotter(platform), render_market_depth(platform, symbol)],
        equal=True,
        expand=True,
    )
    console.print(top_row)

    # Middle row: Ledger + Settlements
    mid_row = Columns(
        [render_ledger_accounts(platform), render_settlements(platform)],
        equal=True,
        expand=True,
    )
    console.print(mid_row)

    # Bottom row: Audit + Chain
    bottom_row = Columns(
        [render_audit_status(platform), render_chain_view(platform)],
        equal=True,
        expand=True,
    )
    console.print(bottom_row)


def live_dashboard(platform: TradingPlatform, symbol: str = "AAPL"):
    """Continuously updating dashboard view."""
    with Live(console=console, refresh_per_second=4, screen=True) as live:
        while True:
            # We'd need to export a renderable, so for now use the static view
            visualize_platform(platform, symbol)
            break  # Remove break for continuous mode in actual use
