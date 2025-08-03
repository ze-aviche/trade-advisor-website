#!/usr/bin/env python3
"""
Test script for the complete sequential workflow including execution agent
"""

import asyncio
import os
from google.adk.session import InMemorySessionService
from google.adk.runner import Runner
from agents.gap_up_trade_workflow_agent import gap_up_trade_workflow_agent

async def test_complete_workflow():
    """Test the complete end-to-end trading workflow"""
    
    print("🚀 Testing Complete Gap-Up Trade Workflow")
    print("=" * 50)
    
    # Set up Google API key
    os.environ["GOOGLE_API_KEY"] = "YOUR_API_KEY"  # Replace with your actual API key
    
    # Create session service and runner
    session_service = InMemorySessionService()
    runner = Runner()
    
    # Create a session
    session_id = "test_workflow_session"
    session = await session_service.create_session(session_id)
    
    print("📋 Starting workflow with test message...")
    print("Message: 'Identify gap-up stocks and analyze them for trading opportunities'")
    print("-" * 50)
    
    # Run the workflow
    async for event in runner.run(
        agent=gap_up_trade_workflow_agent,
        session=session,
        message="Identify gap-up stocks and analyze them for trading opportunities"
    ):
        if hasattr(event, 'content') and event.content:
            print(f"📊 {event.content}")
            print("-" * 30)
    
    print("\n✅ Workflow test completed!")

def test_agent_imports():
    """Test that all agents can be imported correctly"""
    
    print("\n🧪 Testing Agent Imports")
    print("=" * 30)
    
    try:
        from agents.gap_up_trade_workflow_agent import gap_up_trade_workflow_agent
        print("✅ gap_up_trade_workflow_agent imported successfully")
        
        from agents.data_agent import data_agent
        print("✅ data_agent imported successfully")
        
        from agents.trade_planning_agent import trade_planning_agent
        print("✅ trade_planning_agent imported successfully")
        
        from agents.execution_agent import execution_agent
        print("✅ execution_agent imported successfully")
        
        print("\n✅ All agent imports successful!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")

if __name__ == "__main__":
    # Test imports first
    test_agent_imports()
    
    # Then test the workflow
    asyncio.run(test_complete_workflow()) 