# CMDAPI_PYTHON Usage Guide

This guide explains how to use the methods available in `src/core/CMDAPI_PYTHON.py` for implementing trading strategies.

## Available Classes

### 1. Connection Class
**Purpose**: Manages the connection to the DAS Trader Pro server

**Available Methods**:
- `ConnectToServer()` - Establishes connection to DAS server
- `SendScript(script)` - Sends commands to DAS server and returns response
- `Disconnect()` - Closes the connection
- `__enter__()` / `__exit__()` - Context manager support

### 2. cmdAPI Class
**Purpose**: Provides high-level methods for interacting with DAS

**Available Methods**:
- `GetShortInfo(connection, symbol=None)` - Get current market data
- `Subscribe(connection)` - Subscribe to real-time data streams

## Method Details

### GetShortInfo Method
```python
def GetShortInfo(self, connection, symbol=None):
```

**Parameters**:
- `connection`: Connection object
- `symbol`: Optional symbol parameter (if None, prompts user)

**Behavior**:
- **Interactive**: If `symbol=None`, prompts user for input
- **Automated**: If `symbol` is provided, uses that symbol directly

**Usage Examples**:
```python
# Interactive usage (prompts for symbol)
result = cmd.GetShortInfo(connection)

# Automated usage (specify symbol)
result = cmd.GetShortInfo(connection, "AAPL")
```

### Subscribe Method
```python
async def Subscribe(self, connection):
```

**Parameters**:
- `connection`: Connection object

**Behavior**:
- **Interactive**: Prompts user for subscription level and symbol
- **Subscription Levels**:
  - `1` or `"Lv1"` - Level 1 quotes (bid/ask/last)
  - `2` or `"Lv2"` - Level 2 market depth
  - `3` or `"TMS"` - Time & Sales data

**Usage Example**:
```python
# Interactive subscription (prompts for level and symbol)
await cmd.Subscribe(connection)
```

## Current Limitations

### 1. Interactive Methods
Both `GetShortInfo` and `Subscribe` methods use `input()` to prompt for user data, making them unsuitable for automated trading without modification.

### 2. No Direct Symbol Passing
The methods don't accept symbols as parameters in their original form, requiring user interaction.

## Workarounds for Automated Trading

### Option 1: Use Direct Script Sending
Instead of using the high-level methods, send commands directly:

```python
# Get market data for AAPL
script = "GET SHORTINFO AAPL"
result = connection.SendScript(bytearray(script + "\r\n", encoding="ascii"))

# Subscribe to AAPL Level 1 data
script = "SUBSCRIBE AAPL Lv1"
result = connection.SendScript(bytearray(script + "\r\n", encoding="ascii"))
```

### Option 2: Modify the Methods (Not Recommended)
You could modify the original methods to accept parameters, but this would change the original API.

### Option 3: Create Wrapper Methods
Create wrapper methods in your strategy classes:

```python
class BaseStrategy:
    def get_market_data_automated(self, connection, symbol):
        """Automated market data retrieval"""
        script = f"GET SHORTINFO {symbol.upper()}"
        return connection.SendScript(bytearray(script + "\r\n", encoding="ascii"))
    
    async def subscribe_automated(self, connection, symbol, level="Lv1"):
        """Automated subscription"""
        script = f"SUBSCRIBE {symbol.upper()} {level}"
        return connection.SendScript(bytearray(script + "\r\n", encoding="ascii"))
```

## Recommended Implementation for Strategies

### 1. Use Direct Script Sending
```python
class RSIStrategy(BaseStrategy):
    async def get_market_data(self, cmd: cmdAPI, connection: Connection) -> Dict:
        """Get current market data for the symbol"""
        try:
            # Use direct script sending instead of cmd.GetShortInfo
            script = f"GET SHORTINFO {self.symbol}"
            short_info = connection.SendScript(bytearray(script + "\r\n", encoding="ascii"))
            return self.parse_short_info(short_info)
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return {}
```

### 2. Implement Subscription in TradingBot
```python
class TradingBot:
    async def subscribe_to_symbols(self):
        """Subscribe to all strategy symbols"""
        for strategy in self.strategies:
            symbol = strategy.symbol
            script = f"SUBSCRIBE {symbol} Lv1"
            try:
                self.connection.SendScript(bytearray(script + "\r\n", encoding="ascii"))
                logger.info(f"Subscribed to {symbol}")
            except Exception as e:
                logger.error(f"Failed to subscribe to {symbol}: {e}")
```

## Testing the API

Use the provided test scripts:
- `examples/test_cmdapi_simple.py` - Tests method availability without DAS connection
- `examples/test_cmdapi.py` - Full test suite (requires DAS running)

## Best Practices

1. **Always handle exceptions** when calling DAS methods
2. **Use direct script sending** for automated trading
3. **Implement proper connection management** with context managers
4. **Log all API interactions** for debugging
5. **Test thoroughly** before deploying to production

## Example Strategy Implementation

```python
class AutomatedStrategy(BaseStrategy):
    async def get_market_data(self, cmd: cmdAPI, connection: Connection) -> Dict:
        """Automated market data retrieval"""
        try:
            # Direct script sending - no user interaction required
            script = f"GET SHORTINFO {self.symbol}"
            response = connection.SendScript(bytearray(script + "\r\n", encoding="ascii"))
            
            # Parse the response
            return self.parse_das_response(response)
        except Exception as e:
            logger.error(f"Error getting market data for {self.symbol}: {e}")
            return {}
    
    def parse_das_response(self, response):
        """Parse DAS response format"""
        # Implement parsing logic based on DAS response format
        # This will depend on the actual response structure
        return {
            'symbol': self.symbol,
            'price': 0.0,  # Extract from response
            'volume': 0,   # Extract from response
            'timestamp': datetime.now()
        }
```

