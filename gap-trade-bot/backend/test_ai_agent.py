#!/usr/bin/env python3
"""
Test script for the Google AI Agent
Run this script to verify the AI agent is working correctly
"""

import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_ai_agent():
    """Test the AI agent functionality"""
    
    print("🤖 Testing Google AI Agent...")
    print("=" * 50)
    
    # Check if API key is set
    api_key = os.getenv('GOOGLE_AI_API_KEY')
    if not api_key or api_key == 'your_google_ai_api_key_here':
        print("❌ Error: GOOGLE_AI_API_KEY not set in .env file")
        print("Please set your Google AI API key in the .env file")
        return False
    
    try:
        # Import the AI agent
        from ai_agent import GoogleAIAgent
        print("✅ AI Agent module imported successfully")
        
        # Initialize the agent
        agent = GoogleAIAgent()
        print("✅ AI Agent initialized successfully")
        
        # Test basic search functionality
        print("\n🔍 Testing web search...")
        search_result = agent.google_search("AAPL stock news", num_results=3)
        if search_result['success']:
            print(f"✅ Search successful: {search_result['total_results']} results found")
            for i, result in enumerate(search_result['results'][:2], 1):
                print(f"  {i}. {result['title']}")
        else:
            print(f"❌ Search failed: {search_result['error']}")
        
        # Test stock news functionality
        print("\n📰 Testing stock news...")
        news_result = agent.get_stock_news("AAPL", days=3)
        if news_result['success']:
            print(f"✅ Stock news successful: {news_result['news_count']} news items found")
        else:
            print(f"❌ Stock news failed: {news_result['error']}")
        
        # Test sentiment analysis
        print("\n📊 Testing sentiment analysis...")
        sentiment_result = agent.analyze_sentiment("Apple stock is performing well with strong earnings")
        if sentiment_result['success']:
            print("✅ Sentiment analysis successful")
            if 'analysis' in sentiment_result and isinstance(sentiment_result['analysis'], dict):
                sentiment = sentiment_result['analysis'].get('sentiment', 'unknown')
                print(f"  Sentiment: {sentiment}")
        else:
            print(f"❌ Sentiment analysis failed: {sentiment_result['error']}")
        
        # Test message processing
        print("\n💬 Testing message processing...")
        message_result = agent.process_message("Get latest news for TSLA")
        if message_result['success']:
            print("✅ Message processing successful")
            print(f"  Tools used: {message_result.get('tools_used', [])}")
            print(f"  Symbols analyzed: {message_result.get('symbols_analyzed', [])}")
            print(f"  Response length: {len(message_result['response'])} characters")
        else:
            print(f"❌ Message processing failed: {message_result['error']}")
        
        print("\n" + "=" * 50)
        print("🎉 All tests completed successfully!")
        print("The AI Agent is ready to use.")
        return True
        
    except ImportError as e:
        print(f"❌ Error importing AI Agent: {e}")
        print("Make sure all dependencies are installed: pip install -r requirements.txt")
        return False
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_api_endpoints():
    """Test the API endpoints"""
    
    print("\n🌐 Testing API endpoints...")
    print("=" * 50)
    
    try:
        import requests
        
        base_url = "http://localhost:5000"
        
        # Test start session endpoint
        print("Testing /api/ai-agent/start-session...")
        response = requests.post(f"{base_url}/api/ai-agent/start-session")
        if response.status_code == 200:
            data = response.json()
            if data['success']:
                session_id = data['data']['session_id']
                print(f"✅ Session started: {session_id}")
                
                # Test chat endpoint
                print("Testing /api/ai-agent/chat...")
                chat_response = requests.post(f"{base_url}/api/ai-agent/chat", 
                                            json={"message": "Hello", "session_id": session_id})
                if chat_response.status_code == 200:
                    chat_data = chat_response.json()
                    if chat_data['success']:
                        print("✅ Chat endpoint working")
                    else:
                        print(f"❌ Chat failed: {chat_data['error']}")
                else:
                    print(f"❌ Chat endpoint error: {chat_response.status_code}")
            else:
                print(f"❌ Session start failed: {data['error']}")
        else:
            print(f"❌ Session endpoint error: {response.status_code}")
        
        print("✅ API endpoint tests completed")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the backend is running:")
        print("   python app.py")
        return False
    except Exception as e:
        print(f"❌ API test error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Google AI Agent Test Suite")
    print("=" * 50)
    
    # Test AI agent functionality
    agent_success = test_ai_agent()
    
    # Test API endpoints (only if agent test passed)
    if agent_success:
        api_success = test_api_endpoints()
    else:
        api_success = False
    
    print("\n" + "=" * 50)
    if agent_success and api_success:
        print("🎉 All tests passed! Your AI Agent is ready to use.")
        print("\nNext steps:")
        print("1. Start the backend server: python app.py")
        print("2. Open the frontend: http://localhost:5000")
        print("3. Navigate to the AI Agent tab")
        print("4. Start a session and try asking questions!")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print("\nTroubleshooting:")
        print("1. Make sure GOOGLE_AI_API_KEY is set in .env")
        print("2. Install dependencies: pip install -r requirements.txt")
        print("3. Check the setup guide: AI_AGENT_SETUP.md")
