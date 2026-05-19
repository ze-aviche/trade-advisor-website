import os
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import anthropic

logger = logging.getLogger(__name__)

# Per-user conversation history (in-memory, keyed by user_id)
_conversation_histories: Dict[str, List[Dict]] = {}

SYSTEM_PROMPT = """You are an expert trading advisor specializing in gap and swing trading strategies. \
You help traders analyze stocks, identify gap setups, interpret news catalysts, and evaluate \
technical conditions.

Use your tools to fetch real data before answering questions about specific tickers. \
Be specific, data-driven, and actionable. Clearly state when data is unavailable or limited. \
Keep responses concise but thorough — traders value clarity over length.

FORMATTING RULES (strictly follow):
- For earnings data (dates, EPS estimates, revenue estimates, surprise %) ALWAYS use a markdown table with columns: Symbol | Date | EPS Est | EPS Actual | Revenue Est | Surprise %.
- For technical analysis output (RSI, MACD, moving averages, support/resistance levels, volume) ALWAYS use a markdown table with columns: Indicator | Value | Signal.
- For news summaries use a numbered list with **bold** headlines followed by a brief summary.
- Use ## section headers to separate Earnings, Technical Analysis, News, and Summary sections.
- Use **bold** for key prices, percentages, and important values.
- Keep tables compact — do not add unnecessary columns.
- For simple one-line factual answers, plain text is fine — no table needed."""

TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for current market news or general trading information using DuckDuckGo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_stock_news",
        "description": "Fetch recent news articles for a specific stock symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"},
                "days": {"type": "integer", "description": "Days of history to search (default 7)"}
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_market_data",
        "description": "Get real-time quote snapshot for a stock from Alpaca Data API, including price, volume, and today's gap.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"}
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_technical_analysis",
        "description": "Fetch recent daily OHLCV bars and compute basic technical indicators (SMA10, SMA20, recent gaps) for a stock.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker symbol"},
                "days": {"type": "integer", "description": "Trading days of history to fetch (default 20)"}
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_earnings_calendar",
        "description": "Look up upcoming or recent earnings dates and estimates for a stock.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker symbol (optional)"}
            },
            "required": []
        }
    }
]


class ClaudeAIAgent:
    """Claude-powered trading advisor using Anthropic API with native tool use"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self._alpaca_key    = os.getenv('ALPACA_API_KEY', '')
        self._alpaca_secret = os.getenv('ALPACA_API_SECRET', '')
        self.model = "claude-haiku-4-5-20251001"
        logger.info("Claude AI Agent initialized")

    # ── Tool implementations ────────────────────────────────────────────────

    def _web_search(self, query: str) -> Dict[str, Any]:
        try:
            resp = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            if data.get("Abstract"):
                results.append({
                    "title": data.get("Heading", ""),
                    "snippet": data["Abstract"],
                    "url": data.get("AbstractURL", "")
                })
            for topic in data.get("RelatedTopics", [])[:4]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic["Text"].split(" - ")[0],
                        "snippet": topic["Text"],
                        "url": topic.get("FirstURL", "")
                    })
            return {"query": query, "results": results}
        except Exception as e:
            return {"query": query, "error": str(e), "results": []}

    def _get_stock_news(self, symbol: str, days: int = 7) -> Dict[str, Any]:
        result = self._web_search(f"{symbol} stock news last {days} days earnings announcement")
        return {"symbol": symbol, "news": result.get("results", []), "query": result.get("query")}

    def _get_market_data(self, symbol: str) -> Dict[str, Any]:
        if not self._alpaca_key or not self._alpaca_secret:
            return {"symbol": symbol, "error": "ALPACA_API_KEY / ALPACA_API_SECRET not configured"}
        try:
            sym = symbol.upper()
            headers = {
                'APCA-API-KEY-ID':     self._alpaca_key,
                'APCA-API-SECRET-KEY': self._alpaca_secret,
            }
            resp = requests.get(
                'https://data.alpaca.markets/v2/stocks/snapshots',
                headers=headers,
                params={'symbols': sym, 'feed': 'sip'},
                timeout=10,
            )
            resp.raise_for_status()
            snap = resp.json().get(sym, {})
            day      = snap.get('dailyBar') or {}
            prev_day = snap.get('prevDailyBar') or {}
            trade    = snap.get('latestTrade') or {}
            prev_close = prev_day.get('c')
            today_open = day.get('o')
            gap_pct = None
            if prev_close and today_open and prev_close != 0:
                gap_pct = round(((today_open - prev_close) / prev_close) * 100, 2)
            change_pct = None
            if prev_close and day.get('c') and prev_close != 0:
                change_pct = round(((day['c'] - prev_close) / prev_close) * 100, 2)
            return {
                "symbol": sym,
                "current_price": trade.get('p') or day.get('c'),
                "today_open": today_open,
                "today_high": day.get('h'),
                "today_low": day.get('l'),
                "today_close": day.get('c'),
                "today_volume": day.get('v'),
                "prev_close": prev_close,
                "gap_percent": gap_pct,
                "change_percent": change_pct,
            }
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def _get_technical_analysis(self, symbol: str, days: int = 20) -> Dict[str, Any]:
        if not self._alpaca_key or not self._alpaca_secret:
            return {"symbol": symbol, "error": "ALPACA_API_KEY / ALPACA_API_SECRET not configured"}
        try:
            sym   = symbol.upper()
            end   = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days + 14)).strftime("%Y-%m-%d")
            headers = {
                'APCA-API-KEY-ID':     self._alpaca_key,
                'APCA-API-SECRET-KEY': self._alpaca_secret,
            }
            resp = requests.get(
                f'https://data.alpaca.markets/v2/stocks/{sym}/bars',
                headers=headers,
                params={'timeframe': '1Day', 'start': start, 'end': end,
                        'limit': 50, 'adjustment': 'raw', 'feed': 'sip'},
                timeout=10,
            )
            resp.raise_for_status()
            bars = resp.json().get('bars') or []
            if not bars:
                return {"symbol": sym, "error": "No price data returned from Alpaca"}

            def _bar_date(b):
                return b['t'][:10]  # ISO string "2024-01-01T..." → "2024-01-01"

            closes = [b['c'] for b in bars]
            sma10 = round(sum(closes[-10:]) / min(len(closes), 10), 2)
            sma20 = round(sum(closes[-20:]) / min(len(closes), 20), 2)
            gaps = []
            for i in range(1, len(bars)):
                pc = bars[i - 1]['c']
                if pc:
                    gap = round(((bars[i]['o'] - pc) / pc) * 100, 2)
                    if abs(gap) >= 1:
                        gaps.append({"date": _bar_date(bars[i]), "gap_pct": gap})
            recent = [
                {"date": _bar_date(b), "o": b['o'], "h": b['h'],
                 "l": b['l'], "c": b['c'], "v": b['v']}
                for b in bars[-5:]
            ]
            return {
                "symbol": sym,
                "bars_fetched": len(bars),
                "sma10": sma10,
                "sma20": sma20,
                "latest_close": closes[-1],
                "range_high": max(closes),
                "range_low": min(closes),
                "recent_gaps": gaps[-5:],
                "recent_bars": recent,
            }
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def _get_earnings_calendar(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        if symbol:
            # Specific ticker: get company info from yfinance, then web search for earnings dates
            company_info = {}
            try:
                import yfinance as yf
                info = yf.Ticker(symbol.upper()).info
                company_info = {
                    "company_name": info.get("longName"),
                    "market_cap": info.get("marketCap"),
                    "description": (info.get("longBusinessSummary") or "")[:200],
                }
            except Exception:
                pass
            search = self._web_search(f"{symbol} earnings date estimate analyst forecast")
            return {
                "symbol": symbol.upper(),
                "company_reference": company_info,
                "web_results": search.get("results", [])
            }

        # General calendar: fetch next 5 days from Nasdaq public earnings API
        earnings = []
        today = datetime.now()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*"
        }
        for delta in range(5):
            date_str = (today + timedelta(days=delta)).strftime("%Y-%m-%d")
            try:
                resp = requests.get(
                    "https://api.nasdaq.com/api/calendar/earnings",
                    params={"date": date_str},
                    headers=headers,
                    timeout=10
                )
                if resp.status_code == 200:
                    rows = resp.json().get("data", {}).get("rows") or []
                    for row in rows[:15]:
                        earnings.append({
                            "date": date_str,
                            "symbol": row.get("symbol"),
                            "company": row.get("name"),
                            "time": row.get("time"),
                            "eps_forecast": row.get("epsForecast"),
                            "last_year_eps": row.get("lastYearEPS"),
                            "fiscal_quarter": row.get("fiscalQuarterEnding")
                        })
            except Exception:
                pass

        if earnings:
            return {"earnings_next_5_days": earnings, "total": len(earnings)}

        # Fallback to web search if Nasdaq API fails
        result = self._web_search("upcoming earnings calendar this week major stocks")
        return {"earnings_info": result.get("results", []), "note": "Live API unavailable, showing web search results"}

    def _dispatch_tool(self, name: str, inputs: Dict) -> str:
        if name == "web_search":
            return json.dumps(self._web_search(inputs["query"]))
        if name == "get_stock_news":
            return json.dumps(self._get_stock_news(inputs["symbol"], inputs.get("days", 7)))
        if name == "get_market_data":
            return json.dumps(self._get_market_data(inputs["symbol"]))
        if name == "get_technical_analysis":
            return json.dumps(self._get_technical_analysis(inputs["symbol"], inputs.get("days", 20)))
        if name == "get_earnings_calendar":
            return json.dumps(self._get_earnings_calendar(inputs.get("symbol")))
        return json.dumps({"error": f"Unknown tool: {name}"})

    # ── Main entry point ────────────────────────────────────────────────────

    def process_message(self, message: str, user_id: str = "anonymous") -> Dict[str, Any]:
        history = _conversation_histories.setdefault(user_id, [])

        # Build messages from stored history + new user message
        messages = [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": message})

        tools_used = []

        try:
            while True:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages
                )

                if response.stop_reason == "tool_use":
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            tools_used.append(block.name)
                            result_str = self._dispatch_tool(block.name, block.input)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_str
                            })
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results})
                else:
                    final_text = next(
                        (b.text for b in response.content if hasattr(b, "text")), ""
                    )
                    # Persist simple text turns to history
                    history.append({"role": "user", "content": message})
                    history.append({"role": "assistant", "content": final_text})
                    # Cap history to last 40 messages (~20 turns) to control token usage
                    if len(history) > 40:
                        _conversation_histories[user_id] = history[-40:]
                    return {
                        "success": True,
                        "response": final_text,
                        "tools_used": list(set(tools_used)),
                        "user_id": user_id
                    }

        except Exception as e:
            logger.error(f"Error in process_message: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"I encountered an error processing your request: {str(e)}"
            }

    def get_conversation_history(self, user_id: str) -> List[Dict]:
        return _conversation_histories.get(user_id, [])

    def clear_conversation_history(self, user_id: str) -> bool:
        _conversation_histories.pop(user_id, None)
        return True


# ── Specialized agent: Historical gap-up intraday analysis ───────────────────

GAP_UP_TRADE_SYSTEM_PROMPT = """You are a quantitative gap-up trading analyst specializing in intraday price action.

Your sole job is to analyze a stock's multi-year history of gap-up days and produce a precise, evidence-based intraday trading playbook:
- Long vs short bias (derived from Runner/Fader ratio and closing percent distribution)
- Optimal entry type and timing (open, premarket high break, first pullback, etc.)
- Specific stop placement (% from entry or reference price level)
- Exit targets and time-based stops (derived from day-high time distribution)
- Premarket signals that predict Runner vs Fader (premarket volume thresholds, extension %)

MISSING DATA RULES — strictly follow:
- "—" in the table means the data point was unavailable for that day. It does NOT mean zero.
- "0vol" means premarket volume was confirmed as zero (no premarket activity). Treat as a meaningful signal (no PM interest).
- Never infer a pattern from a column that has many "—" values — instead state that the signal is unreliable due to missing data.
- Only draw statistical conclusions from rows where the relevant field is present.
- A row where Runner/Fader is "—" provides no bias information — exclude it from Runner/Fader analysis.
- When fewer than 5 complete data points exist for a signal, say "insufficient data" rather than inventing a pattern.

Other rules:
- Base ALL conclusions on the statistical evidence in the data rows provided. Reference specific numbers.
- Entry, stop, and target must be specific enough for a trader to execute immediately.
- Never omit the stop loss.
- Your setup_card must be self-contained — a trader should be able to trade from it alone.
- Output ONLY valid JSON — no markdown, no commentary outside the JSON structure."""


class GapUpTradeAgent:
    """
    Stateless single-shot agent for historical gap-up intraday pattern analysis.
    Receives raw per-day data rows and returns a structured trading playbook.
    Separate from ClaudeAIAgent (chat) and SwingPicksAgent — does not share conversation history.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY', '')
        self.client  = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None
        self.model   = 'claude-sonnet-4-6'  # Sonnet — higher-quality pattern analysis

    @staticmethod
    def _fmt(val, width: int) -> str:
        """Format a value for the table: None → '—', preserve 0 as '0'."""
        if val is None or val == '':
            return f'{"—":<{width}}'
        return f'{str(val):<{width}}'

    def _format_rows(self, rows: list) -> str:
        """Convert raw gap-up day rows to a compact text table for the prompt."""
        header = (
            'Date       | PDClose | PMOpen  | PMHigh  | PMHiTime | PMVol  '
            '| Open    | Gap%  | DayHigh | DayHiTime | Close   | Close% | R/F'
        )
        lines = [header, '-' * len(header)]
        for r in rows:
            # Distinguish None (no data → "—") from 0 (confirmed zero volume → "0vol")
            pm_vol_raw = r.get('premarket volume')
            if pm_vol_raw is None:
                vol_str = '—'
            elif pm_vol_raw == 0:
                vol_str = '0vol'
            elif pm_vol_raw >= 1e6:
                vol_str = f'{pm_vol_raw/1e6:.1f}M'
            else:
                vol_str = f'{pm_vol_raw/1e3:.0f}k'

            lines.append(
                f'{self._fmt(r.get("date"), 10)} | '
                f'{self._fmt(r.get("pd close"), 7)} | '
                f'{self._fmt(r.get("premarket open"), 7)} | '
                f'{self._fmt(r.get("premarket high"), 7)} | '
                f'{self._fmt(r.get("premarket high time"), 8)} | '
                f'{vol_str:<6} | '
                f'{self._fmt(r.get("open"), 7)} | '
                f'{self._fmt(r.get("gap up % at open"), 5)} | '
                f'{self._fmt(r.get("day high") or r.get("high"), 7)} | '
                f'{self._fmt(r.get("day high time"), 9)} | '
                f'{self._fmt(r.get("close price"), 7)} | '
                f'{self._fmt(r.get("closing percent"), 6)} | '
                f'{r.get("Runner/Fader") or "—"}'
            )
        return '\n'.join(lines)

    def _data_quality_summary(self, rows: list) -> str:
        """
        Compute per-column completeness so Claude knows which signals are reliable.
        A field counts as present if it is not None and not empty string.
        """
        n = len(rows)
        if n == 0:
            return 'No rows.'

        def pct(key):
            count = sum(1 for r in rows if r.get(key) not in (None, '', 0))
            return f'{round(count / n * 100)}%'

        rf_complete = sum(1 for r in rows if r.get('Runner/Fader') in ('Runner', 'Fader', 'Neutral'))
        missing_rf  = n - rf_complete

        lines = [
            f'Total rows: {n}  |  Rows with valid Runner/Fader outcome: {rf_complete}'
            + (f'  |  Rows excluded from bias analysis (missing R/F): {missing_rf}' if missing_rf else ''),
            f'Column completeness (non-null present):',
            f'  premarket open:      {pct("premarket open")}',
            f'  premarket high:      {pct("premarket high")}',
            f'  premarket high time: {pct("premarket high time")}',
            f'  premarket volume:    {pct("premarket volume")}',
            f'  day high time:       {pct("day high time")}',
            f'  closing percent:     {pct("closing percent")}',
            f'  gap up % at open:    {pct("gap up % at open")}',
        ]
        return '\n'.join(lines)

    def analyze(
        self,
        ticker: str,
        rows: list,
        stats: dict,
        sector_info: dict,
        sector_perf: dict,
    ) -> dict:
        """
        Analyze historical gap-up rows and return a structured trading playbook dict.
        Raises on API error — caller should catch.
        """
        if not self.client:
            raise RuntimeError('GapUpTradeAgent: ANTHROPIC_API_KEY not set')

        # Limit to most recent 200 rows (sufficient for pattern detection, avoids huge prompts)
        rows_for_prompt = rows[-200:] if len(rows) > 200 else rows
        table   = self._format_rows(rows_for_prompt)
        dq_note = self._data_quality_summary(rows_for_prompt)

        etf_data  = sector_perf.get('sector_etf', {})
        spy_data  = sector_perf.get('spy', {})
        rel_str   = sector_perf.get('relative_strength', 'unknown')
        sector_block = (
            f"SECTOR: {sector_info.get('sector','N/A')} — ETF {sector_info.get('etf','N/A')}: "
            f"1d {etf_data.get('change_1d_pct','N/A')}% | 5d {etf_data.get('change_5d_pct','N/A')}% | "
            f"trend {etf_data.get('trend_5d','N/A')} | "
            f"vs SPY 5d: {spy_data.get('change_5d_pct','N/A')}% | relative: {rel_str}"
        )

        prompt = f"""Analyze ALL {len(rows_for_prompt)} historical gap-up trading days for {ticker.upper()} \
({sector_info.get('company_name','')}) and produce a precise intraday trading playbook.

DATA QUALITY NOTE — read before analyzing:
{dq_note}
"—" = data unavailable for that day (not zero, not applicable — simply missing).
"0vol" = confirmed zero premarket volume (no premarket activity; this IS informative).
Only draw conclusions from columns with high completeness. If a column is below ~40% complete, \
note the signal as unreliable rather than deriving a pattern from it.

DATA ({stats.get('period','N/A')}, {stats.get('minGap',5)}%+ gaps, {len(rows_for_prompt)} gap-up days shown):

{table}

AGGREGATE SUMMARY (computed from same data):
- Runner days: {stats.get('runnerDays',0)} ({stats.get('runnerPct',0)}%) | Fader days: {stats.get('faderDays',0)} ({stats.get('faderPct',0)}%)
- Avg gap: {stats.get('avgGap',0)}% | Avg day high from prev close: {stats.get('avgDayHigh',0)}% | Avg closing: {stats.get('avgClose',0)}%
- Avg premarket vol: {stats.get('avgPremarketVol',0)}M | Most common day-high time: {stats.get('commonHighTime','N/A')}
- Gap distribution: {stats.get('gapDistribution',{})}
- Recent 30d runner rate: {stats.get('recent30RunnerPct',0)}% vs full-period {stats.get('runnerPct',0)}%
- High-vol days runner rate (top 50% by PM vol): {stats.get('highVolRunnerPct',0)}%
{sector_block}

Analyze the raw data rows directly. Identify:
1. Under what premarket conditions (PM volume, PM extension %, PM high vs open) does this stock tend to be a Runner vs Fader?
2. What is the optimal entry type and timing (at open, pullback, premarket high break)?
3. Where should the stop be placed relative to entry?
4. What are the realistic profit targets and when should a time-stop exit occur?

Return ONLY valid JSON (no markdown, no text outside the JSON):
{{
  "bias": "Long" | "Short" | "Mixed",
  "bias_confidence": "High" | "Medium" | "Low",
  "bias_evidence": "One sentence citing specific runner/fader ratios and what drives the outcome",
  "summary": "2-3 sentence executive summary of the intraday gap-up trading pattern for {ticker.upper()}",
  "entry": {{
    "type": "At open" | "Premarket high break" | "First pullback" | "Wait for confirmation" | "Short at open",
    "specific_trigger": "Precise trigger — e.g. Buy 1-min candle break above premarket high, or Short if PM vol < 500k and open drops below premarket high",
    "best_pm_signals": ["premarket signal that predicts Runner", "premarket signal that predicts Fader — avoid entry"],
    "conditions": ["condition 1 for taking the entry", "condition 2"]
  }},
  "stop": {{
    "placement": "Where to place the stop relative to entry (e.g. below premarket high, below open, below VWAP)",
    "pct_from_entry": "X.X% below entry",
    "rationale": "Why this level is meaningful based on the data"
  }},
  "exit": {{
    "primary_target": "+X.X% from open (cite avg day high or specific distribution)",
    "secondary_target": "+Y.Y% from open",
    "optimal_exit_window": "Time range when day high most commonly occurs based on the data",
    "time_stop": "Exit by HH:MM ET if primary target not hit",
    "conditions": ["exit trigger 1", "exit trigger 2"]
  }},
  "pattern_insights": [
    "Quantitative insight 1 — cite specific numbers from the data",
    "Quantitative insight 2 — premarket volume or extension threshold observed",
    "Quantitative insight 3 — gap size or time-of-day pattern",
    "Quantitative insight 4 — regime or recent-trend observation"
  ],
  "setup_card": {{
    "entry": "One-line entry instruction",
    "stop": "One-line stop instruction",
    "target_1": "+X.X% — rationale",
    "target_2": "+Y.Y% — rationale",
    "time_limit": "Exit by HH:MM if not at target 1",
    "risk_reward": "1:X.X",
    "notes": "Any important caveat (e.g. only trade if PM vol > X)"
  }},
  "sector_impact": "One sentence on how current {sector_info.get('sector','N/A')} sector trend affects the reliability of this setup today",
  "caution": {{
    "level": "High" | "Medium" | "Low",
    "factors": ["risk factor 1", "risk factor 2"]
  }}
}}"""

        resp = self.client.messages.create(
            model=self.model,
            max_tokens=4096,  # JSON schema is large; 2000 always truncated mid-object
            system=GAP_UP_TRADE_SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = resp.content[0].text.strip()
        logger.debug(f'GapUpTradeAgent raw response ({len(raw)} chars): {raw[:500]}')

        # Strip markdown fences if present
        import re as _re
        if raw.startswith('```'):
            raw = _re.sub(r'^```(?:json)?\s*', '', raw)
            raw = _re.sub(r'\s*```$', '', raw).strip()

        # Extract the outermost JSON object
        m = _re.search(r'\{[\s\S]*\}', raw)
        if not m:
            logger.error(f'GapUpTradeAgent: no JSON object in response: {raw[:300]}')
            raise ValueError(f'GapUpTradeAgent returned no JSON object')

        json_str = m.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.error(
                f'GapUpTradeAgent: JSON parse failed ({exc}). '
                f'stop_reason={resp.stop_reason} raw_len={len(raw)} '
                f'json_len={len(json_str)} tail={json_str[-200:]}'
            )
            raise


# ── Specialized agent: Swing picks ranking ───────────────────────────────────

SWING_PICKS_SYSTEM_PROMPT = """You are an expert swing trader ranking candidates for 3-10 day hold positions.

Your grades feed the BrownBot autonomous trading system, so accuracy matters over breadth:
- Grade A: high-confidence setup — strong volume confirmation, clean structure above SMA10, clear catalyst or momentum
- Grade B: solid setup with one hesitation (e.g. slightly extended, or lower volume, or consolidating)
- Grade C: speculative — informational only, BrownBot will not auto-trade these

Bias must be Bullish or Bearish — never neutral on a pick.
Output ONLY valid JSON — no markdown, no commentary outside the JSON structure."""


class SwingPicksAgent:
    """
    Stateless single-shot agent for swing trade candidate ranking.
    Replaces the inline Anthropic call in _compute_and_save_swing_picks().
    Separate from ClaudeAIAgent (chat) and GapUpTradeAgent — no shared state.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY', '')
        self.client  = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None
        self.model   = 'claude-haiku-4-5-20251001'  # Haiku — fast, sufficient for structured ranking

    def rank_candidates(self, candidates: list, session_date: str, market_open: bool) -> dict:
        """
        Rank swing candidates and return the AI result dict with 'picks' and 'market_note'.
        Raises on API/JSON error — caller should catch.
        """
        if not self.client:
            raise RuntimeError('SwingPicksAgent: ANTHROPIC_API_KEY not set')

        def _row(c):
            vol_tag  = f'  surge {c["vol_ratio"]:.1f}×' if c.get('vol_ratio') else ''
            cap_tag  = (f'  mktcap ${c["market_cap_m"]/1000:.1f}B'
                        if c.get('market_cap_m') and c['market_cap_m'] >= 1000
                        else f'  mktcap ${c["market_cap_m"]:.0f}M' if c.get('market_cap_m') else '')
            sma_tag  = f'  sma10 ${c["sma10"]:.2f}' if c.get('sma10') else ''
            cpos_tag = f'  cpos {c["close_pos"]:.0%}' if c.get('close_pos') is not None else ''
            return (
                f"{c['ticker']:6s}  ${c['price']:>7.2f}"
                f"  {'+' if c['chg_pct'] >= 0 else ''}{c['chg_pct']:>6.2f}%"
                f"  vol {c['volume_m']:.1f}M  range {c['day_range']}%"
                f"  [{c['direction']}]{vol_tag}{cap_tag}{sma_tag}{cpos_tag}"
            )

        market_ctx = (
            'Note: this data is from the most recent completed trading session '
            '(market is currently closed).' if not market_open else ''
        )

        prompt = f"""You are an expert swing trader scanning for the best setups on {session_date}.
{market_ctx}

Candidates are pre-filtered: all pass min $10 price, $3M+ daily dollar volume, $300M+ market cap, \
close above 10-day SMA, and bullish intraday price structure (close in upper range, close ≥ VWAP). \
Broken patterns and sell-off volume have already been removed.

Column guide: cpos = close position in day range (100% = closed at high, 0% = closed at low). \
sma10 = 10-day SMA. surge = today vol ÷ yesterday vol.

Sources: [gainer/loser] top daily movers · [gap-up] intraday gap-ups · [vol-surge] unusual accumulation volume.

Pick the 6-8 BEST swing trading candidates for a 3-10 day hold.
Prefer: strong volume confirmation on up moves, gap-ups with continuation potential, \
vol-surge with high close_pos (price held near high), stocks above SMA10 with room to run.
Avoid: extended moves without consolidation, low-grade setups where the only edge is momentum without structure.

CANDIDATES
{chr(10).join(_row(c) for c in candidates)}

Return ONLY a JSON object — no markdown, no commentary:
{{
  "picks": [
    {{
      "ticker": "SYM",
      "grade": "A|B|C",
      "bias": "Bullish|Bearish",
      "reason": "One sentence on why this is a swing candidate",
      "entry_zone": "price or range string",
      "watch_for": "one short condition (e.g. hold above $X, volume > Y)",
      "risk": "key stop or invalidation level"
    }}
  ],
  "market_note": "1-2 sentence overall market context for swing traders"
}}"""

        msg = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=SWING_PICKS_SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)  # raises JSONDecodeError on bad response
