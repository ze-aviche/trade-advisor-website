#!/bin/bash

# Gap-Trade-Bot Status Check Script

# Get the project root directory (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📊 Gap-Trade-Bot Status Check"
echo "=============================="

# Function to check service status
check_service() {
    local name="$1"
    local pattern="$2"
    local port="$3"
    local url="$4"
    
    local pids=$(pgrep -f "$pattern")
    if [ -n "$pids" ]; then
        echo "✅ $name: Running (PIDs: $pids)"
        if [ -n "$url" ]; then
            echo "   🌐 URL: $url"
        fi
        return 0
    else
        echo "❌ $name: Not running"
        return 1
    fi
}

# Check all services
BOT_RUNNING=false
BACKEND_RUNNING=false
FRONTEND_RUNNING=false

# Debug: Show all Python processes
echo "🔍 Debug: All Python processes:"
ps aux | grep python | grep -v grep | head -10

if check_service "Trading Bot" "run_bot.py"; then
    BOT_RUNNING=true
fi

if check_service "Backend" "app.py" "5000" "http://localhost:5000"; then
    BACKEND_RUNNING=true
fi

if check_service "Frontend" "http.server" "3000" "http://localhost:3000"; then
    FRONTEND_RUNNING=true
fi

# Check ports
echo ""
echo "🔍 Port Status:"
if lsof -i :5000 >/dev/null 2>&1; then
    BACKEND_PORT_PID=$(lsof -ti:5000)
    echo "✅ Port 5000: Backend server (PID: $BACKEND_PORT_PID)"
else
    echo "❌ Port 5000: Not in use"
fi

if lsof -i :3000 >/dev/null 2>&1; then
    FRONTEND_PORT_PID=$(lsof -ti:3000)
    echo "✅ Port 3000: Frontend server (PID: $FRONTEND_PORT_PID)"
else
    echo "❌ Port 3000: Not in use"
fi

# Test backend health if running
if [ "$BACKEND_RUNNING" = true ]; then
    echo ""
    echo "🔍 Backend Health Check:"
    if curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
        echo "✅ Backend API is responding"
        
        # Get bot status from API
        BOT_STATUS=$(curl -s http://localhost:5000/api/bot/status | grep -o '"is_running":[^,]*' | cut -d':' -f2)
        if [ "$BOT_STATUS" = "true" ]; then
            echo "✅ Bot status: Running"
        else
            echo "⚠️ Bot status: Stopped"
        fi
    else
        echo "❌ Backend API is not responding"
    fi
fi

# Show recent logs
echo ""
echo "📋 Recent Logs:"
if [ -f "$PROJECT_ROOT/backend/bot/logs/gap_trade_bot_all.log" ]; then
    echo "🤖 Bot log (last 5 lines):"
    tail -5 "$PROJECT_ROOT/backend/bot/logs/gap_trade_bot_all.log" | sed 's/^/   /'
else
    echo "❌ No bot log found"
fi

if [ -f "$PROJECT_ROOT/backend/logs/gap_trade_backend_all.log" ]; then
    echo "🔧 Backend log (last 5 lines):"
    tail -5 "$PROJECT_ROOT/backend/logs/gap_trade_backend_all.log" | sed 's/^/   /'
else
    echo "❌ No backend log found"
fi

if [ -f "$PROJECT_ROOT/frontend/frontend.log" ]; then
    echo "🌐 Frontend log (last 5 lines):"
    tail -5 "$PROJECT_ROOT/frontend/frontend.log" | sed 's/^/   /'
else
    echo "❌ No frontend log found"
fi

# Summary
echo ""
echo "📊 Summary:"
if [ "$BOT_RUNNING" = true ] && [ "$BACKEND_RUNNING" = true ] && [ "$FRONTEND_RUNNING" = true ]; then
    echo "🎯 All services are running!"
else
    echo "⚠️ Some services are not running"
fi 