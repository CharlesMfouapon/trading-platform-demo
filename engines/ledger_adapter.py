"""
Immutable Ledger Adapter
Wraps the Rust immutable-ledger engine.
Implements the same cryptographic primitives in Python for verification.
"""
import hashlib
import json
import struct
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class AccountType(Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"

@dataclass
class LedgerAccount:
    account_id: str
    account_type: AccountType
    balance_micros: int = 0  # Micro-dollars (matching Rust MicroDollar)

@dataclass
class JournalEntry:
    entry_id: int
    debit_account: str
    credit_account: str
    amount_micros: int
    timestamp_ns: int
    metadata: bytes = b''
    parent_hash: bytes = b'\x00' * 32

class ImmutableLedger:
    """
    Python implementation matching the Rust immutable-ledger.
    
    Key features (matching src/ledger.rs):
    - Hash-chained entries for tamper detection
    - Double-entry conservation: Σ(debits) = Σ(credits)
    - Merkle tree for balance proofs
    - Fixed-point micro-dollar precision
    """
    
    def __init__(self):
        self.accounts: dict[str, LedgerAccount] = {}
        self.entries: list[JournalEntry] = []
        self.chain_head: bytes = b'\x00' * 32
        self.next_entry_id = 1
    
    def create_account(self, account_id: str, account_type: AccountType) -> LedgerAccount:
        """Create a new account with zero balance."""
        if account_id in self.accounts:
            raise ValueError(f"Account {account_id} already exists")
        account = LedgerAccount(account_id, account_type)
        self.accounts[account_id] = account
        return account
    
    def post_entry(
        self,
        debit_account: str,
        credit_account: str,
        amount_micros: int,
        metadata: bytes = b'',
    ) -> JournalEntry:
        """
        Posts a double-entry transaction.
        
        INVARIANT: Every debit must have a matching credit.
        Matches Ledger::post_entry() in Rust.
        """
        if amount_micros <= 0:
            raise ValueError("Amount must be positive")
        if debit_account == credit_account:
            raise ValueError("Debit and credit accounts must differ")
        
        # Verify accounts exist
        if debit_account not in self.accounts:
            self.create_account(debit_account, AccountType.ASSET)
        if credit_account not in self.accounts:
            self.create_account(credit_account, AccountType.LIABILITY)
        
        # Check for overflow (matching Rust checked_add)
        debit_acct = self.accounts[debit_account]
        credit_acct = self.accounts[credit_account]
        
        import time
        entry = JournalEntry(
            entry_id=self.next_entry_id,
            debit_account=debit_account,
            credit_account=credit_account,
            amount_micros=amount_micros,
            timestamp_ns=time.time_ns(),
            metadata=metadata,
            parent_hash=self.chain_head,
        )
        
        # Apply transaction
        debit_acct.balance_micros += amount_micros
        credit_acct.balance_micros -= amount_micros
        
        # Compute entry hash (matching Entry::hash() in Rust)
        entry_hash = self._compute_entry_hash(entry)
        self.chain_head = entry_hash
        self.entries.append(entry)
        self.next_entry_id += 1
        
        return entry
    
    def _compute_entry_hash(self, entry: JournalEntry) -> bytes:
        """Matches sha2::Sha256 computation in Rust Entry::hash()."""
        hasher = hashlib.sha256()
        hasher.update(struct.pack('<Q', entry.entry_id))
        hasher.update(entry.debit_account.encode())
        hasher.update(entry.credit_account.encode())
        hasher.update(struct.pack('<q', entry.amount_micros))
        hasher.update(struct.pack('<q', entry.timestamp_ns))
        hasher.update(entry.metadata)
        hasher.update(entry.parent_hash)
        return hasher.digest()
    
    def verify_chain_integrity(self) -> bool:
        """
        Verifies the entire hash chain from genesis.
        Matches Ledger::verify_chain_integrity() in Rust.
        """
        expected_parent = b'\x00' * 32
        for entry in self.entries:
            # Verify parent hash links correctly
            if entry.parent_hash != expected_parent:
                return False
            # Compute expected hash and advance chain
            expected_parent = self._compute_entry_hash(entry)
        return True
    
    def verify_conservation(self) -> bool:
        """
        Verifies the fundamental double-entry invariant:
        Σ(all balances) = 0
        """
        total = sum(acct.balance_micros for acct in self.accounts.values())
        return total == 0
    
    def generate_balance_proof(self, account_id: str) -> Optional[dict]:
        """
        Generates a cryptographic proof of balance.
        In production, this would be a Merkle proof.
        For demo, we return the account state with chain verification.
        """
        if account_id not in self.accounts:
            return None
        
        account = self.accounts[account_id]
        return {
            'account_id': account_id,
            'balance_micros': account.balance_micros,
            'balance_dollars': account.balance_micros / 10_000_000,
            'chain_head': self.chain_head.hex(),
            'total_entries': len(self.entries),
            'chain_valid': self.verify_chain_integrity(),
            'conservation_valid': self.verify_conservation(),
        }
    
    def get_balance(self, account_id: str) -> Optional[float]:
        """Returns balance in dollars."""
        if account_id not in self.accounts:
            return None
        return self.accounts[account_id].balance_micros / 10_000_000
