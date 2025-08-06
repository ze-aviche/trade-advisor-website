# 🧪 **Test Suite Documentation**

This directory contains comprehensive test suites for the gap-trade-bot system, organized by functionality.

## 📁 **Test Categories**

### 🔍 **Gap Tracking Tests** (`gap_tracking/`)
Tests for the new gap tracking system that prevents overkill detection.

**Files:**
- `test_gap_tracker.py` - Comprehensive tests for peak detection and drop tracking

**Features Tested:**
- ✅ Peak gap detection and tracking
- ✅ Significant drop detection for shorting
- ✅ Overkill prevention (no repeated detections)
- ✅ Multi-stock tracking
- ✅ Data persistence across sessions
- ✅ Edge cases and error handling

### 📊 **Position Sizing Tests** (`position_sizing/`)
Tests for the advanced position sizing system.

**Files:**
- `test_position_sizing.py` - Tests position size calculations
- `test_positions.py` - Tests current position retrieval
- `test_position_check.py` - Tests position validation

**Features Tested:**
- ✅ Risk-based position sizing
- ✅ Price-based limits
- ✅ Portfolio concentration checks
- ✅ Account-based capital calculation
- ✅ Small account optimization

### 🤖 **Bot Integration Tests** (`bot_integration/`)
Tests for the complete bot integration and workflow.

**Files:**
- `test_bot_integration.py` - Tests bot's internal logic
- `test_real_trading.py` - Tests real trading scenarios
- `test_realistic_conditions.py` - Tests realistic market conditions

**Features Tested:**
- ✅ Strategy selection logic
- ✅ Entry/exit signal validation
- ✅ Position management
- ✅ Risk management integration
- ✅ Real-time data processing

### 🌐 **API Tests** (`api/`)
Tests for web API endpoints and frontend integration.

**Files:**
- `test_bot_status.py` - Tests bot status endpoint
- `test_web_api.py` - Tests web API functionality
- `test_trades.py` - Tests trade history endpoints
- `test_unsubscribe.py` - Tests unsubscribe functionality
- `test_auto_sync.py` - Tests automatic sync features
- `check_account.py` - Tests Alpaca account integration

**Features Tested:**
- ✅ REST API endpoints
- ✅ Real-time data updates
- ✅ Frontend-backend communication
- ✅ Error handling and validation
- ✅ Authentication and security

### 🎯 **Strategy Tests** (`strategies/`)
Tests for trading strategies and AI agent integration.

**Files:**
- `test_ai_agent.py` - Tests AI agent functionality

**Features Tested:**
- ✅ Strategy analysis
- ✅ AI agent integration
- ✅ Decision making logic

## 🚀 **Running Tests**

### **Run All Tests**
```bash
# From the backend directory
python3 -m pytest tests/ -v
```

### **Run Specific Test Category**
```bash
# Gap tracking tests
python3 tests/gap_tracking/test_gap_tracker.py

# Position sizing tests
python3 tests/position_sizing/test_position_sizing.py

# Bot integration tests
python3 tests/bot_integration/test_bot_integration.py

# API tests
python3 tests/api/test_bot_status.py
```

### **Run Individual Test Files**
```bash
# Test gap tracking
python3 tests/gap_tracking/test_gap_tracker.py

# Test position sizing
python3 tests/position_sizing/test_position_sizing.py

# Test bot integration
python3 tests/bot_integration/test_bot_integration.py
```

## 📋 **Test Requirements**

### **Dependencies**
- Python 3.8+
- pytest (for automated testing)
- All bot dependencies (see `requirements.txt`)

### **Environment Setup**
```bash
# Install test dependencies
pip install pytest pytest-cov

# Set up environment variables
export POLYGON_API_KEY="your_api_key"
export ALPACA_API_KEY="your_api_key"
export ALPACA_SECRET_KEY="your_secret_key"
```

## 📊 **Test Coverage**

### **Gap Tracking System**
- ✅ Peak detection accuracy
- ✅ Drop tracking precision
- ✅ Overkill prevention
- ✅ Multi-stock handling
- ✅ Data persistence
- ✅ Edge case handling

### **Position Sizing System**
- ✅ Risk calculation accuracy
- ✅ Price-based limits
- ✅ Account size adaptation
- ✅ Portfolio concentration
- ✅ Small account optimization

### **Bot Integration**
- ✅ Strategy selection
- ✅ Entry signal validation
- ✅ Position management
- ✅ Risk management
- ✅ Real-time processing

### **API Integration**
- ✅ Endpoint functionality
- ✅ Data validation
- ✅ Error handling
- ✅ Authentication
- ✅ Real-time updates

## 🔧 **Adding New Tests**

### **Test File Structure**
```python
#!/usr/bin/env python3
"""
Test description and purpose
"""

import sys
import os
from datetime import datetime

# Add parent directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

def test_feature_name():
    """Test description"""
    # Test implementation
    pass

if __name__ == "__main__":
    test_feature_name()
```

### **Test Categories**
1. **Unit Tests** - Test individual functions
2. **Integration Tests** - Test component interactions
3. **End-to-End Tests** - Test complete workflows
4. **Performance Tests** - Test system performance
5. **Edge Case Tests** - Test boundary conditions

## 📈 **Test Results**

### **Success Criteria**
- ✅ All tests pass
- ✅ No false positives
- ✅ Proper error handling
- ✅ Performance within limits
- ✅ Memory usage acceptable

### **Reporting**
Test results are logged to:
- Console output for immediate feedback
- Log files for detailed analysis
- Coverage reports for completeness

## 🐛 **Debugging Tests**

### **Common Issues**
1. **Import Errors** - Check path setup
2. **API Errors** - Verify API keys
3. **Database Errors** - Check database connectivity
4. **Timeout Errors** - Increase timeout values

### **Debug Commands**
```bash
# Run with verbose output
python3 -m pytest tests/ -v -s

# Run with coverage
python3 -m pytest tests/ --cov=. --cov-report=html

# Run specific test with debug
python3 -m pytest tests/test_file.py::test_function -v -s
```

## 📚 **Documentation**

Each test category has its own README file with specific documentation:
- `gap_tracking/README.md` - Gap tracking test documentation
- `position_sizing/README.md` - Position sizing test documentation
- `bot_integration/README.md` - Bot integration test documentation
- `api/README.md` - API test documentation
- `strategies/README.md` - Strategy test documentation 