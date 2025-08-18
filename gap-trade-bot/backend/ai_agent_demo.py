#!/usr/bin/env python3
"""
Demo script for the Google AI Agent
This script demonstrates how to use the AI agent programmatically
"""

import os
import json
from dotenv import load_dotenv
from ai_agent import GoogleAIAgent

# Load environment variables
load_dotenv()

def demo_ai_agent():
    """Demonstrate the AI agent capabilities"""
    
    print("🤖 Google AI Agent Demo")
    print("=" * 60)
    
    # Check API key
    api_key = os.getenv('GOOGLE_AI_API_KEY')
    if not api_key or api_key == 'your_google_ai_api_key_here':
        print("❌ Please set your GOOGLE_AI_API_KEY in the .env file")
        return
    
    try:
        # Initialize the agent
        agent = GoogleAIAgent()
        print("✅ AI Agent initialized successfully\n")
        
        # Demo 1: Stock News
        print("📰 Demo 1: Stock News")
        print("-" * 30)
        result = agent.get_stock_news("AAPL", days=3)
        if result['success']:
            print(f"Found {result['news_count']} news items for AAPL:")
            for i, news in enumerate(result['news_items'][:3], 1):
                print(f"  {i}. {news['title']}")
                print(f"     {news['summary'][:100]}...")
                print()
        else:
            print(f"Error: {result['error']}")
        
        # Demo 2: Sentiment Analysis
        print("📊 Demo 2: Sentiment Analysis")
        print("-" * 30)
        text = "Apple's latest earnings report shows strong growth in iPhone sales and services revenue"
        result = agent.analyze_sentiment(text)
        if result['success']:
            analysis = result['analysis']
            print(f"Text: {text}")
            print(f"Sentiment: {analysis.get('sentiment', 'unknown')}")
            print(f"Confidence: {analysis.get('confidence', 'N/A')}")
            if 'trading_implications' in analysis:
                print(f"Trading Implications: {analysis['trading_implications']}")
        else:
            print(f"Error: {result['error']}")
        print()
        
        # Demo 3: Technical Analysis
        print("📈 Demo 3: Technical Analysis")
        print("-" * 30)
        result = agent.get_technical_analysis("MSFT")
        if result['success']:
            print(f"Found {result['total_insights']} technical insights for MSFT:")
            for i, insight in enumerate(result['technical_insights'][:2], 1):
                print(f"  {i}. {insight['title']}")
                print(f"     {insight['analysis'][:100]}...")
                print()
        else:
            print(f"Error: {result['error']}")
        
        # Demo 4: Earnings Calendar
        print("📅 Demo 4: Earnings Calendar")
        print("-" * 30)
        result = agent.get_earnings_calendar()
        if result['success']:
            print(f"Found {result['total_results']} earnings-related items:")
            for i, item in enumerate(result['earnings_info'][:2], 1):
                print(f"  {i}. {item['title']}")
                print(f"     {item['summary'][:100]}...")
                print()
        else:
            print(f"Error: {result['error']}")
        
        # Demo 5: Interactive Chat
        print("💬 Demo 5: Interactive Chat")
        print("-" * 30)
        print("Processing a complex query...")
        
        query = "What's the latest news about Tesla and how does it affect their stock price?"
        result = agent.process_message(query)
        
        if result['success']:
            print(f"Query: {query}")
            print(f"Tools used: {', '.join(result['tools_used'])}")
            print(f"Symbols analyzed: {', '.join(result['symbols_analyzed'])}")
            print("\nResponse:")
            print(result['response'])
        else:
            print(f"Error: {result['error']}")
        
        print("\n" + "=" * 60)
        print("🎉 Demo completed successfully!")
        print("\nThe AI Agent can now be used in your trading application.")
        
    except Exception as e:
        print(f"❌ Error during demo: {e}")

def interactive_demo():
    """Interactive demo where user can ask questions"""
    
    print("\n🎯 Interactive Demo Mode")
    print("=" * 60)
    print("You can now ask questions to the AI agent.")
    print("Type 'quit' to exit, 'help' for examples.\n")
    
    try:
        agent = GoogleAIAgent()
        
        while True:
            try:
                question = input("🤖 You: ").strip()
                
                if question.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                elif question.lower() == 'help':
                    print("\n💡 Example questions:")
                    print("  • Get latest news for AAPL")
                    print("  • Analyze sentiment for Tesla stock")
                    print("  • Show technical analysis for MSFT")
                    print("  • What are the upcoming earnings?")
                    print("  • How is the market performing today?")
                    print("  • Explain the current tech sector trends")
                    print()
                    continue
                elif not question:
                    continue
                
                print("🤔 AI is thinking...")
                result = agent.process_message(question)
                
                if result['success']:
                    print(f"\n🤖 AI: {result['response']}")
                    if result.get('tools_used'):
                        print(f"   Tools used: {', '.join(result['tools_used'])}")
                    if result.get('symbols_analyzed'):
                        print(f"   Symbols: {', '.join(result['symbols_analyzed'])}")
                else:
                    print(f"\n❌ Error: {result['error']}")
                
                print()
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                print()
                
    except Exception as e:
        print(f"❌ Failed to start interactive demo: {e}")

if __name__ == "__main__":
    print("🚀 Google AI Agent Demo Suite")
    print("=" * 60)
    
    # Run the automated demo
    demo_ai_agent()
    
    # Ask if user wants interactive demo
    try:
        choice = input("\nWould you like to try the interactive demo? (y/n): ").strip().lower()
        if choice in ['y', 'yes']:
            interactive_demo()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
