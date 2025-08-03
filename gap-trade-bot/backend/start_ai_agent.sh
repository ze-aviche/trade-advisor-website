#!/bin/bash

echo "🤖 AI Agent Integration Setup"
echo "============================"

# Check if Google API key is set
if [ -z "$GOOGLE_API_KEY" ] || [ "$GOOGLE_API_KEY" = "YOUR_GOOGLE_API_KEY" ]; then
    echo "❌ Google API key not configured"
    echo ""
    echo "To get a Google API key:"
    echo "1. Go to https://makersuite.google.com/app/apikey"
    echo "2. Create a new API key"
    echo "3. Set it as an environment variable:"
    echo "   export GOOGLE_API_KEY='your-api-key-here'"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "✅ Google API key is configured"

# Check if Python dependencies are installed
echo "📦 Checking dependencies..."
if ! python3 -c "import google.adk" 2>/dev/null; then
    echo "❌ Google ADK not installed"
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
else
    echo "✅ Dependencies are installed"
fi

# Test the AI Agent
echo "🧪 Testing AI Agent..."
python3 test_ai_agent.py

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 AI Agent is ready!"
    echo ""
    echo "To start the backend server:"
    echo "python3 app.py"
    echo ""
    echo "Then open http://localhost:3000 in your browser"
    echo "and go to the 'AI Agent' tab to start chatting."
else
    echo ""
    echo "❌ AI Agent test failed. Please check the errors above."
    exit 1
fi 