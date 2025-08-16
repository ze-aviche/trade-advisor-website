# Windows Scripts for Gap-Trade-Bot

This directory contains Windows batch scripts for managing the Gap-Trade-Bot services on Windows.

## Available Scripts

### Batch Files (.bat)
- **`check_status.bat`** - Check the status of all Gap-Trade-Bot services
- **`start_services.bat`** - Start all services in the background
- **`stop_services.bat`** - Stop all services

## Usage

Simply double-click or run the `.bat` files from Windows Explorer or Command Prompt:

```cmd
# Check status
check_status.bat

# Start services
start_services.bat

# Stop services
stop_services.bat
```

## Features

### Status Check (`check_status.bat`)
- ✅ Checks if Python processes are running
- 🌐 Displays port status (5000 for backend, 3000 for frontend)
- 📊 Provides summary of all services
- 🎯 Shows service URLs

### Start Services (`start_services.bat`)
- 🚀 Starts trading bot, backend, and frontend in sequence
- 🔍 Validates port availability
- 🛑 Cleans up existing processes
- ⏳ Waits for services to initialize
- 🏥 Tests backend health
- 📋 Creates log directories if needed

### Stop Services (`stop_services.bat`)
- 🛑 Stops all Gap-Trade-Bot processes
- 💀 Graceful shutdown with force kill fallback
- 🧹 Cleans up processes on ports 5000 and 3000
- ✅ Provides status feedback

## Requirements

- **Windows 10/11**
- **Python** installed and in PATH
- **Command Prompt** or **PowerShell**

## Troubleshooting

### Python Not Found
Ensure Python is installed and added to your system PATH. You can verify this by running:
```cmd
python --version
```

### Port Conflicts
If ports 5000 or 3000 are already in use, the scripts will automatically kill the conflicting processes.

### Permission Issues
If you encounter permission issues, run the scripts as Administrator.

## Log Files

The scripts create and manage log files in these locations:
- **Bot logs**: `backend\bot\logs\gap_trade_bot_all.log`
- **Backend logs**: `backend\logs\gap_trade_backend_all.log`
- **Frontend logs**: `frontend\frontend.log`

## Service URLs

Once started, the services will be available at:
- **Backend API**: http://localhost:5000
- **Frontend**: http://localhost:3000
- **Bot Status**: http://localhost:5000/api/bot/status

## Quick Start

1. **Check current status**: `check_status.bat`
2. **Start all services**: `start_services.bat`
3. **Stop all services**: `stop_services.bat`

## Notes

- The scripts use native Windows commands for maximum compatibility
- All scripts include error handling and user-friendly output
- Services are started in the correct order: Bot → Backend → Frontend
- The status check provides real-time information about running services
