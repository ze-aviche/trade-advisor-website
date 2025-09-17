# DAS Pro Startup and Management Scripts

This directory contains comprehensive scripts for starting DAS Pro and managing connections for automated trading operations.

## 📁 Files Overview

### Core Scripts
- **`start_das_pro.py`** - Main DAS Pro startup and connection script
- **`das_utils.py`** - Utility functions for DAS Pro operations
- **`das_config.json`** - Configuration file for DAS Pro settings

### Startup Scripts
- **`start_das.bat`** - Windows batch file for easy startup
- **`start_das.ps1`** - PowerShell script for Windows users

## 🚀 Quick Start

### Option 1: Using Batch File (Windows)
```bash
# Double-click or run from command prompt
start_das.bat
```

### Option 2: Using PowerShell (Windows)
```powershell
# Run from PowerShell
.\start_das.ps1
```

### Option 3: Direct Python Execution
```bash
# From the backend directory
python start_das_pro.py
```

## ⚙️ Configuration

### DAS Configuration File (`das_config.json`)

```json
{
  "das_path": "",                    // Path to DAS Pro executable (auto-detected if empty)
  "host": "127.0.0.1",              // DAS Pro server host
  "port": 9800,                     // DAS Pro server port
  "userid": "IDAS12181",            // Your DAS Pro user ID
  "password": "Dastrader@2",        // Your DAS Pro password
  "account": "TRIDAS12181",         // Your DAS Pro account
  "startup_timeout": 30,            // Timeout for DAS Pro startup (seconds)
  "connection_timeout": 10,         // Timeout for connection attempts (seconds)
  "retry_attempts": 3,              // Number of retry attempts for connection
  "retry_delay": 2                  // Delay between retry attempts (seconds)
}
```

### Updating Configuration

1. **Edit the JSON file directly**:
   ```bash
   # Edit das_config.json with your credentials
   ```

2. **Use the utility script**:
   ```bash
   python das_utils.py
   # Select option 11 to update configuration
   ```

## 🔧 Usage Examples

### Basic Startup
```python
from start_das_pro import DASProManager

# Create manager instance
das_manager = DASProManager()

# Start DAS Pro and connect
if das_manager.start_and_connect():
    print("✅ DAS Pro is ready!")
else:
    print("❌ Failed to start DAS Pro")
```

### Using Utility Functions
```python
from das_utils import DASUtils

# Create utility instance
utils = DASUtils()

# Quick start
if utils.quick_start():
    print("✅ DAS Pro started!")

# Get account information
account_info = utils.get_account_info()
print(f"Account: {account_info}")

# Get current positions
positions = utils.get_positions()
print(f"Positions: {positions}")
```

### Integration with Trading Bot
```python
from start_das_pro import DASProManager
from das_integration import das_trade_manager

# Start DAS Pro
das_manager = DASProManager()
if das_manager.start_and_connect():
    # Now you can use the existing DAS integration
    success, message, count = das_trade_manager.sync_trades_from_das()
    print(f"Synced {count} trades: {message}")
```

## 📊 Status Monitoring

### Check DAS Status
```python
from das_utils import DASUtils

utils = DASUtils()
status = utils.check_das_status()

print(f"DAS Running: {status['is_running']}")
print(f"Connected: {status['is_connected']}")
print(f"Process ID: {status['process_id']}")
```

### Export Status Report
```python
from das_utils import DASUtils

utils = DASUtils()
report_file = utils.export_status_report()
print(f"Status report saved to: {report_file}")
```

## 🛠️ Troubleshooting

### Common Issues

1. **DAS Pro Not Found**
   ```
   ❌ DAS Pro executable not found in common locations
   ```
   **Solution**: Update `das_path` in `das_config.json` with the correct path to your DAS Pro installation.

2. **Connection Timeout**
   ```
   ❌ DAS Pro failed to start within 30 seconds
   ```
   **Solution**: Increase `startup_timeout` in configuration or check if DAS Pro is already running.

3. **Authentication Failed**
   ```
   ❌ Connection test failed
   ```
   **Solution**: Verify your `userid`, `password`, and `account` in `das_config.json`.

### Debug Mode
Enable debug logging by modifying the logging configuration:
```python
import logging
logging.getLogger('das_startup').setLevel(logging.DEBUG)
```

### Manual Testing
```bash
# Test connection without starting DAS Pro
python -c "from das_utils import DASUtils; utils = DASUtils(); print(utils.check_das_status())"
```

## 🔄 Integration with Existing Code

### With Trading Bot
The startup scripts are designed to work seamlessly with the existing trading bot infrastructure:

```python
# In your trading bot initialization
from start_das_pro import DASProManager

class TradingBot:
    def __init__(self):
        self.das_manager = DASProManager()
        
    def start(self):
        # Start DAS Pro first
        if not self.das_manager.start_and_connect():
            raise Exception("Failed to start DAS Pro")
        
        # Continue with bot initialization
        # ... rest of your bot code
```

### With Scheduled Sync
```python
# In your scheduled sync service
from start_das_pro import DASProManager
from scheduled_das_sync import scheduled_sync

# Ensure DAS Pro is running before starting sync
das_manager = DASProManager()
if das_manager.start_and_connect():
    scheduled_sync.start_scheduler()
```

## 📝 Logging

All scripts use the existing logging configuration from `logging_config.py`. Logs are written to:
- `logs/gap_trade_backend_all.log` - All log messages
- `logs/gap_trade_backend_errors.log` - Error messages only

## 🔒 Security Notes

1. **Credentials**: The `das_config.json` file contains sensitive information. Ensure it's not committed to version control.
2. **File Permissions**: Set appropriate file permissions on the configuration file.
3. **Network**: DAS Pro runs on localhost by default, which is secure for local operations.

## 🆘 Support

If you encounter issues:

1. Check the log files for detailed error messages
2. Verify your DAS Pro installation and credentials
3. Test the connection manually using the utility script
4. Export a status report for debugging

## 📋 Requirements

- Python 3.7+
- DAS Pro installed and licensed
- Windows operating system (for DAS Pro)
- Required Python packages (see `requirements.txt`)

## 🔄 Updates

To update the scripts:
1. Backup your `das_config.json` file
2. Replace the script files
3. Restore your configuration
4. Test the startup process
