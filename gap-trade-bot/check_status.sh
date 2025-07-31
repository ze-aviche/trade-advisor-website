#!/bin/bash

# Gap-Trade-Bot Status Check Script

echo "📊 Gap-Trade-Bot Status Check"
echo "=" * 30

# Check backend
BACKEND_PID=$(pgrep -f "python3.*app.py")
if [ -n "$BACKEND_PID" ]; then
    echo "✅ Backend: Running (PID: $BACKEND_PID)"
    echo "   📊 URL: http://localhost:5000"
else
    echo "❌ Backend: Not running"
fi

# Check frontend
FRONTEND_PID=$(pgrep -f "python3.*http.server")
if [ -n "$FRONTEND_PID" ]; then
    echo "✅ Frontend: Running (PID: $FRONTEND_PID)"
    echo "   🌐 URL: http://localhost:3000"
else
    echo "❌ Frontend: Not running"
fi

# Check ports
echo ""
echo "🔍 Port Status:"
if lsof -i :5000 >/dev/null 2>&1; then
    echo "✅ Port 5000: Backend server"
else
    echo "❌ Port 5000: Not in use"
fi

if lsof -i :3000 >/dev/null 2>&1; then
    echo "✅ Port 3000: Frontend server"
else
    echo "❌ Port 3000: Not in use"
fi

# Show recent logs
echo ""
echo "📋 Recent Logs:"
if [ -f "logs/backend.log" ]; then
    echo "🔧 Backend log (last 3 lines):"
    tail -3 logs/backend.log
else
    echo "❌ No backend log found"
fi

if [ -f "logs/frontend.log" ]; then
    echo "🌐 Frontend log (last 3 lines):"
    tail -3 logs/frontend.log
else
    echo "❌ No frontend log found"
fi 