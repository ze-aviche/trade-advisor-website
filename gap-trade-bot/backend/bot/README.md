# 🤖 Gap Trade Bot

A sophisticated automated trading bot that identifies and trades gap-up stocks using real-time market data, historical analysis, and advanced risk management.

## 🚀 Features

- **Real-time Gap Detection**: Identifies stocks that gap up at market open
- **Break Out Strategy**: Trades stocks breaking above day high with volume confirmation
- **Risk Management**: 15% stop-loss, position sizing, daily loss limits
- **Alpaca Integration**: Paper trading with real market data
- **WebSocket Data**: Real-time price, volume, and VWAP data
- **Historical Analysis**: Compares current conditions with historical patterns
- **Database Tracking**: Persistent storage of positions, orders, and performance
- **Multi-terminal Management**: Start, stop, and monitor from different terminals

## 📊 Strategy Overview

### Break Out Strategy
- **Entry**: Buy when price breaks above day high with volume confirmation
- **Volume Conditions**: 
  - Minimum volume threshold
  - Volume above VWAP
  - Dynamic volume multiplier based on market conditions
- **Exit Conditions**:
  - 15% stop-loss
  - 50% profit target
  - Trailing stop (basic implementation)

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8+
- Alpaca Trading Account (paper or live)
- Polygon API Key (for market data)

### 1. Install Dependencies
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create `.env` file in `backend/` directory:
```bash
# Alpaca Trading API Credentials
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
ALPACA_ENDPOINT=https://paper-api.alpaca.markets

# Polygon API Key (for market data)
POLYGON_API_KEY=your_polygon_api_key_here

# Broker Selection
BROKER_TYPE=alpaca
```

### 3. Get API Keys
- **Alpaca**: Sign up at [alpaca.markets](https://alpaca.markets) for paper trading
- **Polygon**: Sign up at [polygon.io](https://polygon.io) for market data

## 🚀 Usage

### Starting the Bot
```bash
cd backend/bot
source ../../venv/bin/activate
python3 run_bot.py
```

### Stopping the Bot
```bash
# From another terminal
cd backend/bot
./stop_bot.sh

# Or using PID
kill $(cat bot.pid)
```

### Checking Bot Status
```bash
cd backend/bot
./check_bot.sh
```

### Background Operation
```bash
# Start in background
cd backend/bot
source ../../venv/bin/activate
nohup python3 run_bot.py > bot.log 2>&1 &

# Check if running
./check_bot.sh

# Stop background process
./stop_bot.sh
```

## 📁 Project Structure

```
backend/bot/
├── README.md                 # This file
├── run_bot.py               # Main bot runner
├── stop_bot.sh              # Stop script
├── check_bot.sh             # Status check script
├── config.py                # Configuration management
├── trading_bot.py           # Main bot orchestrator
├── data_manager.py          # Real-time and historical data
├── websocket_client.py      # WebSocket market data
├── position_manager.py      # Position tracking
├── order_manager.py         # Order execution
├── risk_manager.py          # Risk management
├── alpaca_client.py         # Alpaca broker integration
├── broker_factory.py        # Broker selection
├── trading_database.py      # Database management
├── strategies/
│   └── break_out.py        # Break out strategy
├── logs/                    # Log files
├── bot.pid                  # Process ID (created when running)
└── bot_status.json         # Bot status (created when running)
```

## 🔧 Configuration

### Trading Parameters
- **Volume per trade**: 1000 shares
- **Stop loss**: 15%
- **Profit target**: 50%
- **Max positions**: 10 concurrent
- **Daily loss limit**: $1000

### Strategy Parameters
- **Minimum gap**: 25%
- **Volume threshold**: 500,000 shares
- **Confidence threshold**: 60%
- **Historical analysis**: 730 days (2 years)

### Market Hours
- **Pre-market**: 4:00 AM ET
- **Market open**: 9:30 AM ET
- **Market close**: 4:00 PM ET
- **After-hours**: 8:00 PM ET

## 📊 Monitoring & Logs

### Log Files
- `logs/all.log` - All bot activity
- `logs/errors.log` - Error messages
- `logs/api.log` - API calls
- `logs/performance.log` - Performance metrics
- `logs/cache.log` - Cache operations

### Status Files
- `bot.pid` - Process ID for external management
- `bot_status.json` - Current bot status and statistics

### Database Files
- `trading_advisor.db` - Historical data cache
- `trading_positions.db` - Positions, orders, trades

## 🔍 Strategy Details

### Break Out Strategy Logic

1. **Gap Detection**: Identifies stocks with 25%+ gap-up
2. **Volume Analysis**: Checks for sufficient volume and VWAP confirmation
3. **Historical Comparison**: Analyzes similar historical patterns
4. **Entry Conditions**:
   - Price above day high
   - Volume above threshold
   - Above VWAP
   - High confidence score
5. **Risk Management**:
   - Position sizing based on risk
   - Stop-loss orders
   - Profit target orders

### Volume Forecasting
- Predicts full-day volume based on current volume and time
- Adjusts volume requirements based on market conditions
- Dynamic volume multiplier based on performance

## 🛡️ Risk Management

### Position Sizing
- Maximum 2% portfolio risk per trade
- Position size calculated based on stop-loss distance
- Account for available capital

### Stop Loss
- 15% fixed stop-loss
- Automatic stop-loss order placement
- Real-time position monitoring

### Daily Limits
- Maximum daily loss: $1000
- Maximum concurrent positions: 10
- Portfolio risk limits

## 📈 Performance Tracking

### Metrics Tracked
- Total trades
- Winning/losing trades
- Win rate
- Total P&L
- Average trade duration
- Position performance

### Database Tables
- `positions` - Open positions
- `orders` - Order history
- `trades` - Completed trades
- `performance_metrics` - Daily performance
- `risk_limits` - Risk management settings

## 🔧 Troubleshooting

### Common Issues

**Bot won't start:**
```bash
# Check dependencies
pip install -r requirements.txt

# Check environment variables
python3 -c "from config import config; print(config.validate_config())"
```

**Can't stop bot:**
```bash
# Force kill
kill -KILL $(cat bot.pid)

# Find and kill by process name
pkill -f "python3 run_bot.py"
```

**No gap-up stocks found:**
- Check if market is open
- Verify Polygon API key
- Check network connection

**Order placement fails:**
- Verify Alpaca credentials
- Check account status
- Ensure sufficient buying power

### Log Analysis
```bash
# View recent logs
tail -f logs/all.log

# Check for errors
tail -f logs/errors.log

# Monitor API calls
tail -f logs/api.log
```

## 🔮 Future Enhancements

### Planned Features
- [ ] Advanced exit strategies (trailing stops, time-based)
- [ ] Multiple strategy support
- [ ] DAS Trading Platform integration
- [ ] Real-time performance dashboard
- [ ] Email/SMS alerts
- [ ] Backtesting framework
- [ ] Machine learning integration

### Strategy Improvements
- [ ] Dynamic stop-loss adjustment
- [ ] Volume profile analysis
- [ ] Market sentiment integration
- [ ] Sector rotation analysis
- [ ] Options trading support

## 📞 Support

### Getting Help
1. Check the logs for error messages
2. Verify all API keys are correct
3. Ensure market is open for testing
4. Review configuration settings

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python3 run_bot.py
```

## ⚠️ Disclaimer

This trading bot is for educational and testing purposes. Trading involves substantial risk of loss and is not suitable for all investors. Past performance does not guarantee future results. Always test thoroughly with paper trading before using real money.

## 📄 License

This project is for educational purposes. Use at your own risk.

---

**Happy Trading! 🚀📈** 