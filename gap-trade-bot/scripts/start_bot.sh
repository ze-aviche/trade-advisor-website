#!/bin/bash

# Gap-Trade-Bot Bot Start Script

# Get the project root directory (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🤖 Starting Trading Bot..."

# Function to check if port is available
check_port() {
    local port=$1
    local service=$2
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "❌ Port $port is already in use by $service"
        return 1
    else
        echo "✅ Port $port is available"
        return 0
    fi
}

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

# Clean up any existing bot processes
echo "🛑 Cleaning up any existing bot processes..."
kill_process "run_bot.py" "Trading Bot"

# Check if bot directory exists
if [ ! -d "$PROJECT_ROOT/backend/bot" ]; then
    echo "❌ Bot directory not found: $PROJECT_ROOT/backend/bot"
    exit 1
fi

# Start trading bot
echo "🚀 Starting trading bot..."
cd "$PROJECT_ROOT/backend/bot"
nohup python3 run_bot.py > logs/gap_trade_bot_all.log 2>&1 &
BOT_PID=$!
cd "$PROJECT_ROOT/scripts"

# Wait for bot to initialize
echo "⏳ Waiting for bot to initialize..."
sleep 5

# Check if bot started successfully
if ps -p $BOT_PID > /dev/null 2>&1; then
    echo "✅ Trading bot started successfully (PID: $BOT_PID)"
    echo "📋 Log file: $PROJECT_ROOT/backend/bot/logs/gap_trade_bot_all.log"
    echo "📋 Error log: $PROJECT_ROOT/backend/bot/logs/gap_trade_bot_errors.log"
    echo ""
    echo "🛑 To stop bot: $PROJECT_ROOT/scripts/stop_bot.sh"
    echo "📊 To check status: $PROJECT_ROOT/scripts/check_status.sh"
else
    echo "❌ Trading bot failed to start"
    echo "📋 Check $PROJECT_ROOT/backend/bot/logs/gap_trade_bot_all.log for details"
    exit 1
fi 