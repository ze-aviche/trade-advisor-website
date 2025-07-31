# 📊 Gap-Trade-Bot Logging System Guide

## 🚀 Overview

The gap-trade-bot now has a comprehensive logging system that provides detailed debugging information and performance metrics. All logs are stored in the `logs/` directory at the project root.

## 📁 Log Files Structure

```
logs/
├── gap_trade_bot_all.log      # All application logs (DEBUG+)
├── gap_trade_bot_errors.log   # Error logs only (ERROR+)
├── gap_trade_bot_api.log      # API request logs
├── gap_trade_bot_performance.log  # Performance metrics
└── gap_trade_bot_cache.log    # Cache operation logs
```

## 🔧 Log Levels

- **DEBUG**: Detailed debugging information
- **INFO**: General application information
- **WARNING**: Warning messages
- **ERROR**: Error messages with stack traces
- **CRITICAL**: Critical errors

## 📊 Log Categories

### **1. Application Logs (`gap_trade_bot_all.log`)**
- All application events
- Function calls and returns
- Data processing steps
- Cache operations
- API interactions

### **2. Error Logs (`gap_trade_bot_errors.log`)**
- Exceptions and errors
- Stack traces
- Error context information
- Failed operations

### **3. API Logs (`gap_trade_bot_api.log`)**
- HTTP request/response details
- Endpoint access
- Request duration
- User agent information

### **4. Performance Logs (`gap_trade_bot_performance.log`)**
- Function execution times
- API call durations
- Batch processing metrics
- Cache hit/miss rates

### **5. Cache Logs (`gap_trade_bot_cache.log`)**
- Cache hits and misses
- Data storage operations
- Cache clearing events
- Delta fetching operations

## 🎯 Key Logging Features

### **Structured Logging**
```
2025-07-30 18:38:22,180 | historical_cache | INFO | historical_cache.py:79 | init_cache_tables() | ✅ Historical data cache tables initialized
```

**Format**: `timestamp | logger_name | level | filename:line | function() | message`

### **Performance Tracking**
```python
# Automatic performance logging
log_performance('batch_daily_data', duration, {
    'ticker': 'WINT',
    'data_points': 251,
    'start_date': '2024-07-30',
    'end_date': '2025-07-30'
})
```

### **Error Context**
```python
# Detailed error logging
log_error(e, {
    'ticker': 'WINT',
    'days': 365,
    'endpoint': 'historical_data'
})
```

### **API Request Logging**
```python
# API request tracking
log_api_request('GET', '/api/historical-data/WINT', 200, duration=0.5)
```

## 🔍 Debugging Examples

### **1. Check API Performance**
```bash
tail -f logs/gap_trade_bot_performance.log
```

### **2. Monitor Errors**
```bash
tail -f logs/gap_trade_bot_errors.log
```

### **3. Track Cache Operations**
```bash
tail -f logs/gap_trade_bot_cache.log
```

### **4. View All Activity**
```bash
tail -f logs/gap_trade_bot_all.log
```

## 🛠️ Usage in Code

### **Import Logging**
```python
from logging_config import get_logger, log_performance, log_error, log_api_request

# Get module logger
logger = get_logger(__name__)
```

### **Performance Logging**
```python
import time

def my_function():
    start_time = time.time()
    try:
        # Your code here
        result = process_data()
        
        duration = time.time() - start_time
        log_performance('my_function', duration, {'data_points': len(result)})
        return result
    except Exception as e:
        duration = time.time() - start_time
        log_error(e, {'function': 'my_function'})
        raise
```

### **API Request Logging**
```python
@app.route('/api/endpoint')
def my_endpoint():
    start_time = time.time()
    try:
        # Process request
        result = process_request()
        
        duration = time.time() - start_time
        log_api_request('GET', '/api/endpoint', 200, duration)
        return jsonify(result)
    except Exception as e:
        duration = time.time() - start_time
        log_api_request('GET', '/api/endpoint', 500, duration)
        log_error(e, {'endpoint': '/api/endpoint'})
        return jsonify({'error': str(e)}), 500
```

## 📈 Performance Monitoring

### **Key Metrics Tracked**
1. **API Response Times**: All endpoint durations
2. **Data Processing**: Batch operations, gap-up detection
3. **Cache Performance**: Hit/miss rates, storage operations
4. **Error Rates**: Exception frequency and types
5. **Resource Usage**: Memory and CPU patterns

### **Sample Performance Log**
```
2025-07-30 18:38:22,205 | performance | INFO | historical_data.py:458 | get_historical_gap_up_data() | ⏱️ historical_gap_up_data | Duration: 0.025s | Details: {'ticker': 'WINT', 'days': 30, 'use_cache': True, 'total_days': 251, 'gap_up_days': 4}
```

## 🔧 Configuration

### **Log Level Setup**
```python
# In your application startup
from logging_config import setup_logging

# Setup with custom log level
setup_logging(log_level='DEBUG', log_dir='logs')
```

### **Log Rotation**
- **All logs**: 10MB max, 5 backup files
- **Error logs**: 5MB max, 3 backup files
- **Performance logs**: 5MB max, 3 backup files
- **API logs**: 5MB max, 3 backup files
- **Cache logs**: 5MB max, 3 backup files

## 🚨 Troubleshooting

### **Common Issues**

1. **Log files not created**
   - Check directory permissions
   - Ensure `logs/` directory exists

2. **Performance logs empty**
   - Verify `log_performance()` calls
   - Check log level configuration

3. **Too much logging**
   - Increase log level to WARNING or ERROR
   - Adjust log rotation settings

### **Debug Commands**
```bash
# Check log file sizes
ls -lh logs/

# Monitor real-time logs
tail -f logs/gap_trade_bot_all.log

# Search for specific errors
grep "ERROR" logs/gap_trade_bot_all.log

# Check performance metrics
grep "Duration" logs/gap_trade_bot_performance.log
```

## 📋 Best Practices

1. **Use appropriate log levels**
   - DEBUG: Detailed debugging
   - INFO: General information
   - WARNING: Potential issues
   - ERROR: Actual errors

2. **Include context in logs**
   - Ticker symbols
   - Request parameters
   - Performance metrics

3. **Monitor log file sizes**
   - Regular cleanup of old logs
   - Adjust rotation settings as needed

4. **Use structured logging**
   - Consistent message format
   - Include relevant metadata

## 🔄 Integration with Existing Code

The logging system is designed to work seamlessly with existing code:

- **Automatic setup**: Called in `app.py` startup
- **Backward compatible**: Existing `logger.info()` calls work
- **Performance tracking**: Added to key functions
- **Error handling**: Enhanced with context

---

*Last Updated: July 30, 2025*
*Version: 1.0* 