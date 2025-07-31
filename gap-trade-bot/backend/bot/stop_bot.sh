#!/bin/bash

# Stop Trading Bot Script
# Usage: ./stop_bot.sh

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$BOT_DIR/bot.pid"
STATUS_FILE="$BOT_DIR/bot_status.json"

echo "🤖 Gap Trade Bot - Stop Script"
echo "================================"

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo "❌ Bot PID file not found. Bot may not be running."
    echo "📁 Expected PID file: $PID_FILE"
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
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "❌ Process $PID is not running"
    echo "🧹 Cleaning up stale PID file..."
    rm -f "$PID_FILE"
    exit 1
fi

echo "🛑 Stopping bot process $PID..."

# Try graceful shutdown first
kill -TERM "$PID" 2>/dev/null

# Wait for graceful shutdown
for i in {1..10}; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ Bot stopped gracefully"
        exit 0
    fi
    echo "⏳ Waiting for graceful shutdown... ($i/10)"
    sleep 1
done

# Force kill if still running
echo "⚠️ Force killing bot process..."
kill -KILL "$PID" 2>/dev/null

# Check if killed
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "✅ Bot force stopped"
else
    echo "❌ Failed to stop bot process"
    exit 1
fi

# Show final status if available
if [ -f "$STATUS_FILE" ]; then
    echo ""
    echo "📊 Final Bot Status:"
    cat "$STATUS_FILE" | python3 -m json.tool 2>/dev/null || cat "$STATUS_FILE"
fi

echo "✅ Bot stop script completed" 