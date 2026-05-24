"""
Purple Feedback Bot — analyses closed trade history and uses Claude to
generate actionable configuration recommendations.

Usage:
    analyzer = FeedbackAnalyzer()
    result   = analyzer.analyze(trades, lookback_days=30)
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

_ET = ZoneInfo('America/New_York')

import anthropic

_SYSTEM_PROMPT = """\
You are a professional trading performance coach analysing a systematic \
day/swing trader's results. You receive pre-aggregated statistics — never raw fills.
All times in the data are Eastern Time (ET). US equity market hours are 09:30–16:00 ET.

You may also receive a "prior_runs" array with summaries of previous analyses.
Use them to track whether past recommendations were acted on and whether performance improved.
If prior runs exist, explicitly compare key metrics (win rate, profit factor) to the most recent prior run.

Rules:
- Only surface patterns backed by ≥ 5 trades in that segment
- Be specific: reference actual numbers from the data
- If a prior recommendation appears to have been acted on (metric improved), acknowledge it
- Output ONLY valid JSON — no prose, no markdown fences
- Max 5 recommendations, ranked by expected impact on profitability

Output schema (strict):
{
  "summary": "<2-3 sentence overall assessment, comparing to prior run if available>",
  "strongest_setup": "<best-performing pattern with concrete numbers>",
  "recommendations": [
    {
      "priority": "HIGH|MEDIUM|LOW",
      "category": "Timing|Position Sizing|Entry Filter|Hold Duration|Day of Week|Instrument",
      "title": "<≤8 word title>",
      "detail": "<what the data shows — include specific numbers>",
      "suggestion": "<concrete config change or behaviour change>"
    }
  ]
}"""


class FeedbackAnalyzer:
    """Computes trade statistics and calls Claude for recommendations."""

    def __init__(self, api_key: Optional[str] = None):
        _key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not _key:
            raise ValueError('ANTHROPIC_API_KEY not set')
        self._client = anthropic.Anthropic(api_key=_key)
        self._model  = 'claude-haiku-4-5-20251001'

    # ── public entry point ──────────────────────────────────────────────────

    def analyze(self, trades: List[Dict], lookback_days: int = 30,
                prior_runs: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Compute stats from trade list and call Claude for recommendations.

        prior_runs: list of previous analysis dicts (newest first) — passed to
        Claude so it can track improvement over time.
        """
        if not trades:
            return self._empty_result(lookback_days)

        stats = self._compute_stats(trades, lookback_days)
        recs  = self._call_claude(stats, prior_runs or [])
        return {
            'generated_at':    datetime.utcnow().isoformat() + 'Z',
            'lookback_days':   lookback_days,
            'trade_count':     stats['total_trades'],
            'total_pnl':       stats['total_pnl'],
            'win_rate':        stats['win_rate'],
            'stats':           stats,
            'recommendations': recs.get('recommendations', []),
            'summary':         recs.get('summary', ''),
            'strongest_setup': recs.get('strongest_setup', ''),
        }

    # ── stats computation ───────────────────────────────────────────────────

    def _compute_stats(self, trades: List[Dict], lookback_days: int) -> Dict:
        pnls         = [float(t.get('pnl', 0)) for t in trades]
        winners      = [p for p in pnls if p > 0]
        losers       = [p for p in pnls if p < 0]
        gross_profit = sum(winners)
        gross_loss   = abs(sum(losers))

        return {
            'lookback_days':    lookback_days,
            'total_trades':     len(trades),
            'total_pnl':        round(sum(pnls), 2),
            'win_rate':         round(len(winners) / len(trades), 3) if trades else 0,
            'avg_win':          round(gross_profit / len(winners), 2) if winners else 0,
            'avg_loss':         round(sum(losers)  / len(losers),  2) if losers  else 0,
            'profit_factor':    round(gross_profit / gross_loss,   2) if gross_loss else None,
            'by_time_of_day':   self._by_time_bucket(trades),
            'by_day_of_week':   self._by_day_of_week(trades),
            'by_position_type': self._by_position_type(trades),
            'by_symbol':        self._by_symbol(trades, top_n=10),
        }

    def _by_time_bucket(self, trades: List[Dict]) -> List[Dict]:
        buckets: Dict[str, List[float]] = defaultdict(list)
        for t in trades:
            raw = str(t.get('trade_time') or '')
            try:
                if 'T' in raw or len(raw) > 8:
                    # Full ISO datetime — convert UTC → ET
                    dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    dt_et = dt.astimezone(_ET)
                    h, m = dt_et.hour, dt_et.minute
                else:
                    # Time-only string (HH:MM or HH:MM:SS) — assume already ET
                    h, m = int(raw[:2]), int(raw[3:5])
                label = f'{h:02d}:{(m // 30) * 30:02d} ET'
            except Exception:
                label = 'unknown'
            buckets[label].append(float(t.get('pnl', 0)))

        result = []
        for window in sorted(b for b in buckets if b != 'unknown'):
            pl = buckets[window]
            wins = [p for p in pl if p > 0]
            result.append({
                'window':    window,
                'trades':    len(pl),
                'win_rate':  round(len(wins) / len(pl), 3),
                'avg_pnl':   round(sum(pl) / len(pl), 2),
                'total_pnl': round(sum(pl), 2),
            })
        return result

    def _by_day_of_week(self, trades: List[Dict]) -> List[Dict]:
        names   = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        buckets: Dict[int, List[float]] = defaultdict(list)
        for t in trades:
            try:
                raw_time = str(t.get('trade_time') or '')
                raw_date = str(t.get('trade_date', ''))
                if 'T' in raw_time or len(raw_time) > 8:
                    # Derive weekday from the full timestamp converted to ET
                    dt = datetime.fromisoformat(raw_time.replace('Z', '+00:00'))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    d = dt.astimezone(_ET).weekday()
                else:
                    d = datetime.fromisoformat(raw_date).weekday()
                buckets[d].append(float(t.get('pnl', 0)))
            except Exception:
                pass
        result = []
        for idx in range(5):
            pl = buckets.get(idx, [])
            if not pl:
                continue
            wins = [p for p in pl if p > 0]
            result.append({
                'day':       names[idx],
                'trades':    len(pl),
                'win_rate':  round(len(wins) / len(pl), 3),
                'avg_pnl':   round(sum(pl) / len(pl), 2),
                'total_pnl': round(sum(pl), 2),
            })
        return result

    def _by_position_type(self, trades: List[Dict]) -> Dict[str, Dict]:
        buckets: Dict[str, List[float]] = defaultdict(list)
        for t in trades:
            buckets[t.get('position_type') or 'day'].append(float(t.get('pnl', 0)))
        out = {}
        for pt, pl in buckets.items():
            wins = [p for p in pl if p > 0]
            out[pt] = {
                'trades':    len(pl),
                'win_rate':  round(len(wins) / len(pl), 3),
                'avg_pnl':   round(sum(pl) / len(pl), 2),
                'total_pnl': round(sum(pl), 2),
            }
        return out

    def _by_symbol(self, trades: List[Dict], top_n: int = 10) -> List[Dict]:
        buckets: Dict[str, List[float]] = defaultdict(list)
        for t in trades:
            buckets[(t.get('symbol') or '').upper()].append(float(t.get('pnl', 0)))
        rows = []
        for sym, pl in buckets.items():
            wins = [p for p in pl if p > 0]
            rows.append({
                'symbol':    sym,
                'trades':    len(pl),
                'win_rate':  round(len(wins) / len(pl), 3),
                'total_pnl': round(sum(pl), 2),
            })
        rows.sort(key=lambda r: abs(r['total_pnl']), reverse=True)
        return rows[:top_n]

    # ── Claude call ─────────────────────────────────────────────────────────

    def _call_claude(self, stats: Dict, prior_runs: List[Dict]) -> Dict:
        prior_section = ''
        if prior_runs:
            # Send only the lightweight summary fields of prior runs — not full stats
            summaries = [
                {
                    'generated_at':    r.get('generated_at'),
                    'lookback_days':   r.get('lookback_days'),
                    'trade_count':     r.get('trade_count'),
                    'total_pnl':       r.get('total_pnl'),
                    'win_rate':        r.get('win_rate'),
                    'profit_factor':   r.get('stats', {}).get('profit_factor'),
                    'summary':         r.get('summary'),
                    'recommendations': r.get('recommendations', []),
                }
                for r in prior_runs[:3]   # cap at 3 prior runs to control tokens
            ]
            prior_section = (
                f'\n\nPrevious analysis runs (newest first) for trend comparison:\n'
                f'{json.dumps(summaries, indent=2)}\n'
            )

        prompt = (
            f'Here are the aggregated trading statistics for the past '
            f'{stats["lookback_days"]} days:\n\n'
            f'{json.dumps(stats, indent=2)}'
            f'{prior_section}\n\n'
            f'Analyse and return your JSON recommendations.'
        )
        try:
            msg  = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=_SYSTEM_PROMPT,
                messages=[{'role': 'user', 'content': prompt}],
            )
            text = msg.content[0].text.strip()
            # Strip markdown fences if Claude adds them despite instructions
            if '```' in text:
                parts = text.split('```')
                # parts[1] is inside the fences; strip optional language tag
                text = parts[1].lstrip('json').strip() if len(parts) > 1 else text
            # Extract just the JSON object in case there's surrounding prose
            start = text.find('{')
            end   = text.rfind('}')
            if start != -1 and end != -1:
                text = text[start:end + 1]
            return json.loads(text)
        except Exception as _e:
            return {
                'summary':         f'Analysis failed: {_e}',
                'strongest_setup': '',
                'recommendations': [],
            }

    def _empty_result(self, lookback_days: int) -> Dict:
        return {
            'generated_at':    datetime.utcnow().isoformat() + 'Z',
            'lookback_days':   lookback_days,
            'trade_count':     0,
            'total_pnl':       0.0,
            'win_rate':        0.0,
            'stats':           {},
            'recommendations': [],
            'summary':         f'No completed trades found in the past {lookback_days} days.',
            'strongest_setup': '',
        }
