# Google AI Agent Setup Guide

This guide will help you set up the Google AI Agent for stock market analysis and news gathering in your trading advisor application.

## Prerequisites

1. Python 3.8 or higher
2. Google AI API key
3. Internet connection for web searches and API calls

## Setup Instructions

### 1. Get Google AI API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated API key

### 2. Configure Environment Variables

1. Copy the template file:
   ```bash
   cp backend/ai_env_template.txt backend/.env
   ```

2. Edit the `.env` file and add your API key:
   ```
   GOOGLE_AI_API_KEY=your_actual_api_key_here
   ```

### 3. Install Dependencies

The required dependencies are already included in `requirements.txt`. Install them:

```bash
cd backend
pip install -r requirements.txt
```

### 4. Test the Setup

1. Start the backend server:
   ```bash
   python app.py
   ```

2. Open the frontend in your browser:
   ```
   http://localhost:5000
   ```

3. Navigate to the "AI Agent" tab
4. Click "Start Session"
5. Try asking a question like "Get latest news for AAPL"

## Features

The Google AI Agent provides the following capabilities:

### 🔍 Web Search
- Search for real-time information about stocks, markets, and companies
- Uses DuckDuckGo API for free, reliable search results

### 📰 Stock News
- Get recent news for specific stock symbols
- Filter news by relevance and time period
- Analyze news sentiment

### 📊 Market Analysis
- Technical analysis insights
- Market sentiment analysis
- Earnings calendar information

### 🤖 AI-Powered Responses
- Natural language processing
- Context-aware responses
- Multi-tool integration

## Available Tools

1. **Google Search**: General web searches for market information
2. **Stock News**: Get recent news for specific stocks
3. **Market Data**: Basic market data (requires additional API integration)
4. **Sentiment Analysis**: Analyze text sentiment using Google AI
5. **Earnings Calendar**: Get upcoming earnings information
6. **Technical Analysis**: Get technical analysis insights

## Usage Examples

### Stock News
```
"Get latest news for AAPL"
"What's happening with Tesla stock?"
"Show me recent news about Microsoft"
```

### Market Analysis
```
"Analyze market sentiment for TSLA"
"Get technical analysis for MSFT"
"What's the market outlook for tech stocks?"
```

### General Queries
```
"What are the top gainers today?"
"Show me upcoming earnings calendar"
"Explain the current market conditions"
```

## Configuration Options

You can customize the AI Agent behavior by modifying the `.env` file:

- `GOOGLE_AI_MODEL`: Choose between different AI models
- `GOOGLE_AI_TEMPERATURE`: Control response creativity (0.0-1.0)
- `SEARCH_MAX_RESULTS`: Number of search results to fetch
- `NEWS_DAYS_BACK`: How many days of news to look back
- `ENABLE_CACHE`: Enable/disable result caching

## Troubleshooting

### Common Issues

1. **API Key Error**
   - Ensure your Google AI API key is correctly set in `.env`
   - Verify the API key is valid and has proper permissions

2. **Import Errors**
   - Make sure all dependencies are installed: `pip install -r requirements.txt`
   - Check Python version compatibility

3. **Search Failures**
   - Verify internet connectivity
   - Check if DuckDuckGo API is accessible

4. **Slow Responses**
   - The AI Agent uses multiple tools which can take time
   - Consider enabling caching for better performance

### Error Messages

- **"AI Agent module not available"**: Check dependencies and imports
- **"Google AI API key is required"**: Set the API key in `.env`
- **"Search failed"**: Check internet connectivity

## Security Notes

- Never commit your API key to version control
- Use environment variables for sensitive configuration
- The AI Agent includes safety settings to prevent harmful content
- All web searches are logged for debugging purposes

## Performance Tips

1. Enable caching for frequently requested information
2. Use specific stock symbols for better results
3. Keep questions focused and specific
4. Monitor API usage to stay within limits

## Support

If you encounter issues:

1. Check the browser console for error messages
2. Review the backend logs for detailed error information
3. Verify all configuration settings
4. Test with simple queries first

## Future Enhancements

Planned improvements:

- Real-time market data integration
- Advanced technical analysis tools
- Portfolio analysis capabilities
- Custom trading strategy recommendations
- Multi-language support
- Voice interaction
