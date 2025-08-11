#!/bin/bash

# Linux Trading Bot Startup Script
# Handles environment setup and bot startup on Linux

echo "🚀 Starting Trading Bot on Linux..."
echo "=================================="

# Check if we're in the right directory
if [ ! -f "run_agent.py" ]; then
    echo "❌ Error: run_agent.py not found!"
    echo "Please run this script from the bot directory:"
    echo "cd gap-trade-bot/backend/bot"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to create virtual environment"
        echo "Please install python3-venv:"
        echo "sudo apt install python3-venv"
        exit 1
    fi
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if requirements are installed
if [ ! -f "venv/lib/python*/site-packages/flask" ]; then
    echo "📦 Installing requirements..."
    pip install --upgrade pip
    pip install -r requirements_linux.txt
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to install requirements"
        exit 1
    fi
fi

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export FLASK_ENV=development

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found"
    echo "Creating basic .env file..."
    cat > .env << EOF
# Linux Configuration
BROKER_TYPE=alpaca
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_ENDPOINT=https://paper-api.alpaca.markets
POLYGON_API_KEY=your_polygon_key_here

# Linux paths
LOG_PATH=/app/logs
DATA_PATH=/app/data
LOG_LEVEL=INFO
EOF
    echo "✅ Created .env file. Please update with your API keys."
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs data

# Fix permissions
echo "🔧 Fixing permissions..."
chmod +x *.py
chmod +x *.sh
chmod 644 *.db 2>/dev/null || true
chmod 644 *.json 2>/dev/null || true

# Check if port 5000 is available
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  Warning: Port 5000 is already in use"
    echo "Killing existing process..."
    sudo lsof -ti:5000 | xargs kill -9 2>/dev/null || true
fi

# Start the bot
echo "🤖 Starting trading bot..."
echo "Press Ctrl+C to stop the bot"
echo "=================================="

# Run the bot
python run_agent.py

echo "👋 Bot stopped."

