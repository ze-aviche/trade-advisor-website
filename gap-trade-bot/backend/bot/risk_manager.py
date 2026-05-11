"""BrownBot portfolio-level risk gate."""
from datetime import datetime


class RiskManager:
    def __init__(self, config: dict):
        self.max_daily_loss = float(config.get('max_daily_loss', -500.0))
        self.max_concurrent_day = int(config.get('max_concurrent_day', 3))
        self.max_concurrent_swing = int(config.get('max_concurrent_swing', 5))

    def can_enter(self, symbol: str, position_type: str,
                  active_positions: dict) -> tuple:
        """Return (allowed: bool, reason: str). Call before every NEWORDER."""
        day_count = sum(
            1 for p in active_positions.values()
            if p.get('position_type') in ('day', 'brown_day')
        )
        swing_count = sum(
            1 for p in active_positions.values()
            if p.get('position_type') in ('swing', 'brown_swing')
        )
        daily_pnl = self._get_daily_pnl()

        if daily_pnl <= self.max_daily_loss:
            return False, f"Daily loss limit hit (P&L: ${daily_pnl:.0f}, limit: ${self.max_daily_loss:.0f})"
        if position_type == 'day' and day_count >= self.max_concurrent_day:
            return False, f"Max day positions ({self.max_concurrent_day}) reached"
        if position_type == 'swing' and swing_count >= self.max_concurrent_swing:
            return False, f"Max swing positions ({self.max_concurrent_swing}) reached"
        return True, "OK"

    def status(self, active_positions: dict) -> dict:
        """Return a snapshot dict for the risk-status API endpoint."""
        daily_pnl = self._get_daily_pnl()
        day_count = sum(
            1 for p in active_positions.values()
            if p.get('position_type') in ('day', 'brown_day')
        )
        swing_count = sum(
            1 for p in active_positions.values()
            if p.get('position_type') in ('swing', 'brown_swing')
        )
        circuit_open = daily_pnl <= self.max_daily_loss
        return {
            'daily_pnl': round(daily_pnl, 2),
            'max_daily_loss': self.max_daily_loss,
            'open_day': day_count,
            'max_concurrent_day': self.max_concurrent_day,
            'open_swing': swing_count,
            'max_concurrent_swing': self.max_concurrent_swing,
            'circuit_breaker_open': circuit_open,
        }

    def _get_daily_pnl(self) -> float:
        try:
            from database import db_manager
            today = datetime.now().strftime('%Y-%m-%d')
            summary = db_manager.get_trade_summary(start_date=today, end_date=today)
            return float(summary.get('total_pnl', 0.0)) if summary else 0.0
        except Exception:
            return 0.0
