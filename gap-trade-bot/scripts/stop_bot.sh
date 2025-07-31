#!/bin/bash

# Gap-Trade-Bot Bot Stop Script

# Get the project root directory (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🛑 Stopping Trading Bot..."

# Function to kill process by pattern
kill_process() {
    local pattern="$1"
    local name="$2"
    
    echo "🔍 Looking for $name processes..."
    local pids=$(pgrep -f "$pattern")
    
    if [ -n "$pids" ]; then
        echo "📋 Found $name PIDs: $pids"
        echo "💀 Killing $name processes..."
        pkill -f "$pattern"
        sleep 1
        
        # Force kill if still running
        local still_running=$(pgrep -f "$pattern")
        if [ -n "$still_running" ]; then
            echo "⚡ Force killing $name processes..."
            pkill -9 -f "$pattern"
            sleep 1
        fi
        
        # Final check
        local final_check=$(pgrep -f "$pattern")
        if [ -z "$final_check" ]; then
            echo "✅ $name stopped successfully"
        else
            echo "❌ $name still running (PIDs: $final_check)"
        fi
    else
        echo "ℹ️ No $name processes found"
    fi
}

# Kill trading bot
kill_process "run_bot.py" "Trading Bot"

# Additional cleanup - remove bot PID file if it exists
if [ -f "$PROJECT_ROOT/backend/bot/bot.pid" ]; then
    echo "🗑️ Removing bot PID file..."
    rm -f "$PROJECT_ROOT/backend/bot/bot.pid"
fi

# Additional cleanup - remove bot status file if it exists
if [ -f "$PROJECT_ROOT/backend/bot/bot_status.json" ]; then
    echo "🗑️ Removing bot status file..."
    rm -f "$PROJECT_ROOT/backend/bot/bot_status.json"
fi

echo ""
echo "🎯 Trading Bot stop process completed!"
echo "📊 To check status: $PROJECT_ROOT/scripts/check_status.sh"
echo "🚀 To start bot: $PROJECT_ROOT/scripts/start_bot.sh" 