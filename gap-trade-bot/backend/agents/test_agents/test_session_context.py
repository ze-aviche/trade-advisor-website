import asyncio
import os
import dotenv
from google.adk.agents import SequentialAgent, LlmAgent
from google.adk.sessions import InMemorySessionService, Session
from google.adk.runners import Runner
from google.genai.types import Content, Part
from google.adk.tools import google_search
import google.generativeai as genai

dotenv.load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

APP_NAME = "sentence_maker"
USER_ID = "avinash"
SESSION_ID = "google_synonyms_session_01"


agent1 = LlmAgent(
    name = "synonyms_agent", 
    description = "exmaple agent to test how sessions work",
    instruction = "uses google_Search to give synonyms of words",
    model = "gemini-2.0-flash",
    output_key="google_synonyms"
)

agent2 = LlmAgent(
    name = "sentence_agent", 
    description = "make a sentence using the synonyms",
    instruction = "uses google_synonyms to make a sentence",
    model = "gemini-2.0-flash",
    output_key="sentence"
)

simple_agent = SequentialAgent(
    name = "sentence_maker", 
    description = "make a sentence using the synonyms",
    sub_agents = [agent1, agent2], 
    
)

async def main():
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    runner = Runner(app_name=APP_NAME, agent=simple_agent, session_service=session_service)

    def run_agent(user_message):
        content = Content(parts=[Part(text=user_message)])
        
        for event in runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content): 
            print(f"Event Author: {event.author}")
            if event.actions:
                print(f"Event Actions: {event.actions}")

            if event.content and event.content.parts:
                print(f"Content: {event.content}")
                if event.content.parts[0].text:
                    continue
                    #print(f"Content Parts: {event.content.parts[0].text}")
            if event.get_function_calls():
                print(f"Type: Tool Call Request")
                    
            elif event.get_function_responses():
                print(f"Type: Tool Call Response")
            # elif event.is_final_response():
            #     print(f"Type: Final Response")

    run_agent("Hello! How are you? Frame few sentences using the word Everest")

if __name__ == "__main__":
    asyncio.run(main())
