# 🤖 Auto Schedule Setup Guide

This guide explains how to set up automatic scheduling for the **complete Gap Trade Bot system** (frontend, backend, and trading bot) to start at 5 AM ET and stop at 8 PM ET on both Linux and Windows.

## 📅 Schedule Overview

- **Start Time**: 5:00 AM ET (Eastern Time)
- **Stop Time**: 8:00 PM ET (Eastern Time)
- **Days**: Monday through Friday (trading days only)
- **Timezone**: All times are in Eastern Time (ET)

## 🏗️ System Components

The auto-schedule system manages **three components**:

1. **🤖 Trading Bot** (`run_bot.py`)
   - Automated gap-up stock trading
   - Real-time market data processing
   - Order execution and position management

2. **🚀 Backend Server** (`backend/app.py`)
   - Flask web server (port 5000)
   - API endpoints for data
   - WebSocket connections
   - Database management

3. **🌐 Frontend Server** (`frontend/`)
   - HTTP server (port 3000)
   - Web interface for monitoring
   - Real-time dashboard

## 🐧 Linux Setup

### Prerequisites
- Linux system with cron service running
- Python 3.8+ installed
- Virtual environment set up
- All dependencies installed

### Installation Steps

1. **Navigate to bot directory:**
   ```bash
   cd backend/bot
   ```

2. **Make script executable:**
   ```bash
   chmod +x auto_schedule_full_linux.sh
   ```

3. **Test the script:**
   ```bash
   ./auto_schedule_full_linux.sh check
   ```

4. **Setup auto scheduling:**
   ```bash
   ./auto_schedule_full_linux.sh setup
   ```

5. **Verify installation:**
   ```bash
   ./auto_schedule_full_linux.sh status
   ```

### Linux Commands

| Command | Description |
|---------|-------------|
| `./auto_schedule_full_linux.sh start` | Start all components (backend, frontend, bot) |
| `./auto_schedule_full_linux.sh stop` | Stop all components |
| `./auto_schedule_full_linux.sh check` | Check status of all components |
| `./auto_schedule_full_linux.sh setup` | Install cron jobs for auto scheduling |
| `./auto_schedule_full_linux.sh remove` | Remove cron jobs |
| `./auto_schedule_full_linux.sh status` | Show system status and cron jobs |

### Cron Jobs Created

The setup script creates these cron jobs:

```bash
# Gap Trade Bot Full System - Auto Schedule
0 10 * * 1-5 /path/to/bot/auto_schedule_full_linux.sh start >> /path/to/bot/auto_schedule_full.log 2>&1
0 1 * * 2-6 /path/to/bot/auto_schedule_full_linux.sh stop >> /path/to/bot/auto_schedule_full.log 2>&1
```

- **Start**: 10:00 AM UTC (5:00 AM ET) Monday-Friday
- **Stop**: 1:00 AM UTC (8:00 PM ET) Tuesday-Saturday

## 🪟 Windows Setup

### Prerequisites
- Windows 10/11 or Windows Server
- Python 3.8+ installed
- Virtual environment set up
- All dependencies installed
- Administrator privileges (for Task Scheduler)

### Installation Steps

1. **Open Command Prompt as Administrator**

2. **Navigate to bot directory:**
   ```cmd
   cd backend\bot
   ```

3. **Test the script:**
   ```cmd
   auto_schedule_full_windows.bat check
   ```

4. **Setup auto scheduling:**
   ```cmd
   auto_schedule_full_windows.bat setup
   ```

5. **Verify installation:**
   ```cmd
   auto_schedule_full_windows.bat status
   ```

### Windows Commands

| Command | Description |
|---------|-------------|
| `auto_schedule_full_windows.bat start` | Start all components (backend, frontend, bot) |
| `auto_schedule_full_windows.bat stop` | Stop all components |
| `auto_schedule_full_windows.bat check` | Check status of all components |
| `auto_schedule_full_windows.bat setup` | Install scheduled tasks |
| `auto_schedule_full_windows.bat remove` | Remove scheduled tasks |
| `auto_schedule_full_windows.bat status` | Show system status and scheduled tasks |

### Scheduled Tasks Created

The setup script creates these Windows scheduled tasks:

- **GapTradeBot_Full_Start**: Runs daily at 10:00 AM UTC (5:00 AM ET)
- **GapTradeBot_Full_Stop**: Runs daily at 1:00 AM UTC (8:00 PM ET)

## 🔧 Configuration

### Timezone Considerations

The scripts use UTC times internally to avoid daylight saving time issues:

| Local Time (ET) | UTC Time | Purpose |
|-----------------|----------|---------|
| 5:00 AM ET | 10:00 AM UTC | System Start |
| 8:00 PM ET | 1:00 AM UTC (next day) | System Stop |

### Startup Sequence

The system starts components in this order:

1. **Backend Server** (Flask app on port 5000)
2. **Frontend Server** (HTTP server on port 3000)
3. **Trading Bot** (Automated trading)

### Shutdown Sequence

The system stops components in this order:

1. **Trading Bot** (Most important - stop trading first)
2. **Frontend Server** (Stop web interface)
3. **Backend Server** (Stop API and database connections)

### Customizing Times

To change the schedule, edit the scripts:

**Linux (`auto_schedule_full_linux.sh`):**
```bash
# Change these lines in setup_cron() function
echo "0 10 * * 1-5 $BOT_DIR/auto_schedule_full_linux.sh start >> $LOG_FILE 2>&1" >> "$CRON_TEMP"
echo "0 1 * * 2-6 $BOT_DIR/auto_schedule_full_linux.sh stop >> $LOG_FILE 2>&1" >> "$CRON_TEMP"
```

**Windows (`auto_schedule_full_windows.bat`):**
```cmd
REM Change these lines in setup_tasks section
schtasks /create /tn "GapTradeBot_Full_Start" /tr "cmd /c \"%BOT_DIR%!SCRIPT_NAME! start\"" /sc daily /st 10:00 /f /ru System /rl highest
schtasks /create /tn "GapTradeBot_Full_Stop" /tr "cmd /c \"%BOT_DIR%!SCRIPT_NAME! stop\"" /sc daily /st 01:00 /f /ru System /rl highest
```

## 📊 Monitoring

### Log Files

Both scripts create comprehensive log files:

- **Linux**: `auto_schedule_full.log`
- **Windows**: `auto_schedule_full.log`
- **Backend**: `backend.log`
- **Frontend**: `frontend.log`
- **Bot**: `bot_auto.log`

### Manual Monitoring

**Linux:**
```bash
# Check system status
./auto_schedule_full_linux.sh check

# View recent logs
tail -f auto_schedule_full.log

# Check cron jobs
crontab -l | grep "Gap Trade Bot Full System"
```

**Windows:**
```cmd
# Check system status
auto_schedule_full_windows.bat check

# View recent logs
type auto_schedule_full.log

# Check scheduled tasks
schtasks /query /tn "GapTradeBot_Full_Start"
schtasks /query /tn "GapTradeBot_Full_Stop"
```

### System Status Output

The status command shows:

```
🤖 Trading Bot:
  ✅ Running (PID: 12345)

🌐 Frontend:
  ✅ Running (PID: 12346) - http://localhost:3000

🚀 Backend:
  ✅ Running (PID: 12347) - http://localhost:5000
```

### Access Points

When the system is running, you can access:

- **Frontend Dashboard**: http://localhost:3000
- **Backend API**: http://localhost:5000
- **Trading Bot**: Running in background with logs

## 🛠️ Troubleshooting

### Common Issues

**System won't start automatically:**
1. Check if virtual environment exists
2. Verify Python path in scripts
3. Check log files for errors
4. Ensure cron/Task Scheduler is running
5. Verify all dependencies are installed

**Components stop unexpectedly:**
1. Check system resources (CPU, memory)
2. Review error logs for each component
3. Verify API credentials
4. Check network connectivity
5. Ensure ports 3000 and 5000 are available

**Scheduled tasks not running:**
1. **Linux**: Check cron service status
2. **Windows**: Verify Task Scheduler service
3. Check user permissions
4. Review system logs

### Debug Commands

**Linux:**
```bash
# Check cron service
sudo systemctl status cron

# View cron logs
sudo tail -f /var/log/cron

# Test manual start
./auto_schedule_full_linux.sh start

# Check individual components
ps aux | grep python
netstat -tlnp | grep -E "(3000|5000)"
```

**Windows:**
```cmd
# Check Task Scheduler service
sc query Schedule

# View Task Scheduler events
eventvwr.msc

# Test manual start
auto_schedule_full_windows.bat start

# Check individual components
tasklist | findstr python
netstat -an | findstr ":3000\|:5000"
```

### Component-Specific Issues

**Backend Issues:**
- Check Flask app logs in `backend.log`
- Verify database connections
- Check API endpoints

**Frontend Issues:**
- Check HTTP server logs in `frontend.log`
- Verify static files are accessible
- Check browser console for errors

**Bot Issues:**
- Check bot logs in `bot_auto.log`
- Verify Alpaca API credentials
- Check market data connections

## 🔄 Maintenance

### Regular Maintenance

1. **Weekly**: Check all log files for errors
2. **Monthly**: Review scheduled task status
3. **Quarterly**: Update all dependencies
4. **Annually**: Review and update schedule times

### Updating Schedule

To change the schedule:

1. **Remove existing schedule:**
   ```bash
   # Linux
   ./auto_schedule_full_linux.sh remove
   
   # Windows
   auto_schedule_full_windows.bat remove
   ```

2. **Edit script with new times**

3. **Reinstall schedule:**
   ```bash
   # Linux
   ./auto_schedule_full_linux.sh setup
   
   # Windows
   auto_schedule_full_windows.bat setup
   ```

### Performance Monitoring

Monitor these metrics:

- **CPU Usage**: All three components
- **Memory Usage**: Especially bot during trading
- **Network**: API calls and data streaming
- **Disk Space**: Log files and databases
- **Port Usage**: 3000 (frontend) and 5000 (backend)

## ⚠️ Important Notes

### Security Considerations

- **Linux**: Scripts run with user permissions
- **Windows**: Tasks run with System privileges
- **Logs**: May contain sensitive trading information
- **PID files**: Should be protected from unauthorized access
- **Ports**: Ensure 3000 and 5000 are not exposed publicly

### Performance Considerations

- **Startup time**: Full system takes 60-90 seconds to initialize
- **Shutdown time**: Graceful shutdown takes 15-30 seconds
- **Resource usage**: Monitor CPU and memory usage across all components
- **Network**: Ensure stable internet connection for all components

### Backup Recommendations

- **Configuration**: Backup `.env` file
- **Database**: Backup `trading_positions.db` and `trading_advisor.db`
- **Logs**: Archive old log files regularly
- **Scripts**: Version control all scripts
- **Frontend**: Backup static files and configurations

## 📞 Support

### Getting Help

1. **Check logs first**: `auto_schedule_full.log`
2. **Test manually**: Run start/stop commands manually
3. **Verify environment**: Ensure Python and all dependencies are correct
4. **Check permissions**: Ensure proper file and service permissions
5. **Component isolation**: Test each component individually

### Emergency Stop

If the system needs to be stopped immediately:

**Linux:**
```bash
# Stop all components
./auto_schedule_full_linux.sh stop

# Force kill all Python processes
pkill -f "python3"
```

**Windows:**
```cmd
# Stop all components
auto_schedule_full_windows.bat stop

# Force kill all Python processes
taskkill /F /IM python.exe
```

### Recovery Procedures

**If components fail to start:**
1. Check individual component logs
2. Restart components one by one
3. Verify dependencies and configurations
4. Check system resources

**If scheduled tasks fail:**
1. Test manual start/stop commands
2. Check system services (cron/Task Scheduler)
3. Verify file permissions
4. Review system logs

---

**Happy Automated Trading! 🚀📈** 