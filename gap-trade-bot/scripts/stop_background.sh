#!/bin/bash

# Gap-Trade-Bot Background Stop Script

echo "🛑 Stopping Gap-Trade-Bot..."

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

# Kill backend
kill_process "app.py" "Backend"

# Kill frontend
kill_process "http.server" "Frontend"

# Additional cleanup - kill any remaining Python processes on our ports
echo "🧹 Cleaning up any remaining processes on our ports..."

# Kill anything on port 5000 (backend)
lsof -ti:5000 | xargs kill -9 2>/dev/null || echo "ℹ️ No processes on port 5000"

# Kill anything on port 3000 (frontend)
lsof -ti:3000 | xargs kill -9 2>/dev/null || echo "ℹ️ No processes on port 3000"

echo ""
echo "🎯 Gap-Trade-Bot stop process completed!" 