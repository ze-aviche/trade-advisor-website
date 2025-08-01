# Backtesting Framework

A consolidated backtesting framework that allows you to test any trading strategy with a single file. All strategy implementations are contained within `run_general_backtest.py`.

## 🚀 Quick Start

```bash
# Run break-out strategy
python3 run_general_backtest.py --strategy break_out --days 730 --capital 100000

# Run with custom parameters
python3 run_general_backtest.py \
  --strategy break_out \
  --days 365 \
  --capital 50000 \
  --position-size 500 \
  --commission 0.01 \
  --max-positions 5
```

## 📁 File Structure

```
strategies/
├── base_backtest.py              # Core backtesting engine
├── run_general_backtest.py       # Main runner + all strategy implementations
├── strategy_template.py           # Template for reference
└── README.md                     # This file
```

## 🏗️ Architecture

### Core Components

1. **`BaseBacktest`** - Abstract base class providing common functionality
2. **`run_general_backtest.py`** - Contains all strategy implementations
3. **Strategy Classes** - Each strategy inherits from `BaseBacktest`

### Framework Design

```
BaseBacktest (Abstract Base Class)
├── Common functionality
│   ├── Data fetching & processing
│   ├── Performance metrics calculation
│   ├── Reporting & visualization
│   └── Configuration management
├── Abstract methods (must implement)
│   ├── get_stocks_for_date()
│   └── get_market_data_for_stock()
└── Optional overrides
    ├── add_strategy_specific_metrics()
    └── add_strategy_specific_performance_metrics()

Strategy Implementation
├── Inherits from BaseBacktest
├── Implements required methods
└── Adds custom logic & metrics
```

## 📊 Available Strategies

### 1. Break Out Strategy (`break_out`)

**Description:** Tests gap-up stocks that break above their day high with volume confirmation.

**Entry Conditions:**
- Gap percentage ≥ 25%
- Price above day high (HOD)
- Market is open
- Price above VWAP
- Sufficient volume (≥500k forecasted)
- Breakout volume (≥2x average volume)
- Confidence level ≥ 60%

**Exit Conditions:**
- Profit target hit (50% gain)
- Stop loss hit (15% loss)
- Trailing stop (10% from entry)
- End of day exit

**Usage:**
```bash
python3 run_general_backtest.py --strategy break_out
```

### 2. Template Strategy (`template`)

**Description:** Template for implementing new strategies.

**Usage:**
```bash
python3 run_general_backtest.py --strategy template
```

## ⚙️ Command Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--strategy` | string | required | Strategy name (break_out, template) |
| `--days` | int | 730 | Number of days to backtest |
| `--capital` | int | 100000 | Initial capital in dollars |
| `--position-size` | int | 1000 | Number of shares per trade |
| `--commission` | float | 0.005 | Commission per trade in dollars |
| `--max-positions` | int | 10 | Maximum concurrent positions |
| `--output-dir` | string | backtest_reports | Output directory for reports |

## 🔧 How to Add a New Strategy

### Step 1: Create Strategy Class

Add a new class in `run_general_backtest.py`:

```python
class YourStrategyBacktest(BaseBacktest):
    """Your strategy implementation"""
    
    def __init__(self):
        # Import your strategy
        from your_strategy import YourStrategy
        strategy = YourStrategy()
        super().__init__(strategy, "your_strategy")
    
    def get_stocks_for_date(self, date: datetime) -> List[str]:
        """Get stocks to test for a specific date"""
        # Implement your stock selection logic
        return your_stock_list
    
    def get_market_data_for_stock(self, ticker: str, date: datetime) -> Optional[Dict[str, Any]]:
        """Get additional market data for your strategy"""
        # Implement your data collection logic
        return your_market_data
    
    def add_strategy_specific_metrics(self, trade_result: Dict[str, Any], entry_data: Dict[str, Any], analysis: Dict[str, Any]):
        """Add your custom metrics to trade result"""
        trade_result.update({
            'your_metric': entry_data.get('your_metric', 0)
        })
    
    def add_strategy_specific_performance_metrics(self, metrics: Dict[str, Any], df: pd.DataFrame):
        """Add your custom performance analysis"""
        # Implement your custom analysis
        pass
```

### Step 2: Register Strategy

Add your strategy to the `strategy_map`:

```python
def get_strategy_backtest(strategy_name: str):
    strategy_map = {
        'break_out': BreakoutBacktest,
        'template': TemplateBacktest,
        'your_strategy': YourStrategyBacktest  # Add here
    }
    
    if strategy_name in strategy_map:
        return strategy_map[strategy_name]
    else:
        raise ValueError(f"Strategy '{strategy_name}' not implemented. Available strategies: {list(strategy_map.keys())}")
```

### Step 3: Run Your Strategy

```bash
python3 run_general_backtest.py --strategy your_strategy
```

## 📈 Output

### Console Output
Real-time progress and final summary statistics.

### JSON Results File
Detailed results saved as `{strategy_name}_backtest_results_YYYYMMDD_HHMMSS.json` containing:
- Backtest configuration
- All trade results
- Performance metrics
- Timestamp

### Reports Directory
Generated in `backtest_reports/` with timestamp:
- `{strategy_name}_summary_report_YYYYMMDD_HHMMSS.txt` - Key performance metrics
- `{strategy_name}_trade_analysis_YYYYMMDD_HHMMSS.txt` - Detailed trade analysis
- `{strategy_name}_performance_charts_YYYYMMDD_HHMMSS.png` - Performance visualizations

## 📊 Performance Metrics

### Basic Metrics
- Total trades executed
- Win rate percentage
- Total P&L and returns
- Average P&L per trade

### Risk Metrics
- Sharpe ratio
- Maximum drawdown
- Standard deviation of returns
- Maximum profit/loss per trade

### Strategy-Specific Metrics
Each strategy can add custom metrics:
- **Break Out:** Gap percentage analysis, volume ratio analysis
- **Your Strategy:** Your custom metrics

## 🔍 Example Output

```
🚀 Starting break_out Strategy Backtest
📅 Days to test: 730
💰 Initial Capital: $100,000
📊 Position Size: 1000 shares
💸 Commission: $5.00 per trade
🎯 Max Positions: 10

📊 BREAK_OUT BACKTEST RESULTS SUMMARY
==================================================
Total Trades: 1,247
Winning Trades: 743
Losing Trades: 504
Win Rate: 59.58%
Total P&L: $45,230.50
Total Return: 45.23%
Average P&L per Trade: $36.27
Sharpe Ratio: 1.85
Maximum Drawdown: -12.34%
Max Profit: $2,450.00
Max Loss: -$1,850.00
==================================================
```

## 🛠️ Framework Features

### Common Functionality (Provided by BaseBacktest)

1. **Data Management**
   - Historical data fetching from Polygon API
   - Intraday data processing (1-minute bars)
   - Market data simulation

2. **Performance Analysis**
   - Win rate, P&L, returns calculation
   - Sharpe ratio, drawdown analysis
   - Risk metrics

3. **Reporting**
   - Summary reports
   - Trade analysis
   - Performance charts
   - JSON results export

4. **Configuration**
   - Capital, position size, commission
   - Date ranges, max positions
   - Customizable parameters

### Strategy-Specific Features (You Implement)

1. **Stock Selection**
   - Which stocks to test each day
   - Filtering criteria

2. **Entry Logic**
   - Entry conditions
   - Entry price calculation
   - Confidence scoring

3. **Exit Logic**
   - Exit conditions
   - Target and stop loss calculation

4. **Custom Metrics**
   - Strategy-specific performance metrics
   - Custom analysis

## 🎯 Benefits

### ✅ **Consolidated**
- All strategies in one file
- No need for separate files
- Easy to maintain

### ✅ **Extensible**
- Easy to add new strategies
- Consistent interface
- Reusable framework

### ✅ **Flexible**
- Customizable parameters
- Strategy-specific logic
- Comprehensive reporting

### ✅ **Robust**
- Error handling
- Logging
- Performance tracking

## 🔮 Future Enhancements

- **Multi-strategy comparison** - Compare multiple strategies side-by-side
- **Strategy optimization** - Parameter optimization framework
- **Real-time integration** - Connect to live trading system
- **Advanced analytics** - More sophisticated performance metrics
- **Strategy combinations** - Portfolio of multiple strategies

## 🚨 Troubleshooting

### Common Issues

1. **"Strategy not implemented"**
   - Check if strategy name is in `strategy_map`
   - Ensure strategy class exists

2. **Import errors**
   - Check if required modules are installed
   - Verify import paths

3. **No data found**
   - Check Polygon API key
   - Verify date ranges
   - Check market hours

### Performance Tips

- Use smaller date ranges for quick testing
- Reduce position size for faster processing
- Monitor memory usage for large backtests

## 📝 Example: Adding a Moving Average Strategy

```python
class MovingAverageBacktest(BaseBacktest):
    def __init__(self):
        from moving_average_strategy import MovingAverageStrategy
        strategy = MovingAverageStrategy()
        super().__init__(strategy, "moving_average")
    
    def get_stocks_for_date(self, date: datetime) -> List[str]:
        # Get all stocks or specific universe
        return self.get_all_stocks()
    
    def get_market_data_for_stock(self, ticker: str, date: datetime) -> Optional[Dict[str, Any]]:
        # Calculate moving averages
        short_ma = self.calculate_moving_average(ticker, date, 10)
        long_ma = self.calculate_moving_average(ticker, date, 50)
        
        return {
            'short_ma': short_ma,
            'long_ma': long_ma
        }

# Add to strategy_map:
strategy_map = {
    'break_out': BreakoutBacktest,
    'template': TemplateBacktest,
    'moving_average': MovingAverageBacktest
}
```

Then run:
```bash
python3 run_general_backtest.py --strategy moving_average
```

That's it! Your new strategy is ready to use. 🎯 