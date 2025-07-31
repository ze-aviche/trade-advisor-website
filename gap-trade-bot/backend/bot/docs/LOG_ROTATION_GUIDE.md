# 🗑️ Log Rotation System Guide

This guide explains the automatic log rotation system that prevents log files from growing too large and consuming disk space.

## 📋 Overview

The log rotation system automatically deletes log files every 6 hours to prevent them from growing indefinitely. This helps maintain system performance and prevents disk space issues.

## 🕐 Schedule

- **Frequency**: Every 6 hours
- **Times**: 00:00, 06:00, 12:00, 18:00 (UTC)
- **Days**: Every day (including weekends)

## 📁 Log Files Rotated

The following log files are automatically deleted:

### Linux/Mac:
- `backend/bot/auto_schedule_full.log`
- `backend/bot/bot_auto.log`
- `backend/backend.log`
- `backend/frontend.log`
- `backend/bot/auto_schedule.log`

### Windows:
- `backend\bot\auto_schedule_full.log`
- `backend\bot\bot_auto.log`
- `backend\backend.log`
- `backend\frontend.log`
- `backend\bot\auto_schedule.log`

## 🚀 Setup

### Linux/Mac Setup

1. **Make script executable:**
   ```bash
   chmod +x backend/bot/log_rotation.sh
   ```

2. **Install automatic rotation:**
   ```bash
   cd backend/bot
   ./log_rotation.sh setup
   ```

3. **Verify installation:**
   ```bash
   ./log_rotation.sh status
   ```

### Windows Setup

1. **Install automatic rotation:**
   ```cmd
   cd backend\bot
   log_rotation.bat setup
   ```

2. **Verify installation:**
   ```cmd
   log_rotation.bat status
   ```

## 🛠️ Commands

### Linux/Mac Commands

| Command | Description |
|---------|-------------|
| `./log_rotation.sh setup` | Install automatic log rotation |
| `./log_rotation.sh remove` | Remove automatic log rotation |
| `./log_rotation.sh status` | Show rotation status and file sizes |
| `./log_rotation.sh manual` | Manually rotate logs now |
| `./log_rotation.sh rotate` | Rotate logs (internal use) |

### Windows Commands

| Command | Description |
|---------|-------------|
| `log_rotation.bat setup` | Install automatic log rotation |
| `log_rotation.bat remove` | Remove automatic log rotation |
| `log_rotation.bat status` | Show rotation status and file sizes |
| `log_rotation.bat manual` | Manually rotate logs now |
| `log_rotation.bat rotate` | Rotate logs (internal use) |

## 📊 Monitoring

### Check Current Status

**Linux/Mac:**
```bash
./log_rotation.sh status
```

**Windows:**
```cmd
log_rotation.bat status
```

### View Rotation Log

**Linux/Mac:**
```bash
tail -f backend/bot/log_rotation.log
```

**Windows:**
```cmd
type backend\bot\log_rotation.log
```

## 🔧 Configuration

### Customizing Rotation Schedule

To change the rotation frequency, edit the cron job:

**Linux/Mac:**
```bash
# Edit the cron job in log_rotation.sh
CRON_JOB="0 */6 * * * $BOT_DIR/log_rotation.sh rotate >> $BOT_DIR/log_rotation.log 2>&1"
```

**Windows:**
```cmd
# Edit the scheduled task in log_rotation.bat
schtasks /create /tn "GapTradeBot_LogRotation" /tr "..." /sc daily /st 00:00
```

### Adding More Log Files

To rotate additional log files, edit the `LOG_FILES` array:

**Linux/Mac (`log_rotation.sh`):**
```bash
LOG_FILES=(
    "$BOT_DIR/auto_schedule_full.log"
    "$BOT_DIR/bot_auto.log"
    "$PROJECT_ROOT/backend.log"
    "$PROJECT_ROOT/frontend.log"
    "$BOT_DIR/auto_schedule.log"
    "$BOT_DIR/your_new_log.log"  # Add new files here
)
```

**Windows (`log_rotation.bat`):**
```batch
REM Add new log files to the rotation list
if exist "%BOT_DIR%your_new_log.log" (
    call :log_message "🗑️ Deleting: %BOT_DIR%your_new_log.log"
    del "%BOT_DIR%your_new_log.log"
    set /a deleted_count+=1
)
```

## ⚠️ Important Notes

### What Gets Deleted

- **All log files** are completely deleted (not truncated)
- **No backup** is created before deletion
- **Rotation log** (`log_rotation.log`) is preserved

### When Rotation Happens

- **Automatic**: Every 6 hours via cron/scheduled task
- **Manual**: When you run `manual` command
- **System**: During normal operation

### Recovery

If you need to recover deleted logs:

1. **Check rotation log** for deletion timestamps
2. **Restore from backup** if available
3. **Check system logs** for recent activity

## 🐛 Troubleshooting

### Common Issues

**Rotation not working:**
```bash
# Check if cron job exists
crontab -l | grep log_rotation

# Check if scheduled task exists (Windows)
schtasks /query /tn "GapTradeBot_LogRotation"
```

**Permission errors:**
```bash
# Make script executable
chmod +x log_rotation.sh

# Run as administrator (Windows)
# Right-click Command Prompt → Run as administrator
```

**Log files not found:**
- Check file paths in the script
- Verify log files exist before rotation
- Check for typos in file names

### Debug Mode

**Linux/Mac:**
```bash
# Run with verbose output
bash -x ./log_rotation.sh manual
```

**Windows:**
```cmd
# Run with verbose output
cmd /v:on /c log_rotation.bat manual
```

## 📈 Performance Impact

### Benefits

- **Disk space**: Prevents unlimited log growth
- **Performance**: Faster log file operations
- **Maintenance**: Automatic cleanup
- **Monitoring**: Built-in size tracking

### Considerations

- **Data loss**: Old logs are permanently deleted
- **Debugging**: Recent logs may be needed for troubleshooting
- **Compliance**: May need to retain logs for longer periods

## 🔄 Integration with Auto-Schedule

The log rotation system works alongside the auto-schedule system:

1. **Auto-schedule** starts/stops the trading system
2. **Log rotation** cleans up log files every 6 hours
3. **Both systems** log their activities for monitoring

### Combined Monitoring

```bash
# Check both systems
./auto_schedule_full_linux.sh status
./log_rotation.sh status
```

## 📞 Support

### Getting Help

1. **Check rotation log**: `tail -f log_rotation.log`
2. **Verify cron jobs**: `crontab -l`
3. **Test manually**: `./log_rotation.sh manual`
4. **Check file permissions**: `ls -la log_rotation.sh`

### Emergency Stop

**Linux/Mac:**
```bash
./log_rotation.sh remove
```

**Windows:**
```cmd
log_rotation.bat remove
```

---

**Last Updated**: July 31, 2025  
**Version**: 1.0  
**Compatibility**: Linux, macOS, Windows 