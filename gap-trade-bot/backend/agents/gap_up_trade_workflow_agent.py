from google.adk.agents import LlmAgent, SequentialAgent
from agents.prompts.prompt_gap_up_listing_agent import GAP_UP_LISTING_AGENT_PROMPT
from api_helper.polygon_api_get_gap_ups import get_gap_up_list, get_ticker_details
from agents.data_agent import data_agent
from agents.trade_planning_agent import trade_planning_agent
from agents.execution_agent import execution_agent

# Gap-up identification agent - identifies potential gap-up stocks
gap_up_identification_agent = LlmAgent(
    name="gap_up_identification_agent",
    description="Identifies gap-up tickers using market APIs like Polygon and filters them based on criteria.",
    instruction=GAP_UP_LISTING_AGENT_PROMPT,
    model="gemini-2.5-pro",
    tools=[get_gap_up_list, get_ticker_details],
    output_key="identified_gap_up_stocks"
)

# Main workflow agent that orchestrates the complete trading pipeline
gap_up_trade_workflow_agent = SequentialAgent(
    name="gap_up_trade_workflow_agent",
    description="Complete end-to-end trading workflow: identifies gap-ups, analyzes patterns, plans trades, and executes them.",
    sub_agents=[
        gap_up_identification_agent,  # Step 1: Identify gap-up stocks
        data_agent,                   # Step 2: Analyze historical patterns and data
        trade_planning_agent       # Step 3: Plan trades based on analysis
                       # Step 4: Execute trades on Alpaca
    ]
) 