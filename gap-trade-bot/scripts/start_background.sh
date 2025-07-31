#!/bin/bash

# Gap-Trade-Bot Background Startup Script

# Get the project root directory (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting Gap-Trade-Bot in background..."
echo "📁 Project root: $PROJECT_ROOT"

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

# Function to start service with validation
start_service() {
    local name="$1"
    local command="$2"
    local log_file="$3"
    local port="$4"
    
    echo "🔍 Starting $name..."
    
    # Check port if specified
    if [ -n "$port" ]; then
        if ! check_port $port $name; then
            echo "💀 Killing process on port $port..."
            lsof -ti:$port | xargs kill -9 2>/dev/null
            sleep 2
        fi
    fi
    
    # Start the service
    eval $command
    local pid=$!
    
    # Wait for service to start
    sleep 3
    
    # Check if process is running
    if ps -p $pid > /dev/null 2>&1; then
        echo "✅ $name started successfully (PID: $pid)"
        return $pid
    else
        echo "❌ $name failed to start"
        return 1
    fi
}

# Create logs directories if they don't exist
mkdir -p "$PROJECT_ROOT/backend/logs"
mkdir -p "$PROJECT_ROOT/backend/bot/logs"
mkdir -p "$PROJECT_ROOT/frontend"

# Clean up any existing processes
echo "🛑 Cleaning up any existing processes..."
pkill -f "python3.*run_bot.py" 2>/dev/null
pkill -f "python3.*app.py" 2>/dev/null
pkill -f "python3.*http.server" 2>/dev/null
sleep 2

# Check if ports are available
echo "🔍 Checking port availability..."
check_port 5000 "Backend" || exit 1
check_port 3000 "Frontend" || exit 1

# Start trading bot first
echo "🤖 Starting trading bot..."
cd "$PROJECT_ROOT/backend/bot"
nohup python3 run_bot.py > logs/gap_trade_bot_all.log 2>&1 &
BOT_PID=$!
cd "$PROJECT_ROOT/scripts"

# Wait for bot to initialize
echo "⏳ Waiting for bot to initialize..."
sleep 5

# Check if bot started successfully
if ps -p $BOT_PID > /dev/null 2>&1; then
    echo "✅ Trading bot started (PID: $BOT_PID)"
else
    echo "❌ Trading bot failed to start"
    echo "📋 Check $PROJECT_ROOT/backend/bot/logs/gap_trade_bot_all.log for details"
    exit 1
fi

# Start backend
echo "🔧 Starting backend server..."
cd "$PROJECT_ROOT/backend"
nohup python3 app.py > logs/gap_trade_backend_all.log 2>&1 &
BACKEND_PID=$!
cd "$PROJECT_ROOT/scripts"

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 5

# Check if backend started successfully
if ps -p $BACKEND_PID > /dev/null 2>&1; then
    echo "✅ Backend started (PID: $BACKEND_PID)"
else
    echo "❌ Backend failed to start"
    echo "📋 Check $PROJECT_ROOT/backend/logs/gap_trade_backend_all.log for details"
    exit 1
fi

# Test backend health
echo "🔍 Testing backend health..."
sleep 2
if curl -s http://localhost:5000/api/health > /dev/null 2>&1; then
    echo "✅ Backend is responding"
else
    echo "⚠️ Backend health check failed, but continuing..."
fi

# Start frontend
echo "🌐 Starting frontend server..."
cd "$PROJECT_ROOT/frontend"
nohup python3 -m http.server 3000 > frontend.log 2>&1 &
FRONTEND_PID=$!
cd "$PROJECT_ROOT/scripts"

# Wait for frontend to start
echo "⏳ Waiting for frontend to start..."
sleep 3

# Check if frontend started successfully
if ps -p $FRONTEND_PID > /dev/null 2>&1; then
    echo "✅ Frontend started (PID: $FRONTEND_PID)"
else
    echo "❌ Frontend failed to start"
    echo "📋 Check $PROJECT_ROOT/frontend/frontend.log for details"
    exit 1
fi

# Final status check
echo ""
echo "🎯 Gap-Trade-Bot startup completed!"
echo "📊 Backend: http://localhost:5000"
echo "🌐 Frontend: http://localhost:3000"
echo "📋 Logs: $PROJECT_ROOT/backend/bot/logs/gap_trade_bot_all.log, $PROJECT_ROOT/backend/logs/gap_trade_backend_all.log, $PROJECT_ROOT/frontend/frontend.log"
echo ""
echo "🛑 To stop: $PROJECT_ROOT/scripts/stop_background.sh"
echo "📊 To check status: $PROJECT_ROOT/scripts/check_status.sh"
echo ""
echo "🔍 Checking final status..."
"$PROJECT_ROOT/scripts/check_status.sh" 