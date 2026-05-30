"""
Order Book Adapter
Wraps the Java limit-order-book engine.
In demo mode, replicates the exact matching logic from 
com.fintech.lob.engine.OrderBook.java
"""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from collections import defaultdict
import heapq
import uuid
import time

class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"

@dataclass
class Order:
    order_id: str
    symbol: str
    side: Side
    price: float      # In micro-dollars internally, but we'll convert
    quantity: int
    timestamp_ns: int = field(default_factory=time.time_ns)

@dataclass
class Trade:
    buy_order_id: str
    sell_order_id: str
    symbol: str
    price: float
    quantity: int
    timestamp_ns: int

class OrderBook:
    """
    Python implementation matching the Java limit-order-book engine.
    Uses price-time priority: best price first, then earliest timestamp.
    
    Matches the architecture in:
    src/main/java/com/fintech/lob/engine/OrderBook.java
    """
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        # Bids: max-heap (negate price for Python's min-heap)
        self.bids: list[tuple[float, int, Order]] = []
        # Asks: min-heap
        self.asks: list[tuple[float, int, Order]] = []
        self.trades: list[Trade] = []
    
    def add_order(self, order: Order) -> list[Trade]:
        """Process an order and return any resulting trades.
        Implements the same matchOrder() logic as the Java engine.
        """
        if order.side == Side.BUY:
            return self._match_buy(order)
        else:
            return self._match_sell(order)
    
    def _match_buy(self, order: Order) -> list[Trade]:
        new_trades = []
        remaining = order.quantity
        
        # Match against asks (lowest price first)
        while self.asks and remaining > 0:
            best_ask_price, _, best_ask = self.asks[0]
            
            # Price check: buy order's limit must meet or exceed ask
            if order.price < best_ask_price:
                break
            
            # Remove from heap
            heapq.heappop(self.asks)
            match_qty = min(remaining, best_ask.quantity)
            
            trade = Trade(
                buy_order_id=order.order_id,
                sell_order_id=best_ask.order_id,
                symbol=self.symbol,
                price=best_ask_price,
                quantity=match_qty,
                timestamp_ns=time.time_ns(),
            )
            new_trades.append(trade)
            
            remaining -= match_qty
            best_ask.quantity -= match_qty
            
            # Re-add if partially filled (preserves timestamp priority)
            if best_ask.quantity > 0:
                heapq.heappush(self.asks, (best_ask_price, best_ask.timestamp_ns, best_ask))
        
        # Resting order for remaining quantity
        if remaining > 0:
            resting = Order(
                order_id=order.order_id,
                symbol=order.symbol,
                side=Side.BUY,
                price=order.price,
                quantity=remaining,
                timestamp_ns=order.timestamp_ns,
            )
            heapq.heappush(self.bids, (-order.price, order.timestamp_ns, resting))
        
        self.trades.extend(new_trades)
        return new_trades
    
    def _match_sell(self, order: Order) -> list[Trade]:
        new_trades = []
        remaining = order.quantity
        
        # Match against bids (highest price first)
        while self.bids and remaining > 0:
            best_bid_neg, _, best_bid = self.bids[0]
            best_bid_price = -best_bid_neg
            
            # Price check: sell order's limit must be at or below bid
            if order.price > best_bid_price:
                break
            
            heapq.heappop(self.bids)
            match_qty = min(remaining, best_bid.quantity)
            
            trade = Trade(
                buy_order_id=best_bid.order_id,
                sell_order_id=order.order_id,
                symbol=self.symbol,
                price=best_bid_price,
                quantity=match_qty,
                timestamp_ns=time.time_ns(),
            )
            new_trades.append(trade)
            
            remaining -= match_qty
            best_bid.quantity -= match_qty
            
            if best_bid.quantity > 0:
                heapq.heappush(self.bids, (-best_bid.price, best_bid.timestamp_ns, best_bid))
        
        if remaining > 0:
            resting = Order(
                order_id=order.order_id,
                symbol=order.symbol,
                side=Side.SELL,
                price=order.price,
                quantity=remaining,
                timestamp_ns=order.timestamp_ns,
            )
            heapq.heappush(self.asks, (order.price, order.timestamp_ns, resting))
        
        self.trades.extend(new_trades)
        return new_trades
    
    def get_depth(self) -> dict:
        """Returns current order book depth for visualization."""
        bids_depth = defaultdict(int)
        asks_depth = defaultdict(int)
        
        for neg_price, _, order in self.bids:
            bids_depth[-neg_price] += order.quantity
        
        for price, _, order in self.asks:
            asks_depth[price] += order.quantity
        
        return {
            'bids': dict(sorted(bids_depth.items(), reverse=True)),
            'asks': dict(sorted(asks_depth.items())),
        }
