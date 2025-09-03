# ORB Strategy Rules & Mechanics

## Overview
This document explains the detailed rules and mechanics of the Opening Range Breakout (ORB) strategy implemented in `orb_tester.py`. The strategy is designed to capture momentum breakouts that occur after the market opens and an initial range is established.

## Strategy Timeline

### Market Hours (UTC)
- **Session Start**: 14:30:00 UTC (9:30 AM EST)
- **Session End**: 21:00:00 UTC (4:00 PM EST)
- **Opening Range Window**: 14:30:00 - 14:34:59 UTC (5 minutes)
- **Breakout Allowed**: Starting at 14:35:00 UTC (9:35 AM EST)

## Entry Rules

### 1. Opening Range Formation
- **Duration**: First 5 minutes after market open (14:30-14:34 UTC)
- **Data Required**: 1-minute OHLCV bars from TimescaleDB
- **Range Calculation**:
  - **ORH (Opening Range High)**: Highest high during the 5-minute window
  - **ORL (Opening Range Low)**: Lowest low during the 5-minute window

### 2. Breakout Detection
- **Trigger**: First 1-minute bar that CLOSES above the opening range high (ORH)
- **Timing**: Must occur AFTER 14:35:00 UTC (opening range is established)
- **Confirmation**: Close price > ORH (not just a wick or high)

### 3. Entry Price Calculation
```python
entry = breakout_candle_close + slippage_cents
```
- **Base Price**: Close price of the breakout candle
- **Slippage**: +$0.01 to simulate realistic fill prices
- **Final Entry**: Rounded to 2 decimal places

### 4. Entry Filters
- **Price Filter**: Stock must be above $1.00 (`min_price`)
- **Volume Filter**: Dollar volume must exceed $1M (`min_dollar_volume_m`)
- **Data Quality**: Must have sufficient 1-minute bars for the day

## Stop Loss Rules

### 1. Stop Price Calculation
```python
stop = max(0.0001, ORL × (1 - stop_buffer_pct))
```
- **Base Stop**: Opening Range Low (ORL)
- **Buffer**: 1% below ORL (`stop_buffer_pct = 0.01`)
- **Minimum**: Never below $0.0001 (prevents division errors)

### 2. Stop Logic
- **Purpose**: Defines maximum loss per trade
- **Trigger**: When any subsequent bar's LOW touches or goes below stop
- **Exit Price**: Stop price minus slippage (slightly worse fill)

### 3. Example Stop Calculation
```
ORL = $2.56
Stop Buffer = 1%
Stop = max(0.0001, 2.56 × 0.99) = $2.53
```

## Take Profit Rules

### 1. Target Calculation
```python
target = entry + (take_profit_R × risk_per_share)
```
- **Risk per Share**: Entry price - Stop price
- **Take Profit R**: 2.0 (default - exit at 2× initial risk)
- **Target**: Entry + (2 × risk per share)

### 2. Take Profit Logic
- **Trigger**: When any subsequent bar's HIGH reaches or exceeds target
- **Exit Price**: Exactly at target price (good fill)
- **Reason**: "target"

### 3. Example Take Profit Calculation
```
Entry: $2.89
Stop: $2.53
Risk per Share: $2.89 - $2.53 = $0.36
Target: $2.89 + (2 × $0.36) = $3.61
```

## Time-Based Exit Rules

### 1. Time Exit Calculation
```python
time_exit_ts = pd.Timestamp(f"{date} {cfg.time_exit}", tz='UTC')
# Default: 16:00:00 UTC (11:00 AM EST)
```

### 2. Time Exit Logic
- **Trigger**: When current bar time reaches or exceeds time_exit
- **Exit Price**: Current bar's close price minus slippage
- **Reason**: "time_exit"
- **Purpose**: Prevents holding positions too long, captures morning momentum

### 3. Timing Strategy
- **Market Open**: 14:30 UTC (9:30 AM EST)
- **Time Exit**: 16:00 UTC (11:00 AM EST)
- **Duration**: Gives trades ~1.5 hours to develop
- **Logic**: Morning breakouts often resolve within first few hours

## End-of-Day Exit Rules

### 1. EOD Liquidation
- **Trigger**: If trade is still open at session end (21:00 UTC)
- **Exit Price**: Last bar's close price minus slippage
- **Reason**: "eod"
- **Purpose**: No overnight positions, clean slate for next day

### 2. EOD Logic
```python
if exit_price is None:  # No other exit triggered
    last = df_1m.iloc[-1]
    exit_price = last["close"] - slippage_cents
    reason = "eod"
```

## Position Sizing Rules

### 1. Risk Calculation
```python
risk_per_share = entry - stop
shares = risk_per_trade_usd / risk_per_share
```

### 2. Risk Management
- **Fixed Risk**: $100 per trade (`risk_per_trade_usd`)
- **Position Size**: Automatically calculated to risk exactly $100
- **Shares**: Rounded down to whole shares
- **Maximum Loss**: Always $100 (excluding fees)

### 3. Example Position Sizing
```
Entry: $2.89
Stop: $2.53
Risk per Share: $0.36
Shares: $100 ÷ $0.36 = 277 shares
Max Loss: 277 × $0.36 = $99.72
```

## Exit Priority Rules

The strategy follows a strict exit priority (first event wins):

1. **Stop Loss** (highest priority)
   - Protects capital, prevents large losses
   - Triggered by price action

2. **Take Profit** (second priority)
   - Captures profits at predetermined target
   - Triggered by price action

3. **Time Exit** (third priority)
   - Prevents over-holding positions
   - Triggered by time

4. **End-of-Day** (lowest priority)
   - Clean exit, no overnight risk
   - Triggered by session end

## Fee and Slippage Rules

### 1. Slippage Model
- **Entry**: +$0.01 (realistic fill above breakout)
- **Exit**: -$0.01 (realistic fill below target/stop)
- **Purpose**: Simulates real-world trading conditions

### 2. Fee Structure
```python
fees = fees_per_share × shares
# Default: $0.0005 per share
```

### 3. Net PnL Calculation
```python
gross_pnl = (exit_price - entry) × shares
net_pnl = gross_pnl - fees
```

## Data Requirements

### 1. TimescaleDB Table
- **Table**: `ohlcv_1m`
- **Columns**: `ticker`, `ts`, `day`, `open`, `high`, `low`, `close`, `volume`
- **Timeframe**: 1-minute bars
- **Timezone**: UTC

### 2. Data Quality Checks
- **Minimum Bars**: Must have data for entire trading session
- **Price Validation**: All OHLC values must be positive
- **Volume Validation**: Volume must be non-negative

## Strategy Parameters

### 1. Core Parameters
```python
orb_minutes: int = 5              # Opening range duration
slippage_cents: float = 0.01      # Entry/exit slippage
fees_per_share: float = 0.0005    # Per-share fees
stop_buffer_pct: float = 0.01     # Stop below ORL
risk_per_trade_usd: float = 100.0 # Fixed risk per trade
take_profit_R: float = 2.0        # Take profit at 2R
time_exit: str = "16:00:00"       # Time-based exit
```

### 2. Filter Parameters
```python
min_price: float = 1.0            # Minimum stock price
min_dollar_volume_m: float = 1.0  # Minimum dollar volume
```

## Performance Metrics

### 1. Trade-Level Metrics
- **Entry/Exit Times**: UTC timestamps
- **Entry/Exit Prices**: Rounded to 2 decimals
- **Shares**: Position size
- **PnL**: Net profit/loss after fees
- **R-Multiple**: PnL ÷ initial risk ($100)

### 2. Summary Metrics
- **Total Trades**: Number of completed trades
- **Win Rate**: Percentage of profitable trades
- **Total PnL**: Sum of all trade PnLs
- **Total R**: Sum of all R-multiples
- **Average R**: Mean R-multiple per trade
- **Median R**: Median R-multiple per trade

## Risk Management Summary

1. **Fixed Risk**: $100 per trade maximum
2. **Defined Stop**: Based on opening range low
3. **Take Profit**: 2× initial risk (2R)
4. **Time Limit**: 1.5 hours maximum hold time
5. **No Overnight**: All positions closed by session end
6. **Position Sizing**: Automatically calculated for consistent risk

## Strategy Logic Flow

```
Market Open (14:30 UTC)
    ↓
Build 5-min Opening Range (14:30-14:34)
    ↓
Wait for Breakout (14:35+)
    ↓
Entry on Close > ORH
    ↓
Monitor for Exit Conditions:
    ├─ Stop Loss (price ≤ stop)
    ├─ Take Profit (price ≥ target)
    ├─ Time Exit (time ≥ 16:00 UTC)
    └─ EOD Exit (time ≥ 21:00 UTC)
    ↓
Calculate PnL and R-Multiple
```

This strategy is designed to capture the momentum that often occurs when stocks break out of their initial opening range, while maintaining strict risk management and avoiding overnight positions.
