from google.adk.agents import LlmAgent
from agents.gap_up_trade_workflow_agent import gap_up_identification_agent

# Main trading advisor agent - this is the root agent that will be loaded by adk run
trading_advisor_agent = gap_up_identification_agent

# Root agent for ADK web interface compatibility
root_agent = gap_up_identification_agent