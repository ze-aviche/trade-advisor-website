import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# Configure logging
logger = logging.getLogger(__name__)

class GoogleAIAgent:
    """Google AI Agent for stock market analysis and news gathering"""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Google AI Agent"""
        self.api_key = api_key or os.getenv('GOOGLE_AI_API_KEY')  # Fixed: correct env var name
        if not self.api_key:
            raise ValueError("Google AI API key is required. Set GOOGLE_AI_API_KEY environment variable.")
        
        # Configure Google AI
        genai.configure(api_key=self.api_key)
        
        # Initialize the model
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Configure safety settings
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }
        
        # Initialize conversation history
        self.conversation_history = []
        
        # Available tools
        self.tools = {
            'google_search': self.google_search,
            'get_stock_news': self.get_stock_news,
            'get_market_data': self.get_market_data,
            'analyze_sentiment': self.analyze_sentiment,
            'get_earnings_calendar': self.get_earnings_calendar,
            'get_technical_analysis': self.get_technical_analysis
        }
        
        logger.info("Google AI Agent initialized successfully")

    def google_search(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        """Perform a web search using DuckDuckGo Instant Answer API"""
        try:
            # Use DuckDuckGo Instant Answer API as a free alternative to Google Search
            url = "https://api.duckduckgo.com/"
            params = {
                'q': query,
                'format': 'json',
                'no_html': '1',
                'skip_disambig': '1'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            # Extract abstract if available
            if data.get('Abstract'):
                results.append({
                    'title': data.get('Heading', 'Abstract'),
                    'snippet': data.get('Abstract'),
                    'url': data.get('AbstractURL', ''),
                    'source': 'DuckDuckGo Abstract'
                })
            
            # Extract related topics
            for topic in data.get('RelatedTopics', [])[:num_results-1]:
                if isinstance(topic, dict) and topic.get('Text'):
                    results.append({
                        'title': topic.get('Text', '').split(' - ')[0] if ' - ' in topic.get('Text', '') else 'Related Topic',
                        'snippet': topic.get('Text', ''),
                        'url': topic.get('FirstURL', ''),
                        'source': 'DuckDuckGo Related'
                    })
            
            return {
                'success': True,
                'query': query,
                'results': results[:num_results],
                'total_results': len(results)
            }
            
        except Exception as e:
            logger.error(f"Error in google_search: {e}")
            return {
                'success': False,
                'error': str(e),
                'query': query,
                'results': []
            }

    def get_stock_news(self, symbol: str, days: int = 7) -> Dict[str, Any]:
        """Get recent news for a stock symbol"""
        try:
            query = f"{symbol} stock news last {days} days"
            search_results = self.google_search(query, num_results=8)
            
            if not search_results['success']:
                return search_results
            
            # Filter and enhance results
            news_results = []
            for result in search_results['results']:
                if any(keyword in result['title'].lower() or keyword in result['snippet'].lower() 
                      for keyword in ['news', 'earnings', 'report', 'announcement', 'update']):
                    news_results.append(result)
            
            return {
                'success': True,
                'symbol': symbol,
                'news_count': len(news_results),
                'news': news_results,
                'search_query': query
            }
            
        except Exception as e:
            logger.error(f"Error in get_stock_news: {e}")
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol,
                'news': []
            }

    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data for a stock symbol (placeholder for real API integration)"""
        try:
            # This is a placeholder - in a real implementation, you'd integrate with
            # a market data API like Alpha Vantage, Yahoo Finance, or Polygon
            query = f"{symbol} stock price market data"
            search_results = self.google_search(query, num_results=3)
            
            return {
                'success': True,
                'symbol': symbol,
                'message': f"Market data for {symbol} would be fetched from a real API",
                'search_results': search_results.get('results', []),
                'note': 'This is a placeholder. Integrate with a real market data API for live prices.'
            }
            
        except Exception as e:
            logger.error(f"Error in get_market_data: {e}")
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol
            }

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text using Google AI"""
        try:
            prompt = f"""
            Analyze the sentiment of the following text and provide:
            1. Overall sentiment (positive, negative, neutral)
            2. Confidence score (0-100)
            3. Key emotional indicators
            4. Brief explanation
            
            Text: {text}
            
            Respond in JSON format:
            {{
                "sentiment": "positive/negative/neutral",
                "confidence": 85,
                "emotional_indicators": ["optimistic", "confident"],
                "explanation": "Brief explanation of the sentiment analysis"
            }}
            """
            
            response = self.model.generate_content(prompt)
            
            # Try to parse JSON response
            try:
                result = json.loads(response.text)
                return {
                    'success': True,
                    'text': text[:100] + "..." if len(text) > 100 else text,
                    'analysis': result
                }
            except json.JSONDecodeError:
                # If JSON parsing fails, return the raw response
                return {
                    'success': True,
                    'text': text[:100] + "..." if len(text) > 100 else text,
                    'analysis': {
                        'sentiment': 'neutral',
                        'confidence': 50,
                        'emotional_indicators': [],
                        'explanation': response.text
                    }
                }
                
        except Exception as e:
            logger.error(f"Error in analyze_sentiment: {e}")
            return {
                'success': False,
                'error': str(e),
                'text': text[:100] + "..." if len(text) > 100 else text
            }

    def get_earnings_calendar(self, symbol: str = None) -> Dict[str, Any]:
        """Get earnings calendar information"""
        try:
            if symbol:
                query = f"{symbol} earnings calendar 2024"
            else:
                query = "stock earnings calendar this week"
            
            search_results = self.google_search(query, num_results=6)
            
            return {
                'success': True,
                'symbol': symbol,
                'earnings_info': search_results.get('results', []),
                'search_query': query
            }
            
        except Exception as e:
            logger.error(f"Error in get_earnings_calendar: {e}")
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol,
                'earnings_info': []
            }

    def get_technical_analysis(self, symbol: str) -> Dict[str, Any]:
        """Get technical analysis insights for a stock"""
        try:
            query = f"{symbol} technical analysis chart patterns"
            search_results = self.google_search(query, num_results=5)
            
            return {
                'success': True,
                'symbol': symbol,
                'technical_analysis': search_results.get('results', []),
                'search_query': query
            }
            
        except Exception as e:
            logger.error(f"Error in get_technical_analysis: {e}")
            return {
                'success': False,
                'error': str(e),
                'symbol': symbol,
                'technical_analysis': []
            }

    def process_message(self, message: str, session_id: str = None) -> Dict[str, Any]:
        """Process a user message and return AI response with tool usage"""
        try:
            # Add user message to history
            self.conversation_history.append({
                'role': 'user',
                'content': message,
                'timestamp': datetime.now().isoformat(),
                'session_id': session_id
            })
            
            # Analyze message to determine which tools to use
            tools_used = []
            symbols_analyzed = []
            tool_results = {}
            
            # Simple keyword-based tool selection (in a real implementation, you'd use AI to determine this)
            message_lower = message.lower()
            
            # Check for stock symbols (simple pattern matching)
            import re
            stock_symbols = re.findall(r'\b[A-Z]{1,5}\b', message.upper())
            symbols_analyzed = [sym for sym in stock_symbols if len(sym) >= 2 and len(sym) <= 5]
            
            # Determine which tools to use based on keywords
            if any(word in message_lower for word in ['search', 'find', 'look up']):
                tools_used.append('google_search')
                tool_results['google_search'] = self.google_search(message, num_results=3)
            
            if any(word in message_lower for word in ['news', 'latest', 'update']) and symbols_analyzed:
                tools_used.append('get_stock_news')
                for symbol in symbols_analyzed[:2]:  # Limit to 2 symbols
                    tool_results[f'get_stock_news_{symbol}'] = self.get_stock_news(symbol)
            
            if any(word in message_lower for word in ['price', 'market', 'data']) and symbols_analyzed:
                tools_used.append('get_market_data')
                for symbol in symbols_analyzed[:2]:
                    tool_results[f'get_market_data_{symbol}'] = self.get_market_data(symbol)
            
            if any(word in message_lower for word in ['sentiment', 'feel', 'mood', 'tone']):
                tools_used.append('analyze_sentiment')
                tool_results['analyze_sentiment'] = self.analyze_sentiment(message)
            
            if any(word in message_lower for word in ['earnings', 'quarterly', 'financial']):
                tools_used.append('get_earnings_calendar')
                symbol = symbols_analyzed[0] if symbols_analyzed else None
                tool_results['get_earnings_calendar'] = self.get_earnings_calendar(symbol)
            
            if any(word in message_lower for word in ['technical', 'chart', 'pattern', 'indicator']):
                tools_used.append('get_technical_analysis')
                for symbol in symbols_analyzed[:2]:
                    tool_results[f'get_technical_analysis_{symbol}'] = self.get_technical_analysis(symbol)
            
            # Generate AI response based on tool results
            response_prompt = f"""
            You are a helpful AI assistant for stock market analysis. A user asked: "{message}"
            
            Tools used: {', '.join(tools_used) if tools_used else 'None'}
            Symbols analyzed: {', '.join(symbols_analyzed) if symbols_analyzed else 'None'}
            
            Tool results:
            {json.dumps(tool_results, indent=2) if tool_results else 'No tools were used'}
            
            Please provide a helpful, informative response based on the available information.
            If tools were used, summarize the key findings. If no tools were used, provide general guidance.
            Keep your response conversational and informative.
            """
            
            response = self.model.generate_content(response_prompt)
            
            # Add AI response to history
            self.conversation_history.append({
                'role': 'assistant',
                'content': response.text,
                'timestamp': datetime.now().isoformat(),
                'session_id': session_id,
                'tools_used': tools_used,
                'symbols_analyzed': symbols_analyzed
            })
            
            return {
                'success': True,
                'response': response.text,
                'tools_used': tools_used,
                'symbols_analyzed': symbols_analyzed,
                'tool_results': tool_results,
                'session_id': session_id
            }
            
        except Exception as e:
            logger.error(f"Error in process_message: {e}")
            return {
                'success': False,
                'error': str(e),
                'response': f"I encountered an error while processing your request: {str(e)}"
            }

    def get_conversation_history(self, session_id: str = None) -> List[Dict[str, Any]]:
        """Get conversation history, optionally filtered by session_id"""
        if session_id:
            return [msg for msg in self.conversation_history if msg.get('session_id') == session_id]
        return self.conversation_history

    def clear_conversation_history(self, session_id: str = None) -> bool:
        """Clear conversation history, optionally filtered by session_id"""
        try:
            if session_id:
                self.conversation_history = [msg for msg in self.conversation_history if msg.get('session_id') != session_id]
            else:
                self.conversation_history = []
            logger.info("Conversation history cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing conversation history: {e}")
            return False
