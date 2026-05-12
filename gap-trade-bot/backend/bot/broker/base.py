"""
Abstract broker interface.  Every broker adapter (DAS, Alpaca, Tradier, …)
must subclass BrokerBase and implement all abstract methods.  The bots
(Entry Bot, Exit Bot, BrownBot) depend only on this interface — they never
import a concrete adapter directly.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY  = 'buy'
    SELL = 'sell'


class OrderType(str, Enum):
    MARKET     = 'market'
    LIMIT      = 'limit'
    STOP       = 'stop'
    STOP_LIMIT = 'stop_limit'


class OrderStatus(str, Enum):
    PENDING   = 'pending'
    SUBMITTED = 'submitted'
    FILLED    = 'filled'
    PARTIAL   = 'partial'
    CANCELLED = 'cancelled'
    REJECTED  = 'rejected'
    UNKNOWN   = 'unknown'


@dataclass
class Order:
    order_id:          str
    symbol:            str
    side:              OrderSide
    qty:               float
    order_type:        OrderType
    status:            OrderStatus
    filled_qty:        float        = 0.0
    filled_avg_price:  Optional[float] = None
    limit_price:       Optional[float] = None
    stop_price:        Optional[float] = None
    raw:               dict         = field(default_factory=dict)  # broker-native response


@dataclass
class Position:
    symbol:            str
    qty:               float          # positive = long, negative = short
    side:              str            # 'long' | 'short'
    avg_entry_price:   float
    current_price:     float
    unrealized_pnl:    float
    market_value:      float
    raw:               dict = field(default_factory=dict)


@dataclass
class Quote:
    symbol:  str
    bid:     float
    ask:     float
    last:    float
    volume:  int


@dataclass
class AccountInfo:
    account_id:    str
    cash:          float
    buying_power:  float
    equity:        float
    day_trade_count: int  = 0
    pattern_day_trader: bool = False
    paper_trading: bool  = False


class BrokerBase(ABC):
    """
    Broker-agnostic interface for order execution and account management.

    Concrete adapters must implement every abstract method.  Methods may raise
    BrokerError on hard failures; callers should always wrap in try/except.
    """

    # ------------------------------------------------------------------
    # Identity / connectivity
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable broker name, e.g. 'Alpaca (paper)'."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if the broker connection is live and authenticated."""

    @abstractmethod
    def connect(self) -> bool:
        """Establish / verify the connection.  Returns True on success."""

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """Return current account snapshot (equity, buying power, …)."""

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    @abstractmethod
    def place_order(
        self,
        symbol:      str,
        side:        OrderSide,
        qty:         float,
        order_type:  OrderType        = OrderType.MARKET,
        limit_price: Optional[float]  = None,
        stop_price:  Optional[float]  = None,
        time_in_force: str            = 'day',
    ) -> Order:
        """Submit an order.  Returns an Order object with at least order_id."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order.  Returns True if successfully cancelled."""

    @abstractmethod
    def get_order(self, order_id: str) -> Order:
        """Fetch the current state of an order by ID."""

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    @abstractmethod
    def get_positions(self) -> list[Position]:
        """Return all open positions."""

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """Return the open position for *symbol*, or None if flat."""

    @abstractmethod
    def close_position(self, symbol: str) -> Order:
        """Close the entire position for *symbol* at market."""

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        """Return the latest quote for *symbol*."""

    # ------------------------------------------------------------------
    # Helpers (concrete, built on the abstract primitives above)
    # ------------------------------------------------------------------

    def get_current_price(self, symbol: str) -> float:
        """Convenience wrapper — returns last trade price."""
        return self.get_quote(symbol).last

    def to_dict(self) -> dict:
        """Serialisable summary for API responses / logging."""
        return {
            'broker':       self.name,
            'connected':    self.is_connected(),
        }


class BrokerError(Exception):
    """Raised when a broker operation fails in a non-recoverable way."""
