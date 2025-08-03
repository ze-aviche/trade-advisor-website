from google.adk.agents import LlmAgent
from api_helper.execute_trades_alpaca import (
    execute_trade_simple,
    place_simple_market_order,
    place_simple_limit_order,
    place_simple_stop_order,
    get_current_price_simple,
    check_order_status,
    add_trade_to_continuous_monitoring,
    get_continuous_monitoring_status
)
from agents.prompts.prompt_execution_agent import EXECUTION_AGENT_PROMPT

# Execution Agent - executes trades on Alpaca
execution_agent = LlmAgent(
    name="execution_agent",
    description="Executes trades on Alpaca paper trading platform based on recommendations from the Trade Planning Agent",
    instruction=EXECUTION_AGENT_PROMPT,
    model="gemini-2.5-pro",
    tools=[
        execute_trade_simple,
        place_simple_market_order,
        place_simple_limit_order,
        place_simple_stop_order,
        get_current_price_simple,
        check_order_status,
        add_trade_to_continuous_monitoring,
        get_continuous_monitoring_status
    ],
    output_key="trade_execution_results"
)