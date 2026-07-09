"""
Backtest engine for gap-up strategy — Day Trade and Swing Trade modes.

Day backtest
  Candidates : gap_data filtered by min_gap, price, volume
  Entry      : first 1-min bar at-or-after entry_start_time that passes all
               configured signals (VWAP, candle, extension, volume surge)
  Exit       : stop / target / EOD cutoff on subsequent 1-min bars
  Fallback   : daily OHLC from gap_data when no 1-min bars exist

Swing backtest
  Candidates : gap_data cross-filtered by market cap (Polygon reference API,
               cached in ticker_metadata table with 7-day TTL)
  Entry      : today_close of gap day (confirming the move before buying)
  Exit       : walk daily bars from Polygon — stop / target / max hold days
  Data       : Polygon /v2/aggs/1/day fetched on demand, cached per ticker

Timestamp handling (UTC vs naive ET):
  Bars stored with '+00:00' → UTC.  ET cutoffs are converted to UTC before
  comparison so the hot inner loop does only string comparison.
  Bars stored without tz suffix → assumed ET (Polygon naive format).
"""
from __future__ import annotations

import os
import math
import time
import sqlite3
from datetime import datetime, date, timedelta
from typing import Any, Optional

import pytz
import requests

ET = pytz.timezone('US/Eastern')

DB_PATH = os.getenv('DATABASE_PATH') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'trading_advisor.db'
)
OHLCV_DB_PATH = os.getenv('OHLCV_DB_PATH') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'ohlcv_1m.db'
)

POLYGON_KEY = os.getenv('POLYGON_API_KEY', '')


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _ohlcv_conn() -> sqlite3.Connection:
    c = sqlite3.connect(OHLCV_DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


# ── Market cap cache ───────────────────────────────────────────────────────────

TICKER_META_REFRESH_DAYS = 7


def _ensure_ticker_metadata_table():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticker_metadata (
                ticker       TEXT PRIMARY KEY,
                market_cap_m REAL,
                fetched_at   TEXT NOT NULL
            )
        """)
        conn.commit()


def _fetch_polygon_market_cap(ticker: str) -> Optional[float]:
    """Return market cap in millions from Polygon reference API, or None."""
    url = (
        f"https://api.polygon.io/v3/reference/tickers/{ticker.upper()}"
        f"?apiKey={POLYGON_KEY}"
    )
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            cap = resp.json().get('results', {}).get('market_cap')
            if cap:
                return round(cap / 1e6, 2)
    except Exception:
        pass
    return None


def _load_cached_market_caps(tickers: list[str]) -> dict[str, Optional[float]]:
    """Load market caps from ticker_metadata that are still within TTL."""
    if not tickers:
        return {}
    cutoff = (date.today() - timedelta(days=TICKER_META_REFRESH_DAYS)).isoformat()
    upper = [t.upper() for t in tickers]
    placeholders = ','.join('?' * len(upper))
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT ticker, market_cap_m FROM ticker_metadata "
            f"WHERE ticker IN ({placeholders}) AND fetched_at >= ?",
            upper + [cutoff]
        ).fetchall()
    return {r['ticker']: r['market_cap_m'] for r in rows}


def _upsert_market_cap(ticker: str, cap_m: Optional[float]):
    today = date.today().isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO ticker_metadata (ticker, market_cap_m, fetched_at) "
            "VALUES (?, ?, ?)",
            (ticker.upper(), cap_m, today)
        )
        conn.commit()


def fetch_and_cache_market_caps(
    tickers: list[str],
    progress_cb=None,
) -> dict[str, Optional[float]]:
    """
    Return {TICKER: market_cap_m} for every ticker in the list.
    Reads from the ticker_metadata cache first; fetches missing/stale entries
    from Polygon one at a time (≈150 ms apart to respect rate limits).
    progress_cb(fetched, total) is called after each Polygon fetch if provided.
    """
    _ensure_ticker_metadata_table()
    upper_tickers = [t.upper() for t in tickers]

    result = _load_cached_market_caps(upper_tickers)

    to_fetch = [t for t in upper_tickers if t not in result]

    for i, ticker in enumerate(to_fetch):
        cap_m = _fetch_polygon_market_cap(ticker)
        _upsert_market_cap(ticker, cap_m)
        result[ticker] = cap_m
        if progress_cb:
            progress_cb(i + 1, len(to_fetch))
        time.sleep(0.15)

    return result


# ── Timestamp helpers ──────────────────────────────────────────────────────────

_cutoff_cache: dict[tuple, str] = {}


def _et_hhmm_to_comparable(hhmm_et: str, day_str: str, is_utc: bool) -> str:
    """Convert ET 'HH:MM' to the storage format for bar timestamps."""
    if not is_utc:
        return hhmm_et
    key = (day_str, hhmm_et)
    if key in _cutoff_cache:
        return _cutoff_cache[key]
    h, m = map(int, hhmm_et.split(':'))
    naive = datetime.strptime(day_str, '%Y-%m-%d').replace(hour=h, minute=m)
    utc_hhmm = ET.localize(naive).astimezone(pytz.UTC).strftime('%H:%M')
    _cutoff_cache[key] = utc_hhmm
    return utc_hhmm


def _ts_is_utc(ts_str: str) -> bool:
    return '+' in ts_str or ts_str.endswith('Z')


# ── Info endpoint ──────────────────────────────────────────────────────────────

def get_backtest_info() -> dict:
    min_date = max_date = None
    total = distinct_days = distinct_tickers = 0

    try:
        with _conn() as conn:
            row = conn.execute(
                "SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(*) as total "
                "FROM gap_data"
            ).fetchone()
            min_date        = row['min_date']
            max_date        = row['max_date']
            total           = row['total'] or 0
            distinct_days   = conn.execute(
                "SELECT COUNT(DISTINCT date) FROM gap_data"
            ).fetchone()[0] or 0
            distinct_tickers = conn.execute(
                "SELECT COUNT(DISTINCT ticker) FROM gap_data"
            ).fetchone()[0] or 0
    except Exception:
        pass  # gap_data table not yet populated on this instance

    ohlcv_rows = ohlcv_days = 0
    if os.path.exists(OHLCV_DB_PATH):
        try:
            with _ohlcv_conn() as oc:
                ohlcv_rows = oc.execute("SELECT COUNT(*) FROM ohlcv_1m").fetchone()[0]
                ohlcv_days = oc.execute("SELECT COUNT(DISTINCT day) FROM ohlcv_1m").fetchone()[0]
        except Exception:
            pass

    return {
        'min_date':          min_date,
        'max_date':          max_date,
        'total_candidates':  total,
        'distinct_days':     distinct_days,
        'distinct_tickers':  distinct_tickers,
        'ohlcv_1m_rows':     ohlcv_rows,
        'ohlcv_1m_days':     ohlcv_days,
    }


# ── Public router ──────────────────────────────────────────────────────────────

def run_backtest(cfg: dict) -> dict:
    if cfg.get('trade_type') == 'swing':
        return run_swing_backtest(cfg)
    return run_day_backtest(cfg)


# ══════════════════════════════════════════════════════════════════════════════
# DAY TRADE BACKTEST
# ══════════════════════════════════════════════════════════════════════════════

def run_day_backtest(cfg: dict) -> dict:
    """
    cfg keys:
      start_date, end_date, initial_capital
      position_size_pct    % of capital per trade
      stop_loss_pct        % below entry
      profit_target_pct    % above entry
      min_gap_pct, min_price, max_price, min_volume_m, max_float_m
      entry_start_time     HH:MM ET — earliest bar to consider (default '09:35')
      entry_end_time       HH:MM ET — latest bar to enter; skip if not entered by then (default '10:30')
      eod_exit_time        HH:MM ET — flatten at or after this time (default '15:55')
      day_check_vwap       bool — bar close must be above session VWAP
      day_check_candle     bool — bar must be bullish (close >= open)
      day_max_extension_pct float — bar close must be <= this % above today_open (0 = disabled)
      day_check_volume_surge bool — bar volume >= 1.5x recent average
    """
    start       = cfg.get('start_date')
    end         = cfg.get('end_date')
    capital     = float(cfg.get('initial_capital', 100_000))
    pos_pct     = float(cfg.get('position_size_pct', 10))
    sl_pct      = float(cfg.get('stop_loss_pct', 2))
    tgt_pct     = float(cfg.get('profit_target_pct', 4))
    min_gap     = float(cfg.get('min_gap_pct', 5))
    min_price   = float(cfg.get('min_price', 1))
    max_price   = float(cfg.get('max_price', 9999))
    min_vol     = float(cfg.get('min_volume_m', 0))
    max_float   = float(cfg.get('max_float_m', 0))
    entry_start = cfg.get('entry_start_time', '09:35')
    entry_end   = cfg.get('entry_end_time',   '10:30')
    eod_et      = cfg.get('eod_exit_time',    '15:55')
    # Entry signals — mirror the live BrownBot _check_day_entry_signal():
    # OR'd breakout triggers (PMHB / DHB / ORB) + AND'd condition gates
    # (VWAP / candle / volume surge / extension-from-open / max % below day high).
    # Keep this dict in sync with brown_bot_config day_* fields.
    sig = {
        'pmh_on':    bool(cfg.get('day_check_pmh', False)),
        'dhb_on':    bool(cfg.get('day_check_dayhigh_break', False)),
        'orb_on':    bool(cfg.get('day_check_orb', False)),
        'orb_min':   int(cfg.get('day_orb_minutes', 15) or 15),
        'buf':       float(cfg.get('day_pmh_break_buffer_pct', 0.2)),
        'vol_mult':  float(cfg.get('day_pmh_vol_mult', 1.5)),
        'max_wick':  float(cfg.get('day_pmh_max_wick_pct', 60.0)),
        'accept_n':  int(cfg.get('day_pmh_acceptance_bars', 0) or 0),
        'chk_vwap':  bool(cfg.get('day_check_vwap', False)),
        'chk_candle':bool(cfg.get('day_check_candle', False)),
        'chk_surge': bool(cfg.get('day_check_volume_surge', False)),
        'max_ext':   float(cfg.get('day_max_extension_pct', 0)),
        'max_below': float(cfg.get('day_max_below_dayhigh_pct', 0)),
        # Dynamic stops (mirror live exit loop)
        'breakeven_on':  bool(cfg.get('day_breakeven_enabled', False)),
        'be_trigger':    float(cfg.get('day_breakeven_trigger_pct', 50.0)),
        'trailing_on':   bool(cfg.get('day_trailing_stop_enabled', False)),
        'trailing_pct':  float(cfg.get('day_trailing_stop_pct', 1.5)),
        # Max total entries per symbol per day (1 = no re-entry). Mirrors the live
        # day_max_reentry cap: after a position exits, re-scan for another entry.
        'max_reentry':   int(cfg.get('day_max_reentry', 1) or 1),
        # ── SHORT setups (RedBot) — OR triggers + AND conditions, mirroring the
        # long side's structure but for fading gap-ups. Only used when
        # direction='short'. All off by default.
        'sr_reject':     bool(cfg.get('short_pmh_reject', False)),      # failed PMH breakout (gap fade)
        'sr_vwap_loss':  bool(cfg.get('short_vwap_loss', False)),       # lost VWAP after holding it
        'sr_lower_high': bool(cfg.get('short_lower_high', False)),      # rolling over (breaks recent low w/ lower high)
        'sc_below_vwap': bool(cfg.get('short_below_vwap', False)),      # AND: price under VWAP
        'sc_bearish':    bool(cfg.get('short_bearish_candle', False)),  # AND: red 1-min bar
        'sc_surge':      bool(cfg.get('short_volume_surge', False)),    # AND: breakdown bar ≥1.5× avg vol
        'sc_min_ext':    float(cfg.get('short_min_ext_pct', 0)),        # AND: ≥X% above VWAP ("extended")
    }

    # Portfolio realism (mirror live constraints + real-world frictions).
    max_concurrent = int(cfg.get('max_concurrent_day', 5) or 5)
    slippage_pct   = float(cfg.get('day_slippage_pct', 0.1))     # per side (%)
    commission     = float(cfg.get('commission_per_trade', 0.0)) # $ per round-trip
    # Margin realism: you cannot deploy more than (equity × margin_factor) at once.
    #   1.0 = cash account · 2.0 = Reg-T overnight · 4.0 = PDT intraday buying power.
    # position_size_pct × max_concurrent can exceed this; excess entries are skipped
    # for lack of buying power (exposure_capped), exactly as a real broker would reject.
    margin_factor  = float(cfg.get('margin_factor', 1.0) or 1.0)
    # Trade direction: 'long' (BrownBot) or 'short' (RedBot experiment — fade the
    # exact same breakout entries). Short flips stop/target and P&L sign.
    _direction     = str(cfg.get('direction', 'long')).lower()

    # No trigger enabled → no entries (matches live). Return an explicit note
    # instead of a silently-empty run. Short uses its own trigger set.
    _long_trig  = sig['pmh_on'] or sig['dhb_on'] or sig['orb_on']
    _short_trig = sig['sr_reject'] or sig['sr_vwap_loss'] or sig['sr_lower_high']
    if (_direction == 'short' and not _short_trig) or (_direction != 'short' and not _long_trig):
        _msg = ('No short trigger enabled — enable Failed-PMH / VWAP-loss / Roll-over.'
                if _direction == 'short'
                else 'No entry trigger enabled — enable PMHB, ORB, or DHB to run a day backtest.')
        return {
            'summary': _calc_summary([], capital, capital, 0.0, []),
            'trades': [], 'equity_curve': [{'date': start, 'equity': capital}],
            'note': _msg,
        }

    candidates = _fetch_candidates(start, end, min_gap, min_price, max_price, min_vol, max_float,
                                   cfg.get('float_operator', '<='))

    use_1m  = os.path.exists(OHLCV_DB_PATH)
    ohlcv_c = _ohlcv_conn() if use_1m else None

    # ── 1) Simulate every candidate on 1-min bars → raw outcomes with times ──
    # Triggers can only be evaluated with intraday bars, so days without 1-min
    # data are skipped (no OHLC fallback — it can't confirm a trigger).
    from collections import defaultdict
    raw_by_date: dict = defaultdict(list)
    no_entry_count = 0
    no_bars_count  = 0

    if not ohlcv_c:
        return {
            'summary': _calc_summary([], capital, capital, 0.0, []),
            'trades': [], 'equity_curve': [{'date': start, 'equity': capital}],
            'note': 'No 1-min bar data on this instance — day-trigger backtests need the ohlcv_1m cache.',
        }

    for row in candidates:
        ticker = row['ticker']; trade_date = row['date']
        if float(row['today_open'] or 0) <= 0:
            continue
        if _direction == 'short':
            sim = _simulate_short_day_1m(ohlcv_c, ticker, trade_date, sl_pct, tgt_pct,
                                         entry_start, entry_end, eod_et,
                                         float(row['today_open'] or 0), sig)
        else:
            sim = _simulate_day_trade_1m(ohlcv_c, ticker, trade_date, sl_pct, tgt_pct,
                                         entry_start, entry_end, eod_et,
                                         float(row['today_open'] or 0), sig)
        if sim is False:
            no_bars_count += 1;  continue     # no 1-min bars → can't confirm a trigger
        if not sim:
            no_entry_count += 1; continue     # had bars, no confirmed entry
        gp = round(float(row['gap_percentage'] or 0), 2)
        for t in sim:                          # 1+ trades (initial + re-entries)
            if t['entry'] <= 0:
                continue
            t['ticker']  = ticker
            t['gap_pct'] = gp
            raw_by_date[trade_date].append(t)

    ohlcv_c.close()

    # ── 2) Portfolio walk: day-level compounding + concurrency cap + slippage ──
    trades        = []
    equity        = capital
    equity_curve  = [{'date': start, 'equity': round(equity, 2)}]
    peak_equity   = capital
    max_dd        = 0.0
    daily_returns: list[float] = []
    skipped_slot  = 0
    skipped_expo  = 0
    max_gross_pct = 0.0   # peak simultaneous deployment seen (as % of equity)

    for d in sorted(raw_by_date.keys()):
        day_trades = sorted(raw_by_date[d], key=lambda t: t.get('entry_ts') or '')
        day_start_equity = equity
        # Each open position tracked as (exit_ts, trade_value, worst_case_loss$) so we
        # can enforce the buying-power cap and mark unrealized intraday heat.
        open_pos: list = []
        day_pnl = 0.0
        buying_power = day_start_equity * margin_factor
        day_intraday_low = day_start_equity   # lowest mark-to-worst equity intraday

        for t in day_trades:
            ets = t.get('entry_ts') or ''
            xts = t.get('exit_ts') or ''
            # Free capital/slots for positions that already closed by this entry time.
            open_pos = [p for p in open_pos if p[0] > ets]
            if len(open_pos) >= max_concurrent:
                skipped_slot += 1
                continue

            entry = t['entry']
            trade_value = day_start_equity * (pos_pct / 100)
            # Buying-power cap: sum of open deployment + this trade must fit margin.
            deployed = sum(p[1] for p in open_pos)
            if deployed + trade_value > buying_power + 1e-6:
                skipped_expo += 1
                continue
            shares = math.floor(trade_value / entry)
            if shares < 1:
                continue
            # Slippage & P&L by direction. Long: buy up on entry, sell down on
            # exit. Short: sell down on entry (fill lower), buy up on cover (fill
            # higher), and P&L is (entry - exit). Slippage always hurts.
            if _direction == 'short':
                fill_entry = entry * (1 - slippage_pct / 100)
                fill_exit  = t['exit'] * (1 + slippage_pct / 100)
                pnl     = round((fill_entry - fill_exit) * shares - commission, 2)
                pnl_pct = round((fill_entry - fill_exit) / fill_entry * 100, 3) if fill_entry else 0
            else:
                fill_entry = entry * (1 + slippage_pct / 100)
                fill_exit  = t['exit'] * (1 - slippage_pct / 100)
                pnl     = round((fill_exit - fill_entry) * shares - commission, 2)
                pnl_pct = round((fill_exit - fill_entry) / fill_entry * 100, 3) if fill_entry else 0
            day_pnl += pnl

            # Track this position as open for buying-power + intraday-heat modelling.
            # Worst case = position runs to its stop (mark-to-worst) incl. slippage.
            worst_loss = shares * fill_entry * (sl_pct / 100) + commission
            open_pos.append((xts, trade_value, worst_loss))
            # Intraday heat: realized-so-far minus every still-open position's worst case.
            # (day_pnl already includes this trade's *final* pnl, so back it out and
            #  substitute its worst case to avoid double counting the winners.)
            realized_prior = day_pnl - pnl
            unreal_worst   = sum(p[2] for p in open_pos)
            mark = day_start_equity + realized_prior - unreal_worst
            if mark < day_intraday_low:
                day_intraday_low = mark
            gross = sum(p[1] for p in open_pos)
            if day_start_equity > 0:
                gp = gross / day_start_equity * 100
                if gp > max_gross_pct:
                    max_gross_pct = gp

            trades.append({
                'date':         d,
                'ticker':       t['ticker'],
                'gap_pct':      t['gap_pct'],
                'entry':        round(entry, 4),
                'exit':         round(t['exit'], 4),
                'shares':       shares,
                'stop':         round(entry * (1 - sl_pct / 100), 4),
                'target':       round(entry * (1 + tgt_pct / 100), 4),
                'pnl':          pnl,
                'pnl_pct':      pnl_pct,
                'trigger':      t.get('trigger'),
                'exit_reason':  t['reason'],
                'entry_ts':     t.get('entry_ts'),
                'equity_after': round(day_start_equity + day_pnl, 2),
            })

        equity += day_pnl
        if equity > peak_equity:
            peak_equity = equity
        # Drawdown against BOTH the end-of-day equity and the worst intraday mark
        # (positions marked to their stops), so 250%-gross days show real heat.
        if peak_equity > 0:
            low_equity = min(equity, day_intraday_low)
            dd = (peak_equity - low_equity) / peak_equity * 100
            if dd > max_dd:
                max_dd = dd
        daily_returns.append(day_pnl / day_start_equity if day_start_equity else 0)
        equity_curve.append({'date': d, 'equity': round(equity, 2)})

    equity_curve.append({'date': end, 'equity': round(equity, 2)})

    summary = _calc_summary(trades, capital, equity, max_dd, daily_returns)
    # Per-entry-trigger and per-exit-reason breakdowns (like the Stats tab).
    summary['by_trigger']     = _perf_breakdown(trades, 'trigger')
    summary['by_exit_reason'] = _perf_breakdown(trades, 'exit_reason')
    summary['segments']       = _segment_report(trades)
    summary['skipped_slot_cap'] = skipped_slot
    summary['skipped_exposure'] = skipped_expo
    summary['peak_gross_pct']   = round(max_gross_pct, 1)
    summary['margin_factor']    = margin_factor
    summary['no_entry']        = no_entry_count
    summary['no_bars']         = no_bars_count

    return {'summary': summary, 'trades': trades, 'equity_curve': equity_curve}


def _perf_breakdown(trades: list, key: str) -> list:
    """Aggregate trades by a key ('trigger' | 'exit_reason'): count, win-rate, P&L."""
    agg: dict = {}
    for t in trades:
        k = t.get(key) or 'UNKNOWN'
        a = agg.setdefault(k, {'name': k, 'trades': 0, 'wins': 0, 'pnl': 0.0})
        a['trades'] += 1
        a['wins']   += 1 if t.get('pnl', 0) > 0 else 0
        a['pnl']    += t.get('pnl', 0)
    out = [{
        'name': a['name'], 'trades': a['trades'], 'wins': a['wins'],
        'win_rate': round(a['wins'] / a['trades'] * 100, 1) if a['trades'] else 0.0,
        'total_pnl': round(a['pnl'], 2),
        'avg_pnl': round(a['pnl'] / a['trades'], 2) if a['trades'] else 0.0,
    } for a in agg.values()]
    out.sort(key=lambda x: x['trades'], reverse=True)
    return out


def _seg_stats(trades: list, keyfn) -> list:
    """Group trades by keyfn → trades, win-rate, total/avg P&L, and profit factor."""
    agg: dict = {}
    for t in trades:
        k = keyfn(t)
        if k is None:
            continue
        a = agg.setdefault(k, {'segment': k, 'trades': 0, 'wins': 0,
                               'gp': 0.0, 'gl': 0.0, 'pnl': 0.0})
        p = t.get('pnl', 0)
        a['trades'] += 1
        a['pnl'] += p
        if p > 0:
            a['wins'] += 1; a['gp'] += p
        else:
            a['gl'] += abs(p)
    out = []
    for a in agg.values():
        n = a['trades']
        out.append({
            'segment': a['segment'], 'trades': n, 'wins': a['wins'],
            'win_rate': round(a['wins'] / n * 100, 1) if n else 0.0,
            'total_pnl': round(a['pnl'], 2),
            'avg_pnl': round(a['pnl'] / n, 2) if n else 0.0,
            'profit_factor': round(a['gp'] / a['gl'], 2) if a['gl'] > 0 else (999.0 if a['gp'] > 0 else 0.0),
        })
    return out


def _segment_report(trades: list) -> dict:
    """Break trades into sub-populations so we can see WHERE the edge lives."""
    def gap_bucket(t):
        g = t.get('gap_pct', 0) or 0
        return '10-20%' if g < 20 else '20-30%' if g < 30 else '30-50%' if g < 50 else '50%+'

    def price_bucket(t):
        p = t.get('entry', 0) or 0
        return '$1-5' if p < 5 else '$5-10' if p < 10 else '$10-20' if p < 20 else '$20-50' if p < 50 else '$50+'

    def hour_bucket(t):
        ets = t.get('entry_ts')
        if not ets:
            return None
        try:
            d = datetime.fromisoformat(str(ets).replace('Z', '+00:00')).astimezone(ET)
        except Exception:
            return None
        m = d.hour * 60 + d.minute
        return ('09:30-10:00' if m < 600 else '10:00-10:30' if m < 630 else
                '10:30-11:00' if m < 660 else '11:00-12:00' if m < 720 else '12:00+')

    _DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    def dow_bucket(t):
        try:
            return _DOW[date.fromisoformat(t['date']).weekday()]
        except Exception:
            return None

    def _ordered(rows, order):
        idx = {v: i for i, v in enumerate(order)}
        return sorted(rows, key=lambda r: idx.get(r['segment'], 99))

    return {
        'by_gap':   _ordered(_seg_stats(trades, gap_bucket), ['10-20%', '20-30%', '30-50%', '50%+']),
        'by_price': _ordered(_seg_stats(trades, price_bucket), ['$1-5', '$5-10', '$10-20', '$20-50', '$50+']),
        'by_hour':  _ordered(_seg_stats(trades, hour_bucket), ['09:30-10:00', '10:00-10:30', '10:30-11:00', '11:00-12:00', '12:00+']),
        'by_dow':   _ordered(_seg_stats(trades, dow_bucket), _DOW),
    }


def _add_min(hhmm: str, mins: int) -> str:
    from datetime import datetime as _d, timedelta as _td
    return (_d.strptime(hhmm, '%H:%M') + _td(minutes=mins)).strftime('%H:%M')


def _confirm_breakout_bt(level, session_bars, cur_close, buf, vol_mult, max_wick, accept_n) -> bool:
    """
    Backtest port of the live _confirm_breakout(): session_bars[-1] is the
    breakout candle, cur_close ≈ current price. Keep in sync with app.py.
    """
    if not level or level <= 0 or not session_bars:
        return False
    threshold = level * (1 + buf / 100.0)
    last = session_bars[-1]
    if cur_close <= level:            # price must still hold above the level
        return False
    if last['c'] <= threshold:        # candle must close above level + buffer
        return False
    if vol_mult > 0 and len(session_bars) >= 3:
        avg = sum(b['v'] for b in session_bars[:-1]) / (len(session_bars) - 1)
        if not (avg > 0 and last['v'] >= avg * vol_mult):
            return False
    if 0 < max_wick < 100:
        rng = last['h'] - last['l']
        up  = last['h'] - max(last['o'], last['c'])
        if ((up / rng * 100) if rng > 0 else 0.0) > max_wick:
            return False
    if accept_n >= 2:
        if len(session_bars) < accept_n:
            return False
        if not all(b['c'] > level for b in session_bars[-accept_n:]):
            return False
    return True


def _simulate_day_trade_1m(
    conn: sqlite3.Connection,
    ticker: str,
    day: str,
    sl_pct: float,
    tgt_pct: float,
    entry_start_et: str,
    entry_end_et: str,
    eod_et: str,
    gap_open: float,
    sig: dict,
    direction: str = 'long',
) -> 'Optional[tuple[float, float, str]] | bool':
    """
    Mirror of the live BrownBot _check_day_entry_signal(): walk 1-min bars,
    and at each bar in [entry_start, entry_end] require ALL enabled condition
    gates to pass AND (if any breakout trigger is enabled) at least one trigger
    to confirm. Enter at the first qualifying bar's open, then simulate exit.

    Triggers (OR): PMHB (pre-market-high break), ORB (opening-range break),
    DHB (day-high break) — each via _confirm_breakout_bt.
    Conditions (AND): VWAP, bullish candle, volume surge, extension-from-open,
    max % below day high.

    Note: PMHB needs pre-market (04:00–09:30 ET) bars for that day; where the
    1-min cache lacks them, pm_high stays 0 and PMHB simply never fires for that
    day (honest — the break can't be confirmed without the level).

    Returns: (entry, exit, reason) | None (had bars, no entry) | False (no bars).
    """
    bars = conn.execute(
        "SELECT ts, open, high, low, close, volume FROM ohlcv_1m "
        "WHERE ticker=? AND day=? ORDER BY ts ASC",
        (ticker, day)
    ).fetchall()
    if not bars:
        return False  # sentinel: no 1-min data → caller should use OHLC fallback

    is_utc = _ts_is_utc(bars[0]['ts'])
    entry_start_cmp = _et_hhmm_to_comparable(entry_start_et, day, is_utc)
    entry_end_cmp   = _et_hhmm_to_comparable(entry_end_et,   day, is_utc)
    eod_cmp         = _et_hhmm_to_comparable(eod_et,         day, is_utc)
    pm_start_cmp    = _et_hhmm_to_comparable('04:00', day, is_utc)
    open_cmp        = _et_hhmm_to_comparable('09:30', day, is_utc)
    orb_end_cmp     = _et_hhmm_to_comparable(_add_min('09:30', sig['orb_min']), day, is_utc)

    pmh_on, dhb_on, orb_on = sig['pmh_on'], sig['dhb_on'], sig['orb_on']
    buf, vol_mult, max_wick, accept_n = sig['buf'], sig['vol_mult'], sig['max_wick'], sig['accept_n']
    chk_vwap, chk_candle, chk_surge = sig['chk_vwap'], sig['chk_candle'], sig['chk_surge']
    max_ext, max_below = sig['max_ext'], sig['max_below']
    breakeven_on, be_trigger = sig['breakeven_on'], sig['be_trigger']
    trailing_on, trailing_pct = sig['trailing_on'], sig['trailing_pct']
    _short = (direction == 'short')
    if _short:
        # Short mode fades the SAME breakout entries with a fixed stop/target
        # only (dynamic breakeven/trailing are long-oriented and disabled here).
        breakeven_on = trailing_on = False
    any_trigger = pmh_on or dhb_on or orb_on
    if not any_trigger:
        return []   # a breakout trigger is required to enter (mirrors live)

    max_entries = max(1, int(sig.get('max_reentry', 1)))  # total entries/symbol/day

    trades_out: list = []     # completed trades (initial + re-entries)
    entry = None
    entry_ts = None
    trigger_tag = None
    stop = target = 0.0
    hi_water = 0.0
    at_be = False
    in_position = False
    pm_high = session_open = orb_high = day_high = 0.0
    vwap_num = vwap_den = 0.0
    session_bars: list = []   # {o,h,l,c,v} for bars ≥ 09:30 ET

    for bar in bars:
        hhmm = bar['ts'][11:16]
        o = float(bar['open'] or 0);  h = float(bar['high'] or 0)
        l = float(bar['low'] or 0);   c = float(bar['close'] or 0)
        v = float(bar['volume'] or 0)

        if not in_position:
            # Pre-market (04:00–09:30 ET): accumulate the pre-market high.
            if hhmm < open_cmp:
                if hhmm >= pm_start_cmp and h > pm_high:
                    pm_high = h
                continue

            # Regular-session bar (≥ 09:30): update session state.
            if not session_open:
                session_open = o if o > 0 else c
            prior_high = day_high            # day high BEFORE this bar → DHB level
            session_bars.append({'o': o, 'h': h, 'l': l, 'c': c, 'v': v})
            if h > day_high:
                day_high = h
            if hhmm < orb_end_cmp and h > orb_high:
                orb_high = h
            tp = (h + l + c) / 3
            if v > 0:
                vwap_num += tp * v
                vwap_den += v
            session_vwap = vwap_num / vwap_den if vwap_den else 0

            # No more entries allowed (re-entry cap) and flat → done for the day.
            if len(trades_out) >= max_entries:
                break
            if hhmm < entry_start_cmp:
                continue
            if hhmm > entry_end_cmp:
                break  # entry window closed and flat — no more (re-)entries

            # ── Condition gates (AND) ──
            cond_ok = True
            if chk_vwap and session_vwap > 0 and c < session_vwap:
                cond_ok = False
            if cond_ok and chk_candle and c < o:
                cond_ok = False
            if cond_ok and max_ext > 0 and session_open > 0:
                if (c - session_open) / session_open * 100 > max_ext:
                    cond_ok = False
            if cond_ok and chk_surge:
                if len(session_bars) < 3:
                    cond_ok = False
                else:
                    avg = sum(b['v'] for b in session_bars[:-1]) / (len(session_bars) - 1)
                    if not (avg > 0 and v >= avg * 1.5):
                        cond_ok = False
            if cond_ok and max_below > 0 and day_high > 0:
                if (day_high - c) / day_high * 100 > max_below:
                    cond_ok = False

            # ── Breakout triggers (OR) — capture which fired (PMHB > ORB > DHB) ──
            pmh_fire = pmh_on and _confirm_breakout_bt(pm_high, session_bars, c, buf, vol_mult, max_wick, accept_n)
            orb_fire = orb_on and hhmm >= orb_end_cmp and _confirm_breakout_bt(orb_high, session_bars, c, buf, vol_mult, max_wick, accept_n)
            dhb_fire = dhb_on and _confirm_breakout_bt(prior_high, session_bars, c, buf, vol_mult, max_wick, accept_n)
            trig_ok = pmh_fire or orb_fire or dhb_fire

            if not (cond_ok and trig_ok):
                continue

            # Enter at the CONFIRMING bar's CLOSE (the signal is only known once
            # the bar closes) — not its open, which would be a 1-bar look-ahead.
            entry = c
            if entry <= 0:
                continue
            entry_ts = bar['ts']
            trigger_tag = 'PMHB' if pmh_fire else ('ORB' if orb_fire else 'DHB')
            if _short:
                # Short the SAME breakout entry: stop ABOVE, target BELOW.
                stop   = round(entry * (1 + sl_pct  / 100), 4)
                target = round(entry * (1 - tgt_pct / 100), 4)
            else:
                stop     = round(entry * (1 - sl_pct  / 100), 4)
                target   = round(entry * (1 + tgt_pct / 100), 4)
            hi_water = entry
            in_position = True
            continue  # exits are evaluated from the NEXT bar onward (no look-ahead)

        # In position — exit checks first, using the stop set from PRIOR bars'
        # high-water (avoids intrabar look-ahead), then ratchet for the next bar.
        exit_price = exit_reason = None
        if hhmm >= eod_cmp:
            exit_price, exit_reason = c, 'EOD Close'
        elif _short:
            # Short: stop is ABOVE (price rising hits it), target is BELOW.
            if h >= stop:
                exit_price, exit_reason = stop, 'Stop Loss'
            elif l <= target:
                exit_price, exit_reason = target, 'Target Hit'
        else:
            if l <= stop:
                exit_price, exit_reason = stop, 'Stop Loss'
            elif h >= target:
                exit_price, exit_reason = target, 'Target Hit'

        if exit_reason:
            trades_out.append({'entry': entry, 'exit': exit_price, 'reason': exit_reason,
                               'entry_ts': entry_ts, 'exit_ts': bar['ts'], 'trigger': trigger_tag})
            in_position = False
            entry = entry_ts = trigger_tag = None
            stop = target = hi_water = 0.0
            at_be = False
            if exit_reason == 'EOD Close':
                break  # end of day — no re-entries
            continue   # re-scan for a re-entry from the next bar (if cap allows)

        # Update high-water, then apply breakeven + trailing (mirror live).
        if h > hi_water:
            hi_water = h
        if breakeven_on and not at_be and target > entry:
            if (hi_water - entry) / (target - entry) * 100 >= be_trigger:
                if entry > stop:
                    stop = entry
                at_be = True
        if trailing_on and hi_water > 0:
            new_stop = round(hi_water * (1 - trailing_pct / 100), 4)
            if new_stop > stop:
                stop = new_stop

    # Position still open when bars ran out → close at the last bar.
    if in_position and bars:
        trades_out.append({'entry': entry, 'exit': float(bars[-1]['close'] or 0), 'reason': 'EOD Close',
                           'entry_ts': entry_ts, 'exit_ts': bars[-1]['ts'], 'trigger': trigger_tag})
    return trades_out


def _simulate_short_day_1m(conn, ticker, day, sl_pct, tgt_pct,
                           entry_start_et, entry_end_et, eod_et, gap_open, sig):
    """
    SHORT-side day simulation (RedBot). Fades gap-ups with short-specific
    entries — NOT the inverted long breakout. Structure mirrors the long sim:
    OR triggers + AND condition gates.

      OR triggers (≥1 must fire):
        sr_reject     — failed PMH breakout / gap fade: price poked ≥ pre-market
                        high earlier, now closes back below it (buffer-confirmed).
        sr_vwap_loss  — held above VWAP earlier, now closes below it.
        sr_lower_high — rolling over: prints a lower high vs the day high AND
                        breaks below the recent N-bar swing low.
      AND conditions (all enabled must pass):
        sc_below_vwap — close < VWAP        sc_bearish — red 1-min bar
        sc_surge      — breakdown bar ≥1.5× avg vol
        sc_min_ext    — price ≥ X% ABOVE VWAP ("extended", for the roll-over play)

    Enters short at the confirming bar CLOSE. Stop ABOVE (sl_pct), target BELOW
    (tgt_pct), EOD flat. Returns list of {entry,exit,reason,entry_ts,exit_ts,
    trigger}; [] no entry; False no bars.
    """
    is_utc = None
    bars = conn.execute(
        "SELECT ts, open, high, low, close, volume FROM ohlcv_1m "
        "WHERE ticker=? AND day=? ORDER BY ts ASC", (ticker, day)).fetchall()
    if not bars:
        return False
    is_utc = _ts_is_utc(bars[0]['ts'])
    entry_start_cmp = _et_hhmm_to_comparable(entry_start_et, day, is_utc)
    entry_end_cmp   = _et_hhmm_to_comparable(entry_end_et,   day, is_utc)
    eod_cmp         = _et_hhmm_to_comparable(eod_et,         day, is_utc)
    pm_start_cmp    = _et_hhmm_to_comparable('04:00', day, is_utc)
    open_cmp        = _et_hhmm_to_comparable('09:30', day, is_utc)

    buf       = sig['buf']
    accept_n  = max(3, int(sig['accept_n'] or 3))   # swing-low lookback for roll-over
    sr_reject, sr_vwap_loss, sr_lower_high = sig['sr_reject'], sig['sr_vwap_loss'], sig['sr_lower_high']
    sc_below_vwap, sc_bearish, sc_surge = sig['sc_below_vwap'], sig['sc_bearish'], sig['sc_surge']
    sc_min_ext = sig['sc_min_ext']
    if not (sr_reject or sr_vwap_loss or sr_lower_high):
        return []   # a short trigger is required
    max_entries = max(1, int(sig.get('max_reentry', 1)))

    trades_out: list = []
    entry = entry_ts = trigger_tag = None
    stop = target = 0.0
    in_position = False
    pm_high = day_high = 0.0
    vwap_num = vwap_den = 0.0
    pmh_tested = was_above_vwap = False
    session_bars: list = []

    for bar in bars:
        hhmm = bar['ts'][11:16]
        o = float(bar['open'] or 0); h = float(bar['high'] or 0)
        l = float(bar['low'] or 0);  c = float(bar['close'] or 0)
        v = float(bar['volume'] or 0)

        if not in_position:
            if hhmm < open_cmp:
                if hhmm >= pm_start_cmp and h > pm_high:
                    pm_high = h
                continue
            session_bars.append({'o': o, 'h': h, 'l': l, 'c': c, 'v': v})
            if h > day_high:
                day_high = h
            if pm_high > 0 and h >= pm_high:
                pmh_tested = True
            tp = (h + l + c) / 3
            if v > 0:
                vwap_num += tp * v; vwap_den += v
            svwap = vwap_num / vwap_den if vwap_den else 0
            if svwap > 0 and c > svwap:
                was_above_vwap = True

            if len(trades_out) >= max_entries:
                break
            if hhmm < entry_start_cmp:
                continue
            if hhmm > entry_end_cmp:
                break

            # ── AND condition gates ──
            cond_ok = True
            if sc_below_vwap and svwap > 0 and c >= svwap:
                cond_ok = False
            if cond_ok and sc_bearish and c >= o:
                cond_ok = False
            if cond_ok and sc_min_ext > 0:
                if not (svwap > 0 and (c - svwap) / svwap * 100 >= sc_min_ext):
                    cond_ok = False
            if cond_ok and sc_surge:
                if len(session_bars) < 3:
                    cond_ok = False
                else:
                    avg = sum(b['v'] for b in session_bars[:-1]) / (len(session_bars) - 1)
                    if not (avg > 0 and v >= avg * 1.5):
                        cond_ok = False

            # ── OR short triggers ──
            reject_fire = (sr_reject and pmh_tested and pm_high > 0
                           and c < pm_high * (1 - buf / 100))
            vwap_fire   = (sr_vwap_loss and was_above_vwap and svwap > 0
                           and c < svwap * (1 - buf / 100))
            roll_fire = False
            if sr_lower_high and len(session_bars) > accept_n and day_high > 0:
                recent = session_bars[-(accept_n + 1):-1]
                swing_low  = min(b['l'] for b in recent)
                swing_high = max(b['h'] for b in recent)
                # lower high (not making new day highs) AND breaks recent swing low
                if swing_high < day_high and c < swing_low * (1 - buf / 100):
                    roll_fire = True
            trig_ok = reject_fire or vwap_fire or roll_fire

            if not (cond_ok and trig_ok):
                continue

            entry = c
            if entry <= 0:
                continue
            entry_ts = bar['ts']
            trigger_tag = ('REJECT' if reject_fire else
                           ('VWAP_LOSS' if vwap_fire else 'ROLL_OVER'))
            stop   = round(entry * (1 + sl_pct  / 100), 4)   # above
            target = round(entry * (1 - tgt_pct / 100), 4)   # below
            in_position = True
            continue   # exits from the NEXT bar (no look-ahead)

        # In position (short) — exit checks.
        exit_price = exit_reason = None
        if hhmm >= eod_cmp:
            exit_price, exit_reason = c, 'EOD Close'
        elif h >= stop:
            exit_price, exit_reason = stop, 'Stop Loss'
        elif l <= target:
            exit_price, exit_reason = target, 'Target Hit'

        if exit_reason:
            trades_out.append({'entry': entry, 'exit': exit_price, 'reason': exit_reason,
                               'entry_ts': entry_ts, 'exit_ts': bar['ts'], 'trigger': trigger_tag})
            in_position = False
            entry = entry_ts = trigger_tag = None
            stop = target = 0.0
            if exit_reason == 'EOD Close':
                break
            continue

    if in_position and bars:
        trades_out.append({'entry': entry, 'exit': float(bars[-1]['close'] or 0), 'reason': 'EOD Close',
                           'entry_ts': entry_ts, 'exit_ts': bars[-1]['ts'], 'trigger': trigger_tag})
    return trades_out


# ══════════════════════════════════════════════════════════════════════════════
# SWING TRADE BACKTEST
# ══════════════════════════════════════════════════════════════════════════════

def run_swing_backtest(cfg: dict) -> dict:
    """
    cfg keys:
      start_date, end_date, initial_capital
      swing_position_pct      % of capital per trade (default 3)
      swing_stop_loss_pct     % below entry (default 7)
      swing_profit_target_pct % above entry (default 15)
      swing_max_hold_days     calendar days to hold before force-close (default 20)
      min_market_cap_m        min market cap in $M — 0 = disabled (default 500)
      min_gap_pct, min_price, max_price, min_volume_m, max_float_m

    Candidate source: gap_data cross-filtered by market cap (>= min_market_cap_m).
    Market cap is fetched from Polygon and cached in ticker_metadata (7-day TTL).
    Entry: today_close of gap day — simulating "confirmed gap, buy at close".
    Exit: walk Polygon daily bars (stop → target → max hold days).
    """
    start         = cfg.get('start_date')
    end           = cfg.get('end_date')
    capital       = float(cfg.get('initial_capital', 100_000))
    pos_pct       = float(cfg.get('swing_position_pct', 3))
    sl_pct        = float(cfg.get('swing_stop_loss_pct', 7))
    tgt_pct       = float(cfg.get('swing_profit_target_pct', 15))
    max_hold      = int(cfg.get('swing_max_hold_days', 20))
    min_cap_m     = float(cfg.get('min_market_cap_m', 500))
    min_gap       = float(cfg.get('min_gap_pct', 5))
    min_price     = float(cfg.get('min_price', 1))
    max_price     = float(cfg.get('max_price', 9999))
    min_vol       = float(cfg.get('min_volume_m', 0))
    max_float     = float(cfg.get('max_float_m', 0))

    if not POLYGON_KEY:
        raise ValueError('POLYGON_API_KEY is required for swing backtest (daily bar fetch)')

    candidates = _fetch_candidates(start, end, min_gap, min_price, max_price, min_vol, max_float,
                                   cfg.get('float_operator', '<='))
    total_before_cap_filter = len(candidates)

    # ── Market cap filter ──────────────────────────────────────────────────────
    market_cap_filtered = 0
    if min_cap_m > 0 and candidates:
        unique_tickers = list({row['ticker'].upper() for row in candidates})
        market_caps = fetch_and_cache_market_caps(unique_tickers)
        filtered = []
        for row in candidates:
            cap = market_caps.get(row['ticker'].upper())
            if cap is not None and cap >= min_cap_m:
                filtered.append(row)
            else:
                market_cap_filtered += 1
        candidates = filtered

    # Pre-fetch daily bars per unique ticker (one API call each, cached).
    # Extend the fetch window by max_hold days so stocks near the end of the
    # backtest range still get enough bars to reach stop/target/max-hold.
    fetch_end = (datetime.strptime(end, '%Y-%m-%d') + timedelta(days=max_hold + 10)).strftime('%Y-%m-%d')

    unique_tickers = list({row['ticker'] for row in candidates})
    daily_bars_cache: dict[str, dict[str, dict]] = {}
    for ticker in unique_tickers:
        bars = _fetch_polygon_daily_bars(ticker, start, fetch_end)
        daily_bars_cache[ticker] = {b['date']: b for b in bars}
        time.sleep(0.13)   # ~7 req/s within Polygon limits

    trades        = []
    equity        = capital
    equity_curve  = [{'date': start, 'equity': round(equity, 2)}]
    peak_equity   = capital
    max_dd        = 0.0
    daily_returns: list[float] = []
    no_data_count = 0

    for row in candidates:
        ticker     = row['ticker']
        trade_date = row['date']
        entry      = float(row['today_close'] or 0)  # enter at gap-day close

        if entry <= 0:
            continue

        trade_value = equity * (pos_pct / 100)
        shares = math.floor(trade_value / entry)
        if shares < 1:
            continue

        # Daily bars after entry date, capped at max_hold_days
        ticker_bars = daily_bars_cache.get(ticker, {})
        hold_dates  = sorted(d for d in ticker_bars if d > trade_date)[:max_hold]

        if not hold_dates:
            no_data_count += 1
            continue

        hold_bars = [ticker_bars[d] for d in hold_dates]
        exit_price, exit_reason, days_held = _simulate_swing_trade(entry, sl_pct, tgt_pct, hold_bars)

        stop   = round(entry * (1 - sl_pct  / 100), 4)
        target = round(entry * (1 + tgt_pct / 100), 4)

        pnl     = round((exit_price - entry) * shares, 2)
        pnl_pct = round((exit_price - entry) / entry * 100, 3)
        equity += pnl

        if equity > peak_equity:
            peak_equity = equity
        dd = (peak_equity - equity) / peak_equity * 100
        if dd > max_dd:
            max_dd = dd

        daily_returns.append(pnl / (entry * shares) if entry * shares else 0)

        trades.append({
            'date':         trade_date,
            'ticker':       ticker,
            'gap_pct':      round(float(row['gap_percentage'] or 0), 2),
            'entry':        round(entry, 4),
            'exit':         round(exit_price, 4),
            'shares':       shares,
            'stop':         round(stop, 4),
            'target':       round(target, 4),
            'pnl':          pnl,
            'pnl_pct':      pnl_pct,
            'exit_reason':  exit_reason,
            'days_held':    days_held,
            'equity_after': round(equity, 2),
        })
        equity_curve.append({'date': trade_date, 'equity': round(equity, 2)})

    equity_curve.append({'date': end, 'equity': round(equity, 2)})

    summary = _calc_summary(trades, capital, equity, max_dd, daily_returns)
    summary['no_data_count']          = no_data_count
    summary['max_hold_exits']         = sum(1 for t in trades if t['exit_reason'] == 'Max Hold Days')
    summary['market_cap_filtered']    = market_cap_filtered
    summary['total_before_cap_filter'] = total_before_cap_filter

    return {'summary': summary, 'trades': trades, 'equity_curve': equity_curve}


def _fetch_polygon_daily_bars(ticker: str, start: str, end: str) -> list[dict]:
    """Fetch daily OHLCV from Polygon. Returns [] on error or missing key."""
    if not POLYGON_KEY:
        return []
    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{ticker.upper()}/range/1/day/"
        f"{start}/{end}?adjusted=true&sort=asc&limit=5000&apiKey={POLYGON_KEY}"
    )
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return [
                {
                    'date':   datetime.utcfromtimestamp(r['t'] / 1000).strftime('%Y-%m-%d'),
                    'open':   r.get('o'),
                    'high':   r.get('h'),
                    'low':    r.get('l'),
                    'close':  r.get('c'),
                    'volume': r.get('v'),
                }
                for r in resp.json().get('results', [])
                if r.get('t')
            ]
    except Exception:
        pass
    return []


def _simulate_swing_trade(
    entry_price: float,
    sl_pct: float,
    tgt_pct: float,
    daily_bars: list[dict],
) -> tuple[float, str, int]:
    """
    Walk daily bars. Conservative same-day ordering: stop fires before target.
    Returns (exit_price, exit_reason, days_held).
    """
    stop   = entry_price * (1 - sl_pct  / 100)
    target = entry_price * (1 + tgt_pct / 100)

    for i, bar in enumerate(daily_bars):
        low   = float(bar['low']   or 0)
        high  = float(bar['high']  or 0)
        close = float(bar['close'] or 0)

        if low <= stop:
            return (round(stop,   4), 'Stop Loss',     i + 1)
        if high >= target:
            return (round(target, 4), 'Target Hit',    i + 1)

    return (round(float(daily_bars[-1]['close'] or 0), 4), 'Max Hold Days', len(daily_bars))


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _fetch_candidates(start, end, min_gap, min_price, max_price, min_vol, max_float,
                      float_operator: str = '<=') -> list:
    query = """
        SELECT date, ticker, gap_percentage, today_open, today_high, today_low,
               today_close, volume_m, yesterday_close
        FROM gap_data
        WHERE date BETWEEN ? AND ?
          AND gap_percentage >= ?
          AND today_open >= ?
          AND today_open <= ?
          AND volume_m >= ?
    """
    params: list[Any] = [start, end, min_gap, min_price, max_price, min_vol]

    try:
        with _conn() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(gap_data)").fetchall()}
            if 'float_shares' in cols and max_float > 0:
                # Match the live BrownBot float gate: '>=' (min float) or '<=' (max
                # float). NULL float is never excluded (no data ≠ fails the filter).
                op = '>=' if float_operator == '>=' else '<='
                query += f" AND (float_shares IS NULL OR float_shares / 1e6 {op} ?)"
                params.append(max_float)
            query += " ORDER BY date ASC, gap_percentage DESC"
            return conn.execute(query, params).fetchall()
    except Exception:
        return []  # gap_data table not populated on this instance


def _calc_summary(trades, initial_capital, final_equity, max_dd, daily_returns) -> dict:
    if not trades:
        return {
            'total_trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0,
            'total_pnl': 0, 'total_return_pct': 0,
            'initial_capital': initial_capital, 'final_capital': final_equity,
            'avg_win': 0, 'avg_loss': 0, 'largest_win': 0, 'largest_loss': 0,
            'profit_factor': 0, 'max_drawdown_pct': 0, 'sharpe_ratio': 0,
            'stop_exits': 0, 'target_exits': 0, 'eod_exits': 0,
        }

    wins         = [t for t in trades if t['pnl'] > 0]
    losses       = [t for t in trades if t['pnl'] <= 0]
    gross_profit = sum(t['pnl'] for t in wins)
    gross_loss   = abs(sum(t['pnl'] for t in losses))

    import statistics
    sharpe = 0.0
    if len(daily_returns) > 1:
        mu = statistics.mean(daily_returns)
        sd = statistics.stdev(daily_returns)
        sharpe = round((mu / sd) * (252 ** 0.5), 2) if sd else 0.0

    return {
        'total_trades':     len(trades),
        'wins':             len(wins),
        'losses':           len(losses),
        'win_rate':         round(len(wins) / len(trades) * 100, 1),
        'total_pnl':        round(sum(t['pnl'] for t in trades), 2),
        'total_return_pct': round((final_equity - initial_capital) / initial_capital * 100, 2),
        'initial_capital':  round(initial_capital, 2),
        'final_capital':    round(final_equity, 2),
        'avg_win':          round(gross_profit / len(wins), 2)  if wins   else 0,
        'avg_loss':         round(-gross_loss  / len(losses), 2) if losses else 0,
        'largest_win':      round(max(t['pnl'] for t in wins), 2)  if wins   else 0,
        'largest_loss':     round(min(t['pnl'] for t in losses), 2) if losses else 0,
        'profit_factor':    round(gross_profit / gross_loss, 2) if gross_loss else 0,
        'max_drawdown_pct': round(max_dd, 2),
        'sharpe_ratio':     sharpe,
        'stop_exits':       sum(1 for t in trades if t['exit_reason'] == 'Stop Loss'),
        'target_exits':     sum(1 for t in trades if t['exit_reason'] == 'Target Hit'),
        'eod_exits':        sum(1 for t in trades if t['exit_reason'] == 'EOD Close'),
    }
