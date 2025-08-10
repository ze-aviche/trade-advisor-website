USED DBs: 

gap-trade-bot/backend/trading_advisor.db (110KB) - Main application database
Users, sessions, historical data cache
Used by: database.py, historical_cache.py, config.py
gap-trade-bot/backend/bot/trading_positions.db (86KB) - Trading bot database
Positions, orders, trades
Used by: trading_database.py
gap-trade-bot/backend/bot/strategies/gap_up_history.db (90KB) - Gap-up historical data
Historical gap-up data for backtesting
Used by: gap_up_detector.py, gap_up_db.py, fetch_gap_up_history.py
gap-trade-bot/backend/bot/data/gap_up_cache.db (0KB) - Gap-up cache database
Caching system for gap-up detection
Used by: gap_up_db.py