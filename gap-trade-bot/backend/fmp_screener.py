#!/usr/bin/env python3
"""
Financial Modeling Prep (FMP) fundamentals fetcher for the Screener tab.

Pulls a comprehensive fundamentals snapshot for the US equity universe from
FMP's *stable* API (the legacy v3 endpoints were retired Aug 2025) and stores
it in the local SQLite DB so the frontend can filter Finviz-style without ever
hitting FMP at query time.

Rate limit: the subscription is capped at 300 requests/min.  A process-wide
token-bucket limiter (RATE_LIMIT below, set a little under 300 for safety)
throttles every outbound call regardless of how many worker threads run.

Universe source: FMP's symbol-list / screener endpoints are restricted on this
plan, so we reuse the Alpaca asset list already wired up in gap_up_detector
(`_get_alpaca_equity_universe`).  FMP is then queried per symbol.

Endpoints used per symbol (stable API):
  profile            -> identity, price, size, sector/industry, isEtf/isFund
  ratios-ttm         -> valuation multiples, margins, liquidity, leverage
  key-metrics-ttm    -> ROE/ROA/ROIC, EV multiples, yields
  financial-growth   -> revenue/EPS growth (annual = YoY, quarter = QoQ)
  analyst-estimates  -> forward EPS estimate

This module only knows how to *fetch and shape* a row.  Persistence lives in
database.py (`upsert_fundamentals` / `query_fundamentals`); the orchestration
loop and the nightly thread live in app.py.
"""
import os
import time
import threading
import logging
import requests

logger = logging.getLogger(__name__)

FMP_API_KEY = os.environ.get('FMP_API_KEY', '').strip().strip('"')
BASE = 'https://financialmodelingprep.com/stable'

# Stay safely under the 300/min plan cap.  Token-bucket refills continuously.
RATE_LIMIT_PER_MIN = 280
# Per-symbol we make this many calls; bump workers but keep the bucket binding.
MAX_WORKERS = 12
HTTP_TIMEOUT = 20


class _RateLimiter:
    """Process-wide token bucket. Blocks until a token is available."""

    def __init__(self, per_min: int):
        self.capacity = float(per_min)
        self.tokens = float(per_min)
        self.refill_per_sec = per_min / 60.0
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self):
        while True:
            with self._lock:
                now = time.monotonic()
                self.tokens = min(
                    self.capacity,
                    self.tokens + (now - self._last) * self.refill_per_sec,
                )
                self._last = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                # time until one token is available
                wait = (1.0 - self.tokens) / self.refill_per_sec
            time.sleep(min(wait, 1.0))


_limiter = _RateLimiter(RATE_LIMIT_PER_MIN)


def is_configured() -> bool:
    return bool(FMP_API_KEY)


def _get(endpoint: str, params: dict) -> object:
    """Rate-limited GET against the FMP stable API. Returns parsed JSON or None."""
    if not FMP_API_KEY:
        return None
    params = dict(params or {})
    params['apikey'] = FMP_API_KEY
    _limiter.acquire()
    try:
        resp = requests.get(f'{BASE}/{endpoint}', params=params, timeout=HTTP_TIMEOUT)
    except Exception as e:
        logger.debug(f'[FMP] {endpoint} request error: {e}')
        return None
    if resp.status_code == 429:
        # Rate limited despite the bucket — back off and retry once.
        logger.warning('[FMP] 429 rate limit hit; backing off 2s')
        time.sleep(2)
        try:
            resp = requests.get(f'{BASE}/{endpoint}', params=params, timeout=HTTP_TIMEOUT)
        except Exception:
            return None
    if resp.status_code != 200:
        logger.debug(f'[FMP] {endpoint} HTTP {resp.status_code}')
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    # Error envelopes come back as dicts, valid data as lists.
    if isinstance(data, dict) and ('Error Message' in data or 'message' in data):
        return None
    return data


def _first(data):
    """FMP list endpoints return a single-element list; unwrap safely."""
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict):
        return data
    return None


def _num(d: dict, key):
    if not d:
        return None
    v = d.get(key)
    if v in (None, '', 'None'):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_symbol(symbol: str) -> dict | None:
    """
    Fetch the full fundamentals snapshot for one symbol and return a flat dict
    matching the `fundamentals` table columns. Returns None if the symbol has no
    usable profile (delisted / no data).
    """
    profile = _first(_get('profile', {'symbol': symbol}))
    if not profile:
        return None

    ratios = _first(_get('ratios-ttm', {'symbol': symbol})) or {}
    metrics = _first(_get('key-metrics-ttm', {'symbol': symbol})) or {}
    g_annual = _first(_get('financial-growth',
                           {'symbol': symbol, 'period': 'annual', 'limit': 1})) or {}
    g_qtr = _first(_get('financial-growth',
                        {'symbol': symbol, 'period': 'quarter', 'limit': 1})) or {}
    cf_annual = _first(_get('cash-flow-statement-growth',
                            {'symbol': symbol, 'period': 'annual', 'limit': 1})) or {}
    cf_qtr = _first(_get('cash-flow-statement-growth',
                         {'symbol': symbol, 'period': 'quarter', 'limit': 1})) or {}

    price = _num(profile, 'price')

    # Forward EPS: nearest future annual analyst estimate.
    eps_forward = None
    estimates = _get('analyst-estimates',
                     {'symbol': symbol, 'period': 'annual', 'limit': 6})
    if isinstance(estimates, list) and estimates:
        today = time.strftime('%Y-%m-%d')
        future = [e for e in estimates if str(e.get('date', '')) >= today]
        pick = min(future, key=lambda e: e.get('date', '')) if future else estimates[0]
        eps_forward = _num(pick, 'epsAvg')

    forward_pe = None
    if price and eps_forward and eps_forward != 0:
        forward_pe = price / eps_forward

    return {
        'symbol': symbol,
        'company_name': profile.get('companyName'),
        'sector': profile.get('sector'),
        'industry': profile.get('industry'),
        'exchange': profile.get('exchange'),
        'country': profile.get('country'),
        'is_etf': 1 if profile.get('isEtf') else 0,
        'is_fund': 1 if profile.get('isFund') else 0,

        'price': price,
        'market_cap': _num(profile, 'marketCap'),
        'volume': _num(profile, 'volume'),
        'avg_volume': _num(profile, 'averageVolume'),
        'beta': _num(profile, 'beta'),
        'change_pct': _num(profile, 'changePercentage'),

        # Valuation
        'pe': _num(ratios, 'priceToEarningsRatioTTM'),
        'forward_pe': forward_pe,
        'peg': _num(ratios, 'priceToEarningsGrowthRatioTTM'),
        'ps': _num(ratios, 'priceToSalesRatioTTM'),
        'pb': _num(ratios, 'priceToBookRatioTTM'),
        'pfcf': _num(ratios, 'priceToFreeCashFlowRatioTTM'),
        'ev_ebitda': _num(metrics, 'evToEBITDATTM'),
        'ev_sales': _num(metrics, 'evToSalesTTM'),

        # Earnings
        'eps_ttm': _num(ratios, 'netIncomePerShareTTM'),
        'eps_forward': eps_forward,
        'earnings_yield': _num(metrics, 'earningsYieldTTM'),

        # Growth (annual = YoY, quarter = QoQ)
        'revenue_growth_yoy': _num(g_annual, 'revenueGrowth'),
        'revenue_growth_qoq': _num(g_qtr, 'revenueGrowth'),
        'eps_growth_yoy': _num(g_annual, 'epsgrowth'),
        'eps_growth_qoq': _num(g_qtr, 'epsgrowth'),
        'net_income_growth_yoy': _num(g_annual, 'netIncomeGrowth'),
        'fcf_growth_yoy': _num(cf_annual, 'growthFreeCashFlow'),
        'fcf_growth_qoq': _num(cf_qtr, 'growthFreeCashFlow'),
        'ocf_growth_yoy': _num(cf_annual, 'growthOperatingCashFlow'),

        # Profitability
        'roe': _num(metrics, 'returnOnEquityTTM'),
        'roa': _num(metrics, 'returnOnAssetsTTM'),
        'roic': _num(metrics, 'returnOnInvestedCapitalTTM'),
        'gross_margin': _num(ratios, 'grossProfitMarginTTM'),
        'operating_margin': _num(ratios, 'operatingProfitMarginTTM'),
        'net_margin': _num(ratios, 'netProfitMarginTTM'),

        # Financial health
        'debt_to_equity': _num(ratios, 'debtToEquityRatioTTM'),
        'current_ratio': _num(ratios, 'currentRatioTTM'),
        'quick_ratio': _num(ratios, 'quickRatioTTM'),
        'interest_coverage': _num(ratios, 'interestCoverageRatioTTM'),

        # Cash / dividend
        'fcf_per_share': _num(ratios, 'freeCashFlowPerShareTTM'),
        'fcf_yield': _num(metrics, 'freeCashFlowYieldTTM'),
        'dividend_yield': _num(ratios, 'dividendYieldTTM'),
        'payout_ratio': _num(ratios, 'dividendPayoutRatioTTM'),
    }


def _safe_round(v, dec=2):
    try:
        return round(float(v), dec)
    except (TypeError, ValueError):
        return None


def earnings_calendar(from_date: str, to_date: str) -> list:
    """
    Upcoming/historical earnings between two ISO dates (inclusive) from FMP.
    Returns the raw FMP list (symbol, date, epsActual, epsEstimated,
    revenueActual, revenueEstimated) or [] on failure.
    """
    data = _get('earnings-calendar', {'from': from_date, 'to': to_date})
    return data if isinstance(data, list) else []


def earnings_research(symbol: str) -> dict | None:
    """
    Assemble the earnings-research payload for one symbol entirely from FMP,
    matching the shape the frontend expects (see /api/earnings/<ticker>).
    Returns None if FMP has no earnings rows (caller should fall back to YF).
    """
    symbol = symbol.upper().strip()
    rows = _get('earnings', {'symbol': symbol, 'limit': 20})
    if not isinstance(rows, list) or not rows:
        return None

    today = time.strftime('%Y-%m-%d')

    # Next earnings date: nearest future row.
    future = sorted([r for r in rows if str(r.get('date', '')) >= today],
                    key=lambda r: r.get('date', ''))
    next_er = future[0]['date'] if future else None

    # History: reported quarters (epsActual present), newest first, max 12.
    reported = sorted([r for r in rows if r.get('epsActual') is not None],
                      key=lambda r: r.get('date', ''), reverse=True)[:12]
    history = []
    for r in reported:
        est = r.get('epsEstimated')
        act = r.get('epsActual')
        surprise = None
        if est not in (None, 0) and act is not None:
            try:
                surprise = round((float(act) - float(est)) / abs(float(est)) * 100, 2)
            except (TypeError, ValueError, ZeroDivisionError):
                surprise = None
        history.append({
            'date': str(r.get('date', ''))[:10],
            'eps_estimate': _safe_round(est, 4),
            'eps_actual': _safe_round(act, 4),
            'surprise_pct': surprise,
        })

    # Quarterly revenue (actuals, last 4 reported).
    rev_rows = [r for r in reported if r.get('revenueActual') is not None][:4]
    quarterly_revenue = [{
        'date': str(r.get('date', ''))[:10],
        'revenue_b': _safe_round(float(r['revenueActual']) / 1e9, 2),
    } for r in rev_rows]

    # Forward estimates for the *next quarter* (the upcoming report) come straight
    # from the next earnings row — consistent with the "Next ER" framing. Per-quarter
    # low/high aren't published, so they stay null.
    eps_avg = eps_low = eps_high = None
    rev_avg = rev_low = rev_high = None
    if future:
        nxt = future[0]
        eps_avg = _num(nxt, 'epsEstimated')
        rev_est = _num(nxt, 'revenueEstimated')
        rev_avg = _safe_round(rev_est / 1e9, 2) if rev_est else None

    # Price targets + current price.
    pt = _first(_get('price-target-consensus', {'symbol': symbol})) or {}
    quote = _first(_get('quote', {'symbol': symbol})) or {}
    price_targets = {}
    if pt or quote:
        price_targets = {
            'current': _safe_round(quote.get('price')),
            'mean': _safe_round(pt.get('targetConsensus')),
            'median': _safe_round(pt.get('targetMedian')),
            'high': _safe_round(pt.get('targetHigh')),
            'low': _safe_round(pt.get('targetLow')),
        }

    # Analyst rating distribution.
    gc = _first(_get('grades-consensus', {'symbol': symbol})) or {}
    recommendations = {}
    if gc:
        recommendations = {
            'strong_buy': int(gc.get('strongBuy', 0) or 0),
            'buy': int(gc.get('buy', 0) or 0),
            'hold': int(gc.get('hold', 0) or 0),
            'sell': int(gc.get('sell', 0) or 0),
            'strong_sell': int(gc.get('strongSell', 0) or 0),
        }

    name = quote.get('name') or symbol

    return {
        'success': True, 'ticker': symbol, 'name': name, 'source': 'fmp',
        'next_er': next_er,
        'eps_est_avg': _safe_round(eps_avg, 4),
        'eps_est_low': _safe_round(eps_low, 4),
        'eps_est_high': _safe_round(eps_high, 4),
        'rev_est_avg_b': rev_avg,
        'rev_est_low_b': rev_low,
        'rev_est_high_b': rev_high,
        'history': history,
        'quarterly_revenue': quarterly_revenue,
        'price_targets': price_targets,
        'recommendations': recommendations,
    }


def get_universe() -> list:
    """US equity symbol universe, reused from the existing Alpaca asset list."""
    try:
        from gap_up_detector import _get_alpaca_equity_universe
        syms = _get_alpaca_equity_universe() or []
        # De-dup, drop anything with a dot/slash class share that FMP won't match.
        return sorted({s for s in syms if s and '.' not in s and '/' not in s})
    except Exception as e:
        logger.error(f'[FMP] universe fetch failed: {e}')
        return []
