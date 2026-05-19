"""BrownBot portfolio-level risk gate."""
from datetime import datetime, timedelta


class RiskManager:
    def __init__(self, config: dict):
        # Always store as a negative threshold regardless of sign the user entered.
        # e.g. both 500 and -500 mean "halt if daily P&L drops below -$500".
        self.max_daily_loss = -abs(float(config.get('max_daily_loss', -500.0)))
        self.max_concurrent_day = int(config.get('max_concurrent_day', 3))
        self.max_concurrent_swing = int(config.get('max_concurrent_swing', 5))

    def can_enter(self, symbol: str, position_type: str,
                  active_positions: dict, unrealized_pnl: float = 0.0) -> tuple:
        """Return (allowed: bool, reason: str). Call before every NEWORDER.

        unrealized_pnl: sum of unrealized_pnl across all active positions,
        passed in by the caller so the circuit breaker uses total P&L
        (realized + unrealized) rather than realized-only.
        """
        day_count = sum(
            1 for p in active_positions.values()
            if p.get('position_type') in ('day', 'brown_day')
        )
        swing_count = sum(
            1 for p in active_positions.values()
            if p.get('position_type') in ('swing', 'brown_swing')
        )
        daily_pnl = self._get_daily_pnl() + unrealized_pnl

        if daily_pnl <= self.max_daily_loss:
            return False, (f"Daily loss limit hit "
                           f"(total P&L: ${daily_pnl:.0f} = "
                           f"realized ${daily_pnl - unrealized_pnl:.0f} + "
                           f"unrealized ${unrealized_pnl:.0f}, "
                           f"limit: ${self.max_daily_loss:.0f})")
        if position_type == 'day' and day_count >= self.max_concurrent_day:
            return False, f"Max day positions ({self.max_concurrent_day}) reached"
        if position_type == 'swing' and swing_count >= self.max_concurrent_swing:
            return False, f"Max swing positions ({self.max_concurrent_swing}) reached"
        return True, "OK"

    def status(self, active_positions: dict, unrealized_pnl: float = 0.0) -> dict:
        """Return a snapshot dict for the risk-status API endpoint.

        unrealized_pnl: sum of unrealized_pnl across all active positions.
        """
        realized_pnl  = self._get_daily_pnl()
        total_pnl     = realized_pnl + unrealized_pnl
        day_count = sum(
            1 for p in active_positions.values()
            if p.get('position_type') in ('day', 'brown_day')
        )
        swing_count = sum(
            1 for p in active_positions.values()
            if p.get('position_type') in ('swing', 'brown_swing')
        )
        circuit_open = total_pnl <= self.max_daily_loss
        return {
            'daily_pnl':          round(total_pnl, 2),
            'realized_pnl':       round(realized_pnl, 2),
            'unrealized_pnl':     round(unrealized_pnl, 2),
            'max_daily_loss':     self.max_daily_loss,
            'open_day':           day_count,
            'max_concurrent_day': self.max_concurrent_day,
            'open_swing':         swing_count,
            'max_concurrent_swing': self.max_concurrent_swing,
            'circuit_breaker_open': circuit_open,
        }

    def _get_daily_pnl(self) -> float:
        try:
            import pytz
            from database import db_manager
            et_tz = pytz.timezone('US/Eastern')
            d = datetime.now(et_tz)
            while d.weekday() >= 5:  # roll back to last trading day (ET)
                d -= timedelta(days=1)
            today = d.strftime('%Y-%m-%d')
            summary = db_manager.get_trade_summary(start_date=today, end_date=today)
            return float(summary.get('total_pnl', 0.0)) if summary else 0.0
        except Exception:
            return 0.0
