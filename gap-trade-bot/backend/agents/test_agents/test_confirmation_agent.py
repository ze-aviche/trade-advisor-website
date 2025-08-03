import asyncio
from confirmation_agent import ConfirmationAgent

async def test_confirmation_agent():
    print("Testing Confirmation Agent")
    print("=" * 50)
    
    # Test 1: Basic confirmation
    print("\n🧪 TEST 1: Basic Confirmation")
    confirm_agent1 = ConfirmationAgent(
        previous_agent_name="Data Collection Agent",
        next_agent_name="Analysis Agent"
    )
    
    # Simulate results from previous agent
    results1 = {
        "tickers_found": ["AAPL", "MSFT", "GOOGL"],
        "data_points": 1500,
        "processing_time": "2.3 seconds"
    }
    
    should_proceed1 = await confirm_agent1.confirm_and_proceed(
        previous_results=results1,
        user_message="Successfully collected market data for 3 major stocks."
    )
    
    print(f"Result: {'Proceed' if should_proceed1 else 'Stop'}")
    
    # Test 2: No results confirmation
    print("\n🧪 TEST 2: No Results Confirmation")
    confirm_agent2 = ConfirmationAgent(
        previous_agent_name="Validation Agent",
        next_agent_name="Execution Agent"
    )
    
    should_proceed2 = await confirm_agent2.confirm_and_proceed(
        user_message="Data validation completed successfully."
    )
    
    print(f"Result: {'Proceed' if should_proceed2 else 'Stop'}")

if __name__ == "__main__":
    asyncio.run(test_confirmation_agent()) 