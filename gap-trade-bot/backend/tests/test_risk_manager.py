"""
Unit tests for bot/risk_manager.py

Covers: circuit breaker (realized + unrealized P&L),
        day/swing slot caps, exit-pending exclusion, status snapshot.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch
from bot.risk_manager import RiskManager


# ── helpers ──────────────────────────────────────────────────────────────────

def _rm(max_daily_loss=-500, max_day=3, max_swing=5):
    return RiskManager({
        'max_daily_loss': max_daily_loss,
        'max_concurrent_day': max_day,
        'max_concurrent_swing': max_swing,
    })

def _pos(type_='day', exit_pending=False):
    return {'position_type': type_, '_exit_pending': exit_pending}

def _enter(rm, symbol='NVDA', type_='day', positions=None, unrealized=0.0, pnl=0.0):
    """Convenience: patch _get_daily_pnl and call can_enter."""
    with patch.object(rm, '_get_daily_pnl', return_value=pnl):
        return rm.can_enter(symbol, type_, positions or {}, unrealized_pnl=unrealized)


# ── circuit breaker ───────────────────────────────────────────────────────────

class TestCircuitBreaker:
    def test_allows_just_above_limit(self):
        allowed, _ = _enter(_rm(-500), pnl=-499.99)
        assert allowed

    def test_blocks_at_exactly_limit(self):
        allowed, _ = _enter(_rm(-500), pnl=-500.0)
        assert not allowed

    def test_blocks_below_limit(self):
        allowed, reason = _enter(_rm(-500), pnl=-600.0)
        assert not allowed
        assert 'Daily loss limit' in reason

    def test_positive_input_normalised_to_negative(self):
        """User entering 500 (without minus) must behave identically to -500."""
        rm = _rm(max_daily_loss=500)
        assert rm.max_daily_loss == -500.0

    def test_unrealized_loss_trips_breaker(self):
        # realized -400, unrealized -150 → total -550 < -500 limit
        allowed, _ = _enter(_rm(-500), pnl=-400.0, unrealized=-150.0)
        assert not allowed

    def test_unrealized_gain_keeps_breaker_open(self):
        # realized -480, unrealized +100 → total -380 > -500 limit
        allowed, _ = _enter(_rm(-500), pnl=-480.0, unrealized=100.0)
        assert allowed

    def test_reason_includes_both_components(self):
        _, reason = _enter(_rm(-500), pnl=-300.0, unrealized=-250.0)
        assert 'realized' in reason.lower() or 'unrealized' in reason.lower()


# ── day slot cap ──────────────────────────────────────────────────────────────

class TestDaySlotCap:
    def test_blocks_when_at_cap(self):
        positions = {'a': _pos('day'), 'b': _pos('day'), 'c': _pos('day')}
        allowed, reason = _enter(_rm(max_day=3), positions=positions)
        assert not allowed
        assert 'Max day' in reason

    def test_allows_one_below_cap(self):
        positions = {'a': _pos('day'), 'b': _pos('day')}
        allowed, _ = _enter(_rm(max_day=3), positions=positions)
        assert allowed

    def test_exit_pending_excluded_from_count(self):
        # Two active + one pending exit → only 2 count → cap of 3 not reached
        positions = {
            'a': _pos('day'),
            'b': _pos('day'),
            'c': _pos('day', exit_pending=True),
        }
        allowed, _ = _enter(_rm(max_day=3), positions=positions)
        assert allowed

    def test_brown_day_counts_toward_day_cap(self):
        positions = {'a': _pos('day'), 'b': _pos('brown_day')}
        allowed, _ = _enter(_rm(max_day=2), positions=positions)
        assert not allowed

    def test_swing_positions_ignored_for_day_cap(self):
        positions = {'a': _pos('swing'), 'b': _pos('swing'), 'c': _pos('swing')}
        allowed, _ = _enter(_rm(max_day=1), positions=positions)
        assert allowed


# ── swing slot cap ────────────────────────────────────────────────────────────

class TestSwingSlotCap:
    def test_blocks_when_at_cap(self):
        positions = {'a': _pos('swing'), 'b': _pos('swing')}
        allowed, reason = _enter(_rm(max_swing=2), type_='swing', positions=positions)
        assert not allowed
        assert 'Max swing' in reason

    def test_allows_one_below_cap(self):
        positions = {'a': _pos('swing')}
        allowed, _ = _enter(_rm(max_swing=2), type_='swing', positions=positions)
        assert allowed

    def test_brown_swing_counts_toward_swing_cap(self):
        positions = {'a': _pos('brown_swing'), 'b': _pos('swing')}
        allowed, _ = _enter(_rm(max_swing=2), type_='swing', positions=positions)
        assert not allowed

    def test_day_positions_ignored_for_swing_cap(self):
        positions = {'a': _pos('day'), 'b': _pos('day'), 'c': _pos('day')}
        allowed, _ = _enter(_rm(max_swing=1), type_='swing', positions=positions)
        assert allowed

    def test_exit_pending_swing_excluded(self):
        positions = {
            'a': _pos('swing'),
            'b': _pos('swing', exit_pending=True),
        }
        allowed, _ = _enter(_rm(max_swing=2), type_='swing', positions=positions)
        assert allowed


# ── status snapshot ───────────────────────────────────────────────────────────

class TestStatus:
    def _status(self, rm, positions, pnl=0.0, unrealized=0.0):
        with patch.object(rm, '_get_daily_pnl', return_value=pnl):
            return rm.status(positions, unrealized_pnl=unrealized)

    def test_circuit_open_at_limit(self):
        s = self._status(_rm(-500), {}, pnl=-500.0)
        assert s['circuit_breaker_open'] is True

    def test_circuit_closed_above_limit(self):
        s = self._status(_rm(-500), {}, pnl=-499.0)
        assert s['circuit_breaker_open'] is False

    def test_day_count_excludes_pending_and_swing(self):
        positions = {
            'a': _pos('day'),
            'b': _pos('day', exit_pending=True),
            'c': _pos('swing'),
        }
        s = self._status(_rm(), positions)
        assert s['open_day'] == 1
        assert s['open_swing'] == 1

    def test_unrealized_included_in_daily_pnl(self):
        s = self._status(_rm(-500), {}, pnl=-300.0, unrealized=-150.0)
        assert s['daily_pnl'] == pytest.approx(-450.0)
        assert s['realized_pnl'] == pytest.approx(-300.0)
        assert s['unrealized_pnl'] == pytest.approx(-150.0)

    def test_config_values_reflected(self):
        s = self._status(_rm(max_day=5, max_swing=3), {})
        assert s['max_concurrent_day'] == 5
        assert s['max_concurrent_swing'] == 3
        assert s['max_daily_loss'] == -500.0
