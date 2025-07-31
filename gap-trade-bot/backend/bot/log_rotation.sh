#!/bin/bash
# Log Rotation Script for Gap Trade Bot
# Deletes logs every 6 hours to prevent disk space issues

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$BOT_DIR")"

# Log files to rotate
LOG_FILES=(
    "$BOT_DIR/auto_schedule_full.log"
    "$BOT_DIR/bot_auto.log"
    "$PROJECT_ROOT/backend.log"
    "$PROJECT_ROOT/frontend.log"
    "$BOT_DIR/auto_schedule.log"
)

# Function to log messages
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$BOT_DIR/log_rotation.log"
    echo "$1"
}

# Function to rotate logs
rotate_logs() {
    log_message "🔄 Starting log rotation..."
    
    local deleted_count=0
    local total_size_before=0
    local total_size_after=0
    
    # Calculate total size before deletion
    for log_file in "${LOG_FILES[@]}"; do
        if [ -f "$log_file" ]; then
            size=$(stat -f%z "$log_file" 2>/dev/null || stat -c%s "$log_file" 2>/dev/null || echo 0)
            total_size_before=$((total_size_before + size))
        fi
    done
    
    # Delete log files
    for log_file in "${LOG_FILES[@]}"; do
        if [ -f "$log_file" ]; then
            log_message "🗑️ Deleting: $log_file"
            rm -f "$log_file"
            deleted_count=$((deleted_count + 1))
        fi
    done
    
    # Calculate total size after deletion
    for log_file in "${LOG_FILES[@]}"; do
        if [ -f "$log_file" ]; then
            size=$(stat -f%z "$log_file" 2>/dev/null || stat -c%s "$log_file" 2>/dev/null || echo 0)
            total_size_after=$((total_size_after + size))
        fi
    done
    
    local freed_space=$((total_size_before - total_size_after))
    log_message "✅ Log rotation completed:"
    log_message "   - Files deleted: $deleted_count"
    log_message "   - Space freed: ${freed_space} bytes"
    log_message "   - Total size before: ${total_size_before} bytes"
    log_message "   - Total size after: ${total_size_after} bytes"
}

# Function to setup cron job for log rotation
setup_log_rotation() {
    log_message "🔧 Setting up log rotation cron job..."
    
    # Create cron job to run every 6 hours
    CRON_JOB="0 */6 * * * $BOT_DIR/log_rotation.sh rotate >> $BOT_DIR/log_rotation.log 2>&1"
    
    # Add to crontab if not already present
    if ! crontab -l 2>/dev/null | grep -q "log_rotation.sh"; then
        (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
        log_message "✅ Log rotation cron job installed (every 6 hours)"
    else
        log_message "⚠️ Log rotation cron job already exists"
    fi
}

# Function to remove log rotation cron job
remove_log_rotation() {
    log_message "🗑️ Removing log rotation cron job..."
    
    # Remove the cron job
    crontab -l 2>/dev/null | grep -v "log_rotation.sh" | crontab -
    log_message "✅ Log rotation cron job removed"
}

# Function to show log rotation status
show_status() {
    log_message "📊 Log rotation status:"
    
    # Check if cron job exists
    if crontab -l 2>/dev/null | grep -q "log_rotation.sh"; then
        log_message "✅ Log rotation cron job is active"
        crontab -l | grep "log_rotation.sh"
    else
        log_message "❌ Log rotation cron job not found"
    fi
    
    # Show log file sizes
    log_message "📁 Current log file sizes:"
    for log_file in "${LOG_FILES[@]}"; do
        if [ -f "$log_file" ]; then
            size=$(stat -f%z "$log_file" 2>/dev/null || stat -c%s "$log_file" 2>/dev/null || echo 0)
            size_mb=$(echo "scale=2; $size / 1024 / 1024" | bc 2>/dev/null || echo "0")
            log_message "   - $log_file: ${size_mb} MB"
        else
            log_message "   - $log_file: Not found"
        fi
    done
}

# Main script logic
case "${1:-}" in
    "rotate")
        rotate_logs
        ;;
    "setup")
        setup_log_rotation
        ;;
    "remove")
        remove_log_rotation
        ;;
    "status")
        show_status
        ;;
    "manual")
        rotate_logs
        ;;
    *)
        echo "🤖 Gap Trade Bot - Log Rotation Script"
        echo "======================================"
        echo ""
        echo "Usage: $0 {rotate|setup|remove|status|manual}"
        echo ""
        echo "Commands:"
        echo "  rotate  - Rotate logs (delete old log files)"
        echo "  setup   - Install cron job for automatic rotation (every 6 hours)"
        echo "  remove  - Remove cron job for automatic rotation"
        echo "  status  - Show log rotation status and file sizes"
        echo "  manual  - Manually rotate logs now"
        echo ""
        echo "Log files rotated:"
        for log_file in "${LOG_FILES[@]}"; do
            echo "  - $log_file"
        done
        echo ""
        echo "Schedule: Every 6 hours (0, 6, 12, 18)"
        ;;
esac 