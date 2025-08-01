#!/bin/bash
"""
Setup script for daily gap-up capture cron job
Runs the gap-up capture script every weekday at 9:30 AM ET (market open)
"""

# Get the absolute path to the script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CAPTURE_SCRIPT="$SCRIPT_DIR/daily_gap_up_capture.py"

# Create the cron job entry
# Run every weekday (Monday-Friday) at 9:30 AM ET
CRON_JOB="30 9 * * 1-5 cd $PROJECT_DIR/backend && python3 $CAPTURE_SCRIPT >> $PROJECT_DIR/logs/daily_gap_up_capture.log 2>&1"

echo "🎯 Setting up daily gap-up capture cron job..."
echo "📋 Cron job will run: $CRON_JOB"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "daily_gap_up_capture.py"; then
    echo "⚠️ Cron job already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "daily_gap_up_capture.py" | crontab -
fi

# Add the new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Cron job added successfully!"
echo ""
echo "📊 Current cron jobs:"
crontab -l
echo ""
echo "📋 The script will run every weekday at 9:30 AM ET"
echo "📋 Logs will be saved to: $PROJECT_DIR/logs/daily_gap_up_capture.log"
echo ""
echo "🔧 To manually run the script:"
echo "   cd $PROJECT_DIR && python3 $CAPTURE_SCRIPT"
echo ""
echo "🔧 To remove the cron job:"
echo "   crontab -e"
echo "   (then delete the line with daily_gap_up_capture.py)" 