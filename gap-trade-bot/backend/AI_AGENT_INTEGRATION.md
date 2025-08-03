# AI Agent Integration

This document describes the integration of the Google LLM AI Agent into the Trading Advisor website.

## Overview

The AI Agent provides intelligent trading assistance using Google's Gemini 2.5 Pro model. It can help with:
- Gap-up trading strategies
- Market analysis
- Trade planning
- Historical pattern analysis
- Risk management

## Files Added

### Backend Files
- `agents/` - Complete agent system from Google LLM project
- `api_helper/` - API helper functions for market data
- `run_agent.py` - Original agent runner script
- `test_ai_agent.py` - Test script for integration

### API Endpoints
- `GET /api/ai-agent/status` - Check AI Agent status
- `POST /api/ai-agent/start-session` - Start new AI session
- `POST /api/ai-agent/chat` - Send message to AI Agent

## Setup Instructions

### 1. Install Dependencies
```bash
cd gap-trade-bot/backend
pip install -r requirements.txt
```

### 2. Configure Google API Key
Set your Google API key as an environment variable:
```bash
export GOOGLE_API_KEY="your-google-api-key-here"
```

To get a Google API key:
1. Go to https://makersuite.google.com/app/apikey
2. Create a new API key
3. Set it as an environment variable

### 3. Test the Integration
```bash
cd gap-trade-bot/backend
python test_ai_agent.py
```

### 4. Start the Backend
```bash
cd gap-trade-bot/backend
python app.py
```

## Usage

### Frontend Integration
The AI Agent is accessible through the "AI Agent" tab in the web interface. Users can:

1. **Start Session**: Click "Start Session" to begin a new AI conversation
2. **Send Messages**: Type questions about trading strategies
3. **Get Responses**: Receive intelligent responses from the AI Agent

### Example Queries
- "What is gap-up trading?"
- "How do I identify good gap-up opportunities?"
- "What are the risks of gap-up trading?"
- "Can you analyze TSLA for gap-up patterns?"
- "What's the best entry strategy for gap-ups?"

## Agent Architecture

The AI Agent uses a sequential workflow:

1. **Gap-Up Identification Agent**: Identifies potential gap-up stocks
2. **Data Analysis Agent**: Analyzes historical patterns and data
3. **Trade Planning Agent**: Creates comprehensive trade plans
4. **Execution Agent**: Executes trades (optional)

## Troubleshooting

### Common Issues

1. **Google API Key Not Configured**
   - Error: "Google API key not configured"
   - Solution: Set GOOGLE_API_KEY environment variable

2. **Dependencies Missing**
   - Error: "AI Agent dependencies not available"
   - Solution: Install requirements: `pip install -r requirements.txt`

3. **Import Errors**
   - Error: "Failed to import AI Agent"
   - Solution: Check that all agent files are in the correct location

### Testing
Run the test script to verify everything works:
```bash
python test_ai_agent.py
```

## API Response Format

### Status Endpoint
```json
{
  "success": true,
  "data": {
    "available": true,
    "configured": true,
    "message": "AI Agent is ready"
  }
}
```

### Chat Endpoint
```json
{
  "success": true,
  "data": {
    "response": "AI Agent response here...",
    "timestamp": "2024-01-01T12:00:00"
  }
}
```

## Security Notes

- The AI Agent requires a valid Google API key
- API calls are made to Google's servers
- No sensitive trading data is sent to external services
- All responses are processed locally

## Performance

- Response times depend on Google's API
- Typical response time: 2-5 seconds
- Rate limits apply based on Google API quota
- Consider implementing caching for repeated queries

## Future Enhancements

- Add conversation history persistence
- Implement streaming responses
- Add more specialized trading agents
- Integrate with real-time market data
- Add backtesting capabilities 