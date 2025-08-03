import asyncio
from api_helper.execute_trades_alpaca import (
    get_current_price,
    place_market_order,
    place_stop_order,
    place_limit_order,
    check_order_status,
    monitor_and_execute,
    _check_entry_criteria,
    _check_exit_criteria
)

def test_execution_functions():
    print("Testing Execution Functions")
    print("=" * 50)
    
    # Test 1: Get current price
    print("\n🧪 TEST 1: Get Current Price")
    price = get_current_price("AAPL")
    print(f"AAPL current price: ${price}")
    
    # Test 2: Example trade criteria (for demonstration)
    print("\n🧪 TEST 2: Trade Criteria Example")
    
    # Entry criteria from trade planning agent
    entry_criteria = {
        'price_target': 150.0,  # Enter when price goes above $150
        'direction': 'above',
        'qty': 10,
        'order_type': 'market'
    }
    
    # Exit criteria from trade planning agent
    exit_criteria = {
        'stop_loss': 145.0,     # Stop loss at $145
        'take_profit': 160.0,   # Take profit at $160
        'qty': 10
    }
    
    print("Entry Criteria:")
    print(f"  - Price Target: ${entry_criteria['price_target']}")
    print(f"  - Direction: {entry_criteria['direction']}")
    print(f"  - Quantity: {entry_criteria['qty']}")
    print(f"  - Order Type: {entry_criteria['order_type']}")
    
    print("\nExit Criteria:")
    print(f"  - Stop Loss: ${exit_criteria['stop_loss']}")
    print(f"  - Take Profit: ${exit_criteria['take_profit']}")
    print(f"  - Quantity: {exit_criteria['qty']}")
    
    # Test 3: Check criteria logic
    print("\n🧪 TEST 3: Criteria Logic")
    
    # Test entry criteria
    test_prices = [140, 150, 160]
    for price in test_prices:
        entry_met = _check_entry_criteria(price, entry_criteria)
        print(f"Price ${price}: Entry criteria met = {entry_met}")
    
    # Test exit criteria
    test_prices = [140, 145, 150, 160, 165]
    for price in test_prices:
        exit_met = _check_exit_criteria(price, exit_criteria)
        print(f"Price ${price}: Exit criteria met = {exit_met}")
    
    # Test 4: Simulate monitoring (without actual trading)
    print("\n🧪 TEST 4: Monitoring Simulation")
    print("Note: This is a simulation. No actual trades will be placed.")
    
    # Simulate current price monitoring
    simulated_prices = [148, 151, 155, 158, 161]  # Price progression
    
    entry_executed = False
    for i, price in enumerate(simulated_prices):
        print(f"\nStep {i+1}: Price = ${price}")
        
        # Check entry
        if not entry_executed:
            entry_met = _check_entry_criteria(price, entry_criteria)
            if entry_met:
                print(f"  ✅ Entry criteria met at ${price}")
                entry_executed = True
            else:
                print(f"  ⏳ Waiting for entry criteria...")
        
        # Check exit (if entry was made)
        if entry_executed:
            exit_met = _check_exit_criteria(price, exit_criteria)
            if exit_met:
                print(f"  ✅ Exit criteria met at ${price}")
                break
            else:
                print(f"  📊 Monitoring for exit...")
    
    print("\n✅ Execution functions tests completed!")

def test_with_planning_agent_recommendation():
    """
    Example of how to use execution functions with trade planning agent recommendations
    """
    print("\n" + "=" * 60)
    print("EXAMPLE: Integration with Trade Planning Agent")
    print("=" * 60)
    
    # Simulate recommendation from trade planning agent
    planning_recommendation = {
        'ticker': 'AAPL',
        'strategy': 'gap_up_breakout',
        'entry_criteria': {
            'price_target': 155.0,
            'direction': 'above',
            'qty': 5,
            'order_type': 'market',
            'reason': 'Breakout above resistance level'
        },
        'exit_criteria': {
            'stop_loss': 150.0,
            'take_profit': 165.0,
            'qty': 5,
            'reason': 'Risk management with 2:1 reward-to-risk ratio'
        },
        'confidence': 0.85,
        'expected_return': 0.065
    }
    
    print("Trade Planning Agent Recommendation:")
    print(f"  Ticker: {planning_recommendation['ticker']}")
    print(f"  Strategy: {planning_recommendation['strategy']}")
    print(f"  Confidence: {planning_recommendation['confidence']}")
    print(f"  Expected Return: {planning_recommendation['expected_return']:.1%}")
    
    print("\nEntry Criteria:")
    for key, value in planning_recommendation['entry_criteria'].items():
        print(f"  {key}: {value}")
    
    print("\nExit Criteria:")
    for key, value in planning_recommendation['exit_criteria'].items():
        print(f"  {key}: {value}")
    
    print(f"\n🚀 Ready to execute trade for {planning_recommendation['ticker']}")
    print("Note: Set up your Alpaca API keys to enable actual trading.")
    
    # Uncomment to start actual monitoring (requires API keys)
    # result = monitor_and_execute(
    #     planning_recommendation['ticker'],
    #     planning_recommendation['entry_criteria'],
    #     planning_recommendation['exit_criteria']
    # )
    # print(f"Execution result: {result}")

def test_agent_integration():
    """
    Test the execution agent integration
    """
    print("\n" + "=" * 60)
    print("TESTING: Execution Agent Integration")
    print("=" * 60)
    
    from agents.execution_agent import execution_agent
    
    print("✅ Execution Agent loaded successfully")
    print(f"Agent name: {execution_agent.name}")
    print(f"Agent description: {execution_agent.description}")
    print(f"Available tools: {len(execution_agent.tools)} tools")
    
    for i, tool in enumerate(execution_agent.tools):
        print(f"  Tool {i+1}: {tool.__name__}")

if __name__ == "__main__":
    test_execution_functions()
    test_with_planning_agent_recommendation()
    test_agent_integration() 