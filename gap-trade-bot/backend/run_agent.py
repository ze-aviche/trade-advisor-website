#!/usr/bin/env python3
"""
Simple script to run the trading advisor agent directly
"""
import asyncio
import os
from google.adk.sessions import InMemorySessionService
from google.adk import Runner
from google.genai.types import Content
from agents.agent import trading_advisor_agent

async def main():
    # Check for API key
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key or api_key == "YOUR_GOOGLE_API_KEY":
        print("❌ Error: Please set your GOOGLE_API_KEY environment variable")
        print("Example: export GOOGLE_API_KEY='your-api-key-here'")
        print("\nTo get an API key:")
        print("1. Go to https://makersuite.google.com/app/apikey")
        print("2. Create a new API key")
        print("3. Set it as: export GOOGLE_API_KEY='your-actual-key'")
        return
    
    # Create session service
    session_service = InMemorySessionService()
    
    # Create runner
    runner = Runner(
        app_name="trading_advisor",
        agent=trading_advisor_agent,
        session_service=session_service
    )
    
    # Create session
    session = await session_service.create_session(
        app_name="trading_advisor",
        user_id="user",
        session_id="trading_session"
    )
    
    print("🤖 Trading Advisor Agent")
    print("=" * 50)
    print("AI-powered automated trading system for gap-up day trading")
    print("Type 'quit' to exit")
    print()
    
    while True:
        try:
            # Get user input
            user_input = input("You: ")
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if not user_input.strip():
                continue
            
            # Create content object for the message
            new_message = Content(parts=[{"text": user_input}])
            
            # Run the agent
            print("\n🤖 Agent is thinking...")
            async for event in runner.run_async(
                user_id="user",
                session_id="trading_session",
                new_message=new_message
            ):
                if hasattr(event, 'content'):
                    print(f"Agent: {event.content}")
                else:
                    print(f"Event: {event}")
            
            print()
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            error_msg = str(e)
            if "API key not valid" in error_msg:
                print("❌ Error: Invalid Google API key")
                print("Please check your GOOGLE_API_KEY environment variable")
                print("Make sure it's a valid API key from https://makersuite.google.com/app/apikey")
            elif "quota" in error_msg.lower():
                print("❌ Error: API quota exceeded")
                print("Please check your Google AI API usage limits")
            else:
                print(f"❌ Error: {error_msg}")
            print("Please try again or type 'quit' to exit")

if __name__ == "__main__":
    asyncio.run(main()) 