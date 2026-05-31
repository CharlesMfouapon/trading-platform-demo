# Trading Platform Demo

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/CharlesMfouapon/trading-platform-demo?quickstart=1)

End-to-end demonstration: FIX order → Order Book matching → Immutable Ledger settlement with cryptographic proofs. Polyglot microservices orchestration.

Integration demonstration connecting three high-performance financial engines:

| Engine | Language | Repository |
|---|---|---|
| FIX Protocol Parser | C++20 | [fix-engine](https://github.com/CharlesMfouapon/fix-engine) |
| Limit Order Book | Java 21 | [limit-order-book](https://github.com/CharlesMfouapon/limit-order-book) |
| Immutable Ledger | Rust | [immutable-ledger](https://github.com/CharlesMfouapon/immutable-ledger) |
```

Architecture:

Client FIX Order
|
v
+-----------------+
|   FIX Engine    |  C++  - Wire-speed protocol parsing
|   (Session)     |         Sequence validation, checksum
+--------+--------+
|
v
+-----------------+
|   Order Book    |  Java - Price-time priority matching
|   (Matching)    |        Lock-free, micro-dollar precision
+--------+--------+
|
v
+-----------------+
| Immutable Ledger|  Rust - Hash-chained journal entries
|  (Settlement)   |        Merkle proofs, invariant verification
+-----------------+
|
v
Audit Report
(Cryptographic Proof)

```

## Quick Start

```bash
pip install -r requirements.txt
python demo.py
```

## Lifecycle

1. Order Submission -- FIX 4.4 NewOrderSingle encoded and transmitted
2. Order Matching -- Price-time priority engine matches crossing orders
3. Trade Settlement -- Double-entry journal posted to immutable ledger
4. Audit Verification -- Hash chain integrity and conservation invariant verified

### Invariants Verified

* [x] Hash chain remains unbroken after every transaction
* [x] Sum of all account balances = 0 (double-entry conservation)
* [x] Best price always matched first, then earliest timestamp
* [x] Every settlement creates a verifiable journal entry

## Testing

```bash
pytest tests/ -v
```

***Tests verify:***

* [x] Full pipeline: FIX order to ledger settlement
* [x] Partial fill tracking
* [x] Price-time priority correctness
* [x] Ledger conservation invariant under random order flow
* [x] Chain integrity after 50+ transactions
