"""
Unit tests for database.py

Covers: BrownBot config round-trip (create, update, per-user isolation,
        default fallback, boolean coercion) and get_brown_daily_realized_pnl
        (sum, date filter, open-position exclusion).

Uses a fresh temporary SQLite file per test so production data is never touched.
"""
import sys, os, tempfile, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from database import DatabaseManager


# ── temp DB fixture ───────────────────────────────────────────────────────────

class _TempDB(DatabaseManager):
    """DatabaseManager that initialises against a throwaway temp file."""
    def __init__(self, path):
        self.db_file = path
        self.init_database()


@pytest.fixture
def db(tmp_path):
    inst = _TempDB(str(tmp_path / 'test.db'))
    yield inst


# ── helpers ───────────────────────────────────────────────────────────────────

def _insert_brown_position(db, trade_date, realized_pnl, status='closed', user_id=1):
    """Insert a minimal brown_positions row for P&L tests."""
    pos_id = str(uuid.uuid4())
    with db.get_connection() as conn:
        conn.execute(
            '''INSERT INTO brown_positions
               (position_id, symbol, position_type, entry_price, quantity,
                entry_time, status, trade_date, realized_pnl, user_id)
               VALUES (?, 'NVDA', 'day', 100.0, 10, '2026-05-25T09:35:00', ?, ?, ?, ?)''',
            (pos_id, status, trade_date, realized_pnl, user_id)
        )
        conn.commit()


# ── BrownBot config ───────────────────────────────────────────────────────────

class TestBrownBotConfig:

    def test_defaults_when_no_row(self, db):
        cfg = db.get_brown_bot_config(user_id=99)
        assert cfg['day_eod_exit_time'] == '15:55'
        assert cfg['min_gap_pct'] == 25.0
        assert cfg['min_volume_m'] == 10.0
        assert cfg['min_price'] == 1.0
        assert cfg['max_price'] == 50.0
        assert cfg['day_ai_playbook'] is False
        assert cfg['swing_check_above_sma20'] is True
        assert cfg['swing_check_ma_cross'] is True
        assert cfg['max_concurrent_day'] == 5
        assert cfg['max_concurrent_swing'] == 3
        assert cfg['float_operator'] == '>='
        assert cfg['max_float_m'] == 5.0

    def test_create_row_and_read_back(self, db):
        ok, _ = db.update_brown_bot_config(
            {'day_eod_exit_time': '15:30', 'min_gap_pct': 8.0}, user_id=1
        )
        assert ok
        cfg = db.get_brown_bot_config(user_id=1)
        assert cfg['day_eod_exit_time'] == '15:30'
        assert cfg['min_gap_pct'] == 8.0

    def test_update_existing_row(self, db):
        db.update_brown_bot_config({'min_gap_pct': 10.0}, user_id=1)
        db.update_brown_bot_config({'min_gap_pct': 30.0}, user_id=1)
        assert db.get_brown_bot_config(user_id=1)['min_gap_pct'] == 30.0

    def test_partial_update_leaves_other_fields(self, db):
        db.update_brown_bot_config({'min_gap_pct': 20.0, 'min_price': 2.0}, user_id=1)
        db.update_brown_bot_config({'min_gap_pct': 35.0}, user_id=1)
        cfg = db.get_brown_bot_config(user_id=1)
        assert cfg['min_gap_pct'] == 35.0
        assert cfg['min_price'] == 2.0   # untouched by second update

    def test_users_are_isolated(self, db):
        db.update_brown_bot_config({'min_gap_pct': 10.0}, user_id=1)
        db.update_brown_bot_config({'min_gap_pct': 50.0}, user_id=2)
        assert db.get_brown_bot_config(user_id=1)['min_gap_pct'] == 10.0
        assert db.get_brown_bot_config(user_id=2)['min_gap_pct'] == 50.0

    def test_unset_fields_fall_back_to_defaults(self, db):
        # Write only one field — everything else should come from defaults dict
        db.update_brown_bot_config({'min_gap_pct': 99.0}, user_id=1)
        cfg = db.get_brown_bot_config(user_id=1)
        assert cfg['day_eod_exit_time'] == '15:55'

    def test_boolean_true_round_trips(self, db):
        db.update_brown_bot_config({'day_ai_playbook': True}, user_id=1)
        assert db.get_brown_bot_config(user_id=1)['day_ai_playbook'] is True

    def test_boolean_false_round_trips(self, db):
        db.update_brown_bot_config({'swing_check_above_sma20': False}, user_id=1)
        assert db.get_brown_bot_config(user_id=1)['swing_check_above_sma20'] is False

    def test_unknown_field_silently_ignored(self, db):
        ok, _ = db.update_brown_bot_config({'nonexistent_field': 999}, user_id=1)
        assert ok  # should not crash


# ── get_brown_daily_realized_pnl ──────────────────────────────────────────────

class TestBrownDailyRealizedPnL:

    def test_zero_when_no_trades(self, db):
        assert db.get_brown_daily_realized_pnl('2026-05-25') == 0.0

    def test_sums_multiple_closed_positions(self, db):
        _insert_brown_position(db, '2026-05-25', 150.0)
        _insert_brown_position(db, '2026-05-25', -50.0)
        assert db.get_brown_daily_realized_pnl('2026-05-25') == pytest.approx(100.0)

    def test_excludes_open_positions(self, db):
        _insert_brown_position(db, '2026-05-25', 200.0, status='open')
        assert db.get_brown_daily_realized_pnl('2026-05-25') == 0.0

    def test_filters_by_date(self, db):
        _insert_brown_position(db, '2026-05-24', 500.0)
        _insert_brown_position(db, '2026-05-25', 100.0)
        assert db.get_brown_daily_realized_pnl('2026-05-25') == pytest.approx(100.0)

    def test_no_date_sums_all_closed(self, db):
        _insert_brown_position(db, '2026-05-24', 200.0)
        _insert_brown_position(db, '2026-05-25', 300.0)
        assert db.get_brown_daily_realized_pnl() == pytest.approx(500.0)

    def test_negative_pnl_day(self, db):
        _insert_brown_position(db, '2026-05-25', -300.0)
        _insert_brown_position(db, '2026-05-25', -200.0)
        assert db.get_brown_daily_realized_pnl('2026-05-25') == pytest.approx(-500.0)

    def test_returns_float(self, db):
        _insert_brown_position(db, '2026-05-25', 42.0)
        result = db.get_brown_daily_realized_pnl('2026-05-25')
        assert isinstance(result, float)
