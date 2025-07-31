#!/bin/bash

# Gap-Trade-Bot Background Stop Script

echo "🛑 Stopping Gap-Trade-Bot..."

# Kill backend processes
echo "🔧 Stopping backend server..."
pkill -f "python3.*app.py"

# Kill frontend processes
echo "🌐 Stopping frontend server..."
pkill -f "python3.*http.server"

# Wait a moment
sleep 2

# Check if processes are still running
BACKEND_RUNNING=$(pgrep -f "python3.*app.py")
FRONTEND_RUNNING=$(pgrep -f "python3.*http.server")

if [ -z "$BACKEND_RUNNING" ]; then
    echo "✅ Backend stopped"
else
    echo "❌ Backend still running (PID: $BACKEND_RUNNING)"
fi

if [ -z "$FRONTEND_RUNNING" ]; then
    echo "✅ Frontend stopped"
else
    echo "❌ Frontend still running (PID: $FRONTEND_RUNNING)"
fi

echo ""
echo "🎯 Gap-Trade-Bot stopped!" 