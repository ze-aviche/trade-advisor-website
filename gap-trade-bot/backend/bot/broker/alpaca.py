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
            from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest
            sym = symbol.upper()

            quote_req  = StockLatestQuoteRequest(symbol_or_symbols=sym)
            quote_data = self._data_client.get_stock_latest_quote(quote_req)
            q          = quote_data[sym]

            # Use the actual last trade price, not ask_price, so exit condition
            # checks reflect real executions rather than the (higher) ask.
            try:
                trade_req  = StockLatestTradeRequest(symbol_or_symbols=sym)
                trade_data = self._data_client.get_stock_latest_trade(trade_req)
                t          = trade_data[sym]
                last_price = float(t.price) if t and t.price else float(q.bid_price or 0)
            except Exception:
                last_price = float(q.bid_price or q.ask_price or 0)

            return Quote(
                symbol = sym,
                bid    = float(q.bid_price or 0),
                ask    = float(q.ask_price or 0),
                last   = last_price,
                volume = 0,
            )
        except Exception as e:
            raise BrokerError(f'Alpaca get_quote {symbol} failed: {e}') from e

    # ------------------------------------------------------------------
    # Order history
    # ------------------------------------------------------------------

    def get_orders_history(
        self,
        status: str = 'filled',
        limit: int = 100,
        after: Optional[str] = None,
        until: Optional[str] = None,
        symbols: Optional[list] = None,
    ) -> list[dict]:
        """Return orders as plain dicts suitable for JSON serialisation.

        status: 'filled' / 'closed' → filled+cancelled; 'open'; 'all'
        after / until: ISO date string 'YYYY-MM-DD' or full ISO datetime.
        """
        self._require_client()
        try:
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus

            status_map = {
                'filled': QueryOrderStatus.CLOSED,
                'closed': QueryOrderStatus.CLOSED,
                'open':   QueryOrderStatus.OPEN,
                'all':    QueryOrderStatus.ALL,
            }
            req_kwargs: dict = {
                'status': status_map.get(status.lower(), QueryOrderStatus.CLOSED),
                'limit':  limit,
            }
            if after or until:
                from datetime import datetime as _dt
                if after:
                    s = after if 'T' in after else after + 'T00:00:00'
                    req_kwargs['after'] = _dt.fromisoformat(s)
                if until:
                    s = until if 'T' in until else until + 'T23:59:59'
                    req_kwargs['until'] = _dt.fromisoformat(s)
            if symbols:
                req_kwargs['symbols'] = [s.upper() for s in symbols]

            orders = self._client.get_orders(filter=GetOrdersRequest(**req_kwargs))

            def _val(x):
                return x.value if hasattr(x, 'value') else str(x) if x is not None else None

            result = []
            for o in orders:
                result.append({
                    'order_id':         str(o.id),
                    'symbol':           str(o.symbol).upper(),
                    'side':             _val(o.side),
                    'qty':              float(o.qty or 0),
                    'filled_qty':       float(o.filled_qty or 0),
                    'filled_avg_price': float(o.filled_avg_price) if o.filled_avg_price else None,
                    'status':           _val(o.status),
                    'order_type':       _val(o.order_type),
                    'time_in_force':    _val(o.time_in_force),
                    'created_at':       o.created_at.isoformat() if o.created_at else None,
                    'submitted_at':     o.submitted_at.isoformat() if o.submitted_at else None,
                    'filled_at':        o.filled_at.isoformat() if o.filled_at else None,
                    'limit_price':      float(o.limit_price) if o.limit_price else None,
                    'stop_price':       float(o.stop_price) if o.stop_price else None,
                })
            return result
        except Exception as e:
            raise BrokerError(f'Alpaca get_orders_history failed: {e}') from e

    # ------------------------------------------------------------------
    # Account activities
    # ------------------------------------------------------------------

    def get_activities(
        self,
        activity_type: str = 'FILL',
        date: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Return account activities via direct REST call.

        activity_type: 'FILL' for trade executions, 'JNLC' for journal cash, etc.
        date: 'YYYY-MM-DD' to filter to a single day (Alpaca UTC boundary).
        """
        self._require_client()
        try:
            import requests as _req
            base = ('https://paper-api.alpaca.markets'
                    if self._paper else 'https://api.alpaca.markets')
            url     = f'{base}/v2/account/activities/{activity_type}'
            params: dict = {'page_size': min(limit, 100)}
            if date:
                params['date'] = date
            headers = {
                'APCA-API-KEY-ID':     self._api_key,
                'APCA-API-SECRET-KEY': self._api_secret,
            }
            resp = _req.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise BrokerError(f'Alpaca get_activities failed: {e}') from e

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
