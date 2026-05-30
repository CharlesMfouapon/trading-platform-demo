#!/usr/bin/env python3
"""
Trading Platform Demo
Demonstrates the complete lifecycle:
  FIX Order -> Order Book Matching -> Immutable Ledger Settlement

Usage:
  python demo.py
"""
import time
import random
import sys
from platform import TradingPlatform
from visualize import visualize_platform

def run_demo():
    print("=" * 60)
    print("  TRADING PLATFORM DEMO")
    print("  FIX Engine | Order Book | Immutable Ledger")
    print("=" * 60)
    print()

    platform = TradingPlatform()

    # Phase 1: Seed the order book with resting orders
    print("[Phase 1] Seeding order book with resting liquidity...")
    seed_orders = [
        ("AAPL", "SELL", 175.50, 500),
        ("AAPL", "SELL", 176.00, 1000),
        ("AAPL", "SELL", 176.50, 300),
        ("AAPL", "BUY",  174.00, 400),
        ("AAPL", "BUY",  173.50, 600),
        ("AAPL", "BUY",  173.00, 800),
    ]

    for symbol, side, price, qty in seed_orders:
        platform.submit_order(symbol, side, price, qty)
        print(f"  + {side} {qty} {symbol} @ ${price:.2f}")

    print(f"\n  Order book seeded with {len(seed_orders)} resting orders.\n")
    time.sleep(1)

    # Phase 2: Submit aggressive orders that will match
    print("[Phase 2] Submitting aggressive orders for matching...")
    aggressive_orders = [
        ("AAPL", "BUY",  176.00, 800, "CL-AGGR-001"),
        ("AAPL", "SELL", 173.00, 1000, "CL-AGGR-002"),
        ("AAPL", "BUY",  177.00, 500, "CL-AGGR-003"),
    ]

    for symbol, side, price, qty, cl_ord_id in aggressive_orders:
        lifecycle = platform.submit_order(symbol, side, price, qty, cl_ord_id)
        fills = len(lifecycle.fills)
        total_filled = sum(f['quantity'] for f in lifecycle.fills)
        print(
            f"  > {side} {qty} {symbol} @ ${price:.2f}  "
            f"-> {fills} fill(s), {total_filled} shares, "
            f"Status: {lifecycle.status}"
        )
        if lifecycle.settlement:
            print(f"    Settled: {lifecycle.settlement.trade_id} "
                  f"(Entry #{lifecycle.settlement.settlement_entry_id})")

    print(f"\n  Aggressive orders processed.\n")
    time.sleep(1)

    # Phase 3: Generate audit report
    print("[Phase 3] Generating cryptographic audit report...")
    report = platform.get_audit_report()
    ledger = report['ledger_state']

    print(f"  Chain Integrity:    {'PASS' if ledger['chain_valid'] else 'FAIL'}")
    print(f"  Conservation:       {'PASS' if ledger['conservation_valid'] else 'FAIL'}")
    print(f"  Total Entries:      {ledger['total_entries']}")
    print(f"  Settlements:        {report['settlements_count']}")
    print(f"  Chain Head:         {ledger['chain_head'][:32]}...")
    print()

    # Phase 4: Display account balances
    print("[Phase 4] Ledger account balances:")
    for acct_id, data in ledger['accounts'].items():
        print(f"  {acct_id:<30} ${data['balance_dollars']:>12,.2f}  ({data['type']})")
    print()

    # Phase 5: Visual dashboard
    print("[Phase 5] Rendering visual dashboard...")
    print()
    time.sleep(1)

    visualize_platform(platform, symbol="AAPL")

    print()
    print("=" * 60)
    print("  Demo complete.")
    print("  Stack: Python orchestration layer over")
    print("  C++ FIX Engine | Java Order Book | Rust Ledger")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
