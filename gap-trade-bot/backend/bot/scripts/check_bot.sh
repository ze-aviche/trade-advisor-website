#!/bin/bash

# Check Trading Bot Status Script
# Usage: ./check_bot.sh

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$BOT_DIR/bot.pid"
STATUS_FILE="$BOT_DIR/bot_status.json"

echo "🤖 Gap Trade Bot - Status Check"
echo "================================"

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo "❌ Bot PID file not found"
    echo "📁 Expected PID file: $PID_FILE"
    echo "💡 Bot may not be running"
    exit 1
fi

# Read PID from file
PID=$(cat "$PID_FILE" 2>/dev/null)

if [ -z "$PID" ]; then
    echo "❌ Could not read PID from file"
    exit 1
fi

echo "📝 Bot PID: $PID"

# Check if process is running
if ps -p "$PID" > /dev/null 2>&1; then
    echo "✅ Bot process is running"
    
    # Show process info
    echo ""
    echo "📊 Process Information:"
    ps -p "$PID" -o pid,ppid,etime,pcpu,pmem,command
    
    # Show status file if available
    if [ -f "$STATUS_FILE" ]; then
        echo ""
        echo "📈 Bot Status:"
        cat "$STATUS_FILE" | python3 -m json.tool 2>/dev/null || cat "$STATUS_FILE"
    fi
    
    # Show recent logs
    LOG_DIR="$BOT_DIR/logs"
    if [ -d "$LOG_DIR" ]; then
        echo ""
        echo "📋 Recent Logs (last 5 lines):"
        if [ -f "$LOG_DIR/all.log" ]; then
            echo "📄 all.log:"
            tail -5 "$LOG_DIR/all.log"
        fi
        if [ -f "$LOG_DIR/errors.log" ]; then
            echo "📄 errors.log:"
            tail -5 "$LOG_DIR/errors.log"
        fi
    fi
    
else
    echo "❌ Bot process is not running"
    echo "🧹 Cleaning up stale PID file..."
    rm -f "$PID_FILE"
    exit 1
fi

echo ""
echo "🛑 To stop the bot: ./stop_bot.sh"
echo "📊 To check status again: ./check_bot.sh" 