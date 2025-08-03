from google.adk.agents import LlmAgent
from agents.prompts.prompt_trade_planning_agent import TRADE_PLANNING_AGENT_PROMPT

# Trade Planning Agent - creates comprehensive trade plans
trade_planning_agent = LlmAgent(
    name="trade_planning_agent",
    description="Creates comprehensive trade plans based on historical analysis and pattern recognition",
    instruction=TRADE_PLANNING_AGENT_PROMPT,
    model="gemini-2.5-pro",
    output_key="trade_plan"
)