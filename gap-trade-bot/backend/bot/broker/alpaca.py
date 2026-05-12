"""
AlpacaBroker — cloud-native broker adapter using the Alpaca Trading API.

Works from any cloud server (Render, etc.) — no local desktop app required.
Supports both paper trading and live trading via the same interface.

Requires: pip install alpaca-py
Docs: https://docs.alpaca.markets/reference/trading-api
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


def _map_order_status(alpaca_status: str) -> OrderStatus:
    return {
        'new':              OrderStatus.SUBMITTED,
        'partially_filled': OrderStatus.PARTIAL,
        'filled':           OrderStatus.FILLED,
        'canceled':         OrderStatus.CANCELLED,
        'cancelled':        OrderStatus.CANCELLED,
        'rejected':         OrderStatus.REJECTED,
        'pending_new':      OrderStatus.PENDING,
        'accepted':         OrderStatus.SUBMITTED,
        'held':             OrderStatus.SUBMITTED,
    }.get(alpaca_status.lower(), OrderStatus.UNKNOWN)


class AlpacaBroker(BrokerBase):
    """
    Broker adapter for Alpaca Markets.
    Both paper (sandbox) and live environments are supported via the
    paper=True/False flag in the config.

    Config keys expected:
        api_key    – Alpaca API key ID
        api_secret – Alpaca secret key
        paper      – bool, default True (use paper trading endpoint)
    """

    def __init__(self, api_key: str, api_secret: str, paper: bool = True):
        self._api_key    = api_key
        self._api_secret = api_secret
        self._paper      = paper
        self._client     = None   # TradingClient, lazy-initialised in connect()
        self._data_client = None  # StockLatestQuoteRequest, lazy-initialised

    # ------------------------------------------------------------------
    # Identity / connectivity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        env = 'paper' if self._paper else 'live'
        return f'Alpaca ({env})'

    def is_connected(self) -> bool:
        return self._client is not None

    def connect(self) -> bool:
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.data.historical import StockHistoricalDataClient
            self._client      = TradingClient(self._api_key, self._api_secret,
                                              paper=self._paper)
            self._data_client = StockHistoricalDataClient(self._api_key, self._api_secret)
            # Verify credentials by fetching account
            self._client.get_account()
            logger.info(f'AlpacaBroker connected ({self.name})')
            return True
        except Exception as e:
            logger.warning(f'AlpacaBroker.connect failed: {e}')
            self._client = None
            return False

    def _require_client(self):
        if not self._client:
            if not self.connect():
                raise BrokerError('Alpaca client not connected')

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def get_account(self) -> AccountInfo:
        self._require_client()
        acc = self._client.get_account()
        return AccountInfo(
            account_id         = str(acc.id),
            cash               = float(acc.cash),
            buying_power       = float(acc.buying_power),
            equity             = float(acc.equity),
            day_trade_count    = int(getattr(acc, 'daytrade_count', 0)),
            pattern_day_trader = bool(getattr(acc, 'pattern_day_trader', False)),
            paper_trading      = self._paper,
        )

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def place_order(
        self,
        symbol:       str,
        side:         OrderSide,
        qty:          float,
        order_type:   OrderType       = OrderType.MARKET,
        limit_price:  Optional[float] = None,
        stop_price:   Optional[float] = None,
        time_in_force: str            = 'day',
    ) -> Order:
        self._require_client()
        from alpaca.trading.requests import (
            MarketOrderRequest, LimitOrderRequest,
            StopOrderRequest, StopLimitOrderRequest,
        )
        from alpaca.trading.enums import OrderSide as AlpacaSide, TimeInForce

        alpaca_side = AlpacaSide.BUY if side == OrderSide.BUY else AlpacaSide.SELL
        tif = TimeInForce.DAY if time_in_force == 'day' else TimeInForce.GTC

        if order_type == OrderType.MARKET:
            req = MarketOrderRequest(symbol=symbol, qty=qty,
                                     side=alpaca_side, time_in_force=tif)
        elif order_type == OrderType.LIMIT:
            req = LimitOrderRequest(symbol=symbol, qty=qty, side=alpaca_side,
                                    time_in_force=tif, limit_price=limit_price)
        elif order_type == OrderType.STOP:
            req = StopOrderRequest(symbol=symbol, qty=qty, side=alpaca_side,
                                   time_in_force=tif, stop_price=stop_price)
        elif order_type == OrderType.STOP_LIMIT:
            req = StopLimitOrderRequest(symbol=symbol, qty=qty, side=alpaca_side,
                                        time_in_force=tif, limit_price=limit_price,
                                        stop_price=stop_price)
        else:
            raise BrokerError(f'Unsupported order type: {order_type}')

        try:
            resp = self._client.submit_order(req)
            return Order(
                order_id         = str(resp.id),
                symbol           = symbol.upper(),
                side             = side,
                qty              = float(qty),
                order_type       = order_type,
                status           = _map_order_status(str(resp.status)),
                filled_qty       = float(resp.filled_qty or 0),
                filled_avg_price = float(resp.filled_avg_price) if resp.filled_avg_price else None,
                limit_price      = limit_price,
                stop_price       = stop_price,
                raw              = {'id': str(resp.id), 'status': str(resp.status)},
            )
        except Exception as e:
            raise BrokerError(f'Alpaca place_order failed: {e}') from e

    def cancel_order(self, order_id: str) -> bool:
        self._require_client()
        try:
            self._client.cancel_order_by_id(order_id)
            return True
        except Exception as e:
            logger.warning(f'AlpacaBroker.cancel_order {order_id}: {e}')
            return False

    def get_order(self, order_id: str) -> Order:
        self._require_client()
        resp = self._client.get_order_by_id(order_id)
        return Order(
            order_id         = str(resp.id),
            symbol           = str(resp.symbol).upper(),
            side             = OrderSide.BUY if str(resp.side) == 'buy' else OrderSide.SELL,
            qty              = float(resp.qty),
            order_type       = OrderType.MARKET,
            status           = _map_order_status(str(resp.status)),
            filled_qty       = float(resp.filled_qty or 0),
            filled_avg_price = float(resp.filled_avg_price) if resp.filled_avg_price else None,
            raw              = {'id': str(resp.id), 'status': str(resp.status)},
        )

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_positions(self) -> list[Position]:
        self._require_client()
        return [self._alpaca_pos_to_position(p)
                for p in self._client.get_all_positions()]

    def get_position(self, symbol: str) -> Optional[Position]:
        self._require_client()
        try:
            p = self._client.get_open_position(symbol.upper())
            return self._alpaca_pos_to_position(p)
        except Exception:
            return None

    def close_position(self, symbol: str) -> Order:
        self._require_client()
        try:
            resp = self._client.close_position(symbol.upper())
            return Order(
                order_id  = str(resp.id),
                symbol    = symbol.upper(),
                side      = OrderSide.SELL,
                qty       = float(resp.qty),
                order_type= OrderType.MARKET,
                status    = _map_order_status(str(resp.status)),
                raw       = {'id': str(resp.id)},
            )
        except Exception as e:
            raise BrokerError(f'Alpaca close_position {symbol} failed: {e}') from e

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def get_quote(self, symbol: str) -> Quote:
        self._require_client()
        try:
            from alpaca.data.requests import StockLatestQuoteRequest
            req  = StockLatestQuoteRequest(symbol_or_symbols=symbol.upper())
            data = self._data_client.get_stock_latest_quote(req)
            q    = data[symbol.upper()]
            return Quote(
                symbol = symbol.upper(),
                bid    = float(q.bid_price or 0),
                ask    = float(q.ask_price or 0),
                last   = float(q.ask_price or q.bid_price or 0),
                volume = 0,
            )
        except Exception as e:
            raise BrokerError(f'Alpaca get_quote {symbol} failed: {e}') from e

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _alpaca_pos_to_position(p) -> Position:
        qty = float(p.qty)
        return Position(
            symbol          = str(p.symbol).upper(),
            qty             = qty,
            side            = 'long' if qty > 0 else 'short',
            avg_entry_price = float(p.avg_entry_price),
            current_price   = float(p.current_price or p.avg_entry_price),
            unrealized_pnl  = float(p.unrealized_pl or 0),
            market_value    = float(p.market_value or 0),
            raw             = {'asset_id': str(p.asset_id)},
        )
