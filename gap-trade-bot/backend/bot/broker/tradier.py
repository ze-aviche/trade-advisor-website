"""
TradierBroker — adapter for Tradier brokerage REST API.
Stub implementation — full adapter to be built in Phase 3.
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

_SANDBOX_BASE = 'https://sandbox.tradier.com/v1'
_LIVE_BASE    = 'https://api.tradier.com/v1'


class TradierBroker(BrokerBase):
    """
    Broker adapter for Tradier.
    Requires: pip install requests
    Config: api_key, paper (bool)
    """

    def __init__(self, api_key: str, paper: bool = True):
        self._api_key = api_key
        self._paper   = paper
        self._base    = _SANDBOX_BASE if paper else _LIVE_BASE
        self._account_id: str = ''

    @property
    def name(self) -> str:
        return f'Tradier ({"sandbox" if self._paper else "live"})'

    def is_connected(self) -> bool:
        return bool(self._account_id)

    def connect(self) -> bool:
        try:
            import requests
            r = requests.get(f'{self._base}/user/profile',
                             headers=self._headers(), timeout=5)
            r.raise_for_status()
            accounts = r.json().get('profile', {}).get('account', [])
            if isinstance(accounts, dict):
                accounts = [accounts]
            if accounts:
                self._account_id = accounts[0].get('account_number', '')
            return bool(self._account_id)
        except Exception as e:
            logger.warning(f'TradierBroker.connect failed: {e}')
            return False

    def get_account(self) -> AccountInfo:
        import requests
        r = requests.get(f'{self._base}/accounts/{self._account_id}/balances',
                         headers=self._headers(), timeout=5)
        r.raise_for_status()
        b = r.json().get('balances', {})
        return AccountInfo(
            account_id   = self._account_id,
            cash         = float(b.get('cash', {}).get('cash_available', 0)),
            buying_power = float(b.get('margin', {}).get('stock_buying_power', 0)
                                 or b.get('cash', {}).get('cash_available', 0)),
            equity       = float(b.get('total_equity', 0)),
            paper_trading= self._paper,
        )

    def place_order(self, symbol, side, qty, order_type=OrderType.MARKET,
                    limit_price=None, stop_price=None, time_in_force='day') -> Order:
        import requests
        tradier_side = 'buy' if side == OrderSide.BUY else 'sell'
        tradier_type = {
            OrderType.MARKET:     'market',
            OrderType.LIMIT:      'limit',
            OrderType.STOP:       'stop',
            OrderType.STOP_LIMIT: 'stop_limit',
        }.get(order_type, 'market')

        payload = {
            'class': 'equity', 'symbol': symbol.upper(),
            'side': tradier_side, 'quantity': int(qty),
            'type': tradier_type, 'duration': time_in_force,
        }
        if limit_price: payload['price'] = limit_price
        if stop_price:  payload['stop']  = stop_price

        r = requests.post(f'{self._base}/accounts/{self._account_id}/orders',
                          data=payload, headers=self._headers(), timeout=5)
        r.raise_for_status()
        order_id = str(r.json().get('order', {}).get('id', ''))
        return Order(order_id=order_id, symbol=symbol.upper(), side=side,
                     qty=float(qty), order_type=order_type,
                     status=OrderStatus.SUBMITTED, raw=r.json())

    def cancel_order(self, order_id: str) -> bool:
        import requests
        r = requests.delete(
            f'{self._base}/accounts/{self._account_id}/orders/{order_id}',
            headers=self._headers(), timeout=5)
        return r.status_code == 200

    def get_order(self, order_id: str) -> Order:
        import requests
        r = requests.get(
            f'{self._base}/accounts/{self._account_id}/orders/{order_id}',
            headers=self._headers(), timeout=5)
        r.raise_for_status()
        o = r.json().get('order', {})
        return Order(order_id=order_id, symbol=o.get('symbol', '').upper(),
                     side=OrderSide.BUY, qty=float(o.get('quantity', 0)),
                     order_type=OrderType.MARKET, status=OrderStatus.UNKNOWN,
                     raw=o)

    def get_positions(self) -> list[Position]:
        import requests
        r = requests.get(f'{self._base}/accounts/{self._account_id}/positions',
                         headers=self._headers(), timeout=5)
        r.raise_for_status()
        raw = r.json().get('positions', {}).get('position', [])
        if isinstance(raw, dict):
            raw = [raw]
        return [Position(
            symbol=p['symbol'].upper(), qty=float(p['quantity']),
            side='long' if p['quantity'] > 0 else 'short',
            avg_entry_price=float(p['cost_basis'] / max(abs(p['quantity']), 1)),
            current_price=0.0, unrealized_pnl=0.0,
            market_value=float(p.get('market_value', 0)), raw=p,
        ) for p in raw]

    def get_position(self, symbol: str) -> Optional[Position]:
        for p in self.get_positions():
            if p.symbol == symbol.upper():
                return p
        return None

    def close_position(self, symbol: str) -> Order:
        pos = self.get_position(symbol)
        if not pos:
            raise BrokerError(f'No open position for {symbol}')
        side = OrderSide.SELL if pos.qty > 0 else OrderSide.BUY
        return self.place_order(symbol, side, abs(pos.qty))

    def get_quote(self, symbol: str) -> Quote:
        import requests
        r = requests.get(f'{self._base}/markets/quotes',
                         params={'symbols': symbol.upper(), 'greeks': 'false'},
                         headers=self._headers(), timeout=5)
        r.raise_for_status()
        q = r.json().get('quotes', {}).get('quote', {})
        return Quote(symbol=symbol.upper(),
                     bid=float(q.get('bid', 0)), ask=float(q.get('ask', 0)),
                     last=float(q.get('last', 0)), volume=int(q.get('volume', 0)))

    def _headers(self) -> dict:
        return {'Authorization': f'Bearer {self._api_key}',
                'Accept': 'application/json'}
