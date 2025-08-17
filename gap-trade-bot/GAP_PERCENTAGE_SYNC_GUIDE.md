# Gap Percentage Synchronization Guide

## Overview
This guide explains how the `min_gap_percentage` setting is synchronized between the frontend and backend to ensure consistency.

## How It Works

### 1. **Single Source of Truth**
- **Primary Location**: `config.py` - `GAP_UP_MIN_PERCENTAGE = 25.0`
- **All components** read from this single source to ensure consistency

### 2. **Backend Configuration Flow**

#### **Configuration Storage**
```python
# config.py
GAP_UP_MIN_PERCENTAGE = 25.0  # Single source of truth
```

#### **API Endpoints** (`app.py`)
```python
# GET /api/gap-ups/config
# Reads from config.py and returns current value

# POST /api/gap-ups/config  
# Updates config.py file and returns success message
```

#### **Gap-Up Detection** (`gap_up_detector.py`)
```python
# Imports from config.py to ensure synchronization
import config as config_module
GAP_UP_MIN_PERCENTAGE = getattr(config_module, 'GAP_UP_MIN_PERCENTAGE', 25.0)
```

### 3. **Frontend Integration**

#### **Loading Configuration**
```javascript
// app.js - loadGapUpConfig()
const response = await fetch('http://localhost:5000/api/gap-ups/config');
const data = await response.json();
this.gapUpConfig.min_percentage = data.data.min_percentage;
```

#### **Saving Configuration**
```javascript
// app.js - saveGapUpConfig()
const response = await fetch('http://localhost:5000/api/gap-ups/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ min_percentage: this.gapUpConfig.min_percentage })
});
```

#### **Using Configuration**
```javascript
// app.js - loadGapUps()
const response = await fetch(`http://localhost:5000/api/gap-ups?min_percentage=${this.gapUpConfig.min_percentage}`);
```

## Synchronization Points

### 1. **Frontend Load**
- ✅ Loads current value from `/api/gap-ups/config` GET
- ✅ Displays in UI input field
- ✅ Uses for gap-up filtering

### 2. **Frontend Save**
- ✅ Sends new value to `/api/gap-ups/config` POST
- ✅ Updates `config.py` file
- ✅ Reloads gap-ups with new threshold

### 3. **Backend Processing**
- ✅ Reads from `config.py` for all gap-up detection
- ✅ Uses updated value immediately
- ✅ Returns consistent results

## Testing Synchronization

Run the test script to verify synchronization:
```bash
cd gap-trade-bot/backend
python test_gap_percentage_sync.py
```

This test:
1. Gets current configuration
2. Updates to 30%
3. Verifies the update
4. Tests gap-ups endpoint
5. Resets to original value

## Troubleshooting

### **If Values Don't Match:**

1. **Check `config.py`**: Ensure `GAP_UP_MIN_PERCENTAGE` is set correctly
2. **Restart Backend**: Changes to `config.py` require backend restart
3. **Clear Frontend Cache**: Refresh browser or clear localStorage
4. **Check API Response**: Verify `/api/gap-ups/config` returns correct value

### **Common Issues:**

1. **Backend Not Restarted**: Changes to `config.py` require restart
2. **Frontend Cache**: Browser might cache old values
3. **File Permissions**: Backend needs write access to `config.py`
4. **Import Errors**: Check for Python import issues

## Best Practices

1. **Always Use API**: Don't edit `config.py` directly
2. **Restart After Changes**: Backend restart required for config changes
3. **Test Changes**: Use test script to verify synchronization
4. **Monitor Logs**: Check backend logs for configuration errors

## File Locations

- **Configuration**: `backend/config.py`
- **API Endpoints**: `backend/app.py` (lines 183-240)
- **Gap Detection**: `backend/gap_up_detector.py` (lines 290-295)
- **Frontend**: `frontend/app.js` (gapUpConfig methods)
- **Test Script**: `backend/test_gap_percentage_sync.py`

## Summary

The system ensures `min_gap_percentage` synchronization through:
- ✅ Single source of truth in `config.py`
- ✅ API endpoints for reading/writing
- ✅ Consistent imports across all components
- ✅ Frontend integration with real-time updates
- ✅ Test script for verification

This ensures that the frontend and backend always use the same gap percentage threshold for detecting and displaying gap-up stocks.
