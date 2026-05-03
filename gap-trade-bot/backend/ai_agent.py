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

SYSTEM_PROMPT = """You are an expert trading advisor specializing in gap trading strategies. \
You help traders analyze stocks, identify gap setups, interpret news catalysts, and evaluate \
technical conditions.

Use your tools to fetch real data before answering questions about specific tickers. \
Be specific, data-driven, and actionable. Clearly state when data is unavailable or limited. \
Keep responses concise but thorough — traders value clarity over length."""

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
        "description": "Get real-time quote snapshot for a stock from Polygon.io, including price, volume, and today's gap.",
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
        self.polygon_api_key = os.getenv('POLYGON_API_KEY')
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
        if not self.polygon_api_key:
            return {"symbol": symbol, "error": "POLYGON_API_KEY not configured"}
        try:
            url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{symbol.upper()}"
            resp = requests.get(url, params={"apiKey": self.polygon_api_key}, timeout=10)
            resp.raise_for_status()
            ticker = resp.json().get("ticker", {})
            day = ticker.get("day", {})
            prev_day = ticker.get("prevDay", {})
            last_trade = ticker.get("lastTrade", {})
            last_quote = ticker.get("lastQuote", {})
            prev_close = prev_day.get("c")
            today_open = day.get("o")
            gap_pct = None
            if prev_close and today_open and prev_close != 0:
                gap_pct = round(((today_open - prev_close) / prev_close) * 100, 2)
            return {
                "symbol": symbol.upper(),
                "current_price": last_trade.get("p") or last_quote.get("P"),
                "today_open": today_open,
                "today_high": day.get("h"),
                "today_low": day.get("l"),
                "today_close": day.get("c"),
                "today_volume": day.get("v"),
                "prev_close": prev_close,
                "gap_percent": gap_pct,
                "change_percent": ticker.get("todaysChangePerc")
            }
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def _get_technical_analysis(self, symbol: str, days: int = 20) -> Dict[str, Any]:
        if not self.polygon_api_key:
            return {"symbol": symbol, "error": "POLYGON_API_KEY not configured"}
        try:
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=days + 14)).strftime("%Y-%m-%d")
            url = f"https://api.polygon.io/v2/aggs/ticker/{symbol.upper()}/range/1/day/{start}/{end}"
            resp = requests.get(
                url,
                params={"adjusted": "true", "sort": "asc", "limit": 50, "apiKey": self.polygon_api_key},
                timeout=10
            )
            resp.raise_for_status()
            bars = resp.json().get("results", [])
            if not bars:
                return {"symbol": symbol, "error": "No price data returned from Polygon"}
            closes = [b["c"] for b in bars]
            sma10 = round(sum(closes[-10:]) / min(len(closes), 10), 2)
            sma20 = round(sum(closes[-20:]) / min(len(closes), 20), 2)
            gaps = []
            for i in range(1, len(bars)):
                pc = bars[i - 1]["c"]
                if pc:
                    gap = round(((bars[i]["o"] - pc) / pc) * 100, 2)
                    if abs(gap) >= 1:
                        gaps.append({
                            "date": datetime.fromtimestamp(bars[i]["t"] / 1000).strftime("%Y-%m-%d"),
                            "gap_pct": gap
                        })
            recent = [
                {
                    "date": datetime.fromtimestamp(b["t"] / 1000).strftime("%Y-%m-%d"),
                    "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "v": b["v"]
                }
                for b in bars[-5:]
            ]
            return {
                "symbol": symbol.upper(),
                "bars_fetched": len(bars),
                "sma10": sma10,
                "sma20": sma20,
                "latest_close": closes[-1],
                "range_high": max(closes),
                "range_low": min(closes),
                "recent_gaps": gaps[-5:],
                "recent_bars": recent
            }
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def _get_earnings_calendar(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        if symbol:
            # Specific ticker: try Polygon reference then fall back to web search
            polygon_info = {}
            if self.polygon_api_key:
                try:
                    resp = requests.get(
                        f"https://api.polygon.io/v3/reference/tickers/{symbol.upper()}",
                        params={"apiKey": self.polygon_api_key},
                        timeout=10
                    )
                    if resp.status_code == 200:
                        d = resp.json().get("results", {})
                        polygon_info = {
                            "company_name": d.get("name"),
                            "market_cap": d.get("market_cap"),
                            "description": (d.get("description") or "")[:200]
                        }
                except Exception:
                    pass
            search = self._web_search(f"{symbol} earnings date estimate analyst forecast")
            return {
                "symbol": symbol.upper(),
                "polygon_reference": polygon_info,
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
