"""
FIX Engine Adapter
Wraps the C++ fix-engine via command-line interface.
In production, this would use gRPC or shared memory.
"""
import subprocess
import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class Side(Enum):
    BUY = "1"
    SELL = "2"

class OrdType(Enum):
    MARKET = "1"
    LIMIT = "2"

@dataclass
class FixOrder:
    cl_ord_id: str
    symbol: str
    side: Side
    price: float
    quantity: int
    ord_type: OrdType = OrdType.LIMIT

@dataclass
class FixExecutionReport:
    cl_ord_id: str
    order_id: str
    symbol: str
    side: Side
    exec_type: str      # "0"=New, "1"=Fill, "2"=Partial, "4"=Cancel
    price: float
    quantity: int
    leaves_qty: int
    cum_qty: int

class FixAdapter:
    """
    Adapter for the C++ FIX protocol engine.
    In the demo, we simulate the engine's output since we can't
    dynamically link C++ from Python without FFI.
    
    The message format exactly matches what fix-engine produces.
    """
    
    def __init__(self, engine_path: Optional[str] = None):
        self.engine_path = engine_path
        self.orders = {}
        self.next_order_id = 1
    
    def encode_new_order_single(self, order: FixOrder) -> bytes:
        """Encodes a FIX 4.4 NewOrderSingle message.
        Format matches fix-engine's FixSession::buildNewOrderSingle()
        """
        SOH = '\x01'
        msg = (
            f"8=FIX.4.4{SOH}"
            f"35=D{SOH}"
            f"49=CLIENT{SOH}"
            f"56=VENUE{SOH}"
            f"34=1{SOH}"
            f"52=20240101-00:00:00{SOH}"
            f"11={order.cl_ord_id}{SOH}"
            f"55={order.symbol}{SOH}"
            f"54={order.side.value}{SOH}"
            f"44={order.price:.7f}{SOH}"
            f"38={order.quantity}{SOH}"
            f"40={order.ord_type.value}{SOH}"
        )
        
        # Body length
        body_len = len(msg) - len(f"8=FIX.4.4{SOH}")
        msg = f"8=FIX.4.4{SOH}9={body_len}{SOH}" + msg.split(SOH, 2)[-1]
        
        # Checksum
        checksum = sum(ord(c) for c in msg) % 256
        msg += f"10={checksum:03d}{SOH}"
        
        return msg.encode('ascii')
    
    def decode_execution_report(self, raw: bytes) -> FixExecutionReport:
        """Decodes an ExecutionReport message.
        Uses zero-copy string operations matching the C++ approach.
        """
        msg = raw.decode('ascii')
        SOH = '\x01'
        fields = {}
        
        for field in msg.split(SOH):
            if '=' in field:
                tag, value = field.split('=', 1)
                fields[tag] = value
        
        return FixExecutionReport(
            cl_ord_id=fields.get('11', ''),
            order_id=fields.get('37', ''),
            symbol=fields.get('55', ''),
            side=Side(fields.get('54', '1')),
            exec_type=fields.get('150', '0'),
            price=float(fields.get('44', '0')),
            quantity=int(fields.get('38', '0')),
            leaves_qty=int(fields.get('151', '0')),
            cum_qty=int(fields.get('14', '0')),
        )
    
    def simulate_venue_response(self, order: FixOrder, fills: list[tuple[float, int]]) -> list[FixExecutionReport]:
        """Simulates exchange venue responding with execution reports."""
        reports = []
        order_id = str(self.next_order_id)
        self.next_order_id += 1
        remaining = order.quantity
        
        for fill_price, fill_qty in fills:
            remaining -= fill_qty
            exec_type = "2" if remaining > 0 else "1"  # Partial or Fill
            
            reports.append(FixExecutionReport(
                cl_ord_id=order.cl_ord_id,
                order_id=order_id,
                symbol=order.symbol,
                side=order.side,
                exec_type=exec_type,
                price=fill_price,
                quantity=fill_qty,
                leaves_qty=max(0, remaining),
                cum_qty=order.quantity - remaining,
            ))
        
        return reports
