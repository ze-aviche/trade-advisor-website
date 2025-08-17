# Enhanced Trading Bot with Position Monitoring

## Overview

The enhanced trading bot integrates position monitoring capabilities from the accentor-trading-bot project, providing automated position management, DAS Trader integration, and real-time exit management.

## Features

### 🔍 Position Monitoring
- **Automatic Discovery**: Discovers existing positions in DAS Trader account
- **Real-time Tracking**: Monitors positions continuously for exit conditions
- **New Position Detection**: Automatically detects manually opened positions
- **Position Cleanup**: Removes closed positions from tracking

### 📊 Exit Management
- **Profit Targets**: Configurable profit target percentages
- **Stop Losses**: Configurable stop loss percentages
- **Automated Exits**: Automatically closes positions when conditions are met
- **P&L Tracking**: Calculates and logs profit/loss for closed positions

### 🔌 DAS Trader Integration
- **Socket Connection**: Direct connection to DAS Trader via CMD API
- **Position Queries**: Real-time position data retrieval
- **Order Execution**: Automated order placement for exits
- **Level 1 Data**: Real-time price data subscriptions

### ⚙️ Configuration
- **Profit Target**: Default 5% profit target (configurable)
- **Stop Loss**: Default 2.5% stop loss (configurable)
- **Monitor Interval**: Default 5-second monitoring cycle (configurable)

## Architecture

### Core Classes

#### `TradingBot`
Main bot class that orchestrates all functionality:
- Manages DAS connection
- Handles position discovery and monitoring
- Controls monitoring thread lifecycle
- Provides status and configuration management

#### `DASConnection`
Handles communication with DAS Trader:
- Socket-based connection to DAS server
- Login and authentication
- Script execution and response handling
- Connection lifecycle management

#### `PositionParser`
Parses DAS position data:
- Converts raw DAS position strings to structured data
- Validates position information
- Handles both LONG and SHORT positions

#### `PriceManager`
Manages real-time price data:
- Level 1 data subscriptions
- Price caching and retrieval
- Symbol subscription management

#### `ExitConditionChecker`
Evaluates exit conditions:
- Profit target checking
- Stop loss validation
- Position type-specific logic

#### `OrderManager`
Handles order execution:
- Market order placement
- Position closing logic
- Order result validation

### Data Structures

#### `Position`
```python
@dataclass
class Position:
    symbol: str
    type: str  # "LONG" or "SHORT"
    size: int
    entry_price: float
    profit_target: float
    stop_loss: float
    entry_time: float
    position_id: str
```

#### `PriceData`
```python
@dataclass
class PriceData:
    ask: float = 0.0
    bid: float = 0.0
    last: float = 0.0
    timestamp: float = 0.0
```

## API Endpoints

### Bot Status
- `GET /api/bot/status` - Get bot status and monitoring state

### Bot Control
- `POST /api/bot/start` - Start the trading bot
- `POST /api/bot/stop` - Stop the trading bot

### Position Management
- `GET /api/bot/positions` - Get current active positions
- `POST /api/bot/discover-positions` - Manually trigger position discovery

### Configuration
- `GET /api/bot/config` - Get current bot configuration
- `POST /api/bot/config` - Update bot configuration

### Strategy Management
- `POST /api/bot/update-strategies` - Update trading strategies
- `POST /api/bot/unsubscribe-stocks` - Unsubscribe from stock updates

## Usage

### Basic Usage

```python
from bot.trading_bot import TradingBot

# Create bot with configuration
config = {
    'profit_target_pct': 5.0,    # 5% profit target
    'stop_loss_pct': 2.5,        # 2.5% stop loss
    'monitor_interval': 5         # 5-second monitoring cycle
}

bot = TradingBot(config)

# Start the bot
success = bot.start()
if success:
    print("Bot started successfully")
    
    # Bot will automatically:
    # 1. Connect to DAS Trader
    # 2. Discover existing positions
    # 3. Start monitoring positions
    # 4. Execute exits when conditions are met
```

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `profit_target_pct` | 5.0 | Profit target percentage |
| `stop_loss_pct` | 2.5 | Stop loss percentage |
| `monitor_interval` | 5 | Monitoring cycle interval in seconds |

### DAS Trader Setup

1. **Enable CMD API**: In DAS Trader, enable the CMD API feature
2. **Configure Login**: Update login credentials in `DASConnection.ConnectToServer()`
3. **Port Configuration**: Default port is 9800 (configurable)

## Monitoring Workflow

### 1. Position Discovery
- Bot connects to DAS Trader
- Retrieves current positions using `GET POSITIONS`
- Parses position data and creates `Position` objects
- Calculates profit targets and stop losses
- Subscribes to Level 1 data for each position

### 2. Continuous Monitoring
- Runs in a separate thread with configurable interval
- Checks each active position for exit conditions
- Updates price data for monitored symbols
- Detects new positions opened manually
- Removes closed positions from tracking

### 3. Exit Execution
- When exit conditions are met:
  - Places market order to close position
  - Calculates and logs P&L
  - Removes position from tracking
  - Unsubscribes from price data

## Error Handling

### Connection Errors
- Automatic retry logic for DAS connection
- Graceful handling of connection failures
- Logging of connection issues

### Order Errors
- SSR (Short Sale Restriction) detection
- Order failure handling
- Position tracking cleanup

### Data Errors
- Invalid position data handling
- Price data validation
- Parsing error recovery

## Logging

The bot provides comprehensive logging:
- Connection events
- Position discovery and tracking
- Price updates and exit conditions
- Order execution results
- Error conditions and recovery

## Testing

Run the test script to verify functionality:

```bash
python test_enhanced_bot.py
```

This will test:
- Bot import and creation
- Position parsing
- DAS connection (if available)
- API endpoints
- Bot lifecycle

## Future Enhancements

### Entry Automation
- Automated entry signals based on technical analysis
- Entry order placement
- Risk management for new positions

### Advanced Strategies
- Multiple strategy support
- Strategy-specific exit conditions
- Portfolio-level risk management

### Enhanced Monitoring
- WebSocket-based real-time updates
- Dashboard integration
- Performance analytics

### Risk Management
- Position sizing algorithms
- Portfolio-level stop losses
- Maximum drawdown protection

## Dependencies

- `socket` - DAS Trader communication
- `threading` - Background monitoring
- `dataclasses` - Data structures
- `logging` - Logging functionality
- `time` - Timing and intervals
- `uuid` - Unique identifiers

## Security Considerations

- DAS Trader credentials should be stored securely
- Network communication should be encrypted
- Order execution should be validated
- Position data should be verified

## Troubleshooting

### Common Issues

1. **DAS Connection Failed**
   - Verify DAS Trader is running
   - Check CMD API is enabled
   - Validate login credentials
   - Confirm port configuration

2. **Position Discovery Issues**
   - Check DAS position format
   - Verify account has positions
   - Review position parsing logic

3. **Exit Order Failures**
   - Check for SSR restrictions
   - Verify position still exists
   - Review order format

4. **Price Data Issues**
   - Check Level 1 subscriptions
   - Verify symbol format
   - Review price parsing logic

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger('bot.trading_bot').setLevel(logging.DEBUG)
```

## Support

For issues and questions:
1. Check the logs for error details
2. Verify DAS Trader configuration
3. Test with the provided test script
4. Review the troubleshooting section
