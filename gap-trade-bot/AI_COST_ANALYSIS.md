# AI Predict — Cost Analysis & Optimisation

## What triggers a cost

Each **AI Predict** click (historical tab) makes:

| Call | Provider | Notes |
|---|---|---|
| Ticker reference lookup | Polygon | SIC / sector classification |
| Sector ETF bars (e.g. XLK) | Polygon | Last 10 trading days |
| SPY bars | Polygon | Broader market comparison |
| Claude analysis | Anthropic | ~1,200 input + ~400 output tokens |

---

## Claude token cost (Haiku model)

| Metric | Value |
|---|---|
| Model | `claude-haiku-4-5` |
| Avg prompt tokens | ~1,200 |
| Avg response tokens | ~400 |
| Input price | $0.25 / 1M tokens |
| Output price | $1.25 / 1M tokens |
| **Cost per call** | **~$0.0008** |

---

## Cost at scale — before caching

| Active users/day | Clicks/user/day | Claude calls/day | Claude cost/month | Polygon calls/day |
|---|---|---|---|---|
| 100 | 2 | 200 | ~$5 | 600 |
| 500 | 2 | 1,000 | ~$24 | 3,000 |
| 1,000 | 3 | 3,000 | ~$72 | 9,000 |

> Polygon free tier: 5 calls/min, unlimited/day on Starter ($29/mo).  
> At 1,000 users the bottleneck shifts to Polygon rate limits before Claude cost.

---

## Optimisations implemented

### 1 — Analysis cache (`_analysis_cache`, 4 h TTL)

Cache key: `ticker | period | minGap | calendar_date`

- First user to request e.g. `NVDA | 1Y | 25% | 2026-05-09` pays the full cost.
- Every subsequent request with the same key within 4 hours is served from memory — **0 Claude calls, 0 Polygon calls**.
- Cache resets at midnight (new `calendar_date` in the key).
- UI shows a ⚡ `cached` badge so the user knows the result is reused.

### 2 — Sector ETF cache (`_sector_etf_cache`, 4 h TTL)

Cache key: `etf_symbol` (e.g. `XLK`, `XLF`)

- XLK/SPY bars change once per trading day.
- All tickers in the same sector share one cached Polygon fetch.
- Analysing AMD after NVDA costs **1 Polygon call** (reference only) instead of 3.

### 3 — Per-IP rate limit (5 calls / hour)

- Sliding-window counter keyed by client IP.
- Returns HTTP 429 with a human-readable wait time (e.g. `"2m 30s"`).
- Frontend shows a warning notification rather than a generic error.
- Prevents a single user (or bot) from draining the Claude budget.

---

## Cost at scale — after caching

Assumption: 10 users share the same popular ticker/settings per day.

| Active users/day | Real Claude calls/day | Claude cost/month | Polygon calls/day |
|---|---|---|---|
| 100 | ~20 | ~$0.50 | ~60 |
| 500 | ~100 | ~$2.40 | ~300 |
| 1,000 | ~200 | ~$5 | ~600 |

> **~93 % cost reduction** vs. uncached at 1,000 users.

---

## Savings breakdown per request

| Scenario | Claude calls | Polygon calls |
|---|---|---|
| First user — NVDA / 1Y / 25% today | 1 | 3 |
| 2nd–Nth user, same settings, same day | **0** | **0** |
| Different ticker, same sector (AMD after NVDA) | 1 | **1** (ref only) |
| Same user clicks again within 4 h | **0** | **0** |
| Same user exceeds 5 clicks/hour | blocked (429) | 0 |

---

## Code locations

| Component | File | Line |
|---|---|---|
| Cache + rate-limit data structures | `backend/app.py` | ~1487 |
| `_cache_get` / `_cache_set` helpers | `backend/app.py` | ~1498 |
| `_check_rate_limit` (sliding window) | `backend/app.py` | ~1512 |
| Sector ETF cache hit/set | `backend/app.py` | ~1630 |
| Rate limit gate (endpoint entry) | `backend/app.py` | ~1695 |
| Analysis cache hit/set | `backend/app.py` | ~1712 |

---

## If you scale beyond ~2,000 users/day

The current implementation uses in-memory Python dicts — fine for a single-process deployment but dicts are lost on server restart and not shared across multiple workers.

Consider migrating to **Redis** at that point:

```python
# Drop-in replacement sketch
import redis
r = redis.Redis()

def _cache_get(key, ttl):
    val = r.get(key)
    return json.loads(val) if val else None

def _cache_set(key, value, ttl):
    r.setex(key, ttl, json.dumps(value))
```

Redis also enables atomic rate limiting via `INCR` + `EXPIRE`, removing the need for the manual lock.

---

## Tier gating (existing)

The historical tab — and therefore AI Predict — is already gated behind the **Beginner** subscription tier and above. Free/anonymous users cannot trigger any AI or Polygon calls from this feature.
