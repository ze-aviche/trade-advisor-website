from google.adk.agents import LlmAgent
from agents.prompts.prompt_data_agent import DATA_AGENT_PROMPT
from api_helper.wrapper_functions import (
    analyze_tool,
    get_intraday_volume_analysis_tool,
    get_price_action_patterns_tool,
    get_historical_pattern_analysis_tool
)

# Data Analysis Agent - analyzes historical patterns and data
data_agent = LlmAgent(
    name="data_agent",
    description="Fetches comprehensive historical market data and analyzes multiple trading patterns for gap-up stocks.",
    instruction=DATA_AGENT_PROMPT,
    model="gemini-2.5-pro",
    tools=[
        analyze_tool,
        get_intraday_volume_analysis_tool,
        get_price_action_patterns_tool,
        get_historical_pattern_analysis_tool
    ],
    output_key="comprehensive_pattern_analysis"
)