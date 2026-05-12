"""
TastytradeBroker — adapter for the Tastytrade REST API.
Stub implementation — full adapter to be built in Phase 3.
Requires: pip install tastytrade
"""
from __future__ import annotations
from typing import Optional
from logging_config import get_logger
from .base import (
    BrokerBase, BrokerError,
    Order, Position, Quote, AccountInfo,
    OrderSide, OrderType, OrderStatus,
)

logger = get_logger(__name__)


class TastytradeBroker(BrokerBase):
    """
    Broker adapter for Tastytrade.
    Config: username, password, paper (bool)
    """

    def __init__(self, username: str, password: str, paper: bool = False):
        self._username   = username
        self._password   = password
        self._paper      = paper
        self._session    = None
        self._account_id = ''

    @property
    def name(self) -> str:
        return f'Tastytrade ({"paper" if self._paper else "live"})'

    def is_connected(self) -> bool:
        return self._session is not None

    def connect(self) -> bool:
        try:
            from tastytrade import Session, Account
            self._session = Session(self._username, self._password,
                                    is_test=self._paper)
            accounts = Account.get_accounts(self._session)
            if accounts:
                self._account_id = accounts[0].account_number
            return True
        except Exception as e:
            logger.warning(f'TastytradeBroker.connect failed: {e}')
            self._session = None
            return False

    def _require_session(self):
        if not self._session:
            if not self.connect():
                raise BrokerError('Tastytrade session not connected')

    def get_account(self) -> AccountInfo:
        self._require_session()
        from tastytrade import Account
        acc = Account.get_account(self._session, self._account_id)
        bal = acc.get_balances(self._session)
        return AccountInfo(
            account_id   = self._account_id,
            cash         = float(getattr(bal, 'cash_balance', 0)),
            buying_power = float(getattr(bal, 'derivative_buying_power', 0)
                                 or getattr(bal, 'equity_buying_power', 0)),
            equity       = float(getattr(bal, 'net_liquidating_value', 0)),
            paper_trading= self._paper,
        )

    def place_order(self, symbol, side, qty, order_type=OrderType.MARKET,
                    limit_price=None, stop_price=None, time_in_force='day') -> Order:
        raise BrokerError('TastytradeBroker.place_order not yet implemented')

    def cancel_order(self, order_id: str) -> bool:
        raise BrokerError('TastytradeBroker.cancel_order not yet implemented')

    def get_order(self, order_id: str) -> Order:
        raise BrokerError('TastytradeBroker.get_order not yet implemented')

    def get_positions(self) -> list[Position]:
        self._require_session()
        from tastytrade import Account
        acc  = Account.get_account(self._session, self._account_id)
        positions = acc.get_positions(self._session)
        result = []
        for p in positions:
            qty = float(getattr(p, 'quantity', 0))
            result.append(Position(
                symbol          = str(p.symbol).upper(),
                qty             = qty,
                side            = 'long' if qty > 0 else 'short',
                avg_entry_price = float(getattr(p, 'average_open_price', 0)),
                current_price   = float(getattr(p, 'mark', 0)),
                unrealized_pnl  = float(getattr(p, 'unrealized_day_gain', 0)),
                market_value    = float(getattr(p, 'market_value', 0)),
            ))
        return result

    def get_position(self, symbol: str) -> Optional[Position]:
        for p in self.get_positions():
            if p.symbol == symbol.upper():
                return p
        return None

    def close_position(self, symbol: str) -> Order:
        raise BrokerError('TastytradeBroker.close_position not yet implemented')

    def get_quote(self, symbol: str) -> Quote:
        self._require_session()
        from tastytrade.instruments import Equity
        from tastytrade.market_data import get_market_data
        eq   = Equity.get_equity(self._session, symbol.upper())
        data = get_market_data(self._session, [eq])
        if data:
            d = data[0]
            return Quote(symbol=symbol.upper(),
                         bid=float(getattr(d, 'bid', 0)),
                         ask=float(getattr(d, 'ask', 0)),
                         last=float(getattr(d, 'last', 0)),
                         volume=int(getattr(d, 'volume', 0)))
        raise BrokerError(f'No quote data for {symbol}')
