#!/bin/bash

# Auto Schedule Trading Bot - Linux
# Automatically starts bot at 5 AM ET and stops at 8 PM ET

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$BOT_DIR/../../venv"
LOG_FILE="$BOT_DIR/auto_schedule.log"

echo "🤖 Gap Trade Bot - Auto Schedule (Linux)"
echo "=========================================="

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to start bot
start_bot() {
    log_message "🚀 Starting bot..."
    
    # Check if bot is already running
    if [ -f "$BOT_DIR/bot.pid" ]; then
        PID=$(cat "$BOT_DIR/bot.pid" 2>/dev/null)
        if ps -p "$PID" > /dev/null 2>&1; then
            log_message "⚠️ Bot is already running (PID: $PID)"
            return 1
        else
            log_message "🧹 Cleaning up stale PID file"
            rm -f "$BOT_DIR/bot.pid"
        fi
    fi
    
    # Activate virtual environment and start bot
    cd "$BOT_DIR"
    source "$VENV_PATH/bin/activate"
    
    # Start bot in background
    nohup python3 run_bot.py > bot_auto.log 2>&1 &
    BOT_PID=$!
    
    # Wait a moment and check if started successfully
    sleep 3
    if ps -p "$BOT_PID" > /dev/null 2>&1; then
        log_message "✅ Bot started successfully (PID: $BOT_PID)"
        return 0
    else
        log_message "❌ Failed to start bot"
        return 1
    fi
}

# Function to stop bot
stop_bot() {
    log_message "🛑 Stopping bot..."
    
    if [ -f "$BOT_DIR/bot.pid" ]; then
        PID=$(cat "$BOT_DIR/bot.pid" 2>/dev/null)
        if ps -p "$PID" > /dev/null 2>&1; then
            # Try graceful shutdown
            kill -TERM "$PID" 2>/dev/null
            
            # Wait for graceful shutdown
            for i in {1..10}; do
                if ! ps -p "$PID" > /dev/null 2>&1; then
                    log_message "✅ Bot stopped gracefully"
                    return 0
                fi
                sleep 1
            done
            
            # Force kill if still running
            log_message "⚠️ Force killing bot process"
            kill -KILL "$PID" 2>/dev/null
            
            if ! ps -p "$PID" > /dev/null 2>&1; then
                log_message "✅ Bot force stopped"
                return 0
            else
                log_message "❌ Failed to stop bot"
                return 1
            fi
        else
            log_message "⚠️ Bot process not running"
            rm -f "$BOT_DIR/bot.pid"
            return 0
        fi
    else
        log_message "⚠️ No PID file found - bot may not be running"
        return 0
    fi
}

# Function to check bot status
check_bot() {
    if [ -f "$BOT_DIR/bot.pid" ]; then
        PID=$(cat "$BOT_DIR/bot.pid" 2>/dev/null)
        if ps -p "$PID" > /dev/null 2>&1; then
            log_message "✅ Bot is running (PID: $PID)"
            return 0
        else
            log_message "❌ Bot is not running (stale PID file)"
            rm -f "$BOT_DIR/bot.pid"
            return 1
        fi
    else
        log_message "❌ Bot is not running (no PID file)"
        return 1
    fi
}

# Function to setup cron jobs
setup_cron() {
    log_message "🔧 Setting up cron jobs..."
    
    # Get current user's crontab
    CRON_TEMP=$(mktemp)
    crontab -l 2>/dev/null > "$CRON_TEMP" || echo "" > "$CRON_TEMP"
    
    # Remove existing bot cron jobs
    sed -i '/# Gap Trade Bot/d' "$CRON_TEMP"
    sed -i '/bot\/auto_schedule_linux.sh/d' "$CRON_TEMP"
    
    # Add new cron jobs (5 AM ET = 10 AM UTC, 8 PM ET = 1 AM UTC next day)
    echo "# Gap Trade Bot - Auto Schedule" >> "$CRON_TEMP"
    echo "0 10 * * 1-5 $BOT_DIR/auto_schedule_linux.sh start >> $LOG_FILE 2>&1" >> "$CRON_TEMP"
    echo "0 1 * * 2-6 $BOT_DIR/auto_schedule_linux.sh stop >> $LOG_FILE 2>&1" >> "$CRON_TEMP"
    
    # Install new crontab
    crontab "$CRON_TEMP"
    rm "$CRON_TEMP"
    
    log_message "✅ Cron jobs installed:"
    log_message "   - Start: 5:00 AM ET (10:00 AM UTC) Monday-Friday"
    log_message "   - Stop:  8:00 PM ET (1:00 AM UTC next day) Monday-Friday"
}

# Function to remove cron jobs
remove_cron() {
    log_message "🗑️ Removing cron jobs..."
    
    CRON_TEMP=$(mktemp)
    crontab -l 2>/dev/null > "$CRON_TEMP" || echo "" > "$CRON_TEMP"
    
    # Remove bot cron jobs
    sed -i '/# Gap Trade Bot/d' "$CRON_TEMP"
    sed -i '/bot\/auto_schedule_linux.sh/d' "$CRON_TEMP"
    
    crontab "$CRON_TEMP"
    rm "$CRON_TEMP"
    
    log_message "✅ Cron jobs removed"
}

# Function to show cron status
show_cron() {
    echo "📅 Current Cron Jobs:"
    crontab -l 2>/dev/null | grep -E "(Gap Trade Bot|auto_schedule_linux.sh)" || echo "No bot cron jobs found"
}

# Main script logic
case "${1:-}" in
    "start")
        start_bot
        ;;
    "stop")
        stop_bot
        ;;
    "check")
        check_bot
        ;;
    "setup")
        setup_cron
        ;;
    "remove")
        remove_cron
        ;;
    "status")
        show_cron
        echo ""
        check_bot
        ;;
    *)
        echo "Usage: $0 {start|stop|check|setup|remove|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the trading bot"
        echo "  stop    - Stop the trading bot"
        echo "  check   - Check if bot is running"
        echo "  setup   - Install cron jobs for auto scheduling"
        echo "  remove  - Remove cron jobs"
        echo "  status  - Show cron status and bot status"
        echo ""
        echo "Auto Schedule:"
        echo "  - Start: 5:00 AM ET Monday-Friday"
        echo "  - Stop:  8:00 PM ET Monday-Friday"
        echo ""
        echo "Log file: $LOG_FILE"
        ;;
esac 