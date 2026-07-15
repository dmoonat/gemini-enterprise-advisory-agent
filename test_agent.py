import asyncio
import logging
import time
from dotenv import load_dotenv

# Load environment variables from .env before initializing agent
load_dotenv(".env")

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from ge_agent.agent import root_agent
from google.genai import types

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TEST_CASES = [
    {
        "id": "TC_01_RELEASE_NOTES_30_DAYS",
        "name": "Release Notes Query with User Input Interval (30 Days)",
        "query": "Show me the Gemini Enterprise Agent Platform release notes and updates published in the last 30 days."
    },
    {
        "id": "TC_02_RELEASE_NOTES_90_DAYS",
        "name": "Release Notes Query with User Input Interval (90 Days)",
        "query": "Can you check for any Gemini Enterprise Agent Platform release notes over the last 90 days?"
    },
    {
        "id": "TC_03_DOCUMENTATION_GET_STARTED",
        "name": "Gemini Enterprise Documentation Lookup",
        "query": "How do I get started with Gemini Enterprise? What are the key setup steps or features?"
    },
    {
        "id": "TC_04_OUT_OF_SCOPE",
        "name": "Out-of-Scope Query Enforcement",
        "query": "What is the recommended temperature and recipe for baking a chocolate cake?"
    }
]

async def run_test_case(runner: Runner, session_service: InMemorySessionService, test_case: dict, user_id: str = "test_user"):
    session_id = f"session_{test_case['id']}_{int(time.time())}"
    await session_service.create_session(
        app_name="ge_agent_test", user_id=user_id, session_id=session_id
    )
    
    print("=" * 80)
    print(f"Executing Test: [{test_case['id']}] {test_case['name']}")
    print(f"Prompt / Query: \"{test_case['query']}\"")
    print("-" * 80)
    
    start_time = time.time()
    response_text = ""
    
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part.from_text(text=test_case["query"])]
            ),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text + "\n"
                    elif part.function_call:
                        print(f"[Tool Called]: {part.function_call.name} with args: {part.function_call.args}")
                    elif part.function_response:
                        print(f"[Tool Response from {part.function_response.name}]")
        
        duration = time.time() - start_time
        print("\n--- Agent Response ---")
        print(response_text.strip())
        print(f"\nCompleted in {duration:.2f} seconds.")
    except Exception as e:
        print(f"\n[ERROR] Test Case Failed with Exception: {e}")
    print("=" * 80 + "\n")

async def main():
    print("Initializing InMemorySessionService & ADK Runner...")
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent, app_name="ge_agent_test", session_service=session_service
    )
    print("Agent Initialization Successful. Running Test Suite...\n")
    
    for tc in TEST_CASES:
        await run_test_case(runner, session_service, tc)

if __name__ == "__main__":
    asyncio.run(main())
