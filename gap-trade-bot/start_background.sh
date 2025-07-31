#!/bin/bash

# Gap-Trade-Bot Background Startup Script

echo "🚀 Starting Gap-Trade-Bot in background..."

# Create logs directory if it doesn't exist
mkdir -p logs

# Kill any existing processes
echo "🛑 Stopping any existing processes..."
pkill -f "python3.*app.py" 2>/dev/null
pkill -f "python3.*http.server" 2>/dev/null

# Start backend
echo "🔧 Starting backend server..."
cd backend
nohup python3 app.py > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Start frontend
echo "🌐 Starting frontend server..."
cd frontend
nohup python3 -m http.server 3000 > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
sleep 2

# Check if processes are running
if ps -p $BACKEND_PID > /dev/null; then
    echo "✅ Backend started (PID: $BACKEND_PID)"
else
    echo "❌ Backend failed to start"
fi

if ps -p $FRONTEND_PID > /dev/null; then
    echo "✅ Frontend started (PID: $FRONTEND_PID)"
else
    echo "❌ Frontend failed to start"
fi

echo ""
echo "🎯 Gap-Trade-Bot is now running!"
echo "📊 Backend: http://localhost:5000"
echo "🌐 Frontend: http://localhost:3000"
echo "📋 Logs: logs/backend.log, logs/frontend.log"
echo ""
echo "🛑 To stop: ./stop_background.sh"
echo "📊 To check status: ./check_status.sh" 