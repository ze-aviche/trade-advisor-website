# Configuration Naming Conventions

This document explains the configuration naming conventions used in the trading advisor project.

## Config Files

### 1. Main Backend Config (`config.py`)
- **Purpose**: Flask web application configuration
- **Import**: `from config import config as web_config`
- **Contains**: SECRET_KEY, DEBUG, CORS, Rate Limiting, Cache settings
- **Structure**: Dictionary-based (Flask standard)

### 2. Bot Config (`bot/config.py`)
- **Purpose**: Trading bot configuration
- **Import**: `from bot.config import config as bot_config`
- **Contains**: Trading parameters, API keys, risk management, broker settings
- **Structure**: Class-based with validation methods

## Import Examples

### For Web Application (Flask)
```python
from config import config as web_config
# Use: web_config['development']
```

### For Trading Bot Components
```python
from bot.config import config as bot_config
# Use: bot_config.POLYGON_API_KEY
```

## Why This Naming Convention?

1. **Clarity**: Immediately know which config you're using
2. **Prevents Conflicts**: No more import confusion
3. **Explicit**: Makes code more readable and maintainable
4. **Future-Proof**: Easy to add more configs if needed

## Updated Files

All bot modules now use the explicit naming:
- `bot/websocket_client.py`
- `bot/risk_manager.py`
- `bot/data_manager.py`
- `bot/order_manager.py`
- `bot/broker_factory.py`
- `bot/broker_websocket_client.py`
- `bot/trading_bot.py`
- `bot/alpaca_client.py`
- `bot/das_client.py`
- `bot/strategies/strategy_template.py`
- `bot/strategies/base_backtest.py`

## Benefits

✅ **No more import conflicts**  
✅ **Clear and explicit imports**  
✅ **Easy to understand which config is being used**  
✅ **Maintainable and scalable**  
✅ **Prevents future confusion** 