# Strategy Selection Logic

This document explains how the trading bot selects which strategy to use for a given gap-up stock.

## Strategy Selection Rules

### **Time-Based Logic** ⏰

The bot uses **TIME** as the primary factor for strategy selection:

| Time | Gap Percentage | Strategy | Direction | Reasoning |
|------|----------------|----------|-----------|-----------|
| **Before 10 AM** | Any gap | **Break Out** | LONG | Early morning gaps often continue upward |
| **After 10 AM** | ≥ 40% | **Gap Up Short** | SHORT | High gaps after 10 AM often reverse |
| **After 10 AM** | < 40% | **Break Out** | LONG | Moderate gaps can still break out |

### **Why This Logic Makes Sense:**

#### **Before 10 AM (Break Out Only)**
- Early morning gaps often have momentum
- Volume is typically lower, making breakouts more likely
- Market sentiment is still forming
- **No shorting** during pre-market/early hours

#### **After 10 AM (Conditional)**
- High gaps (≥40%) often exhaust themselves
- Volume increases, making reversals more likely
- Market has had time to digest the gap
- **Shorting becomes viable** for overextended stocks

## Strategy Details

### **Break Out Strategy**
- **Minimum Gap**: 25%
- **Direction**: LONG
- **Target**: 50% profit
- **Stop Loss**: 15%
- **Conditions**: Above day high, above VWAP, sufficient volume

### **Gap Up Short Strategy**
- **Minimum Gap**: 40%
- **Direction**: SHORT
- **Target**: 15% profit (short)
- **Stop Loss**: 15% (short)
- **Conditions**: After 10 AM, below premarket high, volume in range

## Implementation

### **Trading Bot Logic**
```python
if current_time >= ten_am and gap_percent >= 40:
    # After 10 AM + High gap: Use Gap Up Short strategy
    strategy = GapUpShortStrategy()
else:
    # Before 10 AM OR moderate gap: Use Break Out strategy
    strategy = BreakOutStrategy()
```

### **Web API Logic**
Same time-based logic applied to the bot status endpoint.

## Benefits

✅ **Time-Aware**: Respects market timing patterns  
✅ **Risk-Managed**: No shorting during volatile early hours  
✅ **Gap-Optimized**: Uses appropriate strategy for gap size  
✅ **Consistent**: Same logic across bot and web API  

## Example Scenarios

### **Scenario 1: 9:30 AM, 50% Gap**
- **Time**: Before 10 AM
- **Strategy**: Break Out (LONG)
- **Reason**: Early morning momentum

### **Scenario 2: 10:30 AM, 45% Gap**
- **Time**: After 10 AM
- **Gap**: ≥ 40%
- **Strategy**: Gap Up Short (SHORT)
- **Reason**: High gap after 10 AM likely to reverse

### **Scenario 3: 10:30 AM, 30% Gap**
- **Time**: After 10 AM
- **Gap**: < 40%
- **Strategy**: Break Out (LONG)
- **Reason**: Moderate gap can still break out 