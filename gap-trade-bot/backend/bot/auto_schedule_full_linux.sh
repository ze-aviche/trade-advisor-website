#!/bin/bash

# Auto Schedule Full System - Linux
# Manages frontend, backend, and trading bot
# Automatically starts at 5 AM ET and stops at 8 PM ET

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$BOT_DIR/../.."
VENV_PATH="$PROJECT_ROOT/venv"
LOG_FILE="$BOT_DIR/auto_schedule_full.log"

echo "🤖 Gap Trade Bot - Full System Auto Schedule (Linux)"
echo "===================================================="

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to check if process is running
is_process_running() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file" 2>/dev/null)
        if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Function to start backend server
start_backend() {
    log_message "🚀 Starting backend server..."
    
    if is_process_running "$PROJECT_ROOT/backend.pid"; then
        log_message "⚠️ Backend is already running"
        return 1
    fi
    
    cd "$PROJECT_ROOT"
    source "$VENV_PATH/bin/activate"
    
    # Start backend in background
    nohup python3 backend/app.py > backend.log 2>&1 &
    BACKEND_PID=$!
    
    # Wait for backend to start
    sleep 5
    
    if ps -p "$BACKEND_PID" > /dev/null 2>&1; then
        echo "$BACKEND_PID" > "$PROJECT_ROOT/backend.pid"
        log_message "✅ Backend started successfully (PID: $BACKEND_PID)"
        return 0
    else
        log_message "❌ Failed to start backend"
        return 1
    fi
}

# Function to start frontend server
start_frontend() {
    log_message "🌐 Starting frontend server..."
    
    if is_process_running "$PROJECT_ROOT/frontend.pid"; then
        log_message "⚠️ Frontend is already running"
        return 1
    fi
    
    cd "$PROJECT_ROOT/frontend"
    
    # Start frontend in background
    nohup python3 -m http.server 3000 > frontend.log 2>&1 &
    FRONTEND_PID=$!
    
    # Wait for frontend to start
    sleep 3
    
    if ps -p "$FRONTEND_PID" > /dev/null 2>&1; then
        echo "$FRONTEND_PID" > "$PROJECT_ROOT/frontend.pid"
        log_message "✅ Frontend started successfully (PID: $FRONTEND_PID)"
        return 0
    else
        log_message "❌ Failed to start frontend"
        return 1
    fi
}

# Function to start trading bot
start_bot() {
    log_message "🤖 Starting trading bot..."
    
    if is_process_running "$BOT_DIR/bot.pid"; then
        log_message "⚠️ Bot is already running"
        return 1
    fi
    
    cd "$BOT_DIR"
    source "$VENV_PATH/bin/activate"
    
    # Start bot in background
    nohup python3 run_bot.py > bot_auto.log 2>&1 &
    BOT_PID=$!
    
    # Wait for bot to start
    sleep 10
    
    if ps -p "$BOT_PID" > /dev/null 2>&1; then
        log_message "✅ Bot started successfully (PID: $BOT_PID)"
        return 0
    else
        log_message "❌ Failed to start bot"
        return 1
    fi
}

# Function to start all components
start_all() {
    log_message "🚀 Starting full system..."
    
    # Start backend
    if start_backend; then
        log_message "✅ Backend started"
    else
        log_message "⚠️ Backend start failed or already running"
    fi
    
    # Wait a moment
    sleep 2
    
    # Start frontend
    if start_frontend; then
        log_message "✅ Frontend started"
    else
        log_message "⚠️ Frontend start failed or already running"
    fi
    
    # Wait a moment
    sleep 2
    
    # Start bot
    if start_bot; then
        log_message "✅ Bot started"
    else
        log_message "⚠️ Bot start failed or already running"
    fi
    
    log_message "🎉 Full system startup completed"
}

# Function to stop backend
stop_backend() {
    log_message "🛑 Stopping backend..."
    
    if [ -f "$PROJECT_ROOT/backend.pid" ]; then
        local pid=$(cat "$PROJECT_ROOT/backend.pid" 2>/dev/null)
        if ps -p "$pid" > /dev/null 2>&1; then
            kill -TERM "$pid" 2>/dev/null
            
            # Wait for graceful shutdown
            for i in {1..10}; do
                if ! ps -p "$pid" > /dev/null 2>&1; then
                    log_message "✅ Backend stopped gracefully"
                    rm -f "$PROJECT_ROOT/backend.pid"
                    return 0
                fi
                sleep 1
            done
            
            # Force kill
            kill -KILL "$pid" 2>/dev/null
            log_message "✅ Backend force stopped"
            rm -f "$PROJECT_ROOT/backend.pid"
        else
            log_message "⚠️ Backend process not running"
            rm -f "$PROJECT_ROOT/backend.pid"
        fi
    else
        log_message "⚠️ No backend PID file found"
    fi
}

# Function to stop frontend
stop_frontend() {
    log_message "🛑 Stopping frontend..."
    
    if [ -f "$PROJECT_ROOT/frontend.pid" ]; then
        local pid=$(cat "$PROJECT_ROOT/frontend.pid" 2>/dev/null)
        if ps -p "$pid" > /dev/null 2>&1; then
            kill -TERM "$pid" 2>/dev/null
            
            # Wait for graceful shutdown
            for i in {1..5}; do
                if ! ps -p "$pid" > /dev/null 2>&1; then
                    log_message "✅ Frontend stopped gracefully"
                    rm -f "$PROJECT_ROOT/frontend.pid"
                    return 0
                fi
                sleep 1
            done
            
            # Force kill
            kill -KILL "$pid" 2>/dev/null
            log_message "✅ Frontend force stopped"
            rm -f "$PROJECT_ROOT/frontend.pid"
        else
            log_message "⚠️ Frontend process not running"
            rm -f "$PROJECT_ROOT/frontend.pid"
        fi
    else
        log_message "⚠️ No frontend PID file found"
    fi
}

# Function to stop bot
stop_bot() {
    log_message "🛑 Stopping bot..."
    
    if [ -f "$BOT_DIR/bot.pid" ]; then
        local pid=$(cat "$BOT_DIR/bot.pid" 2>/dev/null)
        if ps -p "$pid" > /dev/null 2>&1; then
            kill -TERM "$pid" 2>/dev/null
            
            # Wait for graceful shutdown
            for i in {1..10}; do
                if ! ps -p "$pid" > /dev/null 2>&1; then
                    log_message "✅ Bot stopped gracefully"
                    rm -f "$BOT_DIR/bot.pid"
                    return 0
                fi
                sleep 1
            done
            
            # Force kill
            kill -KILL "$pid" 2>/dev/null
            log_message "✅ Bot force stopped"
            rm -f "$BOT_DIR/bot.pid"
        else
            log_message "⚠️ Bot process not running"
            rm -f "$BOT_DIR/bot.pid"
        fi
    else
        log_message "⚠️ No bot PID file found"
    fi
}

# Function to stop all components
stop_all() {
    log_message "🛑 Stopping full system..."
    
    # Stop bot first (most important)
    stop_bot
    
    # Stop frontend
    stop_frontend
    
    # Stop backend
    stop_backend
    
    log_message "🎉 Full system shutdown completed"
}

# Function to check status of all components
check_status() {
    log_message "📊 Checking system status..."
    
    echo "🤖 Trading Bot:"
    if is_process_running "$BOT_DIR/bot.pid"; then
        local pid=$(cat "$BOT_DIR/bot.pid")
        echo "  ✅ Running (PID: $pid)"
    else
        echo "  ❌ Not running"
    fi
    
    echo "🌐 Frontend:"
    if is_process_running "$PROJECT_ROOT/frontend.pid"; then
        local pid=$(cat "$PROJECT_ROOT/frontend.pid")
        echo "  ✅ Running (PID: $pid) - http://localhost:3000"
    else
        echo "  ❌ Not running"
    fi
    
    echo "🚀 Backend:"
    if is_process_running "$PROJECT_ROOT/backend.pid"; then
        local pid=$(cat "$PROJECT_ROOT/backend.pid")
        echo "  ✅ Running (PID: $pid) - http://localhost:5000"
    else
        echo "  ❌ Not running"
    fi
}

# Function to setup cron jobs
setup_cron() {
    log_message "🔧 Setting up cron jobs for full system..."
    
    # Get current user's crontab
    CRON_TEMP=$(mktemp)
    crontab -l 2>/dev/null > "$CRON_TEMP" || echo "" > "$CRON_TEMP"
    
    # Remove existing full system cron jobs
    sed -i '/# Gap Trade Bot Full System/d' "$CRON_TEMP"
    sed -i '/auto_schedule_full_linux.sh/d' "$CRON_TEMP"
    
    # Add new cron jobs (5 AM ET = 10 AM UTC, 8 PM ET = 1 AM UTC next day)
    echo "# Gap Trade Bot Full System - Auto Schedule" >> "$CRON_TEMP"
    echo "0 10 * * 1-5 $BOT_DIR/auto_schedule_full_linux.sh start >> $LOG_FILE 2>&1" >> "$CRON_TEMP"
    echo "0 1 * * 2-6 $BOT_DIR/auto_schedule_full_linux.sh stop >> $LOG_FILE 2>&1" >> "$CRON_TEMP"
    
    # Install new crontab
    crontab "$CRON_TEMP"
    rm "$CRON_TEMP"
    
    log_message "✅ Cron jobs installed:"
    log_message "   - Start: 5:00 AM ET (10:00 AM UTC) Monday-Friday"
    log_message "   - Stop:  8:00 PM ET (1:00 AM UTC next day) Monday-Friday"
}

# Function to remove cron jobs
remove_cron() {
    log_message "🗑️ Removing cron jobs..."
    
    CRON_TEMP=$(mktemp)
    crontab -l 2>/dev/null > "$CRON_TEMP" || echo "" > "$CRON_TEMP"
    
    # Remove full system cron jobs
    sed -i '/# Gap Trade Bot Full System/d' "$CRON_TEMP"
    sed -i '/auto_schedule_full_linux.sh/d' "$CRON_TEMP"
    
    crontab "$CRON_TEMP"
    rm "$CRON_TEMP"
    
    log_message "✅ Cron jobs removed"
}

# Main script logic
case "${1:-}" in
    "start")
        start_all
        ;;
    "stop")
        stop_all
        ;;
    "check")
        check_status
        ;;
    "setup")
        setup_cron
        ;;
    "remove")
        remove_cron
        ;;
    "status")
        check_status
        echo ""
        echo "📅 Current Cron Jobs:"
        crontab -l 2>/dev/null | grep -E "(Gap Trade Bot Full System|auto_schedule_full_linux.sh)" || echo "No full system cron jobs found"
        ;;
    *)
        echo "Usage: $0 {start|stop|check|setup|remove|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Start all components (backend, frontend, bot)"
        echo "  stop    - Stop all components"
        echo "  check   - Check status of all components"
        echo "  setup   - Install cron jobs for auto scheduling"
        echo "  remove  - Remove cron jobs"
        echo "  status  - Show system status and cron jobs"
        echo ""
        echo "Components:"
        echo "  - Backend: Flask server (port 5000)"
        echo "  - Frontend: HTTP server (port 3000)"
        echo "  - Trading Bot: Automated trading"
        echo ""
        echo "Auto Schedule:"
        echo "  - Start: 5:00 AM ET Monday-Friday"
        echo "  - Stop:  8:00 PM ET Monday-Friday"
        echo ""
        echo "Log file: $LOG_FILE"
        ;;
esac 