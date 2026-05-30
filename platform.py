"""
Trading Platform Demo
Orchestrates the full lifecycle:
  FIX Order → Order Book → Immutable Ledger

Architecture:
  ┌──────────┐    ┌─────────────┐    ┌──────────────────┐
  │ FIX Engine│───▶│ Order Book  │───▶│ Immutable Ledger │
  │ (C++)    │    │ (Java)      │    │ (Rust)           │
  └──────────┘    └─────────────┘    └──────────────────┘
       │                 │                     │
       └─────────────────┴─────────────────────┘
                         │
                  ┌──────▼──────┐
                  │  Auditor UI │
                  │  (Rich TUI) │
                  └─────────────┘
"""
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from engines.fix_adapter import FixAdapter, FixOrder, Side as FixSide, OrdType
from engines.orderbook_adapter import OrderBook, Order, Side as OBSide
from engines.ledger_adapter import ImmutableLedger, AccountType

@dataclass
class Settlement:
    """Records the settlement of a trade on the ledger."""
    trade_id: str
    buy_order_id: str
    sell_order_id: str
    symbol: str
    price: float
    quantity: int
    settlement_entry_id: int
    timestamp: datetime

@dataclass
class OrderLifecycle:
    """Tracks an order through its entire lifecycle."""
    cl_ord_id: str
    symbol: str
    side: str
    price: float
    quantity: int
    status: str = "NEW"
    fills: list = field(default_factory=list)
    settlement: Optional[Settlement] = None
    created_at: datetime = field(default_factory=datetime.now)

class TradingPlatform:
    """
    The complete trading platform integrating all three engines.
    
    Lifecycle:
    1. Client submits FIX order
    2. Order Book matches and generates trades
    3. Trades settle on Immutable Ledger
    4. Cryptographic proofs generated for audit
    """
    
    def __init__(self):
        # Initialize engines
        self.fix_adapter = FixAdapter()
        
        # Order books per symbol (matching real venues)
        self.order_books: dict[str, OrderBook] = {}
        
        # Immutable ledger for settlement
        self.ledger = ImmutableLedger()
        
        # Set up chart of accounts
        self._setup_accounts()
        
        # Tracking
        self.order_lifecycles: dict[str, OrderLifecycle] = {}
        self.settlements: list[Settlement] = []
        self.sequence_number = 0
    
    def _setup_accounts(self):
        """Initialize the chart of accounts for a trading venue."""
        # Asset accounts
        self.ledger.create_account("ASSET-CASH", AccountType.ASSET)
        self.ledger.create_account("ASSET-SECURITIES", AccountType.ASSET)
        
        # Liability accounts
        self.ledger.create_account("LIAB-CLIENT-CLEARING", AccountType.LIABILITY)
        self.ledger.create_account("LIAB-UNSETTLED-TRADES", AccountType.LIABILITY)
        
        # Income accounts
        self.ledger.create_account("INC-TRADING-REVENUE", AccountType.INCOME)
        self.ledger.create_account("INC-FEES", AccountType.INCOME)
        
        # Expense accounts
        self.ledger.create_account("EXP-CLEARING-COST", AccountType.EXPENSE)
    
    def get_or_create_book(self, symbol: str) -> OrderBook:
        """Returns the order book for a symbol, creating if needed."""
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol)
        return self.order_books[symbol]
    
    def submit_order(
        self,
        symbol: str,
        side: str,
        price: float,
        quantity: int,
        cl_ord_id: Optional[str] = None,
    ) -> OrderLifecycle:
        """
        Submit a FIX order and process it through the entire pipeline.
        
        Args:
            symbol: Trading symbol (e.g., "AAPL")
            side: "BUY" or "SELL"
            price: Limit price in dollars
            quantity: Number of shares/contracts
            cl_ord_id: Client order ID (auto-generated if None)
        
        Returns:
            OrderLifecycle tracking the order through execution and settlement
        """
        if cl_ord_id is None:
            cl_ord_id = f"CL-{uuid.uuid4().hex[:8].upper()}"
        
        # Phase 1: Create FIX order
        fix_side = FixSide.BUY if side.upper() == "BUY" else FixSide.SELL
        fix_order = FixOrder(
            cl_ord_id=cl_ord_id,
            symbol=symbol,
            side=fix_side,
            price=price,
            quantity=quantity,
        )
        
        # Encode FIX message (what goes over the wire)
        fix_message = self.fix_adapter.encode_new_order_single(fix_order)
        
        # Phase 2: Route to order book for matching
        ob_side = OBSide.BUY if side.upper() == "BUY" else OBSide.SELL
        order = Order(
            order_id=cl_ord_id,
            symbol=symbol,
            side=ob_side,
            price=price,
            quantity=quantity,
        )
        
        book = self.get_or_create_book(symbol)
        trades = book.add_order(order)
        
        # Phase 3: Settle trades on immutable ledger
        lifecycle = OrderLifecycle(
            cl_ord_id=cl_ord_id,
            symbol=symbol,
            side=side.upper(),
            price=price,
            quantity=quantity,
        )
        
        total_filled = 0
        for trade in trades:
            if trade.buy_order_id == cl_ord_id or trade.sell_order_id == cl_ord_id:
                total_filled += trade.quantity
                lifecycle.fills.append({
                    'price': trade.price,
                    'quantity': trade.quantity,
                    'counterparty': trade.sell_order_id if side.upper() == "BUY" else trade.buy_order_id,
                })
                
                # Settle on ledger
                settlement = self._settle_trade(trade)
                lifecycle.settlement = settlement
        
        if total_filled == quantity:
            lifecycle.status = "FILLED"
        elif total_filled > 0:
            lifecycle.status = "PARTIALLY_FILLED"
        else:
            lifecycle.status = "RESTING"
        
        self.order_lifecycles[cl_ord_id] = lifecycle
        return lifecycle
    
    def _settle_trade(self, trade) -> Settlement:
        """Settle a trade on the immutable ledger using double-entry."""
        # Calculate trade value in micro-dollars
        trade_value_micros = int(trade.price * 10_000_000 * trade.quantity)
        
        # Double-entry settlement:
        # Debit: Buyer's clearing account (liability decreases)
        # Credit: Seller's clearing account (asset decreases, effectively)
        
        # For demo purposes, we settle between:
        # - ASSET-SECURITIES (represents the security changing hands)
        # - LIAB-CLIENT-CLEARING (represents client cash)
        
        metadata = json.dumps({
            'trade_id': f"TRD-{uuid.uuid4().hex[:8].upper()}",
            'symbol': trade.symbol,
            'price': trade.price,
            'quantity': trade.quantity,
            'buy_order': trade.buy_order_id,
            'sell_order': trade.sell_order_id,
        }).encode()
        
        # Entry 1: Transfer from buyer's clearing to securities
        entry1 = self.ledger.post_entry(
            debit_account="ASSET-SECURITIES",
            credit_account="LIAB-CLIENT-CLEARING",
            amount_micros=trade_value_micros,
            metadata=metadata,
        )
        
        # Entry 2: Record fee (0.1% for demo)
        fee_micros = int(trade_value_micros * 0.001)
        if fee_micros > 0:
            self.ledger.post_entry(
                debit_account="EXP-CLEARING-COST",
                credit_account="LIAB-CLIENT-CLEARING",
                amount_micros=fee_micros,
                metadata=b'{"type":"clearing_fee"}',
            )
        
        settlement = Settlement(
            trade_id=f"TRD-{uuid.uuid4().hex[:8].upper()}",
            buy_order_id=trade.buy_order_id,
            sell_order_id=trade.sell_order_id,
            symbol=trade.symbol,
            price=trade.price,
            quantity=trade.quantity,
            settlement_entry_id=entry1.entry_id,
            timestamp=datetime.now(),
        )
        self.settlements.append(settlement)
        return settlement
    
    def get_audit_report(self) -> dict:
        """Generate a complete audit report with cryptographic proofs."""
        return {
            'timestamp': datetime.now().isoformat(),
            'order_books': {
                symbol: book.get_depth()
                for symbol, book in self.order_books.items()
            },
            'ledger_state': {
                'chain_valid': self.ledger.verify_chain_integrity(),
                'conservation_valid': self.ledger.verify_conservation(),
                'total_entries': len(self.ledger.entries),
                'chain_head': self.ledger.chain_head.hex(),
                'accounts': {
                    acct_id: {
                        'balance_dollars': acct.balance_micros / 10_000_000,
                        'type': acct.account_type.value,
                    }
                    for acct_id, acct in self.ledger.accounts.items()
                }
            },
            'settlements_count': len(self.settlements),
            'active_orders': len([o for o in self.order_lifecycles.values() if o.status in ("RESTING", "PARTIALLY_FILLED")]),
            'filled_orders': len([o for o in self.order_lifecycles.values() if o.status == "FILLED"]),
        }
