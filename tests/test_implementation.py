"""
Integration tests verifying the full platform pipeline.
Tests FIX -> OrderBook -> Ledger with invariant checking.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from platform import TradingPlatform


class TestFullPipeline:
    """End-to-end tests for the trading platform."""

    def setup_method(self):
        self.platform = TradingPlatform()

    def test_single_order_lifecycle(self):
        """A single order goes through the complete pipeline."""
        lifecycle = self.platform.submit_order("AAPL", "BUY", 150.00, 100)

        assert lifecycle.status in ("RESTING", "FILLED")
        assert lifecycle.cl_ord_id.startswith("CL-")
        assert lifecycle.symbol == "AAPL"

    def test_matching_produces_trades(self):
        """When a buy order crosses a resting sell, trades are generated."""
        # Place resting sell
        self.platform.submit_order("AAPL", "SELL", 150.00, 100)

        # Aggressive buy
        lifecycle = self.platform.submit_order("AAPL", "BUY", 150.00, 100)

        assert lifecycle.status == "FILLED"
        assert len(lifecycle.fills) > 0
        assert lifecycle.settlement is not None

    def test_settlement_creates_ledger_entry(self):
        """Every settled trade creates a journal entry."""
        self.platform.submit_order("AAPL", "SELL", 150.00, 200)
        self.platform.submit_order("AAPL", "BUY", 150.00, 200)

        assert len(self.platform.ledger.entries) > 0
        assert self.platform.ledger.verify_chain_integrity()

    def test_double_entry_conservation(self):
        """The fundamental invariant: sum of all balances must be zero."""
        # Generate multiple trades
        self.platform.submit_order("AAPL", "SELL", 150.00, 300)
        self.platform.submit_order("AAPL", "BUY", 150.00, 200)
        self.platform.submit_order("AAPL", "BUY", 149.00, 100)

        # Verify conservation
        assert self.platform.ledger.verify_conservation()

    def test_hash_chain_integrity(self):
        """The hash chain must remain unbroken after multiple transactions."""
        for i in range(10):
            self.platform.submit_order("AAPL", "SELL", 150.00, 100)
            self.platform.submit_order("AAPL", "BUY", 150.00, 100)

        assert self.platform.ledger.verify_chain_integrity()

    def test_partial_fill_tracking(self):
        """Partial fills are correctly tracked through the lifecycle."""
        # Large resting sell
        self.platform.submit_order("AAPL", "SELL", 150.00, 500)

        # Small buy (partial fill)
        lifecycle = self.platform.submit_order("AAPL", "BUY", 150.00, 200)

        assert lifecycle.status == "FILLED"
        filled = sum(f['quantity'] for f in lifecycle.fills)
        assert filled == 200

    def test_audit_report_consistency(self):
        """Audit report must reflect actual state."""
        self.platform.submit_order("AAPL", "SELL", 150.00, 100)
        self.platform.submit_order("AAPL", "BUY", 150.00, 100)

        report = self.platform.get_audit_report()
        assert report['ledger_state']['chain_valid']
        assert report['ledger_state']['conservation_valid']
        assert report['settlements_count'] > 0

    def test_price_time_priority(self):
        """Better-priced orders match before worse-priced ones."""
        # Place two resting sells at different prices
        self.platform.submit_order("AAPL", "SELL", 150.00, 100)
        self.platform.submit_order("AAPL", "SELL", 151.00, 100)

        # Buy at 151.00 - should match the 150.00 first
        lifecycle = self.platform.submit_order("AAPL", "BUY", 151.00, 100)

        assert len(lifecycle.fills) == 1
        # Should have matched the better price (150.00)
        assert lifecycle.fills[0]['price'] == 150.00


class TestLedgerInvariants:
    """Mathematical invariants that must always hold."""

    def test_genesis_state(self):
        """A fresh platform has valid chain and conservation."""
        platform = TradingPlatform()
        assert platform.ledger.verify_chain_integrity()
        assert platform.ledger.verify_conservation()

    def test_chain_after_chaos(self):
        """After random order submission, chain stays intact."""
        import random
        platform = TradingPlatform()
        symbols = ["AAPL", "GOOG", "MSFT"]
        sides = ["BUY", "SELL"]

        for _ in range(50):
            symbol = random.choice(symbols)
            side = random.choice(sides)
            price = round(random.uniform(100, 200), 2)
            qty = random.randint(100, 1000)
            platform.submit_order(symbol, side, price, qty)

        assert platform.ledger.verify_chain_integrity()
        assert platform.ledger.verify_conservation()
