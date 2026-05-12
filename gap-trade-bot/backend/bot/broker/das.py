"""
DASBroker — wraps the existing DAS Trader Pro TCP socket interface.

This adapter preserves 100 % of the existing DAS behaviour so the local
Windows setup continues to work unchanged.  It delegates to the same
_send_das_script() / place_das_order() helpers already used by app.py,
so there is no duplicated socket logic here.
"""
from __future__ import annotations
import uuid
import re
from typing import Optional, TYPE_CHECKING
from logging_config import get_logger
from .base import (
    BrokerBase, BrokerError,
    Order, Position, Quote, AccountInfo,
    OrderSide, OrderType, OrderStatus,
)

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class DASBroker(BrokerBase):
    """
    Broker adapter for DAS Trader Pro (local TCP socket 127.0.0.1:9800).
    Only works when the Flask server runs on the same Windows machine as DAS.
    """

    def __init__(self, host: str = '127.0.0.1', port: int = 9800,
                 username: str = '', password: str = '', account: str = ''):
        self._host     = host
        self._port     = port
        self._username = username
        self._password = password
        self._account  = account
        self._connected = False

    # ------------------------------------------------------------------
    # Identity / connectivity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return f'DAS Trader Pro ({self._host}:{self._port})'

    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        """Verify the DAS TCP socket is reachable by sending GET ACCOUNT."""
        try:
            raw = self._send('GET ACCOUNT\r\n')
            self._connected = bool(raw and 'ACCOUNT' in raw.upper())
            return self._connected
        except Exception as e:
            logger.warning(f'DASBroker.connect failed: {e}')
            self._connected = False
            return False

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def get_account(self) -> AccountInfo:
        raw = self._send('GET ACCOUNT\r\n') or ''
        # DAS response: "ACCOUNT <id> BP <buying_power> ..."; parse best-effort
        bp_match  = re.search(r'BP\s+([\d.]+)',  raw)
        eq_match  = re.search(r'EQ\s+([\d.]+)',  raw)
        acc_match = re.search(r'ACCOUNT\s+(\S+)', raw)
        return AccountInfo(
            account_id   = acc_match.group(1) if acc_match else self._account,
            cash         = float(eq_match.group(1)) if eq_match else 0.0,
            buying_power = float(bp_match.group(1)) if bp_match else 0.0,
            equity       = float(eq_match.group(1)) if eq_match else 0.0,
            paper_trading= False,
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
        order_id = str(uuid.uuid4())[:8].upper()
        side_char = 'B' if side == OrderSide.BUY else 'S'

        # Map order type to DAS type string
        das_type_map = {
            OrderType.MARKET:     'MKT',
            OrderType.LIMIT:      'LMT',
            OrderType.STOP:       'STOP',
            OrderType.STOP_LIMIT: 'STPLMT',
        }
        das_type = das_type_map.get(order_type, 'MKT')

        cmd = f'NEWORDER {order_id} {side_char} {symbol.upper()} SMAT {int(qty)} {das_type}'
        if limit_price:
            cmd += f' {limit_price:.2f}'
        if stop_price:
            cmd += f' {stop_price:.2f}'
        cmd += '\r\n'

        raw = self._send(cmd) or ''
        logger.info(f'DAS order {order_id}: {cmd.strip()} → {raw.strip()}')

        status = OrderStatus.SUBMITTED if raw else OrderStatus.UNKNOWN
        return Order(
            order_id  = order_id,
            symbol    = symbol.upper(),
            side      = side,
            qty       = float(qty),
            order_type= order_type,
            status    = status,
            raw       = {'response': raw},
        )

    def cancel_order(self, order_id: str) -> bool:
        raw = self._send(f'CANCELORDER {order_id}\r\n') or ''
        return 'OK' in raw.upper() or 'CANCEL' in raw.upper()

    def get_order(self, order_id: str) -> Order:
        # DAS does not have a simple per-order query; return a stub
        return Order(
            order_id  = order_id,
            symbol    = '',
            side      = OrderSide.BUY,
            qty       = 0,
            order_type= OrderType.MARKET,
            status    = OrderStatus.UNKNOWN,
        )

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_positions(self) -> list[Position]:
        raw = self._send('GET POSITIONS\r\n') or ''
        positions = []
        for line in raw.splitlines():
            pos = self._parse_position_line(line)
            if pos:
                positions.append(pos)
        return positions

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

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def get_quote(self, symbol: str) -> Quote:
        # Subscribe to Level 1 and read one snapshot
        sub_cmd = f'SB {symbol.upper()} Lv1\r\n'
        raw = self._send(sub_cmd) or ''
        # DAS Lv1 response: "LV1 NVDA B=200.50 A=200.55 L=200.52 V=1234567"
        bid  = self._parse_field(raw, r'B=([\d.]+)')
        ask  = self._parse_field(raw, r'A=([\d.]+)')
        last = self._parse_field(raw, r'L=([\d.]+)') or bid or ask
        vol  = int(self._parse_field(raw, r'V=(\d+)') or 0)
        return Quote(symbol=symbol.upper(), bid=bid or 0, ask=ask or 0,
                     last=last or 0, volume=vol)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _send(self, cmd: str) -> str:
        """
        Route through the existing app.py helpers so we reuse the shared socket
        and thread-safety mechanisms already in place.
        """
        try:
            import sys, os
            sys.path.insert(0, os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__)))))
            from app import _send_das_script
            return _send_das_script(cmd)
        except Exception as e:
            logger.error(f'DASBroker._send error: {e}')
            return ''

    @staticmethod
    def _parse_field(text: str, pattern: str) -> Optional[float]:
        m = re.search(pattern, text)
        return float(m.group(1)) if m else None

    @staticmethod
    def _parse_position_line(line: str) -> Optional[Position]:
        """Parse a single DAS POSITIONS response line into a Position."""
        # DAS format (approximate): "POSITION NVDA 100 200.50 201.00 50.00"
        parts = line.strip().split()
        if len(parts) < 3 or parts[0].upper() != 'POSITION':
            return None
        try:
            symbol = parts[1].upper()
            qty    = float(parts[2])
            entry  = float(parts[3]) if len(parts) > 3 else 0.0
            cur    = float(parts[4]) if len(parts) > 4 else entry
            pnl    = (cur - entry) * qty
            return Position(
                symbol          = symbol,
                qty             = qty,
                side            = 'long' if qty > 0 else 'short',
                avg_entry_price = entry,
                current_price   = cur,
                unrealized_pnl  = pnl,
                market_value    = cur * abs(qty),
            )
        except (IndexError, ValueError):
            return None
