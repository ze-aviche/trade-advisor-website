# Gap-Trade-Bot

A real-time trading bot for gap-up stock analysis and automated trading.

## 🚀 Quick Start

```bash
# Start all services
./scripts/start_background.sh

# Check status
./scripts/check_status.sh

# Stop all services
./scripts/stop_background.sh
```

## 📁 Project Structure

```
gap-trade-bot/
├── README.md                    # Main project documentation
├── .gitignore                   # Git ignore rules
├── backend/                     # Backend application
│   ├── app.py                   # Main Flask application
│   ├── auth.py                  # Authentication module
│   ├── config.py                # Backend configuration
│   ├── database.py              # Database operations
│   ├── gap_up_detector.py      # Gap-up detection logic
│   ├── historical_cache.py      # Historical data caching
│   ├── historical_data.py       # Historical data processing
│   ├── logging_config.py        # Logging configuration
│   ├── real_time_detector.py    # Real-time detection
│   ├── requirements.txt         # Python dependencies
│   ├── .env                     # Environment variables
│   ├── bot/                     # Trading bot core
│   │   ├── trading_bot.py       # Main trading bot
│   │   ├── data_manager.py      # Data management
│   │   ├── order_manager.py     # Order management
│   │   ├── position_manager.py  # Position management
│   │   ├── risk_manager.py      # Risk management
│   │   ├── broker_factory.py    # Broker factory
│   │   ├── alpaca_client.py     # Alpaca broker client
│   │   ├── das_client.py        # DAS broker client
│   │   ├── websocket_client.py  # WebSocket client
│   │   ├── broker_websocket_client.py # Broker WebSocket
│   │   ├── trading_database.py  # Trading database
│   │   ├── config.py            # Bot configuration
│   │   ├── run_bot.py           # Bot entry point
│   │   ├── bot.pid              # Bot process ID
│   │   ├── strategies/          # Trading strategies
│   │   ├── data/                # Database files
│   │   ├── docs/                # Bot documentation (19 files)
│   │   ├── logs/                # Bot logs
│   │   ├── scripts/             # Bot scripts (10 files)
│   │   └── tests/               # Bot tests (3 files)
│   ├── data/                    # Database files
│   ├── docs/                    # Backend documentation
│   ├── logs/                    # Backend logs
│   ├── scripts/                 # Backend scripts (3 files)
│   └── tests/                   # Backend tests
├── frontend/                    # Web dashboard
├── scripts/                     # Management scripts
├── tests/                       # Test files
├── docs/                        # Documentation
├── logs/                        # Application logs
└── venv/                        # Python virtual environment
```

## 🔧 Features

- **Real-time Gap-up Detection**: Automatically identifies stocks with significant gaps
- **Enhanced Logging**: Detailed analysis of trading conditions and decisions
- **Web Dashboard**: Real-time monitoring and control interface
- **Risk Management**: Position sizing and stop-loss management
- **Ticker Validation**: Filters out invalid/delisted stocks
- **Organized Structure**: Clean separation of concerns with dedicated directories

## 📊 Monitoring

- **Backend API**: http://localhost:5000
- **Frontend Dashboard**: http://localhost:3000
- **Logs**: 
  - `backend/bot/logs/gap_trade_bot_all.log` - Main bot logs
  - `backend/bot/logs/gap_trade_bot_errors.log` - Bot error logs
  - `backend/logs/gap_trade_backend_all.log` - Backend logs
  - `backend/logs/gap_trade_backend_errors.log` - Backend error logs
  - `frontend/frontend.log` - Frontend logs

**Note**: All logs are organized by service in their respective directories.

## 📚 Documentation

### Main Documentation (`docs/`)
- `ARCHITECTURE_GUIDE.md` - System architecture overview
- `TECHNICAL_GUIDE.md` - Technical implementation details
- `LOGGING_GUIDE.md` - Logging and monitoring
- `OPTIMIZATION_GUIDE.md` - Performance optimization
- `CACHING_GUIDE.md` - Data caching strategies

### Backend Documentation (`backend/docs/`)
- Backend-specific documentation and guides

### Bot Documentation (`backend/bot/docs/`)
- `AUTO_SCHEDULE_SETUP.md` - Automated scheduling setup
- `AVERAGE_VOLUME_STANDARDS.md` - Volume analysis standards
- `BROKER_WEBSOCKET_COMPARISON.md` - Broker WebSocket comparison
- `DAS_IMPLEMENTATION.md` - DAS broker implementation
- `DATABASE_ARCHITECTURE_ANALYSIS.md` - Database architecture
- `DATABASE_REFACTORING_SUMMARY.md` - Database refactoring
- `ENHANCED_STRATEGY_SUMMARY.md` - Strategy enhancements
- `EXIT_MANAGEMENT_ANALYSIS.md` - Exit strategy analysis
- `GAP_UP_DETECTOR_INTEGRATION.md` - Gap-up detection integration
- `LEARNING_GUIDE.md` - Learning and development guide
- `LOG_ROTATION_GUIDE.md` - Log rotation management
- `LOG_ROTATION_SUMMARY.md` - Log rotation summary
- `ORDER_MANAGER_ARCHITECTURE.md` - Order management architecture
- `README.md` - Bot-specific readme
- `RENAME_SUMMARY.md` - Renaming and refactoring summary
- `VOLUME_FORECASTING_SUMMARY.md` - Volume forecasting
- `WEBSOCKET_INTEGRATION.md` - WebSocket integration guide

## 🧪 Testing

### Main Tests (`tests/`)
```bash
# Run ticker validation test
python3 tests/test_ticker_validation.py

# Test WebSocket connections
python3 tests/test_bot_websocket.py
python3 tests/test_polygon_websocket.py
```

### Backend Tests (`backend/tests/`)
```bash
# Backend-specific tests
python3 backend/tests/simple_cache_test.py
```

### Bot Tests (`backend/bot/tests/`)
```bash
# Bot-specific tests
python3 backend/bot/tests/test_alpaca.py
python3 backend/bot/tests/test_trading_database.py
python3 backend/bot/tests/test_volume_multipliers.py
```

## 🔍 Status Commands

```bash
# Check all services
./scripts/check_status.sh

# View recent logs
tail -f backend/bot/logs/gap_trade_bot_all.log
tail -f backend/logs/gap_trade_backend_all.log
tail -f frontend/frontend.log
```

## ⚙️ Configuration

- **Environment variables**: `backend/.env`
- **Backend config**: `backend/config.py`
- **Bot config**: `backend/bot/config.py`
- **API keys**: Configure in respective config files

## 📁 Key Directories

- **`backend/bot/docs/`**: 19 documentation files for bot development
- **`backend/bot/scripts/`**: 10 script files for bot management
- **`backend/bot/tests/`**: 3 test files for bot functionality
- **`backend/bot/data/`**: Database and result files
- **`backend/scripts/`**: 3 prepopulate scripts for data setup
- **`scripts/`**: Main management scripts (start, stop, check status)
- **`docs/`**: Main project documentation
- **`tests/`**: Main test files 