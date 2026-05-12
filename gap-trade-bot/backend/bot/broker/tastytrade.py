"""
TastytradeBroker — adapter for the Tastytrade REST API.
Requires: pip install tastytrade>=8.0.0
"""
from __future__ import annotations
from decimal import Decimal
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
    Config keys: username, password, paper (bool)
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
            logger.info(f'TastytradeBroker connected, account={self._account_id}')
            return True
        except Exception as e:
            logger.warning(f'TastytradeBroker.connect failed: {e}')
            self._session = None
            return False

    def _require_session(self):
        if not self._session:
            if not self.connect():
                raise BrokerError('Tastytrade session not connected')

    # ── Account ────────────────────────────────────────────────────────────

    def get_account(self) -> AccountInfo:
        self._require_session()
        from tastytrade import Account
        acc = Account.get_account(self._session, self._account_id)
        bal = acc.get_balances(self._session)
        return AccountInfo(
            account_id    = self._account_id,
            cash          = float(getattr(bal, 'cash_balance', 0)),
            buying_power  = float(getattr(bal, 'derivative_buying_power', 0)
                                  or getattr(bal, 'equity_buying_power', 0)),
            equity        = float(getattr(bal, 'net_liquidating_value', 0)),
            paper_trading = self._paper,
        )

    # ── Orders ─────────────────────────────────────────────────────────────

    def place_order(self, symbol: str, side: OrderSide, qty: float,
                    order_type: OrderType = OrderType.MARKET,
                    limit_price: Optional[float] = None,
                    stop_price: Optional[float] = None,
                    time_in_force: str = 'day') -> Order:
        self._require_session()
        try:
            from tastytrade import Account
            from tastytrade.orders import (
                NewOrder, NewOrderLeg, OrderAction,
                OrderTimeInForce, OrderType as TTType, InstrumentType,
            )

            action = (OrderAction.BUY_TO_OPEN
                      if side == OrderSide.BUY else OrderAction.SELL_TO_CLOSE)

            tt_type_map = {
                OrderType.MARKET:     TTType.MARKET,
                OrderType.LIMIT:      TTType.LIMIT,
                OrderType.STOP:       TTType.STOP,
                OrderType.STOP_LIMIT: TTType.STOP_LIMIT,
            }
            tt_type = tt_type_map.get(order_type, TTType.MARKET)

            tif_map = {'day': OrderTimeInForce.DAY, 'gtc': OrderTimeInForce.GTC}
            tt_tif = tif_map.get(str(time_in_force).lower(), OrderTimeInForce.DAY)

            leg = NewOrderLeg(
                instrument_type=InstrumentType.EQUITY,
                symbol=symbol.upper(),
                quantity=abs(int(qty)),
                action=action,
            )

            order_kwargs: dict = dict(time_in_force=tt_tif, order_type=tt_type, legs=[leg])
            if limit_price is not None:
                order_kwargs['price'] = Decimal(str(round(limit_price, 2)))
            if stop_price is not None:
                order_kwargs['stop_trigger'] = Decimal(str(round(stop_price, 2)))

            acc = Account.get_account(self._session, self._account_id)
            resp = acc.place_order(self._session, NewOrder(**order_kwargs), dry_run=False)
            placed = resp.order

            return self._map_order(placed, symbol, side, qty, order_type,
                                   limit_price, stop_price)
        except BrokerError:
            raise
        except Exception as e:
            raise BrokerError(f'TastytradeBroker.place_order failed: {e}') from e

    def cancel_order(self, order_id: str) -> bool:
        self._require_session()
        try:
            from tastytrade import Account
            acc = Account.get_account(self._session, self._account_id)
            acc.delete_order(self._session, order_id)
            return True
        except Exception as e:
            logger.warning(f'TastytradeBroker.cancel_order({order_id}) failed: {e}')
            return False

    def get_order(self, order_id: str) -> Order:
        self._require_session()
        try:
            from tastytrade import Account
            acc = Account.get_account(self._session, self._account_id)
            placed = acc.get_order(self._session, order_id)
            # Reconstruct minimal Order — we don't know original side/qty from the response alone
            raw_side = str(getattr(placed, 'underlying_direction', '') or '').upper()
            side = OrderSide.BUY if 'BUY' in raw_side else OrderSide.SELL
            qty = float(getattr(placed, 'size', 0) or 0)
            sym = str(getattr(placed, 'underlying_symbol', order_id))
            return self._map_order(placed, sym, side, qty,
                                   OrderType.MARKET, None, None)
        except BrokerError:
            raise
        except Exception as e:
            raise BrokerError(f'TastytradeBroker.get_order({order_id}) failed: {e}') from e

    # ── Positions ──────────────────────────────────────────────────────────

    def get_positions(self) -> list[Position]:
        self._require_session()
        from tastytrade import Account
        acc = Account.get_account(self._session, self._account_id)
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
        pos = self.get_position(symbol)
        if not pos:
            raise BrokerError(f'TastytradeBroker: no open position for {symbol}')
        side = OrderSide.SELL if pos.side == 'long' else OrderSide.BUY
        return self.place_order(symbol, side, abs(pos.qty))

    # ── Quotes ─────────────────────────────────────────────────────────────

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

    # ── Helpers ────────────────────────────────────────────────────────────

    def _map_order(self, placed, symbol: str, side: OrderSide, qty: float,
                   order_type: OrderType, limit_price, stop_price) -> Order:
        status_map = {
            'live':      OrderStatus.SUBMITTED,
            'filled':    OrderStatus.FILLED,
            'cancelled': OrderStatus.CANCELLED,
            'rejected':  OrderStatus.REJECTED,
            'received':  OrderStatus.PENDING,
            'cancelled with legs': OrderStatus.CANCELLED,
        }
        raw_status = str(getattr(placed, 'status', '') or '').lower()
        status = status_map.get(raw_status, OrderStatus.UNKNOWN)
        return Order(
            order_id        = str(getattr(placed, 'id', '')),
            symbol          = symbol.upper(),
            side            = side,
            qty             = abs(int(qty)),
            order_type      = order_type,
            status          = status,
            filled_qty      = int(getattr(placed, 'size', 0) or 0),
            filled_avg_price= float(getattr(placed, 'price', 0) or 0),
            limit_price     = limit_price,
            stop_price      = stop_price,
            raw             = placed,
        )
