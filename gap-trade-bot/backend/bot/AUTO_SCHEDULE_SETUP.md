# 🤖 Auto Schedule Setup Guide

This guide explains how to set up automatic scheduling for the Gap Trade Bot to start at 5 AM ET and stop at 8 PM ET on both Linux and Windows.

## 📅 Schedule Overview

- **Start Time**: 5:00 AM ET (Eastern Time)
- **Stop Time**: 8:00 PM ET (Eastern Time)
- **Days**: Monday through Friday (trading days only)
- **Timezone**: All times are in Eastern Time (ET)

## 🐧 Linux Setup

### Prerequisites
- Linux system with cron service running
- Python 3.8+ installed
- Virtual environment set up
- Bot dependencies installed

### Installation Steps

1. **Navigate to bot directory:**
   ```bash
   cd backend/bot
   ```

2. **Make script executable:**
   ```bash
   chmod +x auto_schedule_linux.sh
   ```

3. **Test the script:**
   ```bash
   ./auto_schedule_linux.sh check
   ```

4. **Setup auto scheduling:**
   ```bash
   ./auto_schedule_linux.sh setup
   ```

5. **Verify installation:**
   ```bash
   ./auto_schedule_linux.sh status
   ```

### Linux Commands

| Command | Description |
|---------|-------------|
| `./auto_schedule_linux.sh start` | Start the bot manually |
| `./auto_schedule_linux.sh stop` | Stop the bot manually |
| `./auto_schedule_linux.sh check` | Check if bot is running |
| `./auto_schedule_linux.sh setup` | Install cron jobs |
| `./auto_schedule_linux.sh remove` | Remove cron jobs |
| `./auto_schedule_linux.sh status` | Show cron and bot status |

### Cron Jobs Created

The setup script creates these cron jobs:

```bash
# Gap Trade Bot - Auto Schedule
0 10 * * 1-5 /path/to/bot/auto_schedule_linux.sh start >> /path/to/bot/auto_schedule.log 2>&1
0 1 * * 2-6 /path/to/bot/auto_schedule_linux.sh stop >> /path/to/bot/auto_schedule.log 2>&1
```

- **Start**: 10:00 AM UTC (5:00 AM ET) Monday-Friday
- **Stop**: 1:00 AM UTC (8:00 PM ET) Tuesday-Saturday

## 🪟 Windows Setup

### Prerequisites
- Windows 10/11 or Windows Server
- Python 3.8+ installed
- Virtual environment set up
- Bot dependencies installed
- Administrator privileges (for Task Scheduler)

### Installation Steps

1. **Open Command Prompt as Administrator**

2. **Navigate to bot directory:**
   ```cmd
   cd backend\bot
   ```

3. **Test the script:**
   ```cmd
   auto_schedule_windows.bat check
   ```

4. **Setup auto scheduling:**
   ```cmd
   auto_schedule_windows.bat setup
   ```

5. **Verify installation:**
   ```cmd
   auto_schedule_windows.bat status
   ```

### Windows Commands

| Command | Description |
|---------|-------------|
| `auto_schedule_windows.bat start` | Start the bot manually |
| `auto_schedule_windows.bat stop` | Stop the bot manually |
| `auto_schedule_windows.bat check` | Check if bot is running |
| `auto_schedule_windows.bat setup` | Install scheduled tasks |
| `auto_schedule_windows.bat remove` | Remove scheduled tasks |
| `auto_schedule_windows.bat status` | Show task and bot status |

### Scheduled Tasks Created

The setup script creates these Windows scheduled tasks:

- **GapTradeBot_Start**: Runs daily at 10:00 AM UTC (5:00 AM ET)
- **GapTradeBot_Stop**: Runs daily at 1:00 AM UTC (8:00 PM ET)

## 🔧 Configuration

### Timezone Considerations

The scripts use UTC times internally to avoid daylight saving time issues:

| Local Time (ET) | UTC Time | Purpose |
|-----------------|----------|---------|
| 5:00 AM ET | 10:00 AM UTC | Bot Start |
| 8:00 PM ET | 1:00 AM UTC (next day) | Bot Stop |

### Customizing Times

To change the schedule, edit the scripts:

**Linux (`auto_schedule_linux.sh`):**
```bash
# Change these lines in setup_cron() function
echo "0 10 * * 1-5 $BOT_DIR/auto_schedule_linux.sh start >> $LOG_FILE 2>&1" >> "$CRON_TEMP"
echo "0 1 * * 2-6 $BOT_DIR/auto_schedule_linux.sh stop >> $LOG_FILE 2>&1" >> "$CRON_TEMP"
```

**Windows (`auto_schedule_windows.bat`):**
```cmd
REM Change these lines in setup_tasks section
schtasks /create /tn "GapTradeBot_Start" /tr "cmd /c \"%BOT_DIR%!SCRIPT_NAME! start\"" /sc daily /st 10:00 /f /ru System /rl highest
schtasks /create /tn "GapTradeBot_Stop" /tr "cmd /c \"%BOT_DIR%!SCRIPT_NAME! stop\"" /sc daily /st 01:00 /f /ru System /rl highest
```

## 📊 Monitoring

### Log Files

Both scripts create log files for monitoring:

- **Linux**: `auto_schedule.log`
- **Windows**: `auto_schedule.log`

### Manual Monitoring

**Linux:**
```bash
# Check if bot is running
./auto_schedule_linux.sh check

# View recent logs
tail -f auto_schedule.log

# Check cron jobs
crontab -l | grep "Gap Trade Bot"
```

**Windows:**
```cmd
# Check if bot is running
auto_schedule_windows.bat check

# View recent logs
type auto_schedule.log

# Check scheduled tasks
schtasks /query /tn "GapTradeBot_Start"
schtasks /query /tn "GapTradeBot_Stop"
```

### Automatic Monitoring

The scripts include built-in monitoring:

- **Process checking**: Verifies bot is actually running
- **PID file management**: Tracks bot process ID
- **Graceful shutdown**: Attempts clean shutdown before force kill
- **Logging**: All actions are logged with timestamps

## 🛠️ Troubleshooting

### Common Issues

**Bot won't start automatically:**
1. Check if virtual environment exists
2. Verify Python path in scripts
3. Check log files for errors
4. Ensure cron/Task Scheduler is running

**Bot stops unexpectedly:**
1. Check system resources
2. Review error logs
3. Verify API credentials
4. Check network connectivity

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
./auto_schedule_linux.sh start
```

**Windows:**
```cmd
# Check Task Scheduler service
sc query Schedule

# View Task Scheduler events
eventvwr.msc

# Test manual start
auto_schedule_windows.bat start
```

## 🔄 Maintenance

### Regular Maintenance

1. **Weekly**: Check log files for errors
2. **Monthly**: Review scheduled task status
3. **Quarterly**: Update bot dependencies
4. **Annually**: Review and update schedule times

### Updating Schedule

To change the schedule:

1. **Remove existing schedule:**
   ```bash
   # Linux
   ./auto_schedule_linux.sh remove
   
   # Windows
   auto_schedule_windows.bat remove
   ```

2. **Edit script with new times**

3. **Reinstall schedule:**
   ```bash
   # Linux
   ./auto_schedule_linux.sh setup
   
   # Windows
   auto_schedule_windows.bat setup
   ```

## ⚠️ Important Notes

### Security Considerations

- **Linux**: Scripts run with user permissions
- **Windows**: Tasks run with System privileges
- **Logs**: May contain sensitive information
- **PID files**: Should be protected from unauthorized access

### Performance Considerations

- **Startup time**: Bot takes 30-60 seconds to fully initialize
- **Shutdown time**: Graceful shutdown takes 10-15 seconds
- **Resource usage**: Monitor CPU and memory usage
- **Network**: Ensure stable internet connection

### Backup Recommendations

- **Configuration**: Backup `.env` file
- **Database**: Backup `trading_positions.db`
- **Logs**: Archive old log files
- **Scripts**: Version control all scripts

## 📞 Support

### Getting Help

1. **Check logs first**: `auto_schedule.log`
2. **Test manually**: Run start/stop commands manually
3. **Verify environment**: Ensure Python and dependencies are correct
4. **Check permissions**: Ensure proper file and service permissions

### Emergency Stop

If the bot needs to be stopped immediately:

**Linux:**
```bash
pkill -f "python3 run_bot.py"
```

**Windows:**
```cmd
taskkill /F /IM python.exe
```

---

**Happy Automated Trading! 🚀📈** 